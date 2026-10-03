import type { SeriesRef } from '$lib/map/stores/layersStore';
import type { MapSeries } from '$lib/data/maps/types';

/**
 * The series list /explore offers above the sheet rows: one row per survey,
 * tap to put the whole thing on the map. A row is one layer — the `maps` rows of one
 * collection, warped live by Allmaps. (Until 2026-10-03 L7014 was also a pre-tiled PMTiles mosaic folded
 * into its row; every sheet of it is a `maps` row now, so there is nothing to fold.)
 */
export interface SeriesRow {
  key: string;
  name: string;
  /** The one layer this row puts on the map. */
  ref: SeriesRef;
  label: string;
  note: string;
  /**
   * The survey's `map_series.key`, which is also its `series_sheets.series_key`
   * and so the address of its coverage page at `/catalog/series/<key>`.
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
 * it contains (mig 083/084). A null denominator means no index was
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
export function buildSeriesRows(db: MapSeries[], canSeeDrafts: boolean): SeriesRow[] {
  return db.map((s) => ({
    key: s.key,
    name: s.name,
    ref: {
      kind: 'series',
      mapId: `series:${s.key}`,
      key: s.key,
      // The collection is the layer's name in the stack, where it sits beside
      // sheet names — so no year span here, which belongs in the note.
      name: s.name,
      parts: [{ kind: 'sheets', seriesKey: s.key, collection: s.collection }],
      bounds: s.bounds,
    },
    label: count(s.sheets, s.surveySheets),
    note: seriesNote(s, canSeeDrafts),
    seriesKey: s.surveySheets ? s.key : undefined,
  }));
}
