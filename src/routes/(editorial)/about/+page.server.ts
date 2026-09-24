/**
 * The numbers on /about, read from the database rather than typed into the
 * page. They were hardcoded until Sept 2026 and had drifted badly — the label
 * count was out by a factor of three and the review count by half — so the one
 * page whose job is to be honest about the state of the archive was the page
 * most out of date. Counting on render is cheaper than remembering to edit.
 *
 * Nine queries, cached at the edge for an hour: nothing here changes faster.
 *
 * The seventh is `series_cells`, and it is here because `maps` alone gives a
 * false floor. 452 of the L7014 1:50,000's held sheets are cells of a pre-tiled
 * mosaic with no `maps` row at all, so the honest answer to "how much of this
 * survey can you draw" lives in the survey's own index, not in the catalogue.
 * Counting them apart from `published` is deliberate: the two overlap (a sheet
 * with a record is in both) and must never be added together.
 *
 * Those three are head counts rather than a `select` of the rows, because
 * PostgREST caps an unbounded select at 1000 and says nothing about it — the
 * indexes are 706 rows today and the surveys in the scout queue run past that.
 * A truncated count here would not look wrong, it would just be low.
 */

import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';

export const load: PageServerLoad = async ({ setHeaders }) => {
  const db = adminClient();
  const head = { count: 'exact' as const, head: true };

  const [
    published,
    drafts,
    labels,
    labelsChecked,
    shapes,
    shapesApproved,
    surveySheets,
    surveySheetsHeld,
    surveys,
  ] = await Promise.all([
    // Not a head count: the same rows give the year range and the city split.
    db.from('maps').select('year, location').in('status', ['public', 'featured']),
    db.from('maps').select('id', head).eq('status', 'draft'),
    db.from('ocr_labels').select('id', head),
    db.from('ocr_labels').select('id', head).eq('review_status', 'validated'),
    db.from('footprints').select('id', head),
    db.from('footprints').select('id', head).eq('review_status', 'approved'),
    // One row per sheet a survey contains, held or not. `held_by` says how it
    // reaches a reader — `'map'` for a catalogue record, `'raster:<key>'` for
    // a mosaic cell — and null means the archive has not got it.
    db.from('series_cells').select('series_key', head),
    db.from('series_cells').select('series_key', head).not('held_by', 'is', null),
    // `survey_sheets` is non-null for exactly the surveys whose own index has
    // been imported, which is the same set `series_cells` has rows for.
    db.from('map_series').select('key', head).not('survey_sheets', 'is', null),
  ]);

  const rows = published.data ?? [];
  const years = rows.map((r) => r.year).filter((y): y is number => typeof y === 'number');
  const cities = new Map<string, number>();
  for (const r of rows) {
    if (r.location) cities.set(r.location, (cities.get(r.location) ?? 0) + 1);
  }

  // One minute, not one hour. The data behind this page changes slowly and an
  // hour was right about that — but the header caches the *HTML*, and a
  // SvelteKit page's HTML names its JS chunks by content hash. A deploy writes
  // new hashes and deletes the old files, so for the rest of its TTL this page
  // served a cached document pointing at eight chunks that no longer existed:
  // 404s, no hydration, and nothing in the page itself to say so. Measured on
  // the 2026-09-13 deploy at `age: 3193` — 53 minutes of a page that renders
  // and does not work.
  //
  // /about is the only editorial page setting a max-age at all; the rest are
  // dynamic and were unaffected. A minute keeps the six queries off a crawl
  // burst and shrinks the post-deploy window to something a hard reload fixes.
  setHeaders({ 'cache-control': 'public, max-age=60' });

  return {
    stats: {
      published: rows.length,
      drafts: drafts.count ?? 0,
      labels: labels.count ?? 0,
      labelsChecked: labelsChecked.count ?? 0,
      shapes: shapes.count ?? 0,
      shapesApproved: shapesApproved.count ?? 0,
      yearFrom: years.length ? Math.min(...years) : null,
      yearTo: years.length ? Math.max(...years) : null,
      // Biggest first — "Saigon 22, Huế 10, Hanoi 7".
      cities: [...cities.entries()].sort((a, b) => b[1] - a[1]),
      surveys: surveys.count ?? 0,
      surveySheets: surveySheets.count ?? 0,
      surveySheetsHeld: surveySheetsHeld.count ?? 0,
    },
  };
};
