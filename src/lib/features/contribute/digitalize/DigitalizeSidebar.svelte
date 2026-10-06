<!--
  DigitalizeSidebar.svelte — the right panel of /scan?mode=prepare and
  ?mode=text: the steps in one, the review table in the other.

  One component and one instance for both viewports: the page fills ToolLayout's
  `right-sidebar` slot, and ToolLayout renders it in the desktop rail or the
  mobile drawer, never both. `compact` (the slot prop) is the drawer variant. So
  the `bind:ocrSidebar` handle the page keeps is never contested.

  The mode switcher is the left rail's footer, not this panel's: it belongs to
  the page frame, beside the sheet list that also does not change with the mode.
  This panel's footer carries the four reading jobs instead — Names · Index ·
  Numbers · Other, each badged with how many rows it holds. See `ocr/jobs.ts`.
-->
<script lang="ts">
  import OcrSidebar from '$lib/features/contribute/ocr/OcrSidebar.svelte';
  import TextReviewedMark from '$lib/features/contribute/ocr/TextReviewedMark.svelte';
  import ToolSidebarShell from '$lib/features/contribute/shared/ToolSidebarShell.svelte';
  import EmptyPanel from '$lib/features/contribute/shared/EmptyPanel.svelte';
  import TriageSidebar from './TriageSidebar.svelte';
  import type { TriageState } from './triagePrefs';
  import type { OcrReviewController } from '../ocr/ocrReviewController';
  import type { SavedTriage } from '$lib/data/maps/triageTypes';

  export let mode: 'prepare' | 'text' = 'prepare';
  export let mapId: string | null = null;
  export let imgWidth = 0;
  export let imgHeight = 0;
  /** Two-way: TriageSidebar and the canvas edit the same neatline / tile grid. */
  export let triage: TriageState;
  /** What `maps.triage` holds for the selected map, and the state of saving it. */
  export let savedTriage: SavedTriage | null = null;
  export let savingTriage = false;
  export let saveTriageError = '';
  export let suggesting = false;
  export let suggestError = '';
  /** The layout pass, bound so the canvas and the list share a selection. */
  export let selectedRegion: number | null = null;
  export let detectingLayout = false;
  export let layoutError = '';
  export let layoutJob: { status: string; error?: string | null } | null = null;
  /** Run status for the Prepare panel. */
  export let run: {
    running: boolean;
    error: string;
    queuedJobId: string | null;
    runs: Record<string, { n: number; categories: Record<string, number> }>;
  };
  export let selectedId: string | null = null;
  export let review: OcrReviewController;
  export let compact = false;
  /** Bound by the page so it can call `load()` / `focusRow()` on the table. */
  export let ocrSidebar: OcrSidebar | undefined = undefined;

  export let onCollapse: (() => void) | null = null;
</script>

<ToolSidebarShell title={mode === 'text' ? 'Text' : 'Prepare'} {onCollapse}>
  {#if !mapId}
    <EmptyPanel
      message={compact ? 'Select a map first.' : 'Pick a map to start.'}
      showIcon={!compact}
    />
  {:else if mode === 'prepare'}
    <TriageSidebar
      {imgWidth}
      {imgHeight}
      bind:neatline={triage.neatline}
      bind:tileSize={triage.tileSize}
      bind:overlap={triage.overlap}
      bind:runId={triage.runId}
      bind:minConfidence={triage.minConfidence}
      tileOverrides={triage.tileOverrides}
      ocrRunning={run.running}
      ocrError={run.error}
      queuedJobId={run.queuedJobId}
      runs={run.runs}
      {savedTriage}
      {savingTriage}
      {saveTriageError}
      {suggesting}
      {suggestError}
      layoutRegions={triage.regions}
      bind:selectedRegion
      {detectingLayout}
      {layoutError}
      {layoutJob}
      on:runOcr
      on:saveTriage
      on:suggestTriage
      on:detectLayout
      on:regionsChange
      on:selectRegion
      on:loadRun
    />
  {:else}
    <OcrSidebar
      bind:this={ocrSidebar}
      {mapId}
      {review}
      {selectedId}
      regions={triage.regions}
      on:loaded
      on:filter
      on:regionFocus
      on:zoomToExtraction
      on:select
    />
    <TextReviewedMark {mapId} />
  {/if}
</ToolSidebarShell>
