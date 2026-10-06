<!--
  ScanLeftRail.svelte — the left rail every /scan mode carries: which sheet, and
  what is drawn over it.

  Those two answers are the same in all four modes, so they stop being each
  mode's business and become part of the page frame. Everything a *mode* does —
  the triage steps, the trace controls, the review queue — moves to the right
  sidebar. That is what lets a mode change swap one panel instead of rebuilding
  the page, and it puts the sheet list somewhere other than on top of the sheet.

  It is built from the same two pieces as `ExploreSidebar`: a `.sb-bar` crown
  (via `ToolSidebarShell`) over `SidebarCard`s, with the same titles — "Browse
  the archive" and "My layers". The body used to be a bare picker over flat
  section strips, which is what made the /scan rail read as a different
  component from the /explore one even though both crowns were already the same
  rule set. There is no draggable splitter here: the layers card is two or three
  rows, so there is nothing to trade height with.

  `mode` puts the mode switcher in the rail's footer, one place for all three
  staff modes. Left unset — which is how `?mode=inspect` mounts it — there is no
  switcher: inspect is the public read-only mode and the other three want a
  session, so an anonymous reader is not offered three doors that ask for one.

  Slots:
    default — extra cards under Layers, for a mode with left-rail content of
              its own. Wrap it in a `SidebarCard` to match the two above.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import ToolSidebarShell from './ToolSidebarShell.svelte';
  import ToolMapPicker from './ToolMapPicker.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import SidebarCard from '$lib/features/shared/SidebarCard.svelte';
  import type { LabelMapInfo } from '$lib/data/supabase/footprints';
  import '$styles/layouts/tool-page.css';

  export let selectedMapId: string | null = null;
  /** Caller-supplied map list; see `ToolMapPicker`. Null means "load them all". */
  export let maps: LabelMapInfo[] | null = null;
  /** Only maps that can be laid on the world; see `ToolMapPicker`. */
  export let requireGeoref = true;
  /** How many of the filters the caller adds (slot `filters`) are set. */
  export let extraActive = 0;
  /** One switchable thing drawn over the scan. `color` draws the swatch that
   *  ties the row to what is on the canvas. */
  export let layers: { id: string; label: string; on: boolean; color?: string }[] = [];
  /** Opacity of the scan under the overlays. Dimming the paper is how a tile
   *  grid becomes readable over dense ink. */
  export let imageOpacity = 1;
  export let onCollapse: (() => void) | null = null;
  /** Which /scan mode is open, for the footer switcher. '' hides it. */
  export let mode: 'prepare' | 'text' | 'shapes' | '' = '';

  const SCAN_MODES = [
    { key: 'prepare', label: 'Prepare', href: '/scan?mode=prepare' },
    { key: 'text', label: 'Text', href: '/scan?mode=text' },
    { key: 'shapes', label: 'Shapes', href: '/scan?mode=shapes' },
  ];

  const dispatch = createEventDispatcher<{
    select: { map: LabelMapInfo };
    loaded: { maps: LabelMapInfo[] };
    error: { message: string };
    toggle: { id: string; on: boolean };
  }>();
</script>

<ToolSidebarShell title="Map" {onCollapse} showFooter={!!mode}>
  <div class="rail-cards">
    <SidebarCard grow={1} flush={true}>
      <ToolMapPicker
        {selectedMapId}
        {maps}
        {requireGeoref}
        {extraActive}
        on:select
        on:loaded
        on:error
      >
        <slot name="filters" slot="filters" />
      </ToolMapPicker>
    </SidebarCard>

    <!-- Fixed height, not a share of the rail: this card is a handful of rows and
       the picker is the list that wants the space. -->
    <SidebarCard title="My layers" grow={0} flush={true} scroll={false} padded={true}>
      {#each layers as l (l.id)}
        <label class="rail-layer">
          <input
            type="checkbox"
            checked={l.on}
            on:change={(e) => dispatch('toggle', { id: l.id, on: e.currentTarget.checked })}
          />
          {#if l.color}
            <span class="rail-swatch" style="background: {l.color}"></span>
          {/if}
          <span class="rail-layer-name">{l.label}</span>
        </label>
      {/each}

      <!-- Always shown, even with nothing over the scan: a mode that draws
         nothing (trace) still wants to dim the paper. -->
      <label class="rail-opacity">
        <span class="sb-section-label">Scan</span>
        <input type="range" min="0.15" max="1" step="0.05" bind:value={imageOpacity} />
        <span class="rail-value">{Math.round(imageOpacity * 100)}%</span>
      </label>
    </SidebarCard>

    <!-- Bare, not wrapped: a caller whose extra row is conditional would
         otherwise leave an empty card sitting at the foot of the rail. Pass a
         `SidebarCard` if you want one. -->
    <slot />
  </div>

  <svelte:fragment slot="footer">
    <Tabs tone="rail" label="Scan modes" tabs={SCAN_MODES} active={mode} />
  </svelte:fragment>
</ToolSidebarShell>

<style>
  /* `.sb-card.is-flush` drops the card margin so the cards run edge to edge, as
     they do on /explore; the gap stands in for that rail's splitter. */
  .rail-cards {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding-bottom: 0.35rem;
  }

  .rail-layer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.8rem;
  }
  .rail-swatch {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
    box-shadow: 0 0 0 1px var(--color-border);
  }
  .rail-layer-name {
    flex: 1;
    min-width: 0;
  }
  .rail-opacity {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .rail-opacity input[type='range'] {
    flex: 1;
    min-width: 0;
  }
  .rail-value {
    font-family: ui-monospace, monospace;
    font-size: 0.72rem;
    color: var(--sb-text-meta);
    min-width: 3ch;
    text-align: right;
  }
</style>
