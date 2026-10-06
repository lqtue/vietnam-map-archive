import type { FeatureCollection } from 'geojson';
import type { Readable } from 'svelte/store';
import type { MeasurementEvent } from '$lib/core/measurement';

export const STUDIO_SAVE_FAILURE = {
  text: 'Could not save to the archive. Changes remain in this browser.',
  tone: 'error' as const,
};

type TrackMeasurement = (event: MeasurementEvent, params?: Record<string, unknown>) => unknown;
type HistoryState = { history: readonly unknown[]; future: readonly unknown[] };

/** Measurement state for one Studio project, with event delivery injected for focused tests. */
export function createStudioMeasurementController(track: TrackMeasurement) {
  let savedFeatures = '';
  let draftOpen = false;

  const signature = (features: FeatureCollection) => JSON.stringify(features);

  function beginProject(features: FeatureCollection) {
    savedFeatures = signature(features);
    draftOpen = false;
  }

  function open() {
    track('contribution_open', {
      surface: 'explore',
      workflow: 'studio',
      mode: 'studio',
      action: 'open',
    });
  }

  function enterProject(features: FeatureCollection) {
    beginProject(features);
    open();
  }

  function observeDraft(features: FeatureCollection): boolean {
    if (draftOpen || signature(features) === savedFeatures) return false;
    draftOpen = true;
    track('draft_started', {
      surface: 'explore',
      workflow: 'studio',
      mode: 'studio',
      action: 'save',
    });
    return true;
  }

  /** Call only after persistence resolves; failures leave the active draft attempt intact. */
  function saved(features: FeatureCollection, persistenceConfirmed: boolean): boolean {
    if (!persistenceConfirmed) return false;
    const nextSignature = signature(features);
    const changed = nextSignature !== savedFeatures;
    savedFeatures = nextSignature;
    draftOpen = false;
    if (!changed || features.features.length === 0) return false;
    track('save_success', {
      surface: 'explore',
      workflow: 'studio',
      mode: 'studio',
      action: 'save',
    });
    return true;
  }

  function exportCompleted() {
    track('export_completed', {
      surface: 'explore',
      workflow: 'studio',
      mode: 'studio',
      action: 'export',
    });
  }

  function watchHistory<T extends HistoryState>(
    source: Readable<T>,
    getFeatures: () => FeatureCollection | null,
    isEditorOpen: () => boolean,
    isRestoring: () => boolean
  ) {
    let previousHistory: readonly unknown[] | null = null;
    let previousFuture: readonly unknown[] | null = null;
    let skipInitialHistory = true;
    return source.subscribe((state) => {
      const changed = state.history !== previousHistory || state.future !== previousFuture;
      previousHistory = state.history;
      previousFuture = state.future;
      if (skipInitialHistory) {
        skipInitialHistory = false;
        return;
      }
      if (!changed || isRestoring() || !isEditorOpen()) return;
      const features = getFeatures();
      if (features) observeDraft(features);
    });
  }

  return { beginProject, open, enterProject, observeDraft, saved, exportCompleted, watchHistory };
}
