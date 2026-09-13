import type { SeriesRef, SheetsRef } from '$lib/map/stores/layersStore';
import type { MapSeries } from '$lib/data/maps/types';

/**
 * The series list /explore offers above the sheet rows: one row per survey,
 * tap to put the whole thing on the map.
 *
 * A row is not one layer. L7014 is held two ways — 452 cells pre-tiled into a
 * raster archive, 9 as `maps` rows warped live by Allmaps — and those two are
 * complementary, not alternative: the mosaic cannot draw Saigon, because the
 * 24 sheets over the city are the plain JPGs PCL published with no embedded
 * georeference, which is exactly why they are `maps` rows at all; and the city
 * sheets cannot draw anywhere else. Offered as two rows they read as a choice
 * between two things. Added together they compose into one survey, the warped
 * sheets filling the hole in the mosaic.
 *
 * So a row carries `refs`, and they go on and come off together.
 */
export interface SeriesRow {
  key: string;
  name: string;
  /** Bottom-up: `addOverlay` puts each new layer on top of the stack. */
  refs: SeriesRef[];
  label: string;
  note: string;
  /**
   * The survey's `map_series.key`, which is also its `series_sheets.series_key`
   * and so the address of its coverage page at `/catalog/series/<key>`. Not the
   * same as `key` above, which for a folded row is the raster archive's own key
   * — the page is keyed on the database series, and a pure raster archive that
   * is `halfOf` nothing has no index and therefore no page.
   *
   * Undefined unless the survey's index has actually been imported. A
   * `map_series` row exists for every survey with georeferenced sheets, but
   * `series_sheets` is seeded per survey by hand: AMS L909 has three sheets and
   * no index, so its page is a 404, and offering a link to it from a row that
   * works is worse than offering none. `surveySheets` is exactly that signal —
   * null means "not counted", which is the same thing as "no page".
   */
  seriesKey?: string;
}

/**
 * A pre-tiled raster archive, which no database row describes. The list of them
 * is the caller's (`ExploreBrowsePanel`), because `L7014_OVERLAY` lives in
 * `map/constants.ts` next to OpenLayers layer builders — importing it here
 * would pull OL into a module that is otherwise pure arithmetic over the view's
 * rows, and out of reach of the browser-less tests.
 */
export interface RasterSeries {
  ref: SeriesRef;
  name: string;
  /**
   * The `series_key` of the database series this archive is the other half of,
   * or undefined when it stands alone.
   */
  halfOf?: string;
  /** Cells in the archive. Not in the database, so it cannot be counted. */
  sheets: number;
  note: string;
}

/** The `SheetsRef` that draws a database series' sheets, warped live. */
export function sheetsRef(s: MapSeries): SheetsRef {
  return {
    kind: 'sheets',
    mapId: `sheets:${s.key}`,
    key: s.key,
    collection: s.collection,
    // The collection is the layer's name in the stack, where it sits beside
    // sheet names — so no year span here, which belongs in the note.
    name: s.name,
    bounds: s.bounds,
  };
}

/**
 * Only a reader who can see drafts is shown a draft count, because only they
 * can be looking at one: for everyone else `sheets` is already the published
 * count and saying so twice would be noise.
 */
function draftsNote(s: MapSeries, canSeeDrafts: boolean): string {
  return canSeeDrafts && s.publishedSheets < s.sheets
    ? `${s.sheets - s.publishedSheets} unpublished`
    : '';
}

/** "1903–27", plus what a reader who can see drafts should know about them. */
export function seriesNote(s: MapSeries, canSeeDrafts: boolean): string {
  const span =
    s.firstYear && s.lastYear
      ? s.firstYear === s.lastYear
        ? `${s.firstYear}`
        : `${s.firstYear}–${String(s.lastYear).slice(-2)}`
      : '';
  return [span, draftsNote(s, canSeeDrafts)].filter(Boolean).join(' · ');
}

/**
 * "53 sheets", or "9 of 627 sheets" where the survey's own index says how many
 * it contains (mig 083/084). The denominator matters most exactly where it is
 * largest: without it L7014 said "9 sheets" for a survey of 627, which is what
 * `maps` knows rather than what is true. A null denominator means no index was
 * imported, which is not zero — say nothing rather than "of 0".
 */
function count(held: number, total?: number): string {
  return total && total > held ? `${held} of ${total} sheets` : `${held} sheets`;
}

/**
 * The rows, with each raster archive folded together with the database series
 * it is a half of. A database series nothing claims stands on its own, which is
 * every series but L7014 — so this costs nothing until a second pre-tiled
 * archive appears, and then it costs one `halfOf`.
 */
export function buildSeriesRows(
  db: MapSeries[],
  canSeeDrafts: boolean,
  rasters: RasterSeries[]
): SeriesRow[] {
  const claimed = new Set<string>();
  const rows: SeriesRow[] = rasters.map((r) => {
    const half = db.find((s) => s.key === r.halfOf);
    if (half) claimed.add(half.key);
    // Mosaic under, warped sheets over. The sheets are a sharper survey of the
    // ground the mosaic is missing, and belong above the pixels.
    const refs: SeriesRef[] = half ? [r.ref, sheetsRef(half)] : [r.ref];
    return {
      key: r.ref.key,
      name: r.name,
      refs,
      // Summed, this is finally the honest number: a row that draws both halves
      // may say what both halves hold. Only one year span, because the
      // mosaic's 1963–89 already contains the sheets' 1966–84.
      label: count(r.sheets + (half?.sheets ?? 0), half?.surveySheets),
      note: [r.note, half && draftsNote(half, canSeeDrafts)].filter(Boolean).join(' · '),
      // The coverage page belongs to the database series, not the archive: the
      // index lives in `series_sheets`, keyed by `series_key`. An archive that
      // is half of nothing, or a survey whose index was never imported, has no
      // page — so no link.
      seriesKey: half?.surveySheets ? half.key : undefined,
    };
  });

  for (const s of db) {
    if (claimed.has(s.key)) continue;
    rows.push({
      key: s.key,
      name: s.name,
      refs: [sheetsRef(s)],
      label: count(s.sheets, s.surveySheets),
      note: seriesNote(s, canSeeDrafts),
      seriesKey: s.surveySheets ? s.key : undefined,
    });
  }
  return rows;
}
