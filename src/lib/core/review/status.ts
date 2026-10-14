/**
 * status.ts — the house words for review, and how each table's own words map onto them.
 *
 * A person's decision has three words: `pending`, `approved`, `rejected`. A machine's output is
 * `proposed` until a person decides. The database columns keep their old words (renaming them is
 * a migration for no gain); this module is the one place that says what each old word means, so a
 * page can show "Approved" for an OCR row that the database calls `validated`.
 *
 *   proposed  a machine made it; no person has looked
 *   pending   it is not decided yet and it is not a bare machine output (a draft, a submission)
 *   approved  a person said yes
 *   rejected  a person said no
 *
 * Verified 2026-10-14 against: OCR `set_extraction_status` (mig 112); footprints check (mig 055);
 * scout `scout_candidates` check (mig 045); stories check (mig 059); triage `triageState`
 * (`data/maps/triageTypes.ts`), which has no column — it reads `validated_at`.
 * `tests/review-status.spec.ts` fails to compile if one of those TypeScript types drifts.
 *
 * Labels are English source strings: pass them through `$t(…)` at the call site.
 */

export type ReviewWord = 'proposed' | 'pending' | 'approved' | 'rejected';

/** A person's decision, as opposed to a state waiting for one. */
export const isDecision = (w: ReviewWord): w is 'approved' | 'rejected' =>
  w === 'approved' || w === 'rejected';

type Entry = readonly [word: ReviewWord, label: string];

const OCR = {
  pending: ['proposed', 'Proposed'], // raw from the model
  validated: ['approved', 'Approved'],
  rejected: ['rejected', 'Rejected'],
} as const satisfies Record<string, Entry>;

const FOOTPRINTS = {
  needs_review: ['proposed', 'Proposed'], // SAM2 output enters here
  submitted: ['pending', 'Waiting for review'], // a contributor drew it
  draft: ['pending', 'Draft'],
  approved: ['approved', 'Approved'],
  rejected: ['rejected', 'Rejected'],
} as const satisfies Record<string, Entry>;

const SCOUT = {
  pending: ['proposed', 'Proposed'], // the scout script found it
  approved: ['approved', 'Approved'],
  rejected: ['rejected', 'Rejected'],
  ingested: ['approved', 'Approved and ingested'],
} as const satisfies Record<string, Entry>;

const STORIES = {
  draft: ['pending', 'Draft'],
  submitted: ['pending', 'Waiting for review'],
  approved: ['approved', 'Approved'],
  rejected: ['rejected', 'Rejected'],
} as const satisfies Record<string, Entry>;

/** `triageState` values that carry a proposal; `needs_crop` and `needs_layout` have none yet. */
const TRIAGE = {
  proposed: ['proposed', 'Proposed'],
  ready: ['approved', 'Approved'], // a person accepted the crop (`validated_at` is set)
} as const satisfies Record<string, Entry>;

export const REVIEW_VOCABULARY = {
  ocr: OCR,
  footprints: FOOTPRINTS,
  scout: SCOUT,
  stories: STORIES,
  triage: TRIAGE,
} as const;

export type ReviewTable = keyof typeof REVIEW_VOCABULARY;

function entry(table: ReviewTable, status: string | null | undefined): Entry | null {
  const vocab: Record<string, Entry> = REVIEW_VOCABULARY[table];
  return status != null && Object.hasOwn(vocab, status) ? vocab[status] : null;
}

/** The house word for a table's own status, or `null` for a word the table does not use. */
export function reviewWord(
  table: ReviewTable,
  status: string | null | undefined
): ReviewWord | null {
  return entry(table, status)?.[0] ?? null;
}

/** The display label (English; run it through `$t`), or `null` for an unknown status. */
export function reviewLabel(table: ReviewTable, status: string | null | undefined): string | null {
  return entry(table, status)?.[1] ?? null;
}
