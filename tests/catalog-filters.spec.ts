/**
 * Pure checks for the catalog's year range and its Surveys / Plans split. No browser, no network.
 *
 * They exist because both replaced something that read as data: the year range replaced six
 * hand-written periods, and the kind switch is what keeps Area (filled only on one-off plans) from
 * being offered over survey sheets where every value is empty.
 */
import { test, expect } from '@playwright/test';
import {
  decadeBins,
  passKind,
  passYear,
  yearRange,
  passInstitution,
} from '../src/lib/features/shared/catalogFilters';

const rows = [
  { year: 1791, series_key: null },
  { year: 1882, series_key: null },
  { year: 1965, series_key: 'l7014' },
  { year: 1969, series_key: 'l7014' },
  { year: null, series_key: 'l7014' },
];

test('a year range is inclusive, open at an empty end, and drops rows with no year', () => {
  const within = (year: string[]) => rows.filter((r) => passYear(r, { year })).map((r) => r.year);
  expect(within(['1880', '1969'])).toEqual([1882, 1965, 1969]);
  expect(within(['1900', ''])).toEqual([1965, 1969]);
  expect(within(['', '1800'])).toEqual([1791]);
  // No range at all keeps everything, undated rows included.
  expect(rows.filter((r) => passYear(r, {}))).toHaveLength(5);
  expect(yearRange({ year: ['', ''] })).toBeNull();
  expect(yearRange({ year: ['abc', ''] })).toBeNull();
});

test('kind splits survey sheets from plans, and empty means both', () => {
  expect(rows.filter((r) => passKind(r, { kind: ['surveys'] }))).toHaveLength(3);
  expect(rows.filter((r) => passKind(r, { kind: ['plans'] }))).toHaveLength(2);
  expect(rows.filter((r) => passKind(r, {}))).toHaveLength(5);
});

test('decadeBins runs oldest to newest and keeps the empty decades between', () => {
  const bins = decadeBins(rows);
  expect(bins[0]).toEqual({ decade: 1790, count: 1 });
  expect(bins.at(-1)).toEqual({ decade: 1960, count: 2 });
  expect(bins).toHaveLength(18);
  expect(bins.find((b) => b.decade === 1800)?.count).toBe(0);
  expect(decadeBins([{ year: null }])).toEqual([]);
});

test('institution matches the exact holding name', () => {
  expect(passInstitution({ holding_institution: 'BnF' }, { institution: ['BnF'] })).toBe(true);
  expect(passInstitution({ holding_institution: null }, { institution: ['BnF'] })).toBe(false);
});
