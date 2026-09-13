<!--
  LabelHits.svelte — "On the map" results: OCR'd labels matching the search
  query, from `/api/search?include=labels`. One row per *place*: the same name
  found on four sheets is one row carrying `+3`, not four rows, which is what it
  was until Sept 2026 — directly under a gazetteer row already counting them.

  mode="link" (default) navigates to /explore?map=<id>&at=<lng>,<lat>.
  mode="pick" dispatches `pick` instead, for a caller already on /explore.

  A label in one of the gazetteer's five categories also gets a link to its
  /place/<slug> page. Those pages are server-rendered so search engines index
  them, and until Sept 2026 the only link to one anywhere in the app sat on
  /map/<id> — which is itself one link deep inside a drawer.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import type { LabelHit } from './catalogSearch';
  import { CAT_COLORS } from '$lib/features/contribute/shared/constants';
  import { placeHrefFor } from '$lib/core/utils/placeKey';
  import { letteringClass } from '$lib/core/utils/mapLettering';

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
    <h3 class="title">{$t('On the map')} <span class="n">{hits.length}</span></h3>
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
            <span class="text {letteringClass(h.category)}">{h.text}</span>
            <span class="map"
              >{h.year ?? '—'} · {h.map_name ?? 'Untitled'}{#if h.other_sheets}<span class="more"
                  >+{h.other_sheets}</span
                >{/if}</span
            >
          </svelte:element>
          {#if place}
            <a class="place-link" href={place} title="Every map that names {h.text}"
              >{$t('Place')}</a
            >
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .label-hits {
    margin: var(--space-1) 0 var(--space-3);
  }
  .title {
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--color-gray-500);
    margin: 0 0 var(--space-2);
  }
  .n {
    font-weight: var(--font-normal);
    margin-left: var(--space-1);
  }
  /* The other sheets carrying this same name, collapsed into this row by
     /api/search. The place link beside it is where all of them are listed. */
  .more {
    margin-left: var(--space-1);
    padding: 0 4px;
    border-radius: var(--radius-sm);
    background: var(--color-gray-100);
    color: var(--color-gray-500);
    font-variant-numeric: tabular-nums;
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
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-1) var(--space-2);
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    background: var(--color-white);
    color: var(--color-text);
    text-decoration: none;
    text-align: left;
    font: inherit;
    font-size: var(--text-sm);
    cursor: pointer;
  }
  .hit:hover {
    background: var(--color-gray-50);
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }
  .text {
    font-weight: var(--font-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .map {
    font-size: var(--text-xs);
    color: var(--color-gray-500);
    white-space: nowrap;
  }
  /* The gazetteer door: every map that names this place, on one page. */
  .place-link {
    display: inline-flex;
    align-items: center;
    padding: 0 var(--space-2);
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    background: var(--color-white);
    color: var(--color-gray-500);
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    text-decoration: none;
    white-space: nowrap;
    flex: none;
  }
  .place-link:hover {
    background: var(--color-green);
    color: var(--color-on-accent);
    text-decoration: none;
  }
</style>
