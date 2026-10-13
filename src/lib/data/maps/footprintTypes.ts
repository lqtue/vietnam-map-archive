import { INK, inkAlpha } from '$lib/core/ink';

// Legend items: simple string ("Building") or transcription object ({val: "1", label: "Abattoir Municipal"})
export type LegendItem = string | { val: string; label: string };

// [x, y] pairs in IIIF pixel space (y+ = down, matching IIIF convention)
export type PixelCoord = [number, number];

// Geometry type — determines Polygon vs LineString rendering
// Polygon: parcel, building, land_plot, green_space, water_body; closed road/water surface rings
// LineString: open road/waterway centrelines
export type FeatureType =
  | 'parcel' // a street block: holds land_plots and buildings; roads are the space between
  | 'building'
  | 'land_plot'
  | 'road'
  | 'waterway'
  | 'green_space' // parks, gardens, cemeteries
  | 'water_body' // lakes, ponds (area, not flowing)
  | 'other';

export const FEATURE_TYPE_LABELS: Record<FeatureType, string> = {
  parcel: 'Parcel',
  building: 'Building',
  land_plot: 'Land Plot',
  road: 'Road',
  waterway: 'Waterway',
  green_space: 'Green Space',
  water_body: 'Water Body',
  other: 'Other',
};

/**
 * One colour per feature type, for every surface that shows footprints.
 *
 * Until Sept 2026 there were three of these — the /explore layer, the trace
 * sidebar and the review sidebar each had their own, so a building was green
 * on the map, gold in one list and blue in the other. These are the /explore
 * values, because that is the public surface.
 */
export const FEATURE_TYPE_COLORS: Record<FeatureType, string> = {
  parcel: INK.purple,
  building: INK.green,
  land_plot: INK.yellow,
  road: INK.red,
  waterway: INK.blue,
  green_space: INK.olive,
  water_body: INK.blue,
  other: INK.slate,
};

/** Canvas fill opacity per type — a road wants less ink than a building. */
const FILL_ALPHA: Record<FeatureType, number> = {
  parcel: 0.1, // the plots and buildings inside it stay readable
  building: 0.35,
  land_plot: 0.25,
  road: 0.3,
  waterway: 0.35,
  green_space: 0.3,
  water_body: 0.3,
  other: 0.3,
};

/** `rgba(...)` fill for OpenLayers, which takes colour strings and not tokens. */
export function featureTypeFill(ft: string): string {
  const key = (ft in FEATURE_TYPE_COLORS ? ft : 'other') as FeatureType;
  return inkAlpha(FEATURE_TYPE_COLORS[key], FILL_ALPHA[key]);
}

// Geometry kind derived from feature type
export function geometryKind(ft: FeatureType, pixels?: PixelCoord[]): 'Polygon' | 'LineString' {
  if (ft !== 'road' && ft !== 'waterway') return 'Polygon';
  // Closed rings from surface-mask extraction are areas; hand-drawn open
  // sequences remain centrelines. Closure is part of the pixel geometry contract.
  const first = pixels?.[0],
    last = pixels?.at(-1);
  return pixels &&
    pixels.length >= 4 &&
    first &&
    last &&
    first[0] === last[0] &&
    first[1] === last[1]
    ? 'Polygon'
    : 'LineString';
}

export interface FootprintSubmission {
  id: string;
  mapId: string;
  userId: string;
  pixelPolygon: PixelCoord[]; // closed ring for Polygon, open sequence for LineString
  name: string | null;
  category: string | null;
  featureType: FeatureType;
  status: 'draft' | 'submitted' | 'needs_review' | 'approved' | 'rejected';
}
