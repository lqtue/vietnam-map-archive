import { expect, test } from '@playwright/test';
import { get } from 'svelte/store';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '../src/lib/data/supabase/types';
import type { SeriesRef } from '../src/lib/map/stores/layersStore';
import { createExploreInspection } from '../src/lib/features/explore/exploreInspection';
import { resolveSeriesKeys } from '../src/lib/data/maps/seriesKeys';

const series: SeriesRef = {
  kind: 'series',
  mapId: 'series:s',
  key: 's',
  name: 'Survey',
  parts: [{ kind: 'sheets', seriesKey: 's', collection: 'Survey' }],
  bounds: [0, 0, 1, 1],
};
function db(legacy = false) {
  return {
    from: () => {
      let column = '';
      const query = {
        select: () => query,
        eq: (c: string) => {
          column = c;
          return query;
        },
        order: () => query,
        limit: async () => ({
          data: legacy && column === 'key' ? [] : [{ key: legacy ? 'canonical' : 's' }],
          error: null,
        }),
      };
      return query;
    },
  } as unknown as SupabaseClient<Database>;
}
const json = (body: unknown) =>
  new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });

test('saved collection fallback resolves only after the saved key is absent', async () => {
  expect(await resolveSeriesKeys(db(), series)).toEqual([['s']]);
  expect(await resolveSeriesKeys(db(true), series)).toEqual([['canonical']]);
});

test('inspection retains one page and carries exact total with cursor navigation', async () => {
  const urls: URL[] = [];
  const inspector = createExploreInspection({
    supabase: db(),
    maps: () => [],
    open: () => {},
    fetch: async (input) => {
      const url = new URL(String(input), 'http://localhost');
      urls.push(url);
      const second = !!url.searchParams.get('cursor');
      return json({
        maps: [{ id: second ? 'second' : 'first', name: 'Sheet' }],
        total: { maps: 5000 },
        nextCursor: second ? null : JSON.stringify({ year: 1900, name: 'Sheet', id: 'first' }),
      });
    },
  });
  await inspector.inspectSeries({ ref: series, tab: 'info' });
  expect(get(inspector)).toMatchObject({ total: 5000, page: 1, hasNext: true, mapId: 'first' });
  expect(urls[0].searchParams.get('limit')).toBe('60');
  expect(urls[0].searchParams.get('sources')).toBe('1');
  inspector.nextPage();
  await expect.poll(() => get(inspector).loading).toBe(false);
  expect(get(inspector)).toMatchObject({ total: 5000, page: 2, hasNext: false, mapId: 'second' });
  expect(get(inspector).maps.map((row) => row.id)).toEqual(['second']);
  inspector.previousPage();
  await expect.poll(() => get(inspector).loading).toBe(false);
  expect(get(inspector).mapId).toBe('first');
  inspector.destroy();
});
