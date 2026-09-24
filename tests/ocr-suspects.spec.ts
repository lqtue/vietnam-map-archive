/**
 * The printed legend used as an answer key for the numerals on the map.
 *
 * A numbered sheet states its own denominator: the 1942 Saigon–Cholon sheet
 * prints 1..236 (and skips 22 on the paper), so a numeral the index does not
 * list, or one claimed twice, is wrong without anyone opening the scan. These
 * cases pin the three checks the review table sorts by, and the join that puts
 * a name beside a bare number — without it a reviewer cannot tell a correct 37
 * from a misread 87.
 *
 * The parsing is the fragile half: the number and the grid cell live inside
 * `notes` as "n=..; grid=.." because `ocr_labels` has no column for
 * either, and a human correction lands in `text_validated` / `category_validated`
 * rather than over the model's own fields.
 */
import { test, expect } from '@playwright/test';
import {
  refValue,
  legendEntries,
  suspectRefs,
  entryForRow,
  ambiguousNumbers,
} from '../src/lib/features/contribute/ocr/legendIndex';
import type { OcrExtraction } from '../src/lib/features/contribute/shared/types';

const row = (over: Partial<OcrExtraction> & { id: string }): OcrExtraction => ({
  tile_x: 0,
  tile_y: 0,
  tile_w: 100,
  tile_h: 100,
  global_x: 10,
  global_y: 20,
  global_w: 30,
  global_h: 40,
  category: 'legend_ref',
  text: '1',
  text_validated: null,
  category_validated: null,
  confidence: 0.9,
  status: 'pending',
  notes: null,
  ...over,
});

const entry = (n: number, name: string, grid = '') =>
  row({
    id: `e${n}`,
    category: 'legend_entry',
    text: `${n}. ${name}`,
    notes: `n=${n}; grid=${grid}`,
  });

test('refValue reads the printed forms and rejects the rest', () => {
  expect(refValue('37')).toBe(37);
  // The inset references are printed in parentheses and the prompt keeps them.
  expect(refValue('(12)')).toBe(12);
  expect(refValue(' 8 ')).toBe(8);
  expect(refValue('')).toBeNull();
  expect(refValue('37a')).toBeNull();
  expect(refValue('Rue 37')).toBeNull();
  // Four digits is a year or a parcel number, not a legend key on this corpus.
  expect(refValue('1942')).toBeNull();
});

test('legendEntries strips the leading number and keeps the grid cell', () => {
  const e = legendEntries([
    entry(37, 'Hôpital Grall', 'B10'),
    entry(3, 'Arsenal de la Marine', 'B10-11'),
  ]);
  expect(e.get(37)).toEqual({ n: 37, name: 'Hôpital Grall', grid: 'B10', block: null });
  // A cell range stays verbatim — the paper says B10-11 and the reviewer reads it.
  expect(e.get(3)?.grid).toBe('B10-11');
  expect(e.get(3)?.name).toBe('Arsenal de la Marine');
});

test('an entry with no n= in its notes is skipped, not guessed at', () => {
  const e = legendEntries([
    row({ id: 'x', category: 'legend_entry', text: 'Mairie', notes: 'grid=E3' }),
  ]);
  expect(e.size).toBe(0);
});

test('a number the printed index does not list is flagged', () => {
  const rows = [
    entry(1, 'Abattoir Municipal'),
    row({ id: 'a', text: '1' }),
    row({ id: 'b', text: '240' }),
  ];
  const s = suspectRefs(rows);
  expect(s.get('b')).toEqual(['no-entry']);
  expect(s.has('a')).toBe(false);
});

test('the same number claimed twice flags both rows', () => {
  const rows = [entry(14, 'Casino'), row({ id: 'a', text: '14' }), row({ id: 'b', text: '14' })];
  const s = suspectRefs(rows);
  expect(s.get('a')).toEqual(['duplicate']);
  expect(s.get('b')).toEqual(['duplicate']);
});

test('the same number in two different runs is agreement, not a duplicate', () => {
  // The 1942 sheet carries numerals from two passes. Counted across the table,
  // every numeral in both runs read as a duplicate and the chip was useless.
  const rows = [
    entry(14, 'Casino'),
    row({ id: 'a', text: '14', run_id: 'idx-1' }),
    row({ id: 'b', text: '14', run_id: 'idx-2' }),
  ];
  expect(suspectRefs(rows).size).toBe(0);
});

test('two marks claiming one number inside a single run are still flagged', () => {
  const rows = [
    entry(14, 'Casino'),
    row({ id: 'a', text: '14', run_id: 'idx-1' }),
    row({ id: 'b', text: '14', run_id: 'idx-1' }),
    row({ id: 'c', text: '14', run_id: 'idx-2' }),
  ];
  const s = suspectRefs(rows);
  expect(s.get('a')).toEqual(['duplicate']);
  expect(s.get('b')).toEqual(['duplicate']);
  expect(s.has('c')).toBe(false);
});

test('a reference that is not a number is malformed, and is not also no-entry', () => {
  const s = suspectRefs([entry(1, 'Abattoir'), row({ id: 'a', text: '1a' })]);
  expect(s.get('a')).toEqual(['malformed']);
});

test('with no legend read, no-entry is skipped rather than flagging every numeral', () => {
  // The 22 sheets in the corpus whose legend nobody has run must not light up red.
  const s = suspectRefs([row({ id: 'a', text: '7' }), row({ id: 'b', text: '99' })]);
  expect(s.size).toBe(0);
});

test('only legend_ref rows are checked', () => {
  const rows = [entry(1, 'Abattoir'), row({ id: 's', category: 'street', text: '240' })];
  expect(suspectRefs(rows).size).toBe(0);
});

test('a human correction is what gets checked, not the model output', () => {
  const rows = [
    entry(1, 'Abattoir Municipal'),
    // The model read 240; a reviewer fixed it to 1, so the row is no longer suspect.
    row({ id: 'a', text: '240', text_validated: '1' }),
    // The model called it a street; a reviewer made it a numeral, so it is checked.
    row({ id: 'b', category: 'street', category_validated: 'legend_ref', text: '240' }),
  ];
  const s = suspectRefs(rows);
  expect(s.has('a')).toBe(false);
  expect(s.get('b')).toEqual(['no-entry']);
});

test('entryForRow is the name the table shows beside a bare numeral', () => {
  const rows = [entry(37, 'Hôpital Grall', 'B10')];
  const entries = legendEntries(rows);
  expect(entryForRow(row({ id: 'a', text: '37' }), entries)?.name).toBe('Hôpital Grall');
  // 22 is printed nowhere on this sheet: 21 Casino de Dakao, then 23 Casino de Saigon.
  expect(entryForRow(row({ id: 'b', text: '22' }), entries)).toBeNull();
  expect(entryForRow(row({ id: 'c', category: 'street', text: '37' }), entries)).toBeNull();
});

/**
 * A sheet that prints its index twice.
 *
 * The 1942 Saigon–Cholon sheet carries two `legend` blocks. Read into one table
 * they are one of two things and the numbers cannot say which: blocks that
 * continue one sequence (1..99, then 100..236), where joining a numeral by its
 * number is right; or two independent tables both numbering from 1, where the
 * join hands one table's name to the other table's numerals and `legendEntries`
 * — first writer wins — makes that invisible. The name is the evidence.
 *
 * `block=` in notes is written by `_write_legend_rows` in `ocr.py`, and only on
 * a sheet with more than one block, so every single-block sheet in the corpus
 * reads exactly as it did.
 */
const blockEntry = (n: number, name: string, block: number) =>
  row({
    id: `e${block}-${n}`,
    category: 'legend_entry',
    text: `${n}. ${name}`,
    notes: `n=${n}; grid=; block=${block}`,
  });

test('two blocks continuing one sequence are not ambiguous', () => {
  const rows = [
    blockEntry(1, 'Hôpital Grall', 0),
    blockEntry(99, 'Marché Central', 0),
    blockEntry(100, 'Chùa Bà', 1),
    blockEntry(236, 'Gare', 1),
  ];
  expect([...ambiguousNumbers(rows)]).toEqual([]);
  expect(suspectRefs([...rows, row({ id: 'a', text: '100' })]).size).toBe(0);
});

test('two independent tables flag every numeral of a shared number', () => {
  const rows = [
    blockEntry(1, 'Hôpital Grall', 0),
    blockEntry(52, 'Marché Central', 0),
    blockEntry(1, 'Chùa Bà', 1),
    blockEntry(52, 'Pagode', 1),
  ];
  expect([...ambiguousNumbers(rows)].sort((a, b) => a - b)).toEqual([1, 52]);
  const s = suspectRefs([...rows, row({ id: 'a', text: '52' }), row({ id: 'b', text: '1' })]);
  expect(s.get('a')).toEqual(['ambiguous-entry']);
  expect(s.get('b')).toEqual(['ambiguous-entry']);
});

test('the same line read twice is not two tables', () => {
  // Overlapping blocks, or a re-run: the reading differs in case and diacritics
  // and means the same line. Folding is what keeps that out of the flag.
  const rows = [blockEntry(52, 'Marché Central', 0), blockEntry(52, 'MARCHE  CENTRAL', 1)];
  expect([...ambiguousNumbers(rows)]).toEqual([]);
});

test('a single-block sheet carries no block= and is never ambiguous', () => {
  // Every sheet already in the corpus. The check must be inert on them.
  const rows = [entry(1, 'Abattoir'), entry(2, 'Arsenal')];
  expect([...ambiguousNumbers(rows)]).toEqual([]);
  expect(legendEntries(rows).get(1)?.block).toBeNull();
});

test('legendEntries carries the block a name came from', () => {
  const entries = legendEntries([blockEntry(52, 'Marché Central', 1)]);
  expect(entries.get(52)).toEqual({ n: 52, name: 'Marché Central', grid: '', block: 1 });
});

test('ambiguity stacks with the other reasons rather than replacing them', () => {
  const rows = [
    blockEntry(52, 'Marché Central', 0),
    blockEntry(52, 'Pagode', 1),
    row({ id: 'a', text: '52', run_id: 'r1' }),
    row({ id: 'b', text: '52', run_id: 'r1' }),
  ];
  expect(suspectRefs(rows).get('a')).toEqual(['duplicate', 'ambiguous-entry']);
});
