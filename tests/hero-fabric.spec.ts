/**
 * The home page hero's frozen fabric.
 *
 * `scripts/gen/gen-hero-fabric.mjs` writes this file from the live archive, and the
 * hero draws it without asking anything at runtime. That trade only holds while
 * the generated data is actually drawable: a footprint whose properties lost
 * `feature_type` renders in the fallback colour, a label whose coordinates came
 * back as pixels rather than degrees lands off West Africa, and neither shows
 * up as an error — the hero just looks wrong, on the front page, silently.
 *
 * The runtime filter that used to catch un-warped rows now runs only on fetched
 * data, because the generator applies it. So the generator's output is the
 * thing to assert.
 */
import { expect, test } from '@playwright/test';
import {
  HERO_FOOTPRINTS,
  HERO_FOOTPRINT_COUNT,
  HERO_LABELS,
  HERO_LABEL_COUNT,
} from '../src/lib/features/explore/heroFabric';
import { FEATURE_TYPE_COLORS } from '../src/lib/data/maps/footprintTypes';

/** The 1882 Plan Cadastral, generously bounded. Saigon, not the Gulf of Guinea. */
const SHEET = { minLng: 106.6, maxLng: 106.8, minLat: 10.7, maxLat: 10.85 };

test('the counts the captions quote are the counts that are drawn', () => {
  expect(HERO_FOOTPRINTS.features.length).toBe(HERO_FOOTPRINT_COUNT);
  expect(HERO_LABELS.length).toBe(HERO_LABEL_COUNT);
  // A regeneration that returned nothing is the failure mode this catches: the
  // page still renders, just with an empty third and fourth beat.
  expect(HERO_FOOTPRINT_COUNT).toBeGreaterThan(0);
  expect(HERO_LABEL_COUNT).toBeGreaterThan(0);
});

test('every footprint carries the one property the layer styles on', () => {
  for (const f of HERO_FOOTPRINTS.features) {
    expect(typeof f.properties.feature_type).toBe('string');
    expect(f.properties.feature_type.length).toBeGreaterThan(0);
  }
});

test('feature types are ones the palette knows, not free text', () => {
  const known = new Set(Object.keys(FEATURE_TYPE_COLORS));
  for (const f of HERO_FOOTPRINTS.features) {
    expect(known.has(f.properties.feature_type), `unknown type ${f.properties.feature_type}`).toBe(
      true
    );
  }
});

test('footprint coordinates are degrees on the sheet, not pixels', () => {
  for (const f of HERO_FOOTPRINTS.features) {
    // Polygon rings, or a MultiPolygon's rings of rings — flatten to positions.
    const positions: number[][] = JSON.parse(JSON.stringify(f.geometry.coordinates))
      .flat(f.geometry.type === 'MultiPolygon' ? 2 : 1)
      .filter((p: unknown) => Array.isArray(p) && typeof p[0] === 'number');
    expect(positions.length).toBeGreaterThan(2);
    for (const [lng, lat] of positions) {
      expect(lng).toBeGreaterThan(SHEET.minLng);
      expect(lng).toBeLessThan(SHEET.maxLng);
      expect(lat).toBeGreaterThan(SHEET.minLat);
      expect(lat).toBeLessThan(SHEET.maxLat);
    }
  }
});

test('every label has text and lands on the sheet', () => {
  for (const [text, lng, lat] of HERO_LABELS) {
    expect(text.trim().length).toBeGreaterThan(0);
    expect(lng).toBeGreaterThan(SHEET.minLng);
    expect(lng).toBeLessThan(SHEET.maxLng);
    expect(lat).toBeGreaterThan(SHEET.minLat);
    expect(lat).toBeLessThan(SHEET.maxLat);
  }
});
