#!/usr/bin/env node
// Merge the duplicate `maps.location` spellings.
//
//   node --env-file=.env scripts/oneoff/normalize_map_locations.mjs            # dry run
//   node --env-file=.env scripts/oneoff/normalize_map_locations.mjs --apply
//
// This used to write unless you passed --dry. Nothing in scripts/ writes
// without --apply now.
//
// `maps.location` is a free-text catalogue key, and /about prints one entry per
// distinct value. That was three values and read fine; the L7014 city sheets
// took it to 29, and two of the new ones were cities the archive already had
// under a different spelling:
//
//   'Saigon' -> 'Saigon-HCMC'   (22 rows already; the key /about maps to "Saigon")
//   'Hue'    -> 'Huế'           (10 rows already)
//
// So the page said "Saigon 22 … Saigon 1" and "Huế 9 … Hue 1", which reads as
// four places and is two. The duplicates were both introduced this week, by the
// L7014 city-sheet ingest, which typed the sheet's own ASCII title into the
// column instead of resolving it to the catalogue's existing key.
//
// The rest of the 29 are NOT duplicates and are deliberately left alone. Most
// L7014 sheets are named for somewhere that is not a city — Bach Ma, Thon Trung
// Kien, Nong Truong Nam Dong — and one sheet per place is the true count.
//
// The targets are the spellings with rows behind them, not the "correct" ones:
// `Saigon-HCMC` is a key rather than a name, and moving 22 rows to make one row
// prettier would break every link that filters on it.
//
// ponytail: no constraint or trigger to stop this recurring. Two rows in one
// ingest is not a pattern yet, and a CHECK over a free-text column that holds
// 27 legitimate values would be a list to maintain rather than a rule. If a
// third spelling turns up, the fix is a gazetteer FK, not a longer list.

import { serviceClient } from '../lib/db.mjs';
import { willApply } from '../lib/cli.mjs';

const dry = !willApply();

/** from -> to. Both sides verified present in the corpus before writing. */
const MERGES = [
  ['Saigon', 'Saigon-HCMC'],
  ['Hue', 'Huế'],
];

const db = serviceClient();

let moved = 0;

for (const [from, to] of MERGES) {
  const { data: rows, error: readErr } = await db
    .from('maps')
    .select('id, name, location')
    .eq('location', from);
  if (readErr) throw readErr;

  if (!rows.length) {
    console.log(`${from} -> ${to}: nothing to move`);
    continue;
  }

  // The destination has to exist already, or this is a rename rather than a
  // merge and the wrong spelling may be the one that survives.
  const { count, error: destErr } = await db
    .from('maps')
    .select('id', { count: 'exact', head: true })
    .eq('location', to);
  if (destErr) throw destErr;
  if (!count) throw new Error(`${to} has no rows — refusing to invent a location key`);

  for (const r of rows) console.log(`  ${r.id}  ${r.name}`);
  console.log(`${from} (${rows.length}) -> ${to} (${count} already)`);

  if (dry) continue;

  const { error } = await db
    .from('maps')
    .update({ location: to })
    .in(
      'id',
      rows.map((r) => r.id)
    );
  if (error) throw error;
  moved += rows.length;
}

// Read the column back rather than trusting the writes: this is the number
// /about prints, and it is the only thing that says the merge worked.
const { data: after, error } = await db.from('maps').select('location').not('location', 'is', null);
if (error) throw error;
const distinct = new Set(after.map((r) => r.location));
console.log(
  `${dry ? 'dry run — ' : ''}moved ${moved} row(s); ${distinct.size} distinct locations remain` +
    (dry ? ' — re-run with --apply' : '')
);
for (const [from] of MERGES) {
  if (distinct.has(from)) console.error(`STILL PRESENT: ${from}`);
}
