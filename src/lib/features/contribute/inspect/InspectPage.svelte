<!--
  /scan?mode=inspect — read-only IIIF scan viewer.
  URL: /scan?map=<uuid>

  Same frame as every other /scan mode: `ScanLeftRail` on the left (which sheet,
  and how far to dim it), `ImageShell` in the middle. No right sidebar — a
  read-only viewer has no mode work to put there.

  It supplies its own map list rather than letting the rail load one:
  `fetchLabelMaps` filters to `georef_done`, and an ungeoreferenced scan is
  exactly the thing an inspector is looking at.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import ToolLayout from '$lib/map/shell/ToolLayout.svelte';
  import ImageShell from '$lib/map/shell/ImageShell.svelte';
  import ScanLeftRail from '$lib/features/contribute/shared/ScanLeftRail.svelte';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';
  import '$styles/layouts/tool-page.css';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchMaps } from '$lib/data/maps/service';
  import type { MapListItem } from '$lib/data/maps/types';
  import type { LabelMapInfo } from '$lib/data/supabase/footprints';

  const { supabase } = getSupabaseContext();

  // ── Map list ───────────────────────────────────────────────────────────────
  let maps: MapListItem[] = [];
  let currentMap: MapListItem | null = null;
  let iiifInfoUrl: string | null = null;
  let mapsError = '';

  // ── Layout ─────────────────────────────────────────────────────────────────
  let sidebarCollapsed = false;
  let isMobile = false;
  let isCompact = false;
  let imageOpacity = 1;

  // ── Derived ────────────────────────────────────────────────────────────────
  // Only scans: a row without a IIIF service has nothing to show here.
  // `legend`/`categories`/`triage` are the label tools' business; the rail only
  // reads name, year, location and description.
  $: railMaps = maps
    .filter((m) => !!m.iiif_image)
    .map((m): LabelMapInfo => ({
      id: m.id,
      name: m.name,
      allmapsId: m.allmaps_id ?? '',
      iiifImage: m.iiif_image,
      legend: [],
      categories: [],
      triage: null,
      year: m.year,
      location: m.location,
      description: m.dc_description,
    }));

  function selectMap(map: MapListItem) {
    if (currentMap?.id === map.id) return;
    currentMap = map;
    iiifInfoUrl = map.iiif_image ? map.iiif_image + '/info.json' : null;
  }

  function pick(id: string) {
    const match = maps.find((m) => m.id === id);
    if (match) selectMap(match);
  }

  onMount(async () => {
    try {
      maps = await fetchMaps(supabase, { includeArchived: true });
    } catch (err: any) {
      mapsError = err?.message ?? 'Failed to load maps';
    }
    const paramId = $page.url.searchParams.get('map');
    if (paramId) pick(paramId);
  });
</script>

<svelte:head>
  <title>{currentMap ? `${currentMap.name} — scan` : 'Image viewer'} — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Inspect high-resolution scans of historical maps from the Vietnam Map Archive."
  />
</svelte:head>

<div class="tool-page">
  <ToolLayout bind:sidebarCollapsed bind:isMobile bind:isCompact>
    <!-- Left: which sheet. Same rail, same place, in every /scan mode. -->
    <svelte:fragment slot="sidebar">
      <ScanLeftRail
        maps={railMaps}
        requireGeoref={false}
        selectedMapId={currentMap?.id ?? null}
        bind:imageOpacity
        onCollapse={() => (sidebarCollapsed = true)}
        on:select={(e) => pick(e.detail.map.id)}
      >
        <!-- The way out of a read-only viewer, in the rail's own slot: the card
             this replaced carried a thumbnail of the scan already on screen. -->
        {#if currentMap}
          <SidebarCard grow={0} flush={true} scroll={false} padded={true}>
            <div class="inspect-links">
              {#if currentMap.georef_done}
                <a class="inspect-link primary" href={`/explore?map=${currentMap.id}`}>
                  Open on map
                </a>
              {/if}
              <a class="inspect-link" href={`/explore?mode=studio&map=${currentMap.id}`}>
                Studio
              </a>
            </div>
          </SidebarCard>
        {/if}
      </ScanLeftRail>
    </svelte:fragment>

    <!-- Image stage -->
    {#if currentMap && iiifInfoUrl}
      <ImageShell {iiifInfoUrl} {imageOpacity} />
    {:else}
      <div class="empty-stage">
        <p>Pick a map to inspect its scan.</p>
        {#if mapsError}
          <p class="empty-state error">Couldn't load the map list: {mapsError}</p>
        {/if}
        <a href="/catalog" class="catalog-link">Browse the catalog →</a>
      </div>
    {/if}
  </ToolLayout>
</div>

<style>
  .inspect-links {
    display: flex;
    gap: 0.35rem;
  }
  .inspect-link {
    flex: 1;
    padding: 0.35rem 0.55rem;
    text-align: center;
    background: var(--color-white);
    color: var(--color-text);
    text-decoration: none;
    border: var(--sb-border);
    border-radius: var(--sb-radius-sm);
    font-size: 0.75rem;
    font-weight: var(--font-bold);
  }
  .inspect-link:hover {
    background: var(--sb-row-active);
  }
  .inspect-link.primary {
    background: var(--color-text);
    color: var(--color-white);
  }
</style>
