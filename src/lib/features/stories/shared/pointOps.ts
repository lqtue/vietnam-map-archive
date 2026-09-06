/**
 * pointOps.ts — pure point CRUD over a `Story`.
 *
 * Every operation returns a NEW story (never mutates) and re-stamps
 * `updatedAt`, so callers can assign the result straight back into a reactive
 * variable or a store. Both consumers use these: `/explore?mode=story`'s editor handlers
 * and `storyStore`'s library methods.
 */
import type { PointChallenge, Story, StoryPoint } from './types';

/** A blank guided story owned by `authorId`. */
export function createStoryDraft(
  authorId: string,
  title = 'Untitled Story',
  description = ''
): Story {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    title,
    description,
    mode: 'guided',
    points: [],
    createdAt: now,
    updatedAt: now,
    status: 'draft',
    authorId,
  };
}

export interface NewPointOptions {
  /** Explicit id — defaults to a fresh UUID. */
  id?: string;
  /** Display title — defaults to `Point <order + 1>`. */
  title?: string;
  /** Metres, default 10. */
  triggerRadius?: number;
  challenge?: PointChallenge;
  /** `maps.id` UUID of the historical overlay to pin to this point. */
  overlayMapId?: string;
}

/** Build a story point. Defaults match the original storyStore.addPoint(). */
export function createPoint(
  order: number,
  coordinates: [number, number],
  opts: NewPointOptions = {}
): StoryPoint {
  return {
    id: opts.id ?? crypto.randomUUID(),
    order,
    title: opts.title ?? `Point ${order + 1}`,
    description: '',
    coordinates,
    triggerRadius: opts.triggerRadius ?? 10,
    interaction: 'proximity',
    challenge: opts.challenge ?? { type: 'reach', triggerRadius: 10 },
    overlayMapId: opts.overlayMapId,
  };
}

/** Renumber `order` to match array position. */
function reindex(points: StoryPoint[]): StoryPoint[] {
  return points.map((p, i) => ({ ...p, order: i }));
}

function withPoints(story: Story, points: StoryPoint[]): Story {
  return { ...story, points, updatedAt: Date.now() };
}

/** Append a point. `order` is left as-is (createPoint already set it). */
export function addPoint(story: Story, point: StoryPoint): Story {
  return withPoints(story, [...story.points, point]);
}

/** Patch one point in place. Order is untouched. */
export function updatePoint(story: Story, pointId: string, updates: Partial<StoryPoint>): Story {
  return withPoints(
    story,
    story.points.map((p) => (p.id === pointId ? { ...p, ...updates } : p))
  );
}

/** Drop a point and renumber the rest. */
export function removePoint(story: Story, pointId: string): Story {
  return withPoints(story, reindex(story.points.filter((p) => p.id !== pointId)));
}

/** Move a point from one index to another and renumber. */
export function reorderPoints(story: Story, from: number, to: number): Story {
  const points = [...story.points];
  const [moved] = points.splice(from, 1);
  points.splice(to, 0, moved);
  return withPoints(story, reindex(points));
}

/** Undo the last placement: drop the trailing point. No-op when empty. */
export function undoLastPoint(story: Story): Story {
  if (!story.points.length) return story;
  return withPoints(story, reindex(story.points.slice(0, -1)));
}
