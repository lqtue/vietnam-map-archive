<!--
  /explore — the one MapShell route.

  Browse, annotate and story authoring used to be /explore, /studio and
  /create. Each mounted its own MapShell, so moving between them tore down the
  OpenLayers map, the PMTiles basemap and every warped tile and rebuilt them.
  They are modes of this page now, chosen by `?mode=`, and the map stays warm.

  Dispatcher only: title and an `{#if}` chain. The mode strip is rendered by
  the (app) layout, in the sheet's margin.
-->
<script lang="ts">
  import { page } from '$app/stores';

  import ExplorePage from '$lib/features/explore/ExplorePage.svelte';
  import StudioMode from '$lib/features/studio/StudioMode.svelte';
  import CreateMode from '$lib/features/stories/editor/CreateMode.svelte';

  type Mode = 'browse' | 'annotate' | 'story';

  const MODES: { id: Mode; label: string; title: string; description: string }[] = [
    {
      id: 'browse',
      label: 'Browse',
      title: 'Explore — Vietnam Map Archive',
      description:
        'Browse georeferenced historical maps of Saigon and Vietnam, stack them over the modern city, and play guided stories.',
    },
    {
      id: 'annotate',
      label: 'Annotate',
      title: 'Studio — Vietnam Map Archive',
      description:
        'Draw and annotate historical maps of Vietnam. Create points, lines, and polygons to mark places of interest.',
    },
    {
      id: 'story',
      label: 'Story',
      title: 'Create — Vietnam Map Archive',
      description:
        'Create guided stories and adventures on historical maps of Vietnam. Place points, configure challenges, and share your creations.',
    },
  ];

  // Unknown values fall back to browse rather than rendering nothing.
  $: meta = MODES.find((m) => m.id === $page.url.searchParams.get('mode')) ?? MODES[0];
  $: mode = meta.id;
</script>

<svelte:head>
  <title>{meta.title}</title>
  <meta name="description" content={meta.description} />
</svelte:head>

{#if mode === 'annotate'}
  <StudioMode />
{:else if mode === 'story'}
  <CreateMode />
{:else}
  <ExplorePage />
{/if}
