import { test, expect } from '@playwright/test';
import { get } from 'svelte/store';
import { createExploreRuntime } from '../src/lib/features/explore/exploreRuntime';
import type { MapListItem } from '../src/lib/data/maps/types';

const map = (id: string) =>
  ({
    id,
    slug: `slug-${id}`,
    name: id,
    allmaps_id: `legacy-${id}`,
    status: 'public',
    bbox: [0, 0, 2, 2],
  }) as MapListItem;
const response = (body: unknown) =>
  new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });

test('selected metadata shares requests and resolves all legacy reference forms from cache', async () => {
  let calls = 0;
  const runtime = createExploreRuntime(async () => {
    calls++;
    return response({ map: map('one') });
  });
  const [a, b] = await Promise.all([runtime.ensure('one'), runtime.ensure('one')]);
  expect(a?.id).toBe('one');
  expect(b?.id).toBe('one');
  await runtime.ensure('slug-one');
  await runtime.ensure('legacy-one');
  expect(calls).toBe(1);
  runtime.destroy();
});

test('picking a slim search result hydrates its description once', async () => {
  let calls = 0;
  const runtime = createExploreRuntime(async () => {
    calls++;
    return response({ map: { ...map('selected'), dc_description: 'Full sheet description' } });
  });
  runtime.remember(map('selected'));
  await runtime.ensure('selected');
  await runtime.ensure('selected');
  expect(calls).toBe(1);
  expect(get(runtime.maps)[0].dc_description).toBe('Full sheet description');
  runtime.remember(map('selected'));
  expect(get(runtime.maps)[0].dc_description).toBe('Full sheet description');
  runtime.destroy();
});

test('metadata request concurrency and retained cache stay bounded, preserving pinned sheets', async () => {
  let active = 0;
  let maximum = 0;
  const runtime = createExploreRuntime(async (input) => {
    active++;
    maximum = Math.max(maximum, active);
    await new Promise((resolve) => setTimeout(resolve, 1));
    active--;
    return response({ map: map(new URL(String(input), 'https://local').searchParams.get('ref')!) });
  });
  await runtime.ensure('pinned');
  runtime.pin(['pinned']);
  await Promise.all(Array.from({ length: 130 }, (_, i) => runtime.ensure(String(i))));
  expect(maximum).toBeLessThanOrEqual(4);
  expect(get(runtime.maps)).toHaveLength(100);
  expect(get(runtime.maps).some((item) => item.id === 'pinned')).toBe(true);
  runtime.destroy();
});

test('coverage pages retain full counts, replace rows, and discard obsolete locations', async () => {
  const requests: { url: URL; resolve: (value: Response) => void }[] = [];
  const runtime = createExploreRuntime(
    (input) =>
      new Promise((resolve) =>
        requests.push({ url: new URL(String(input), 'https://local'), resolve })
      )
  );
  const old = runtime.locate([1, 1]);
  const current = runtime.locate([1.5, 1.5]);
  requests[1].resolve(
    response({ maps: [map('new')], total: { maps: 5000 }, nextCursor: '{"id":"new"}' })
  );
  await current;
  requests[0].resolve(response({ maps: [map('old')], total: { maps: 1 }, nextCursor: null }));
  await old;
  expect(get(runtime.coverage).matches.map((item) => item.id)).toEqual(['new']);
  expect(get(runtime.coverage).total).toBe(5000);
  const next = runtime.nextCoverage();
  expect(requests[2].url.searchParams.get('cursor')).toBe('{"id":"new"}');
  requests[2].resolve(response({ maps: [map('last')], total: { maps: 5000 }, nextCursor: null }));
  await next;
  expect(get(runtime.coverage).matches.map((item) => item.id)).toEqual(['last']);
  expect(get(runtime.coverage).hasNext).toBe(false);
  expect(get(runtime.coverage).page).toBe(2);
  const first = runtime.resetCoverage();
  expect(requests[3].url.searchParams.has('cursor')).toBe(false);
  requests[3].resolve(
    response({ maps: [map('new')], total: { maps: 5000 }, nextCursor: '{"id":"new"}' })
  );
  await first;
  expect(get(runtime.coverage).page).toBe(1);
  runtime.destroy();
});

test('coverage lookup failures are explicit and can be retried', async () => {
  let fail = true;
  const runtime = createExploreRuntime(async () =>
    fail
      ? new Response('', { status: 503 })
      : response({ maps: [], total: { maps: 0 }, nextCursor: null })
  );
  await runtime.locate([1, 1]);
  expect(get(runtime.coverage).error).toBe(true);
  fail = false;
  await runtime.resetCoverage();
  expect(get(runtime.coverage).error).toBe(false);
  runtime.destroy();
});
