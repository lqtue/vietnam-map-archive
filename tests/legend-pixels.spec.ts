/**
 * The pixel side of the legend tool: which body numerals can name an entry,
 * whether one agrees with the index cell, which entry is next and which numeral
 * Enter takes. The public ground-space GET and the staff pixel GET share the
 * first two, so one reading cannot drift from the other.
 */
import { test, expect } from '@playwright/test';
import { numeralCandidate } from '../src/lib/server/legendEntry';
import { cellAgreement } from '../src/lib/core/geo/mapGrid';
import {
  bestCandidate,
  mapStatus,
  nextUnplaced,
  filterRows,
  type LegendRow,
} from '../src/lib/features/contribute/legend/legendStage';
import {
  NO_WORK,
  legendReadiness,
  readSummary,
  sheetTracks,
  matchesWork,
  overallState,
  type WorkFacts,
} from '../src/lib/core/sheetWork';

const box = (text: string, x: number, y: number) => ({
  text,
  text_corrected: null,
  global_x: x,
  global_y: y,
  global_w: 10,
  global_h: 10,
});
const legendBox = [{ x: 0, y: 0, w: 100, h: 100 }];

test('a numeral is a bare number up to the legend size, outside the legend box', () => {
  expect(numeralCandidate(box('7', 500, 500), 20, legendBox)).toEqual({ n: 7, x: 505, y: 505 });
  expect(numeralCandidate(box('21', 500, 500), 20, legendBox)).toBeNull();
  expect(numeralCandidate(box('0', 500, 500), 20, legendBox)).toBeNull();
  expect(numeralCandidate(box('7a', 500, 500), 20, legendBox)).toBeNull();
  expect(numeralCandidate(box('7', 20, 20), 20, legendBox)).toBeNull();
  expect(numeralCandidate({ ...box('7', 500, 500), global_x: null }, 20, legendBox)).toBeNull();
});

test('a numeral agrees with its index cell within one cell, and says nothing without a grid', () => {
  const grid = {
    bbox: [0, 0, 400, 400] as [number, number, number, number],
    columns: ['1', '2', '3', '4'],
    rows: ['A', 'B', 'C', 'D'],
  };
  // "B 2" is the box x 100..200, y 100..200, with one cell of slack each side.
  expect(cellAgreement(grid, 'B 2', 150, 150)).toBe(true);
  expect(cellAgreement(grid, 'B 2', 290, 150)).toBe(true);
  expect(cellAgreement(grid, 'B 2', 350, 150)).toBe(false);
  expect(cellAgreement(null, 'B 2', 150, 150)).toBeNull();
  expect(cellAgreement(grid, null, 150, 150)).toBeNull();
  expect(cellAgreement(grid, 'Z 9', 150, 150)).toBeNull();
});

const row = (n: number, x: number | null): LegendRow => ({
  id: `id${n}`,
  n,
  name: `Name ${n}`,
  vn: null,
  grid: null,
  x,
  y: x,
  more: [],
  validated: false,
});

test('n walks to the next unplaced entry, wrapping; Enter never takes a disagreeing numeral', () => {
  const rows = [row(1, 5), row(2, null), row(3, 5), row(4, null)];
  expect(nextUnplaced(rows, null)?.n).toBe(2);
  expect(nextUnplaced(rows, 'id2')?.n).toBe(4);
  expect(nextUnplaced(rows, 'id4')?.n).toBe(2);
  expect(nextUnplaced([row(1, 5)], 'id1')).toBeNull();

  const c = (inCell: boolean | null, labelId: string) => ({ n: 2, x: 1, y: 1, inCell, labelId });
  expect(bestCandidate([c(null, 'a'), c(true, 'b')], 2)?.labelId).toBe('b');
  expect(bestCandidate([c(null, 'a')], 2)?.labelId).toBe('a');
  expect(bestCandidate([c(false, 'a')], 2)).toBeNull();
  expect(bestCandidate([c(true, 'a')], 3)).toBeNull();
});

test('a map is todo, doing, done or has no legend', () => {
  expect(mapStatus(undefined)).toBe('none');
  expect(mapStatus({ total: 0, placed: 0 })).toBe('none');
  expect(mapStatus({ total: 40, placed: 0 })).toBe('todo');
  expect(mapStatus({ total: 40, placed: 12 })).toBe('doing');
  expect(mapStatus({ total: 40, placed: 40 })).toBe('done');
});

test('a sheet is read, ready to read (region found), or unlocated', () => {
  const st = (found: Partial<WorkFacts['found']>, read: Partial<WorkFacts['read']>): WorkFacts => ({
    ...NO_WORK,
    found: { ...NO_WORK.found, ...found },
    read: { ...NO_WORK.read, ...read },
  });
  expect(legendReadiness(undefined)).toBe('unlocated');
  expect(legendReadiness(st({ title: true }, {}))).toBe('unlocated');
  expect(legendReadiness(st({ legend: true }, {}))).toBe('ready');
  expect(legendReadiness(st({ legend: true }, { legend: true }))).toBe('read');
  expect(readSummary(undefined)).toBeUndefined();
  expect(readSummary(st({ legend: true }, { title: true }))).toBe('legend found · title read');
});

test('a sheet has independent work tracks: done, in between, or not yet', () => {
  const states = (f?: WorkFacts) => Object.fromEntries(sheetTracks(f).map((x) => [x.key, x.state]));
  expect(states(undefined)).toEqual({
    triage: 'todo',
    title: 'todo',
    legend: 'todo',
    body: 'todo',
    text: 'todo',
    shapes: 'todo',
  });
  // Legend read on a sheet whose body never was: the case one linear stage cannot say.
  const legendOnly: WorkFacts = {
    ...NO_WORK,
    triage: 'proposed',
    found: { ...NO_WORK.found, legend: true },
    read: { ...NO_WORK.read, legend: true },
  };
  expect(states(legendOnly)).toMatchObject({
    triage: 'doing',
    legend: 'done',
    body: 'todo',
  });
  const reviewed: WorkFacts = {
    ...NO_WORK,
    triage: 'ready',
    ocrRan: true,
    textReviewed: true,
    segRan: true,
  };
  expect(states(reviewed)).toMatchObject({
    triage: 'done',
    body: 'done',
    text: 'done',
    shapes: 'doing',
  });
  // A region the model guessed is not a fact: the track stays grey until a person confirms it.
  expect(states({ ...NO_WORK, found: { ...NO_WORK.found, legend: false } }).legend).toBe('todo');
});

test('"no legend on this sheet" closes the legend track; entries outrank it', () => {
  const none: WorkFacts = { ...NO_WORK, noLegend: true };
  const legend = (f: WorkFacts) => sheetTracks(f).find((x) => x.key === 'legend')!;
  expect(legend(none)).toMatchObject({ state: 'done', hint: 'No legend printed' });
  expect(legendReadiness(none)).toBe('none');
  expect(readSummary(none)).toBe('no legend printed');
  // Even with a person's legend region on file, the sheet needs no legend work.
  const found: WorkFacts = { ...none, found: { ...none.found, legend: true } };
  expect(legendReadiness(found)).toBe('none');
  expect(matchesWork('legend', found)).toBe(false);
  expect(matchesWork('legend', { ...NO_WORK, found: { ...NO_WORK.found, legend: true } })).toBe(
    true
  );
  // Entries win: read, with the ordinary hint, and no conflict shown.
  const both: WorkFacts = { ...none, read: { ...none.read, legend: true } };
  expect(legendReadiness(both)).toBe('read');
  expect(legend(both)).toMatchObject({ state: 'done' });
  expect(legend(both).hint).not.toBe('No legend printed');
  // The track no longer blocks "All done".
  const rest: WorkFacts = {
    ...none,
    triage: 'ready',
    found: { ...none.found, title: true },
    read: { ...none.read, title: true, body: true },
    textReviewed: true,
    shapesReviewed: true,
  };
  expect(overallState(rest)).toBe('done');
  expect(matchesWork('done', rest)).toBe(true);
  expect(matchesWork('done', { ...rest, noLegend: false })).toBe(false);
});

test('the legend list filters, searches without accents, and keeps the open row', () => {
  const row = (n: number, name: string, grid: string | null, x: number | null): LegendRow => ({
    id: `r${n}`,
    n,
    name,
    vn: null,
    grid,
    x,
    y: x,
    more: [],
    validated: false,
  });
  const rows = [
    row(1, 'Théâtre', 'B2', 5),
    row(2, 'Casino', null, null),
    row(3, 'Hôtel', 'A10', null),
  ];
  const base = {
    filter: 'all',
    query: '',
    staged: new Set<string>(),
    suggested: new Set<number>(),
    keepId: null,
  } as const;
  const ns = (o: object) => filterRows(rows, { ...base, ...o }).map((r) => r.n);
  expect(ns({})).toEqual([1, 2, 3]);
  expect(ns({ filter: 'unplaced' })).toEqual([2, 3]);
  expect(ns({ filter: 'placed' })).toEqual([1]);
  expect(ns({ filter: 'edited', staged: new Set(['r3']) })).toEqual([3]);
  expect(ns({ filter: 'suggested', suggested: new Set([3]) })).toEqual([3]);
  expect(ns({ query: 'theatre' })).toEqual([1]);
  expect(ns({ query: 'hotel' })).toEqual([3]);
  expect(ns({ filter: 'placed', keepId: 'r2' })).toEqual([1, 2]);
});
