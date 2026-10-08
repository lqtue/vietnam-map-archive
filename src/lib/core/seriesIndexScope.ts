/** Catalogue-backed lists whose historical survey denominator is not established. */
const PARTIAL = new Set([
  'ams-l909-viet-nam-city-maps-1-12-500',
  // 44 sheets, numbered 01-44 with no gap; whether the atlas had more is unknown.
  'south-vietnam-provincial-maps-1971',
]);
export const isPartialSeriesIndex = (key: string): boolean => PARTIAL.has(key);
