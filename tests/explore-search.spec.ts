import { expect, test } from '@playwright/test';
import { get } from 'svelte/store';
import {
  createExploreSearch,
  createExplorePickedFilter,
  type ExploreSearchPage,
} from '../src/lib/features/shared/exploreSearch';

const result = (ids: string[], nextCursor: string | null = null): ExploreSearchPage => ({
  maps: ids.map((id) => ({ id })),
  total: { maps: 10000, drafts: 2, scout: 0 },
  facets: { series_key: { large: 9999 } },
  choices: { area: [], region: [], type: [], institution: [], series: [] },
  yearBins: [{ decade: 1960, count: 9999 }],
  seriesCounts: { large: 9999 },
  nextCursor,
});
const json = (body: unknown) => new Response(JSON.stringify(body));

test('Explore keeps one page while totals and series matches cover the full query', async () => {
  const calls: URL[] = [];
  const search = createExploreSearch({
    debounceMs: 0,
    fetch: (async (url) => {
      const params = new URL(String(url), 'http://local');
      calls.push(params);
      return json(
        params.searchParams.has('cursor') ? result(['last']) : result(['first'], 'cursor')
      );
    }) as typeof fetch,
  });
  try {
    search.start();
    await expect.poll(() => get(search.mapsReady)).toBe(true);
    expect(get(search.total).maps).toBe(10000);
    expect(get(search.seriesCounts!)).toEqual({ large: 9999 });
    expect(get(search.yearBins)).toEqual([{ decade: 1960, count: 9999 }]);
    search.pagination!.next();
    await expect.poll(() => get(search.results).map((r) => r.id)).toEqual(['last']);
    expect(get(search.pagination!.page)).toBe(2);
    expect(calls[1].searchParams.get('cursor')).toBe('cursor');
    search.pagination!.previous();
    await expect.poll(() => get(search.results).map((r) => r.id)).toEqual(['first']);
    expect(calls[2].searchParams.has('cursor')).toBe(false);
    expect(calls.every((call) => call.searchParams.get('limit') === '60')).toBe(true);
  } finally {
    search.destroy!();
  }
});

test('changing filters cancels old rows immediately and resets pagination', async () => {
  const calls: URL[] = [];
  const search = createExploreSearch({
    debounceMs: 0,
    fetch: (async (url) => {
      calls.push(new URL(String(url), 'http://local'));
      return json(result(['row'], 'next'));
    }) as typeof fetch,
  });
  try {
    search.start();
    await expect.poll(() => get(search.mapsReady)).toBe(true);
    search.pagination!.next();
    await expect.poll(() => calls.length).toBe(2);
    await expect.poll(() => get(search.loading)).toBe(false);
    search.setSingle('series_key', 'large');
    expect(get(search.results)).toEqual([]);
    expect(get(search.pagination!.page)).toBe(1);
    await expect.poll(() => calls.length).toBe(3);
    expect(calls[2].searchParams.has('cursor')).toBe(false);
    expect(JSON.parse(calls[2].searchParams.get('filters')!)).toEqual({ series_key: ['large'] });
  } finally {
    search.destroy!();
  }
});

test('a response arriving during a new query cannot replace its results', async () => {
  let finish!: (response: Response) => void;
  let calls = 0;
  const search = createExploreSearch({
    debounceMs: 0,
    fetch: (() => {
      calls++;
      if (calls === 1)
        return new Promise<Response>((resolve) => {
          finish = resolve;
        });
      return Promise.resolve(json(result(['new'])));
    }) as typeof fetch,
  });
  try {
    search.start();
    search.query.set('new');
    finish(json(result(['obsolete'])));
    await expect.poll(() => get(search.results).map((row) => row.id)).toEqual(['new']);
  } finally {
    search.destroy!();
  }
});

test('failed searches show an error and retry restores readiness', async () => {
  let calls = 0;
  const search = createExploreSearch({
    fetch: (async () =>
      ++calls === 1 ? new Response('', { status: 503 }) : json(result(['ok']))) as typeof fetch,
  });
  try {
    search.start();
    await expect.poll(() => get(search.mapsError)).toBe(true);
    expect(get(search.mapsReady)).toBe(false);
    search.refresh();
    await expect.poll(() => get(search.mapsReady)).toBe(true);
    expect(get(search.mapsError)).toBe(false);
  } finally {
    search.destroy!();
  }
});

test('destroy cancels scheduled searches and ignores late results', async () => {
  let finish!: (response: Response) => void;
  let calls = 0;
  const search = createExploreSearch({
    debounceMs: 10,
    fetch: (() => {
      calls++;
      return new Promise<Response>((resolve) => {
        finish = resolve;
      });
    }) as typeof fetch,
  });
  search.start();
  search.query.set('pending');
  search.destroy!();
  finish(json(result(['late'])));
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(calls).toBe(1);
  expect(get(search.results)).toEqual([]);
});

test('picked layers match beyond the archive page using bounded id batches', async () => {
  const sizes: number[] = [];
  const picked = createExplorePickedFilter((async (url) => {
    const params = new URL(String(url), 'http://local').searchParams;
    const ids: string[] = JSON.parse(params.get('ids')!);
    sizes.push(ids.length);
    return json(result(ids.filter((id) => id === 'selected-204')));
  }) as typeof fetch);
  try {
    await picked.update(
      'Huế',
      { year: ['1960', '1970'] },
      Array.from({ length: 205 }, (_, i) => `selected-${i}`)
    );
    expect(sizes).toEqual([100, 100, 5]);
    expect(get(picked.ids)).toEqual(['selected-204']);
    await picked.update(
      'Huế',
      { year: ['1960', '1970'] },
      Array.from({ length: 205 }, (_, i) => `selected-${204 - i}`)
    );
    expect(sizes).toEqual([100, 100, 5]);
    await picked.update('', {}, []);
    expect(get(picked.ids)).toBeNull();
  } finally {
    picked.destroy();
  }
});
