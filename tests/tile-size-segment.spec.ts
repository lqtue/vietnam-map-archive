import { expect, test } from '@playwright/test';
import { widthOnlySizeToExplicit, wholeRegionToFull } from '../worker/src/iiifKeys';

/**
 * The IIIF size segment, and the 404 that hid behind it.
 *
 * `vips dzsave --layout iiif3` writes every derivative with an explicit `w,h`
 * size. IIIF's canonical "this width, proportional height" is width-only, and
 * that is what @allmaps/render and OpenLayers ask for — so a width-only request
 * missed R2 for *every* map in the bucket. Maps with a `sources/` entry hid it
 * by proxying each tile to their origin; maps without one (every self-hosted
 * scan) answered `{"error":"Source not found"}` and drew nothing.
 *
 * The cases below are real keys read out of the bucket. The rounding is the
 * part worth pinning: get it wrong and nothing throws, the tile simply is not
 * found again.
 */

test('a square tile keeps its size', () => {
  expect(widthOnlySizeToExplicit('/0,0,512,512/256,/0/default.jpg')).toBe(
    '/0,0,512,512/256,256/0/default.jpg'
  );
  expect(widthOnlySizeToExplicit('/0,0,256,256/256,/0/default.jpg')).toBe(
    '/0,0,256,256/256,256/0/default.jpg'
  );
});

test('an edge tile rounds the way dzsave rounded — up, not to nearest', () => {
  // Real key: 3758 * 256 / 4096 = 234.875, and the bucket holds `256,235`.
  // Math.floor would ask for 234 and miss.
  expect(widthOnlySizeToExplicit('/0,0,4096,3758/256,/0/default.jpg')).toBe(
    '/0,0,4096,3758/256,235/0/default.jpg'
  );

  // …but .875 rounds up under *every* rule, so the case above cannot tell
  // `ceil` from `round`, and for a year it did not: the bottom row of the
  // Indochine sheets lands below .5, where round becomes floor. Real key from
  // 0775a31e (2652 x 3753) at factor 8: 1705 / 8 = 213.125, bucket holds
  // `256,214`. Math.round asks 213 and misses.
  expect(widthOnlySizeToExplicit('/0,2048,2048,1705/256,/0/default.jpg')).toBe(
    '/0,2048,2048,1705/256,214/0/default.jpg'
  );
  // Same sheet, factor 16, whole image: 3753 / 16 = 234.5625.
  expect(widthOnlySizeToExplicit('/0,0,2652,3753/166,/0/default.jpg')).toBe(
    '/0,0,2652,3753/166,235/0/default.jpg'
  );
});

test('a corner tile takes its height from the factor, not the rounded width', () => {
  // Both axes inexact. The width is already rounded up (604 / 8 = 75.5 -> 76),
  // so the ratio it carries is not the scale factor: 1705 * 76 / 604 = 214.56
  // overshoots, and ceil and round alike ask for 215. The bucket holds
  // `76,214` — only recovering the factor gets there.
  expect(widthOnlySizeToExplicit('/2048,2048,604,1705/76,/0/default.jpg')).toBe(
    '/2048,2048,604,1705/76,214/0/default.jpg'
  );
  // Real key from 013daa15 (4998 x 3780), factor 16: 902 / 16 = 56.375 -> 57,
  // and 3780 / 16 = 236.25 -> 237.
  expect(widthOnlySizeToExplicit('/4096,0,902,3780/57,/0/default.jpg')).toBe(
    '/4096,0,902,3780/57,237/0/default.jpg'
  );
});

test('a width no power of two produces is left to the proxy', () => {
  // Nothing in the pyramid answers to it, so inventing a height would only
  // manufacture a second miss.
  expect(widthOnlySizeToExplicit('/0,0,2048,2048/200,/0/default.jpg')).toBeNull();
  expect(widthOnlySizeToExplicit('/0,0,2048,2048/999,/0/default.jpg')).toBeNull();
});

test('the offset is carried through untouched', () => {
  expect(widthOnlySizeToExplicit('/0,1536,512,512/256,/0/default.jpg')).toBe(
    '/0,1536,512,512/256,256/0/default.jpg'
  );
  expect(widthOnlySizeToExplicit('/1024,2048,1024,1024/256,/0/default.jpg')).toBe(
    '/1024,2048,1024,1024/256,256/0/default.jpg'
  );
});

test('a request that already names both dimensions is left alone', () => {
  // Already the stored spelling — rewriting it would be a second lookup for
  // the key we just missed.
  expect(widthOnlySizeToExplicit('/0,0,512,512/256,256/0/default.jpg')).toBeNull();
});

test('regions dzsave does not tile fall through to the proxy', () => {
  // `full`, `square` and `pct:` have no region size to compute a height from.
  expect(widthOnlySizeToExplicit('/full/400,/0/default.jpg')).toBeNull();
  expect(widthOnlySizeToExplicit('/full/max/0/default.jpg')).toBeNull();
  expect(widthOnlySizeToExplicit('/square/256,/0/default.jpg')).toBeNull();
  expect(widthOnlySizeToExplicit('/pct:10,10,50,50/256,/0/default.jpg')).toBeNull();
});

test('info.json and nonsense are not tiles', () => {
  expect(widthOnlySizeToExplicit('/info.json')).toBeNull();
  expect(widthOnlySizeToExplicit('')).toBeNull();
  expect(widthOnlySizeToExplicit('/0,0,0,0/256,/0/default.jpg')).toBeNull();
  expect(widthOnlySizeToExplicit('/0,0,512,512/0,/0/default.jpg')).toBeNull();
});

test('the quality and format tail is preserved, whatever it is', () => {
  // IIIF v2 origins answer native.jpg; the worker already handles that swap
  // downstream, so this must not eat it.
  expect(widthOnlySizeToExplicit('/0,0,512,512/256,/0/native.jpg')).toBe(
    '/0,0,512,512/256,256/0/native.jpg'
  );
  expect(widthOnlySizeToExplicit('/0,0,512,512/256,/90/gray.png')).toBe(
    '/0,0,512,512/256,256/90/gray.png'
  );
});

/**
 * The whole-image overview. @allmaps/render asks for it as a region covering
 * everything; dzsave files it under `full/`. It is the first thing the renderer
 * fetches and a precondition for drawing anything, so a map with an otherwise
 * complete pyramid still comes up blank without this.
 */

test('a region covering the whole image is the same as full', () => {
  // Real request and real key, from the Phat Diem sheet (5001 x 3771).
  expect(wholeRegionToFull('/0,0,5001,3771/157,118/0/default.jpg', 5001, 3771)).toBe(
    '/full/157,118/0/default.jpg'
  );
  expect(wholeRegionToFull('/0,0,5160,3695/162,116/0/default.jpg', 5160, 3695)).toBe(
    '/full/162,116/0/default.jpg'
  );
});

test('a region that is not the whole image is never full', () => {
  // The trap an aspect-ratio test would fall into: this is one corner tile, and
  // answering it with `full` serves the entire map in place of that tile.
  expect(wholeRegionToFull('/0,0,1024,1024/256,256/0/default.jpg', 5001, 3771)).toBeNull();
  expect(wholeRegionToFull('/0,0,5001,3770/157,118/0/default.jpg', 5001, 3771)).toBeNull();
  expect(wholeRegionToFull('/0,0,5000,3771/157,118/0/default.jpg', 5001, 3771)).toBeNull();
});

test('a region with an offset is not the whole image', () => {
  expect(wholeRegionToFull('/512,0,5001,3771/157,118/0/default.jpg', 5001, 3771)).toBeNull();
});

test('the width-only overview composes both rewrites', () => {
  // The renderer asks for the whole image width-only, and `full/` keys carry an
  // explicit `w,h` like every other derivative — so the two rewrites have to
  // run in series. `/full/166,` is not a key; `/full/166,235` is.
  const explicit = widthOnlySizeToExplicit('/0,0,2652,3753/166,/0/default.jpg');
  expect(explicit).toBe('/0,0,2652,3753/166,235/0/default.jpg');
  expect(wholeRegionToFull(explicit as string, 2652, 3753)).toBe('/full/166,235/0/default.jpg');
});

test('non-region paths are left alone', () => {
  expect(wholeRegionToFull('/full/157,118/0/default.jpg', 5001, 3771)).toBeNull();
  expect(wholeRegionToFull('/info.json', 5001, 3771)).toBeNull();
});
