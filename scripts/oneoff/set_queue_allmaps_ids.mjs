// One-off: give every not-yet-georeferenced draft the allmaps_id Allmaps will file its
// work under. "Open in Allmaps" on /contribute/georef hands the Editor `maps.iiif_image`;
// Allmaps keys the result by generateId(that url). With allmaps_id NULL nothing on our
// side can find a contributor's annotation (sync-georef only probes rows that have one).
//
// Same rule as src/routes/api/admin/maps (+ [id]): generateId over the IIIF URL with a
// trailing /info.json and slashes stripped (src/lib/core/iiif/allmapsId.ts). Every update
// is guarded with .is('allmaps_id', null), so an existing id is never overwritten.
//
//   node --env-file=.env scripts/oneoff/set_queue_allmaps_ids.mjs        # dry run
//   node --env-file=.env scripts/oneoff/set_queue_allmaps_ids.mjs --apply
import { generateId } from '@allmaps/id';
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

// Keep identical to canonicalIiifUrl in src/lib/core/iiif/allmapsId.ts.
const canonical = (url) => url.replace(/\/(info\.json)?$/, '').replace(/\/+$/, '');
const derive = (iiifImage) => generateId(canonical(iiifImage));

// Known-good pair: if this drifts, the hash is wrong and nothing may be written.
const probe = await derive('https://iiif.maparchive.vn/iiif/20ec4f9a-16bd-4895-a593-40c6ed9c9555');
if (probe !== '5b13e6b7b7303867') throw new Error(`generateId self-check failed: ${probe}`);

const apply = willApply();
const db = serviceClient();

const { data: rows, error } = await db
  .from('maps')
  .select('id, name, iiif_image')
  .eq('status', 'draft')
  .eq('is_georeferenced', false)
  .is('allmaps_id', null)
  .not('iiif_image', 'is', null)
  .order('name')
  .range(0, 4999);
if (error) throw error;

const todo = [];
for (const r of rows) todo.push({ ...r, allmaps_id: await derive(r.iiif_image) });

for (const r of todo.slice(0, 5))
  console.log(`${r.id}  ${r.name}\n  ${r.iiif_image} -> ${r.allmaps_id}`);
const dupes = todo.length - new Set(todo.map((r) => r.allmaps_id)).size;
console.log(
  `\n${todo.length} drafts to update${dupes ? `  (${dupes} duplicate ids, shared iiif_image)` : ''}`
);

if (!apply) {
  dryNotice(`It would set allmaps_id on ${todo.length} drafts.`);
  process.exit(0);
}

let written = 0;
for (const r of todo) {
  const { data, error: e } = await db
    .from('maps')
    .update({ allmaps_id: r.allmaps_id })
    .eq('id', r.id)
    .is('allmaps_id', null)
    .select('id');
  if (e) throw e;
  written += data.length;
}
console.log(`set allmaps_id on ${written} of ${todo.length} drafts`);
