// Guess pixel locations for the 15 saigon6 landmarks on the two NEW, ungeoreferenced
// BnF originals (Plan de Saïgon GE C-17229 / Plan de Cholon GE C-17230) that are
// replacing the stitched 1942 composite (eca788e5-...) -- see georef-tooling-district4
// memory, 2026-09-23, and add_1942_saigon_scout.mjs.
//
// Same trick as gcp_inverse_lookup.mjs (inverse-transform known ground points through
// a sheet's own annotation to get an approximate pixel), composed with two more steps
// specific to this split:
//
//   1. Inverse-transform each landmark's consensus lon/lat (median across the OTHER
//      five D4-series sheets, i.e. NOT 1942 -- that's the sheet being replaced) through
//      the composite's OWN transform to get an approximate pixel on the 14915x12602
//      composite. NOTE: must read maps.annotation_url (the production mirror, 8 pts,
//      15.9m RMSE), NOT allmaps_id -- 1942's live Allmaps-hosted copy is the known-bad
//      9-point/117m-RMSE landmine (see memory), and gcp_inverse_lookup.mjs's normal
//      "live first" preference would silently pull it here.
//   2. Composite pixel -> panel-local pixel, using the panel boxes
//      work/analysis/district4/sheet_panels.py already fit to the neat-line.
//   3. Panel-local pixel -> new-scan pixel, by the ratio between that panel's box size
//      (on the composite) and the new Gallica scan's own canvas size. This assumes the
//      composite's embedded panel and the fresh Gallica scan differ only by a uniform
//      crop/scale, not a rotation or flip -- true to within the 0.02-0.05deg
//      panel-to-panel rotation sheet_panels.py measured, which is negligible at
//      "zoom here and confirm by eye" tolerance.
//
// This is a GUESS to save you scanning an 8000-14000px image by hand, not a fit --
// confirm the feature by eye before placing the real GCP, same as every other use of
// this technique in this repo.
//
//   node --env-file=.env scripts/oneoff/guess_1942_split_xy.mjs
//   node --env-file=.env scripts/oneoff/guess_1942_split_xy.mjs --json

import { createClient } from '@supabase/supabase-js';
import { GcpTransformer } from '@allmaps/transform';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const MAP_1942 = 'eca788e5-6780-4dca-bf23-7651a1c48aba';

// sheet_panels.py PANELS["1942"], rescan (14915x12602) coordinates.
const PANEL_BOX = {
  Cholon: { x0: 253, x1: 7427, y0: 2297, y1: 12233 },
  Saigon: { x0: 7363, x1: 14540, y0: 327, y1: 10253 },
};

// New Gallica scans' own canvas size (from their IIIF manifests).
const NEW_SCAN = {
  Saigon: { width: 8172, height: 10860, ark: 'btv1b53197000p' },
  Cholon: { width: 7840, height: 10846, ark: 'btv1b53189369q' },
};

// Landmark -> consensus ground truth, median lon/lat across 1882/1898/1923/1959/1968
// (1942 excluded -- it's the sheet being replaced). From work/analysis/saigon6/points.json
// via sheet_align.mjs --json, computed 2026-09-23.
const LANDMARKS = [
  ['Entrance of Jardin Botanique', 106.70685, 10.78544],
  ['Thi Nghe Bridge', 106.706193, 10.791626],
  ['Rond Point', 106.706352, 10.775297],
  ['Mat de Signaux', 106.70629, 10.769774],
  ['Norodom', 106.695943, 10.777655],
  ["Chateau D'eau", 106.69591, 10.782604],
  ['Citadel Edge', 106.69757, 10.78649],
  ['Marche Cau Ong Lanh', 106.698788, 10.764724],
  ['Edge of town', 106.689433, 10.773653],
  ['D4', 106.708152, 10.762419],
  ['End D4', 106.72067, 10.757752],
  ['Cholon Canal', 106.659137, 10.750558],
  ['Station radioelectrique', 106.656061, 10.7781],
  ['Out of town top', 106.653374, 10.792995],
  ['Double canal', 106.634081, 10.723269],
];

const { data: row, error } = await db
  .from('maps')
  .select('id,annotation_url,allmaps_id')
  .eq('id', MAP_1942)
  .single();
if (error) throw error;

// Deliberately annotation_url (production mirror), not allmaps_id -- see header.
const res = await fetch(row.annotation_url);
if (!res.ok) throw new Error(`mirror fetch failed: ${res.status}`);
const annotation = await res.json();
const item = annotation.items?.[0] ?? annotation;
const body = item.body ?? item;
if (body.features.length !== 8) {
  console.warn(`WARNING: expected 8-point corrected mirror, got ${body.features.length}`);
}

const gcps = body.features.map((f) => ({
  resource: f.properties.resourceCoords,
  geo: f.geometry.coordinates,
}));
const transformer = new GcpTransformer(gcps, body.transformation?.type ?? 'polynomial');

function panelFor(px, py) {
  for (const [name, box] of Object.entries(PANEL_BOX)) {
    if (px >= box.x0 && px <= box.x1 && py >= box.y0 && py <= box.y1) return name;
  }
  // fall back to nearer box by x, for points guessed just outside a panel's box
  const dCholon = Math.abs(px - (PANEL_BOX.Cholon.x0 + PANEL_BOX.Cholon.x1) / 2);
  const dSaigon = Math.abs(px - (PANEL_BOX.Saigon.x0 + PANEL_BOX.Saigon.x1) / 2);
  return dCholon < dSaigon ? 'Cholon' : 'Saigon';
}

const results = LANDMARKS.map(([name, lon, lat]) => {
  const [cx, cy] = transformer.transformToResource([lon, lat]);
  const panel = panelFor(cx, cy);
  const box = PANEL_BOX[panel];
  const scan = NEW_SCAN[panel];
  const localX = cx - box.x0;
  const localY = cy - box.y0;
  const sx = scan.width / (box.x1 - box.x0);
  const sy = scan.height / (box.y1 - box.y0);
  const guessX = Math.round(localX * sx);
  const guessY = Math.round(localY * sy);
  const outOfBounds = guessX < 0 || guessY < 0 || guessX > scan.width || guessY > scan.height;
  const editorUrl =
    `https://editor.allmaps.org/#/collection?url=` +
    encodeURIComponent(`https://gallica.bnf.fr/iiif/ark:/12148/${scan.ark}/f1/info.json`);
  return {
    name,
    panel,
    lon,
    lat,
    guessX,
    guessY,
    outOfBounds,
    editorUrl,
    compositePx: [Math.round(cx), Math.round(cy)],
  };
});

if (process.argv.includes('--json')) {
  console.log(JSON.stringify(results, null, 2));
} else {
  for (const panel of ['Saigon', 'Cholon']) {
    console.log(`\n## ${panel} (${NEW_SCAN[panel].width}x${NEW_SCAN[panel].height})`);
    for (const r of results.filter((r) => r.panel === panel)) {
      const flag = r.outOfBounds ? '  [OUT OF BOUNDS -- guess unreliable]' : '';
      console.log(`${r.name}`);
      console.log(`  ${r.guessX} ${r.guessY} ${r.lon} ${r.lat}${flag}`);
      console.log(`  ${r.editorUrl}`);
    }
  }
}
