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

test('an edge tile rounds the way dzsave rounded', () => {
  // Real key: 3758 * 256 / 4096 = 234.875, and the bucket holds `256,235`.
  // Math.floor would ask for 234 and miss.
  expect(widthOnlySizeToExplicit('/0,0,4096,3758/256,/0/default.jpg')).toBe(
    '/0,0,4096,3758/256,235/0/default.jpg'
  );
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

test('non-region paths are left alone', () => {
  expect(wholeRegionToFull('/full/157,118/0/default.jpg', 5001, 3771)).toBeNull();
  expect(wholeRegionToFull('/info.json', 5001, 3771)).toBeNull();
});
