// Push draft annotations to Allmaps only (no VMA write), so they open pre-filled in the editor.
//   node work/tonkin-1950/push.mjs <annotations-dir> [--apply | --update]
// --update PATCHes maps already pushed (check allmaps_drift-style first: it overwrites editor edits).
// Skips an image Allmaps already holds a map for; records new map ids in <dir>/../allmaps-ids.json.
import { readFileSync, readdirSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { generateId } from '@allmaps/id';
import { toAllmapsMap, push } from '../../scripts/lib/allmaps.mjs';

const [dir, flag] = process.argv.slice(2);
const apply = flag === '--apply';
const update = flag === '--update';
const idsPath = join(dirname(dir), 'allmaps-ids.json');
const ids = existsSync(idsPath) ? JSON.parse(readFileSync(idsPath, 'utf8')) : {};
for (const f of readdirSync(dir).filter((f) => f.endsWith('.json'))) {
  const mapId = f.replace('.json', '');
  const ann = JSON.parse(readFileSync(join(dir, f), 'utf8'));
  const iiif = ann.items[0].target.source.id;
  const imageId = await generateId(iiif);
  const res = await fetch(`https://annotations.allmaps.org/images/${imageId}`, { headers: { 'User-Agent': 'curl/8.7.1' } });
  const held = res.ok ? ((await res.json()).items ?? []).length : 0;
  if (update) {
    if (ids[mapId]) console.log(mapId, 'patched', await push(toAllmapsMap(ann), ids[mapId]));
    continue;
  }
  if (ids[mapId] || held) {
    console.log(mapId, 'skip: Allmaps already has', ids[mapId] ?? `${held} map(s) on image ${imageId}`);
    continue;
  }
  if (!apply) { console.log(mapId, 'would POST', imageId); continue; }
  ids[mapId] = await push(toAllmapsMap(ann));
  writeFileSync(idsPath, JSON.stringify(ids, null, 1));
  console.log(mapId, 'posted', ids[mapId]);
}
