import { expect, test } from '@playwright/test';
import { exploreMapsParameters, shapeExploreMaps } from '../src/lib/server/exploreMaps';

const params = (values: Record<string, string> = {}, staff = false) =>
  exploreMapsParameters(new URLSearchParams(values), staff);

test('Explore folds accents and tokenizes safely without accepting tsquery operators', () => {
  expect(params({ q: 'Huế Đà Nẵng | !' }).p_query).toBe('hue:* & da:* & nang:*');
  expect(params({ q: '6330-4' }).p_query).toBe('6330-4');
  expect(params({ q: '1960s' }).p_query).toBe('196:*');
  expect(params({ filters: '{"type":["plan"]}' }).p_filters.type).toEqual(['city_plan']);
});
test('Explore bounds results and trusts only the server role argument', () => {
  expect(params({ limit: '9999', staff: 'true', sources: '1' })).toMatchObject({
    p_limit: 100,
    p_staff: false,
    p_sources: true,
  });
  expect(params({}, true).p_staff).toBe(true);
  expect(params({ limit: '-3' }).p_limit).toBe(1);
  expect(params({ limit: 'garbage' }).p_limit).toBe(60);
});
test('Explore rejects malformed filters, points, IDs and cursors', () => {
  const invalid: Record<string, string>[] = [
    { filters: 'null' },
    { filters: '[]' },
    { filters: '{"area":[1]}' },
    { filters: '{"year":["1","2","3"]}' },
    { filters: '{"year":["NaN"]}' },
    { point: '[181,0]' },
    { point: '[0,91]' },
    { point: '[0,"0"]' },
    { ids: '["------------------------------------"]' },
    { cursor: '{"year":2147483648,"name":"a","id":"00000000-0000-0000-0000-000000000000"}' },
    { cursor: '{"year":null,"name":"a","id":"invalid"}' },
    { cursor: '[]' },
    { cursor: '{' },
  ];
  for (const values of invalid) expect(() => params(values)).toThrow();
});
test('Explore exposes a bounded allowlist of map properties', () => {
  const result = shapeExploreMaps({
    maps: [
      {
        id: 'one',
        name: 'Map',
        status: 'featured',
        is_georeferenced: true,
        extra_metadata: { private: true },
        description: 'large',
        publisher: 'BnF',
      },
    ],
    nextCursor: { year: null, name: 'Map', id: 'one' },
  });
  expect(result.maps[0]).toMatchObject({
    id: 'one',
    georef_done: true,
    isFeatured: true,
    dc_publisher: 'BnF',
  });
  expect(result.maps[0]).not.toHaveProperty('extra_metadata');
  expect(result.maps[0]).not.toHaveProperty('description');
  expect(JSON.parse(result.nextCursor!)).toMatchObject({ id: 'one' });
});

test('anonymous summary cache shares canonical queries, uses 300 seconds and isolates role/spatial requests', async () => {
  const { cachedExploreMaps } = await import('../src/lib/server/exploreMapsCache');
  const records = new Map<string, unknown>();
  const keys: string[] = [];
  let loads = 0;
  const load = async () => ({ value: ++loads });
  const cache = async <T>(
    _platform: unknown,
    key: string,
    read: () => Promise<T>,
    options: { ttl: number }
  ): Promise<T> => {
    expect(options.ttl).toBe(300);
    keys.push(key);
    if (!records.has(key)) records.set(key, await read());
    return records.get(key) as T;
  };
  const a = params({ filters: '{"institution":["BnF","TTU"],"area":["Huế"]}' });
  const b = params({ filters: '{"area":["Huế"],"institution":["TTU","BnF"]}' });
  expect(await cachedExploreMaps(undefined, true, a, load, cache)).toEqual({ value: 1 });
  expect(await cachedExploreMaps(undefined, true, b, load, cache)).toEqual({ value: 1 });
  expect(keys[0]).toBe(keys[1]);
  for (const [anonymous, args] of [
    [false, params()],
    [true, params({}, true)],
    [true, params({ point: '[106,10]' })],
    [true, params({ ids: '[]' })],
    [
      true,
      params({ cursor: '{"year":1900,"name":"Map","id":"00000000-0000-0000-0000-000000000000"}' }),
    ],
  ] as const)
    await cachedExploreMaps(undefined, anonymous, args, load, cache);
  expect(keys).toHaveLength(2);
  expect(loads).toBe(6);
  await cachedExploreMaps(undefined, true, params({ sources: '1' }), load, cache);
  expect(keys[2]).not.toBe(keys[0]);
});

test('exact-map neighbor retains both OR groups and role gates in the actual PostgREST request', async () => {
  const { createClient } = await import('@supabase/supabase-js');
  const { readExploreMap } = await import('../src/lib/server/exploreMap');
  const urls: URL[] = [];
  const current = {
    id: '00000000-0000-0000-0000-000000000001',
    name: 'Map, "A"',
    year: 1900,
    status: 'public',
    allmaps_id: 'scan',
  };
  const db = createClient('https://database.invalid', 'fake-key', {
    global: {
      fetch: async (request) => {
        urls.push(new URL(String(request)));
        return new Response(JSON.stringify(current), {
          headers: { 'content-type': 'application/json' },
        });
      },
    },
  });
  await readExploreMap(db as any, 'map-reference', false, 1);
  const step = urls[1].searchParams;
  expect(step.get('status')).toBe('neq.archived');
  expect(step.getAll('status')).toContain('in.(public,featured)');
  expect(step.getAll('or')).toHaveLength(2);
  expect(step.getAll('or')[0]).toContain('allmaps_id.not.is.null');
  expect(step.getAll('or')[1]).toContain('year.gt.1900');
  expect(step.getAll('or')[1]).toContain('year.is.null');
  expect(step.getAll('or')[1]).toContain('name.gt."Map, \\"A\\""');
  expect(step.get('order')).toBe('year.asc.nullslast,name.asc,id.asc');
  urls.length = 0;
  await readExploreMap(db as any, 'map-reference', true, -1);
  expect(urls[1].searchParams.getAll('status')).toEqual(['neq.archived']);
  expect(urls[1].searchParams.getAll('or')[1]).toContain('year.lt.1900');
  expect(urls[1].searchParams.get('order')).toBe('year.desc.nullsfirst,name.desc,id.desc');
});
