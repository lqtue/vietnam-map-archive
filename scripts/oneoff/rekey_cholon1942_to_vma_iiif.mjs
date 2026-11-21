// Re-key Plan de Cholon 1942 (map 8c605819) to the Allmaps annotation filed under VMA's own IIIF image,
// so the viewer and "fix on Allmaps" no longer depend on Gallica (2026-11-21, Tuệ).
// The new annotation (59 junction GCPs, polynomial order 1) lives at
// https://annotations.allmaps.org/images/1d6dd4ad4de602a0 ; the Gallica-keyed one stays as a fallback.
//
//   node --env-file=.env scripts/oneoff/rekey_cholon1942_to_vma_iiif.mjs            # dry run (read only)
//   node --env-file=.env scripts/oneoff/rekey_cholon1942_to_vma_iiif.mjs --apply

import { createClient } from '@supabase/supabase-js';
import { generateId } from '@allmaps/id';

const apply = process.argv.includes('--apply');
const MAP_ID = '8c605819-a8c3-4b2f-aa4a-6fad12893eab';
const VMA_IMAGE = 'https://iiif.maparchive.vn/iiif/8c605819-a8c3-4b2f-aa4a-6fad12893eab';
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

const newId = await generateId(VMA_IMAGE);
const { data: map, error } = await db.from('maps').select('id, slug, allmaps_id, annotation_url').eq('id', MAP_ID).single();
if (error) throw error;
const { data: imgs, error: e2 } = await db.from('map_images').select('*').eq('map_id', MAP_ID);
if (e2) throw e2;
console.log('map', { slug: map.slug, allmaps_id: map.allmaps_id, annotation_url: map.annotation_url });
console.log('new allmaps_id', newId);
for (const s of imgs) {
  const h = s.iiif_image ? await generateId(s.iiif_image.replace(/\/info\.json$/, '')) : null;
  console.log('source', { source_type: s.source_type, label: s.label, iiif_image: s.iiif_image, hash: h, matches_new: h === newId });
}
const live = await fetch(`https://annotations.allmaps.org/images/${newId}`);
console.log('annotation on Allmaps', live.status);
if (!imgs.some((s) => s.iiif_image && s.iiif_image.replace(/\/info\.json$/, '') === VMA_IMAGE))
  console.log('WARNING: no map_images row has the VMA image URL; verifiedEditorSourceId() would not find it');
if (live.status !== 200) throw new Error('annotation not found on Allmaps; not applying');

if (apply) {
  const patch = { allmaps_id: newId };
  if (map.annotation_url) console.log('NOTE: annotation_url is set and takes precedence in mapBounds; left unchanged:', map.annotation_url);
  const { error: e3 } = await db.from('maps').update(patch).eq('id', MAP_ID);
  if (e3) throw e3;
  console.log('applied', patch, 'previous allmaps_id', map.allmaps_id);
} else console.log('dry run: nothing written');
