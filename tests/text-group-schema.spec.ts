import { expect, test } from '@playwright/test';
import { missingTextGroupColumns } from '../src/lib/core/utils/textGroupSchema';

test('only missing migration-112 columns allow the legacy reader', () => {
  expect(
    missingTextGroupColumns({
      code: '42703',
      message: 'column ocr_labels.is_text_group does not exist',
    })
  ).toBe(true);
  expect(
    missingTextGroupColumns({
      code: 'PGRST204',
      message: "Could not find the 'text_group_id' column in the schema cache",
    })
  ).toBe(true);
  expect(
    missingTextGroupColumns({ code: '42703', message: 'column text_corrected does not exist' })
  ).toBe(false);
  expect(
    missingTextGroupColumns({ code: '42501', message: 'permission denied for text_group_id' })
  ).toBe(false);
  expect(missingTextGroupColumns({ code: '', message: 'TypeError: fetch failed' })).toBe(false);
  expect(missingTextGroupColumns(null)).toBe(false);
});
