<!--
  /scan — the four IIIF-canvas tools behind one route, picked by `?mode=`:
  inspect (default, public read-only) · triage · trace · review.

  A dispatcher: a title and one component. Every tool's behaviour — staff
  gating included — stays in its own component under $lib/features/contribute/.
  The mode strip is rendered by the (app) layout, in the sheet's margin, and
  carries `?map=<id>` across a switch.
-->
<script lang="ts">
  import { page } from '$app/stores';
  import InspectPage from '$lib/features/contribute/inspect/InspectPage.svelte';
  import DigitalizePage from '$lib/features/contribute/digitalize/DigitalizePage.svelte';
  import TracePage from '$lib/features/contribute/trace/TracePage.svelte';
  import ReviewPage from '$lib/features/contribute/review/ReviewPage.svelte';

  type Mode = 'inspect' | 'triage' | 'trace' | 'review';

  const META: Record<Mode, [string, string]> = {
    inspect: [
      'Inspect a scan',
      'Read a historical map of Vietnam at full IIIF resolution, tile by tile.',
    ],
    triage: [
      'Triage & OCR',
      "Crop a sheet's neatline, set tile priorities, and check the place names the pipeline read off it.",
    ],
    trace: [
      'Trace footprints',
      'Outline buildings, roads and waterways on a georeferenced map. Every shape goes into the open dataset.',
    ],
    review: [
      'Review contributions',
      'Approve or reject the polygons SAM2 and volunteers submitted.',
    ],
  };

  // Unknown values fall back to inspect rather than rendering nothing.
  $: mode = ((): Mode => {
    const m = $page.url.searchParams.get('mode');
    return m && m in META ? (m as Mode) : 'inspect';
  })();
</script>

<svelte:head>
  <title>{META[mode][0]} — Vietnam Map Archive</title>
  <meta name="description" content={META[mode][1]} />
</svelte:head>

{#if mode === 'triage'}
  <DigitalizePage />
{:else if mode === 'trace'}
  <TracePage />
{:else if mode === 'review'}
  <ReviewPage />
{:else}
  <InspectPage />
{/if}
