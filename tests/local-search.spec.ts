/**
 * Pure checks for the catalog's in-browser search. No browser, no network.
 *
 * They exist because the server's `simple` text-search config cannot fold accents, so the archive's
 * Vietnamese names were findable only by someone typing the diacritics — and because the sheet-number
 * rule has to survive moving here from the server.
 */
import { test, expect } from '@playwright/test';
import { matchesQuery, queryTokens } from '../src/lib/features/shared/localSearch';

const hue = {
  name: 'Plan de Huế',
  creator: 'Service géographique',
  year: 1923,
  sheet_number: null,
};
const hanoi = { name: 'Plan annamite d’Hanoï', year: 1880, year_label: 'ca. 1880' };
const sheet = { name: 'Saigon', year: 1965, sheet_number: '5929-3', location: 'Đà Nẵng' };

test('accents fold both ways, đ included', () => {
  expect(matchesQuery(hue, 'hue')).toBe(true);
  expect(matchesQuery(hue, 'Huế')).toBe(true);
  expect(matchesQuery(hanoi, 'hanoi')).toBe(true);
  expect(matchesQuery(sheet, 'da nang')).toBe(true);
  expect(matchesQuery(sheet, 'đà nẵng')).toBe(true);
});

test('every token must start a word, in any field', () => {
  expect(matchesQuery(hue, 'plan 192')).toBe(true); // name word + year prefix
  expect(matchesQuery(hue, 'plan 188')).toBe(false);
  expect(matchesQuery(hanoi, 'hano')).toBe(true);
  expect(matchesQuery(hanoi, 'noi')).toBe(false); // a prefix, not a substring
  expect(matchesQuery(hue, 'service')).toBe(true);
});

test('a decade written 1920s is its prefix', () => {
  expect(queryTokens('1920s')).toEqual(['192']);
  expect(matchesQuery(hue, '1920s')).toBe(true);
  expect(matchesQuery(hanoi, '1920s')).toBe(false);
});

test('a sheet number matches the column exactly, and nothing looser', () => {
  expect(matchesQuery(sheet, '5929-3')).toBe(true);
  expect(matchesQuery({ ...sheet, sheet_number: '5929-4' }, '5929-3')).toBe(false);
  // Its parts are years and house numbers: the dash form must not fall through to token matching.
  expect(matchesQuery({ name: 'Plan 5929 3' }, '5929-3')).toBe(false);
});

test('an empty or punctuation-only query keeps every row', () => {
  expect(matchesQuery(hue, '')).toBe(true);
  expect(matchesQuery(hue, '  ')).toBe(true);
  expect(matchesQuery(hue, '--')).toBe(true);
});
