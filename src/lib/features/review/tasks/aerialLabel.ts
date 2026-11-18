/**
 * The aerial-label task (`aerial-label-1950`): one point on a 1950 aerial, answered built, open or unsure.
 * Same frame, keys and timing as the place-link task; no proposal arm, so no blind arm.
 *
 * Keys: `b` built, `o` open, `.` unsure. `u` stays undo (the house key), so unsure cannot be `u`; `.` is
 * where the place-link plan moves its unsure too (placeLink.ts).
 */

import AerialLabelOverlay from './AerialLabelOverlay.svelte';
import AerialLabelDecision from './AerialLabelDecision.svelte';
import type { ReviewTaskDef } from './placeLink';

export const aerialLabel: ReviewTaskDef = {
  key: 'aerial-label',
  overlay: AerialLabelOverlay,
  decision: AerialLabelDecision,
  relations: [
    { key: 'b', relation: 'built', label: 'built' },
    { key: 'o', relation: 'open', label: 'open' },
    { key: '.', relation: 'unsure', label: 'unsure' },
  ],
};
