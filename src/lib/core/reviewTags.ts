/**
 * The reviewer's diagnosis vocabulary — the one copy on this side of the wire.
 *
 * Three readers have to agree on this list: the Validate sidebar that renders
 * the checkboxes, `/api/admin/footprints` that rejects an unknown one with a
 * 400, and the check constraint in migration 091. The constraint is the guard
 * that actually holds, but a client and a server spelling it separately drift
 * into a 400 that names no cause, so those two read from here.
 *
 * Adding a tag is therefore two edits, not three: this file and a migration.
 */

export const REVIEW_TAGS = [
  ['boundary_too_wide', 'Boundary too wide'],
  ['boundary_too_small', 'Boundary too small'],
  ['needs_split', 'Needs split'],
  ['needs_merge', 'Needs merge'],
  ['wrong_class', 'Wrong class'],
  ['text_or_ornament', 'Text / ornament'],
  ['water_land_confusion', 'Water / land'],
  ['false_positive', 'False positive'],
  ['missed_neighbour', 'Missed neighbour'],
  ['uncertain', 'Uncertain'],
] as const satisfies readonly (readonly [string, string])[];

export type ReviewTag = (typeof REVIEW_TAGS)[number][0];

const VALUES: ReadonlySet<string> = new Set(REVIEW_TAGS.map(([value]) => value));

export function isReviewTag(value: unknown): value is ReviewTag {
  return typeof value === 'string' && VALUES.has(value);
}

/** Matches the `review_note` length the column and the textarea both cap at. */
export const REVIEW_NOTE_MAX = 2000;
