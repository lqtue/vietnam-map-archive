<!--
  /archive/place/<name> — everything the archive holds about one place name.

  A landing page, not a tool: the sheets that name it, the span of years it is
  attested, the other spellings it was written with, and one link into
  /explore at the spot. Server-rendered so it reads without JavaScript.
-->
<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import PressPanel from '$lib/features/explore/PressPanel.svelte';
  import type { PageData } from './$types';

  export let data: PageData;

  $: place = data.place as {
    name: string;
    variants: string[] | null;
    years: number[] | null;
    first_year: number | null;
    last_year: number | null;
    mentions: number;
    category: string | null;
    lng: number | null;
    lat: number | null;
    geom_rmse: number | null;
  };
  $: maps = data.maps as Array<{
    id: string;
    name: string | null;
    year: number | null;
    year_label: string | null;
    thumbnail: string | null;
    holding_institution: string | null;
  }>;

  $: span =
    place.first_year && place.last_year && place.first_year !== place.last_year
      ? `${place.first_year}–${place.last_year}`
      : (place.first_year ?? place.last_year ?? null);

  $: otherSpellings = (place.variants ?? []).filter((v) => v !== place.name);

  $: exploreHref =
    place.lng != null && place.lat != null
      ? `/explore?map=${maps[0].id}&at=${place.lng.toFixed(6)},${place.lat.toFixed(6)}`
      : `/explore?map=${maps[0].id}`;

  $: description = `“${place.name}” appears on ${maps.length} historical map${
    maps.length === 1 ? '' : 's'
  } of Saigon in the Vietnam Map Archive${span ? `, ${span}` : ''}.`;
</script>

<svelte:head>
  <title>{place.name} — Vietnam Map Archive</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={`${place.name} — Vietnam Map Archive`} />
  <meta property="og:description" content={description} />
  {#if maps[0]?.thumbnail}
    <meta property="og:image" content={maps[0].thumbnail} />
  {/if}
</svelte:head>

<PageHero title={place.name} sub={description} />

<main class="place">
  <p class="facts">
    {#if span}<span><strong>{span}</strong> attested</span>{/if}
    <span><strong>{maps.length}</strong> map{maps.length === 1 ? '' : 's'}</span>
    <span><strong>{place.mentions}</strong> mention{place.mentions === 1 ? '' : 's'}</span>
    {#if place.category}<span>{place.category}</span>{/if}
  </p>

  {#if otherSpellings.length}
    <p class="spellings">
      Also written {#each otherSpellings as v, i}<em>{v}</em>{i < otherSpellings.length - 1
          ? ', '
          : ''}{/each}. Spellings come from the maps themselves and from optical character
      recognition, so some are the sheet's own orthography and some are reading errors a reviewer
      has not reached yet.
    </p>
  {/if}

  <a class="cta" href={exploreHref}>Open on the map</a>

  {#if place.geom_rmse != null}
    <p class="caveat">
      Position is warped through each sheet's own georeference, whose control points sit about
      {Math.round(place.geom_rmse)} m from where they claim to be on the least accurate of these maps.
      Treat the spot as a neighbourhood, not a doorstep.
    </p>
  {/if}

  <!-- Client-side: the archives take seconds to answer and this page should
       render without waiting for them. -->
  <section class="press-section">
    <PressPanel
      inline
      q={place.name}
      year={place.first_year ?? place.last_year}
      variants={place.variants ?? []}
      window_={20}
    />
  </section>

  <h2>On these maps</h2>
  <ul class="maps">
    {#each maps as m (m.id)}
      <li>
        <a href={`/archive/${m.id}`}>
          {#if m.thumbnail}<img src={m.thumbnail} alt="" loading="lazy" />{/if}
          <span class="year">{m.year_label ?? m.year ?? '—'}</span>
          <span class="title">{m.name ?? 'Untitled'}</span>
          {#if m.holding_institution}
            <span class="holder">{m.holding_institution}</span>
          {/if}
        </a>
      </li>
    {/each}
  </ul>
</main>

<style>
  .place {
    max-width: 60rem;
    margin: 0 auto;
    padding: var(--s-4) var(--s-4) var(--s-6);
  }
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-4);
    margin: 0 0 var(--s-4);
    font-size: var(--t-sm);
    color: var(--ink-soft);
  }
  .facts strong {
    color: var(--ink);
  }
  .spellings {
    margin: 0 0 var(--s-4);
    font-size: var(--t-sm);
    max-width: 42rem;
  }
  .cta {
    display: inline-block;
    padding: var(--s-2) var(--s-4);
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--radius-pill);
    background: var(--accent);
    color: var(--ground-raised);
    font-weight: var(--w-semi);
    text-decoration: none;
  }
  .caveat {
    margin: var(--s-4) 0 0;
    font-size: var(--t-xs);
    color: var(--ink-soft);
    max-width: 42rem;
  }
  .press-section {
    margin: var(--s-5) 0 0;
  }

  h2 {
    margin: var(--s-5) 0 var(--s-3);
    font-size: var(--t-md);
  }
  .maps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
    gap: var(--s-3);
  }
  .maps a {
    display: grid;
    gap: var(--s-1);
    padding: var(--s-2);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
    color: inherit;
    text-decoration: none;
  }
  .maps img {
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    border-radius: var(--radius);
  }
  .year {
    font-size: var(--t-xs);
    font-weight: var(--w-semi);
    color: var(--ink-soft);
  }
  .title {
    font-size: var(--t-sm);
    font-weight: var(--w-medium);
  }
  .holder {
    font-size: var(--t-xs);
    color: var(--ink-soft);
  }
</style>
