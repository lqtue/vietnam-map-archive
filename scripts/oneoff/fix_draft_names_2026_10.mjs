// One-off, 2026-10-05: the four `title` findings of scripts/catalog_audit.mjs (all drafts), and
// retiring the combined 1942 Saigon-Cho Lon draft.
//
//   node --env-file=.env scripts/oneoff/fix_draft_names_2026_10.mjs          # dry run
//   node --env-file=.env scripts/oneoff/fix_draft_names_2026_10.mjs --apply
//
// Each rename names the value it expects to replace; a row that has changed since the audit is
// skipped, not overwritten. Slugs do not move on a rename (mig 088).
//
// `plan-de-saigon-cho-lon` is the whole 1942 plan georeferenced as one piece. The two public
// sheets `plan-de-cholon` and `plan-de-saigon` are its halves (their bboxes abut at lon 106.672
// and their union matches the draft within ~60 m), so the draft is redundant. It is archived, not
// deleted: mig 107 says to keep a map's identity, annotation and image rather than delete it, and
// `duplicate_of_map_id` is not usable here (it needs a shared reviewed printing, and the target is
// two maps, not one). Archived rows leave every public and catalog read.
import { createClient } from '@supabase/supabase-js';

/** @type {{slug: string, from: string, to: string}[]} */
const RENAMES = [
  { slug: 'xieng-khouang-ouest-w', from: 'Xieng Khouang ouest (W)', to: 'Xieng Khouang (W)' },
  // "Phu -My" is a typo: the L7014 sheet is "Phu My".
  { slug: 'phu-my-est-e', from: 'Phu -My est (E)', to: 'Phu My (E)' },
  { slug: 'battambang-ouest-w-1947', from: 'Battambang Ouest (W)', to: 'Battambang (W)' },
  { slug: 'battambang-est-e-1947', from: 'Battambang Est (E)', to: 'Battambang (E)' },
];

const ARCHIVE = {
  id: 'eca788e5-6780-4dca-bf23-7651a1c48aba',
  slug: 'plan-de-saigon-cho-lon',
  reason:
    'Whole 1942 plan georeferenced as one piece; superseded by its two published halves, ' +
    'plan-de-saigon and plan-de-cholon (same Gallica scan, bboxes abut and sum to this one).',
};

const apply = process.argv.includes('--apply');
const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

let changed = 0;
for (const { slug, from, to } of RENAMES) {
  const { data, error } = await db.from('maps').select('name').eq('slug', slug).maybeSingle();
  if (error) throw new Error(`${slug}: ${error.message}`);
  if (!data) {
    console.log(`MISSING  ${slug}`);
    continue;
  }
  if (data.name !== from) {
    console.log(
      `SKIP     ${slug}.name is now ${JSON.stringify(data.name)}, expected ${JSON.stringify(from)}`
    );
    continue;
  }
  console.log(
    `${apply ? 'UPDATE  ' : 'WOULD   '} ${slug}.name: ${JSON.stringify(from)} -> ${JSON.stringify(to)}`
  );
  if (!apply) continue;
  const { data: rows, error: e2 } = await db
    .from('maps')
    .update({ name: to })
    .eq('slug', slug)
    .eq('name', from)
    .select('slug');
  if (e2) throw new Error(`${slug}: ${e2.message}`);
  if (!rows.length) throw new Error(`${slug}.name: changed under us, nothing written`);
  changed++;
}

// Archive: only the exact draft row, and only while it is still a draft.
const { data: draft, error: eg } = await db
  .from('maps')
  .select('id,slug,status')
  .eq('id', ARCHIVE.id)
  .maybeSingle();
if (eg) throw new Error(`${ARCHIVE.slug}: ${eg.message}`);
if (!draft) console.log(`MISSING  ${ARCHIVE.slug}`);
else if (draft.slug !== ARCHIVE.slug || draft.status !== 'draft')
  console.log(`SKIP     ${ARCHIVE.slug} is now ${draft.slug} / ${draft.status}, expected draft`);
else {
  console.log(`${apply ? 'ARCHIVE ' : 'WOULD   '} ${ARCHIVE.slug}: draft -> archived`);
  if (apply) {
    const { data: rows, error: e3 } = await db
      .from('maps')
      .update({ status: 'archived', archive_reason: ARCHIVE.reason })
      .eq('id', ARCHIVE.id)
      .eq('status', 'draft')
      .select('slug');
    if (e3) throw new Error(`${ARCHIVE.slug}: ${e3.message}`);
    if (!rows.length) throw new Error(`${ARCHIVE.slug}: changed under us, nothing written`);
    changed++;
  }
}
console.log(apply ? `\n${changed} rows updated.` : '\nDry run. Re-run with --apply.');
