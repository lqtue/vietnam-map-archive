<!--
  TopSheetActions.svelte — the way out of the viewer for the sheet on top of
  the stack: its traced fabric, its annotation page, and its own page in the
  catalog, which is where the scan lives too since Sept 2026.

  /explore had zero outbound links until Sept 2026. The strip lived at the foot
  of the layer stack in the left rail, then briefly above the right rail's tab
  strip — where it pushed the tabs down and belonged to no tab. It sits inside
  the right rail's Info tab now, under the sheet's name, which is also why it
  prints no name of its own.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import { mapRef } from '$lib/core/utils/mapSlug';

  const dispatch = createEventDispatcher<{ toggleVectors: { mapId: string } }>();

  export let mapId: string | null = null;
  /** The sheet's readable address (migration 088). Null falls back to the uuid,
   *  which still resolves — a draft picked up before its row carried a slug. */
  export let slug: string | null = null;

  $: ref = mapId ? mapRef({ id: mapId, slug }) : null;
  /** Whether the sheet is public. Only the wording turns on it now: since
   *  Sept 2026 /catalog/[id] resolves for a draft too, for a signed-in reader,
   *  but a draft's page is not a link anyone can share. */
  export let published = false;
  export let vectorsOn = false;
</script>

{#if mapId}
  <div class="tsa">
    <button
      type="button"
      class="sb-btn is-sm"
      class:is-on={vectorsOn}
      on:click={() => dispatch('toggleVectors', { mapId })}
      aria-pressed={vectorsOn}
      title="Traced footprints">⬡ Traced</button
    >
    <a class="sb-btn is-sm" href="/explore?mode=studio&map={ref}">Studio</a>
    <!-- Was two buttons to two places, and is one because the places merged:
         the scan is on the sheet's own page now, not behind /scan?map=. -->
    <a class="sb-btn is-sm" href="/catalog/{ref}">{published ? $t('Share') : $t('Scan')}</a>
  </div>
{/if}

<style>
  /* Inside a card body, which owns the padding. */
  .tsa {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0 0 0.6rem;
  }
</style>
