// Copy the two printed legend panels from the 1942 composite OCR map onto its
// separately georeferenced Saigon and Cholon sheets. Pixel positions are
// transformed from the composite panels into each sheet's own scan.
//
// Dry run by default; pass --apply to write. The composite is left untouched.
import { randomUUID } from 'node:crypto';
import { createClient } from '@supabase/supabase-js';
import { parseAnnotation } from '@allmaps/annotation';
import { GcpTransformer } from '@allmaps/transform';
import { gcpRmseMetres, gcpSrcHash } from '../../src/lib/core/georef/version.ts';

const SOURCE_ID = 'eca788e5-6780-4dca-bf23-7651a1c48aba';
const PANELS = {
  Cholon: {
    mapId: '8c605819-a8c3-4b2f-aa4a-6fad12893eab',
    box: { x0: 253, x1: 7427, y0: 2297, y1: 12233 },
    width: 7840,
    height: 10846,
  },
  Saigon: {
    mapId: '6989a04e-0f51-439e-9390-a6678aff374c',
    box: { x0: 7363, x1: 14540, y0: 327, y1: 10253 },
    width: 8172,
    height: 10860,
  },
};
const PAGE = 500;
const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

function entryNumber(row) {
  const fromNotes = /(?:^|;)\s*n=(\d+)/.exec(row.notes ?? '')?.[1];
  const fromText = /^\s*\(?\s*(\d+)/.exec(row.text_corrected ?? row.text ?? '')?.[1];
  const n = Number(fromNotes ?? fromText);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}

function referenceNumber(row) {
  const match = /^\s*\(?\s*(\d{1,3})\s*\)?\s*$/.exec(row.text_corrected ?? row.text ?? '');
  return match ? Number(match[1]) : null;
}

function panelAt(row) {
  if (row.global_x == null || row.global_y == null) return null;
  const x = row.global_x + (row.global_w ?? 0) / 2;
  const y = row.global_y + (row.global_h ?? 0) / 2;
  const hit = (name) => {
    const { box } = PANELS[name];
    return x >= box.x0 && x <= box.x1 && y >= box.y0 && y <= box.y1;
  };
  const cholon = hit('Cholon');
  const saigon = hit('Saigon');
  if (cholon && saigon)
    return x < (PANELS.Cholon.box.x1 + PANELS.Saigon.box.x0) / 2 ? 'Cholon' : 'Saigon';
  if (cholon) return 'Cholon';
  if (saigon) return 'Saigon';
  return null;
}

function readAll(queryFactory) {
  return (async () => {
    const out = [];
    for (let from = 0; ; from += PAGE) {
      const { data, error } = await queryFactory(from, from + PAGE - 1);
      if (error) throw error;
      out.push(...(data ?? []));
      if (!data || data.length < PAGE) break;
    }
    return out;
  })();
}

async function targetTransformer(map) {
  const annotationUrl =
    map.annotation_url ||
    (map.allmaps_id ? `https://annotations.allmaps.org/images/${map.allmaps_id}` : null);
  if (!annotationUrl) throw new Error(`${map.name} has no usable georeference URL`);
  const response = await fetch(annotationUrl);
  if (!response.ok) throw new Error(`${map.name} annotation returned HTTP ${response.status}`);
  const annotation = await response.json();
  const parsed = parseAnnotation(annotation);
  if (!parsed.length) throw new Error(`${map.name} annotation contains no georeferenced map`);
  const transformer = GcpTransformer.fromGeoreferencedMap(parsed[0]);
  return {
    transformer,
    geomSrc: await gcpSrcHash(transformer),
    geomRmse: gcpRmseMetres(transformer),
  };
}

const { data: source, error: sourceError } = await db
  .from('maps')
  .select('id,name,year,status,triage')
  .eq('id', SOURCE_ID)
  .single();
if (sourceError) throw sourceError;
if (source.year !== 1942 || source.status !== 'draft')
  throw new Error('Source map is no longer the expected draft 1942 map');

const targetIds = Object.values(PANELS).map((panel) => panel.mapId);
const { data: maps, error: mapsError } = await db
  .from('maps')
  .select('id,name,year,status,annotation_url,allmaps_id,source_url')
  .in('id', targetIds);
if (mapsError) throw mapsError;
const targetById = new Map((maps ?? []).map((map) => [map.id, map]));
for (const [panelName, panel] of Object.entries(PANELS)) {
  const map = targetById.get(panel.mapId);
  if (!map || map.year !== 1942 || map.status !== 'public')
    throw new Error(`${panelName} target is missing or no longer public 1942`);
}

const sourceRows = await readAll((from, to) =>
  db
    .from('ocr_labels')
    .select('*')
    .eq('map_id', SOURCE_ID)
    .in('category', ['legend_entry', 'legend_ref'])
    .order('id')
    .range(from, to)
);
const entries = sourceRows.filter(
  (row) => row.category === 'legend_entry' && row.review_status !== 'rejected'
);
const references = sourceRows.filter(
  (row) => row.category === 'legend_ref' && row.review_status !== 'rejected'
);
if (entries.length !== 235) throw new Error(`Unexpected source entry count: ${entries.length}`);

const entryPanelByNumber = new Map();
const byPanel = { Saigon: [], Cholon: [] };
for (const row of entries) {
  const n = entryNumber(row);
  const panelName = panelAt(row);
  if (!n || !panelName) throw new Error(`Cannot assign source legend row ${row.id} to a panel`);
  if (entryPanelByNumber.has(n)) throw new Error(`Duplicate legend number ${n} on source map`);
  entryPanelByNumber.set(n, panelName);
  byPanel[panelName].push(row);
}
const saigonNumbers = byPanel.Saigon.map(entryNumber).sort((a, b) => a - b);
const cholonNumbers = byPanel.Cholon.map(entryNumber).sort((a, b) => a - b);
const saigonExpected = Array.from({ length: 155 }, (_, i) => i + 1).filter((n) => n !== 22);
const cholonExpected = Array.from({ length: 81 }, (_, i) => i + 156);
if (JSON.stringify(saigonNumbers) !== JSON.stringify(saigonExpected))
  throw new Error('Saigon panel legend numbers do not match 1–155 with only 22 missing');
if (JSON.stringify(cholonNumbers) !== JSON.stringify(cholonExpected))
  throw new Error('Cholon panel legend numbers do not match 156–236');

const refsByPanel = { Saigon: [], Cholon: [] };
let outsideReferences = 0;
let crossPanelReferences = 0;
for (const row of references) {
  const n = referenceNumber(row);
  const physicalPanel = panelAt(row);
  const legendPanel = entryPanelByNumber.get(n);
  if (!physicalPanel) {
    outsideReferences++;
    continue;
  }
  // These 20 OCR reads land in the other sheet panel than the index row for
  // the number claims. Keeping them would warp a likely misread to the wrong
  // published map, so leave them on the composite for later review.
  if (!n || !legendPanel || physicalPanel !== legendPanel) {
    crossPanelReferences++;
    continue;
  }
  refsByPanel[physicalPanel].push(row);
}

for (const [panelName, panel] of Object.entries(PANELS)) {
  const map = targetById.get(panel.mapId);
  const { data: existing, error } = await db
    .from('ocr_labels')
    .select('id')
    .eq('map_id', panel.mapId)
    .in('category', ['legend_entry', 'legend_ref'])
    .limit(1);
  if (error) throw error;
  if (existing?.length)
    throw new Error(`${map.name} already has legend OCR rows; refusing to duplicate`);
  panel.map = map;
  panel.transform = await targetTransformer(map);
  panel.sx = panel.width / (panel.box.x1 - panel.box.x0);
  panel.sy = panel.height / (panel.box.y1 - panel.box.y0);
}

function scaleX(panel, x) {
  return (x - panel.box.x0) * panel.sx;
}
function scaleY(panel, y) {
  return (y - panel.box.y0) * panel.sy;
}
function pointEwkt(panel, row) {
  const [lng, lat] = panel.transform.transformer.transformToGeo([
    row.global_x + (row.global_w ?? 0) / 2,
    row.global_y + (row.global_h ?? 0) / 2,
  ]);
  if (!Number.isFinite(lng) || !Number.isFinite(lat))
    throw new Error(`Could not warp extraction ${row.id} onto ${panel.map.name}`);
  return `SRID=4326;POINT(${lng.toFixed(8)} ${lat.toFixed(8)})`;
}

function buildRow(sourceRow, panelName) {
  const panel = PANELS[panelName];
  const width = panel.width;
  const height = panel.height;
  const rawX = scaleX(panel, sourceRow.global_x);
  const rawY = scaleY(panel, sourceRow.global_y);
  const rawW = Math.max(0, sourceRow.global_w ?? 0) * panel.sx;
  const rawH = Math.max(0, sourceRow.global_h ?? 0) * panel.sy;
  const gx = Math.min(width, Math.max(0, rawX));
  const gy = Math.min(height, Math.max(0, rawY));
  const gw = Math.min(rawW, width - gx);
  const gh = Math.min(rawH, height - gy);
  const notes = [
    sourceRow.notes,
    `migration_source=${SOURCE_ID}`,
    `split_panel=${panelName.toLowerCase()}`,
  ]
    .filter(Boolean)
    .join('; ');
  return {
    id: randomUUID(),
    map_id: panel.mapId,
    run_id: `${sourceRow.run_id}:split-${panelName.toLowerCase()}`,
    tile_x: Math.round(scaleX(panel, sourceRow.tile_x)),
    tile_y: Math.round(scaleY(panel, sourceRow.tile_y)),
    tile_w: Math.max(1, Math.round(sourceRow.tile_w * panel.sx)),
    tile_h: Math.max(1, Math.round(sourceRow.tile_h * panel.sy)),
    global_x: gx,
    global_y: gy,
    global_w: gw,
    global_h: gh,
    category: sourceRow.category,
    text: sourceRow.text,
    text_corrected: sourceRow.text_corrected,
    category_corrected: sourceRow.category_corrected,
    confidence: sourceRow.confidence,
    notes,
    model: sourceRow.model,
    prompt: sourceRow.prompt,
    rotation_deg: sourceRow.rotation_deg,
    label_w: sourceRow.label_w == null ? null : sourceRow.label_w * panel.sx,
    label_h: sourceRow.label_h == null ? null : sourceRow.label_h * panel.sy,
    review_status: 'pending',
    reviewed_by: null,
    reviewed_at: null,
    created_at: sourceRow.created_at,
    geom: pointEwkt(panel, {
      ...sourceRow,
      global_x: gx,
      global_y: gy,
      global_w: gw,
      global_h: gh,
    }),
    geom_src: panel.transform.geomSrc,
    geom_rmse: panel.transform.geomRmse,
  };
}

const rowsByPanel = {
  Saigon: [
    ...byPanel.Saigon.map((row) => buildRow(row, 'Saigon')),
    ...refsByPanel.Saigon.map((row) => buildRow(row, 'Saigon')),
  ],
  Cholon: [
    ...byPanel.Cholon.map((row) => buildRow(row, 'Cholon')),
    ...refsByPanel.Cholon.map((row) => buildRow(row, 'Cholon')),
  ],
};

const summaries = Object.fromEntries(
  Object.entries(rowsByPanel).map(([panelName, rows]) => [
    panelName,
    {
      map: PANELS[panelName].map.name,
      legendEntries: rows.filter((row) => row.category === 'legend_entry').length,
      bodyReferences: rows.filter((row) => row.category === 'legend_ref').length,
      uniqueReferenceNumbers: new Set(
        rows.filter((row) => row.category === 'legend_ref').map(referenceNumber)
      ).size,
      dimensions: [PANELS[panelName].width, PANELS[panelName].height],
      transformedPixelsInBounds: rows.every(
        (row) =>
          row.global_x >= 0 &&
          row.global_y >= 0 &&
          row.global_x + (row.global_w ?? 0) <= PANELS[panelName].width &&
          row.global_y + (row.global_h ?? 0) <= PANELS[panelName].height
      ),
    },
  ])
);
console.log(
  JSON.stringify(
    {
      mode: apply ? 'APPLY' : 'DRY RUN',
      source: { map: source.name, entries: entries.length, bodyReferences: references.length },
      targets: summaries,
      skipped: {
        missingIndexNumber: 22,
        crossPanelReferences,
        outsidePanelReferences: outsideReferences,
      },
    },
    null,
    2
  )
);

if (Object.values(summaries).some((summary) => !summary.transformedPixelsInBounds))
  throw new Error('At least one transformed OCR box falls outside its destination scan');
if (!apply) {
  console.log('\nDry run only. Pass --apply to insert the rows.');
  process.exit(0);
}

const insertedIds = Object.values(rowsByPanel)
  .flat()
  .map((row) => row.id);
try {
  for (const [panelName, rows] of Object.entries(rowsByPanel)) {
    for (let i = 0; i < rows.length; i += 100) {
      const { error } = await db.from('ocr_labels').insert(rows.slice(i, i + 100));
      if (error) throw error;
      console.log(`${panelName}: inserted ${Math.min(i + 100, rows.length)} / ${rows.length}`);
    }
  }
} catch (writeError) {
  console.error('Insert failed; removing rows written by this run.');
  for (let i = 0; i < insertedIds.length; i += 100) {
    const { error } = await db
      .from('ocr_labels')
      .delete()
      .in('id', insertedIds.slice(i, i + 100));
    if (error) console.error('Rollback failed for one batch:', error.message);
  }
  throw writeError;
}

for (const [panelName, panel] of Object.entries(PANELS)) {
  const { count, error } = await db
    .from('ocr_labels')
    .select('id', { count: 'exact', head: true })
    .eq('map_id', panel.mapId)
    .eq('category', 'legend_entry');
  if (error) throw error;
  if (count !== summaries[panelName].legendEntries)
    throw new Error(
      `${panel.map.name} verification count ${count} does not match ${summaries[panelName].legendEntries}`
    );
}
console.log('Verified migrated legend entry counts. The source draft remains unchanged.');
