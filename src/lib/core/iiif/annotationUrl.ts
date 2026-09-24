// ---- Allmaps annotation URL resolver ----
// Lives in $lib/core/iiif (not $lib/map/shell) so pure utilities — geo/mapBounds,
// iiif/iiifImageInfo — can resolve an annotation source without pulling
// @allmaps/openlayers (and the whole WarpedMapLayer bundle) in with them.

import { generateId } from '@allmaps/id';

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
 * The editor keys a map off its IIIF resource, not off an annotation: it
 * hashes whatever URL you hand it (`@allmaps/id`'s `generateId`, the same
 * function `verifiedEditorSourceId` below calls) and looks up the annotation
 * filed under that hash. Hand it the wrong URL for a given map and it opens a
 * blank canvas, not an error — that hash simply has nothing behind it yet.
 *
 * An R2 source is skipped by default — most maps were georeferenced against
 * their original scan, so R2's URL usually hashes to a different id than
 * `allmaps_id` and would open blank. `verifiedSourceId` overrides the default
 * whenever it matches one of `sources`, r2 included, for the sheets where
 * that default is backwards (the whole District 4 series; 1942 most visibly —
 * its R2 copy is a distinct, higher-res rescan the original scan never had).
 *
 * Pass `verifiedEditorSourceId(map, sources)`'s result as `verifiedSourceId`.
 * Do not pass a `target.source.id` read out of a stored annotation mirror —
 * that field records whatever the mirror was last rewritten to, not what
 * `allmaps_id` is actually keyed to on Allmaps' own server, and the two can
 * disagree for months without anything flagging it (confirmed 2026-09-23:
 * every R2-mirrored map but one hashed to a different id than its
 * `allmaps_id`, because mirroring always rewrites the stored copy's source to
 * R2 regardless of what's actually live upstream).
 *
 * Returns '' when the map carries nothing the editor can open.
 */
export function allmapsEditorSourceUrl(
  map: {
    annotation_url?: string | null;
    allmaps_id?: string | null;
  },
  sources: {
    iiif_image?: string | null;
    iiif_manifest?: string | null;
    source_type?: string | null;
  }[] = [],
  verifiedSourceId?: string | null
): string {
  if (verifiedSourceId) {
    const stripInfoJson = (u: string) => u.replace(/\/info\.json$/, '');
    const matched = sources.find(
      (s) => s.iiif_image && stripInfoJson(s.iiif_image) === stripInfoJson(verifiedSourceId)
    )?.iiif_image;
    if (matched) return withInfoJson(matched);
  }
  // maps.iiif_manifest was dropped (mig 095, dead/duplicated) — a manifest now
  // only lives per-source, on map_images (was map_iiif_sources).
  const manifest =
    sources.find((s) => s.source_type !== 'r2' && s.iiif_manifest)?.iiif_manifest ??
    sources.find((s) => s.iiif_manifest)?.iiif_manifest;
  if (manifest) return withInfoJson(manifest);
  const original = sources.find((s) => s.source_type !== 'r2' && s.iiif_image)?.iiif_image;
  if (original) return withInfoJson(original);
  // An annotation URL is not a IIIF resource, so it never takes /info.json —
  // appending one 404s. The editor resolves the image from the annotation itself.
  if (!map.annotation_url && map.allmaps_id)
    return `https://annotations.allmaps.org/images/${map.allmaps_id}`;
  return '';
}

/**
 * Ground truth for which of a map's IIIF sources its Allmaps annotation is
 * actually keyed to. Hashes each candidate the way Allmaps itself does and
 * returns the one that matches `map.allmaps_id` — no network fetch, and
 * nothing to go stale, unlike reading `target.source.id` out of a mirror copy
 * (see `allmapsEditorSourceUrl` above).
 */
export async function verifiedEditorSourceId(
  map: { allmaps_id?: string | null },
  sources: { iiif_image?: string | null; iiif_manifest?: string | null }[]
): Promise<string | null> {
  if (!map.allmaps_id) return null;
  const candidates = [
    ...sources.map((s) => s.iiif_manifest),
    ...sources.map((s) => s.iiif_image),
  ].filter((u): u is string => !!u);
  for (const url of candidates) {
    if ((await generateId(url)) === map.allmaps_id) return url;
  }
  return null;
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
