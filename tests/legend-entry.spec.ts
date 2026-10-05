/**
 * A staff-placed legend position is stored in image pixels (`px=x,y`), not on
 * the ground: a lng/lat frozen at save time stops matching the scan when the map
 * is re-georeferenced. `point=lng,lat` is the legacy form, still read.
 */
import { test, expect } from '@playwright/test';
import {
  editLegendNotes,
  extraLegendPoints,
  manualLegendPoint,
} from '../src/lib/server/legendEntry';

test('a save writes pixels and drops the legacy ground point', () => {
  const notes = editLegendNotes('n=4; point=106.7,10.77; src=ocr', {
    vn: null,
    grid: 'J 6',
    px: [1203.6, 88.2],
  });
  expect(notes).toBe('n=4; src=ocr; grid=J 6; px=1204,88');
  expect(manualLegendPoint(notes)).toEqual({ px: [1204, 88] });
});

test('pixels win; a legacy ground point is still read; junk is nothing', () => {
  expect(manualLegendPoint('px=5,6; point=106.7,10.77')).toEqual({ px: [5, 6] });
  expect(manualLegendPoint('point=106.7,10.77')).toEqual({ lngLat: [106.7, 10.77] });
  expect(manualLegendPoint('px=-1,6')).toBeNull();
  expect(manualLegendPoint('point=200,10')).toBeNull();
  expect(manualLegendPoint(null)).toBeNull();
});

test('a number printed on several plots keeps its extra points beside the first', () => {
  const notes = editLegendNotes('n=21; more=1,1', {
    vn: null,
    grid: null,
    px: [100.4, 200.6],
    more: [
      [300.2, 400.8],
      [5, 6],
    ],
  });
  expect(notes).toBe('n=21; px=100,201; more=300,401|5,6');
  expect(extraLegendPoints(notes)).toEqual([
    [300, 401],
    [5, 6],
  ]);
  // The first point is what `manualLegendPoint` still reads.
  expect(manualLegendPoint(notes)).toEqual({ px: [100, 201] });
});

test('extra points never outlive the first one, and junk in them is skipped', () => {
  expect(
    editLegendNotes('n=21; more=1,1', { vn: null, grid: null, px: null, more: [[2, 2]] })
  ).toBe('n=21');
  expect(extraLegendPoints('more=1,2|x|-3,4|5,6')).toEqual([
    [1, 2],
    [5, 6],
  ]);
  expect(extraLegendPoints(null)).toEqual([]);
});
