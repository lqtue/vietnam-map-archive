/**
 * The self-hosted vector basemap.
 *
 * One ~348 MB PMTiles archive (Protomaps' daily OpenStreetMap build, bbox
 * 105.5,8.5 → 108.5,21.6, z0–15) living in our own R2 bucket and served by
 * `worker/` at `iiif.maparchive.vn/basemap/`. No API key, no quota, no
 * third-party usage policy — the same independence the map imagery already has.
 *
 * The bbox spans Hanoi to the Mekong because the archive does. Its Saigon-only
 * predecessor (37 MB, 106.3,10.3 → 107.1,11.2) left 21 of 40 georeferenced
 * maps — every Huế and Hanoi sheet, two of them featured — floating on the
 * bare `earth` fill with no roads or water beneath them.
 *
 * Rebuild when OSM has moved on enough to matter:
 *
 *   scripts/pmtiles_extract.sh vietnam 105.5,8.5,108.5,21.6 15 --upload
 *
 * Builds are retained for about a week; the script walks back from today, and
 * names the uploaded key after the build date it found. The date is not
 * decoration: `tiles.maparchive.vn` is an R2 custom domain behind a cache rule
 * with a one-month edge TTL, so a rebuild written over the same key would
 * leave every reader on stale bytes. A new build is a new name and a new value
 * for the constant below. The predecessor served from
 * `iiif.maparchive.vn/basemap/*`, through the worker — one Worker invocation
 * per byte-range read, and PMTiles is nothing but byte-range reads.
 *
 * The styling is deliberately quiet. This is the backdrop a georeferenced
 * historical map is laid over, so it reads as reference, not as content: muted
 * land, restrained water, roads that thin out at low zoom, and labels only where
 * they help you place yourself. Protomaps v4 schema layers are `earth`,
 * `landcover`, `landuse`, `water`, `roads`, `buildings`, `boundaries`, `places`
 * and `pois`; anything not handled below renders nothing on purpose.
 */

import VectorTileLayer from 'ol/layer/VectorTile';
import TileLayer from 'ol/layer/Tile';
import { PMTilesVectorSource, PMTilesRasterSource } from 'ol-pmtiles';
import Style from 'ol/style/Style';
import Fill from 'ol/style/Fill';
import Stroke from 'ol/style/Stroke';
import Text from 'ol/style/Text';
import type { FeatureLike } from 'ol/Feature';
import type { Loader, LoaderOptions } from 'ol/source/DataTile';
import { isDarkTheme } from '$lib/core/utils/theme';

export const BASEMAP_PMTILES_URL = 'https://tiles.maparchive.vn/basemap/vietnam-20260906.pmtiles';

/**
 * The AMS Series L7014 mosaic: 509 GeoPDF sheets from the Perry-Castañeda
 * Library, each clipped to its own printed neatline and warped off the eight
 * control points the sheet carries, tiled into one raster archive by
 * `scripts/l7014_mosaic.py`.
 *
 * Like the basemap above, the key carries its build date because the R2 domain
 * sits behind a long edge TTL — a rebuild written over the same key would
 * strand readers on stale bytes. A new build is a new name and a new constant.
 */
export const L7014_PMTILES_URL = 'https://tiles.maparchive.vn/overlay/l7014-20260912.pmtiles';

/**
 * A tile the archive does not hold, as something drawable.
 *
 * `PMTilesRasterSource` returns an empty `Uint8Array` for a miss, and a sparse
 * archive is nothing but misses — every tile outside a sheet, inside a hole, or
 * past the last zoom level. The canvas renderer throws outright on array data
 * ("Rendering array data is not yet supported"), and the WebGL one paints it
 * black, which is worse: it hides the street basemap underneath instead of
 * letting it through. An untouched canvas is transparent, so a miss simply
 * shows what is below it.
 *
 * It has to match the archive's own tile size. A `DataTileSource` assumes every
 * tile is the size its grid declares, and handing back a 512 px blank where the
 * grid says 256 does not read as "nothing here" — it reads as four tiles' worth
 * of data, and the neighbouring tiles render as black bands.
 */
const blankTiles = new Map<number, HTMLCanvasElement>();
function blank(size: number): HTMLCanvasElement {
  let tile = blankTiles.get(size);
  if (!tile) {
    tile = document.createElement('canvas');
    tile.width = tile.height = size;
    blankTiles.set(size, tile);
  }
  return tile;
}

/**
 * The mosaic's tile source. The loader the parent installs is wrapped rather
 * than replaced — the constructor calls `setLoader` itself once the PMTiles
 * header has arrived, so overriding the method is what gets in front of it.
 */
class SparsePMTilesSource extends PMTilesRasterSource {
  protected override setLoader(loader: Loader): void {
    super.setLoader(async (z: number, x: number, y: number, options: LoaderOptions) => {
      const data = await loader(z, x, y, options);
      if (!(data instanceof Uint8Array)) return data;
      const size = this.getTileGrid()?.getTileSize(z);
      return blank(typeof size === 'number' ? size : (size?.[0] ?? 256));
    });
  }
}

/** The pre-warped raster archives, by the key a `RasterRef` carries. */
const RASTER_ARCHIVES: Record<string, { url: string; attribution: string }> = {
  l7014: {
    url: L7014_PMTILES_URL,
    attribution:
      'U.S. Army Map Service, Series L7014 &mdash; <a href="https://maps.lib.utexas.edu/maps/topo/vietnam/" target="_blank">Perry-Castañeda Library Map Collection</a>, University of Texas at Austin',
  },
};

/**
 * One raster archive as a stackable overlay layer. `LayerRenderer` owns its
 * z-index, opacity and visibility, the same as it does for a warped sheet.
 *
 * It stops at the sheets' own native resolution (~4.2 m/px, so zoom 15); past
 * that the tiles run out and whatever is beneath shows through, which is the
 * reader's basemap rather than a black screen.
 */
export function buildRasterOverlayLayer(key: string): TileLayer {
  const archive = RASTER_ARCHIVES[key];
  if (!archive) throw new Error(`unknown raster archive: ${key}`);
  return new TileLayer({
    source: new SparsePMTilesSource({
      url: archive.url,
      attributions: [archive.attribution],
    }),
    properties: { name: `raster-${key}` },
  });
}

/**
 * Two palettes, because a canvas cannot read a CSS token: OL paints these as
 * draw calls, so `light-dark()` and `var(--color-…)` mean nothing here. Same
 * reason `core/ink.ts` exists for the annotation colours.
 *
 * The dark one is not an inversion of the light one. It is the same quiet
 * hierarchy — earth, then landcover, then water, then roads, with buildings
 * barely there — moved onto a warm near-black so the map sits beside the dark
 * chrome instead of glaring next to it. Historical sheets warped on top keep
 * their own ink either way; they are photographs of paper.
 */
interface Palette {
  earth: string;
  landcover: string;
  park: string;
  water: string;
  waterLine: string;
  building: string;
  boundary: string;
  roadFill: string;
  roadCasing: string;
  highway: string;
  highwayCasing: string;
  label: string;
  labelHalo: string;
  waterLabel: string;
}

const LIGHT: Palette = {
  earth: '#f4f1ea',
  landcover: '#e9eee2',
  park: '#e2ebdd',
  water: '#cddfe8',
  waterLine: '#b9d2df',
  building: '#e6e1d6',
  boundary: '#b8b2a6',
  roadFill: '#ffffff',
  roadCasing: '#e0d9cb',
  highway: '#f6e6c8',
  highwayCasing: '#dcc79b',
  label: '#5b554a',
  labelHalo: '#f8f6f1',
  waterLabel: '#7796a5',
};

const DARK: Palette = {
  earth: '#232019',
  landcover: '#272b22',
  park: '#26302a',
  water: '#1c2c36',
  waterLine: '#27404e',
  building: '#2c2823',
  boundary: '#4e4838',
  roadFill: '#3b362c',
  roadCasing: '#211e19',
  highway: '#4d4430',
  highwayCasing: '#2a2419',
  label: '#a8a091',
  labelHalo: '#17150f',
  waterLabel: '#6d8f9f',
};

/** The palette in force. `styleFor` reads it fresh on every call. */
let C: Palette = LIGHT;

/** Cheap singletons — a style function runs per feature per frame. */
function singletons(c: Palette) {
  return {
    earth: new Style({ fill: new Fill({ color: c.earth }) }),
    landcover: new Style({ fill: new Fill({ color: c.landcover }) }),
    park: new Style({ fill: new Fill({ color: c.park }) }),
    water: new Style({ fill: new Fill({ color: c.water }) }),
    building: new Style({ fill: new Fill({ color: c.building }) }),
    boundary: new Style({
      stroke: new Stroke({ color: c.boundary, width: 1, lineDash: [4, 3] }),
    }),
  };
}

let S = singletons(C);

/**
 * Layers built so far, so a theme change can ask them to redraw. Entries that
 * are no longer on a map are dropped on the way past — a navigation away from
 * /explore leaves its layer behind, and nothing else would let it go.
 */
const built = new Set<VectorTileLayer>();

function applyBasemapTheme(dark: boolean): void {
  const next = dark ? DARK : LIGHT;
  if (next === C) return;
  C = next;
  S = singletons(C);
  for (const layer of built) {
    if (layer.getMapInternal()) layer.changed();
    else built.delete(layer);
  }
}

if (typeof window !== 'undefined') {
  isDarkTheme.subscribe(applyBasemapTheme);
}

const PARK_KINDS = new Set(['park', 'garden', 'forest', 'nature_reserve', 'recreation_ground']);

/** Road casing + fill widths, in screen px, by road class and zoom. */
function roadWidth(kind: string, zoom: number): number {
  if (kind === 'highway') return zoom < 9 ? 0.8 : zoom < 12 ? 1.6 : zoom < 14 ? 3 : 5;
  if (kind === 'major_road') return zoom < 10 ? 0 : zoom < 12 ? 1 : zoom < 14 ? 2.2 : 4;
  if (kind === 'medium_road') return zoom < 12 ? 0 : zoom < 14 ? 1.2 : 2.6;
  if (kind === 'minor_road') return zoom < 14 ? 0 : 1.4;
  return 0;
}

function waterLineWidth(zoom: number): number {
  return zoom < 9 ? 0.5 : zoom < 12 ? 1 : zoom < 14 ? 1.8 : 3;
}

/**
 * Vietnamese administrative sub-units — `Khu phố 13`, `Ấp 4`, `Tổ 7` — are
 * numbered blocks, not places anyone navigates by. OSM has one per few streets,
 * so rendering them buries Saigon under a grid of numerals. Named
 * neighbourhoods (Tân Định, Đa Kao, Ba Son) are exactly what you *do* want.
 */
// Matches the prefix *and* its number, so a real name like "Ấp Bắc" survives.
// No `\b` here: JavaScript word boundaries are ASCII-only, and "khu phố" ends
// in `ố`, so `\b` never matches after it.
const ADMIN_BLOCK = /^(khu phố|khu vực|ấp|tổ|thôn|xóm)\s+\d/iu;

/** Place labels appear as you zoom in, biggest settlements first. */
function placeLabel(
  kind: string,
  zoom: number,
  name: string
): { size: number; weight: number } | null {
  if (kind === 'locality' || kind === 'city') {
    if (zoom < 6) return null;
    return { size: zoom < 10 ? 12 : 14, weight: 600 };
  }
  if (kind === 'town') return zoom < 10 ? null : { size: 12, weight: 500 };
  if (kind === 'village') return zoom < 12 ? null : { size: 11, weight: 500 };
  if (kind === 'neighbourhood' || kind === 'suburb') {
    if (zoom < 14 || ADMIN_BLOCK.test(name)) return null;
    return { size: 11, weight: 400 };
  }
  return null;
}

function label(text: string, size: number, weight: number, color: string, italic = false): Style {
  return new Style({
    text: new Text({
      text,
      font: `${italic ? 'italic ' : ''}${weight} ${size}px "Inter", system-ui, sans-serif`,
      fill: new Fill({ color }),
      stroke: new Stroke({ color: C.labelHalo, width: 3 }),
      overflow: false,
    }),
  });
}

/**
 * Name in the local script, falling back to the romanised name. Vietnamese IS
 * the local script here, so `name` is already what we want; `name:en` only wins
 * when a feature has no local name at all.
 */
function nameOf(f: FeatureLike): string | null {
  return (f.get('name') as string) || (f.get('name:en') as string) || null;
}

function styleFor(feature: FeatureLike, resolution: number): Style | Style[] | undefined {
  // OL gives resolution, the schema thinks in zoom. 156543 m/px is z0 at the equator.
  const zoom = Math.log2(156543.03392 / resolution);
  const layer = feature.get('layer') as string;
  const kind = (feature.get('kind') as string) ?? '';

  switch (layer) {
    case 'earth':
      return S.earth;

    case 'landcover':
      return zoom < 8 ? undefined : S.landcover;

    case 'landuse':
      return PARK_KINDS.has(kind) ? S.park : undefined;

    case 'water': {
      if (feature.getGeometry()?.getType() === 'LineString') {
        const w = waterLineWidth(zoom);
        return new Style({ stroke: new Stroke({ color: C.waterLine, width: w }) });
      }
      if (zoom >= 12) {
        const name = nameOf(feature);
        if (name && (kind === 'river' || kind === 'lake' || kind === 'canal')) {
          return [S.water, label(name, 11, 400, C.waterLabel, true)];
        }
      }
      return S.water;
    }

    case 'buildings':
      return zoom < 15 ? undefined : S.building;

    case 'boundaries':
      // Only the national line; admin subdivisions add noise at this scale.
      return kind === 'country' ? S.boundary : undefined;

    case 'roads': {
      const w = roadWidth(kind, zoom);
      if (w === 0) return undefined;
      const isHighway = kind === 'highway';
      return [
        new Style({
          stroke: new Stroke({
            color: isHighway ? C.highwayCasing : C.roadCasing,
            width: w + 1.4,
          }),
        }),
        new Style({
          stroke: new Stroke({ color: isHighway ? C.highway : C.roadFill, width: w }),
        }),
      ];
    }

    case 'places': {
      const name = nameOf(feature);
      if (!name) return undefined;
      const spec = placeLabel(kind, zoom, name);
      return spec ? label(name, spec.size, spec.weight, C.label) : undefined;
    }

    default:
      return undefined;
  }
}

/** The basemap layer. `visible` is owned by the caller, as with every base layer. */
export function buildPmtilesBasemapLayer(visible: boolean): VectorTileLayer {
  const layer = new VectorTileLayer({
    // Labels must not collide; polygons and lines are drawn in schema order.
    declutter: true,
    source: new PMTilesVectorSource({
      url: BASEMAP_PMTILES_URL,
      attributions: [
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
        '<a href="https://protomaps.com" target="_blank">Protomaps</a>',
      ],
    }),
    style: styleFor,
    visible,
    zIndex: 0,
  });
  built.add(layer);
  return layer;
}
