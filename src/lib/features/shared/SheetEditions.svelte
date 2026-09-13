<!--
  The other printings of the sheet on top of the stack.

  A sheet is a 15' x 15' cell and an edition is one printing of it, so cell
  6330-4 is both SÀI GÒN (content 1965, reprinted 1978) and THÀNH PHỐ HỒ CHÍ
  MINH (compiled 1984) — the same square of ground, one renaming apart. Without
  this list the second one is reachable only by searching its sheet number,
  which no reader does.

  Adding one puts it on the layer stack beside the sheet already there, which is
  the point: the opacity slider between two editions of one cell is the archive's
  own argument at sheet scale. An edition that is catalogued but not yet
  georeferenced says so rather than offering a button that draws nothing —
  `georef_done`, because a self-hosted scan gets an `allmaps_id` the moment it
  is tiled.
-->
<script lang="ts">
  import { onDestroy } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchSheetEditions, type SheetEdition } from '$lib/data/maps/service';
  import { layersStore, toggleOverlayFor } from '$lib/map/stores/layersStore';
  import { t } from '$lib/core/i18n';

  /** The sheet whose siblings to look for. */
  export let mapId: string | null = null;

  const { supabase } = getSupabaseContext();

  let editions: SheetEdition[] = [];
  let loadedFor: string | null = null;

  // A stale response must not paint over a newer one: the reader can change the
  // top sheet while this is in flight.
  let requestId = 0;

  async function load(id: string) {
    // Claimed before the await, not after: the statement below re-runs on the
    // next render either way, so setting it late asks for the same sheet
    // twice, and leaves the previous sheet's editions on screen under the new
    // sheet's name. Writing it here makes the guard the termination condition.
    loadedFor = id;
    editions = [];
    const mine = ++requestId;
    const rows = await fetchSheetEditions(supabase, id);
    if (mine !== requestId) return;
    editions = rows;
  }

  $: if (mapId && mapId !== loadedFor) load(mapId);
  $: if (!mapId) {
    editions = [];
    loadedFor = null;
  }

  $: onStack = new Set($layersStore.overlays.map((o) => o.ref.mapId));

  onDestroy(() => {
    requestId++;
  });

  function label(e: SheetEdition): string {
    // The year alone does not separate two rows of the same cell: a reprint
    // keeps its content date, so both of 6330-1's printings read 1969.
    const parts = [e.year ? String(e.year) : null, e.edition ? `ed. ${e.edition}` : null];
    return parts.filter(Boolean).join(' · ');
  }
</script>

{#if editions.length > 0}
  <div class="se">
    <h4 class="se-title">{$t('Other editions of this sheet')}</h4>
    <ul class="se-list">
      {#each editions as edition (edition.id)}
        {@const drawable = edition.georef_done}
        <li class="se-row">
          <div class="se-meta">
            <span class="se-name">{edition.name}</span>
            <span class="se-sub">
              {label(edition)}
              {#if edition.status === 'draft'}<em class="se-draft">{$t('draft')}</em>{/if}
            </span>
            {#if edition.printing}
              <span class="se-printing">{edition.printing}</span>
            {/if}
          </div>
          {#if drawable}
            <button
              type="button"
              class="btn is-xs"
              class:is-on={onStack.has(edition.id)}
              on:click={() => toggleOverlayFor(edition)}
            >
              {onStack.has(edition.id) ? $t('On map') : $t('Compare')}
            </button>
          {:else}
            <span class="se-nogeo">{$t('not georeferenced')}</span>
          {/if}
        </li>
      {/each}
    </ul>
  </div>
{/if}

<style>
  .se {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: var(--sb-border);
  }
  /* Same face as the Info tab's own <dt>, so the section reads as one more
     field of the sheet rather than a second design. */
  .se-title {
    margin: 0 0 0.45rem;
    font-family: var(--sb-font-display);
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--sb-text-meta);
  }
  .se-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .se-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .se-meta {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    min-width: 0;
  }
  .se-name {
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.25;
    color: var(--sb-text);
  }
  .se-sub,
  .se-printing {
    font-size: 0.68rem;
    color: var(--sb-text-meta);
  }
  .se-printing {
    font-style: italic;
  }
  .se-draft {
    margin-left: 0.35rem;
    font-style: normal;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--sb-text-muted);
  }
  .se-nogeo {
    flex: none;
    font-size: 0.68rem;
    color: var(--sb-text-muted);
  }
</style>
