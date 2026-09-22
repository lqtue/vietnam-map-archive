import {
  expect,
  test,
  request as playwrightRequest,
  type APIRequestContext,
} from '@playwright/test';
import { createClient, type Session } from '@supabase/supabase-js';
import { createServerClient } from '@supabase/ssr';
import { loadSchema, unsupportedKeywords, validate } from './schemaCheck';
import { placeCoreKey } from '../src/lib/core/utils/placeKey';

/**
 * Write-path smokes (roadmap-record A5). Unlike smoke.spec.ts these DO write rows, so
 * they refuse to run against anything but a loopback Supabase and delete what
 * they create.
 *
 * Covered: the OCR-review API route (staff-gated server write), footprint
 * submission and story publishing (both RLS-gated client writes), the
 * negative case that an anonymous caller cannot reach the staff route, and
 * label search (mig 065: fuzzy hit, draft-map labels hidden from anonymous).
 *
 * ponytail: the client writes go through supabase-js on the same contract the
 * app's data layer uses, not through the drawing UI — canvas-dragging tests
 * would cost far more than the coverage they add. Add those when a UI wiring
 * bug actually escapes.
 */

const SUPABASE_URL = process.env.PUBLIC_SUPABASE_URL!;
const ANON_KEY = process.env.PUBLIC_SUPABASE_ANON_KEY!;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY!;

const TEST_EMAIL = 'write-smoke@vma.test';
const TEST_PASSWORD = 'write-smoke-password';
const TEST_MAP_ALLMAPS_ID = 'f0f0f0f0f0f0f0f0';
const TEST_WORKER_TOKEN = 'write-smoke-worker-token';

if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:|\/|$)/.test(SUPABASE_URL ?? '')) {
  throw new Error(
    `write.spec.ts writes rows and must not run against ${SUPABASE_URL}. Point .env.test at a local stack (supabase start).`
  );
}

const admin = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });

let session: Session;
let mapId: string;
let staffRequest: APIRequestContext;
/** Everything this file inserts, so afterAll can take it back out. */
const created = {
  runIds: [] as string[],
  footprintIds: [] as string[],
  storyIds: [] as string[],
  jobIds: [] as string[],
  mapIds: [] as string[],
  seriesKeys: [] as string[],
};

test.beforeAll(async () => {
  const auth = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  const { data, error } = await auth.auth.signInWithPassword({
    email: TEST_EMAIL,
    password: TEST_PASSWORD,
  });
  if (error || !data.session) {
    throw new Error(
      `Could not sign in as ${TEST_EMAIL} — run: node --env-file=.env.test scripts/seed-test-db.mjs (${error?.message})`
    );
  }
  session = data.session;

  const { data: map, error: mapErr } = await admin
    .from('maps')
    .select('id')
    .eq('allmaps_id', TEST_MAP_ALLMAPS_ID)
    .single();
  if (mapErr || !map) throw new Error('Fixture map missing — run scripts/seed-test-db.mjs');
  mapId = map.id;

  // The app authenticates server routes by cookie, so let @supabase/ssr write
  // the cookies itself (name, chunking and encoding all match that way).
  const jar: { name: string; value: string }[] = [];
  const ssr = createServerClient(SUPABASE_URL, ANON_KEY, {
    cookies: { getAll: () => jar, setAll: (cookies) => cookies.forEach((c) => jar.push(c)) },
  });
  await ssr.auth.setSession(session);

  staffRequest = await playwrightRequest.newContext({
    baseURL: 'http://localhost:5199',
    storageState: {
      cookies: jar.map((c) => ({
        name: c.name,
        value: c.value,
        domain: 'localhost',
        path: '/',
        expires: -1,
        httpOnly: false,
        secure: false,
        sameSite: 'Lax' as const,
      })),
      origins: [],
    },
  });
});

test.afterAll(async () => {
  for (const runId of created.runIds)
    await admin.from('ocr_extractions').delete().eq('run_id', runId);
  for (const id of created.footprintIds)
    await admin.from('footprint_submissions').delete().eq('id', id);
  for (const id of created.storyIds) await admin.from('stories').delete().eq('id', id);
  for (const id of created.jobIds) await admin.from('pipeline_jobs').delete().eq('id', id);
  for (const key of created.seriesKeys)
    await admin.from('series_sheets').delete().eq('series_key', key);
  for (const id of created.mapIds) await admin.from('maps').delete().eq('id', id);
  await staffRequest?.dispose();
});

test('staff can create and validate an OCR bbox through the review API', async () => {
  const runId = `write-smoke-${Date.now()}`;
  created.runIds.push(runId);

  const post = await staffRequest.post(`/api/admin/maps/${mapId}/ocr-review`, {
    data: {
      run_id: runId,
      global_x: 100,
      global_y: 200,
      global_w: 50,
      global_h: 20,
      text: 'Rue Catinat',
      category: 'street_name',
    },
  });
  expect(post.ok(), await post.text()).toBe(true);
  const { id } = await post.json();
  expect(id).toBeTruthy();

  const patch = await staffRequest.patch(`/api/admin/maps/${mapId}/ocr-review`, {
    data: { id, status: 'validated', text: 'Rue Catinat' },
  });
  expect(patch.ok(), await patch.text()).toBe(true);

  const get = await staffRequest.get(`/api/admin/maps/${mapId}/ocr-review?run_id=${runId}`);
  expect(get.ok()).toBe(true);
  const { extractions } = await get.json();
  const row = extractions.find((e: { id: string }) => e.id === id);
  expect(row.status).toBe('validated');
  expect(row.text_validated).toBe('Rue Catinat');
  expect(row.validated_at).toBeTruthy();
  // A drawn box is upright, so it is its own label rectangle (mig 076).
  expect(row.label_w).toBe(50);
  expect(row.label_h).toBe(20);
});

test('turning a label writes its own rectangle, not just the box', async () => {
  const runId = `write-smoke-obb-${Date.now()}`;
  created.runIds.push(runId);

  const post = await staffRequest.post(`/api/admin/maps/${mapId}/ocr-review`, {
    data: { run_id: runId, global_x: 0, global_y: 0, global_w: 200, global_h: 20 },
  });
  expect(post.ok(), await post.text()).toBe(true);
  const { id } = await post.json();

  // What the editor sends after a turn: the label unchanged, the box around it
  // recomputed. The two must come back exactly as sent — deriving the size from
  // the box is what the columns exist to avoid.
  const patch = await staffRequest.patch(`/api/admin/maps/${mapId}/ocr-review`, {
    data: {
      id,
      rotation_deg: 45,
      label_w: 200,
      label_h: 20,
      global_x: -27.78,
      global_y: 66.22,
      global_w: 155.56,
      global_h: 155.56,
    },
  });
  expect(patch.ok(), await patch.text()).toBe(true);

  const get = await staffRequest.get(`/api/admin/maps/${mapId}/ocr-review?run_id=${runId}`);
  const { extractions } = await get.json();
  const row = extractions.find((e: { id: string }) => e.id === id);
  expect(row.rotation_deg).toBe(45);
  expect(row.label_w).toBe(200);
  expect(row.label_h).toBe(20);
  expect(row.global_w).toBeCloseTo(155.56, 2);

  const bad = await staffRequest.patch(`/api/admin/maps/${mapId}/ocr-review`, {
    data: { id, label_w: 'wide' },
  });
  expect(bad.status()).toBe(400);
});

test('an anonymous caller cannot reach the staff review API', async () => {
  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  const res = await anon.get(`/api/admin/maps/${mapId}/ocr-review`);
  expect(res.status()).toBe(401);
  await anon.dispose();
});

test('a signed-in user can submit a footprint and it lands as submitted', async () => {
  const asUser = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  await asUser.auth.setSession(session);

  const { data, error } = await asUser
    .from('footprint_submissions')
    .insert({
      map_id: mapId,
      user_id: session.user.id,
      pixel_polygon: [
        [10, 10],
        [30, 10],
        [30, 30],
        [10, 30],
      ],
      name: 'write-smoke building',
      feature_type: 'building',
    })
    .select('id, status')
    .single();

  expect(error, error?.message).toBeNull();
  created.footprintIds.push(data!.id);
  expect(data!.status).toBe('submitted');

  // The map is public, so the row is readable without a session (RLS mig 038).
  const anon = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  const { data: readBack } = await anon
    .from('footprint_submissions')
    .select('id')
    .eq('id', data!.id)
    .single();
  expect(readBack?.id).toBe(data!.id);
});

test('publishing a story makes it readable by anonymous visitors', async () => {
  const asUser = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  await asUser.auth.setSession(session);

  const { data: story, error } = await asUser
    .from('stories')
    .insert({ user_id: session.user.id, title: 'Write-smoke tour', mode: 'guided' })
    .select('id, status')
    .single();
  expect(error, error?.message).toBeNull();
  created.storyIds.push(story!.id);
  expect(story!.status).toBe('draft');

  const anon = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  const draftRead = await anon.from('stories').select('id').eq('id', story!.id).maybeSingle();
  expect(draftRead.data).toBeNull();

  // Publishing submits for review; an author cannot approve their own story.
  const { error: subErr } = await asUser
    .from('stories')
    .update({ status: 'submitted' })
    .eq('id', story!.id);
  expect(subErr, subErr?.message).toBeNull();
  expect(
    (await anon.from('stories').select('id').eq('id', story!.id).maybeSingle()).data
  ).toBeNull();

  const selfApprove = await asUser
    .from('stories')
    .update({ status: 'approved' })
    .eq('id', story!.id);
  expect(selfApprove.error, 'an author must not be able to approve their own story').not.toBeNull();

  // A mod decides, through the API, and only then is it public.
  const review = await staffRequest.patch('/api/admin/stories', {
    data: { id: story!.id, status: 'approved' },
  });
  expect(review.ok(), await review.text()).toBe(true);

  const publishedRead = await anon.from('stories').select('id').eq('id', story!.id).maybeSingle();
  expect(publishedRead.data?.id).toBe(story!.id);

  const { data: stamped } = await admin
    .from('stories')
    .select('reviewed_by, reviewed_at')
    .eq('id', story!.id)
    .single();
  expect(stamped!.reviewed_by).toBe(session.user.id);
  expect(stamped!.reviewed_at).toBeTruthy();
});

test('running OCR enqueues one job, and only one at a time', async () => {
  const post = await staffRequest.post(`/api/admin/maps/${mapId}/ocr`, {
    data: { run_id: `write-smoke-${Date.now()}`, tile_size: 2400, overlap: 600 },
  });
  expect(post.status(), await post.text()).toBe(202);
  const { job_id, status } = await post.json();
  created.jobIds.push(job_id);
  expect(status).toBe('queued');

  // idx_pipeline_jobs_one_live: a second click must not queue a duplicate run.
  const again = await staffRequest.post(`/api/admin/maps/${mapId}/ocr`, { data: {} });
  expect(again.status()).toBe(409);

  // Filtered by kind: publishing a map queues hosting jobs too (mig 058).
  const { data: jobs } = await admin
    .from('pipeline_jobs')
    .select('id, kind, payload')
    .eq('map_id', mapId)
    .eq('kind', 'ocr');
  expect(jobs).toHaveLength(1);
  // The worker builds its command line from this payload, so the defaults matter.
  expect((jobs![0].payload as { tile_size: number; auto: boolean }).tile_size).toBe(2400);
  expect((jobs![0].payload as { tile_size: number; auto: boolean }).auto).toBe(true);

  // The one-live-job index is per (kind, map), so leaving this queued would
  // block the next test from enqueuing its own.
  await admin.from('pipeline_jobs').delete().eq('map_id', mapId).eq('kind', 'ocr');
});

test('a saved triage round-trips and steers the queued job', async () => {
  const triage = {
    neatline: [10, 20, 3000, 2000],
    tile_size: 1800,
    overlap: 200,
    tile_overrides: { '0_0_1800_1800': 'skip' },
    saved_at: new Date().toISOString(),
  };

  const patch = await staffRequest.patch(`/api/admin/maps/${mapId}`, { data: { triage } });
  expect(patch.status(), await patch.text()).toBe(200);

  const { data: saved } = await admin.from('maps').select('triage').eq('id', mapId).single();
  expect(saved!.triage).toMatchObject(triage);

  // A non-object must drop rather than land: `asObject` in mapFields.ts is what
  // stops a stray string becoming a payload the worker then splices into argv.
  // With nothing left to write the PATCH is a bad request, not a server fault.
  const bad = await staffRequest.patch(`/api/admin/maps/${mapId}`, { data: { triage: 'nope' } });
  expect(bad.status()).toBe(400);
  const { data: still } = await admin.from('maps').select('triage').eq('id', mapId).single();
  expect(still!.triage).toMatchObject(triage);

  // The point of saving it: the neatline and grid reach the job the worker runs.
  const post = await staffRequest.post(`/api/admin/maps/${mapId}/ocr`, {
    data: {
      run_id: `triage-smoke-${Date.now()}`,
      neatline: triage.neatline,
      tile_size: triage.tile_size,
      overlap: triage.overlap,
      tile_overrides: triage.tile_overrides,
      model: 'gemini-2.5-flash-lite',
    },
  });
  expect(post.status(), await post.text()).toBe(202);
  const { job_id } = await post.json();
  created.jobIds.push(job_id);

  const { data: job } = await admin
    .from('pipeline_jobs')
    .select('payload')
    .eq('id', job_id)
    .single();
  const payload = job!.payload as Record<string, unknown>;
  expect(payload.neatline).toEqual(triage.neatline);
  expect(payload.tile_size).toBe(1800);
  expect(payload.tile_overrides).toEqual(triage.tile_overrides);
  expect(payload.model).toBe('gemini-2.5-flash-lite');

  await admin.from('pipeline_jobs').delete().eq('id', job_id);
  await admin.from('maps').update({ triage: {} }).eq('id', mapId);
});

test('a worker key claims a job and reports back through /api/pipeline', async () => {
  const runId = `worker-smoke-${Date.now()}`;
  created.runIds.push(runId);

  const { data: job, error: jobErr } = await admin
    .from('pipeline_jobs')
    .insert({ kind: 'ocr', map_id: mapId, payload: { run_id: runId } })
    .select('id')
    .single();
  expect(jobErr, jobErr?.message).toBeNull();
  created.jobIds.push(job!.id);

  const asWorker = await playwrightRequest.newContext({
    baseURL: 'http://localhost:5199',
    extraHTTPHeaders: { Authorization: `Bearer ${TEST_WORKER_TOKEN}` },
  });

  const claim = await asWorker.post('/api/pipeline/claim', {
    data: { kinds: ['ocr'], worker: 'write-smoke-box' },
  });
  expect(claim.ok(), await claim.text()).toBe(true);
  const claimed = (await claim.json()).job;
  expect(claimed.id).toBe(job!.id);
  expect(claimed.status).toBe('claimed');
  expect(claimed.payload.run_id).toBe(runId);

  // One round trip carries the rows, the stage and the job's own outcome.
  const results = await asWorker.post('/api/pipeline/results', {
    data: {
      job_id: job!.id,
      status: 'done',
      result: { returncode: 0 },
      extractions: [
        {
          map_id: mapId,
          run_id: runId,
          tile_x: 0,
          tile_y: 0,
          tile_w: 512,
          tile_h: 512,
          global_x: 10,
          global_y: 20,
          global_w: 30,
          global_h: 12,
          category: 'street_name',
          text: 'Boulevard Bonard',
          confidence: 0.9,
          model: 'write-smoke',
          prompt: 'write-smoke',
        },
      ],
    },
  });
  expect(results.ok(), await results.text()).toBe(true);

  const { data: finished } = await admin
    .from('pipeline_jobs')
    .select('status, result, finished_at')
    .eq('id', job!.id)
    .single();
  expect(finished!.status).toBe('done');
  expect(finished!.finished_at).toBeTruthy();

  const { data: rows } = await admin.from('ocr_extractions').select('text').eq('run_id', runId);
  expect(rows).toHaveLength(1);

  // Nothing wrote a stage: map_pipeline_status is a view (mig 056), so closing
  // the job is what advances it.
  const { data: stage } = await admin
    .from('map_pipeline_status')
    .select('stage, ocr_run_id')
    .eq('map_id', mapId)
    .single();
  expect(stage!.stage).toBe('ocr_done');
  expect(stage!.ocr_run_id).toBe(runId);

  await asWorker.dispose();
});

test('only the human stages can be set by hand', async () => {
  const derived = await staffRequest.patch(`/api/admin/maps/${mapId}/pipeline`, {
    data: { stage: 'ocr_done' },
  });
  expect(derived.status()).toBe(400);

  const marked = await staffRequest.patch(`/api/admin/maps/${mapId}/pipeline`, {
    data: { stage: 'reviewed' },
  });
  expect(marked.ok(), await marked.text()).toBe(true);
  expect((await marked.json()).reviewed_at).toBeTruthy();

  await staffRequest.patch(`/api/admin/maps/${mapId}/pipeline`, { data: { stage: 'idle' } });
  await admin.from('map_review_marks').delete().eq('map_id', mapId);
});

test('the pipeline endpoints refuse a missing or unknown worker token', async () => {
  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  expect((await anon.post('/api/pipeline/claim', { data: { kinds: ['ocr'] } })).status()).toBe(401);

  const wrong = await playwrightRequest.newContext({
    baseURL: 'http://localhost:5199',
    extraHTTPHeaders: { Authorization: 'Bearer not-a-real-token' },
  });
  expect((await wrong.post('/api/pipeline/results', { data: { job_id: mapId } })).status()).toBe(
    401
  );

  await anon.dispose();
  await wrong.dispose();
});

test('reviewing a footprint moves it out of the queue exactly once', async () => {
  const { data: fp, error: fpErr } = await admin
    .from('footprint_submissions')
    .insert({
      map_id: mapId,
      user_id: session.user.id,
      pixel_polygon: [
        [0, 0],
        [10, 0],
        [10, 10],
      ],
      feature_type: 'building',
      status: 'needs_review',
      source: 'sam-auto',
    })
    .select('id')
    .single();
  expect(fpErr, fpErr?.message).toBeNull();
  created.footprintIds.push(fp!.id);

  const approve = await staffRequest.patch('/api/admin/footprints', {
    data: {
      id: fp!.id,
      status: 'approved',
      review_tags: ['boundary_too_wide', 'needs_split'],
      review_note: 'A parcel contains two buildings.',
      pixel_polygon: [
        [0, 0],
        [12, 0],
        [12, 12],
      ],
    },
  });
  expect(approve.ok(), await approve.text()).toBe(true);

  const { data: reviewed } = await admin
    .from('footprint_submissions')
    .select('status, source, review_tags, review_note, reviewed_by, reviewed_at')
    .eq('id', fp!.id)
    .single();
  // `approved` is what /api/export/footprints filters on. This used to assert
  // `submitted`, which is the inbox the row was already in — so nothing in the
  // archive could ever reach the state the export reads (migration 090).
  expect(reviewed!.status).toBe('approved');
  // An edited polygon is machine output a human fixed, and exports care.
  expect(reviewed!.source).toBe('sam-corrected');
  expect(reviewed!.review_tags).toEqual(['boundary_too_wide', 'needs_split']);
  expect(reviewed!.review_note).toBe('A parcel contains two buildings.');
  expect(reviewed!.reviewed_by).toBe(session.user.id);
  expect(reviewed!.reviewed_at).toBeTruthy();

  // A decided row leaves the queue exactly once: a second verdict is refused
  // rather than silently applied.
  const again = await staffRequest.patch('/api/admin/footprints', {
    data: { id: fp!.id, status: 'rejected' },
  });
  expect(again.status()).toBe(409);
});

test('a volunteer trace is reviewable, not only machine output', async () => {
  // The review queue is two states. `submitted` is where /contribute/trace puts
  // a hand-drawn polygon, and set_footprint_status used to match `needs_review`
  // alone — so every volunteer trace in the archive was permanently unreviewable
  // and the panel answered 409 on a row it had just listed. 46 of them sat on
  // the 1882 cadastral like that.
  const { data: fp, error: fpErr } = await admin
    .from('footprint_submissions')
    .insert({
      map_id: mapId,
      user_id: session.user.id,
      pixel_polygon: [
        [0, 0],
        [8, 0],
        [8, 8],
      ],
      feature_type: 'building',
      status: 'submitted',
      source: 'volunteer',
    })
    .select('id')
    .single();
  expect(fpErr, fpErr?.message).toBeNull();
  created.footprintIds.push(fp!.id);

  const approve = await staffRequest.patch('/api/admin/footprints', {
    data: { id: fp!.id, status: 'approved' },
  });
  expect(approve.ok(), await approve.text()).toBe(true);

  const { data: reviewed } = await admin
    .from('footprint_submissions')
    .select('status, source')
    .eq('id', fp!.id)
    .single();
  expect(reviewed!.status).toBe('approved');
  // Untouched geometry stays a volunteer trace rather than becoming corrected.
  expect(reviewed!.source).toBe('volunteer');
});

test('submitted is an inbox, not a verdict', async () => {
  const { data: fp } = await admin
    .from('footprint_submissions')
    .insert({
      map_id: mapId,
      user_id: session.user.id,
      pixel_polygon: [
        [0, 0],
        [4, 0],
        [4, 4],
      ],
      feature_type: 'building',
      status: 'needs_review',
      source: 'sam-auto',
    })
    .select('id')
    .single();
  created.footprintIds.push(fp!.id);

  const res = await staffRequest.patch('/api/admin/footprints', {
    data: { id: fp!.id, status: 'submitted' },
  });
  expect(res.status()).toBe(400);
});

test('publishing a map queues its hosting jobs, once', async () => {
  const { data: draft, error: draftErr } = await admin
    .from('maps')
    .insert({
      allmaps_id: `pub${Date.now()}`.slice(0, 16),
      name: 'Publish-smoke fixture',
      status: 'draft',
      // Both jobs are wanted here, so the fixture has to earn both: an upstream
      // annotation to mirror (georef_done) and imagery not yet on our host.
      georef_done: true,
      iiif_image: 'https://example.invalid/iiif/publish-smoke',
    })
    .select('id')
    .single();
  expect(draftErr, draftErr?.message).toBeNull();

  const { data: quiet } = await admin.from('pipeline_jobs').select('id').eq('map_id', draft!.id);
  expect(quiet).toHaveLength(0); // a draft queues nothing

  await admin.from('maps').update({ status: 'public' }).eq('id', draft!.id);

  const { data: queued } = await admin.from('pipeline_jobs').select('kind').eq('map_id', draft!.id);
  expect(queued!.map((j) => j.kind).sort()).toEqual(['mirror_annotation', 'tile_to_r2']);

  // Re-publishing must not pile up duplicates while the first pair is live.
  await admin.from('maps').update({ status: 'draft' }).eq('id', draft!.id);
  await admin.from('maps').update({ status: 'featured' }).eq('id', draft!.id);
  const { data: still } = await admin.from('pipeline_jobs').select('id').eq('map_id', draft!.id);
  expect(still).toHaveLength(2);

  await admin.from('maps').delete().eq('id', draft!.id); // cascades to the jobs
});

test('publishing queues neither job when neither would accomplish anything', async () => {
  // The shape of the 62 drafts: never georeferenced, scan already served from
  // our own host. Migration 064 stops both jobs; before it, publishing these
  // queued a doomed mirror and a redundant re-tile apiece.
  const { data: draft } = await admin
    .from('maps')
    .insert({
      allmaps_id: `noop${Date.now()}`.slice(0, 16),
      name: 'Publish-smoke no-op fixture',
      status: 'draft',
      georef_done: false,
      iiif_image: 'https://iiif.maparchive.vn/iiif/publish-smoke-noop',
    })
    .select('id')
    .single();

  await admin.from('maps').update({ status: 'public' }).eq('id', draft!.id);

  const { data: queued } = await admin.from('pipeline_jobs').select('kind').eq('map_id', draft!.id);
  expect(queued).toHaveLength(0);

  // Georeferencing it later is what earns the mirror.
  await admin.from('maps').update({ status: 'draft' }).eq('id', draft!.id);
  await admin.from('maps').update({ georef_done: true }).eq('id', draft!.id);
  await admin.from('maps').update({ status: 'public' }).eq('id', draft!.id);

  const { data: after } = await admin.from('pipeline_jobs').select('kind').eq('map_id', draft!.id);
  expect(after!.map((j) => j.kind)).toEqual(['mirror_annotation']);

  await admin.from('maps').delete().eq('id', draft!.id);
});

test('finishing the georeference of an already-published map queues the mirror', async () => {
  // The sync-georef path (mig 080): a volunteer georeferences a map that is
  // already public, so only `georef_done` moves. Under 058+064 the trigger
  // returned early on an unchanged status and the mirror was never queued, so
  // the map served its georeference from allmaps.org forever.
  const { data: draft } = await admin
    .from('maps')
    .insert({
      allmaps_id: `flip${Date.now()}`.slice(0, 16),
      name: 'Georef-flip fixture',
      status: 'draft',
      georef_done: false,
      // Off our host on purpose: publishing earns the tile job, which lets the
      // assertions below prove the flip does *not* earn a second one.
      iiif_image: 'https://example.invalid/iiif/georef-flip',
    })
    .select('id')
    .single();

  await admin.from('maps').update({ status: 'public' }).eq('id', draft!.id);

  const { data: onPublish } = await admin
    .from('pipeline_jobs')
    .select('id, kind')
    .eq('map_id', draft!.id);
  expect(onPublish!.map((j) => j.kind)).toEqual(['tile_to_r2']); // not georeferenced yet

  // Close the tile job out, so the one-live-job index cannot be what suppresses
  // a re-queue — only the trigger's own publish-path gate can.
  await admin.from('pipeline_jobs').update({ status: 'done' }).eq('id', onPublish![0].id);

  await admin.from('maps').update({ georef_done: true }).eq('id', draft!.id);

  const { data: afterFlip } = await admin
    .from('pipeline_jobs')
    .select('kind, status')
    .eq('map_id', draft!.id);
  expect(afterFlip!.filter((j) => j.status === 'queued').map((j) => j.kind)).toEqual([
    'mirror_annotation',
  ]);
  expect(afterFlip!.filter((j) => j.kind === 'tile_to_r2')).toHaveLength(1); // tiles did not move

  await admin.from('maps').delete().eq('id', draft!.id);
});

test('the server-side executor only takes the kinds it can run', async () => {
  const { data: job } = await admin
    .from('pipeline_jobs')
    .insert({ kind: 'ocr', map_id: mapId, payload: { run_id: `exec-${Date.now()}` } })
    .select('id')
    .single();
  created.jobIds.push(job!.id);

  const asWorker = await playwrightRequest.newContext({
    baseURL: 'http://localhost:5199',
    extraHTTPHeaders: { Authorization: `Bearer ${TEST_WORKER_TOKEN}` },
  });

  // ocr has real compute behind it: the worker runs it and reports results.
  const wrongKind = await asWorker.post('/api/pipeline/execute', { data: { job_id: job!.id } });
  expect(wrongKind.status()).toBe(400);

  const missing = await asWorker.post('/api/pipeline/execute', {
    data: { job_id: '00000000-0000-4000-8000-000000000000' },
  });
  expect(missing.status()).toBe(404);

  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  expect((await anon.post('/api/pipeline/execute', { data: { job_id: job!.id } })).status()).toBe(
    401
  );

  await asWorker.dispose();
  await anon.dispose();
  await admin.from('pipeline_jobs').delete().eq('id', job!.id);
});

test('the share page is server-rendered and hides drafts', async () => {
  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });

  // No JavaScript runs here: this is what a link-preview crawler sees.
  const res = await anon.get(`/catalog/${mapId}`);
  expect(res.status()).toBe(200);
  const html = await res.text();
  expect(html).toContain('og:title');
  expect(html).toContain('Write-smoke fixture map');
  // The page links onward by slug, not by uuid (mig 088) — the readable address
  // is the one a reader copies out of this page.
  const { data: fixture } = await admin.from('maps').select('slug').eq('id', mapId).single();
  expect(html).toContain(`/explore?map=${fixture!.slug}`);

  const { data: draft } = await admin
    .from('maps')
    .insert({
      allmaps_id: `shr${Date.now()}`.slice(0, 16),
      name: 'Share-smoke draft',
      status: 'draft',
    })
    .select('id')
    .single();

  // A draft is not published, so its link must not resolve for anyone.
  expect((await anon.get(`/catalog/${draft!.id}`)).status()).toBe(404);

  await admin.from('maps').delete().eq('id', draft!.id);
  await anon.dispose();
});

test('tracing submits through the API, which stamps the author', async () => {
  const res = await staffRequest.post('/api/contribute/footprints', {
    data: {
      map_id: mapId,
      pixel_polygon: [
        [1, 1],
        [5, 1],
        [5, 5],
      ],
      name: 'api-traced building',
      // A body that tried to attribute the trace to someone else must not win.
      user_id: '00000000-0000-4000-8000-000000000000',
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  const { id } = await res.json();
  created.footprintIds.push(id);

  const { data: row } = await admin
    .from('footprint_submissions')
    .select('user_id, source, status')
    .eq('id', id)
    .single();
  expect(row!.user_id).toBe(session.user.id);
  // 'volunteer' is the schema's word for hand-traced; 'manual' was never valid.
  expect(row!.source).toBe('volunteer');
  expect(row!.status).toBe('submitted');

  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  const rejected = await anon.post('/api/contribute/footprints', {
    data: {
      map_id: mapId,
      pixel_polygon: [
        [0, 0],
        [1, 1],
      ],
    },
  });
  expect(rejected.status()).toBe(401);
  await anon.dispose();
});

test('a published map must be georeferenceable', async () => {
  // Neither annotation_url nor allmaps_id: nothing to warp with, so publishing
  // is refused (mig 062) rather than shipping a map that cannot render.
  const { data: draft } = await admin
    .from('maps')
    .insert({ name: 'Ungeoreferenced fixture', status: 'draft' })
    .select('id')
    .single();

  const { error: pubErr } = await admin
    .from('maps')
    .update({ status: 'public' })
    .eq('id', draft!.id);
  expect(pubErr?.message ?? '').toContain('maps_public_needs_georef');

  // With an Allmaps id it is publishable, even before the annotation is mirrored.
  await admin
    .from('maps')
    .update({ allmaps_id: `geo${Date.now()}`.slice(0, 16) })
    .eq('id', draft!.id);
  const { error: okErr } = await admin
    .from('maps')
    .update({ status: 'public' })
    .eq('id', draft!.id);
  expect(okErr, okErr?.message).toBeNull();

  await admin.from('maps').delete().eq('id', draft!.id);
});

test('a draft map is invisible to an anonymous reader, visible once signed in', async () => {
  const { data: draft } = await admin
    .from('maps')
    .insert({
      allmaps_id: `rls${Date.now()}`.slice(0, 16),
      name: 'RLS-smoke draft',
      status: 'draft',
    })
    .select('id')
    .single();

  // The publishable key ships in every client bundle, so "anonymous" here is
  // "anyone on the internet". Before migration 063 this returned the row.
  const anon = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  const { data: unauthed } = await anon.from('maps').select('id').eq('id', draft!.id);
  expect(unauthed).toEqual([]);

  // A signed-in volunteer still needs drafts: /contribute/georef selects them
  // by status, and the digitalize and trace pickers are mostly unpublished maps.
  const signedIn = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  await signedIn.auth.signInWithPassword({ email: TEST_EMAIL, password: TEST_PASSWORD });
  const { data: authed } = await signedIn.from('maps').select('id').eq('id', draft!.id);
  expect(authed).toHaveLength(1);

  // Published maps stay readable without an account.
  const { data: published } = await anon.from('maps').select('id').eq('id', mapId);
  expect(published).toHaveLength(1);

  await admin.from('maps').delete().eq('id', draft!.id);
});

test("label search finds a typo'd label on a public map and hides draft-map labels from anonymous", async () => {
  const runId = `write-smoke-labels-${Date.now()}`;
  created.runIds.push(runId);

  const { data: draft, error: draftErr } = await admin
    .from('maps')
    .insert({ name: 'Write-smoke draft map', status: 'draft', year: 1901 })
    .select('id')
    .single();
  expect(draftErr, draftErr?.message).toBeNull();
  created.mapIds.push(draft!.id);

  const row = (map_id: string, text: string, tile_y: number) => ({
    map_id,
    run_id: runId,
    tile_x: 0,
    tile_y,
    tile_w: 100,
    tile_h: 100,
    global_x: 10,
    global_y: 20,
    global_w: 50,
    global_h: 10,
    text,
    category: 'street',
    confidence: 0.9,
  });
  const { error: insErr } = await admin
    .from('ocr_extractions')
    .insert([row(mapId, 'Rue de Khánh-Hội', 0), row(draft!.id, 'Khanh Hoi (draft)', 1)]);
  expect(insErr, insErr?.message).toBeNull();

  // Anonymous: one-letter typo still hits, the draft map's label does not appear.
  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  const res = await anon.get('/api/search?q=khan%20hoy&include=labels');
  expect(res.ok(), await res.text()).toBe(true);
  const { labels } = await res.json();
  const texts = labels.map((l: { text: string }) => l.text);
  expect(texts).toContain('Rue de Khánh-Hội');
  expect(texts).not.toContain('Khanh Hoi (draft)');
  const hit = labels.find((l: { text: string }) => l.text === 'Rue de Khánh-Hội');
  expect(hit.map_id).toBe(mapId);
  expect(hit.bbox).toEqual([10, 20, 50, 10]);
  await anon.dispose();

  // Staff see the draft map's label too.
  const staff = await staffRequest.get('/api/search?q=khanh%20hoi&include=labels');
  expect(staff.ok()).toBe(true);
  const staffTexts = (await staff.json()).labels.map((l: { text: string }) => l.text);
  expect(staffTexts).toContain('Khanh Hoi (draft)');

  // And the raw table no longer leaks draft labels to the publishable key (mig 065 RLS).
  const anonDb = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  const { data: leaked } = await anonDb
    .from('ocr_extractions')
    .select('id')
    .eq('run_id', runId)
    .eq('map_id', draft!.id);
  expect(leaked).toEqual([]);
});

test('the footprint export defaults to approved, filters by year and by ground bbox', async () => {
  // Two polygons on the fixture map: one approved, one still in the queue.
  const ring = (dx: number) => [
    [10 + dx, 10],
    [30 + dx, 10],
    [30 + dx, 30],
    [10 + dx, 30],
  ];
  const { data: made, error: mkErr } = await admin
    .from('footprint_submissions')
    .insert([
      {
        map_id: mapId,
        pixel_polygon: ring(0),
        name: 'export-smoke approved',
        feature_type: 'building',
        status: 'approved',
        source: 'volunteer',
      },
      {
        map_id: mapId,
        pixel_polygon: ring(100),
        name: 'export-smoke submitted',
        feature_type: 'building',
        status: 'submitted',
        source: 'volunteer',
      },
    ])
    .select('id, status');
  expect(mkErr, mkErr?.message).toBeNull();
  for (const r of made!) created.footprintIds.push(r.id);

  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });

  // Assertions are scoped to this test's own rows by name: other tests in this
  // file leave approved footprints on the same fixture map until afterAll, so a
  // bare row count here would depend on execution order.
  const namesOf = async (qs: string): Promise<string[]> => {
    const res = await anon.get(`/api/export/footprints?${qs}`);
    expect(res.ok(), await res.text()).toBe(true);
    return (await res.json()).features
      .map((f: { properties: { name: string | null } }) => f.properties.name)
      .filter((n: string | null) => n?.startsWith('export-smoke'));
  };

  // Default status: the reviewed polygon only.
  expect(await namesOf(`map_id=${mapId}`)).toEqual(['export-smoke approved']);

  // The map's year rides along, and filters.
  const def = await anon.get(`/api/export/footprints?map_id=${mapId}`);
  const props = (await def.json()).features.find(
    (f: { properties: { name: string } }) => f.properties.name === 'export-smoke approved'
  ).properties;
  expect(props.year).toBe(1900);
  expect(await namesOf(`map_id=${mapId}&year=1500-1600`)).toEqual([]);
  expect(await namesOf(`map_id=${mapId}&year=1890-1910`)).toEqual(['export-smoke approved']);

  // bbox selects on the ground. The fixture map has no resolvable annotation,
  // so nothing can be warped and a ground query must return nothing rather
  // than falling back to pixel coordinates that look like coordinates.
  expect(props.geo_converted).toBe(false);
  expect(await namesOf(`map_id=${mapId}&bbox=106.6,10.7,106.8,10.9`)).toEqual([]);

  // Malformed filters are ignored, not fatal.
  expect(await namesOf(`map_id=${mapId}&year=nope&bbox=1,2`)).toEqual(['export-smoke approved']);

  // A comma list is accepted; a malformed id is a 400, not a 500.
  expect(await namesOf(`map_id=${mapId},${mapId}`)).toEqual(['export-smoke approved']);
  const bad = await anon.get('/api/export/footprints?map_id=not-a-uuid');
  expect(bad.status()).toBe(400);

  await anon.dispose();
});

test('the place-time index warps on write, gates drafts, and rewarps on demand', async () => {
  const runId = `write-smoke-ctx-${Date.now()}`;
  created.runIds.push(runId);

  // The fixture map has no resolvable annotation, so a writer cannot warp: the
  // honest result is a null geom, not a guessed one.
  const post = await staffRequest.post(`/api/admin/maps/${mapId}/ocr-review`, {
    data: {
      run_id: runId,
      global_x: 100,
      global_y: 200,
      global_w: 50,
      global_h: 20,
      text: 'Quai de Belgique',
      category: 'street',
    },
  });
  expect(post.ok(), await post.text()).toBe(true);
  const { id: unwarpedId } = await post.json();
  const { data: unwarped } = await admin
    .from('ocr_extractions')
    .select('geom, geom_src')
    .eq('id', unwarpedId)
    .single();
  expect(unwarped!.geom).toBeNull();
  expect(unwarped!.geom_src).toBeNull();

  // Stand in for a successful warp by writing the geometry the way the warp
  // job would, then ask the index what is there.
  const HERE = { lng: 106.70098, lat: 10.77653 };
  await admin
    .from('ocr_extractions')
    .update({
      geom: `SRID=4326;POINT(${HERE.lng} ${HERE.lat})`,
      geom_src: 'smoke-src',
      geom_rmse: 4.2,
    })
    .eq('id', unwarpedId);

  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  const res = await anon.get(`/api/context?lng=${HERE.lng}&lat=${HERE.lat}&radius=200`);
  expect(res.ok(), await res.text()).toBe(true);
  const ctx = await res.json();
  const hit = ctx.labels.find((l: { id: string }) => l.id === unwarpedId);
  expect(hit, 'the warped label should be in range').toBeTruthy();
  expect(hit.text).toBe('Quai de Belgique');
  expect(hit.geom_rmse).toBe(4.2);
  expect(hit.distance_m).toBeLessThan(1);
  expect(hit.year).toBe(1900);

  // A tight radius excludes it; bad coordinates are a 400, not a 500.
  const far = await anon.get(`/api/context?lng=${HERE.lng + 0.5}&lat=${HERE.lat}&radius=100`);
  expect((await far.json()).labels).toEqual([]);
  expect((await anon.get('/api/context?lng=999&lat=0')).status()).toBe(400);

  // A draft map's warped label is invisible to an anonymous caller.
  const { data: draft } = await admin
    .from('maps')
    .insert({ name: 'ctx-smoke draft map', status: 'draft', year: 1901 })
    .select('id')
    .single();
  created.mapIds.push(draft!.id);
  await admin.from('ocr_extractions').insert({
    map_id: draft!.id,
    run_id: runId,
    tile_x: 0,
    tile_y: 9,
    tile_w: 100,
    tile_h: 100,
    global_x: 10,
    global_y: 20,
    global_w: 50,
    global_h: 10,
    text: 'draft-only street',
    category: 'street',
    confidence: 0.9,
    geom: `SRID=4326;POINT(${HERE.lng} ${HERE.lat})`,
    geom_src: 'smoke-src',
  });
  const gated = await anon.get(`/api/context?lng=${HERE.lng}&lat=${HERE.lat}&radius=200`);
  const gatedTexts = (await gated.json()).labels.map((l: { text: string }) => l.text);
  expect(gatedTexts).toContain('Quai de Belgique');
  expect(gatedTexts).not.toContain('draft-only street');

  // Staff see both.
  const staffCtx = await staffRequest.get(
    `/api/context?lng=${HERE.lng}&lat=${HERE.lat}&radius=200`
  );
  const staffTexts = (await staffCtx.json()).labels.map((l: { text: string }) => l.text);
  expect(staffTexts).toContain('draft-only street');
  await anon.dispose();

  // map_context reports coverage and counts a row warped against another
  // georeference as stale — the defect the warp job clears.
  const { data: summary } = await admin.rpc('map_context', {
    p_map_id: mapId,
    p_geom_src: 'a-different-georeference',
  });
  const s = summary as unknown as {
    labels: { total: number; warped: number; stale: number };
  };
  expect(s.labels.warped).toBeGreaterThan(0);
  expect(s.labels.stale).toBeGreaterThan(0);

  // A warp job is claimable and runs server-side; this map has no annotation,
  // so it reports that rather than inventing geometry.
  const { data: job } = await admin
    .from('pipeline_jobs')
    .insert({ kind: 'warp', map_id: mapId, payload: {} })
    .select('id')
    .single();
  created.jobIds.push(job!.id);
  const asWorker = await playwrightRequest.newContext({
    baseURL: 'http://localhost:5199',
    extraHTTPHeaders: { Authorization: `Bearer ${TEST_WORKER_TOKEN}` },
  });
  const claimed = await asWorker.post('/api/pipeline/claim', {
    data: { kinds: ['warp'], worker: 'write-smoke' },
  });
  expect(claimed.ok(), await claimed.text()).toBe(true);
  const ran = await asWorker.post('/api/pipeline/execute', {
    data: { job_id: job!.id },
  });
  expect(ran.ok(), await ran.text()).toBe(true);
  expect((await ran.json()).result.reason).toBe('no usable annotation');
  await asWorker.dispose();
});

test('the published contracts match what the API actually returns', async () => {
  // contracts/ is the written definition consumers outside this repo rely on
  // (docs/platform-design.md §3). This is the executable half: if a field
  // changes shape, it fails here rather than in someone else's app.
  const runId = `write-smoke-contract-${Date.now()}`;
  created.runIds.push(runId);

  const HERE = { lng: 106.70098, lat: 10.77653 };
  const { data: label } = await admin
    .from('ocr_extractions')
    .insert({
      map_id: mapId,
      run_id: runId,
      tile_x: 0,
      tile_y: 42,
      tile_w: 100,
      tile_h: 100,
      global_x: 10,
      global_y: 20,
      global_w: 50,
      global_h: 10,
      text: 'Rue Contractuelle',
      category: 'street',
      confidence: 0.95,
      geom: `SRID=4326;POINT(${HERE.lng} ${HERE.lat})`,
      geom_src: 'contract-smoke',
      geom_rmse: 3.1,
    })
    .select('id')
    .single();

  const { data: print } = await admin
    .from('footprint_submissions')
    .insert({
      map_id: mapId,
      pixel_polygon: [
        [10, 10],
        [30, 10],
        [30, 30],
      ],
      name: 'contract-smoke building',
      feature_type: 'building',
      status: 'approved',
      source: 'volunteer',
      geom: 'SRID=4326;POLYGON((106.7008 10.7764, 106.7012 10.7764, 106.7012 10.7767, 106.7008 10.7764))',
      geom_src: 'contract-smoke',
      geom_rmse: 3.1,
    })
    .select('id')
    .single();
  created.footprintIds.push(print!.id);

  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });

  // Every schema must stay inside the subset the checker implements; a contract
  // that quietly asks for an unchecked keyword is worse than no contract.
  for (const name of [
    'context.schema.json',
    'label-hit.schema.json',
    'footprint-feature.schema.json',
  ]) {
    expect(unsupportedKeywords(loadSchema(name)), `${name} uses unchecked keywords`).toEqual([]);
  }

  const ctxRes = await anon.get(`/api/context?lng=${HERE.lng}&lat=${HERE.lat}&radius=300`);
  expect(ctxRes.ok(), await ctxRes.text()).toBe(true);
  const ctx = await ctxRes.json();
  expect(validate(loadSchema('context.schema.json'), ctx)).toEqual([]);
  expect(ctx.labels.some((l: { id: string }) => l.id === label!.id)).toBe(true);
  expect(ctx.footprints.some((f: { id: string }) => f.id === print!.id)).toBe(true);

  const search = await anon.get('/api/search?q=rue%20contractuelle&include=labels');
  expect(search.ok()).toBe(true);
  const hits = (await search.json()).labels;
  const hitSchema = loadSchema('label-hit.schema.json');
  expect(hits.length).toBeGreaterThan(0);
  for (const h of hits) expect(validate(hitSchema, h)).toEqual([]);

  const exported = await anon.get(`/api/export/footprints?map_id=${mapId}`);
  expect(exported.ok()).toBe(true);
  const features = (await exported.json()).features;
  const featureSchema = loadSchema('footprint-feature.schema.json');
  expect(features.length).toBeGreaterThan(0);
  for (const f of features) expect(validate(featureSchema, f)).toEqual([]);

  // And the checker itself has teeth: a wrong type must be reported.
  expect(validate(hitSchema, { ...hits[0], year: 'nineteen hundred' })).toEqual([
    '$.year: expected integer|null, got string',
  ]);

  await anon.dispose();
});

test('a place page groups every spelling and hides unpublished sheets', async () => {
  const runId = `write-smoke-place-${Date.now()}`;
  created.runIds.push(runId);

  const HERE = { lng: 106.7009, lat: 10.7765 };
  const row = (text: string, tile_y: number) => ({
    map_id: mapId,
    run_id: runId,
    tile_x: 0,
    tile_y,
    tile_w: 100,
    tile_h: 100,
    global_x: 10,
    global_y: 20,
    global_w: 50,
    global_h: 10,
    text,
    category: 'street',
    confidence: 0.9,
    geom: `SRID=4326;POINT(${HERE.lng} ${HERE.lat})`,
    geom_src: 'place-smoke',
    geom_rmse: 7.5,
  });
  // The same street written three ways: hyphenated, spaced, and accented. The
  // gazetteer's key folds punctuation, so all three are one place.
  const { error: insErr } = await admin
    .from('ocr_extractions')
    .insert([row('Rue de Cây-Mai', 51), row('Rue de Cay Mai', 52), row('Rue de Cay Mai', 53)]);
  expect(insErr, insErr?.message).toBeNull();

  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  const res = await anon.get('/catalog/place/rue-de-cay-mai');
  expect(res.ok(), `${res.status()} ${await res.text()}`).toBe(true);
  const html = await res.text();

  // Server-rendered: the crawler must see all of this without JavaScript.
  expect(html).toContain('Rue de Cay Mai'); // the most-attested spelling wins the title
  expect(html).toContain('Rue de Cây-Mai'); // the other spelling is listed as a variant
  expect(html).toContain('Write-smoke fixture map');
  expect(html).toContain('1900');
  expect(html).toContain(`at=${HERE.lng.toFixed(6)}`); // the explore link lands on the spot
  expect(html).toContain('8 m'); // the rounded warp error, stated rather than hidden

  // The share page links to it, which is the only crawl path there is.
  const share = await anon.get(`/catalog/${mapId}`);
  expect(share.ok()).toBe(true);
  expect(await share.text()).toContain('/catalog/place/rue-de-cay-mai');

  // An unknown name is a 404, not an empty page.
  expect((await anon.get('/catalog/place/rue-qui-nexiste-pas')).status()).toBe(404);

  // A name attested only on a draft map has no public page.
  const { data: draft } = await admin
    .from('maps')
    .insert({ name: 'place-smoke draft', status: 'draft', year: 1902 })
    .select('id')
    .single();
  created.mapIds.push(draft!.id);
  await admin.from('ocr_extractions').insert({ ...row('Rue Introuvable', 54), map_id: draft!.id });
  expect((await anon.get('/catalog/place/rue-introuvable')).status()).toBe(404);

  // And a name on BOTH a published and a draft sheet must not leak the draft
  // through the aggregate. The page loader reads the gazetteer on the service
  // client, which bypasses RLS, so the view itself has to be the gate.
  await admin.from('ocr_extractions').insert({ ...row('Rue de Cay Mai', 55), map_id: draft!.id });
  const { data: agg } = await admin
    .from('place_names')
    .select('map_ids, years, mentions')
    .eq('name_key', 'rue de cay mai')
    .single();
  expect(agg!.map_ids).not.toContain(draft!.id);
  expect(agg!.years).not.toContain(1902);
  expect(await (await anon.get('/catalog/place/rue-de-cay-mai')).text()).not.toContain(draft!.id);

  await anon.dispose();
});

test('Postgres and the browser agree on what counts as one place', async () => {
  // `place_core_key` exists twice — migration 081 and `placeCoreKey` in
  // `$lib/core/utils/placeKey` — because a label on screen has to link to its
  // place page without a round trip. When they disagree the link is a 404, and
  // nothing logs it: the page renders "No place with that name in the archive"
  // and the reader assumes the archive has not got it.
  //
  // `tests/palette.spec.ts` pins the word list by reading the migration, which
  // catches an edit to one side only. It cannot catch the two engines folding a
  // character differently — which is exactly what was wrong when this went in:
  // Postgres's `unaccent` expands `œ` to `oe`, and NFD does not decompose it at
  // all, so `Rue Schrœder` keyed as `schroeder` in the view and `schr der` in
  // the browser. Hence this test, which asks the database rather than a fixture.
  const spellings = [
    'Rue Schrœder',
    'Rue des Sœurs',
    'Khánh Hội',
    'Village de Khanh-Hoi',
    'Vge de Khánh Hồi',
    'Boulevard Charner',
    'Bd Charner',
    'Chợ Lớn', // under the four-character floor once stripped: keeps its generic
    'Rạch Bà',
    'Đường Bình Tây',
    'Rue de la Grandière',
    'Arroyo de l’Avalanche',
    'Quai de la', // every token generic — must not strip to nothing
    'Gia Định',
  ];
  for (const text of spellings) {
    const { data, error: err } = await admin.rpc('place_core_key', {
      p_text: text,
      p_validated: null,
    });
    expect(err, `${text}: ${err?.message}`).toBeNull();
    expect(data, `place_core_key disagrees on ${JSON.stringify(text)}`).toBe(placeCoreKey(text));
  }

  // The three Khánh Hội spellings are one place, and that is the whole point:
  // one gazetteer page, and one lookup billed to Gallica and the NLV instead of
  // three.
  const khanhHoi = new Set(
    await Promise.all(
      spellings.slice(2, 5).map(async (t) => {
        const { data } = await admin.rpc('place_core_key', { p_text: t, p_validated: null });
        return data;
      })
    )
  );
  expect([...khanhHoi]).toEqual(['khanh hoi']);
});

test('geometry writes are batched, capped, and ordered correctly', async () => {
  const runId = `write-smoke-batch-${Date.now()}`;
  created.runIds.push(runId);

  // 600 rows: more than one page of the warp job's walk, and the size of
  // problem that made the old one-update-per-row loop impossible inside a
  // Pages Function.
  const rows = Array.from({ length: 600 }, (_, i) => ({
    map_id: mapId,
    run_id: runId,
    tile_x: 0,
    tile_y: 1000 + i,
    tile_w: 10,
    tile_h: 10,
    global_x: i,
    global_y: 0,
    global_w: 5,
    global_h: 5,
    text: `batch-${i}`,
    category: 'street',
    confidence: 0.5,
  }));
  const { error: insErr } = await admin.from('ocr_extractions').insert(rows);
  expect(insErr, insErr?.message).toBeNull();

  const { data: ids } = await admin.from('ocr_extractions').select('id').eq('run_id', runId);
  expect(ids!.length).toBe(600);

  // One call moves all of them.
  const writes = ids!.map((r, i) => ({
    id: r.id,
    geom: `SRID=4326;POINT(${106.7 + i * 1e-5} 10.77)`,
    geom_src: 'batch-smoke',
    geom_rmse: 2.5,
  }));
  const { data: moved, error: rpcErr } = await admin.rpc('set_extraction_geom', {
    p_rows: writes as never,
  });
  expect(rpcErr, rpcErr?.message).toBeNull();
  expect(moved).toBe(600);

  const { count } = await admin
    .from('ocr_extractions')
    .select('id', { count: 'exact', head: true })
    .eq('run_id', runId)
    .eq('geom_src', 'batch-smoke');
  expect(count).toBe(600);

  // A null geom is a legitimate write: it is how a row that cannot be warped
  // is recorded, rather than keeping a stale position.
  const cleared = await admin.rpc('set_extraction_geom', {
    p_rows: [{ id: ids![0].id, geom: null, geom_src: 'batch-smoke', geom_rmse: null }] as never,
  });
  expect(cleared.error).toBeNull();
  const { data: back } = await admin
    .from('ocr_extractions')
    .select('geom')
    .eq('id', ids![0].id)
    .single();
  expect(back!.geom).toBeNull();

  // The cap is enforced in the database, not trusted to the caller.
  const tooMany = await admin.rpc('set_extraction_geom', {
    p_rows: Array.from({ length: 1001 }, () => ({
      id: ids![0].id,
      geom: null,
      geom_src: 'x',
      geom_rmse: null,
    })) as never,
  });
  expect(tooMany.error?.message).toContain('at most 1000 rows');

  // An empty batch is a no-op, not an error — the walk hits this on a page
  // where every row was already warped.
  const none = await admin.rpc('set_extraction_geom', { p_rows: [] as never });
  expect(none.error).toBeNull();
  expect(none.data).toBe(0);

  // Distances come back numerically ordered. Sorted as text, "104.6" would
  // precede "12.3", which is what this had before.
  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  const ctx = await (await anon.get('/api/context?lng=106.7&lat=10.77&radius=2000')).json();
  const distances = ctx.labels.map((l: { distance_m: number }) => l.distance_m);
  expect(distances.length).toBeGreaterThan(2);
  expect([...distances].sort((a: number, b: number) => a - b)).toEqual(distances);

  // Search returns the stored position without fetching any annotation.
  const hits = await (await anon.get('/api/search?q=batch-3&include=labels')).json();
  const hit = hits.labels.find((l: { text: string }) => l.text === 'batch-3');
  expect(hit).toBeTruthy();
  expect(hit.lat).toBeCloseTo(10.77, 4);
  await anon.dispose();
});

test('a sheet series is offered only to a reader who can see its sheets', async () => {
  // `map_series` (mig 082) is what /explore lists as "show the whole series".
  // The view is the gate: a wholly-draft survey must not reach an anonymous
  // reader, who would switch it on and get an empty layer, and a collection
  // that is not a numbered survey must not be a series at all. Both are
  // decided in SQL, so both are asserted against a real Postgres.
  const mk = async (
    name: string,
    collection: string,
    status: string,
    extra: Record<string, unknown>,
    bbox: number[]
  ) => {
    const { data, error } = await admin
      .from('maps')
      .insert({
        name,
        collection,
        status,
        georef_done: true,
        year: 1910,
        bbox,
        extra_metadata: extra,
        allmaps_id: `se${Math.random().toString(16).slice(2, 16)}`.slice(0, 16),
      } as never)
      .select('id')
      .single();
    if (error || !data) throw new Error(`fixture insert failed: ${error?.message}`);
    created.mapIds.push((data as { id: string }).id);
  };

  const draftSeries = `ZZ Draft Survey ${Date.now()}`;
  const pubSeries = `ZZ Published Survey ${Date.now()}`;
  const bucket = `ZZ Bucket ${Date.now()}`;

  await mk('draft a', draftSeries, 'draft', { sheet_number: '1' }, [105, 20, 105.5, 20.5]);
  await mk('draft b', draftSeries, 'draft', { sheet_number: '2' }, [105.5, 20.5, 106, 21]);
  await mk('pub a', pubSeries, 'public', { sheet_number: '1' }, [106, 10, 106.5, 10.5]);
  await mk('pub b', pubSeries, 'featured', { sheet_number: '2' }, [106.5, 10.5, 107, 11]);
  // A second printing of a cell the survey already has. It is a row, not a
  // sheet (mig 084) — the corpus has three of these in the Indochine 1:25,000
  // alone, and counting rows told /explore the survey was three sheets bigger
  // than it is. Its bbox sits inside the union so a miscount cannot hide here
  // as a bounds change.
  await mk('pub a, 2nd ed', pubSeries, 'public', { sheet_number: '1' }, [106.1, 10.1, 106.2, 10.2]);
  // Numbered, but only one sheet: a map, not a series.
  await mk('solo', `ZZ Solo ${Date.now()}`, 'public', { sheet_number: '1' }, [100, 5, 101, 6]);
  // The same trap one level down: two rows, one cell. Two printings of a single
  // sheet are a map printed twice, and `count(*) > 1` called it a survey.
  const twins = `ZZ Twins ${Date.now()}`;
  await mk('twin a', twins, 'public', { sheet_number: '7' }, [101, 6, 102, 7]);
  await mk('twin b', twins, 'public', { sheet_number: '7' }, [101, 6, 102, 7]);
  // Two published sheets with no sheet numbers: the archive's catch-all bucket,
  // which must never be offered as a survey to stack on itself.
  await mk('bucket a', bucket, 'public', {}, [100, 5, 110, 23]);
  await mk('bucket b', bucket, 'public', {}, [106, 10, 107, 11]);

  const anon = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  const asUser = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } });
  await asUser.auth.setSession(session);

  // The survey's own index (mig 083): what it CONTAINS, which `maps` cannot
  // say because it only holds successes. Five cells, of which we hold two.
  const pubKeyForIndex = pubSeries.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  created.seriesKeys.push(pubKeyForIndex);
  const { error: idxError } = await admin.from('series_sheets').insert(
    ['1', '2', '3', '4', '5'].map((n) => ({
      series_key: pubKeyForIndex,
      sheet_number: n,
      held_by: n === '1' || n === '2' ? 'map' : null,
    })) as never
  );
  if (idxError) throw new Error(`series_sheets fixture failed: ${idxError.message}`);

  // 083's check constraint, which had never been shown to fire: a row pointing
  // at a map must say it is held by one, or it is a held sheet that would not
  // be counted — the exact miscount that table exists to prevent.
  const { error: badHold } = await admin.from('series_sheets').insert({
    series_key: pubKeyForIndex,
    sheet_number: 'unheld-with-a-map',
    map_id: created.mapIds[0],
    held_by: null,
  } as never);
  expect(badHold?.message ?? '').toContain('series_sheets_held_by_map');

  const keysFor = async (client: typeof anon) => {
    const { data, error } = await client
      .from('map_series')
      .select('key, sheets, survey_sheets, bounds');
    if (error) throw new Error(`map_series read failed: ${error.message}`);
    return data ?? [];
  };

  const anonRows = await keysFor(anon);
  const userRows = await keysFor(asUser);
  const anonKeys = anonRows.map((r) => r.key);
  const userKeys = userRows.map((r) => r.key);

  const draftKey = draftSeries.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const pubKey = pubSeries.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const bucketKey = bucket.toLowerCase().replace(/[^a-z0-9]+/g, '-');

  // The published survey is public; the draft one is not.
  expect(anonKeys).toContain(pubKey);
  expect(anonKeys).not.toContain(draftKey);
  // A signed-in reader may read drafts (mig 063), so the survey appears.
  expect(userKeys).toContain(draftKey);
  expect(userKeys).toContain(pubKey);

  // Neither reader is offered the bucket or the one-sheet collection.
  expect(anonKeys).not.toContain(bucketKey);
  expect(userKeys).not.toContain(bucketKey);
  expect([...anonKeys, ...userKeys].filter((k) => k?.startsWith('zz-solo'))).toEqual([]);

  // Bounds are the union of the sheets' own boxes — what "zoom to the series"
  // means. A wrong fold here points the camera at the wrong country silently.
  const pub = userRows.find((r) => r.key === pubKey);
  // Three rows over two cells. `sheets` is what the layer draws and what the
  // row promises, so it counts cells (mig 084).
  expect(pub?.sheets).toBe(2);
  expect(pub?.bounds).toEqual([106, 10, 107, 11]);

  // Two printings of one cell are not a survey, for either reader.
  const twinKey = twins.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  expect(anonKeys).not.toContain(twinKey);
  expect(userKeys).not.toContain(twinKey);

  // The denominator comes from the survey's index, not from `maps` — "2 of 5",
  // which is the whole point of joining it. A survey with no index row reads
  // null rather than 0, so a caller can tell "not counted" from "contains none".
  expect(pub?.survey_sheets).toBe(5);
  expect(userRows.find((r) => r.key === draftKey)?.survey_sheets).toBeNull();
});

/**
 * ── migration 088: the readable address ──────────────────────────────────────
 *
 * `/catalog/<uuid>` told a reader nothing about what was on the other end. The
 * rule these pin is in Postgres, not here: a sheet's name, then the year when
 * the name collides, then a counter only when the year cannot split them
 * either. What makes it worth a test is the second half — when a name collides,
 * the sheet that already held the bare name has to GIVE IT UP, and the address
 * it gave up has to keep working. Get only the first half right and the archive
 * looks correct while every link to the older sheet has quietly moved.
 */
/** A unique 16-char `allmaps_id`. The column is unique and the width is fixed,
 *  so a discriminator has to fit INSIDE the 16 rather than be appended to a
 *  timestamp that already fills it. */
const slugFixtureId = () => `s${Math.random().toString(36).slice(2)}${Date.now()}`.slice(0, 16);

/** `status` is spelled out on every fixture below because `maps.status` still
 *  defaults to `pending_georef` (migration 001) and migration 060 narrowed the
 *  check constraint to draft|public|featured without touching the default — so
 *  an insert that omits it is rejected. */

test('a sheet is addressed by its name, and a collision moves both onto the year', async () => {
  const stem = `Slug Fixture ${Date.now()}`;
  const base = stem.toLowerCase().replace(/[^a-z0-9]+/g, '-');

  const insert = (year: number) =>
    admin
      .from('maps')
      .insert({ allmaps_id: slugFixtureId(), name: stem, year, status: 'draft' })
      .select('id, slug')
      .single();

  // Alone, a sheet gets its name and nothing else.
  const { data: first, error: firstErr } = await insert(1906);
  expect(firstErr, firstErr?.message).toBeNull();
  created.mapIds.push(first!.id);
  expect(first!.slug).toBe(base);

  // A second sheet of the same name cannot take it, and must not be handed a
  // bare counter when the two are a decade apart — the year is the thing that
  // tells a reader which sheet they are looking at.
  const { data: second, error: secondErr } = await insert(1919);
  expect(secondErr, secondErr?.message).toBeNull();
  created.mapIds.push(second!.id);
  expect(second!.slug).toBe(`${base}-1919`);

  // ...and the incumbent gives up the bare name rather than keeping it by
  // seniority. `/catalog/<base>` would otherwise claim to be *the* sheet of that
  // name while being one of two, chosen by upload order.
  const { data: firstNow } = await admin.from('maps').select('slug').eq('id', first!.id).single();
  expect(firstNow!.slug).toBe(`${base}-1906`);

  // The address it gave up still resolves. This is what makes the demotion
  // affordable: nothing that was ever published dies.
  const { data: alias } = await admin
    .from('map_slug_aliases')
    .select('map_id')
    .eq('slug', base)
    .single();
  expect(alias!.map_id).toBe(first!.id);

  // No sheet is addressable two ways at once.
  const { data: all } = await admin.from('maps').select('slug');
  expect(new Set(all!.map((m) => m.slug)).size).toBe(all!.length);
});

test('a true tie falls back to a counter, and only then', async () => {
  const stem = `Tie Fixture ${Date.now()}`;
  const base = stem.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const insert = () =>
    admin
      .from('maps')
      .insert({ allmaps_id: slugFixtureId(), name: stem, year: 1904, status: 'draft' })
      .select('id, slug')
      .single();

  const { data: a, error: aErr } = await insert();
  expect(aErr, aErr?.message).toBeNull();
  created.mapIds.push(a!.id);
  const { data: b, error: bErr } = await insert();
  expect(bErr, bErr?.message).toBeNull();
  created.mapIds.push(b!.id);

  // Same name AND same year: there is nothing left to tell them apart with, so
  // a number is the honest answer rather than a fabricated distinction.
  const slugs = [
    (await admin.from('maps').select('slug').eq('id', a!.id).single()).data!.slug,
    b!.slug,
  ].sort();
  expect(slugs).toEqual([`${base}-1904`, `${base}-1904-2`]);
});

test('renaming a sheet does not move its address', async () => {
  const { data: map, error: mapErr } = await admin
    .from('maps')
    .insert({
      allmaps_id: slugFixtureId(),
      name: `Rename Fixture ${Date.now()}`,
      status: 'draft',
    })
    .select('id, slug')
    .single();
  expect(mapErr, mapErr?.message).toBeNull();
  created.mapIds.push(map!.id);

  // A title is edited for a typo or a fuller transcription. If that moved the
  // URL, every link already shared would break — silently, and after the fact.
  await admin.from('maps').update({ name: 'Rename Fixture, corrected' }).eq('id', map!.id);
  const { data: after } = await admin.from('maps').select('slug').eq('id', map!.id).single();
  expect(after!.slug).toBe(map!.slug);
});

test('a uuid link and a retired name both 301 to the readable address', async () => {
  const anon = await playwrightRequest.newContext({ baseURL: 'http://localhost:5199' });
  const { data: fixture } = await admin.from('maps').select('slug').eq('id', mapId).single();

  // Every link the archive published before Sept 2026 is a uuid, and those are
  // in other people's messages and bookmarks. They redirect; they never 404.
  const byUuid = await anon.get(`/catalog/${mapId}`, { maxRedirects: 0 });
  expect(byUuid.status()).toBe(301);
  expect(byUuid.headers()['location']).toBe(`/catalog/${fixture!.slug}`);

  // The canonical address answers directly — one page, one URL, no redirect
  // chain for a crawler to discount.
  expect((await anon.get(`/catalog/${fixture!.slug}`, { maxRedirects: 0 })).status()).toBe(200);

  // A retired name (a demotion, or a deliberate re-mint) lands the same way.
  await admin
    .from('map_slug_aliases')
    .insert({ slug: `retired-${Date.now()}`, map_id: mapId })
    .select('slug')
    .single()
    .then(async ({ data }) => {
      const res = await anon.get(`/catalog/${data!.slug}`, { maxRedirects: 0 });
      expect(res.status()).toBe(301);
      expect(res.headers()['location']).toBe(`/catalog/${fixture!.slug}`);
      await admin.from('map_slug_aliases').delete().eq('slug', data!.slug);
    });

  // A name that was never an address is still a 404, not a redirect to nowhere.
  expect((await anon.get('/catalog/no-such-sheet-anywhere', { maxRedirects: 0 })).status()).toBe(
    404
  );
  await anon.dispose();
});
