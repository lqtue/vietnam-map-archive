#!/usr/bin/env node
// File the three AMS L909 city maps as one series.
//
//   node --env-file=.env scripts/oneoff/fix_l909_series_index.mjs [--dry]
//
// AMS series L909 (Việt Nam City Maps 1:12,500, edition 2-AMS, 1968) is three
// rows in this archive — Hà Nội, Huế and Sài Gòn — and has never once appeared
// in /explore as a series. Two reasons, both in the rows rather than in the
// view:
//
//   - Sài Gòn is filed under `Vietnam Map Archive`, the archive's catch-all
//     bucket, while the other two are under `AMS L909 — Việt Nam City Maps
//     1:12,500`. `series_key()` (mig 082) is a function of `collection`, so
//     one survey was two, one of them a bucket of 36 unrelated sheets.
//   - None of the three carries `extra_metadata.sheet_number`, which is the
//     test 082 uses to tell a survey from a bucket. All three carry
//     `extra_metadata.sheet`, the city, which IS this series' sheet identifier:
//     L909 numbers nothing, it names cities, and PCL's own filenames
//     (`txu-oclc-232337961-hanoi-1968`) carry no number either.
//
// So the fix is to copy `sheet` into `sheet_number` and move one row's
// collection. Nothing about the view needs loosening: the gate is right and the
// rows were wrong, which is the whole reason 082 tests the data rather than
// keeping a list of series in the code.
//
// After this the series has three sheets and a bounds spanning Hà Nội to Sài
// Gòn — wide for a layer, and correct: a city-map series is not contiguous. It
// gets no `series_sheets` index here because nothing yet establishes how many
// cities L909 covers; without one /explore says "3 sheets" rather than
// "3 of N", which is 084's null-denominator case working as intended.

import { createClient } from '@supabase/supabase-js';

const dry = process.argv.includes('--dry');
const COLLECTION = 'AMS L909 — Việt Nam City Maps 1:12,500';

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
});

// Every row that says it is L909, wherever it is currently filed.
const { data, error } = await db
  .from('maps')
  .select('id,name,status,collection,extra_metadata')
  .eq('extra_metadata->>series', 'L909');
if (error) throw error;

const todo = [];
for (const m of data) {
  const meta = m.extra_metadata ?? {};
  // The city is the sheet. Fall back to nothing rather than guessing from the
  // name: a wrong sheet_number is worse than a missing one, because it makes
  // two cities one cell and `map_series` then counts them as one sheet.
  const sheet = typeof meta.sheet === 'string' ? meta.sheet : null;
  const wantsNumber = sheet && meta.sheet_number !== sheet;
  const wantsCollection = m.collection !== COLLECTION;
  if (!wantsNumber && !wantsCollection) continue;
  if (!sheet && !meta.sheet_number) {
    console.warn(`! ${m.name} — no extra_metadata.sheet, cannot name its cell; skipped`);
    continue;
  }
  todo.push({
    id: m.id,
    name: m.name,
    from: m.collection,
    sheet_number: meta.sheet_number ?? sheet,
    patch: {
      collection: COLLECTION,
      extra_metadata: { ...meta, sheet_number: meta.sheet_number ?? sheet },
    },
  });
}

if (!todo.length) {
  console.log('nothing to do — all three L909 rows are already filed as one numbered series');
  process.exit(0);
}

for (const t of todo)
  console.log(
    `${dry ? 'would fix' : 'fixing'}  ${t.name}\n    collection: ${t.from} -> ${COLLECTION}\n    sheet_number: ${t.sheet_number}`
  );

if (dry) process.exit(0);

for (const t of todo) {
  const { error: upErr } = await db.from('maps').update(t.patch).eq('id', t.id);
  if (upErr) throw new Error(`${t.name}: ${upErr.message}`);
}

// The point of the exercise, read back the way /explore reads it: as an
// anonymous caller. A service-key client has `auth.uid()` null, which is the
// same gate an anonymous reader passes, so this row is what the public sees.
const { data: series, error: seriesError } = await db
  .from('map_series')
  .select('key, collection, sheets, published_sheets, survey_sheets, bounds');
// `survey_sheets` is 084. Until that is pushed this select is a 400, and an
// unchecked error here prints an empty list under a confident heading — which
// reads as "the fix did nothing" when the fix worked.
if (seriesError) {
  console.log(`\nmap_series not read back: ${seriesError.message}`);
  console.log('(expected until migration 084 is pushed — the rows above are written)');
  process.exit(0);
}
console.log('\nmap_series as an anonymous reader sees it:');
for (const s of series ?? [])
  console.log(
    `  ${s.key}  ${s.sheets} sheets (${s.published_sheets} published)` +
      `${s.survey_sheets ? ` of ${s.survey_sheets} in the survey` : ''}  ${JSON.stringify(s.bounds)}`
  );
