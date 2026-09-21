import { createClient } from '@supabase/supabase-js';

// Combines the three still-unrun fixes from the 2026-09-21 catalog_audit.mjs
// pass (fix_pcl_spelling.mjs and fix_provenance_gaps.mjs already ran). Each
// runs independently and prints its own result; one failing does not stop
// the others, so the run summary at the end shows exactly what landed.

const db = createClient(process.env.PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false }
});

const steps = [
  {
    name: 'cochinchine-francaise year',
    note:
      "BnF's catalogue record (ark:/12148/cb310533394) states this edition was " +
      'published Paris: Berger-Levrault, 1888 — matching year_label exactly. ' +
      '1881 appears nowhere in that record or the related author record.',
    run: () =>
      db
        .from('maps')
        .update({ year: 1888 })
        .eq('slug', 'cochinchine-francaise')
        .select('slug,year,year_label')
  },
  {
    name: 'map-of-imperial-city-of-hue provenance',
    note:
      'CAVEAT: traced to the Nôm Preservation Foundation digitization of Đại ' +
      'Nam nhất thống chí, "Kinh Sư" chapter, sourced from the National ' +
      'Library of Vietnam (R.3504) — confirmed same book/chapter via the ' +
      'preface, but the specific plate was NOT pixel-matched against the scan ' +
      '(network timeouts cut that check short). "Right book, right chapter" ' +
      'confidence, not a verified match.',
    run: () =>
      db
        .from('maps')
        .update({
          holding_institution: 'National Library of Vietnam (Thư viện Quốc gia Việt Nam)',
          source_url: 'https://lib.nomfoundation.org/collection/1/volume/168/'
        })
        .eq('slug', 'map-of-imperial-city-of-hue')
        .select('slug,holding_institution,source_url')
  },
  {
    name: 'sai-gon-viet-nam-city-maps-1-12-500 holding institution',
    note:
      'Identified as Series L909, Edition 2-AMS (29th Engineer Battalion) — ' +
      "matches this row's own dc_description and the user's own PCL lookup. " +
      "PCL's site blocked every fetch attempt from this session, so " +
      'source_url is left as the archive.org mirror rather than guess a PCL ' +
      'page URL.',
    run: () =>
      db
        .from('maps')
        .update({
          holding_institution: 'Perry-Castañeda Library Map Collection, University of Texas at Austin'
        })
        .eq('slug', 'sai-gon-viet-nam-city-maps-1-12-500')
        .select('slug,holding_institution,source_url')
  }
];

const results = [];
for (const step of steps) {
  console.log(`\n--- ${step.name} ---`);
  if (step.note) console.log(`note: ${step.note}`);
  const { data, error } = await step.run();
  if (error) {
    console.log(`FAILED: ${error.message}`);
    results.push({ name: step.name, ok: false, error: error.message });
    continue;
  }
  console.log(JSON.stringify(data, null, 2));
  results.push({ name: step.name, ok: true, row: data[0] });
}

console.log('\n=== summary ===');
for (const r of results) console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${r.name}`);
if (results.some((r) => !r.ok)) process.exitCode = 1;
