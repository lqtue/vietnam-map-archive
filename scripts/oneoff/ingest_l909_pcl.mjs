#!/usr/bin/env node
/**
 * Ingest the indexed PCL L909 images not already held, including two versos.
 * node --env-file=.env scripts/oneoff/ingest_l909_pcl.mjs [--download] [--apply]
 * Default: read-only plan. --download stages/validates local JPEGs. --apply
 * mirrors those images to R2 and creates draft maps with explicit source links.
 * Existing maps and printing identities are never edited. A local journal and
 * source URLs make an interrupted run resumable without duplicate map rows.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { generateId } from '@allmaps/id';
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const key = 'ams-l909-viet-nam-city-maps-1-12-500';
const cacheDir = '/private/tmp/vma-l909-ingest';
const journalPath = path.join(cacheDir, 'journal.json');
const apply = willApply();
const download = apply || process.argv.includes('--download');
const db = serviceClient();
fs.mkdirSync(cacheDir, { recursive: true });
const journal = fs.existsSync(journalPath) ? JSON.parse(fs.readFileSync(journalPath, 'utf8')) : {};
const saveJournal = () => fs.writeFileSync(journalPath, JSON.stringify(journal, null, 2) + '\n');

function run(command, args, logPath) {
  return new Promise((resolve, reject) => {
    const fd = logPath ? fs.openSync(logPath, 'w') : null;
    const child = spawn(command, args, { stdio: ['ignore', fd ?? 'pipe', fd ?? 'pipe'] });
    let output = '';
    let errorOutput = '';
    child.stdout?.on('data', (chunk) => {
      output += chunk;
    });
    child.stderr?.on('data', (chunk) => {
      errorOutput += chunk;
    });
    child.on('error', reject);
    child.on('close', (code) => {
      if (fd != null) fs.closeSync(fd);
      if (code !== 0)
        reject(
          new Error(
            `${command} exited ${code}${logPath ? `; see ${logPath}` : `: ${(errorOutput || output).slice(-500)}`}`
          )
        );
      else resolve(output.trim());
    });
  });
}

const [seriesResult, sourceResult, mapResult] = await Promise.all([
  db.from('series').select('id,key,name').eq('key', key).single(),
  db
    .from('cell_printings')
    .select('id,series_id,sheet_number,title,url,source_ref,year,edition,note')
    .eq('series_key', key)
    .eq('institution', 'PCL')
    .order('sheet_number')
    .order('id'),
  db.from('maps').select('*').eq('series_key', key).neq('status', 'archived'),
]);
for (const result of [seriesResult, sourceResult, mapResult]) if (result.error) throw result.error;
const series = seriesResult.data;
const sources = sourceResult.data;
const existingMaps = mapResult.data;
if (sources.length !== 21)
  throw new Error(`Expected 21 reviewed PCL source items, found ${sources.length}`);
const imageResult = existingMaps.length
  ? await db
      .from('map_images')
      .select('map_id,source_item_id')
      .in(
        'map_id',
        existingMaps.map((map) => map.id)
      )
  : { data: [], error: null };
if (imageResult.error) throw imageResult.error;
const plan = [];
for (const source of sources) {
  const url = new URL(source.url);
  if (
    url.hostname !== 'maps.lib.utexas.edu' ||
    !url.pathname.endsWith('.jpg') ||
    source.series_id !== series.id
  ) {
    throw new Error(`Unreviewed source URL or series: ${source.id}`);
  }
  const existing =
    existingMaps.find((map) => map.source_url === source.url) ??
    existingMaps.find((map) =>
      imageResult.data.some(
        (image) => image.map_id === map.id && image.source_item_id === source.id
      )
    );
  if (existing && (journal[source.id]?.mapId !== existing.id || journal[source.id]?.complete))
    continue;
  journal[source.id] ??= { mapId: randomUUID(), sourceUrl: source.url };
  if (journal[source.id].sourceUrl !== source.url) throw new Error(`Source changed: ${source.id}`);
  plan.push({
    source,
    existing,
    state: journal[source.id],
    file: path.join(cacheDir, source.source_ref),
  });
}
saveJournal();
console.log(
  JSON.stringify(
    {
      series: key,
      existingMaps: existingMaps.length,
      newOrResumableScans: plan.length,
      newCities: new Set(
        plan
          .filter((item) => !item.source.title.includes('[verso]'))
          .map((item) => item.source.sheet_number)
      ).size,
      versos: plan.filter((item) => item.source.title.includes('[verso]')).length,
      targets: plan.map((item) => ({
        city: item.source.sheet_number,
        title: item.source.title,
        year: item.source.year,
        edition: item.source.edition,
      })),
    },
    null,
    2
  )
);
if (!download) {
  dryNotice('Downloads and validates JPEGs, then mirrors and creates draft records.');
  process.exit(0);
}
if (!fs.existsSync(path.join(cacheDir, 'existing-maps-before.json'))) {
  fs.writeFileSync(
    path.join(cacheDir, 'existing-maps-before.json'),
    JSON.stringify(existingMaps, null, 2)
  );
}

// Bound parallel source reads; finish validating every image before any remote write.
let next = 0;
async function stage() {
  while (next < plan.length) {
    const item = plan[next++];
    if (!fs.existsSync(item.file)) {
      const partial = item.file + '.part';
      await run('curl', [
        '-L',
        '--fail',
        '--retry',
        '3',
        '--connect-timeout',
        '20',
        '--max-time',
        '180',
        '-sS',
        item.source.url,
        '-o',
        partial,
      ]);
      fs.renameSync(partial, item.file);
    }
    const width = Number(await run('vipsheader', ['-f', 'width', item.file]));
    const height = Number(await run('vipsheader', ['-f', 'height', item.file]));
    const bytes = fs.readFileSync(item.file);
    if (
      bytes[0] !== 0xff ||
      bytes[1] !== 0xd8 ||
      !Number.isSafeInteger(width) ||
      !Number.isSafeInteger(height) ||
      width < 1000 ||
      height < 1000
    ) {
      throw new Error(`Invalid or undersized JPEG: ${item.source.title}`);
    }
    await run('vips', ['thumbnail', item.file, item.file + '-preview.jpg', '500']);
    item.state.width = width;
    item.state.height = height;
    item.state.sha256 = createHash('sha256').update(bytes).digest('hex');
    item.state.bytes = bytes.length;
    saveJournal();
    console.log(`Staged ${item.source.title}: ${width}×${height}, ${bytes.length} bytes`);
  }
}
await Promise.all([stage(), stage()]);
if (!apply) {
  console.log('All staged images are valid JPEGs. No DB or R2 writes.');
  process.exit(0);
}

async function getImage(url, expectedWidth, expectedSha256) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
    if (response.ok && response.headers.get('content-type')?.includes('image/jpeg')) {
      const bytes = Buffer.from(await response.arrayBuffer());
      if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes.length > 1000) {
        const probe = path.join(cacheDir, `probe-${randomUUID()}.jpg`);
        fs.writeFileSync(probe, bytes);
        if (Number(await run('vipsheader', ['-f', 'width', probe])) === expectedWidth) {
          if (expectedSha256 && createHash('sha256').update(bytes).digest('hex') !== expectedSha256)
            throw new Error(`Native JPEG checksum differs: ${url}`);
          return;
        }
      }
    }
    if (attempt < 5) await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(`Mirrored image verification failed: ${url}`);
}

async function ingest(item) {
  const { source, state, file } = item;
  const iiif = `https://iiif.maparchive.vn/iiif/${state.mapId}`;
  if (!state.mirrored) {
    console.log(`Mirroring ${source.title} → ${state.mapId}`);
    await run(
      'bash',
      ['scripts/tile_map.sh', state.mapId, file],
      path.join(cacheDir, `${state.mapId}-tile.log`)
    );
    // Preserve the native JPEG and add a readable overview, beyond tile_map's
    // small thumbnails. full/max can then resolve to the actual source width.
    const overview = path.join(cacheDir, `${state.mapId}-2048.jpg`);
    await run('vips', [
      'thumbnail',
      file,
      overview,
      '2048',
      '--height',
      '1000000',
      '--size',
      'down',
    ]);
    await run('rclone', [
      'copyto',
      overview,
      `r2:vma-tiles/tiles/${state.mapId}/full/2048,/0/default.jpg`,
      '--s3-no-check-bucket',
    ]);
    await run('rclone', [
      'copyto',
      file,
      `r2:vma-tiles/tiles/${state.mapId}/full/${state.width},/0/default.jpg`,
      '--s3-no-check-bucket',
    ]);
    state.mirrored = true;
    saveJournal();
  }
  const infoResponse = await fetch(`${iiif}/info.json`, { signal: AbortSignal.timeout(30_000) });
  if (!infoResponse.ok)
    throw new Error(`IIIF info failed for ${source.title}: ${infoResponse.status}`);
  const info = await infoResponse.json();
  if (info.width !== state.width || info.height !== state.height || !info.tiles?.length)
    throw new Error(`IIIF dimensions/tiles differ for ${source.title}`);
  await getImage(`${iiif}/full/800,/0/default.jpg`, 800);
  await getImage(`${iiif}/full/2048,/0/default.jpg`, 2048);
  await getImage(`${iiif}/full/max/0/default.jpg`, state.width, state.sha256);
  const sf = info.tiles[0].scaleFactors.at(-1);
  const span = info.tiles[0].width * sf;
  const tw = Math.min(span, state.width),
    th = Math.min(span, state.height);
  const tilePath =
    span >= state.width && span >= state.height
      ? `full/${Math.ceil(state.width / sf)},${Math.ceil(state.height / sf)}`
      : `0,0,${tw},${th}/${Math.ceil(tw / sf)},`;
  await getImage(`${iiif}/${tilePath}/0/default.jpg`, Math.ceil(tw / sf));
  const verso = source.title.includes('[verso]');
  const row = {
    id: state.mapId,
    name: source.title,
    location: source.sheet_number,
    collection: series.name,
    series_id: series.id,
    sheet_number: source.sheet_number,
    year: source.year,
    date_label: source.year == null ? '196-' : String(source.year),
    edition: source.edition,
    language: 'en, vi',
    map_type: 'city_plan',
    source_type: 'r2',
    status: 'draft',
    holding_institution: 'Perry-Castañeda Library Map Collection, University of Texas at Austin',
    source_url: source.url,
    rights: null,
    description: `L909 city-map ${verso ? 'reverse-side index' : 'scan'} from PCL. ${source.note} Georeference and catalogue assertions await review.`,
    iiif_image: iiif,
    thumbnail: `${iiif}/full/800,/0/default.jpg`,
    allmaps_id: await generateId(iiif),
    is_georeferenced: false,
    extra_metadata: {
      series: 'L909',
      source_archive: 'PCL',
      source_catalogue: 'https://maps.lib.utexas.edu/maps/vietnam.html',
      scan_side: verso ? 'verso' : 'recto',
      catalogue_title: source.title,
      catalogue_assertions_reviewed: false,
      ingest_batch: 'l909-pcl-20261006',
    },
  };
  const current = await db.from('maps').select('id').eq('id', state.mapId).maybeSingle();
  if (current.error) throw current.error;
  if (!current.data) {
    const { error } = await db.from('maps').insert(row);
    if (error) throw error;
  }
  state.assetVersion ??= randomUUID();
  saveJournal();
  const image = await db
    .from('map_images')
    .select('id')
    .eq('map_id', state.mapId)
    .eq('iiif_image', iiif)
    .maybeSingle();
  if (image.error) throw image.error;
  if (!image.data) {
    const { error } = await db.from('map_images').insert({
      map_id: state.mapId,
      source_item_id: source.id,
      source_type: 'r2',
      iiif_image: iiif,
      is_primary: true,
      label: `PCL ${verso ? 'verso' : 'recto'}`,
      width: state.width,
      height: state.height,
      content_sha256: state.sha256,
      asset_version: state.assetVersion,
    });
    if (error) throw error;
  }
  state.complete = true;
  saveJournal();
  console.log(`Verified draft: ${source.title} (${state.mapId})`);
}

let ingestNext = 0;
const failures = [];
async function ingestWorker() {
  while (ingestNext < plan.length) {
    const item = plan[ingestNext++];
    try {
      await ingest(item);
    } catch (error) {
      failures.push(`${item.source.title}: ${error.message ?? JSON.stringify(error)}`);
      console.error(`FAILED ${item.source.title}: ${error.message ?? JSON.stringify(error)}`);
    }
  }
}
await Promise.all([ingestWorker(), ingestWorker()]);
if (failures.length) throw new Error(failures.join('\n'));

const result = await db
  .from('maps')
  .select('id,name,status,iiif_image')
  .eq('extra_metadata->>ingest_batch', 'l909-pcl-20261006');
if (result.error) throw result.error;
if (
  result.data.length !== 19 ||
  result.data.some((map) => map.status !== 'draft' || !map.iiif_image)
) {
  throw new Error('Final draft record count/state differs from reviewed plan');
}
const before = JSON.parse(
  fs.readFileSync(path.join(cacheDir, 'existing-maps-before.json'), 'utf8')
);
const unchanged = await db
  .from('maps')
  .select('*')
  .in(
    'id',
    before.map((map) => map.id)
  );
if (unchanged.error) throw unchanged.error;
for (const map of before) {
  if (JSON.stringify(map) !== JSON.stringify(unchanged.data.find((item) => item.id === map.id)))
    throw new Error(`Existing map changed during ingest: ${map.name}`);
}
console.log('Complete: 19 verified draft scans; the original three maps are unchanged.');
