<!--
  SheetWork — the record page's staff block: every work track as a labelled chip,
  and the menu to open the sheet in a tool. The table uses `WorkPips` and
  `OpenInMenu` separately, in two cells.
-->
<script lang="ts">
  import type { WorkFacts } from '$lib/core/sheetWork';
  import WorkPips from './WorkPips.svelte';
  import OpenInMenu from './OpenInMenu.svelte';

  export let mapId: string;
  export let state: WorkFacts | undefined = undefined;
</script>

<div class="sw">
  <WorkPips {state} />
  <OpenInMenu {mapId} />
</div>

<style>
  .sw {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
</style>
