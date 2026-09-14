<script lang="ts">
  /*
    /scan — the ImageShell surface, mode chosen by `?mode=`.

      /scan?mode=prepare    layout · neatline · tile grid · save · queue OCR
      /scan?mode=text       check what came back: Names · Index · Numbers · Other
      /scan?mode=shapes     draw · segment · validate
      /scan?mode=inspect    unlisted — a plain look at a draft scan

    These all mount ImageShell on the same IIIF canvas in pixel coordinates, so
    grouping them by shell keeps the canvas, the level0 tile source and the map
    picker warm across a mode change instead of rebuilding them.

    **There is no default mode any more.** `/scan` with no mode, and any mode
    this shell does not serve, belong at /catalog — `hooks.server.ts` sends them
    there before anything renders, and `resolveScanMode` is the list both it and
    this file read. The `goto` below is the client-side half: a same-app
    navigation never reaches the server hook.

    Prepare and Text are ONE component on purpose: the `{#if}` covers both, so
    moving between them is a prop change and the open sheet and the canvas
    survive it.

    Each mode owns its own <svelte:head> and its own role gate, so there is
    nothing to wire here. As on /explore there is no mode strip: the tool roots
    fill the viewport from a fixed layer, and a sibling strip would render
    behind them — the switcher is the left rail's footer.
  */
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { resolveScanMode } from '$lib/core/scanModes';
  import InspectPage from '$lib/features/contribute/inspect/InspectPage.svelte';
  import DigitalizePage from '$lib/features/contribute/digitalize/DigitalizePage.svelte';
  import ShapesPage from '$lib/features/contribute/trace/ShapesPage.svelte';

  $: mode = resolveScanMode($page.url.searchParams.get('mode'));

  // The one old link that does not land in a /scan mode at all: the story queue
  // has no sheet and no canvas, and moved to /admin with the other queues.
  $: isStoryQueue =
    $page.url.searchParams.get('mode') === 'review' &&
    $page.url.searchParams.get('kind') === 'stories';

  $: if (isStoryQueue) goto('/admin?tab=stories', { replaceState: true });
  else if (!mode) goto(catalogHref($page.url.searchParams.get('map')), { replaceState: true });

  /** A sheet asked for by id keeps its identity across the move. */
  function catalogHref(mapId: string | null): string {
    return mapId ? `/catalog/${encodeURIComponent(mapId)}` : '/catalog';
  }
</script>

{#if mode === 'prepare' || mode === 'text'}
  <DigitalizePage {mode} />
{:else if mode === 'shapes'}
  <ShapesPage />
{:else if mode === 'inspect'}
  <InspectPage />
{/if}
