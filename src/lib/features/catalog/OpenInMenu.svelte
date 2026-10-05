<!--
  OpenInMenu — staff only: open one sheet in a contribution tool. A native
  <details>, so there is no state and it closes with the page. Clicks inside do
  not reach the row, which would open the drawer.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { CONTRIBUTE_TOOLS, toolHref } from '$lib/core/scanModes';

  export let mapId: string;
</script>

<span class="oi" on:click|stopPropagation on:keydown|stopPropagation role="presentation">
  <details>
    <summary class="btn is-xs">{$t('Open in')} ▾</summary>
    <ul>
      {#each CONTRIBUTE_TOOLS as tool (tool.mode)}
        <li><a href={toolHref(tool.mode, mapId)}>{$t(tool.label)}</a></li>
      {/each}
    </ul>
  </details>
</span>

<style>
  .oi {
    position: relative;
    display: inline-block;
  }
  .oi summary {
    cursor: pointer;
    list-style: none;
  }
  .oi ul {
    position: absolute;
    right: 0;
    z-index: 5;
    margin: 0.2rem 0 0;
    padding: 0.25rem;
    list-style: none;
    min-width: 8rem;
    background: var(--color-white);
    border: 1.5px solid var(--color-border);
    border-radius: var(--sb-radius-sm);
  }
  .oi a {
    display: block;
    padding: 0.3rem 0.5rem;
    text-decoration: none;
    color: inherit;
  }
  .oi a:hover {
    background: var(--color-surface-alt, rgba(0, 0, 0, 0.06));
  }
</style>
