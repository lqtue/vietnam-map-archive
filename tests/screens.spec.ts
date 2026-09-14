import { test, expect } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * `/screens` says it holds "everything in `src/lib/ui/`", and the card tables
 * say which selector lives in which file. Both claims are hand-maintained, and
 * both had already gone stale: the page rendered ten of seventeen components
 * while asserting all of them, and its card blurb counted "twenty … four …
 * sixteen" over a list of seven and seven.
 *
 * That is not a cosmetic slip. The page exists so that someone about to build a
 * second tab strip sees the first one — and in September 2026 there were five
 * tab strips, none of them on this page. A reference nobody can trust is worse
 * than none, because it is consulted and then believed.
 *
 * So the claims are checked rather than promised. No browser: this reads the
 * source, which is where the drift is.
 */

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const screens = readFileSync(resolve(root, 'src/routes/(editorial)/screens/+page.svelte'), 'utf8');

test('every component in src/lib/ui is named on /screens', () => {
  const components = readdirSync(resolve(root, 'src/lib/ui'))
    .filter((f) => f.endsWith('.svelte'))
    .map((f) => f.replace('.svelte', ''));

  // A component counts as covered when the page names it in a `sc-code` chip —
  // rendered from a fixture, or listed with the reason it cannot be (AuthGate
  // starts a real sign-in; SnapSheet is fixed-position and would cover the page).
  const missing = components.filter((c) => !screens.includes(`<code class="sc-code">${c}</code>`));
  expect(missing, `not named on /screens: ${missing.join(', ')}`).toEqual([]);
});

test('a card the inventory names still exists in the file it names', () => {
  // The page's own comment records this failure: before the Sept 2026 pass it
  // still advertised eight cards that earlier cleanups had deleted.
  const rows = [...screens.matchAll(/\['(\.[^']+)',\s*'([^']+\.css)'/g)].map((m) => ({
    selector: m[1],
    file: m[2],
  }));
  // A floor, not a count: the point is that the regex still matches something,
  // so a changed array shape fails loudly instead of passing with zero rows.
  // The inventory is meant to shrink — it went 14 → 9 in Sept 2026.
  expect(
    rows.length,
    'card inventory rows were not found — did the array shape change?'
  ).toBeGreaterThan(4);

  const stale = rows.filter(({ selector, file }) => {
    let css: string;
    try {
      css = readFileSync(resolve(root, 'src/styles', file), 'utf8');
    } catch {
      return true;
    }
    return !css.includes(selector);
  });
  expect(
    stale.map((r) => `${r.selector} in ${r.file}`),
    'the card inventory names a selector that is no longer there'
  ).toEqual([]);
});

test('a retired element name does not come back', () => {
  // The vocabulary is small on purpose, and it only stays small if nothing
  // quietly re-adds to it. Each of these was a whole family in September 2026:
  // five tab strips in three faces (only one of them accessible), nine button
  // families spelling four tones three different ways, and four private badges
  // that were `.badge-chip.is-sm` with a tint.
  const dead = [
    // tab strips → $lib/ui/Tabs.svelte
    'chunky-tabs',
    'phase-tabs',
    'admin-tabs',
    // buttons → .btn / .chip + is-*
    'action-btn',
    'pill-btn',
    'tool-btn',
    'ctrl-btn',
    'cmp-btn',
    'btn-primary',
    'btn-danger',
    'btn-success',
    'btn-ghost',
    'btn-outline',
    'btn-sm',
    'btn-xs',
    'btn-icon-edit',
    'btn-icon-delete',
    // badges → .badge-chip.is-sm + a chip-* tone
    'source-type-chip',
    'ocr-cat-chip',
    'essentials-pill',
  ];
  const src = ['src/lib', 'src/routes', 'src/styles'].flatMap((dir) => walk(resolve(root, dir)));

  // Three files are allowed to name them, because in all three the name is the
  // record of what it replaced rather than a use of it: the two component
  // headers, and /screens, which teaches the reader the same thing.
  const ledgers = [
    resolve(root, 'src/lib/ui/Tabs.svelte'),
    resolve(root, 'src/styles/components/buttons.css'),
    resolve(root, 'src/routes/(editorial)/screens/+page.svelte'),
  ];
  for (const name of dead) {
    const hits = src.filter(
      (f) => !ledgers.includes(f) && new RegExp(`\\b${name}\\b`).test(readFileSync(f, 'utf8'))
    );
    expect(
      hits.map((f) => f.slice(root.length + 1)),
      `${name} is back`
    ).toEqual([]);
  }
});

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = resolve(dir, e.name);
    if (e.isDirectory()) return walk(full);
    return /\.(svelte|ts|css)$/.test(e.name) ? [full] : [];
  });
}

/**
 * Every `var(--token)` a component asks for is one `tokens.css` defines.
 *
 * A CSS custom property that was never declared is not an error anywhere: the
 * declaration using it is simply dropped, and the element renders at the
 * browser's default. `gap: var(--space-sm)` becomes no gap, `padding-block:
 * var(--space-lg)` becomes no padding — the page still draws, and what you see
 * is a plausible-looking layout that is missing exactly the spacing someone
 * wrote down.
 *
 * That is what had happened across the series pages: the spacing scale is
 * numeric (`--space-2`, `--space-4`, `--space-6`), three files spelled it
 * `--space-sm/md/lg`, and fourteen declarations had been doing nothing since
 * September 2026. It only became visible when `/catalog` put one of those rows
 * on a wider page and two numbers ran together with no space between them.
 *
 * No browser, and no allowlist to maintain: the tokens are read from the files
 * that declare them.
 */
test('no stylesheet uses a custom property nothing declares', () => {
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const e of readdirSync(resolve(root, dir), { withFileTypes: true })) {
      const p = `${dir}/${e.name}`;
      if (e.isDirectory()) walk(p);
      else if (e.name.endsWith('.css') || e.name.endsWith('.svelte')) files.push(p);
    }
  };
  walk('src');

  // Declared anywhere in the tree: `tokens.css` holds the palette and the
  // scales, but a component may declare its own knob (`--card-pad`) and a
  // caller may set it. Both count as declared.
  //
  // Two declaration sites, not one. A property set from the template —
  // `style:--cat-color={…}` on an element, which is how OcrFilterBar tints a
  // chip per category and how PressPanel sizes a sparkline bar — never appears
  // as `--name:` anywhere. A checker that only knew the CSS form reported both
  // of those as undeclared, which is the failure mode this whole test exists
  // to catch, arriving as noise in the test that catches it.
  const declared = new Set<string>();
  const used = new Map<string, string[]>();
  for (const f of files) {
    const src = readFileSync(resolve(root, f), 'utf8');
    for (const m of src.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)) declared.add(m[1]);
    for (const m of src.matchAll(/\bstyle:(--[a-zA-Z0-9-]+)/g)) declared.add(m[1]);
    // Only the fallback-less form: `var(--x, 1rem)` degrades to something the
    // author chose, which is a different decision from a name that does not exist.
    for (const m of src.matchAll(/var\(\s*(--[a-zA-Z0-9-]+)\s*\)/g)) {
      if (!used.has(m[1])) used.set(m[1], []);
      used.get(m[1])!.push(f);
    }
  }

  const undeclared = [...used.entries()].filter(([name]) => !declared.has(name));
  expect(
    undeclared.map(([name, where]) => `${name} — ${[...new Set(where)].join(', ')}`),
    'These resolve to nothing, and the declaration using them is silently dropped'
  ).toEqual([]);
});
