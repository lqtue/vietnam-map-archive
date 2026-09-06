<!--
  DigitalizeSidebar.svelte — the whole /scan?mode=triage left panel:
  the phase-appropriate body plus the phase tabs in the footer.

  One component and one instance for both viewports: the page fills ToolLayout's
  `sidebar` slot, and ToolLayout renders it in the desktop rail or the mobile
  drawer, never both. `compact` (the slot prop) is the drawer variant — it
  shortens the OCR tab label and trims the Segmentation panel to its badge and
  command. So the `bind:ocrSidebar` handle the page keeps is never contested.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import OcrSidebar from '$lib/features/contribute/ocr/OcrSidebar.svelte';
  import ToolSidebarShell from '$lib/features/contribute/shared/ToolSidebarShell.svelte';
  import EmptyPanel from '$lib/features/contribute/shared/EmptyPanel.svelte';
  import TriageSidebar from './TriageSidebar.svelte';
  import SegSidebar from './SegSidebar.svelte';
  import PhaseTabs from './PhaseTabs.svelte';
  import type { SegConfig } from './segCommand';
  import type { TriageState, StoredTriage } from './triagePrefs';
  import type { PipelineStatus } from '$lib/features/contribute/pipelineApi';

  export let phase: 'triage' | 'ocr' | 'segmentation' = 'triage';
  export let mapId: string | null = null;
  export let imgWidth = 0;
  export let imgHeight = 0;
  export let iiifInfoUrl: string | null = null;
  /** Two-way: TriageSidebar and the canvas edit the same neatline / tile grid. */
  export let triage: TriageState;
  /** What `maps.triage` holds for the selected map, and the state of saving it. */
  export let savedTriage: StoredTriage | null = null;
  export let savingTriage = false;
  export let saveTriageError = '';
  export let suggesting = false;
  export let suggestError = '';
  /** The layout pass, bound so the canvas and the list share a selection. */
  export let selectedRegion: number | null = null;
  export let showRegions = true;
  export let detectingLayout = false;
  export let layoutError = '';
  export let layoutJob: { status: string; error?: string | null } | null = null;
  /** Run status for the Triage panel. */
  export let run: {
    running: boolean;
    error: string;
    queuedJobId: string | null;
    runs: Record<string, { n: number; categories: Record<string, number> }>;
  };
  export let pipeline: { status: PipelineStatus | null; loading: boolean; error: string };
  /** Two-way: the MapSAM2 command config the page persists. */
  export let segConfig: SegConfig;
  export let selectedId: string | null = null;
  export let compact = false;
  /** Bound by the page so it can call `load()` / `focusRow()` on the table. */
  export let ocrSidebar: OcrSidebar | undefined = undefined;

  export let onCollapse: (() => void) | null = null;

  const dispatch = createEventDispatcher<{ phaseChange: { phase: typeof phase } }>();
</script>

<ToolSidebarShell {onCollapse}>
  {#if !mapId}
    <EmptyPanel
      message={compact ? 'Select a map first.' : 'Pick a map to start.'}
      showIcon={!compact}
    />
  {:else if phase === 'triage'}
    <TriageSidebar
      {imgWidth}
      {imgHeight}
      {iiifInfoUrl}
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
      bind:showRegions
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
  {:else if phase === 'ocr'}
    <OcrSidebar
      bind:this={ocrSidebar}
      {mapId}
      {selectedId}
      on:loaded
      on:filter
      on:zoomToExtraction
    />
  {:else}
    <SegSidebar
      {mapId}
      status={pipeline.status}
      loading={pipeline.loading}
      error={pipeline.error}
      bind:config={segConfig}
      {compact}
      on:advance
      on:refresh
    />
  {/if}

  <svelte:fragment slot="footer">
    <PhaseTabs
      {phase}
      ocrLabel={compact ? 'OCR' : 'OCR Review'}
      on:change={(e) => dispatch('phaseChange', e.detail)}
    />
  </svelte:fragment>
</ToolSidebarShell>
