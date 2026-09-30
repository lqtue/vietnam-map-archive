// One-off: fix annotation_url on the 23 sheets `annotate --apply` published
// on 2026-09-30. It wrote a raw Supabase storage URL
// (.../storage/v1/object/public/annotations/<id>.json), which 400s -- that
// bucket has no working public path. Every sheet published before this one
// uses the app's own /api/maps/<id>/annotation route, which serves the same
// bucket through the service-role client. This makes these 23 match.
//
//   node --env-file=.env scripts/oneoff/fix_indochine100k_annotation_urls.mjs        # dry run
//   node --env-file=.env scripts/oneoff/fix_indochine100k_annotation_urls.mjs --apply
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const IDS = [
  '04f35f4f-b19a-4992-bfc7-d1da75a9ddba',
  '1ce2d961-4147-44eb-964c-9a7f64ea48d4',
  '1f025a9f-ea9e-4816-ad35-edfba60bf518',
  '283ae0d8-dca7-4a2d-a86e-1e56dc08527e',
  '3d0a6cca-5ca3-4ceb-9334-5374d4d2afb4',
  '48584dae-d4e3-4821-82a1-bab588ec3dd2',
  '5300b1fc-7b90-4c8d-a800-5f369bea96ca',
  '559ba082-a861-45a8-bbff-e0285f727bd9',
  '65366fa5-092a-4225-a576-69e83bf4c647',
  '65559440-3d12-4cfe-9d52-9e872564f3bd',
  '6bdd9ab8-22dd-460d-b511-0a29d5dd843f',
  '7bf1330c-2cf2-4974-9daa-dded9ed72d00',
  '8289d9a6-6780-4f1e-8ead-7f9f137d6ada',
  '99adde4f-9d56-4a66-b186-6c8e81b63d39',
  'a387ff3f-05c4-4d46-8470-079323555c40',
  'a8039626-c205-4a4d-a136-87acb33c2fc8',
  'ba3f38a6-78ed-49d6-a656-8390961cab3b',
  'c19c68a6-5ce8-4b74-86ec-9272f0c98a21',
  'dcfb2452-b976-4092-bddb-8c9e04300db3',
  'e8b02c15-5e15-4bc5-bf99-b5d4e2c008e2',
  'edb34855-cc39-4b9b-83cd-113f5aafb505',
  'edd8be90-fa2d-422f-aa46-cbc1f6c657ac',
  'f9fc556b-8311-4e0a-8f72-fd5801b13ef1',
];

const apply = willApply();
const db = serviceClient();

const { data, error } = await db.from('maps').select('id, name, annotation_url').in('id', IDS);
if (error) throw error;

for (const row of data) {
  const wanted = `https://maparchive.vn/api/maps/${row.id}/annotation`;
  console.log(`${row.name}\n  was: ${row.annotation_url}\n  ->:  ${wanted}`);
}

if (!apply) {
  dryNotice(`It would fix annotation_url on ${data.length} sheets.`);
  process.exit(0);
}

for (const row of data) {
  const { error: updateError } = await db
    .from('maps')
    .update({ annotation_url: `https://maparchive.vn/api/maps/${row.id}/annotation` })
    .eq('id', row.id);
  if (updateError) throw updateError;
}
console.log(`\nfixed ${data.length} sheets`);
