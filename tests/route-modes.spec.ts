import { expect, test } from '@playwright/test';
import { DEFAULT_ADMIN_TAB, resolveAdminTab, resolveExploreMode } from '../src/lib/core/routeModes';

test('explore only accepts its current modes and the shipped annotate alias', () => {
  expect(resolveExploreMode(null)).toBe('browse');
  expect(resolveExploreMode('annotate')).toBe('studio');
  expect(resolveExploreMode('story')).toBe('story');
  expect(resolveExploreMode('stroy')).toBeNull();
});

test('admin never resolves an unknown tab to the write-capable bulk screen', () => {
  expect(resolveAdminTab(null)).toBe(DEFAULT_ADMIN_TAB);
  expect(resolveAdminTab('nonsense')).toBe(DEFAULT_ADMIN_TAB);
  expect(resolveAdminTab('bulk')).toBe('bulk');
});
