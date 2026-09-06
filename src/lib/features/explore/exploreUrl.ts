/**
 * exploreUrl.ts — the `?map=` deeplink contract for /explore.
 *
 * `?map=<id>` (query, written here) is the inbound deep link: it is what
 * /archive, /scan?mode=triage and every share link point at. The `&map=`
 * that urlStore used to append to the `#…` hash was a second, competing
 * mechanism for the same thing and was dropped — see `$lib/map/stores/urlStore.ts`.
 * The hash reader stays tolerant of `map=` so old links still land here.
 */
import { pushState, replaceState } from '$app/navigation';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import type { MapListItem } from '$lib/data/maps/types';
import type { Story } from '$lib/features/stories/shared/types';
import { resolveMapRef } from '$lib/features/stories/shared/applyPoint';
import { recordMapOpen } from '$lib/data/supabase/mapOpens';

export interface ExploreUrlOptions {
  supabase: SupabaseClient<Database>;
  /** Current viewer role — staff opens are not tallied. */
  role: () => 'user' | 'mod' | 'admin';
  /** Lets the page mark the deeplink as consumed before we push our own URL. */
  markApplied: () => void;
}

export interface ExploreUrl {
  syncMapParam(mapId: string | null): void;
  /** Writes (or clears) `?at=` so the spot the reader landed on is shareable. */
  syncAtParam(at: { lng: number; lat: number } | null): void;
  tallyMapOpen(mapId: string): void;
}

export function createExploreUrl({ supabase, role, markApplied }: ExploreUrlOptions): ExploreUrl {
  /**
   * Writes the topmost overlay into `?map=` so the selection is shareable and,
   * more importantly, so each opened map shows up as its own path+query in
   * Cloudflare Web Analytics. /explore was previously a single opaque URL, so
   * there was no way to tell which of the ~100 maps anyone actually looked at.
   *
   * ponytail: mirrors only the topmost overlay, not the whole stack. The
   * applyExploreUrlParams() reader takes a single ?map= id, so a full stack
   * encoding would need a reader change too — do that if sharing multi-map
   * stacks is ever asked for.
   */
  function syncMapParam(mapId: string | null) {
    // Read window.location, NOT $page.url: pushState() is shallow routing, so it
    // updates $page.state and leaves $page.url pinned at the last real
    // navigation ("/explore"). Building from $page.url meant the delete below hit
    // a URL that never had ?map= on it, so removal silently no-op'd.
    // MapShell's initUrlSync also owns the #@lat,lng,zoom hash — carrying the
    // live href over keeps its camera state instead of clobbering it.
    const url = new URL(window.location.href);
    if (mapId) url.searchParams.set('map', mapId);
    else url.searchParams.delete('map');
    if (url.href === window.location.href) return;
    // Belt-and-braces: $page.url doesn't currently see our writes, but if that
    // ever changes the deeplink block would fire on our own URL and force-zoom
    // a second time right after handlePickMap's soft zoom.
    markApplied();
    // pushState (not replaceState) so the beacon registers a new pageview and
    // back/forward walks the maps the visitor opened.
    pushState(url, {});
  }

  /**
   * Staff opens are skipped. label_pins and footprint_submissions are both 100%
   * admin rows, which makes them useless as interest signals — cataloguing work
   * would drown out the handful of real visitors here too.
   */
  function tallyMapOpen(mapId: string) {
    if (role() !== 'user') return;
    recordMapOpen(supabase, mapId);
  }

  /**
   * `?at=` is the spot, `?map=` is the sheet. Written on a label pick so the
   * reader can copy the URL and hand someone the same place on the same map;
   * cleared when the overlay changes, because a coordinate from one sheet is
   * not a claim about another.
   */
  function syncAtParam(at: { lng: number; lat: number } | null) {
    const url = new URL(window.location.href);
    if (at) url.searchParams.set('at', `${at.lng.toFixed(6)},${at.lat.toFixed(6)}`);
    else url.searchParams.delete('at');
    if (url.href === window.location.href) return;
    markApplied();
    // replaceState, not pushState: the map param already made a history entry
    // for this pick, and a second one would make Back feel broken.
    replaceState(url, {});
  }

  return { syncMapParam, syncAtParam, tallyMapOpen };
}

export interface ApplyExploreUrlParams {
  mapId: string | null;
  /** `?at=<lng>,<lat>` — a spot on the map to land on (a label hit); needs `mapId`. */
  at: string | null;
  storyId: string | null;
  maps: MapListItem[];
  stories: Story[];
  addMapOverlay: (map: MapListItem) => void;
  tallyMapOpen: (mapId: string) => void;
  zoomToMap: (map: MapListItem, options?: { force?: boolean }) => Promise<void>;
  setView: (view: { lng: number; lat: number; zoom: number }) => void;
  startStory: (story: Story) => void;
}

/** Zoom used when landing on a single label — a street name is legible here. */
export const LABEL_ZOOM = 17;

export function parseAt(at: string | null): { lng: number; lat: number } | null {
  const [lng, lat] = (at ?? '').split(',').map(Number);
  return Number.isFinite(lng) && Number.isFinite(lat) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
    ? { lng, lat }
    : null;
}

/** Applies `?map=` / `?story=` once both `maps` and `stories` have landed. */
export async function applyExploreUrlParams(p: ApplyExploreUrlParams): Promise<void> {
  if (p.mapId) {
    const found = resolveMapRef(p.maps, p.mapId);
    if (found) {
      p.addMapOverlay(found);
      // Arriving on a shared ?map= link is an open too — and it's the one path
      // where the visitor never touches the browse panel.
      p.tallyMapOpen(found.id);
      await p.zoomToMap(found, { force: true });
      const at = parseAt(p.at);
      if (at) p.setView({ ...at, zoom: LABEL_ZOOM });
    }
  }
  if (p.storyId) {
    const story = p.stories.find((s) => s.id === p.storyId);
    if (story) p.startStory(story);
  }
}
