// ---- Allmaps annotation URL resolver ----
// Lives in $lib/core/iiif (not $lib/map/shell) so pure utilities — geo/mapBounds,
// iiif/iiifImageInfo — can resolve an annotation source without pulling
// @allmaps/openlayers (and the whole WarpedMapLayer bundle) in with them.

/**
 * Builds the Allmaps annotation URL for a given source.
 *
 * - Bare hex IDs → `https://annotations.allmaps.org/images/{id}`
 * - Full URLs passed through as-is (e.g. an R2/Supabase-mirrored annotation)
 */
export function annotationUrlForSource(source: string): string {
  const trimmed = source.trim();
  try {
    const url = new URL(trimmed);
    if (url.protocol === 'http:' || url.protocol === 'https:') return trimmed;
  } catch {
    // not a URL — treat as Allmaps image ID
  }
  return `https://annotations.allmaps.org/images/${trimmed}`;
}

/**
 * XYZ tile template for a georeferenced map, served warped by the Allmaps
 * tile server. Paste-able into any editor that takes `{z}/{x}/{y}` — iD on
 * OpenHistoricalMap, JOSM, QGIS.
 *
 * ponytail: leans on allmaps.xyz, a free public service. Self-host
 * @allmaps/tileserver on the R2 worker if it ever rate-limits us.
 */
export function allmapsTileUrl(source: string): string {
  return `https://allmaps.xyz/{z}/{x}/{y}.png?url=${encodeURIComponent(annotationUrlForSource(source))}`;
}

function withInfoJson(url: string): string {
  return /\.json($|\?)/.test(url) ? url : `${url.replace(/\/$/, '')}/info.json`;
}

/**
 * The URL to hand Allmaps Editor so it reopens an existing map's control points.
 *
 * The editor keys a map off its IIIF resource, not off an annotation, so the
 * source has to be the manifest or image service the map was georeferenced
 * from. An R2 source is deliberately skipped: `allmaps_id` derives from the
 * image URL, so opening our mirror would derive a different id and start a
 * blank map instead of loading the points already placed.
 *
 * Returns '' when the map carries nothing the editor can open.
 */
export function allmapsEditorSourceUrl(
  map: {
    iiif_manifest?: string | null;
    annotation_url?: string | null;
    allmaps_id?: string | null;
  },
  sources: { iiif_image?: string | null; source_type?: string | null }[] = []
): string {
  if (map.iiif_manifest) return withInfoJson(map.iiif_manifest);
  const original = sources.find((s) => s.source_type !== 'r2' && s.iiif_image)?.iiif_image;
  if (original) return withInfoJson(original);
  // An annotation URL is not a IIIF resource, so it never takes /info.json —
  // appending one 404s. The editor resolves the image from the annotation itself.
  if (!map.annotation_url && map.allmaps_id)
    return `https://annotations.allmaps.org/images/${map.allmaps_id}`;
  return '';
}

/**
 * The OpenHistoricalMap editor, opened with a warped sheet already set as its
 * background.
 *
 * The value has to be percent-encoded. iD reads its own hash with
 * `pair.split('=')` and keeps the pair only when that yields exactly two
 * parts — a raw tile template carries `?url=` and so yields three, and the
 * parameter is dropped without a word: the editor opens on Bing with the sheet
 * nowhere. Encoding is what iD itself does when it rewrites the hash, and it
 * decodes once on read.
 */
export function ohmEditorUrl(tileUrl: string, bbox?: number[] | null): string {
  const hash = [`background=custom:${encodeURIComponent(tileUrl)}`];
  if (bbox?.length === 4) {
    const [minLon, minLat, maxLon, maxLat] = bbox;
    const span = Math.max(maxLon - minLon, 1e-4);
    const zoom = Math.max(10, Math.min(18, Math.round(Math.log2(360 / span))));
    hash.push(
      `map=${zoom}/${((minLat + maxLat) / 2).toFixed(5)}/${((minLon + maxLon) / 2).toFixed(5)}`
    );
  }
  // OHM may otherwise open a user's preferred editor instead of iD, which
  // does not necessarily understand iD's custom-background hash parameter.
  return `https://www.openhistoricalmap.org/edit?editor=id#${hash.join('&')}`;
}
