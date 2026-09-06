<!--
  LabelHits.svelte — "On the map" results: OCR'd labels matching the search
  query, one row per (map, label), from `/api/search?include=labels`.

  mode="link" (default) navigates to /explore?map=<id>&at=<lng>,<lat>.
  mode="pick" dispatches `pick` instead, for a caller already on /explore.

  A label in one of the gazetteer's five categories also gets a link to its
  /archive/place/<slug> page. Those pages are server-rendered so search engines index
  them, and until Sept 2026 the only link to one anywhere in the app sat on
  /archive/<id> — which is itself one link deep inside a drawer.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { LabelHit } from './catalogSearch';
  import { CAT_COLORS } from '$lib/features/contribute/shared/constants';
  import { placeHrefFor } from '$lib/core/utils/placeKey';

  export let hits: LabelHit[] = [];
  export let mode: 'link' | 'pick' = 'link';

  const dispatch = createEventDispatcher<{ pick: LabelHit }>();

  function href(h: LabelHit): string {
    const at = h.lng != null && h.lat != null ? `&at=${h.lng.toFixed(6)},${h.lat.toFixed(6)}` : '';
    return `/explore?map=${h.map_id}${at}`;
  }
</script>

{#if hits.length}
  <section class="label-hits" aria-label="Labels found on maps">
    <h3 class="title">On the map <span class="n">{hits.length}</span></h3>
    <ul>
      {#each hits as h (h.id)}
        {@const place = placeHrefFor(h.text, h.category)}
        <li>
          <!--
            One element, two behaviours. The button and the anchor carried
            identical innards and an identical place link beside them, so a
            change to a row had to be made twice.
          -->
          <svelte:element
            this={mode === 'pick' ? 'button' : 'a'}
            role={mode === 'pick' ? 'button' : 'link'}
            class="hit"
            type={mode === 'pick' ? 'button' : undefined}
            href={mode === 'pick' ? undefined : href(h)}
            on:click={mode === 'pick' ? () => dispatch('pick', h) : undefined}
          >
            <span class="dot" style:background={CAT_COLORS[h.category] ?? CAT_COLORS.other}></span>
            <span class="text">{h.text}</span>
            <span class="map">{h.year ?? '—'} · {h.map_name ?? 'Untitled'}</span>
          </svelte:element>
          {#if place}
            <a class="place-link" href={place} title="Every map that names {h.text}">Place</a>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .label-hits {
    margin: var(--s-1) 0 var(--s-3);
  }
  .title {
    font-size: var(--t-xs);
    font-weight: var(--w-semi);
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--ink-soft);
    margin: 0 0 var(--s-2);
  }
  .n {
    font-weight: var(--w-regular);
    margin-left: var(--s-1);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  li {
    display: flex;
    align-items: stretch;
    gap: 2px;
    min-width: 0;
  }
  li > :global(:first-child) {
    flex: 1;
    min-width: 0;
  }
  .hit {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: var(--s-2);
    width: 100%;
    padding: var(--s-1) var(--s-2);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
    color: var(--ink);
    text-decoration: none;
    text-align: left;
    font: inherit;
    font-size: var(--t-sm);
    cursor: pointer;
  }
  .hit:hover {
    background: var(--ground);
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }
  .text {
    font-weight: var(--w-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .map {
    font-size: var(--t-xs);
    color: var(--ink-soft);
    white-space: nowrap;
  }
  /* The gazetteer door: every map that names this place, on one page. */
  .place-link {
    display: inline-flex;
    align-items: center;
    padding: 0 var(--s-2);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
    color: var(--ink-soft);
    font-size: var(--t-xs);
    font-weight: var(--w-semi);
    text-decoration: none;
    white-space: nowrap;
    flex: none;
  }
  .place-link:hover {
    background: var(--status-ok);
    color: var(--ground-raised);
    text-decoration: none;
  }
</style>
