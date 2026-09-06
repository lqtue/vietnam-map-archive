import {
  expect,
  test,
  request as playwrightRequest,
  type APIRequestContext,
} from '@playwright/test';
import { createClient, type Session } from '@supabase/supabase-js';
import { createServerClient } from '@supabase/ssr';
import { loadSchema, unsupportedKeywords, validate } from './schemaCheck';

/**
 * Write-path smokes (ROADMAP A5). Unlike smoke.spec.ts these DO write rows, so
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
      status: 'submitted',
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
    .select('status, source')
    .eq('id', fp!.id)
    .single();
  expect(reviewed!.status).toBe('submitted');
  // An edited polygon is machine output a human fixed, and exports care.
  expect(reviewed!.source).toBe('sam-corrected');

  // set_footprint_status only moves rows out of needs_review, so a second
  // decision on the same row is refused rather than silently applied.
  const again = await staffRequest.patch('/api/admin/footprints', {
    data: { id: fp!.id, status: 'rejected' },
  });
  expect(again.status()).toBe(409);
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
  const res = await anon.get(`/archive/${mapId}`);
  expect(res.status()).toBe(200);
  const html = await res.text();
  expect(html).toContain('og:title');
  expect(html).toContain('Write-smoke fixture map');
  expect(html).toContain(`/explore?map=${mapId}`);

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
  expect((await anon.get(`/archive/${draft!.id}`)).status()).toBe(404);

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

  // A signed-in volunteer still needs drafts: /contribute#georef selects them
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
  const res = await anon.get('/archive/place/rue-de-cay-mai');
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
  const share = await anon.get(`/archive/${mapId}`);
  expect(share.ok()).toBe(true);
  expect(await share.text()).toContain('/archive/place/rue-de-cay-mai');

  // An unknown name is a 404, not an empty page.
  expect((await anon.get('/archive/place/rue-qui-nexiste-pas')).status()).toBe(404);

  // A name attested only on a draft map has no public page.
  const { data: draft } = await admin
    .from('maps')
    .insert({ name: 'place-smoke draft', status: 'draft', year: 1902 })
    .select('id')
    .single();
  created.mapIds.push(draft!.id);
  await admin.from('ocr_extractions').insert({ ...row('Rue Introuvable', 54), map_id: draft!.id });
  expect((await anon.get('/archive/place/rue-introuvable')).status()).toBe(404);

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
  expect(await (await anon.get('/archive/place/rue-de-cay-mai')).text()).not.toContain(draft!.id);

  await anon.dispose();
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
