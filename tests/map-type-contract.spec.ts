import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { MAP_TYPES, canonicalMapType } from '../src/lib/core/mapTaxonomy';

test('editor taxonomy matches the database constraint', () => {
  const sql = readFileSync('supabase/migrations/116_map_taxonomy.sql', 'utf8');
  const allowed = [...sql.match(/check \(map_type in \(([^)]+)\)/)![1].matchAll(/'([^']+)'/g)].map(
    (match) => match[1]
  );
  expect(MAP_TYPES.map((type) => type.key).sort()).toEqual(allowed.sort());
  const editor = readFileSync('src/lib/features/admin/MapEditAboutTab.svelte', 'utf8');
  expect(editor).toContain('{#each MAP_TYPES as type (type.key)}');
});

test('old catalog types resolve to the canonical types', () => {
  expect(canonicalMapType('plan')).toBe('city_plan');
  expect(canonicalMapType('regional')).toBe('general_reference');
  expect(canonicalMapType('hydrographic')).toBe('hydrographic');
  expect(canonicalMapType('')).toBeNull();
});
