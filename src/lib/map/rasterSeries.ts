/**
 * The pre-tiled raster archives — the one kind of series that is not `maps`
 * rows, so the one kind the database cannot describe.
 *
 * Everything else /explore offers as a series comes from the `map_series` view
 * (mig 082), which makes adding a survey a matter of ingesting sheets rather
 * than editing a file. An archive on our own tile domain has no row anywhere,
 * so it is declared here: pure data, no OpenLayers, importable by the
 * browser-less tests and by `overlayKind.ts`, which needs `halfOf` to know that
 * two saved stack rows are one survey. The tiles themselves are keyed by `key`
 * in `basemapStyle.ts`'s own archive table.
 */
export interface RasterSeries {
  /** The key `buildRasterOverlayLayer` resolves to a PMTiles archive. */
  key: string;
  name: string;
  /** The archive's own extent, from its PMTiles header. */
  bounds: [number, number, number, number];
  /**
   * The `map_series.key` of the database series this archive is the other half
   * of, or undefined when it stands alone. The two halves are complementary,
   * not alternative — see `SeriesRef` — so they are one row and one layer.
   */
  halfOf?: string;
  /** Cells in the archive. Not in the database, so it cannot be counted. */
  sheets: number;
  /** What the /explore row says under its name. */
  note: string;
}

/**
 * `sheets` is what the deployed archive holds, not what the survey has: 452 of
 * the 627 cells in `work/l7014/index.geojson`. The rest are 93 PCL never
 * published, 62 with no usable georeference (the city sheets, which are the
 * `maps` rows `halfOf` folds in) and 11 off-grid. Read it off
 * `work/l7014/build/<build>.geojson`, whose name matches `L7014_PMTILES_URL` —
 * counting anything else is counting a survey rather than an archive.
 */
export const RASTER_SERIES: RasterSeries[] = [
  {
    key: 'l7014',
    name: 'AMS L7014 1:50,000',
    bounds: [102.2499, 8.4999, 109.5001, 23.25],
    halfOf: 'series-l7014-vietnam-1-50-000',
    sheets: 452,
    note: '1963–89 · 1:50,000',
  },
];

/** The archive a stored series row belongs to — either half claims it. */
export function archiveFor(key: string): RasterSeries | undefined {
  return RASTER_SERIES.find((a) => a.key === key || a.halfOf === key);
}
