/**
 * The place-link task: one small definition, as `review_page.py` has (docs/plans/review-page-plan.md
 * §7). The shared frame reads the keys and the overlay from here; `question` comes from the task
 * row (`review_tasks`), not from this file.
 *
 * The keys are the offline page's, unchanged for the first test so the timing compares like for
 * like. Before contributors (v2) `unsure` moves to `.`, `?` shows the keys, and the See-today links
 * move to Shift+O V W, because `?` and `v` clash with the house keymap (design-system.md § Keys).
 */

import PlaceLinkOverlay from './PlaceLinkOverlay.svelte';
import type { Relation } from '../types';

export const placeLink = {
  key: 'place-link',
  overlay: PlaceLinkOverlay,
  /** Key, relation, and the words on the button. Every key has a visible button. */
  relations: [
    { key: 's', relation: 'same_building', label: 'same building' },
    { key: 'n', relation: 'same_site_new_building', label: 'same site, new building' },
    { key: 'm', relation: 'moved', label: 'moved' },
    { key: 'g', relation: 'gone', label: 'gone' },
    { key: 'x', relation: 'none', label: 'none' },
    { key: '?', relation: 'unsure', label: 'unsure' },
  ] as { key: string; relation: Relation; label: string }[],
};

export type ReviewTaskDef = typeof placeLink;

const DEFINITIONS: ReviewTaskDef[] = [placeLink];

/**
 * The definition that draws a task. A task key is a kind, or a kind and a suffix (`place-link`,
 * `place-link-2`), so a second run of the same question needs no code.
 */
export const taskFor = (key: string): ReviewTaskDef | undefined =>
  DEFINITIONS.find((d) => key === d.key || key.startsWith(`${d.key}-`));
