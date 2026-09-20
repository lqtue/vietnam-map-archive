<script lang="ts">
  /*
    /explore — the MapShell surface, mode chosen by `?mode=`.

    Browse, studio and author-a-story were /explore, /studio and /create:
    three routes that each built the same OpenLayers map, the same basemap
    sources and the same warped-tile pipeline, then tore it all down on the way
    to the next one. Grouping them by shell rather than by verb is what lets
    that stay warm across a mode switch.

    There is no mode strip here on purpose. Each mode's root fills the viewport
    with `position: fixed; inset: var(--nav-height) 0 0 0`, so a strip rendered
    beside it would sit *behind* the map — invisible and unclickable. Mode
    switching is in NavBar, which is outside the fixed layer.
  */
  import { page } from '$app/stores';
  import { resolveExploreMode } from '$lib/core/routeModes';
  import ExplorePage from '$lib/features/explore/ExplorePage.svelte';
  import StudioMode from '$lib/features/annotate/AnnotateMode.svelte';
  import CreateMode from '$lib/features/stories/editor/CreateMode.svelte';

  /* `?mode=annotate` is the name this mode shipped under and is still live in
     share links, bookmarks and the wild, so it stays an alias rather than a
     404 or a silent fall-through to browse. `studio` is what the UI says. */
  $: mode = resolveExploreMode($page.url.searchParams.get('mode')) ?? 'browse';

  /* From the /studio and /create routes this replaced. The browse title and
     viewport meta stay in ExplorePage, which owns them. */
  const HEAD = {
    studio: {
      title: 'Studio — Vietnam Map Archive',
      description:
        'Draw and annotate historical maps of Vietnam. Create points, lines, and polygons to mark places of interest.',
    },
    story: {
      title: 'Create — Vietnam Map Archive',
      description:
        'Create guided stories and adventures on historical maps of Vietnam. Place points, configure challenges, and share your creations.',
    },
  } as const;
  $: head = mode === 'studio' ? HEAD.studio : mode === 'story' ? HEAD.story : null;
</script>

<svelte:head>
  {#if head}
    <title>{head.title}</title>
    <meta name="description" content={head.description} />
  {/if}
</svelte:head>

{#if mode === 'studio'}
  <StudioMode />
{:else if mode === 'story'}
  <CreateMode />
{:else}
  <ExplorePage />
{/if}
