/**
 * allmaps.mjs — the push-only mirror to Allmaps (live.allmaps.org), no key needed.
 *
 * VMA storage is the master. A sheet is POSTed once and PATCHed after that (a second
 * POST creates a duplicate map on the same image), and what Allmaps holds is never
 * pulled back for a script-made sheet; `scripts/allmaps_drift.mjs` only reports a
 * difference. Facts from the 1971 pilot (docs/pipelines.md): `@context` must be the
 * single string below (an array 500s), and the read-back at
 * `annotations.allmaps.org/maps/<id>` is a W3C annotation, not a Georeferenced Map.
 */
import { parseAnnotation } from '@allmaps/annotation';

const LIVE = 'https://live.allmaps.org/maps';
const READ = 'https://annotations.allmaps.org/maps';
const CONTEXT = 'https://schemas.allmaps.org/map/2/context.json';
// Allmaps' Express front answers some default user agents with 403.
const HEADERS = { 'Content-Type': 'application/json', 'User-Agent': 'curl/8.7.1' };

/** The Georeferenced Map Allmaps takes, from one of our annotations. */
export function toAllmapsMap(annotation) {
  const [m] = parseAnnotation(annotation);
  if (!m) throw new Error('annotation holds no georeferenced map');
  return {
    '@context': CONTEXT,
    type: 'GeoreferencedMap',
    resource: m.resource,
    gcps: m.gcps,
    resourceMask: m.resourceMask,
    transformation: m.transformation,
  };
}

/** The map id in whatever a POST/PATCH answered with. Throws, with the body, if there is none. */
export function mapIdFrom(body) {
  let j;
  try {
    j = JSON.parse(body);
  } catch {
    j = null;
  }
  const raw = j?.mapId ?? j?.id ?? (j && Object.values(j).find((v) => typeof v === 'string'));
  const id = String(raw ?? '')
    .split('/')
    .pop();
  if (!/^[0-9a-f]{16}$/.test(id))
    throw new Error(`no Allmaps map id in response: ${body.slice(0, 200)}`);
  return id;
}

/** POST a new map, or PATCH `mapId` when we already pushed one. Returns the map id. */
export async function push(map, mapId = null) {
  const res = await fetch(mapId ? `${LIVE}/${mapId}` : LIVE, {
    method: mapId ? 'PATCH' : 'POST',
    headers: HEADERS,
    body: JSON.stringify(map),
  });
  const body = await res.text();
  if (!res.ok)
    throw new Error(`Allmaps ${mapId ? 'PATCH' : 'POST'} ${res.status}: ${body.slice(0, 200)}`);
  return mapId ?? mapIdFrom(body);
}

/** What Allmaps now serves for a map id, as a parsed Georeferenced Map, or null on a 404. */
export async function fetchMap(mapId) {
  const res = await fetch(`${READ}/${mapId}`, { headers: { 'User-Agent': HEADERS['User-Agent'] } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`annotations.allmaps.org ${res.status} for ${mapId}`);
  return parseAnnotation(await res.json())[0] ?? null;
}

const key = (g) => `${Math.round(g.resource[0])},${Math.round(g.resource[1])}`;

/**
 * How two Georeferenced Maps differ in what the placement is made of, [] when they agree.
 * Pixels compare after rounding (Allmaps stores integers), ground to 1e-6 degrees.
 */
export function differences(ours, theirs) {
  const out = [];
  const a = new Map(ours.gcps.map((g) => [key(g), g.geo]));
  const b = new Map(theirs.gcps.map((g) => [key(g), g.geo]));
  if (a.size !== b.size) out.push(`${a.size} GCPs here, ${b.size} there`);
  for (const [k, geo] of a) {
    const o = b.get(k);
    if (!o) out.push(`GCP at pixel ${k} missing there`);
    else if (Math.abs(o[0] - geo[0]) > 1e-6 || Math.abs(o[1] - geo[1]) > 1e-6)
      out.push(`GCP at pixel ${k} moved: ${geo} here, ${o} there`);
  }
  for (const k of b.keys()) if (!a.has(k)) out.push(`GCP at pixel ${k} only there`);
  const tn = (m) => m.transformation?.type ?? 'polynomial';
  if (tn(ours) !== tn(theirs)) out.push(`transformation ${tn(ours)} here, ${tn(theirs)} there`);
  const mk = (m) => JSON.stringify(m.resourceMask.map((p) => p.map(Math.round)));
  if (mk(ours) !== mk(theirs)) out.push('resource mask differs');
  return out;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const assert = (await import('node:assert')).strict;
  const m = (g, type = 'polynomial') => ({
    gcps: g,
    transformation: { type },
    resourceMask: [
      [0, 0],
      [9, 0],
      [9, 9],
    ],
  });
  const g = [
    { resource: [0, 0], geo: [106.1, 10.9] },
    { resource: [9, 9], geo: [106.2, 10.8] },
  ];
  assert.deepEqual(differences(m(g), m(structuredClone(g))), []);
  assert.equal(differences(m(g), m(g, 'thinPlateSpline')).length, 1);
  const moved = structuredClone(g);
  moved[0].geo[0] += 1e-4;
  assert.match(differences(m(g), m(moved))[0], /moved/);
  assert.equal(mapIdFrom('{"mapId":"9199d6e708ebe292"}'), '9199d6e708ebe292');
  assert.equal(
    mapIdFrom('{"id":"https://annotations.allmaps.org/maps/9199d6e708ebe292"}'),
    '9199d6e708ebe292'
  );
  assert.throws(() => mapIdFrom('oops'));
  console.log('ok');
}
