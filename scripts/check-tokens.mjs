#!/usr/bin/env node
/**
 * Fails if a component <style> block names a colour.
 *
 * The app renders on two surfaces — .surface-paper and .surface-darkroom — and
 * a component picks up whichever one its route set. A hex literal ignores that,
 * so a hardcoded #fff panel is unreadable in the darkroom and a hardcoded #111
 * label is invisible on paper. Reading a role token is the only way a component
 * can be correct on both.
 *
 * Only <style> blocks are checked. Colours handed to OpenLayers stay literal on
 * purpose: OL cannot read a CSS custom property.
 *
 * Escape hatch, for the rare literal that genuinely is not themeable:
 *   /* token-exempt: why *\/
 */
import { readFileSync } from 'node:fs';
import { globSync } from 'node:fs';

const HEX = /#[0-9a-fA-F]{3,8}\b/g;
const files = globSync('src/**/*.svelte').concat(globSync('src/styles/**/*.css'));

let bad = 0;
for (const file of files) {
  const src = readFileSync(file, 'utf8');

  // tokens.css is where the colours are allowed to live.
  if (file.endsWith('tokens.css')) continue;

  // A comment explaining which literal a token replaced is not a literal.
  const decomment = (css) => css.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, ' '));

  const blocks = file.endsWith('.css')
    ? [{ text: decomment(src), offset: 0 }]
    : [...src.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => ({
        text: decomment(m[1]),
        offset: m.index + m[0].indexOf(m[1]),
      }));

  for (const block of blocks) {
    for (const hit of block.text.matchAll(HEX)) {
      const at = block.offset + hit.index;
      const line = src.slice(0, at).split('\n').length;
      // The marker may sit a couple of lines either side: prettier explodes a
      // wrapped declaration, which pushes a trailing comment off its own line.
      const lines = src.split('\n');
      const near = lines.slice(Math.max(0, line - 4), line + 2).join('\n');
      if (near.includes('token-exempt')) continue;
      console.error(`${file}:${line}  ${hit[0]}  ->  use a role token`);
      bad++;
    }
  }
}

if (bad) {
  console.error(
    `\ncheck-tokens: ${bad} hardcoded colour${bad === 1 ? '' : 's'} in style blocks.\n` +
      `Roles: --ground --ground-raised --ink --ink-soft --rule --accent --on-accent` +
      ` --status-ok --status-warn --status-bad --scrim\n`
  );
  process.exit(1);
}
console.log(`check-tokens: ${files.length} files, no hardcoded colours in style blocks`);
