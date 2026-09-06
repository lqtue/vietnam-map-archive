<!--
  MobileDrawerStack.svelte — the < 900px bottom sheet for ToolLayout.

  A horizontal 3-tab bar (Layers · Controls · Browse) over one shared body that
  slides up. Only one drawer is open at a time; the backdrop dismisses. The
  legacy single-drawer ("Tools") fallback is used only when a caller supplies
  `mobile-sidebar` and none of the three named panes.

  Rendered inside ToolLayout's `.workspace`, which is the positioning context
  for the absolutely-positioned backdrop and stack.

  Slots: layers · controls · browse · legacy
-->
<script lang="ts">
  type DrawerKey = 'layers' | 'controls' | 'browse';

  /** Which drawer is open. Bindable so a parent (e.g. the /explore tour) can switch tabs. */
  export let openDrawer: 'none' | DrawerKey | 'legacy' = 'none';
  /** Tab order. Routes that want a different default (e.g. /explore = browse first) pass their own. */
  export let tabOrder: DrawerKey[] = ['layers', 'controls', 'browse'];

  export let hasLayers = false;
  export let hasControls = false;
  export let hasBrowse = false;
  /** Legacy single-drawer fallback; only honoured when none of the three above are present. */
  export let hasLegacy = false;

  $: showLegacy = hasLegacy && !hasLayers && !hasControls && !hasBrowse;

  // Bottom-sheet snap: the body defaults to a 60vh max-height; when the user
  // scrolls inside it past the top, expand to ~90vh so a long list is
  // browseable without forcing them to remember it's behind the fold.
  let drawerExpanded = false;
  function onDrawerScroll(e: Event) {
    const t = e.target as HTMLElement | null;
    if (!t) return;
    drawerExpanded = t.scrollTop > 4;
  }
  $: if (openDrawer === 'none') drawerExpanded = false;

  $: orderOf = (key: DrawerKey) => {
    const i = tabOrder.indexOf(key);
    return i === -1 ? 99 : i;
  };

  function toggle(key: 'none' | DrawerKey | 'legacy') {
    openDrawer = openDrawer === key ? 'none' : key;
  }
</script>

{#if openDrawer !== 'none'}
  <div class="drawer-backdrop" on:click={() => (openDrawer = 'none')} role="presentation"></div>
{/if}

<div class="drawer-stack" class:open={openDrawer !== 'none'} class:is-expanded={drawerExpanded}>
  <!-- Shared body: shows the active drawer's content. Hidden when closed. -->
  <div class="drawer-body" aria-hidden={openDrawer === 'none'} on:scroll|capture={onDrawerScroll}>
    {#if hasLayers}
      <div
        class="drawer-pane"
        class:active={openDrawer === 'layers'}
        style="order: {orderOf('layers')}"
      >
        <slot name="layers" />
      </div>
    {/if}
    {#if hasControls}
      <div
        class="drawer-pane"
        class:active={openDrawer === 'controls'}
        style="order: {orderOf('controls')}"
      >
        <slot name="controls" />
      </div>
    {/if}
    {#if hasBrowse}
      <div
        class="drawer-pane"
        class:active={openDrawer === 'browse'}
        style="order: {orderOf('browse')}"
      >
        <slot name="browse" />
      </div>
    {/if}
    {#if showLegacy}
      <div class="drawer-pane" class:active={openDrawer === 'legacy'}>
        <slot name="legacy" />
      </div>
    {/if}
  </div>

  <!-- Tab row: horizontal, equal-width. -->
  <div class="drawer-tabs" role="tablist">
    {#if hasLayers}
      <button
        type="button"
        class="drawer-tab"
        class:on={openDrawer === 'layers'}
        on:click={() => toggle('layers')}
        aria-pressed={openDrawer === 'layers'}
        style="order: {orderOf('layers')}"
        ><span aria-hidden="true">🗺️</span><span>Layers</span></button
      >
    {/if}
    {#if hasControls}
      <button
        type="button"
        class="drawer-tab"
        class:on={openDrawer === 'controls'}
        on:click={() => toggle('controls')}
        aria-pressed={openDrawer === 'controls'}
        style="order: {orderOf('controls')}"
        ><span aria-hidden="true">⚙️</span><span>Controls</span></button
      >
    {/if}
    {#if hasBrowse}
      <button
        type="button"
        class="drawer-tab"
        class:on={openDrawer === 'browse'}
        on:click={() => toggle('browse')}
        aria-pressed={openDrawer === 'browse'}
        style="order: {orderOf('browse')}"
        ><span aria-hidden="true">📋</span><span>Browse</span></button
      >
    {/if}
    {#if showLegacy}
      <button
        type="button"
        class="drawer-tab"
        class:on={openDrawer === 'legacy'}
        on:click={() => toggle('legacy')}
        aria-pressed={openDrawer === 'legacy'}
        ><span aria-hidden="true">📋</span><span>Tools</span></button
      >
    {/if}
  </div>
</div>

<style>
  .drawer-backdrop {
    position: absolute;
    inset: 0;
    background: var(--sb-scrim);
    z-index: 55;
    animation: db-fade 0.15s ease-out;
  }
  @keyframes db-fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .drawer-stack {
    --tab-h: clamp(40px, 7vh, 52px);
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 60;
    display: flex;
    flex-direction: column;
    pointer-events: auto;
    padding-bottom: env(safe-area-inset-bottom);
    background: transparent;
  }

  /* Shared body: collapses to 0 when no drawer open, defaults to 60vh
     when open. Expands to 90vh once the user scrolls inside it past the
     top — so the bottom sheet acts like a snap drawer without needing a
     drag handle. Closing or switching the drawer resets to default. */
  .drawer-body {
    max-height: 0;
    overflow: hidden;
    background: var(--ground);
    transition:
      max-height 0.25s ease,
      border-top-width 0.25s ease;
    border-top: 0 solid var(--rule);
    display: flex;
    flex-direction: column;
  }
  .drawer-stack.open .drawer-body {
    max-height: 60vh;
    border-top-width: 2px;
  }
  .drawer-stack.open.is-expanded .drawer-body {
    max-height: 90vh;
  }
  .drawer-pane {
    display: none;
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
  }
  .drawer-pane.active {
    display: flex;
    flex-direction: column;
  }
  /* Force scroll inside any wrapper that uses overflow:hidden (e.g. .mobile-pane). */
  .drawer-pane > :global(*) {
    overflow-y: auto;
    min-height: 0;
    -webkit-overflow-scrolling: touch;
  }

  /* Horizontal tab row. Equal-width, side-by-side. */
  .drawer-tabs {
    display: flex;
    flex-direction: row;
    height: var(--tab-h);
    background: var(--ground-raised);
    border-top: var(--rule-hair) solid var(--rule);
  }
  .drawer-tab {
    flex: 1 1 0;
    min-width: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
    padding: 0 var(--s-2);
    background: var(--ground-raised);
    border: none;
    border-left: 1.5px solid var(--rule);
    font: inherit;
    font-family: var(--font-body);
    font-weight: var(--w-semi);
    font-size: 0.82rem;
    color: var(--ink);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .drawer-tab:first-child {
    border-left: none;
  }
  .drawer-tab:active {
    background: var(--sb-bg);
  }
  .drawer-tab.on {
    background: var(--ink);
    color: var(--ground-raised);
  }
</style>
