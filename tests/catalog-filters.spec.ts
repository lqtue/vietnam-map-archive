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
  passArea,
  passYear,
  yearRange,
  passInstitution,
  seriesOptions,
  sheetLabel,
  seriesShort,
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

test('a sheet label carries the half only when the sheet is cut in two', () => {
  expect(sheetLabel({ sheet_number: '5929-3', sheet_half: 'E' })).toBe('5929-3 E');
  expect(sheetLabel({ sheet_number: '5929-3', sheet_half: 'whole' })).toBe('5929-3');
  expect(sheetLabel({ sheet_number: null })).toBe('');
});

test('series options list each survey once, the biggest first, and skip plans', () => {
  const rs = [
    { series_key: 'a', collection: 'A survey' },
    { series_key: 'b', collection: 'B survey' },
    { series_key: 'b', collection: 'B survey' },
    { series_key: null, collection: null },
  ];
  expect(seriesOptions(rs)).toEqual([
    { value: 'b', label: 'B survey' },
    { value: 'a', label: 'A survey' },
  ]);
});

test('a series name shortens to its head plus the scale', () => {
  expect(seriesShort('Series L7014 (Vietnam 1:50,000)')).toBe('L7014 1:50,000');
  expect(seriesShort('Indochine 1:100,000 — 2nd édition SGI (1947–1959)')).toBe(
    'Indochine 1:100,000'
  );
  expect(seriesShort('Indochine 1:25,000 — Tonkin & Thanh Hóa')).toBe('Indochine 1:25,000');
  expect(seriesShort('AMS L909 — Việt Nam City Maps 1:12,500')).toBe('AMS L909 1:12,500');
  expect(seriesShort(null)).toBe('');
});

test('Area matches every listed province, including sheets without a dominant province', () => {
  const sheet = { region: null, regions: ['Long An', 'Hồ Chí Minh'] };
  expect(passArea(sheet, { area: ['Hồ Chí Minh'] })).toBe(true);
  expect(passArea(sheet, { area: ['Hà Nội'] })).toBe(false);
  expect(passArea(sheet, {})).toBe(true);
  expect(passArea({ region: 'Long An' }, { area: ['Long An'] })).toBe(true);
});
