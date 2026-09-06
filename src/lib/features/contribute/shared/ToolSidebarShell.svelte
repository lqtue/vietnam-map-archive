<!--
  ToolSidebarShell.svelte — the `<aside class="panel">` + ToolPanelHeader wrapper
  every contribute tool sidebar repeats (once per viewport, per page).

  Slots:
    default — panel body
    footer  — optional sticky footer (e.g. the digitalize phase tabs)
-->
<script lang="ts">
  import ToolPanelHeader from './ToolPanelHeader.svelte';
  import '$styles/layouts/tool-page.css';

  export let title: string = '';
  export let onCollapse: (() => void) | null = null;
</script>

<aside class="panel">
  <ToolPanelHeader {title} {onCollapse} />
  <slot />
  {#if $$slots.footer}
    <div class="panel-footer">
      <slot name="footer" />
    </div>
  {/if}
</aside>

<style>
  .panel-footer {
    padding: 0.75rem;
    background: var(--ground-raised);
    border-top: var(--rule-thick) solid var(--rule);
    flex-shrink: 0;
    display: flex;
    justify-content: center;
  }
</style>
