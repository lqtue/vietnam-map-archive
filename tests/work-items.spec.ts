/**
 * Pure check: every ROADMAP item a public page names must exist.
 *
 * `/changelog` releases and `/blog` posts carry `items: [...]`, the join key
 * between what readers see and `docs/ROADMAP.md`. A renamed or mistyped item
 * would still render, so nothing else would notice. A name is accepted if it is
 * an open item or appears in backticks in `docs/roadmap-record.md` (closed work).
 */
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { releases } from '../src/routes/(editorial)/changelog/releases';
import { posts } from '../src/routes/(editorial)/blog/posts';

const open = [
  ...readFileSync('docs/ROADMAP.md', 'utf8').matchAll(/^- \[ \] \*\*`([^`]+)`\*\*/gm),
].map((m) => m[1]);
const closed = new Set(
  [...readFileSync('docs/roadmap-record.md', 'utf8').matchAll(/`([a-z0-9][a-z0-9-]*)`/g)].map(
    (m) => m[1]
  )
);

test('ROADMAP still parses into open item names', () => {
  // A format change would make the next check pass on an empty set.
  expect(open.length).toBeGreaterThan(50);
});

test('every item a release or post names is open or recorded as closed', () => {
  const named = [...releases, ...posts].flatMap((p) => (p.items ?? []).map((i) => [p, i] as const));
  expect(named.length).toBeGreaterThan(0);
  const unknown = named.filter(([, i]) => !open.includes(i) && !closed.has(i)).map(([, i]) => i);
  expect(unknown).toEqual([]);
});
