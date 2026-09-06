<script lang="ts">
  import { onMount } from 'svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchMaps, fetchFeaturedMaps } from '$lib/data/maps/service';
  import { annotationUrlForSource } from '$lib/map/shell/warpedOverlay';
  import { fetchFavorites, addFavorite, removeFavorite } from '$lib/data/supabase/favorites';
  import MapCard from '$lib/ui/MapCard.svelte';
  import HeroRegistration from '$lib/features/explore/HeroRegistration.svelte';

  const { supabase, session } = getSupabaseContext();

  let mounted = false;
  let maps: MapListItem[] = [];
  let featuredMaps: MapListItem[] = [];
  let loading = true;
  let thumbnails: Map<string, string> = new Map();
  let selectedFeaturedCity: string = 'all';
  let favoriteIds: string[] = [];
  let filterCollection: 'featured' | 'favorites' = 'featured';

  // sessionStorage cache so a 404 (un-georeferenced map) isn't refetched on reload
  const THUMB_CACHE_KEY = 'vma-thumb-cache-v1';
  function readThumbCache(): Record<string, string | null> {
    try {
      return JSON.parse(sessionStorage.getItem(THUMB_CACHE_KEY) ?? '{}');
    } catch {
      return {};
    }
  }
  function writeThumbCache(id: string, value: string | null): void {
    try {
      const c = readThumbCache();
      c[id] = value;
      sessionStorage.setItem(THUMB_CACHE_KEY, JSON.stringify(c));
    } catch {}
  }

  // Fetch IIIF thumbnail URL from Allmaps annotation
  async function fetchThumbnailUrl(mapId: string): Promise<string | null> {
    if (!mapId) return null;
    const cache = readThumbCache();
    if (Object.prototype.hasOwnProperty.call(cache, mapId)) return cache[mapId];
    try {
      const response = await fetch(annotationUrlForSource(mapId));
      if (!response.ok) {
        writeThumbCache(mapId, null);
        return null;
      }

      const annotation = await response.json();
      const items = annotation.items;
      const source = items?.[0]?.target?.source;
      if (!source?.id) {
        writeThumbCache(mapId, null);
        return null;
      }

      const url = `${source.id}/full/,400/0/default.jpg`;
      writeThumbCache(mapId, url);
      return url;
    } catch {
      writeThumbCache(mapId, null);
      return null;
    }
  }

  async function loadMapCatalog() {
    try {
      const [allMaps, featured] = await Promise.all([
        fetchMaps(supabase),
        fetchFeaturedMaps(supabase),
      ]);

      maps = allMaps;
      featuredMaps = featured.length > 0 ? featured : allMaps.slice(0, 6);

      if (session?.user?.id) {
        const favs = await fetchFavorites(supabase, session.user.id);
        favoriteIds = favs || [];
      }

      loading = false;

      const fetchPromises = maps.map(async (map) => {
        // Only fetch thumbnails for what might be visible, and only if
        // the DB doesn't already have one (skips 404s on un-georeferenced maps).
        const visible = featuredMaps.some((m) => m.id === map.id) || favoriteIds.includes(map.id);
        const source = map.annotation_url ?? map.allmaps_id;
        if (!visible || map.thumbnail || !source) return;
        const url = await fetchThumbnailUrl(source);
        if (url) {
          thumbnails.set(map.id, url);
          thumbnails = thumbnails;
        }
      });
      await Promise.all(fetchPromises);
    } catch (err) {
      console.error('Failed to load map catalog:', err);
    } finally {
      loading = false;
    }
  }

  async function toggleFavorite(mapId: string) {
    if (!session?.user?.id) return;
    const userId = session.user.id;
    const wasFavorited = favoriteIds.includes(mapId);

    // Optimistic update: use array reassignment for guaranteed Svelte reactivity
    if (wasFavorited) {
      favoriteIds = favoriteIds.filter((id) => id !== mapId);
    } else {
      favoriteIds = [...favoriteIds, mapId];
    }

    // Persist
    const success = wasFavorited
      ? await removeFavorite(supabase, userId, mapId)
      : await addFavorite(supabase, userId, mapId);

    // Revert on failure
    if (!success) {
      if (wasFavorited) {
        favoriteIds = [...favoriteIds, mapId];
      } else {
        favoriteIds = favoriteIds.filter((id) => id !== mapId);
      }
    }
  }

  // Get unique cities from maps
  $: cities = Array.from(new Set(maps.map((m) => m.location).filter(Boolean))).sort();

  // Get unique cities from featured maps
  $: featuredCities = Array.from(
    new Set(featuredMaps.map((m) => m.location).filter(Boolean))
  ).sort();

  // Filter featured maps by selected city
  $: displayedFeaturedMaps =
    selectedFeaturedCity === 'all'
      ? featuredMaps
      : featuredMaps.filter((m) => m.location === selectedFeaturedCity);

  $: favoriteMaps = maps.filter((m) => favoriteIds.includes(m.id));

  $: displayedMaps = filterCollection === 'featured' ? displayedFeaturedMaps : favoriteMaps;

  /* The hero registers one sheet onto the live city, so it needs one that is
     actually georeferenced. First featured map with an Allmaps id wins. */
  $: heroMap =
    featuredMaps.find((m) => m.allmaps_id || m.annotation_url) ??
    maps.find((m) => m.allmaps_id || m.annotation_url) ??
    null;

  onMount(() => {
    mounted = true;
    loadMapCatalog();
  });
</script>

<svelte:head>
  <title>Vietnam Map Archive — Saigon's historical maps, open and georeferenced</title>
  <meta
    name="description"
    content="A volunteer-built archive of Saigon's historical maps — georeferenced, traced, and released as open data under CC-BY."
  />
</svelte:head>

<!-- The hero is the argument: a surveyed sheet laid onto the city it surveyed,
     warped live from the same tiles every other page uses. -->
<div class="is-wide hero-slot" class:mounted>
  <HeroRegistration map={heroMap} />
</div>

<p class="standfirst">
  Saigon was surveyed and resurveyed for a century, and almost none of it lines up with the city now
  standing on it. We georeference each sheet, trace what is drawn on it, read the names printed
  across it, and publish all of it as open data.
</p>

<!-- ── The archive ─────────────────────────────────────────────────────── -->
<section class="is-wide block">
  <div class="block__head">
    <h2>The archive</h2>
    <div class="row" role="group" aria-label="Which maps to show">
      <button
        type="button"
        class="btn btn--sm"
        aria-pressed={filterCollection === 'featured'}
        on:click={() => (filterCollection = 'featured')}
      >
        Featured
      </button>
      <button
        type="button"
        class="btn btn--sm"
        aria-pressed={filterCollection === 'favorites'}
        on:click={() => (filterCollection = 'favorites')}
      >
        Saved
      </button>
    </div>
  </div>

  {#if loading}
    <p class="state-msg">Opening the archive…</p>
  {:else if filterCollection === 'favorites' && !session}
    <p class="state-msg">
      Sign in to keep a list. Anything you save shows up here on every device.
    </p>
  {:else if displayedMaps.length > 0}
    <div class="grid">
      {#each displayedMaps as map (map.id)}
        <MapCard
          {map}
          href="/explore?map={map.id}{map.location
            ? `&city=${encodeURIComponent(map.location)}`
            : ''}"
          thumbnail={thumbnails.get(map.id) ?? map.thumbnail ?? undefined}
          showFavorite={!!session}
          isFavorited={favoriteIds.includes(map.id)}
          on:toggleFavorite={(e) => toggleFavorite(e.detail)}
        />
      {/each}
    </div>
  {:else if filterCollection === 'favorites'}
    <p class="state-msg">Nothing saved yet. Open a map and save it to start a list.</p>
  {:else}
    <p class="state-msg">No maps match this view.</p>
  {/if}

  <p class="block__more">
    <a href="/archive">Browse everything</a>
    <a href="/explore">Open the viewer</a>
    <a href="/scan">Inspect a scan</a>
  </p>
</section>

<!-- ── Ways in ─────────────────────────────────────────────────────────
     A ruled list, not numbered: these are three doors into the same
     archive, and no one has to go through them in order. -->
<section class="is-wide block">
  <h2>Ways in</h2>

  <dl class="ways">
    <div>
      <dt><a href="/archive">Archive</a></dt>
      <dd>
        Every sheet we hold, with its date, its surveyor and its scale. Filter by city, period or
        what has already been georeferenced.
      </dd>
    </div>
    <div>
      <dt><a href="/explore">Explore</a></dt>
      <dd>
        Stack any number of sheets over the modern city and fade between them. Draw on what you
        find, or build a story that walks a reader through it.
      </dd>
    </div>
    <div>
      <dt><a href="/contribute">Contribute</a></dt>
      <dd>
        Pin a scan to real coordinates, trace a building, or check the names our pipeline read off a
        sheet. Every contribution is attributed and released under CC-BY.
      </dd>
    </div>
  </dl>
</section>

<!-- ── Notes ───────────────────────────────────────────────────────────── -->
<section class="is-wide block block--split">
  <div>
    <h2>About the project</h2>
    <p>
      We are pulling every building out of colonial Saigon's historical maps — automatically, in the
      open, with volunteer review. The 1882 and 1898 surveys are where it starts. Released under
      CC-BY and ODbL.
    </p>
    <p class="block__more"><a href="/about">Project overview</a></p>
  </div>

  <div>
    <h2>Latest update</h2>
    <p class="label">April 2026 — SAM2 on the 1882 survey</p>
    <p>
      Zero-shot SAM2 segmentation is running on the 1882 Saigon cadastral survey. City blocks are
      out; building footprints are in progress, and volunteers are reviewing the polygons as they
      land.
    </p>
    <p class="block__more"><a href="/blog">All updates</a></p>
  </div>
</section>

<style>
  /* The hero breaks the measure and sits tight under the neatline. */
  .hero-slot {
    margin: calc(var(--s-5) * -1) calc(var(--s-6) * -1) var(--s-5);
    opacity: 0;
    transition: opacity 600ms ease;
  }

  .hero-slot.mounted {
    opacity: 1;
  }

  .standfirst {
    font-family: var(--font-display);
    font-size: var(--t-lg);
    font-weight: var(--w-light);
    line-height: 1.35;
    max-width: 46ch;
    margin-bottom: var(--s-6);
  }

  .block {
    margin-bottom: var(--s-6);
    padding-top: var(--s-4);
    border-top: var(--rule-hair) solid var(--rule);
  }

  .block__head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--s-4);
    flex-wrap: wrap;
    margin-bottom: var(--s-4);
  }

  .block--split {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr));
    gap: var(--s-5);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 15rem), 1fr));
    gap: var(--s-3);
  }

  .block__more {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-4);
    margin: var(--s-4) 0 0;
    font-family: var(--font-mono);
    font-size: var(--t-2xs);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
  }

  .ways {
    margin: var(--s-4) 0 0;
    display: grid;
    gap: var(--s-4);
  }

  .ways > div {
    display: grid;
    grid-template-columns: minmax(6rem, 10rem) 1fr;
    gap: var(--s-4);
    padding-top: var(--s-3);
    border-top: var(--rule-hair) solid var(--rule);
  }

  .ways dt {
    font-family: var(--font-display);
    font-size: var(--t-lg);
    font-weight: var(--w-light);
  }

  .ways dd {
    margin: 0;
    color: var(--ink-soft);
  }

  @media (max-width: 600px) {
    .hero-slot {
      margin-inline: calc(var(--s-4) * -1);
    }

    .ways > div {
      grid-template-columns: 1fr;
      gap: var(--s-2);
    }
  }
</style>
