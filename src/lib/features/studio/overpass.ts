/**
 * Overpass API helpers — fetch OSM features for /explore?mode=annotate import.
 *
 * Query is built from a preset (or raw QL) + a (south, west, north, east) bbox
 * and posted to overpass-api.de. The result is converted to GeoJSON in-memory
 * (no external dep) so DrawTool can ingest it via importGeoJsonText.
 *
 * Supported OSM element types: node, way. Relations are skipped — multipolygon
 * assembly is non-trivial and rare in a single-viewport extract.
 */

const OVERPASS_URL = 'https://overpass-api.de/api/interpreter';

export type OverpassPreset =
  'buildings' | 'roads' | 'waterways' | 'parks' | 'railways' | 'amenities' | 'custom';

/** Visible map bbox as [west, south, east, north] in WGS84. */
export type Bbox4 = [number, number, number, number];

export interface OverpassImportOptions {
  preset: OverpassPreset;
  /** Required when preset === 'custom' — body of the Overpass QL query (no `[out:json]` / `out` lines). */
  customQuery?: string;
  bbox: Bbox4;
  /** Max number of seconds Overpass should spend on the query (default 25). */
  timeoutSec?: number;
}

const PRESET_QL: Record<Exclude<OverpassPreset, 'custom'>, string> = {
  // `nwr` = node | way | relation, but we only convert nodes+ways below.
  buildings: 'nwr["building"];',
  roads: 'way["highway"];',
  waterways: 'way["waterway"];',
  parks: '(way["leisure"="park"]; way["natural"="wood"]; way["leisure"="garden"];);',
  railways: 'way["railway"];',
  amenities: 'node["amenity"];',
};

export function presetLabel(p: OverpassPreset): string {
  switch (p) {
    case 'buildings':
      return 'Buildings';
    case 'roads':
      return 'Roads';
    case 'waterways':
      return 'Waterways';
    case 'parks':
      return 'Parks & green space';
    case 'railways':
      return 'Railways';
    case 'amenities':
      return 'Amenities (points)';
    case 'custom':
      return 'Custom query';
  }
}

export function buildQuery(opts: OverpassImportOptions): string {
  const timeout = opts.timeoutSec ?? 25;
  const [w, s, e, n] = opts.bbox;
  const body = opts.preset === 'custom' ? (opts.customQuery ?? '').trim() : PRESET_QL[opts.preset];
  if (!body) throw new Error('Empty Overpass query');
  // Bbox goes in the global setting so every statement inherits it.
  return `[out:json][timeout:${timeout}][bbox:${s},${w},${n},${e}];\n(${body});\nout body;\n>;\nout skel qt;`;
}

interface OverpassNode {
  type: 'node';
  id: number;
  lat: number;
  lon: number;
  tags?: Record<string, string>;
}
interface OverpassWay {
  type: 'way';
  id: number;
  nodes: number[];
  tags?: Record<string, string>;
}
interface OverpassRelation {
  type: 'relation';
  id: number;
  members: Array<{ type: string; ref: number; role: string }>;
  tags?: Record<string, string>;
}
type OverpassElement = OverpassNode | OverpassWay | OverpassRelation;

interface OverpassResponse {
  elements: OverpassElement[];
}

import type { Feature, FeatureCollection, Geometry } from 'geojson';

/** Convert an Overpass JSON response to a GeoJSON FeatureCollection. */
export function overpassToGeoJson(data: OverpassResponse): FeatureCollection {
  const nodeCoords = new Map<number, [number, number]>();
  for (const el of data.elements) {
    if (el.type === 'node') nodeCoords.set(el.id, [el.lon, el.lat]);
  }

  const features: Feature[] = [];

  for (const el of data.elements) {
    if (el.type === 'node') {
      // Only emit tagged nodes — untagged nodes are just way vertices.
      if (!el.tags || Object.keys(el.tags).length === 0) continue;
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [el.lon, el.lat] },
        properties: featureProps(el.tags, `node/${el.id}`),
      });
    } else if (el.type === 'way') {
      const coords = el.nodes
        .map((id) => nodeCoords.get(id))
        .filter((c): c is [number, number] => !!c);
      if (coords.length < 2) continue;
      const closed =
        coords.length >= 4 &&
        coords[0][0] === coords[coords.length - 1][0] &&
        coords[0][1] === coords[coords.length - 1][1];
      const isArea = closed && wayLooksLikeArea(el.tags);
      const geometry: Geometry = isArea
        ? { type: 'Polygon', coordinates: [coords] }
        : { type: 'LineString', coordinates: coords };
      features.push({
        type: 'Feature',
        geometry,
        properties: featureProps(el.tags ?? {}, `way/${el.id}`),
      });
    }
    // Relations skipped.
  }

  return { type: 'FeatureCollection', features };
}

function featureProps(tags: Record<string, string>, osmId: string) {
  // Pick a human-readable label and a colour by category.
  const label = tags.name || tags.ref || tags.addr_housename || osmId;
  const color = colorForTags(tags);
  return {
    label,
    color,
    hidden: false,
    osm_id: osmId,
    ...tags,
  };
}

function wayLooksLikeArea(tags?: Record<string, string>): boolean {
  if (!tags) return false;
  if (tags.area === 'yes') return true;
  if (tags.area === 'no') return false;
  // Common area-implying keys (small whitelist — full OSM list is huge).
  return Boolean(
    tags.building || tags.landuse || tags['leisure'] || tags['natural'] || tags.amenity || tags.shop
  );
}

function colorForTags(tags: Record<string, string>): string {
  if (tags.building) return '#7b6b9e';
  if (tags.highway) return '#5b8a72';
  if (tags.waterway) return '#2563eb';
  if (tags.railway) return '#7c3a3a';
  if (tags.leisure || tags.natural) return '#3f8a3f';
  if (tags.amenity) return '#d4af37';
  return '#2563eb';
}

/** POST a built Overpass query and return the parsed JSON. */
export async function fetchOverpass(query: string): Promise<OverpassResponse> {
  const res = await fetch(OVERPASS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `data=${encodeURIComponent(query)}`,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`Overpass ${res.status}: ${txt.slice(0, 200)}`);
  }
  return (await res.json()) as OverpassResponse;
}
