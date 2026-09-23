<!--
  SheetInfoPanel.svelte — the Info tab body shared by /explore's right rail
  and Studio: name, TopSheetActions, metadata rows, description, editions,
  holding-library link. Extracted from ExploreRightSidebar (Sept 2026) so a
  second right-side tab strip does not re-derive `infoRows`.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import TopSheetActions from './TopSheetActions.svelte';
  import SheetEditions from './SheetEditions.svelte';

  const dispatch = createEventDispatcher<{ toggleVectors: { mapId: string } }>();

  export let mapId: string | null = null;
  export let map: MapListItem | null = null;
  export let vectorsOn = false;

  $: published = map?.status === 'public' || map?.status === 'featured';

  $: infoRows = map
    ? ([
        ['Year', map.year_label ?? (map.year ? String(map.year) : '')],
        ['Creator', map.creator ?? ''],
        ['Collection', map.collection ?? map.holding_institution ?? ''],
        ['Type', map.map_type ?? ''],
        ['Place', map.location ?? ''],
      ].filter(([, v]) => !!v) as [string, string][])
    : [];
</script>

{#if !map}
  <p class="sb-empty">{$t('Add a map layer to see its details.')}</p>
{:else}
  <h3 class="if-name">{map.name}</h3>
  <TopSheetActions
    {mapId}
    slug={map?.slug ?? null}
    {published}
    {vectorsOn}
    on:toggleVectors={(e) => dispatch('toggleVectors', e.detail)}
  />
  <dl class="if-dl">
    {#each infoRows as [label, value] (label)}
      <dt>{label}</dt>
      <dd>{value}</dd>
    {/each}
  </dl>
  {#if map.dc_description}
    <p class="if-desc">{map.dc_description}</p>
  {/if}
  <SheetEditions {mapId} />
  {#if map.source_url}
    <div class="if-links">
      <!-- No catalogue-page link here: that is TopSheetActions' Share. -->
      <a class="sb-btn is-sm" href={map.source_url} target="_blank" rel="noopener">
        {$t('Holding library')}
      </a>
    </div>
  {/if}
{/if}

<style>
  .if-name {
    margin: 0 0 0.5rem;
    font-family: var(--sb-font-display);
    font-size: 0.92rem;
    line-height: 1.25;
    color: var(--sb-text);
  }
  .if-dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.15rem 0.5rem;
    margin: 0;
    font-size: 0.78rem;
  }
  .if-dl dt {
    font-family: var(--sb-font-display);
    font-size: 0.62rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--sb-text-meta);
    align-self: baseline;
  }
  .if-dl dd {
    margin: 0;
    min-width: 0;
    color: var(--sb-text);
  }
  .if-desc {
    margin: 0.6rem 0 0;
    font-size: 0.76rem;
    line-height: 1.45;
    color: var(--sb-text-meta);
  }
  .if-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.7rem;
  }
</style>
