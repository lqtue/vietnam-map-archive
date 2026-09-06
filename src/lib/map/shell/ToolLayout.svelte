<!--
  ToolLayout.svelte — responsive shell for map tool pages.

  Desktop (≥ 901px):
    [sidebar slot]  [resize handle]  [map-stage]

  Mobile (< 900px):
    Full-screen map with stacked labeled MobileDrawers at the bottom.
    Only one drawer is open at a time. Tabs always visible; tap to expand.

  Slots:
    sidebar           — desktop left panel
    right-sidebar     — desktop right panel (e.g. /explore?mode=story story+point editor)
    default           — map content
    floating          — bottom-right controls
    mobile-layers     — mobile drawer 1 body  (label: "Layers")
    mobile-controls   — mobile drawer 2 body  (label: "Controls")
    mobile-browse     — mobile drawer 3 body  (label: "Browse")
    mobile-sidebar    — legacy fallback (single drawer, label: "Tools")

  A tool that only fills `sidebar` gets that same slot in the mobile drawer,
  with `let:compact` true — one component instance, since the desktop rail and
  the drawer are never mounted at the same time. Fill `mobile-sidebar` only
  when mobile genuinely needs different content.
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import MobileDrawerStack from './MobileDrawerStack.svelte';
  import '$styles/layouts/mode-shared.css';

  export let sidebarCollapsed = false;
  export let isMobile = false;
  export let isCompact = false;
  /** Initial / current width of the desktop sidebar. Bindable so callers (e.g. /explore?mode=story) can set a wider default. */
  export let sidebarWidth = 320;
  /** Max draggable width of the sidebar. /explore?mode=story bumps this so its 2-column sidebar fits. */
  export let sidebarMaxWidth = 600;
  /** Width of the optional right sidebar (only rendered when its slot has content). */
  export let rightSidebarWidth = 360;
  /** Max draggable width of the right sidebar. */
  export let rightSidebarMaxWidth = 560;
  /** Collapsed state of the right sidebar. */
  export let rightSidebarCollapsed = false;
  /** Caller-side hint that the right-sidebar slot is actually populated.
      Required because Svelte's `$$slots` is truthy whenever a parent forwards a
      <slot> tag, even if its own parent provided no content. */
  export let hasRightSidebar = false;

  /** Mobile tab order. Defaults to the historical Layers/Controls/Browse
      order; routes that want a different default (e.g. /explore = browse
      first) pass their own. */
  export let tabOrder: Array<'layers' | 'controls' | 'browse'> = ['layers', 'controls', 'browse'];

  /** Mobile: which drawer is open. Exposed so a parent (e.g. the
      /explore tour) can programmatically switch tabs. */
  export let openDrawer: 'none' | 'layers' | 'controls' | 'browse' | 'legacy' = 'none';

  // ── Sidebar resizing (desktop) ───────────────────────────────
  let resizing: 'left' | 'right' | null = null;

  function startResizingLeft() {
    startResizing('left');
  }
  function startResizingRight() {
    startResizing('right');
  }
  function startResizing(side: 'left' | 'right') {
    resizing = side;
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', stopResizing);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }
  function handleMouseMove(e: MouseEvent) {
    if (!resizing) return;
    // Workspace now sits flush against the viewport edges (no padding), so the
    // handle's x coordinate is simply the cursor distance from the edge.
    if (resizing === 'left') {
      sidebarWidth = Math.max(260, Math.min(sidebarMaxWidth, e.clientX));
    } else {
      rightSidebarWidth = Math.max(
        260,
        Math.min(rightSidebarMaxWidth, window.innerWidth - e.clientX)
      );
    }
  }
  function stopResizing() {
    resizing = null;
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', stopResizing);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }

  // ── Responsive breakpoints ───────────────────────────────────
  let responsiveCleanup: (() => void) | null = null;
  onMount(() => {
    const mobileQuery = window.matchMedia('(max-width: 900px)');
    const compactQuery = window.matchMedia('(max-width: 1280px)');
    const update = () => {
      isMobile = mobileQuery.matches;
      isCompact = compactQuery.matches;
    };
    update();
    mobileQuery.addEventListener('change', update);
    compactQuery.addEventListener('change', update);
    responsiveCleanup = () => {
      mobileQuery.removeEventListener('change', update);
      compactQuery.removeEventListener('change', update);
    };
  });

  onDestroy(() => {
    responsiveCleanup?.();
    stopResizing();
  });

  $: hasSidebar = !!$$slots.sidebar;
  $: hasMobileLayers = !!$$slots['mobile-layers'];
  $: hasMobileControls = !!$$slots['mobile-controls'];
  $: hasMobileBrowse = !!$$slots['mobile-browse'];
  $: hasMobileSidebar = !!$$slots['mobile-sidebar'];
  /** No `mobile-sidebar` of its own: the drawer reuses the `sidebar` slot. */
  $: mobileUsesSidebar = hasSidebar && !hasMobileSidebar;
  $: hasLegacyDrawer = hasMobileSidebar || mobileUsesSidebar;
  $: hasAnyDrawer = hasMobileLayers || hasMobileControls || hasMobileBrowse || hasLegacyDrawer;
  $: showDesktopSidebar = hasSidebar && !sidebarCollapsed && !isMobile;
  $: showRightSidebar = hasRightSidebar && !rightSidebarCollapsed && !isMobile;
</script>

<div
  class="workspace"
  class:with-sidebar={showDesktopSidebar}
  class:with-right-sidebar={showRightSidebar}
  class:compact={isCompact}
  class:mobile={isMobile}
  style="--sidebar-width: {sidebarWidth}px; --right-sidebar-width: {rightSidebarWidth}px"
>
  {#if showDesktopSidebar}
    <div class="sidebar-slot">
      <slot name="sidebar" compact={false} />
    </div>
    <div class="resize-handle" on:mousedown={startResizingLeft} role="presentation"></div>
  {/if}

  <div class="map-stage">
    <slot />

    {#if sidebarCollapsed && !isMobile && hasSidebar}
      <div class="top-controls">
        <button
          type="button"
          class="ctrl-btn"
          on:click={() => (sidebarCollapsed = false)}
          title="Show panel"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" />
          </svg>
        </button>
      </div>
    {/if}

    {#if rightSidebarCollapsed && !isMobile && hasRightSidebar}
      <div class="right-controls">
        <button
          type="button"
          class="ctrl-btn"
          on:click={() => (rightSidebarCollapsed = false)}
          title="Show editor"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M15 3v18" />
          </svg>
        </button>
      </div>
    {/if}

    {#if $$slots.floating}
      <div class="floating-controls">
        <slot name="floating" />
      </div>
    {/if}
  </div>

  {#if showRightSidebar}
    <div
      class="resize-handle resize-handle-right"
      on:mousedown={startResizingRight}
      role="presentation"
    ></div>
    <div class="right-sidebar-slot">
      <slot name="right-sidebar" />
    </div>
  {/if}

  {#if isMobile && hasAnyDrawer}
    <MobileDrawerStack
      bind:openDrawer
      {tabOrder}
      hasLayers={hasMobileLayers}
      hasControls={hasMobileControls}
      hasBrowse={hasMobileBrowse}
      hasLegacy={hasLegacyDrawer}
    >
      <slot name="mobile-layers" slot="layers" />
      <slot name="mobile-controls" slot="controls" />
      <slot name="mobile-browse" slot="browse" />
      <svelte:fragment slot="legacy">
        {#if hasMobileSidebar}
          <slot name="mobile-sidebar" />
        {:else}
          <slot name="sidebar" compact={true} />
        {/if}
      </svelte:fragment>
    </MobileDrawerStack>
  {/if}
</div>

<style>
  .sidebar-slot {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .right-sidebar-slot {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .resize-handle {
    position: absolute;
    top: 0;
    bottom: 0;
    left: var(--sidebar-width);
    width: 8px;
    margin-left: -4px;
    cursor: col-resize;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .resize-handle.resize-handle-right {
    left: auto;
    right: var(--right-sidebar-width);
    margin-left: 0;
    margin-right: -4px;
  }
  /* Visible grip: two short bars rendered via SVG-like CSS so the affordance
     is obvious without needing hover discovery. */
  .resize-handle::before,
  .resize-handle::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 3px;
    height: 28px;
    background: var(--ink);
    border-radius: 2px;
    transition: all 0.15s ease;
    box-shadow: 0 0 0 1px var(--ground-raised);
  }
  .resize-handle::before {
    transform: translate(-5px, -50%);
  }
  .resize-handle::after {
    transform: translate(2px, -50%);
  }
  .resize-handle:hover::before,
  .resize-handle:hover::after {
    background: var(--sb-accent);
    height: 36px;
  }
  .workspace:not(.with-sidebar) .resize-handle:not(.resize-handle-right) {
    display: none;
  }
  .workspace:not(.with-right-sidebar) .resize-handle-right {
    display: none;
  }

  /* Floating "show editor" pill (mirror of .top-controls but right-anchored). */
  .right-controls {
    position: absolute;
    top: var(--s-4);
    right: var(--s-4);
    z-index: 50;
  }
</style>
