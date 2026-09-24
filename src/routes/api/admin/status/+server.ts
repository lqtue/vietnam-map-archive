import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';

/**
 * GET /api/admin/status — the numbers behind `/admin/status`.
 *
 * Every figure here used to be reachable only by running SQL by hand, which
 * meant the person who owns the project could not check the project's own
 * state. This is the same human-in-the-loop idea as `/scan?mode=shapes&tab=validate`,
 * pointed at the pipeline instead of at a map.
 *
 * Counts use `head: true`, so PostgREST returns the tally in a Content-Range
 * header and transfers no rows. The failed-job list is the one query that
 * returns rows; it is small by construction and useless without the detail.
 */
export const GET: RequestHandler = async ({ locals }) => {
  await requireRole(locals, ['admin', 'mod']);
  const db = adminClient();

  const head = { count: 'exact' as const, head: true };

  const results = await Promise.all([
    /*  0 */ db.from('maps').select('*', head),
    /*  1 */ db.from('maps').select('*', head).in('status', ['public', 'featured']),
    /*  2 */ db.from('maps').select('*', head).eq('status', 'draft'),
    /*  3 */ db.from('maps').select('*', head).eq('is_georeferenced', true),
    /*  4 */ db.from('maps').select('*', head).not('bbox', 'is', null),
    // A map counts as read when its OCR job closed. Extractions cannot be
    // counted distinctly through PostgREST, and every route into the table
    // goes through a `pipeline_jobs` row, so the view is the honest proxy.
    /*  5 */ db.from('map_pipeline_status').select('*', head).not('ocr_finished_at', 'is', null),
    /*  6 */ db.from('ocr_labels').select('*', head),
    /*  7 */ db.from('ocr_labels').select('*', head).not('geom', 'is', null),
    /*  8 */ db.from('place_names').select('*', head),
    /*  9 */ db.from('footprints').select('*', head),
    /* 10 */ db.from('footprints').select('*', head).in('source', ['sam-auto', 'sam-corrected']),
    /* 11 */ db.from('footprints').select('*', head).eq('review_status', 'approved'),
    /* 12 */ db
      .from('footprints')
      .select('*', head)
      .in('review_status', ['submitted', 'needs_review']),
    /* 13 */ db.from('pipeline_jobs').select('*', head).eq('status', 'queued'),
    /* 14 */ db.from('pipeline_jobs').select('*', head).in('status', ['claimed', 'running']),
    /* 15 */ db.from('pipeline_jobs').select('*', head).eq('status', 'failed'),
    // A sheet counts as triaged when a person has **accepted** its crop, which is
    // the same predicate `scripts/enqueue_ocr_all.mjs` gates on — so this row
    // answers "how many sheets would a plain enqueue run actually queue?".
    //
    // It used to count a saved neatline, and no sheet in the corpus had one,
    // which is how the script's default mode came to queue nothing while
    // looking like it worked. The crop is proposed automatically now (the
    // layout pass adopts its own main_map region), so what is scarce is the
    // acceptance, not the crop.
    /* 16 */ db.from('maps').select('*', head).not('triage_reviewed_at', 'is', null),
    /* 17 */ db.from('maps').select('*', head).not('triage->>regions', 'is', null),
    // Proposed but not accepted: a crop exists and nobody has looked at it.
    // This is the queue a person actually works through.
    /* 18 */ db
      .from('maps')
      .select('*', head)
      .not('triage->>neatline', 'is', null)
      .is('triage_reviewed_at', null),
  ]);

  const broken = results.find((r) => r.error);
  if (broken?.error) dbError(broken.error, 'Could not read system status');

  const [
    mapsTotal,
    mapsPublished,
    mapsDraft,
    mapsGeoreferenced,
    mapsWithBbox,
    mapsRead,
    words,
    wordsPlaced,
    placeNames,
    fpTotal,
    fpByMachine,
    fpApproved,
    fpAwaitingReview,
    jobsQueued,
    jobsRunning,
    jobsFailed,
    mapsTriaged,
    mapsWithLayout,
    mapsProposed,
  ] = results.map((r) => r.count ?? 0);

  // Only fetched when there is something to show, so the normal case is free.
  let failures: { kind: string; map_id: string | null; attempts: number; error: string | null }[] =
    [];
  if (jobsFailed > 0) {
    const { data, error: err } = await db
      .from('pipeline_jobs')
      .select('kind, map_id, attempts, error')
      .eq('status', 'failed')
      .order('updated_at', { ascending: false })
      .limit(10);
    if (err) dbError(err, 'Could not list failed jobs');
    failures = data ?? [];
  }

  return json({
    checkedAt: new Date().toISOString(),
    maps: {
      total: mapsTotal,
      published: mapsPublished,
      drafts: mapsDraft,
      georeferenced: mapsGeoreferenced,
      withBbox: mapsWithBbox,
      read: mapsRead,
      triaged: mapsTriaged,
      proposed: mapsProposed,
      withLayout: mapsWithLayout,
    },
    words: { total: words, placed: wordsPlaced, placeNames },
    footprints: {
      total: fpTotal,
      byMachine: fpByMachine,
      approved: fpApproved,
      awaitingReview: fpAwaitingReview,
    },
    jobs: { queued: jobsQueued, running: jobsRunning, failed: jobsFailed, failures },
  });
};
