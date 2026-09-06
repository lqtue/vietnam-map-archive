<script context="module" lang="ts">
  export type Snap = 'peek' | 'mid' | 'full';

  /** Default heights for the three snap points. */
  export const DEFAULT_SNAP_HEIGHTS: Record<Snap, string> = {
    peek: 'clamp(76px, 10vh, 104px)',
    mid: '46vh',
    full: '82vh',
  };
</script>

<!--
  SnapSheet.svelte — bottom sheet with three snap points (peek / mid / full).

  Drag the grip up or down to step between snap points; tapping the header
  cycles peek → mid → full → peek. The body is hidden at `peek`, so the header
  doubles as a collapsed summary bar.

  Slots: `head` (rendered under the grip) and the default slot (the body).
  Bind `snap` to drive or observe the current snap point; `locked` freezes both
  the drag and the tap-to-cycle.
-->
<script lang="ts">
  /** Current snap point — bindable. */
  export let snap: Snap = 'peek';
  /** CSS height per snap point; also exposed to the sheet as --sheet-height. */
  export let heights: Record<Snap, string> = DEFAULT_SNAP_HEIGHTS;
  /** When true the sheet stays where it is: no drag, no tap-to-cycle. */
  export let locked = false;
  export let label = 'Sheet';
  export let toggleLabel = 'Expand or collapse the sheet';

  /** Drag distance (px) that commits to the next snap point. */
  const DRAG_THRESHOLD = 60;
  const ORDER: Snap[] = ['peek', 'mid', 'full'];

  $: sheetHeight = heights[snap];

  let dragStartY = 0;
  let dragStartSnap: Snap = 'peek';
  let dragging = false;

  function snapFromDelta(start: Snap, deltaPx: number): Snap {
    // negative delta = drag up = bigger sheet
    const idx = ORDER.indexOf(start);
    if (deltaPx < -DRAG_THRESHOLD && idx < ORDER.length - 1) return ORDER[idx + 1];
    if (deltaPx > DRAG_THRESHOLD && idx > 0) return ORDER[idx - 1];
    return start;
  }

  function onGripPointerDown(e: PointerEvent) {
    if (locked) return;
    dragging = true;
    dragStartY = e.clientY;
    dragStartSnap = snap;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onGripPointerUp(e: PointerEvent) {
    if (!dragging) return;
    dragging = false;
    snap = snapFromDelta(dragStartSnap, e.clientY - dragStartY);
  }

  function toggleSnap() {
    if (locked) return;
    snap = snap === 'peek' ? 'mid' : snap === 'mid' ? 'full' : 'peek';
  }
</script>

<section
  class="sheet"
  class:peek={snap === 'peek'}
  class:mid={snap === 'mid'}
  class:full={snap === 'full'}
  style="--sheet-height: {sheetHeight}"
  data-snap={snap}
  aria-label={label}
>
  <!-- Grip / header is also the tap-target to expand. -->
  <header
    class="sheet-head"
    on:pointerdown={onGripPointerDown}
    on:pointerup={onGripPointerUp}
    on:click={(e) => {
      // Don't toggle when the click came from a header button.
      if ((e.target as HTMLElement).closest('button')) return;
      toggleSnap();
    }}
    on:keydown={(e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      if ((e.target as HTMLElement).closest('button')) return;
      e.preventDefault();
      toggleSnap();
    }}
    role="button"
    tabindex="0"
    aria-label={toggleLabel}
  >
    <div class="grip" aria-hidden="true"></div>
    <slot name="head" />
  </header>

  <div class="sheet-body">
    <slot />
  </div>
</section>

<style>
  .sheet {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: var(--sheet-height);
    background: var(--sb-card-bg);
    border-top: var(--rule-hair) solid var(--rule);
    border-radius: 18px 18px 0 0;
    box-shadow: 0 -6px 0 color-mix(in srgb, var(--ink) 9%, transparent);
    z-index: 100;
    color: var(--sb-text);
    font-family: var(--sb-font-base);
    transition: height 0.3s cubic-bezier(0.22, 0.61, 0.36, 1);
    display: flex;
    flex-direction: column;
    pointer-events: auto;
    overflow: hidden;
  }

  .sheet-head {
    flex-shrink: 0;
    padding: 0.45rem 1rem 0.7rem;
    border-bottom: var(--rule-hair) solid var(--rule);
    cursor: pointer;
    user-select: none;
    touch-action: none; /* let pointermove on the grip work on touch */
  }
  .grip {
    width: 38px;
    height: 4px;
    margin: 0.25rem auto 0.55rem;
    background: color-mix(in srgb, var(--ink) 20%, transparent);
    border-radius: 99px;
  }

  .sheet-body {
    flex: 1;
    overflow-y: auto;
    padding: 0.85rem 1rem calc(env(safe-area-inset-bottom) + 1rem);
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }
  .sheet.peek .sheet-body {
    display: none;
  }
</style>
