/**
 * MapShell Svelte context — exposes the OL Map instance and
 * central stores to any child component.
 *
 * Usage:
 *   // Parent (MapShell / MapWorkspace) — sets context during init
 *   setShellContext({ map, mapStore, layerStore });
 *
 *   // Child — reads context
 *   const { map, mapStore, layerStore } = getShellContext();
 */

import { setContext, getContext } from 'svelte';
import type { Writable } from 'svelte/store';
import type Map from 'ol/Map';
import type { MapStore } from '$lib/map/stores/mapStore';
import type { LayerStore } from '$lib/map/stores/layerStore';

const SHELL_CTX = Symbol('shell-context');

export interface ShellContextValue {
  /** Writable holding the OL Map instance (null until mount) */
  map: Writable<Map | null>;
  mapStore: MapStore;
  layerStore: LayerStore;
}

// Annotation editing state is NOT here: /explore?mode=annotate owns it and passes it through
// `getAnnotationContext()` ($lib/map/annotations/annotationContext), which keeps the
// generic shell free of a feature-specific dependency.

export function setShellContext(value: ShellContextValue): void {
  setContext(SHELL_CTX, value);
}

export function getShellContext(): ShellContextValue {
  const ctx = getContext<ShellContextValue>(SHELL_CTX);
  if (!ctx) {
    throw new Error('Shell context not found — is this component inside a <MapShell>?');
  }
  return ctx;
}
