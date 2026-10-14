import { expect, test } from '@playwright/test';
import {
  REVIEW_VOCABULARY,
  isDecision,
  reviewLabel,
  reviewWord,
  type ReviewTable,
} from '../src/lib/core/review/status';
import type { OcrStatus } from '../src/lib/features/contribute/shared/ocrApi';
import type { StoryStatus } from '../src/lib/features/stories/shared/types';
import type { FootprintSubmission } from '../src/lib/data/maps/footprintTypes';
import type { TriageState } from '../src/lib/data/maps/triageTypes';

/**
 * Pure checks for the review words. A wrong row here does not look like a bug: it shows a rejected
 * footprint as "Approved", or a machine's guess as a person's decision, and the page reads fine.
 */

// Compile-time: every status the app's own types allow is either mapped or left out on purpose.
// `npm run check` fails here if a type gains a status this module has not heard of.
type Known<T, K extends ReviewTable> = T extends keyof (typeof REVIEW_VOCABULARY)[K] ? never : T;
const _ocr: Known<OcrStatus, 'ocr'> extends never ? true : false = true;
const _stories: Known<StoryStatus, 'stories'> extends never ? true : false = true;
const _footprints: Known<FootprintSubmission['status'], 'footprints'> extends never ? true : false =
  true;
// Triage: two of the four states carry no proposal yet, so they are not in the table.
const _triage: Known<Exclude<TriageState, 'needs_crop' | 'needs_layout'>, 'triage'> extends never
  ? true
  : false = true;
void [_ocr, _stories, _footprints, _triage];

test('OCR: the database says validated, the house says approved', () => {
  expect(reviewWord('ocr', 'validated')).toBe('approved');
  expect(reviewWord('ocr', 'rejected')).toBe('rejected');
  expect(reviewWord('ocr', 'pending')).toBe('proposed'); // raw from the model, no person yet
});

test('footprints: SAM2 output is proposed, a contributor submission is pending', () => {
  expect(reviewWord('footprints', 'needs_review')).toBe('proposed');
  expect(reviewWord('footprints', 'submitted')).toBe('pending');
  expect(reviewWord('footprints', 'draft')).toBe('pending');
  expect(reviewWord('footprints', 'approved')).toBe('approved');
  expect(reviewWord('footprints', 'rejected')).toBe('rejected');
});

test('scout: a candidate is a proposal; ingested is approved and done', () => {
  expect(reviewWord('scout', 'pending')).toBe('proposed');
  expect(reviewWord('scout', 'approved')).toBe('approved');
  expect(reviewWord('scout', 'rejected')).toBe('rejected');
  expect(reviewWord('scout', 'ingested')).toBe('approved');
  expect(reviewLabel('scout', 'ingested')).toBe('Approved and ingested');
});

test('stories: draft and submitted are both undecided', () => {
  expect(reviewWord('stories', 'draft')).toBe('pending');
  expect(reviewWord('stories', 'submitted')).toBe('pending');
  expect(reviewWord('stories', 'approved')).toBe('approved');
  expect(reviewWord('stories', 'rejected')).toBe('rejected');
});

test('triage: a proposed crop is proposed; an accepted one is approved', () => {
  expect(reviewWord('triage', 'proposed')).toBe('proposed');
  expect(reviewWord('triage', 'ready')).toBe('approved');
  expect(reviewLabel('triage', 'ready')).toBe('Approved');
});

test('a word the table does not use gives null, never a guess', () => {
  expect(reviewWord('ocr', 'approved')).toBeNull(); // OCR says validated
  expect(reviewWord('stories', 'needs_review')).toBeNull();
  expect(reviewWord('triage', 'needs_layout')).toBeNull();
  expect(reviewWord('ocr', null)).toBeNull();
  expect(reviewWord('ocr', undefined)).toBeNull();
  expect(reviewWord('ocr', 'constructor')).toBeNull(); // not an inherited property
  expect(reviewLabel('ocr', 'nope')).toBeNull();
});

test('every mapped status has a word and a label, and only the four house words appear', () => {
  const words = new Set(['proposed', 'pending', 'approved', 'rejected']);
  for (const table of Object.keys(REVIEW_VOCABULARY) as ReviewTable[]) {
    for (const status of Object.keys(REVIEW_VOCABULARY[table])) {
      expect(words.has(reviewWord(table, status) ?? ''), `${table}.${status}`).toBe(true);
      expect(reviewLabel(table, status), `${table}.${status}`).toBeTruthy();
    }
  }
});

test('only approved and rejected are a person decision', () => {
  expect(isDecision('approved')).toBe(true);
  expect(isDecision('rejected')).toBe(true);
  expect(isDecision('pending')).toBe(false);
  expect(isDecision('proposed')).toBe(false);
});
