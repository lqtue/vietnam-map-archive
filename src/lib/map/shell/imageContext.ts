/**
 * imageContext.ts — Svelte context + reactive store for ImageShell.
 *
 * Pattern: ImageShell calls createImageShellContext() synchronously during
 * component init, which sets a writable store into Svelte context. Child tool
 * components (ShapeTool, bbox tools) call getImageShellStore() during their own
 * init to get the same store. The store starts null; ImageShell populates it
 * in onMount once OL objects exist. Tools react reactively to the store.
 */
import { setContext, getContext } from 'svelte';
import { writable } from 'svelte/store';
import type { Writable } from 'svelte/store';
import type OlMap from 'ol/Map';
import type VectorSource from 'ol/source/Vector';
import type VectorLayer from 'ol/layer/Vector';

export interface ImageShellContext {
  map: OlMap;
  footprintSource: VectorSource;
  /** Temporary source for in-progress drawing — cleared after each shape is committed. */
  drawSource: VectorSource;
  footprintLayer: VectorLayer;
}

export type ImageShellStore = Writable<ImageShellContext | null>;

const IMAGE_CTX = Symbol('image-shell-context');

/** Called by ImageShell during component init — sets context + returns the store. */
export function createImageShellContext(): ImageShellStore {
  const store = writable<ImageShellContext | null>(null);
  setContext(IMAGE_CTX, store);
  return store;
}

/** Called by tool components (children of ImageShell) during their own init. */
export function getImageShellStore(): ImageShellStore {
  return getContext<ImageShellStore>(IMAGE_CTX);
}
