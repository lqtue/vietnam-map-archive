/**
 * Pure checks for how a sheet is addressed in a URL. No browser, no network —
 * they ride the Playwright runner because it is already installed.
 *
 * The minting rule itself lives in Postgres (migration 088) and is pinned by
 * `tests/write.spec.ts` against the local stack. What is left here is the part
 * the browser owns, and it is all fallback behaviour: which of a row's
 * identifiers becomes the link, and which shapes an inbound `?map=` is allowed
 * to arrive in. Both matter because the failure is silent — a row that reaches
 * the UI without its slug would render a link that still works, and a `?map=`
 * shape that stopped resolving would open /explore on an empty map with no
 * error anywhere.
 */
import { test, expect } from '@playwright/test';
import { isUuid, mapRef, mapHref, exploreHref } from '../src/lib/core/utils/mapSlug';
import { resolveMapRef } from '../src/lib/data/maps/resolveRef';
import type { MapListItem } from '../src/lib/data/maps/types';

const UUID = '787439c7-8015-496d-a458-df61b89a4391';
const SHEET = { id: UUID, slug: 'plan-de-la-ville-de-saigon-1799' };

test('the slug is the address when a row carries one', () => {
  expect(mapRef(SHEET)).toBe('plan-de-la-ville-de-saigon-1799');
  expect(mapHref(SHEET)).toBe('/catalog/plan-de-la-ville-de-saigon-1799');
  expect(exploreHref(SHEET)).toBe('/explore?map=plan-de-la-ville-de-saigon-1799');
});

test('a row with no slug still produces a working link', () => {
  // Not a hypothetical: a label hit and a footprint submission reach the UI
  // carrying only `map_id`. A uuid there 301s to the readable address, which is
  // strictly better than rendering no link — so the fallback must not be
  // "optimised away" on the grounds that every map has a slug now.
  expect(mapRef({ id: UUID })).toBe(UUID);
  expect(mapRef({ id: UUID, slug: null })).toBe(UUID);
  expect(mapRef({ id: UUID, slug: '' })).toBe(UUID);
  expect(mapHref({ id: UUID })).toBe(`/catalog/${UUID}`);
});

test('isUuid tells the old address shape from the new one', () => {
  expect(isUuid(UUID)).toBe(true);
  expect(isUuid(UUID.toUpperCase())).toBe(true);
  expect(isUuid('plan-de-la-ville-de-saigon-1799')).toBe(false);
  // A slug that is all hex and hyphens must not be mistaken for a uuid.
  expect(isUuid('deadbeef-cafe')).toBe(false);
  expect(isUuid('')).toBe(false);
});

test('an inbound ?map= resolves in all three shapes it has ever taken', () => {
  const maps = [
    {
      id: UUID,
      slug: 'plan-de-la-ville-de-saigon-1799',
      allmaps_id: 'abcdef0123456789',
      name: 'x',
    },
    { id: '00000000-0000-4000-8000-000000000001', slug: 'vinh-yen-1906', name: 'y' },
  ] as MapListItem[];

  // The slug is what /explore writes today...
  expect(resolveMapRef(maps, 'vinh-yen-1906')?.id).toBe(maps[1].id);
  // ...the uuid is every link shared before it existed...
  expect(resolveMapRef(maps, UUID)?.id).toBe(UUID);
  // ...and `allmaps_id` is older still, carried by saved stories.
  expect(resolveMapRef(maps, 'abcdef0123456789')?.id).toBe(UUID);

  // A reference to nothing resolves to nothing rather than to the first row.
  expect(resolveMapRef(maps, 'vinh-yen-1919')).toBeNull();
  expect(resolveMapRef(maps, null)).toBeNull();
});
