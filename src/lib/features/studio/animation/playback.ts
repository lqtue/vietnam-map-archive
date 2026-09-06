/**
 * playback.ts — sequential keyframe runner for /explore?mode=annotate.
 *
 * For each keyframe:
 *   1. Reconcile overlay membership against `layersStore` by mapId.
 *      (Add missing overlays at opacity 0 so they fade in; remove ones the
 *      target frame doesn't have.)
 *   2. In parallel, tween:
 *        • camera     — OL `view.animate()`
 *        • opacities  — one rAF tween per layer → `layersStore.setOpacity()`
 *   3. Wait `hold_ms`.
 *
 * `stop()` cancels in-flight tweens and the OL view animation.
 */
import OLMap from 'ol/Map';
import { fromLonLat } from 'ol/proj';
import { get } from 'svelte/store';
import { easeInOutCubic, tweenValue } from '$lib/core/utils/tween';
import { layersStore } from '$lib/map/stores/layersStore';
import type { Keyframe } from './timelineStore';

export interface PlaybackHandle {
  stop: () => void;
  isPlaying: () => boolean;
}

export interface PlayOptions {
  onFrameEnter?: (index: number) => void;
  onFinish?: () => void;
  onError?: (e: unknown) => void;
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (ms <= 0) return resolve();
    const t = setTimeout(() => resolve(), ms);
    signal.addEventListener('abort', () => {
      clearTimeout(t);
      reject(new DOMException('aborted', 'AbortError'));
    });
  });
}

function reconcileOverlays(target: Keyframe, mode: 'cut' | 'crossfade'): Map<string, string> {
  // Returns mapId → local overlay id in the live store after reconciliation.
  const live = get(layersStore);
  const liveByMap = new Map(live.overlays.map((o) => [o.ref.mapId, o] as const));
  const targetMapIds = new Set(target.layers.overlays.map((o) => o.mapId));

  // Remove overlays the target frame doesn't include.
  for (const o of live.overlays) {
    if (!targetMapIds.has(o.ref.mapId)) layersStore.removeOverlay(o.id);
  }

  // Set base if it differs.
  const liveBase = live.base;
  const targetBase = target.layers.base;
  const baseChanged =
    liveBase.kind !== targetBase.kind ||
    (liveBase.kind === 'historical' &&
      targetBase.kind === 'historical' &&
      liveBase.mapId !== targetBase.mapId) ||
    (liveBase.kind === 'basemap' &&
      targetBase.kind === 'basemap' &&
      liveBase.key !== targetBase.key);
  if (baseChanged) layersStore.setBase(targetBase);

  // Add missing overlays. In crossfade mode start at 0 so the tween fades them
  // in; in cut mode start at target opacity (the tween loop will see no diff
  // and skip them — instant appearance).
  for (const t of target.layers.overlays) {
    if (!liveByMap.has(t.mapId)) {
      layersStore.addOverlay(
        {
          kind: 'historical',
          mapId: t.mapId,
          allmapsId: t.allmapsId,
          name: t.name,
          thumbnail: t.thumbnail,
        },
        { opacity: mode === 'crossfade' ? 0 : t.opacity }
      );
    }
  }

  // Re-read and build the mapId → liveId map.
  const next = get(layersStore);
  return new Map(next.overlays.map((o) => [o.ref.mapId, o.id] as const));
}

export function playTimeline(
  map: OLMap,
  frames: Keyframe[],
  opts: PlayOptions = {}
): PlaybackHandle {
  const controller = new AbortController();
  const signal = controller.signal;
  let active: Tween[] = [];
  let playing = true;
  let cancelled = false;

  function stop() {
    if (cancelled) return;
    cancelled = true;
    playing = false;
    controller.abort();
    for (const a of active) a.pause();
    active = [];
    try {
      map.getView().cancelAnimations();
    } catch {}
  }

  (async () => {
    try {
      for (let i = 0; i < frames.length; i++) {
        if (cancelled) break;
        const frame = frames[i];
        opts.onFrameEnter?.(i);

        const mode = frame.overlay_transition ?? 'cut';
        const overlayIds = reconcileOverlays(frame, mode);

        // Opacity diff between current live state and target keyframe.
        const live = get(layersStore);
        const targetByMap = new Map(frame.layers.overlays.map((o) => [o.mapId, o] as const));
        active = [];
        for (const o of live.overlays) {
          const target = targetByMap.get(o.ref.mapId);
          const to = target ? target.opacity : 0;
          if (Math.abs(o.opacity - to) < 0.001) continue;
          const id = overlayIds.get(o.ref.mapId) ?? o.id;
          if (mode === 'cut') {
            // Hard cut — apply immediately.
            layersStore.setOpacity(id, to);
            continue;
          }
          active.push(
            tween(o.opacity, to, frame.duration_ms, (v) => layersStore.setOpacity(id, v))
          );
        }

        // Camera tween via OL.
        const view = map.getView();
        const cameraPromise: Promise<void> = new Promise((resolve) => {
          view.animate(
            {
              center: fromLonLat([frame.camera.lng, frame.camera.lat]),
              zoom: frame.camera.zoom,
              rotation: frame.camera.rotation,
              duration: frame.duration_ms,
              easing: easeInOutCubic,
            },
            () => resolve()
          );
        });

        // Wait for both camera + opacity tweens to finish (durations match).
        await Promise.race([
          Promise.all([cameraPromise, wait(frame.duration_ms, signal)]),
          new Promise<void>((_, reject) => {
            signal.addEventListener('abort', () =>
              reject(new DOMException('aborted', 'AbortError'))
            );
          }),
        ]);

        if (cancelled) break;
        if (frame.hold_ms > 0) await wait(frame.hold_ms, signal);
      }
      if (!cancelled) opts.onFinish?.();
    } catch (e) {
      if ((e as DOMException)?.name !== 'AbortError') opts.onError?.(e);
    } finally {
      playing = false;
    }
  })();

  return { stop, isPlaying: () => playing };
}

interface Tween {
  pause(): void;
}

/**
 * Tween one number over `ms`, easing, on the animation frame clock.
 *
 * ponytail: replaces animejs, which was pulled in for exactly this — a proxy
 * object with one numeric property — while the file already carried the easing
 * curve below for the OpenLayers camera. Ceiling: no stagger, no keyframes, no
 * spring. If the timeline ever needs those, take the dependency back rather
 * than growing this.
 */
function tween(from: number, to: number, ms: number, onUpdate: (v: number) => void): Tween {
  let raf = 0;
  let stopped = false;
  const started = performance.now();

  const step = (now: number) => {
    if (stopped) return;
    const t = ms > 0 ? Math.min(1, (now - started) / ms) : 1;
    onUpdate(tweenValue(from, to, t));
    if (t < 1) raf = requestAnimationFrame(step);
  };
  raf = requestAnimationFrame(step);

  return {
    pause() {
      stopped = true;
      cancelAnimationFrame(raf);
    },
  };
}

/** Apply a keyframe instantly (no tween). Used for "Jump to". */
export function applyKeyframeInstant(map: OLMap, frame: Keyframe): void {
  reconcileOverlays(frame, 'cut');
  const live = get(layersStore);
  const targetByMap = new Map(frame.layers.overlays.map((o) => [o.mapId, o] as const));
  for (const o of live.overlays) {
    const target = targetByMap.get(o.ref.mapId);
    layersStore.setOpacity(o.id, target ? target.opacity : 0);
    if (target) layersStore.setVisible(o.id, target.visible);
  }
  const view = map.getView();
  view.cancelAnimations();
  view.setCenter(fromLonLat([frame.camera.lng, frame.camera.lat]));
  view.setZoom(frame.camera.zoom);
  view.setRotation(frame.camera.rotation);
}
