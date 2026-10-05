<!--
  SheetWork — staff only: what has been done to a sheet, and a menu to open it in
  a contribution tool. One component for the catalog table's Status cell and the
  record page, so the two cannot disagree. The tracks and their rules are
  `$lib/core/sheetWork`.

  Green = done, yellow = in between, outline = not yet. The menu is a native
  <details>: no state, closes with the page.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { CONTRIBUTE_TOOLS, toolHref } from '$lib/core/scanModes';
  import { sheetTracks, type TrackState, type WorkFacts } from '$lib/core/sheetWork';

  export let mapId: string;
  export let state: WorkFacts | undefined = undefined;

  const CLASS: Record<TrackState, string> = {
    done: 'chip-green',
    doing: 'chip-yellow',
    todo: 'chip-gray',
  };

  $: tracks = sheetTracks(state);
</script>

<div class="sw" on:click|stopPropagation on:keydown|stopPropagation role="presentation">
  {#each tracks as tr (tr.key)}
    <span
      class="badge-chip is-sm {CLASS[tr.state]}"
      class:sw-todo={tr.state === 'todo'}
      title={$t(tr.hint)}>{$t(tr.label)}</span
    >
  {/each}
  <details class="sw-menu">
    <summary class="btn is-xs">{$t('Open in')} ▾</summary>
    <ul>
      {#each CONTRIBUTE_TOOLS as tool (tool.mode)}
        <li><a href={toolHref(tool.mode, mapId)}>{$t(tool.label)}</a></li>
      {/each}
    </ul>
  </details>
</div>

<style>
  .sw {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem;
  }
  .sw-todo {
    opacity: 0.55;
  }
  .sw-menu {
    position: relative;
  }
  .sw-menu summary {
    cursor: pointer;
    list-style: none;
  }
  .sw-menu ul {
    position: absolute;
    z-index: 5;
    margin: 0.2rem 0 0;
    padding: 0.25rem;
    list-style: none;
    min-width: 8rem;
    background: var(--color-white);
    border: 1.5px solid var(--color-border);
    border-radius: var(--sb-radius-sm);
  }
  .sw-menu a {
    display: block;
    padding: 0.3rem 0.5rem;
    text-decoration: none;
    color: inherit;
  }
  .sw-menu a:hover {
    background: var(--color-surface-alt, rgba(0, 0, 0, 0.06));
  }
</style>
