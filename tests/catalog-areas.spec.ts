import { test, expect } from '@playwright/test';
import {
  CATALOG_REGIONS,
  geographicRegions,
  matchesGeographicRegion,
} from '../src/lib/core/catalogRegions';
import {
  catalogAreaSummary,
  coverageAreas,
  matchesCoverageArea,
} from '../src/lib/core/catalogAreas';

test('geographic regions cover all 63 provinces once and keep mergers separate', () => {
  const provinces = CATALOG_REGIONS.flatMap((r) => [...r.provinces]);
  expect(provinces).toHaveLength(63);
  expect(new Set(provinces).size).toBe(63);
  const row = { regions: ['Hồ Chí Minh', 'Long An'], regions_2025: ['Hồ Chí Minh', 'Tây Ninh'] };
  expect(geographicRegions(row)).toEqual(['southeast', 'mekong-delta']);
  expect(matchesGeographicRegion(row, ['mekong-delta'])).toBe(true);
  expect(matchesGeographicRegion(row, ['red-river-delta'])).toBe(false);
  expect(geographicRegions({ region: 'Hà Nội' })).toEqual(['red-river-delta']);
  expect(geographicRegions({})).toEqual([]);
});

test('coverage matches secondary provinces and preserves the single-region fallback', () => {
  expect(
    matchesCoverageArea({ region: 'Hồ Chí Minh', regions: ['Hồ Chí Minh', 'Long An'] }, ['Long An'])
  ).toBe(true);
  expect(coverageAreas({ regions: [], region: 'Hà Nội' })).toEqual(['Hà Nội']);
  expect(matchesCoverageArea({ region: 'Hà Nội' }, ['Long An'])).toBe(false);
  expect(matchesCoverageArea({}, ['Hà Nội'])).toBe(false);
  expect(matchesCoverageArea({}, [])).toBe(true);
});

test('compact area labels prioritize cities without dropping secondary coverage', () => {
  const row = { region: 'Long An', regions: ['Long An', 'Hồ Chí Minh', 'Đồng Nai'] };
  expect(catalogAreaSummary(row)).toEqual({
    primary: 'Hồ Chí Minh',
    label: 'HCMC +2',
    full: 'Hồ Chí Minh, Long An, Đồng Nai',
  });
  expect(matchesCoverageArea(row, ['Long An'])).toBe(true);
  expect(row.regions).toEqual(['Long An', 'Hồ Chí Minh', 'Đồng Nai']);
  expect(catalogAreaSummary({ regions: ['Bắc Ninh', 'Hà Nội'] }).label).toBe('Hà Nội +1');
  expect(
    catalogAreaSummary({ region: 'Long An', regions: ['Tiền Giang', 'Long An'] }).primary
  ).toBe('Long An');
  expect(catalogAreaSummary({ regions: ['Hà Nội', 'Hà Nội'] }).label).toBe('Hà Nội');
  expect(catalogAreaSummary({}).label).toBe('—');
});
