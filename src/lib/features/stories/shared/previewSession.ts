/**
 * previewSession.ts — the "play my draft inside the editor" lifecycle.
 *
 * `/explore?mode=story` runs the real `StoryPlayback` component against a throwaway
 * `StoryProgress` that never touches the player store. This module owns that
 * throwaway progress; framing the map is the caller's job (it already goes
 * through `applyStoryPoint`).
 */
import type { Story, StoryProgress } from './types';

export interface PreviewSession {
  active: boolean;
  progress: StoryProgress | null;
}

export const CLOSED_PREVIEW: PreviewSession = { active: false, progress: null };

/**
 * Start a preview at the first point. Returns `CLOSED_PREVIEW` when there is
 * nothing to play, so the caller can assign the result unconditionally.
 */
export function startPreview(story: Story | null): PreviewSession {
  if (!story || story.points.length === 0) return CLOSED_PREVIEW;
  return {
    active: true,
    progress: {
      storyId: story.id,
      currentPointIndex: 0,
      completedPoints: [],
      startedAt: Date.now(),
    },
  };
}

/** Move the preview cursor to `index`. */
export function navigatePreview(session: PreviewSession, index: number): PreviewSession {
  if (!session.progress) return session;
  return { ...session, progress: { ...session.progress, currentPointIndex: index } };
}

/** Mark a point complete and step the cursor, clamped to the end of the story. */
export function completePreviewPoint(
  session: PreviewSession,
  story: Story | null,
  pointId: string
): PreviewSession {
  if (!session.progress || !story) return session;
  const done = new Set(session.progress.completedPoints);
  done.add(pointId);
  return {
    ...session,
    progress: {
      ...session.progress,
      completedPoints: Array.from(done),
      currentPointIndex: Math.min(session.progress.currentPointIndex + 1, story.points.length),
    },
  };
}

/** Leave preview mode and throw the progress away. */
export function closePreview(): PreviewSession {
  return CLOSED_PREVIEW;
}
