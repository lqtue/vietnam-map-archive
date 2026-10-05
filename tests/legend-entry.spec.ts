/**
 * A staff-placed legend position is stored in image pixels (`px=x,y`), not on
 * the ground: a lng/lat frozen at save time stops matching the scan when the map
 * is re-georeferenced. `point=lng,lat` is the legacy form, still read.
 */
import { test, expect } from '@playwright/test';
import { editLegendNotes, manualLegendPoint } from '../src/lib/server/legendEntry';

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
