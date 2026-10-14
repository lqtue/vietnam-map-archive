/**
 * Builds `src/lib/core/i18n/vi.ts` from the bilingual tables in
 * `work/copy/translate-vi.md`.
 *
 * Everything after the `# PENDING` heading is ignored: those are rows whose
 * English still sits inside nested markup (a sentence wrapped around a link,
 * a heading that is half a `<span>`), so the string cannot be looked up as one
 * key yet. Keeping them in the markdown preserves the translator's work;
 * keeping them out of the dictionary keeps `tests/i18n.spec.ts` honest about
 * what the app can actually render.
 *
 * Run after editing the markdown:  node scripts/gen/gen-i18n.mjs
 */
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';

const SRC = 'work/copy/translate-vi.md';
const OUT = 'src/lib/core/i18n/vi.ts';

const full = fs.readFileSync(SRC, 'utf8');
const wired = full.split(/^# PENDING/m)[0];

const pairs = new Map();
for (const line of wired.split('\n')) {
  if (!line.startsWith('|')) continue;
  const cells = line
    .split('|')
    .slice(1, -1)
    .map((c) => c.trim());
  if (cells.length !== 2) continue;
  const [en, vi] = cells;
  if (!en || !vi) continue;
  if (en === 'English' || /^-+$/.test(en)) continue;
  if (en === vi) continue; // VMA, GitHub, Studio — nothing to store
  if (pairs.has(en) && pairs.get(en) !== vi) {
    console.error('CONFLICT:', JSON.stringify(en), '→', pairs.get(en), '/', vi);
    process.exitCode = 1;
  }
  pairs.set(en, vi);
}

const esc = (s) => "'" + s.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
const body = [...pairs].map(([k, v]) => `  ${esc(k)}: ${esc(v)},`).join('\n');

fs.writeFileSync(
  OUT,
  `/**\n * Vietnamese strings, keyed by their English source.\n *\n * Generated from \`${SRC}\` by \`scripts/gen/gen-i18n.mjs\`.\n * Edit the markdown and regenerate; do not hand-edit this file.\n */\nexport const vi: Record<string, string> = {\n${body}\n};\n`
);
// Prettier over the emitted file, because the repo lints it like any other
// source. `esc()` always single-quotes, but `.prettierrc` sets singleQuote,
// which flips a string holding an apostrophe to double quotes — so a dictionary
// with one apostrophe in it fails `npm run lint` the moment it is regenerated.
// That is the friction that let this file sit 48 entries behind the markdown.
execFileSync('npx', ['prettier', '--write', OUT], { stdio: 'ignore' });

console.log(pairs.size, 'entries →', OUT);
