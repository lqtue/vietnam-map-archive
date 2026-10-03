import { expect, test } from '@playwright/test';
import {
  pickSheetPrintingFields,
  pickSheetPrintingInsert,
} from '../src/lib/server/sheetPrintingFields';

test('verified printing requires a cited source and a human review note', () => {
  expect(() => pickSheetPrintingInsert({ review_status: 'verified', evidence: {} })).toThrow(
    /evidence source URL and review note/
  );
  expect(() =>
    pickSheetPrintingInsert({
      review_status: 'verified',
      evidence: { source_url: 'javascript:alert(1)', review_note: 'looks right' },
    })
  ).toThrow(/HTTP or HTTPS/);

  expect(
    pickSheetPrintingInsert({
      review_status: 'verified',
      evidence: {
        source_url: 'https://library.example/catalog/123',
        review_note: 'margin date matches',
      },
    })
  ).toMatchObject({ review_status: 'verified' });
});

test('empty optional fields clear cleanly while unresolved records can stay sparse', () => {
  expect(
    pickSheetPrintingFields({
      part: '',
      printing_year: '',
      evidence: {},
      review_status: 'unreviewed',
    })
  ).toMatchObject({ part: null, printing_year: null, evidence: {}, review_status: 'unreviewed' });
  expect(pickSheetPrintingInsert({ evidence: {}, part: 'assemblage' })).toMatchObject({
    evidence: {},
    part: 'assemblage',
  });
});

test('date fields reject booleans, fractions and non-numbers instead of coercing them', () => {
  expect(() => pickSheetPrintingFields({ content_year: true })).toThrow(/whole number/);
  expect(() => pickSheetPrintingFields({ printing_month: 3.5 })).toThrow(/whole number/);
  expect(() => pickSheetPrintingFields({ edition_year: 'unknown' })).toThrow(/whole number/);
});

test('a metadata-only edit preserves existing reviewed evidence', () => {
  const evidence = {
    source_url: 'https://library.example/item/1',
    review_note: 'verified from colophon',
  };
  expect(
    pickSheetPrintingFields({ printer: 'Example Press' }, { review_status: 'verified', evidence })
  ).toEqual({
    printer: 'Example Press',
  });
  expect(() =>
    pickSheetPrintingFields(
      { review_status: 'verified' },
      { review_status: 'verified', evidence: {} }
    )
  ).toThrow(/evidence source URL and review note/);
});
