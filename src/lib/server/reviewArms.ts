/**
 * Arm and order for one reviewer, from a hash. No stored session.
 *
 * `hash(task seed, reviewer, item)` gives every reviewer their own fixed blind set and their own
 * fixed order, so nothing drifts between sittings and adding items does not reshuffle the old ones
 * (docs/plans/review-page-plan.md §2.4). The seed never leaves the server, so a client cannot work
 * out which items are blind.
 *
 * Differs from the offline pages on purpose: `confirm.py` draws an exact 20% with a seeded sample.
 * A hash gives about 20% (a binomial spread around it), and the share a reviewer actually met is
 * what the paper reports, counted from `proposal_shown`.
 *
 * ponytail: FNV-1a, not a cryptographic hash. The seed is secret enough for an arm assignment; use
 * a keyed hash if an arm ever becomes worth attacking.
 */

export type Arm = 'shown' | 'blind' | 'nocand';

/** FNV-1a, 32 bits, over UTF-8 bytes, as an unsigned number. */
export function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const b of new TextEncoder().encode(s)) {
    h ^= b;
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

const unit = (s: string) => fnv1a(s) / 0x1_0000_0000;

/**
 * `nocand` when the item has no proposal (nothing to hide); otherwise `blind` for a hash below
 * `blindFrac`, `shown` for the rest.
 */
export function armFor(
  seed: number,
  reviewer: string,
  itemId: string,
  blindFrac: number,
  hasProposal: boolean
): Arm {
  if (!hasProposal) return 'nocand';
  return unit(`${seed}|${reviewer}|${itemId}|arm`) < blindFrac ? 'blind' : 'shown';
}

/** Sort key for this reviewer's order; ties (a hash clash) break on the item id. */
export function orderKey(seed: number, reviewer: string, itemId: string): number {
  return fnv1a(`${seed}|${reviewer}|${itemId}|order`);
}

export function orderItems(seed: number, reviewer: string, ids: string[]): string[] {
  return [...ids].sort(
    (a, b) => orderKey(seed, reviewer, a) - orderKey(seed, reviewer, b) || (a < b ? -1 : 1)
  );
}
