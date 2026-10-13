#!/usr/bin/env node
/**
 * The L909 city maps from USGS/NGA's GeoPDFs: catalogue all 18, give the 16
 * PCL draft rectos the GeoPDF raster as their primary image, and georeference
 * them from the PDF's own control points and neatline.
 *
 *   node --env-file=.env scripts/oneoff/ingest_l909_usgs.mjs              # plan only
 *   node --env-file=.env scripts/oneoff/ingest_l909_usgs.mjs --download   # + fetch PDFs, render, datum check
 *   node --env-file=.env scripts/oneoff/ingest_l909_usgs.mjs --apply      # + write
 *
 * The geometry is `l909_usgs_georef.py` (it explains the Indian 1960 trap and
 * the gates). The datum check needs a Python with OpenCV: VMA_CV_PYTHON, see
 * that file's header. Without a passing datum check for BOTH Ha Noi and Hue,
 * no georeference is written.
 *
 * Writes, all additive and resumable (local journal; every step re-checks the
 * database before acting):
 *  - `cell_printings` institution USGS, upserted on (institution, source_ref),
 *    for all 18 PDFs. Title, year and edition are the PDF's own metadata.
 *  - per draft recto: R2 tiles at the versioned service `iiif/<map>/v2` (the
 *    PCL tiles at the unversioned prefix are untouched), a `map_images` row
 *    linked to the USGS item, made primary; the PCL row stays, demoted.
 *  - per draft that passes every gate: `annotations/<map>/<stamp>.json` +
 *    `georef_versions` + `annotations/<map>.json`, then `maps.annotation_url`,
 *    `is_georeferenced`, `bbox`. A sheet that fails a gate keeps its new image
 *    and gets no georeference; the reason is recorded in `extra_metadata`.
 * Never touched: public maps (Ha Noi, Hue, Sai Gon), map status, PCL rows.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { generateId } from '@allmaps/id';
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice, flag } from '../lib/cli.mjs';
import { recordGeorefVersion } from '../lib/georef_versions.mjs';

const KEY = 'ams-l909-viet-nam-city-maps-1-12-500';
const CODES = {
  BIENHOA: 'Biên Hòa',
  CANTHO: 'Cần Thơ',
  CHULAIVI: 'Chu Lai',
  DALAT: 'Đà Lạt',
  DANANG: 'Đà Nẵng',
  DONGHOI: 'Đồng Hới',
  HAIPHONG: 'Hải Phòng',
  HANOI: 'Hà Nội',
  HUE: 'Huế',
  LACGIAO: 'Lạc Giao',
  MYTHO: 'Mỹ Tho',
  NHATRANG: 'Nha Trang',
  PHULANGT: 'Phủ Lạng Thương',
  QUANGNGA: 'Quảng Ngãi',
  QUINHON: 'Quy Nhơn',
  TUYHOA: 'Tuy Hòa',
  VINHBENT: 'Vinh và Bến Thủy',
  VINHLONG: 'Vĩnh Long',
};
// Hand-georeferenced public sheets: the outside opinion for the datum, never written.
const DATUM_REFS = {
  HANOI: { mapId: '0a8b92dc-4ad9-47b2-8072-ad570b73e327', ia: 'hanoi1968%2Ftxu-oclc-232337961-hanoi-1968.jpg' },
  HUE: { mapId: '1979d85d-cb9a-4a25-932f-9fefd22a1663', ia: 'hue1968%2Ftxu-oclc-21740104-hue-1968.jpg' },
};
const pdfUrl = (code) => `https://store.usgs.gov/assets/MOD/StoreFiles/NGA/L909X${code}_geo.pdf`;
const sourceRef = (code) => `L909X${code}_geo.pdf`;
const R2 = 'https://iiif.maparchive.vn/iiif';
const VERSION = 2; // the PCL scan is the unversioned prefix
const BATCH = 'l909-usgs-20261006';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const helper = path.join(repo, 'scripts/oneoff/l909_usgs_georef.py');
const cacheDir = '/private/tmp/vma-l909-usgs';
const pdfDir = path.join(cacheDir, 'pdfs');
const journalPath = path.join(cacheDir, 'journal.json');
const analysisPath = path.join(cacheDir, 'analysis.json');
const manifestPath = path.join(repo, 'work/l909/usgs-geopdfs.json');
const apply = willApply();
const download = apply || flag('--download');
const cvPython = process.env.VMA_CV_PYTHON;
const db = serviceClient();
for (const d of [cacheDir, pdfDir, path.join(cacheDir, 'ref')]) fs.mkdirSync(d, { recursive: true });
const journal = fs.existsSync(journalPath) ? JSON.parse(fs.readFileSync(journalPath, 'utf8')) : {};
const saveJournal = () => fs.writeFileSync(journalPath, JSON.stringify(journal, null, 2) + '\n');
const sha256 = (file) => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
// Key order is not data: jsonb hands objects back with its own key order.
const canon = (v) =>
  Array.isArray(v)
    ? v.map(canon)
    : v && typeof v === 'object'
      ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])]))
      : v;
const same = (a, b) => JSON.stringify(canon(a ?? null)) === JSON.stringify(canon(b ?? null));

function run(command, args, logPath) {
  return new Promise((resolve, reject) => {
    const fd = logPath ? fs.openSync(logPath, 'w') : null;
    const child = spawn(command, args, { cwd: repo, stdio: ['ignore', fd ?? 'pipe', fd ?? 'pipe'] });
    let output = '';
    let errorOutput = '';
    child.stdout?.on('data', (chunk) => (output += chunk));
    child.stderr?.on('data', (chunk) => (errorOutput += chunk));
    child.on('error', reject);
    child.on('close', (code) => {
      if (fd != null) fs.closeSync(fd);
      if (code !== 0)
        reject(
          new Error(
            `${command} exited ${code}${logPath ? `; see ${logPath}` : `: ${(errorOutput || output).slice(-800)}`}`
          )
        );
      else resolve(output.trim());
    });
  });
}
const fetchFile = (url, file) =>
  run('curl', ['-L', '--fail', '--retry', '3', '--connect-timeout', '20', '--max-time', '600', '-sS', url, '-o', file]);

// ── read state ───────────────────────────────────────────────────────────────
const [seriesR, cellsR, printingsR, mapsR] = await Promise.all([
  db.from('series').select('id,key,name').eq('key', KEY).single(),
  db.from('series_cells').select('sheet_number').eq('series_key', KEY),
  db.from('cell_printings').select('*').eq('series_key', KEY),
  db.from('maps').select('*').eq('series_key', KEY).neq('status', 'archived'),
]);
for (const r of [seriesR, cellsR, printingsR, mapsR]) if (r.error) throw r.error;
const series = seriesR.data;
const cellNames = new Set(cellsR.data.map((c) => c.sheet_number));
for (const city of Object.values(CODES))
  if (!cellNames.has(city)) throw new Error(`No series cell for ${city}`);
const imagesR = await db
  .from('map_images')
  .select('*')
  .in(
    'map_id',
    mapsR.data.map((m) => m.id)
  );
if (imagesR.error) throw imagesR.error;
const publicBefore = mapsR.data.filter((m) => m.status !== 'draft');

// ── PDFs and the local analysis (read-only) ─────────────────────────────────
const missingPdfs = Object.keys(CODES).filter((c) => !fs.existsSync(path.join(pdfDir, `${c}.pdf`)));
if (missingPdfs.length && download) {
  for (const code of missingPdfs) {
    const part = path.join(pdfDir, `${code}.pdf.part`);
    await fetchFile(pdfUrl(code), part);
    fs.renameSync(part, path.join(pdfDir, `${code}.pdf`));
    console.log(`Downloaded ${sourceRef(code)}`);
  }
} else if (missingPdfs.length) {
  console.log(`PDFs not yet downloaded: ${missingPdfs.join(', ')}`);
  dryNotice('--download fetches them; nothing else can be planned without them.');
  process.exit(0);
}
for (const code of Object.keys(CODES)) {
  const digest = sha256(path.join(pdfDir, `${code}.pdf`));
  journal[code] ??= {};
  if (journal[code].pdfSha256 && journal[code].pdfSha256 !== digest)
    throw new Error(`${code}.pdf changed since the journal recorded it`);
  journal[code].pdfSha256 = digest;
}
saveJournal();
await run('python3', [helper, 'analyse', pdfDir, analysisPath]);
const analysis = JSON.parse(fs.readFileSync(analysisPath, 'utf8'));

// The datum check: both hand-placed sheets must pick the explicit Indian 1960.
const datum = {};
for (const [code, ref] of Object.entries(DATUM_REFS)) {
  const out = path.join(cacheDir, `datum-${code}.json`);
  if (!fs.existsSync(out) && download && cvPython) {
    const ann = path.join(cacheDir, 'ref', `${ref.mapId}.json`);
    const img = path.join(cacheDir, 'ref', `${ref.mapId}.jpg`);
    if (!fs.existsSync(ann))
      await fetchFile(`https://maparchive.vn/api/maps/${ref.mapId}/annotation`, ann);
    if (!fs.existsSync(img))
      await fetchFile(`https://iiif.archive.org/image/iiif/3/${ref.ia}/full/max/0/default.jpg`, img);
    await run(cvPython, [helper, 'datum', path.join(pdfDir, `${code}.pdf`), ann, img, out]);
  }
  datum[code] = fs.existsSync(out) ? JSON.parse(fs.readFileSync(out, 'utf8')) : null;
}
const datumOk = Object.values(datum).every((d) => d?.verdict === 'indian1960');

// ── plan ─────────────────────────────────────────────────────────────────────
const printingRow = (code) => {
  const a = analysis[code];
  return {
    series_key: KEY,
    series_id: series.id,
    sheet_number: CODES[code],
    institution: 'USGS',
    source_ref: sourceRef(code),
    url: pdfUrl(code),
    edition: a.edition,
    title: a.title,
    year: a.year,
    note:
      `USGS Store GeoPDF of NGA's digital edition: recto only, ${a.width}x${a.height} px at 300 dpi, ` +
      `with NGA control points and neatline. Title, edition and year are the PDF's own metadata ` +
      `(XMP pri_date ${a.pri_date ?? 'absent'}).`,
  };
};
const printingPlan = [];
for (const code of Object.keys(CODES)) {
  const want = printingRow(code);
  const have = printingsR.data.find(
    (p) => p.institution === 'USGS' && p.source_ref === want.source_ref
  );
  if (!have || Object.entries(want).some(([k, v]) => !same(have[k], v))) printingPlan.push(want);
}

const leadingInt = (s) => Number(String(s ?? '').match(/^\d+/)?.[0] ?? NaN);
const mapPlan = [];
const skipped = [];
for (const code of Object.keys(CODES)) {
  if (DATUM_REFS[code]) continue;
  const city = CODES[code];
  const a = analysis[code];
  const candidates = mapsR.data.filter(
    (m) =>
      m.sheet_number === city &&
      m.status === 'draft' &&
      m.extra_metadata?.scan_side === 'recto' &&
      m.extra_metadata?.source_archive === 'PCL'
  );
  if (candidates.length !== 1) {
    skipped.push(`${city}: ${candidates.length} PCL draft rectos`);
    continue;
  }
  const map = candidates[0];
  const images = imagesR.data.filter((i) => i.map_id === map.id);
  const pcl = images.find((i) => i.label === 'PCL recto');
  const pclPrinting = printingsR.data.find((p) => p.id === pcl?.source_item_id);
  const holdImage = [];
  if (!pcl) holdImage.push('no PCL image row');
  if (leadingInt(pclPrinting?.edition) !== leadingInt(a.edition))
    holdImage.push(`edition: PCL ${pclPrinting?.edition} vs USGS ${a.edition}`);
  if (map.triage && Object.keys(map.triage).length) holdImage.push('has triage on the PCL pixels');
  const iiif = `${R2}/${map.id}/v${VERSION}`;
  const usgsImage = images.find((i) => i.iiif_image === iiif);
  const holdGeoref = [...(a.held ?? [])];
  if (!datumOk) holdGeoref.push('datum check against Hà Nội / Huế not passed');
  journal[code].mapId ??= map.id;
  if (journal[code].mapId !== map.id) throw new Error(`${code}: journal names another map`);
  mapPlan.push({ code, city, a, map, pcl, iiif, usgsImage, holdImage, holdGeoref });
}
saveJournal();

// Pixel-bound work on the PCL scan would be invalidated by the image swap.
const children = {};
for (const table of ['ocr_labels', 'footprints', 'label_pins']) {
  const r = await db
    .from(table)
    .select('map_id')
    .in(
      'map_id',
      mapPlan.map((p) => p.map.id)
    );
  if (r.error) throw r.error;
  for (const row of r.data) children[row.map_id] = (children[row.map_id] ?? 0) + 1;
}
for (const p of mapPlan)
  if (children[p.map.id]) p.holdImage.push(`${children[p.map.id]} pixel-bound rows on the PCL scan`);

async function liveAnnotation(mapId) {
  const r = await db.storage.from('annotations').download(`${mapId}.json`);
  if (r.error) return null;
  return JSON.parse(await r.data.text());
}
async function expectedAnnotation(p) {
  const out = path.join(cacheDir, `${p.code}-annotation.json`);
  await run('python3', [helper, 'annotation', analysisPath, p.code, p.iiif, out]);
  return JSON.parse(fs.readFileSync(out, 'utf8'));
}
const georefMethod = (p) =>
  `USGS GeoPDF ${sourceRef(p.code)}: ${p.a.gcps} NGA control points (affine, max ${p.a.gcp_max_m} m) and ` +
  `printed neatline; UTM zone ${p.a.zone} on Indian 1960 (Everest 1830 1937 Adj., towgs84 198,881,317), ` +
  `spelled out, not looked up. Datum checked against the hand-georeferenced Hà Nội and Huế sheets.`;
function wantedMapFields(p, annotate) {
  const extra = { ...p.map.extra_metadata, usgs_geopdf: sourceRef(p.code), usgs_batch: BATCH };
  if (annotate) {
    extra.georef_method = georefMethod(p);
    delete extra.georef_held;
  } else extra.georef_held = p.holdGeoref.join('; ');
  return {
    thumbnail: `${p.iiif}/full/800,/0/default.jpg`,
    extra_metadata: extra,
    ...(annotate
      ? {
          annotation_url: `https://maparchive.vn/api/maps/${p.map.id}/annotation`,
          is_georeferenced: true,
          bbox: p.a.bbox,
        }
      : {}),
  };
}

const steps = [];
for (const p of mapPlan) {
  p.todo = [];
  if (p.holdImage.length) continue;
  if (!p.usgsImage) p.todo.push('render+mirror', 'image row');
  if (!p.usgsImage?.is_primary) p.todo.push('primary');
  const annotate = !p.holdGeoref.length;
  p.annotate = annotate;
  if (annotate) {
    p.expected = await expectedAnnotation(p);
    if (!same(await liveAnnotation(p.map.id), p.expected)) p.todo.push('annotation');
  }
  p.allmapsId = await generateId(p.iiif);
  const want = { ...wantedMapFields(p, annotate), allmaps_id: p.allmapsId };
  if (Object.entries(want).some(([k, v]) => !same(p.map[k], v))) p.todo.push('map fields');
  if (p.todo.length) steps.push(p);
}

const fmt = (a) =>
  `${a.width}x${a.height} gcps ${a.gcps} rms ${a.gcp_rms_m} max ${a.gcp_max_m} m, aspect ${a.neatline_aspect}/${a.graticule_aspect}, frame ${Math.round(a.frame_found * 100)}%, city ${a.city_miss_m} m`;
console.log(`Series ${KEY}: ${mapsR.data.length} maps, ${printingsR.data.length} printings`);
console.log(
  `Datum (outside opinion): ` +
    Object.entries(datum)
      .map(([c, d]) =>
        d
          ? `${c} ${d.verdict} — Indian 1960 ${d.at_hand_gcps.indian1960_explicit.median_m} m, WGS84 ${d.at_hand_gcps.wgs84_unshifted.median_m} m, GDAL's reading ${d.at_hand_gcps.gdal_declared.median_m} m`
          : `${c} not run`
      )
      .join('; ')
);
console.log(`cell_printings to upsert: ${printingPlan.length}`);
for (const r of printingPlan) console.log(`  USGS ${r.sheet_number} ${r.source_ref} ed ${r.edition} ${r.year}`);
for (const p of mapPlan) {
  const state = p.holdImage.length
    ? `HOLD image (${p.holdImage.join('; ')})`
    : p.todo.length
      ? `todo: ${p.todo.join(', ')}${p.annotate ? '' : ` — georef HELD: ${p.holdGeoref.join('; ')}`}`
      : `done${p.annotate ? '' : ` (georef held: ${p.holdGeoref.join('; ')})`}`;
  console.log(`  ${p.city.padEnd(18)} ${fmt(p.a)} — ${state}`);
}
for (const s of skipped) console.log(`  skipped ${s}`);
if (!apply) {
  dryNotice(
    steps.length || printingPlan.length
      ? `${printingPlan.length} printing rows and ${steps.length} maps to write.`
      : 'Nothing to write.'
  );
  process.exit(0);
}

// ── apply ────────────────────────────────────────────────────────────────────
if (!datumOk) console.log('Datum check has not passed: images only, no georeference.');
if (printingPlan.length) {
  const { error } = await db
    .from('cell_printings')
    .upsert(printingPlan, { onConflict: 'institution,source_ref' });
  if (error) throw error;
}
const printings = await db
  .from('cell_printings')
  .select('*')
  .eq('series_key', KEY)
  .eq('institution', 'USGS');
if (printings.error) throw printings.error;
for (const code of Object.keys(CODES)) {
  const want = printingRow(code);
  const have = printings.data.find((p) => p.source_ref === want.source_ref);
  if (!have || Object.entries(want).some(([k, v]) => !same(have[k], v)))
    throw new Error(`Printing read-back differs: ${code}`);
  journal[code].printingId = have.id;
}
saveJournal();

async function getImage(url, expectedWidth, expectedSha256) {
  for (let attempt = 0; attempt < 8; attempt++) {
    const response = await fetch(url, { signal: AbortSignal.timeout(60_000) });
    if (response.ok && response.headers.get('content-type')?.includes('image/jpeg')) {
      const bytes = Buffer.from(await response.arrayBuffer());
      if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes.length > 1000) {
        const probe = path.join(cacheDir, `probe-${randomUUID()}.jpg`);
        fs.writeFileSync(probe, bytes);
        const width = Number(await run('vipsheader', ['-f', 'width', probe]));
        fs.unlinkSync(probe);
        if (width === expectedWidth) {
          if (expectedSha256 && createHash('sha256').update(bytes).digest('hex') !== expectedSha256)
            throw new Error(`Native JPEG checksum differs: ${url}`);
          return;
        }
      }
    }
    if (attempt < 7) await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  throw new Error(`Mirrored image verification failed: ${url}`);
}

async function verifyMirror(p, state) {
  const info = await (await fetch(`${p.iiif}/info.json`, { signal: AbortSignal.timeout(30_000) })).json();
  if (info.id !== p.iiif || info.width !== state.width || info.height !== state.height || !info.tiles?.length)
    throw new Error(`IIIF info differs for ${p.city}: ${info.id} ${info.width}x${info.height}`);
  await getImage(`${p.iiif}/full/800,/0/default.jpg`, 800);
  await getImage(`${p.iiif}/full/2048,/0/default.jpg`, 2048);
  await getImage(`${p.iiif}/full/max/0/default.jpg`, state.width, state.sha256);
  const sf = info.tiles[0].scaleFactors.at(-1);
  const span = info.tiles[0].width * sf;
  const tw = Math.min(span, state.width);
  const th = Math.min(span, state.height);
  const tilePath =
    span >= state.width && span >= state.height
      ? `full/${Math.ceil(state.width / sf)},${Math.ceil(state.height / sf)}`
      : `0,0,${tw},${th}/${Math.ceil(tw / sf)},`;
  await getImage(`${p.iiif}/${tilePath}/0/default.jpg`, Math.ceil(tw / sf));
  await getImage(`${p.iiif}/0,0,256,256/256,/0/default.jpg`, 256);
}

async function uploadJson(objectPath, obj) {
  const res = await fetch(
    `${process.env.PUBLIC_SUPABASE_URL}/storage/v1/object/annotations/${objectPath}`,
    {
      method: 'POST',
      headers: {
        apikey: process.env.SUPABASE_SERVICE_KEY,
        Authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY}`,
        'Content-Type': 'application/json',
        'x-upsert': 'true',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(obj, null, 2),
    }
  );
  if (!res.ok) throw new Error(`Storage upload ${objectPath}: ${res.status} ${await res.text()}`);
}

async function process1(p) {
  const state = journal[p.code];
  const jpg = path.join(cacheDir, `${p.code}.jpg`);
  if (!p.usgsImage) {
    if (!state.mirrored) {
      if (!fs.existsSync(jpg)) {
        await run('python3', [helper, 'render', path.join(pdfDir, `${p.code}.pdf`), jpg + '.part.jpg']);
        fs.renameSync(jpg + '.part.jpg', jpg);
      }
      const width = Number(await run('vipsheader', ['-f', 'width', jpg]));
      const height = Number(await run('vipsheader', ['-f', 'height', jpg]));
      if (width !== p.a.width || height !== p.a.height)
        throw new Error(`${p.city}: rendered ${width}x${height}, analysed ${p.a.width}x${p.a.height}`);
      Object.assign(state, { width, height, sha256: sha256(jpg), bytes: fs.statSync(jpg).size });
      saveJournal();
      console.log(`Mirroring ${p.city} → ${p.iiif}`);
      await run(
        'bash',
        ['scripts/tile_map.sh', p.map.id, jpg, '--version', String(VERSION)],
        path.join(cacheDir, `${p.code}-tile.log`)
      );
      const overview = path.join(cacheDir, `${p.code}-2048.jpg`);
      await run('vips', ['thumbnail', jpg, overview, '2048', '--height', '1000000', '--size', 'down']);
      const prefix = `r2:vma-tiles/tiles/${p.map.id}/v${VERSION}`;
      await run('rclone', ['copyto', overview, `${prefix}/full/2048,/0/default.jpg`, '--s3-no-check-bucket']);
      await run('rclone', ['copyto', jpg, `${prefix}/full/${width},/0/default.jpg`, '--s3-no-check-bucket']);
      state.mirrored = true;
      saveJournal();
    }
    await verifyMirror(p, state);
    state.assetVersion ??= randomUUID();
    saveJournal();
    const { data, error } = await db
      .from('map_images')
      .insert({
        map_id: p.map.id,
        source_item_id: state.printingId,
        source_type: 'r2',
        iiif_image: p.iiif,
        is_primary: false,
        label: 'USGS GeoPDF recto',
        width: state.width,
        height: state.height,
        content_sha256: state.sha256,
        asset_version: state.assetVersion,
        content_role: 'main_map',
      })
      .select()
      .single();
    if (error) throw error;
    p.usgsImage = data;
  }
  if (!p.usgsImage.is_primary) {
    // One primary per map (unique index): demote first, then promote; the
    // trigger copies the new primary into maps.iiif_image.
    let r = await db.from('map_images').update({ is_primary: false }).eq('map_id', p.map.id).neq('id', p.usgsImage.id);
    if (r.error) throw r.error;
    r = await db.from('map_images').update({ is_primary: true }).eq('id', p.usgsImage.id);
    if (r.error) throw r.error;
  }
  if (p.annotate && p.todo.includes('annotation')) {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    await uploadJson(`${p.map.id}/${stamp}.json`, p.expected);
    await recordGeorefVersion(db, p.map.id, stamp, p.expected, 'script');
    await uploadJson(`${p.map.id}.json`, p.expected);
    state.annotationStamp = stamp;
    saveJournal();
  }
  const { error } = await db
    .from('maps')
    .update({ ...wantedMapFields(p, p.annotate), allmaps_id: p.allmapsId })
    .eq('id', p.map.id)
    .eq('status', 'draft');
  if (error) throw error;

  // Read back.
  const m = await db.from('maps').select('*').eq('id', p.map.id).single();
  const imgs = await db.from('map_images').select('*').eq('map_id', p.map.id);
  if (m.error || imgs.error) throw m.error ?? imgs.error;
  const primary = imgs.data.filter((i) => i.is_primary);
  if (
    m.data.status !== 'draft' ||
    m.data.iiif_image !== p.iiif ||
    primary.length !== 1 ||
    primary[0].iiif_image !== p.iiif ||
    primary[0].source_item_id !== state.printingId ||
    !imgs.data.some((i) => i.id === p.pcl.id && !i.is_primary && i.iiif_image === p.pcl.iiif_image)
  )
    throw new Error(`${p.city}: map/image read-back differs`);
  if (p.annotate) {
    if (!same(await liveAnnotation(p.map.id), p.expected))
      throw new Error(`${p.city}: live annotation differs from what was written`);
    if (!m.data.is_georeferenced || !same(m.data.bbox, p.a.bbox)) throw new Error(`${p.city}: georef fields`);
  } else if (m.data.annotation_url) throw new Error(`${p.city}: held sheet carries an annotation`);
  state.complete = true;
  saveJournal();
  console.log(`Verified ${p.city}${p.annotate ? ' (georeferenced)' : ` (image only; ${p.holdGeoref.join('; ')})`}`);
}

let next = 0;
const failures = [];
async function worker() {
  while (next < steps.length) {
    const p = steps[next++];
    try {
      await process1(p);
    } catch (e) {
      failures.push(`${p.city}: ${e.message ?? JSON.stringify(e)}`);
      console.error(`FAILED ${p.city}: ${e.message ?? JSON.stringify(e)}`);
    }
  }
}
await Promise.all([worker(), worker()]);

const after = await db
  .from('maps')
  .select('*')
  .in(
    'id',
    publicBefore.map((m) => m.id)
  );
if (after.error) throw after.error;
for (const m of publicBefore)
  if (!same(m, after.data.find((x) => x.id === m.id)))
    throw new Error(`A public map changed: ${m.name}`);

// The checked record.
const manifest = {
  checkedAt: new Date().toISOString(),
  seriesKey: KEY,
  datum: Object.fromEntries(
    Object.entries(datum).map(([c, d]) => [
      c,
      d && {
        verdict: d.verdict,
        handGcps: d.hand.gcps,
        handSelfRmsM: d.hand.self_rms_m,
        registrationInliers: d.registration.inliers,
        medianM: Object.fromEntries(Object.entries(d.at_hand_gcps).map(([k, v]) => [k, v.median_m])),
      },
    ])
  ),
  sheets: Object.keys(CODES).map((code) => {
    const a = analysis[code];
    const p = mapPlan.find((x) => x.code === code);
    return {
      code,
      city: CODES[code],
      sourceRef: sourceRef(code),
      printingId: journal[code].printingId,
      edition: a.edition,
      year: a.year,
      width: a.width,
      height: a.height,
      pdfSha256: journal[code].pdfSha256,
      gcps: a.gcps,
      gcpRmsM: a.gcp_rms_m,
      gcpMaxM: a.gcp_max_m,
      zone: a.zone,
      neatlineAspect: [a.neatline_aspect, a.graticule_aspect],
      frameFound: a.frame_found,
      cityMissM: a.city_miss_m,
      shiftVsWgs84M: a.shift_vs_wgs84_m,
      mapId: p?.map.id ?? null,
      iiifImage: p && !p.holdImage.length ? p.iiif : null,
      imageSha256: journal[code].sha256 ?? null,
      georeferenced: p ? p.annotate && !p.holdImage.length : null,
      held: p ? [...p.holdImage, ...(p.annotate ? [] : p.holdGeoref)] : ['public map: catalogue row only'],
    };
  }),
};
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
if (failures.length) throw new Error(failures.join('\n'));
console.log(`Complete. Public maps unchanged. Record: ${path.relative(repo, manifestPath)}`);
