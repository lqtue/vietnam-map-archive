<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';
  import { toLonLat } from 'ol/proj';
  import { getShellContext } from '$lib/map/shell/context';
  import { layersStore } from '$lib/map/stores/layersStore';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchSeriesSheets, fetchMapsByIds } from '$lib/data/maps/service';
  import type { MapListItem } from '$lib/data/maps/types';
  import { bboxContainsPoint } from './spatialLookup';

  export let mapList: MapListItem[] = [];
  const { map } = getShellContext();
  const { supabase } = getSupabaseContext();
  const dispatch = createEventDispatcher<{
    inspectMap: { mapId: string; tab: 'info' | 'legend' };
  }>();
  let position: { x: number; y: number; lng: number; lat: number } | null = null;
  let candidates: MapListItem[] = [];
  let loading = false;
  let failure = false;
  let request = 0;
  let menu: HTMLElement;
  let previousFocus: HTMLElement | null = null;
  function close() {
    const wasOpen = !!position;
    request += 1;
    position = null;
    if (wasOpen) previousFocus?.focus();
  }
  function inspect(mapId: string, tab: 'info' | 'legend') {
    dispatch('inspectMap', { mapId, tab });
    close();
  }
  async function open(event: MouseEvent) {
    const olMap = $map;
    if (!olMap) return;
    event.preventDefault();
    const coordinate = olMap.getCoordinateFromPixel(olMap.getEventPixel(event));
    if (!coordinate) return;
    const [lng, lat] = toLonLat(coordinate);
    const current = ++request;
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    position = { x: event.clientX, y: event.clientY, lng, lat };
    candidates = [];
    loading = true;
    failure = false;
    await tick();
    if (current !== request) return;
    menu?.focus();
    try {
      const stack = $layersStore.overlays.filter((layer) => layer.visible && layer.opacity > 0);
      const ids = new Set<string>();
      for (const layer of stack) {
        if (layer.ref.kind === 'historical') ids.add(layer.ref.mapId);
        else {
          for (const part of layer.ref.parts) {
            const sheets = await fetchSeriesSheets(
              supabase,
              part.seriesKey ?? layer.ref.key,
              part.seriesKey ? undefined : part.collection
            );
            for (const sheet of sheets) {
              if (sheet.bbox && bboxContainsPoint(sheet.bbox, lng, lat)) ids.add(sheet.id);
            }
          }
        }
      }
      const base = $layersStore.base;
      if (base.kind === 'historical') ids.add(base.mapId);
      let maps = mapList.filter((item) => ids.has(item.id));
      const missing = [...ids].filter((id) => !maps.some((item) => item.id === id));
      for (let from = 0; from < missing.length; from += 100) {
        maps = [...maps, ...(await fetchMapsByIds(supabase, missing.slice(from, from + 100)))];
      }
      if (current !== request) return;
      candidates = [...ids]
        .map((id) => maps.find((item) => item.id === id))
        .filter((item): item is MapListItem => !!item)
        .filter((item) => {
          const bounds = item.bounds ?? item.bbox;
          return bounds && bboxContainsPoint(bounds, lng, lat);
        });
    } catch {
      if (current === request) failure = true;
    } finally {
      if (current === request) loading = false;
    }
  }
  onMount(() => {
    let viewport: HTMLElement | null = null;
    const unsubscribe = map.subscribe((olMap) => {
      viewport?.removeEventListener('contextmenu', open);
      viewport = olMap?.getViewport() ?? null;
      viewport?.addEventListener('contextmenu', open);
    });
    return () => {
      close();
      unsubscribe();
      viewport?.removeEventListener('contextmenu', open);
    };
  });
</script>

<svelte:window
  on:keydown={(event) => {
    if (event.key === 'Escape') close();
  }}
/>
{#if position}
  <button class="menu-dismiss" aria-label="Close map menu" on:click={close}></button>
  <section
    class="map-menu section-card"
    aria-label="Maps at this location"
    bind:this={menu}
    style:left="max(.5rem, min({position.x}px, calc(100vw - 19rem)))"
    style:top="max(.5rem, min({position.y}px, calc(100dvh - 22rem)))"
    tabindex="-1"
  >
    <div class="menu-heading">
      <strong>Map location</strong><button
        class="sb-btn is-sm"
        on:click={close}
        aria-label="Close map menu">Close</button
      >
    </div>
    <p>Latitude {position.lat.toFixed(6)} · Longitude {position.lng.toFixed(6)}</p>
    <h3>Maps here</h3>
    <p class="coverage-note">
      Sheets in visible layers covering this location (approximate bounds).
    </p>
    {#if loading}<p role="status">Looking up sheets…</p>
    {:else if failure}<p role="alert">Could not load sheets. Try again.</p>
    {:else if !candidates.length}<p>No visible sheet bounds at this point.</p>
    {/if}
    {#each candidates as candidate (candidate.id)}
      <div class="candidate">
        <strong>{candidate.name}</strong>
        <div>
          <button class="sb-btn is-sm" on:click={() => inspect(candidate.id, 'info')}
            >Display info</button
          ><button class="sb-btn is-sm" on:click={() => inspect(candidate.id, 'legend')}
            >Display legend</button
          >
        </div>
      </div>
    {/each}
  </section>
{/if}

<style>
  .menu-dismiss {
    position: fixed;
    inset: 0;
    z-index: 110;
    border: 0;
    background: transparent;
  }
  .map-menu {
    position: fixed;
    z-index: 111;
    width: min(18rem, calc(100vw - 1rem));
    max-height: min(21rem, calc(100dvh - 1rem));
    overflow: auto;
    padding: 1rem;
    background: var(--color-white);
  }
  .menu-heading,
  .candidate > div {
    display: flex;
    gap: 0.5rem;
    justify-content: space-between;
    align-items: center;
  }
  p,
  h3 {
    margin: 0.5rem 0;
  }
  .coverage-note {
    font-size: 0.75rem;
    color: var(--color-gray-500);
  }
  .candidate {
    padding: 0.5rem 0;
    border-top: 1px solid var(--color-border);
  }
  .candidate strong {
    display: block;
    margin-bottom: 0.4rem;
  }
</style>
