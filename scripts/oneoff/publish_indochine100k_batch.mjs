// One-off: flip this session's 23 source-reviewed indochine100k sheets from
// draft to public, after `annotate --apply` wrote their draft annotations.
// See docs/journals/260930-series561-handoff.md for how each was verified.
//
//   node --env-file=.env scripts/oneoff/publish_indochine100k_batch.mjs        # dry run
//   node --env-file=.env scripts/oneoff/publish_indochine100k_batch.mjs --apply
import { serviceClient } from '../lib/db.mjs';
import { willApply, dryNotice } from '../lib/cli.mjs';

const IDS = [
  ['04f35f4f-b19a-4992-bfc7-d1da75a9ddba', 'Phan Thiet (W)'],
  ['1ce2d961-4147-44eb-964c-9a7f64ea48d4', 'Muong-Tè (E)'],
  ['1f025a9f-ea9e-4816-ad35-edfba60bf518', 'Tri Binh (W)'],
  ['283ae0d8-dca7-4a2d-a86e-1e56dc08527e', 'Thanh Hoa (E)'],
  ['3d0a6cca-5ca3-4ceb-9334-5374d4d2afb4', 'Phan Rang (W)'],
  ['48584dae-d4e3-4821-82a1-bab588ec3dd2', 'Quang Ngai'],
  ['5300b1fc-7b90-4c8d-a800-5f369bea96ca', 'Lang Son (E)'],
  ['559ba082-a861-45a8-bbff-e0285f727bd9', 'Mon-Cay (E)'],
  ['65366fa5-092a-4225-a576-69e83bf4c647', 'Phu Diên Châu (E)'],
  ['65559440-3d12-4cfe-9d52-9e872564f3bd', 'Muong Ou Tay (W)'],
  ['6bdd9ab8-22dd-460d-b511-0a29d5dd843f', 'Bun-Tai (E)'],
  ['7bf1330c-2cf2-4974-9daa-dded9ed72d00', 'Söng Cau (E)'],
  ['8289d9a6-6780-4f1e-8ead-7f9f137d6ada', 'Ha-Lang (W)'],
  ['99adde4f-9d56-4a66-b186-6c8e81b63d39', 'Vinh (E)'],
  ['a387ff3f-05c4-4d46-8470-079323555c40', 'Lai Châu (E)'],
  ['a8039626-c205-4a4d-a136-87acb33c2fc8', 'Than-Poun (E)'],
  ['ba3f38a6-78ed-49d6-a656-8390961cab3b', 'Qui Nhon (E)'],
  ['c19c68a6-5ce8-4b74-86ec-9272f0c98a21', 'Phan Rang (E)'],
  ['dcfb2452-b976-4092-bddb-8c9e04300db3', 'Tu Lê (E)'],
  ['e8b02c15-5e15-4bc5-bf99-b5d4e2c008e2', 'Nha Trang (E)'],
  ['edb34855-cc39-4b9b-83cd-113f5aafb505', 'Vientiane Ban Keun (E)'],
  ['edd8be90-fa2d-422f-aa46-cbc1f6c657ac', 'Phan Thiet (E)'],
  ['f9fc556b-8311-4e0a-8f72-fd5801b13ef1', 'Quan-Ba (E)'],
];

const apply = willApply();
if (!apply) dryNotice();

const db = serviceClient();
const { data, error } = await db
  .from('maps')
  .select('id, name, status, is_georeferenced')
  .in(
    'id',
    IDS.map(([id]) => id)
  );
if (error) throw error;

const byId = new Map(data.map((r) => [r.id, r]));
for (const [id, name] of IDS) {
  const row = byId.get(id);
  if (!row) {
    console.log(`MISSING from maps table: ${id} (${name})`);
    continue;
  }
  console.log(
    `${row.status.padEnd(8)} -> public  ${name}  (georeferenced=${row.is_georeferenced})`
  );
}

if (!apply) process.exit(0);

const { error: updateError } = await db
  .from('maps')
  .update({ status: 'public' })
  .in(
    'id',
    IDS.map(([id]) => id)
  );
if (updateError) throw updateError;
console.log(`\n${IDS.length} sheets set to public.`);
