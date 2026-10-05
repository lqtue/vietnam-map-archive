import { test, expect } from '@playwright/test';
import {
  filterRows,
  facetCounts,
  facetChoices,
  activeCount,
  groupRows,
  type Facet,
} from '../src/lib/core/utils/facets';

/**
 * The filter/group layer behind /scan?mode=text (and, next, shapes and maps).
 *
 * What it must get right is the thing that looks like data rather than a bug:
 * a chip's count. A reviewer turns `validated` on beside `pending` to see what
 * is already done; if `pending` being the only chip on made `validated` read 0,
 * the chip would vanish and the comparison could not be made.
 */
type Row = { id: string; status: string; cat: string; conf: number; text: string };
const rows: Row[] = [
  { id: 'a', status: 'pending', cat: 'street', conf: 0.9, text: 'Rue Catinat' },
  { id: 'b', status: 'validated', cat: 'street', conf: 0.5, text: 'Rue Pasteur' },
  { id: 'c', status: 'validated', cat: 'place', conf: 0.95, text: 'Cho Ben Thanh' },
  { id: 'd', status: 'rejected', cat: 'place', conf: 0.2, text: 'noise' },
];
const facets: Facet<Row>[] = [
  { key: 'status', label: 'Status', kind: 'many', value: (r) => r.status, primary: true },
  { key: 'cat', label: 'Category', kind: 'many', value: (r) => r.cat },
  { key: 'conf', label: 'Conf', kind: 'min', value: (r) => String(r.conf) },
];
const ids = (rs: Row[]) => rs.map((r) => r.id).join('');

test('an empty selection passes every row; several values are any-of', () => {
  expect(ids(filterRows(rows, facets, {}))).toBe('abcd');
  expect(ids(filterRows(rows, facets, { status: ['pending', 'validated'] }))).toBe('abc');
  expect(ids(filterRows(rows, facets, { status: ['pending', 'validated'], cat: ['place'] }))).toBe(
    'c'
  );
  expect(ids(filterRows(rows, facets, { conf: ['0.9'] }))).toBe('ac');
});

test('search narrows alongside the facets', () => {
  const search = { query: ' rue ', text: (r: Row) => r.text };
  expect(ids(filterRows(rows, facets, { status: ['validated'] }, search))).toBe('b');
});

test('a facet counts against every other choice but not its own', () => {
  const counts = facetCounts(rows, facets, { status: ['pending'], cat: ['street'] });
  // Status ignores itself: validated shows what turning it on would add.
  expect(counts.status).toEqual({ pending: 1, validated: 1 });
  // Category ignores itself, but honours status=pending.
  expect(counts.cat).toEqual({ street: 1 });
  // A search that misses a row removes it from every tally.
  const q = facetCounts(rows, facets, {}, { query: 'rue', text: (r) => r.text });
  expect(q.status).toEqual({ pending: 1, validated: 1 });
});

test('a chosen chip survives a zero count; server totals win over the tally', () => {
  const status = facets[0];
  expect(facetChoices(status, {}, ['rejected']).map((c) => c.value)).toEqual(['rejected']);
  // Named values are always offered; an empty value never is.
  const named: Facet<Row> = { ...status, values: ['pending', 'rejected'] };
  expect(facetChoices(named, { pending: 2 }, []).map((c) => c.value)).toEqual([
    'pending',
    'rejected',
  ]);
  expect(facetChoices(status, { '': 3, flag: 1 }, []).map((c) => c.value)).toEqual(['flag']);
  const withTotals = facetChoices(status, { pending: 1 }, [], { pending: 80, validated: 5 });
  expect(withTotals.map((c) => `${c.value}:${c.count}`)).toEqual(['pending:80', 'validated:5']);
});

test('only changed facets are active, and primary ones are not counted', () => {
  expect(activeCount(facets, { status: ['validated'] }, { status: ['pending'] })).toBe(0);
  expect(activeCount(facets, { cat: ['place', 'street'] }, { cat: ['street', 'place'] })).toBe(0);
  expect(activeCount(facets, { cat: ['place'], conf: ['0.5'] }, { cat: ['street'] })).toBe(2);
});

test('groups keep first-appearance order unless told one, and rows keep theirs', () => {
  const byStatus = groupRows(rows, (r) => r.status);
  expect(byStatus.map((g) => g.key)).toEqual(['pending', 'validated', 'rejected']);
  const ordered = groupRows([rows[3], rows[1], rows[0]], (r) => r.status, [
    'pending',
    'validated',
    'rejected',
  ]);
  expect(ordered.map((g) => g.key)).toEqual(['pending', 'validated', 'rejected']);
  expect(ids(groupRows(rows, (r) => r.cat).flatMap((g) => g.rows))).toBe('abcd');
});
