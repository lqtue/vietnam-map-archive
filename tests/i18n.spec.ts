import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { vi } from '../src/lib/core/i18n/vi';

/**
 * The dictionary is keyed by the English source string, which is what makes a
 * missing translation render as English rather than as `home.hero.title`. The
 * cost of that choice is that editing an English string silently orphans its
 * Vietnamese one — nothing throws, the page just quietly goes back to English.
 * These are the checks that make that loud.
 */

function svelteFiles(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) svelteFiles(p, out);
    else if (e.name.endsWith('.svelte')) out.push(p);
  }
  return out;
}

/** Every `$t('…')` / `tr('…')` key that appears anywhere in the source. */
function usedKeys(): Map<string, string[]> {
  const keys = new Map<string, string[]>();
  for (const f of svelteFiles('src')) {
    const src = readFileSync(f, 'utf8');
    // Both quote styles. `.prettierrc` sets singleQuote, which makes Prettier
    // flip a string to DOUBLE quotes when its content holds an apostrophe — so
    // a single-quote-only regex is blind to exactly the strings most likely to
    // be prose. Two of them sat translated-but-English on production because
    // this extractor could not see the call sites and reported the keys unused.
    for (const m of src.matchAll(/\$?\bt[r]?\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")/g)) {
      const key = m[1] !== undefined ? m[1].replace(/\\'/g, "'") : m[2].replace(/\\"/g, '"');
      if (!keys.has(key)) keys.set(key, []);
      keys.get(key)!.push(f);
    }
  }
  return keys;
}

test('every translated key is still called from somewhere', () => {
  const used = usedKeys();
  const orphans = Object.keys(vi).filter((k) => !used.has(k));
  expect(
    orphans,
    `Translated but no longer used — the English copy changed, or the string was deleted.\n` +
      `Fix the English side in work/copy/translate-vi.md, then: node scripts/gen/gen-i18n.mjs\n` +
      orphans.map((o) => `  ${JSON.stringify(o)}`).join('\n')
  ).toEqual([]);
});

test('placeholders match between a key and its translation', () => {
  const bad: string[] = [];
  for (const [en, viText] of Object.entries(vi)) {
    const left = [...en.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    const right = [...viText.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    if (left.join(',') !== right.join(',')) {
      bad.push(`${JSON.stringify(en)} has {${left}} but the Vietnamese has {${right}}`);
    }
  }
  expect(
    bad,
    `A dropped placeholder renders a blank where a count should be:\n${bad.join('\n')}`
  ).toEqual([]);
});

test('a key never carries the same placeholder twice', () => {
  // `interpolate` fills every occurrence from one value, so two different
  // numbers under one {N} would print the first one twice.
  const bad: string[] = [];
  for (const en of Object.keys(vi)) {
    const names = [...en.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
    if (new Set(names).size !== names.length) bad.push(en);
  }
  expect(bad, `Give the second one its own name ({M}, {from}, {to}):\n${bad.join('\n')}`).toEqual(
    []
  );
});

test('a called key that is missing from the dictionary is English on purpose', () => {
  // Not a failure — untranslated is the designed fallback. This asserts the
  // count does not creep: raise it deliberately, or translate the string.
  const used = usedKeys();
  const missing = [...used.keys()].filter((k) => !(k in vi));
  expect(
    missing.length,
    `Untranslated keys:\n${missing.map((m) => `  ${m}`).join('\n')}`
  ).toBeLessThanOrEqual(0);
});
