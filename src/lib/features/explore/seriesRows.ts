import type { SeriesPart, SeriesRef } from '$lib/map/stores/layersStore';
import { RASTER_SERIES, type RasterSeries } from '$lib/map/rasterSeries';
import type { MapSeries } from '$lib/data/maps/types';

export type { RasterSeries };

type Bbox = [number, number, number, number];

/**
 * The series list /explore offers above the sheet rows: one row per survey,
 * tap to put the whole thing on the map.
 *
 * A row is one layer, and it was two until Sept 2026. L7014 is held two ways —
 * 452 cells pre-tiled into a raster archive, 9 as `maps` rows warped live by
 * Allmaps — and those two are complementary, not alternative: the mosaic cannot
 * draw Saigon, because the 24 sheets over the city are the plain JPGs PCL
 * published with no embedded georeference, which is exactly why they are `maps`
 * rows at all; and the city sheets cannot draw anywhere else. Stacked as two
 * rows they read as a choice between two things, and cost the reader two
 * opacity sliders, two eyes and two of the ten stack slots to control one
 * survey. So they are the two `parts` of one `SeriesRef` instead.
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

/** The box that holds both halves — what "zoom to this layer" means for a row. */
function union(a: Bbox, b?: Bbox): Bbox {
  if (!b) return a;
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
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
  rasters: RasterSeries[] = RASTER_SERIES
): SeriesRow[] {
  const claimed = new Set<string>();
  const rows: SeriesRow[] = rasters.map((r) => {
    const half = db.find((s) => s.key === r.halfOf);
    if (half) claimed.add(half.key);
    // Mosaic under, warped sheets over. The sheets are a sharper survey of the
    // ground the mosaic is missing, and belong above the pixels.
    const parts: SeriesPart[] = [{ kind: 'raster', key: r.key }];
    if (half) parts.push({ kind: 'sheets', collection: half.collection });
    return {
      key: r.key,
      name: r.name,
      ref: {
        kind: 'series',
        mapId: `series:${r.key}`,
        key: r.key,
        name: r.name,
        parts,
        bounds: union(r.bounds, half?.bounds),
      },
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
      ref: {
        kind: 'series',
        mapId: `series:${s.key}`,
        key: s.key,
        // The collection is the layer's name in the stack, where it sits beside
        // sheet names — so no year span here, which belongs in the note.
        name: s.name,
        parts: [{ kind: 'sheets', collection: s.collection }],
        bounds: s.bounds,
      },
      label: count(s.sheets, s.surveySheets),
      note: seriesNote(s, canSeeDrafts),
      seriesKey: s.surveySheets ? s.key : undefined,
    });
  }
  return rows;
}
