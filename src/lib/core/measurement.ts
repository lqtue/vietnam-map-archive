/** Privacy boundary for browser measurement: only named events and bounded values pass. */
export type MeasurementActor = 'guest' | 'reader' | 'staff' | 'unknown';

export const MEASUREMENT_EVENTS = [
  'map_open',
  'search_completed',
  'search_result_open',
  'contribution_open',
  'draft_started',
  'save_success',
  'source_open',
  'export_completed',
  'support_invitation_view',
  'support_open',
] as const;

export type MeasurementEvent = (typeof MEASUREMENT_EVENTS)[number];
export type MeasurementParams = Record<string, string | number | boolean>;

const ALLOWED_VALUES: Record<string, readonly string[]> = {
  surface: ['explore', 'catalog', 'scan', 'stories', 'contribute', 'support', 'palette', 'sheet'],
  workflow: [
    'search',
    'browse',
    'compare',
    'georeference',
    'shapes',
    'text',
    'story',
    'donation',
    'studio',
  ],
  result_kind: ['map', 'place', 'street', 'building', 'institution', 'hydrology', 'other'],
  action: ['open', 'save', 'submit', 'export', 'dismiss', 'complete'],
  mode: ['browse', 'studio', 'story', 'inspect', 'prepare', 'text', 'shapes', 'legend', 'walk'],
  result: ['success', 'failure'],
  actor: ['guest', 'reader'],
};

const ALLOWED_KEYS = new Set([
  'surface',
  'workflow',
  'result_kind',
  'action',
  'mode',
  'result',
  'actor',
  'result_count',
  'map_id',
]);

function safeMapId(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
  );
}

/** Drop unknown keys, free text, oversized values, and values outside fixed vocabularies. */
export function sanitizeMeasurementParams(input?: Record<string, unknown>): MeasurementParams {
  const output: MeasurementParams = {};
  if (!input || typeof input !== 'object') return output;

  for (const [key, value] of Object.entries(input)) {
    if (!ALLOWED_KEYS.has(key)) continue;
    if (key === 'map_id') {
      if (safeMapId(value)) output[key] = value;
      continue;
    }
    if (key === 'result_count') {
      if (typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 100_000) {
        output[key] = value;
      }
      continue;
    }
    const allowed = ALLOWED_VALUES[key];
    if (typeof value === 'string' && allowed?.includes(value)) output[key] = value;
  }
  return output;
}

/** Convert routes to canonical path templates; queries and fragments never enter analytics. */
export function canonicalMeasurementPath(pathname: string): string | null {
  if (typeof pathname !== 'string' || !pathname.startsWith('/') || pathname.length > 512)
    return null;
  let path =
    pathname
      .split(/[?#]/, 1)[0]
      .replace(/\/{2,}/g, '/')
      .replace(/\/$/, '') || '/';
  if (path === '/vi') path = '/';
  else if (path.startsWith('/vi/')) path = path.slice(3);
  if (
    [
      '/',
      '/explore',
      '/scan',
      '/catalog',
      '/directory',
      '/about',
      '/contribute',
      '/support',
      '/walk',
      '/stories',
    ].includes(path)
  ) {
    return path;
  }
  if (/^\/catalog\/series$/.test(path)) return path;
  if (path === '/catalog/institutions' || path === '/catalog/institutions/cartomundi') return path;
  if (/^\/catalog\/series\/[a-zA-Z0-9_-]{1,80}$/.test(path)) return '/catalog/series/:key';
  if (/^\/catalog\/series\/[a-zA-Z0-9_-]{1,80}\/[a-zA-Z0-9_-]{1,80}$/.test(path))
    return '/catalog/series/:key/:number';
  if (/^\/catalog\/area\/[a-zA-Z0-9_-]{1,100}$/.test(path)) return '/catalog/area/:slug';
  if (/^\/catalog\/place\/[a-zA-Z0-9_-]{1,100}$/.test(path)) return '/catalog/place/:slug';
  if (/^\/catalog\/cartomundi\/[a-zA-Z0-9_-]{1,100}$/.test(path)) return '/catalog/cartomundi/:id';
  if (/^\/catalog\/[a-zA-Z0-9_-]{1,100}$/.test(path)) return '/catalog/:slug';
  if (/^\/blog\/[a-zA-Z0-9_-]{1,100}$/.test(path)) return '/blog/:slug';
  if (/^\/trip\/[0-9a-f-]{36}$/i.test(path)) return '/trip/:id';
  return null;
}

export function sanitizeMeasurementMode(mode?: string): string | undefined {
  if (mode === 'annotate') mode = 'studio';
  return mode && ALLOWED_VALUES.mode.includes(mode) ? mode : undefined;
}
