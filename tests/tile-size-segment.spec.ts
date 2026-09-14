import { expect, test } from '@playwright/test';
import {
  explicitFullSizeToWidthOnly,
  fullMaxToSize,
  fullSizeOf,
  iiifR2Key,
  parseFullSizeDirs,
  splitIiifPath,
  wholeRegionToFull,
  widthOnlySizeToExplicit,
} from '../worker/src/iiifKeys';

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

/**
 * The optional version segment, `/iiif/<mapId>/v<N>/…`.
 *
 * A re-tile cannot reuse a map's keys: every derivative is served
 * `immutable, max-age=31536000`, so new bytes at an old URL reach no existing
 * reader for a year. `/v<N>` is the new URL, and it is additive — 155 maps and
 * ~119,616 objects already sit under `tiles/<mapId>/…` and none of them move.
 *
 * The part that needs pinning is not the key, which the old regex produced by
 * accident anyway. It is that the two rewrites above still fire behind the
 * prefix: both anchor on `^/` plus the region, so an un-peeled `/v2` makes them
 * match nothing — and a rewrite that does not fire is not a 404, it is the
 * proxy, i.e. every tile of a freshly re-tiled map fetched from the library we
 * mirrored it from.
 */

test('an unversioned path lands on exactly the key it always did', () => {
  const p = splitIiifPath('/iiif/0775a31e/0,0,512,512/256,256/0/default.jpg');
  expect(p).toEqual({
    mapId: '0775a31e',
    version: '',
    rest: '/0,0,512,512/256,256/0/default.jpg',
  });
  expect(iiifR2Key(p!.mapId, p!.version, p!.rest)).toBe(
    'tiles/0775a31e/0,0,512,512/256,256/0/default.jpg'
  );

  const info = splitIiifPath('/iiif/0775a31e/info.json');
  expect(iiifR2Key(info!.mapId, info!.version, info!.rest)).toBe('tiles/0775a31e/info.json');
});

test('a version segment becomes a key prefix and leaves the rest alone', () => {
  const p = splitIiifPath('/iiif/0775a31e/v2/0,0,512,512/256,256/0/default.jpg');
  expect(p).toEqual({
    mapId: '0775a31e',
    version: '/v2',
    rest: '/0,0,512,512/256,256/0/default.jpg',
  });
  expect(iiifR2Key(p!.mapId, p!.version, p!.rest)).toBe(
    'tiles/0775a31e/v2/0,0,512,512/256,256/0/default.jpg'
  );

  const info = splitIiifPath('/iiif/0775a31e/v12/info.json');
  expect(info!.version).toBe('/v12');
  expect(iiifR2Key(info!.mapId, info!.version, info!.rest)).toBe('tiles/0775a31e/v12/info.json');
});

test('only /v<digits> is a version', () => {
  // A map whose first path segment merely starts with a v is not versioned.
  expect(splitIiifPath('/iiif/abc/video/256,256/0/default.jpg')!.version).toBe('');
  expect(splitIiifPath('/iiif/abc/v/256,256/0/default.jpg')!.version).toBe('');
  expect(splitIiifPath('/iiif/abc/v2x/info.json')!.version).toBe('');
  // …and a bare /v2 with nothing after it is still a version, not a rest.
  expect(splitIiifPath('/iiif/abc/v2')).toEqual({ mapId: 'abc', version: '/v2', rest: '' });
  // Anything that is not an /iiif path at all.
  expect(splitIiifPath('/basemap/vietnam.pmtiles')).toBeNull();
  expect(splitIiifPath('/iiif/')).toBeNull();
});

test('both rewrites still fire behind a version prefix', () => {
  // This is the whole reason the prefix is peeled rather than left on `rest`.
  const p = splitIiifPath('/iiif/0775a31e/v3/0,0,2652,3753/166,/0/default.jpg')!;
  expect(p.version).toBe('/v3');

  const explicit = widthOnlySizeToExplicit(p.rest);
  expect(explicit).toBe('/0,0,2652,3753/166,235/0/default.jpg');
  expect(iiifR2Key(p.mapId, p.version, explicit as string)).toBe(
    'tiles/0775a31e/v3/0,0,2652,3753/166,235/0/default.jpg'
  );

  const full = wholeRegionToFull(explicit as string, 2652, 3753);
  expect(full).toBe('/full/166,235/0/default.jpg');
  expect(iiifR2Key(p.mapId, p.version, full as string)).toBe(
    'tiles/0775a31e/v3/full/166,235/0/default.jpg'
  );
});

/**
 * `sizes`, and the array that was fiction.
 *
 * It used to be synthesised from `scaleFactors`, and on 0775a31e every entry it
 * produced 404d — `full/2652,3753`, `full/1326,1877`, `full/663,939`,
 * `full/332,470` — while the one `w,h` derivative that does exist,
 * `full/166,235`, went unadvertised. The array is now read out of the bucket.
 */

const PREFIXES = [
  'tiles/0775a31e/full/166,235/',
  'tiles/0775a31e/full/200,/',
  'tiles/0775a31e/full/400,/',
  'tiles/0775a31e/full/800,/',
];

test('the full/ listing is parsed in both spellings, widest last', () => {
  expect(parseFullSizeDirs(PREFIXES)).toEqual([
    { name: '166,235', width: 166, height: 235 },
    { name: '200,', width: 200, height: null },
    { name: '400,', width: 400, height: null },
    { name: '800,', width: 800, height: null },
  ]);
});

test('names that are neither spelling are dropped, not guessed at', () => {
  expect(parseFullSizeDirs(['tiles/x/full/max/', 'tiles/x/full/pct:50/', 'tiles/x/full/'])).toEqual(
    []
  );
  expect(parseFullSizeDirs(['tiles/x/full/0,0/', 'tiles/x/full/256,0/'])).toEqual([]);
});

test('an explicit directory wins over a width-only one of the same width', () => {
  // Its height is read rather than derived, so it is the one to advertise.
  expect(parseFullSizeDirs(['tiles/x/full/200,/', 'tiles/x/full/200,283/'])).toEqual([
    { name: '200,283', width: 200, height: 283 },
  ]);
  expect(parseFullSizeDirs(['tiles/x/full/200,283/', 'tiles/x/full/200,/'])).toEqual([
    { name: '200,283', width: 200, height: 283 },
  ]);
});

test('an explicit size is taken from its name, never recomputed', () => {
  // 3753 / 16 = 234.5625, and the bucket holds 235. Whatever rounding wrote it,
  // the name is the record of it.
  expect(fullSizeOf({ name: '166,235', width: 166, height: 235 }, 2652, 3753)).toEqual({
    width: 166,
    height: 235,
  });
});

test('a width-only size derives the height the bucket really holds', () => {
  // Measured against the live derivatives of 0775a31e (2652 x 3753):
  // full/200, is 200x283, full/400, is 400x566, full/800, is 800x1132.
  expect(fullSizeOf({ name: '200,', width: 200, height: null }, 2652, 3753)).toEqual({
    width: 200,
    height: 283,
  });
  expect(fullSizeOf({ name: '400,', width: 400, height: null }, 2652, 3753)).toEqual({
    width: 400,
    height: 566,
  });
  expect(fullSizeOf({ name: '800,', width: 800, height: null }, 2652, 3753)).toEqual({
    width: 800,
    height: 1132,
  });
  // `ceil` — the rule the region rewrite above uses — is the wrong one here and
  // would advertise 284/567/1133, one pixel taller than every one of those
  // files. dzsave's sizes come from a scale factor; `vips thumbnail` resizes
  // with rint instead, so the two halves of `full/` round differently.
});

test('a width wider than the image is clamped, not promised', () => {
  // `vips thumbnail --size down` leaves a smaller image alone, so `full/800,`
  // on a 600px-wide scan is 600 wide, whatever the directory is called.
  expect(fullSizeOf({ name: '800,', width: 800, height: null }, 600, 400)).toEqual({
    width: 600,
    height: 400,
  });
});

test('a size cannot be derived without the image dimensions', () => {
  expect(fullSizeOf({ name: '800,', width: 800, height: null }, 0, 0)).toBeNull();
  // …but an explicit one needs none.
  expect(fullSizeOf({ name: '166,235', width: 166, height: 235 }, 0, 0)).toEqual({
    width: 166,
    height: 235,
  });
});

/**
 * The two requests `info.json` now invites, and the keys they have to reach.
 */

test('an advertised full/w,h falls back to the width-only directory', () => {
  // `sizes` gives every derivative in the w,h syntax the spec asks for, but
  // three of the four directories are named `w,`. Without this the one thing
  // info.json invites a client to do misses R2 and falls through to the proxy.
  expect(explicitFullSizeToWidthOnly('/full/800,1132/0/default.jpg')).toBe(
    '/full/800,/0/default.jpg'
  );
  expect(explicitFullSizeToWidthOnly('/full/200,283/90/gray.png')).toBe('/full/200,/90/gray.png');
});

test('only full/ is respelled — a region keeps dzsave own w,h', () => {
  // A region's `w,h` IS the stored spelling; rewriting it would manufacture a
  // second miss on the key we just looked up.
  expect(explicitFullSizeToWidthOnly('/0,0,512,512/256,256/0/default.jpg')).toBeNull();
  expect(explicitFullSizeToWidthOnly('/full/800,/0/default.jpg')).toBeNull();
  expect(explicitFullSizeToWidthOnly('/full/max/0/default.jpg')).toBeNull();
  expect(explicitFullSizeToWidthOnly('/info.json')).toBeNull();
});

test('full/max resolves to the widest derivative in the bucket', () => {
  // The one request level0 mandates, and the one nothing ever wrote a key for.
  const dirs = parseFullSizeDirs(PREFIXES);
  const widest = dirs[dirs.length - 1];
  expect(widest.name).toBe('800,');
  expect(fullMaxToSize('/full/max/0/default.jpg', widest.name)).toBe('/full/800,/0/default.jpg');
  // v2 clients ask for native.jpg; the tail is carried through so the worker
  // can try default.jpg behind it.
  expect(fullMaxToSize('/full/max/0/native.jpg', widest.name)).toBe('/full/800,/0/native.jpg');
});

test('nothing but full/max is rewritten to a size', () => {
  expect(fullMaxToSize('/full/800,/0/default.jpg', '800,')).toBeNull();
  expect(fullMaxToSize('/0,0,512,512/max/0/default.jpg', '800,')).toBeNull();
  expect(fullMaxToSize('/info.json', '800,')).toBeNull();
});
