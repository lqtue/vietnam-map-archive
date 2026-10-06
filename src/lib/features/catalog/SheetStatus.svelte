<!--
  SheetStatus — one sheet's status, for staff: on the map or a scan only, and the
  work pips beside it. The table's Status cell and the grid card both wear it, so
  the two cannot say different things. A scout candidate is just "scout".
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import type { WorkFacts } from '$lib/core/sheetWork';
  import WorkPips from './WorkPips.svelte';

  export let item: { georef_done?: boolean; _table?: string };
  export let state: WorkFacts | undefined = undefined;
</script>

{#if item._table === 'scout'}
  <span class="badge-chip is-sm scout">scout</span>
{:else}
  <!-- Georeferenced or not is a fact about the sheet, so plain text; the pips are progress. -->
  <span class="geo" title={item.georef_done ? $t('Available on map') : $t('Static image only')}
    >{item.georef_done ? $t('Map') : $t('Image')}</span
  >
  <WorkPips pips {state} />
{/if}

<style>
  .geo {
    display: inline-block;
    min-width: 2.6rem;
    font-size: 0.78rem;
    font-weight: var(--font-semibold);
    color: var(--sb-text-meta);
  }
  /* Two tones only: a tint of a token, not the solid `.chip-yellow`. */
  .scout {
    background: var(--sb-accent-yellow);
  }
</style>
