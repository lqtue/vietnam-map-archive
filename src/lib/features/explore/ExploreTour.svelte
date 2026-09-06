<!--
  ExploreTour.svelte — driver.js coachmark sequence.

  Steps highlight the actual UI element they describe (Browse / Layers /
  Controls). On mobile, the matching drawer is opened automatically before
  the step shows. Auto-advance fires when the relevant store change is
  detected; users can also click Next manually. Final step is a
  "Got it" exit with a "Don't show again" checkbox.
-->
<script lang="ts" context="module">
  import { browser } from '$app/environment';
  const STORAGE_KEY = 'vma-explore-tour-ack-v1';

  export function shouldShowTour(): boolean {
    if (!browser) return false;
    try {
      return localStorage.getItem(STORAGE_KEY) !== 'true';
    } catch {
      return false;
    }
  }
  export function markTourAcked() {
    if (!browser) return;
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {}
  }
</script>

<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { driver, type Driver } from 'driver.js';
  import 'driver.js/dist/driver.css';
  import { layersStore } from '$lib/map/stores/layersStore';
  import type { Readable } from 'svelte/store';

  export let open = false;
  export let mapStore: Readable<{ lng: number; lat: number; zoom: number }>;
  export let layerStore: Readable<{ basemap: string; viewMode: string }>;
  export let isMobile = false;

  const dispatch = createEventDispatcher<{
    close: void;
    setDrawer: { drawer: 'none' | 'layers' | 'controls' | 'browse' };
  }>();

  type TourStep = {
    drawer: 'browse' | 'layers' | 'controls';
    desktopSel: string;
    mobileSel: string;
    title: string;
    body: string;
    detect: () => boolean; // returns true once the user has completed the action
  };

  // ── Baselines captured at the start of each step ────────────────
  let baseStackCount = 0;
  let baseOpacities = new Map<string, number>();
  let baseZoom = 0;
  let baseCenter: [number, number] = [0, 0];
  let baseBasemap = '';
  let baseViewMode = '';

  function captureBaseline() {
    const $l = $layersStore;
    const $m = $mapStore;
    const $ls = $layerStore;
    baseStackCount = $l.overlays.length;
    baseOpacities = new Map($l.overlays.map((o) => [o.id, o.opacity]));
    baseZoom = $m.zoom;
    baseCenter = [$m.lng, $m.lat];
    baseBasemap = $ls.basemap;
    baseViewMode = $ls.viewMode;
  }

  const TOUR_STEPS: TourStep[] = [
    {
      drawer: 'browse',
      desktopSel: '[data-tour="browse"]',
      mobileSel: '[data-tour="browse-mobile"]',
      title: 'Try it: add your first map',
      body: 'Tap the empty ⊕ circle on any row. It turns green ✓ and the historical map appears under your pointer.',
      detect: () => $layersStore.overlays.length > baseStackCount,
    },
    {
      drawer: 'layers',
      desktopSel: '[data-tour="layers"]',
      mobileSel: '[data-tour="layers-mobile"]',
      title: 'Try it: fade and zoom',
      body: 'Drag a row left or right to fade the overlay, or tap its name to zoom to it.',
      detect: () => {
        const opacityChanged = $layersStore.overlays.some(
          (o) => Math.abs((baseOpacities.get(o.id) ?? 1) - o.opacity) > 0.05
        );
        if (opacityChanged) return true;
        const $m = $mapStore;
        const zoomDelta = Math.abs($m.zoom - baseZoom);
        const dx = ($m.lng - baseCenter[0]) * 111000 * Math.cos(($m.lat * Math.PI) / 180);
        const dy = ($m.lat - baseCenter[1]) * 111000;
        return zoomDelta >= 1 || Math.hypot(dx, dy) > 100;
      },
    },
    {
      drawer: 'controls',
      desktopSel: '[data-tour="controls"]',
      mobileSel: '[data-tour="controls-mobile"]',
      title: 'Try it: change a control',
      body: 'Switch the basemap, change view mode (Stacked / Lens / Side-by-side), or jump to a place by name.',
      detect: () => {
        const $ls = $layerStore;
        return $ls.basemap !== baseBasemap || $ls.viewMode !== baseViewMode;
      },
    },
  ];

  let driverObj: Driver | null = null;
  let unsubLayers: (() => void) | null = null;
  let unsubMap: (() => void) | null = null;
  let unsubLayer: (() => void) | null = null;
  let advanceTimer: number | null = null;

  function selectorFor(s: TourStep): string {
    return isMobile ? s.mobileSel : s.desktopSel;
  }

  // We own step-tracking ourselves rather than relying on
  // driverObj.getActiveIndex(). The reason: driver.js's onHighlightStarted
  // fires async (after the popover renders), and a fast user can click the
  // ⊕ on the first row before that callback runs. If the baseline is
  // captured from the callback, baseStackCount sees the post-click value (1)
  // and the detect `overlays.length > baseStackCount` reads as 1 > 1 = false,
  // forcing the user to click a second time. Capturing eagerly here and
  // again just before moveNext() removes the race.
  let currentStep = 0;

  function applyStep(i: number) {
    currentStep = i;
    const s = TOUR_STEPS[i];
    if (!s) return;
    if (isMobile) dispatch('setDrawer', { drawer: s.drawer });
    captureBaseline();
  }

  function checkAutoAdvance() {
    if (!driverObj) return;
    const s = TOUR_STEPS[currentStep];
    if (!s || !s.detect()) return;
    if (advanceTimer) return;
    advanceTimer = window.setTimeout(() => {
      advanceTimer = null;
      if (!driverObj) return;
      if (currentStep >= TOUR_STEPS.length - 1) {
        finish();
        return;
      }
      // Capture baseline for the next step BEFORE moveNext, so any
      // subscriber-triggered detect during driver's render uses fresh
      // numbers instead of the previous step's.
      applyStep(currentStep + 1);
      driverObj.moveNext();
    }, 600);
  }

  function start() {
    if (driverObj) return;
    driverObj = driver({
      showProgress: true,
      progressText: 'Step {{current}} of {{total}}',
      // driver.js builds this overlay in JS, so it cannot read --scrim. Kept in
      // step with the darkroom surface by hand.
      overlayColor: 'rgba(8, 11, 12, 0.62)',
      stagePadding: 6,
      stageRadius: 12,
      animate: true,
      allowClose: true,
      doneBtnText: 'Got it',
      nextBtnText: 'Skip step →',
      prevBtnText: '← Back',
      showButtons: ['next', 'previous', 'close'],
      steps: TOUR_STEPS.map((s) => ({
        element: selectorFor(s),
        popover: {
          title: s.title,
          description: s.body,
          side: isMobile ? 'top' : 'left',
          align: 'start',
        },
      })),
      onDestroyStarted: () => finish(),
    });

    // Eager baseline for step 0 — wired BEFORE subscriptions so the
    // very first user action evaluates against the correct base value.
    applyStep(0);

    unsubLayers = layersStore.subscribe(() => checkAutoAdvance());
    unsubMap = mapStore.subscribe(() => checkAutoAdvance());
    unsubLayer = layerStore.subscribe(() => checkAutoAdvance());

    driverObj.drive();
  }

  function finish() {
    // Tour shown once per device — finishing it (completed or dismissed)
    // counts as ack. Returning users go straight to the map.
    markTourAcked();
    if (advanceTimer) {
      window.clearTimeout(advanceTimer);
      advanceTimer = null;
    }
    if (driverObj) {
      try {
        driverObj.destroy();
      } catch {}
    }
    driverObj = null;
    unsubLayers?.();
    unsubLayers = null;
    unsubMap?.();
    unsubMap = null;
    unsubLayer?.();
    unsubLayer = null;
    dispatch('close');
  }

  $: if (open && !driverObj) start();
  $: if (!open && driverObj) finish();

  onDestroy(() => finish());
</script>

<style>
  :global(.driver-popover) {
    border: var(--rule-hair) solid var(--rule) !important;
    border-radius: var(--radius) !important;
    box-shadow: none !important;
    font-family: var(--font-body) !important;
    background: var(--ground-raised) !important;
  }
  :global(.driver-popover-title) {
    font-family: var(--font-display) !important;
    font-weight: var(--w-semi) !important;
    font-size: 1.05rem !important;
    color: var(--ink) !important;
  }
  :global(.driver-popover-description) {
    font-size: 0.88rem !important;
    line-height: 1.45 !important;
    color: var(--ink-soft) !important;
  }
  :global(.driver-popover-progress-text) {
    color: var(--accent) !important;
    font-weight: var(--w-semi) !important;
  }
  :global(.driver-popover-navigation-btns button) {
    border: var(--rule-hair) solid var(--rule) !important;
    border-radius: var(--radius) !important;
    box-shadow: none !important;
    background: var(--ground-raised) !important;
    color: var(--ink) !important;
    font-weight: var(--w-semi) !important;
    text-shadow: none !important;
    padding: 0.45rem 0.8rem !important;
  }
  :global(.driver-popover-next-btn) {
    background: var(--accent) !important;
    color: var(--on-accent) !important;
  }
  :global(.driver-popover-close-btn) {
    color: var(--ink) !important;
  }
  /* The spotlight ring. driver.js is kept for this: a native popover gives the
     bubble but not the cutout, the anchoring or the store-driven auto-advance. */
  :global(.driver-active-element) {
    box-shadow: 0 0 0 4px var(--accent) !important;
  }
</style>
