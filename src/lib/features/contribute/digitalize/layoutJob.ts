/**
 * layoutJob.ts — the layout pass of /scan?mode=triage.
 *
 * "Detect" asks the model what the sheet is made of. It is a job and not a
 * route because the Gemini key lives on the worker, so the client enqueues and
 * then polls until the job closes. This module owns that request, the poll
 * timer and its cleanup, so the route file is left with layout.
 *
 * Usage:
 *   const layout = createLayoutJob((regions) => (triage.regions = regions));
 *   onDestroy(layout.stop);
 *   $layout.detecting   // in markup
 */

import { writable } from 'svelte/store';
import type { LayoutRegion } from '$lib/data/maps/triageTypes';

export type LayoutJob = { status: string; error?: string | null };

export type LayoutJobState = {
  detecting: boolean;
  error: string;
  job: LayoutJob | null;
};

const IDLE: LayoutJobState = { detecting: false, error: '', job: null };
const LIVE = ['queued', 'claimed', 'running'];
const POLL_MS = 5000;

export function createLayoutJob(onRegions: (regions: LayoutRegion[]) => void) {
  const { subscribe, set, update } = writable<LayoutJobState>({ ...IDLE });
  let timer: ReturnType<typeof setInterval> | null = null;
  let detecting = false;

  /** Clears the poll timer only — `detecting` is released where the job ends. */
  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  /** Pull the saved regions back, and whatever the job is doing. */
  async function refresh(mapId: string): Promise<void> {
    const res = await fetch(`/api/admin/maps/${mapId}/layout`);
    if (!res.ok) return;
    const data = await res.json();
    const job: LayoutJob | null = data.job ?? null;

    if (job && LIVE.includes(job.status)) {
      update((s) => ({ ...s, job }));
      return;
    }
    stop();
    detecting = false;
    // Only adopt the server's answer once the job is finished; mid-run it is
    // still whatever was there before, and overwriting a person's in-progress
    // corrections with it would be the worst possible moment.
    if (Array.isArray(data.regions) && data.regions.length) {
      onRegions(data.regions as LayoutRegion[]);
    }
    update((s) => ({
      ...s,
      job,
      detecting: false,
      error: job?.status === 'failed' ? (job.error ?? 'The layout job failed.') : s.error,
    }));
  }

  return {
    subscribe,

    /** Enqueue a layout job for this map and poll until it closes. */
    async detect(mapId: string) {
      if (detecting) return;
      detecting = true;
      update((s) => ({ ...s, detecting: true, error: '' }));
      try {
        const res = await fetch(`/api/admin/maps/${mapId}/layout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.message ?? res.statusText);
        update((s) => ({ ...s, job: { status: body.status ?? 'queued' } }));
        stop();
        timer = setInterval(() => refresh(mapId), POLL_MS);
      } catch (e: any) {
        detecting = false;
        update((s) => ({
          ...s,
          detecting: false,
          error: e?.message ?? 'Could not enqueue the layout job',
        }));
      }
    },

    /** Selecting another map: drop the previous map's job and its timer. */
    reset() {
      stop();
      detecting = false;
      set({ ...IDLE });
    },

    stop,
  };
}
