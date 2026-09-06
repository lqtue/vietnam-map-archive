import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';

/**
 * GET /api/admin/status — the numbers behind `/admin?tab=status`.
 *
 * Every figure here used to be reachable only by running SQL by hand, which
 * meant the person who owns the project could not check the project's own
 * state. This is the same human-in-the-loop idea as `/scan?mode=review`,
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
    /*  3 */ db.from('maps').select('*', head).eq('georef_done', true),
    /*  4 */ db.from('maps').select('*', head).not('bbox', 'is', null),
    // A map counts as read when its OCR job closed. Extractions cannot be
    // counted distinctly through PostgREST, and every route into the table
    // goes through a `pipeline_jobs` row, so the view is the honest proxy.
    /*  5 */ db.from('map_pipeline_status').select('*', head).not('ocr_finished_at', 'is', null),
    /*  6 */ db.from('ocr_extractions').select('*', head),
    /*  7 */ db.from('ocr_extractions').select('*', head).not('geom', 'is', null),
    /*  8 */ db.from('place_names').select('*', head),
    /*  9 */ db.from('footprint_submissions').select('*', head),
    /* 10 */ db
      .from('footprint_submissions')
      .select('*', head)
      .in('source', ['sam-auto', 'sam-corrected']),
    /* 11 */ db.from('footprint_submissions').select('*', head).eq('status', 'approved'),
    /* 12 */ db
      .from('footprint_submissions')
      .select('*', head)
      .in('status', ['submitted', 'needs_review']),
    /* 13 */ db.from('pipeline_jobs').select('*', head).eq('status', 'queued'),
    /* 14 */ db.from('pipeline_jobs').select('*', head).in('status', ['claimed', 'running']),
    /* 15 */ db.from('pipeline_jobs').select('*', head).eq('status', 'failed'),
    // A sheet counts as triaged when it has a saved neatline — the same
    // predicate `scripts/enqueue_ocr_all.mjs` uses (`triageOf`), so this row
    // answers "how many sheets would a plain enqueue run actually queue?".
    /* 16 */ db.from('maps').select('*', head).not('triage->>neatline', 'is', null),
    /* 17 */ db.from('maps').select('*', head).not('triage->>regions', 'is', null),
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
