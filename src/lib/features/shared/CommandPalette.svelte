<!--
  CommandPalette.svelte — one search for the whole app.

  Mounted once by the root layout, opened with ⌘K / Ctrl+K, by "/" anywhere
  that is not a form field, or by the search button in the nav. It searches
  four things at once through `/api/search`, which already gates by role:

    Pages    the destination list — this is what finally makes the gazetteer,
             the review queue and the design system reachable by name
    Maps     the archive, by title, creator, year or description
    Places   the gazetteer (mig 067), each row its own /archive/place/<slug>
    On maps  OCR'd labels, which open /explore at the spot

  Arrow keys move, Enter opens, Escape closes. Results are one flat list so
  the keyboard never has to know about the group headings.
-->
<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { goto } from '$app/navigation';
  import { paletteOpen, closePalette } from '$lib/core/utils/commandPalette';
  import { debounce } from '$lib/core/utils/debounce';
  import { destinationsFor, matchDestinations, type Destination } from './paletteDestinations';
  import { placeHref } from '$lib/core/utils/placeKey';

  /** Role of the signed-in visitor, or null. Gates which pages are offered. */
  export let role: string | null = null;
  export let signedIn = false;

  type MapHit = { id: string; name: string; year: number | null; year_label: string | null };
  type PlaceRow = {
    key: string;
    name: string;
    mentions: number;
    first_year: number | null;
    last_year: number | null;
  };
  type LabelRow = {
    id: string;
    map_id: string;
    map_name: string | null;
    text: string;
    lng: number | null;
    lat: number | null;
  };

  type Row =
    | { kind: 'page'; href: string; title: string; sub: string }
    | { kind: 'map'; href: string; title: string; sub: string }
    | { kind: 'place'; href: string; title: string; sub: string }
    | { kind: 'label'; href: string; title: string; sub: string };

  const GROUPS: { kind: Row['kind']; heading: string }[] = [
    { kind: 'page', heading: 'Go to' },
    { kind: 'map', heading: 'Maps' },
    { kind: 'place', heading: 'Places' },
    { kind: 'label', heading: 'Named on a map' },
  ];

  let query = '';
  let active = 0;
  let loading = false;
  let searchError = '';
  let input: HTMLInputElement | undefined;
  let listEl: HTMLDivElement | undefined;
  /** Whatever had focus when the palette opened, so Escape gives it back. */
  let opener: HTMLElement | null = null;

  let maps: MapHit[] = [];
  let places: PlaceRow[] = [];
  let labels: LabelRow[] = [];

  $: pages = matchDestinations(destinationsFor(role, signedIn), query);

  $: rows = [
    ...pages.map((d: Destination): Row => ({
      kind: 'page',
      href: d.href,
      title: d.label,
      sub: d.hint,
    })),
    ...maps.map((m): Row => ({
      kind: 'map',
      href: `/explore?map=${m.id}`,
      title: m.name,
      sub: m.year_label ?? (m.year ? String(m.year) : 'Undated'),
    })),
    ...places.map((p): Row => ({
      kind: 'place',
      href: placeHref(p.key),
      title: p.name,
      sub:
        p.first_year && p.last_year && p.first_year !== p.last_year
          ? `${p.mentions} mentions · ${p.first_year}–${p.last_year}`
          : `${p.mentions} mention${p.mentions === 1 ? '' : 's'}`,
    })),
    ...labels.map((l): Row => ({
      kind: 'label',
      // `?at=<lng>,<lat>`, not a `#@…` camera hash: /explore force-zooms to the
      // sheet's bounds when it applies `?map=`, which lands *after* a hash the
      // browser set on load and silently overwrites it. `?at=` is applied after
      // that zoom, and is what pulses the spot. LabelHits and /place both use it.
      href:
        l.lng != null && l.lat != null
          ? `/explore?map=${l.map_id}&at=${l.lng.toFixed(6)},${l.lat.toFixed(6)}`
          : `/explore?map=${l.map_id}`,
      title: l.text,
      sub: l.map_name ?? 'On a map',
    })),
  ];

  // The highlight must never point past the end when results shrink.
  $: if (active >= rows.length) active = Math.max(0, rows.length - 1);

  const search = debounce(async (q: string) => {
    if (!q.trim()) {
      maps = [];
      places = [];
      labels = [];
      loading = false;
      return;
    }
    try {
      const res = await fetch(
        `/api/search?q=${encodeURIComponent(q)}&include=maps,places,labels&limit=6&fields=slim`
      );
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      maps = (data.maps ?? []).slice(0, 6);
      places = (data.places ?? []).slice(0, 5);
      labels = (data.labels ?? []).slice(0, 5);
      searchError = '';
    } catch {
      searchError = "Couldn't reach the archive. Page results still work.";
      maps = [];
      places = [];
      labels = [];
    } finally {
      loading = false;
    }
  }, 180);

  function onInput() {
    active = 0;
    loading = !!query.trim();
    search(query);
  }

  async function open() {
    opener = document.activeElement as HTMLElement | null;
    await tick();
    input?.focus();
    input?.select();
  }
  $: if ($paletteOpen) open();

  /** Close and hand focus back to whatever opened us. */
  function dismiss() {
    closePalette();
    opener?.focus?.();
    opener = null;
  }

  function choose(row: Row | undefined) {
    if (!row) return;
    // Navigating away is its own focus change, so don't restore the opener here.
    closePalette();
    opener = null;
    query = '';
    maps = [];
    places = [];
    labels = [];
    goto(row.href);
  }

  async function move(delta: number) {
    if (!rows.length) return;
    active = (active + delta + rows.length) % rows.length;
    await tick();
    listEl
      ?.querySelector<HTMLElement>('[data-active="true"]')
      ?.scrollIntoView({ block: 'nearest' });
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      dismiss();
    } else if (e.key === 'Tab') {
      // The dialog holds exactly one focusable control; results are reached with
      // the arrows. Swallowing Tab is the whole focus trap.
      e.preventDefault();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      move(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      move(-1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(rows[active]);
    }
  }

  // Index of the first row of each group, so headings land in the right places.
  $: firstOfKind = GROUPS.reduce<Record<string, number>>((acc, g) => {
    const i = rows.findIndex((r) => r.kind === g.kind);
    if (i >= 0) acc[g.kind] = i;
    return acc;
  }, {});

  let mac = false;
  onMount(() => {
    mac = /mac/i.test(navigator.platform ?? '');
  });
</script>

{#if $paletteOpen}
  <button type="button" class="cp-scrim" aria-label="Close search" on:click={dismiss}></button>
  <div class="cp" role="dialog" aria-modal="true" aria-label="Search the archive">
    <div class="cp-field">
      <svg
        class="cp-icon"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" />
      </svg>
      <input
        bind:this={input}
        bind:value={query}
        on:input={onInput}
        on:keydown={onKeydown}
        type="text"
        placeholder="Search maps, places and pages…"
        aria-label="Search maps, places and pages"
        autocomplete="off"
        spellcheck="false"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={rows.length > 0}
        aria-controls="cp-results"
        aria-activedescendant={rows.length ? `cp-row-${active}` : undefined}
      />
      {#if loading}
        <span class="spinner" style="--spinner-size: 15px; --spinner-thickness: 2px"></span>
      {/if}
      <kbd class="cp-esc">esc</kbd>
    </div>

    <!-- Arrow keys move a highlight while focus stays in the input, so without
         this the whole result list is silent to a screen reader. -->
    <p class="sr-only" aria-live="polite">
      {rows.length
        ? `${rows.length} result${rows.length === 1 ? '' : 's'}`
        : query.trim()
          ? 'No results'
          : ''}
    </p>

    <div
      class="cp-list"
      id="cp-results"
      role="listbox"
      aria-label="Search results"
      bind:this={listEl}
    >
      {#if !rows.length}
        <p class="cp-empty">
          {query.trim() ? `Nothing matches “${query.trim()}”.` : 'Type to search.'}
        </p>
      {:else}
        {#each rows as row, i (row.kind + row.href + i)}
          {#if firstOfKind[row.kind] === i}
            <div class="cp-heading" role="presentation">
              {GROUPS.find((g) => g.kind === row.kind)?.heading}
            </div>
          {/if}
          <a
            class="cp-row"
            class:is-active={i === active}
            data-active={i === active}
            id="cp-row-{i}"
            role="option"
            aria-selected={i === active}
            href={row.href}
            on:click|preventDefault={() => choose(row)}
            on:mouseenter={() => (active = i)}
          >
            <span class="cp-kind cp-kind-{row.kind}" aria-hidden="true"></span>
            <span class="cp-text">
              <span class="cp-title">{row.title}</span>
              <span class="cp-sub">{row.sub}</span>
            </span>
          </a>
        {/each}
      {/if}
      {#if searchError}
        <p class="cp-error">{searchError}</p>
      {/if}
    </div>

    <div class="cp-foot">
      <span><kbd>↑</kbd><kbd>↓</kbd> move</span>
      <span><kbd>↵</kbd> open</span>
      <span><kbd>{mac ? '⌘' : 'Ctrl'}</kbd><kbd>K</kbd> anywhere</span>
    </div>
  </div>
{/if}

<style>
  .cp-scrim {
    position: fixed;
    inset: 0;
    z-index: 2000;
    background: var(--scrim);
    border: none;
    padding: 0;
    cursor: default;
  }

  .cp {
    position: fixed;
    z-index: 2001;
    top: 12vh;
    left: 50%;
    transform: translateX(-50%);
    width: min(640px, calc(100vw - 2rem));
    max-height: 70vh;
    display: flex;
    flex-direction: column;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--radius);
    overflow: hidden;
  }

  .cp-field {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.75rem 0.9rem;
    border-bottom: var(--rule-thick) solid var(--rule);
    flex-shrink: 0;
  }
  .cp-icon {
    opacity: 0.45;
    flex-shrink: 0;
  }
  .cp-field input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: none;
    font-family: var(--font-body);
    font-size: 1rem;
    color: var(--ink);
  }
  .cp-esc {
    flex-shrink: 0;
  }

  /* Announced, never drawn. The design system has no sr-only utility yet. */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  .cp-list {
    overflow-y: auto;
    padding: 0.4rem;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .cp-heading {
    font-family: var(--font-display);
    font-size: 0.62rem;
    font-weight: var(--w-semi);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.5;
    padding: 0.6rem 0.55rem 0.25rem;
  }

  .cp-row {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.45rem 0.55rem;
    border-radius: var(--radius);
    color: inherit;
    text-decoration: none;
    min-width: 0;
  }
  .cp-row.is-active {
    background: var(--accent);
    color: var(--on-accent);
  }
  .cp-row:hover {
    text-decoration: none;
  }

  /* The stripe says what kind of thing a row is without spending a word on it. */
  .cp-kind {
    width: 4px;
    align-self: stretch;
    min-height: 1.9rem;
    border-radius: 2px;
    flex-shrink: 0;
  }
  .cp-kind-page {
    background: var(--ink);
  }
  .cp-kind-map {
    background: var(--accent);
  }
  .cp-kind-place {
    background: var(--status-ok);
  }
  .cp-kind-label {
    background: color-mix(in srgb, var(--accent) 55%, var(--status-bad));
  }

  .cp-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
    line-height: 1.25;
  }
  .cp-title {
    font-family: var(--font-body);
    font-size: 0.92rem;
    font-weight: var(--w-semi);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .cp-sub {
    font-size: 0.74rem;
    opacity: 0.62;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .cp-empty,
  .cp-error {
    margin: 0;
    padding: 1.6rem 0.75rem;
    text-align: center;
    font-size: 0.85rem;
    opacity: 0.6;
  }
  .cp-error {
    padding: 0.5rem 0.75rem;
    color: var(--status-bad);
    opacity: 1;
  }

  .cp-foot {
    display: flex;
    gap: 1rem;
    padding: 0.5rem 0.9rem;
    border-top: var(--rule-hair) solid var(--rule);
    background: var(--ground);
    font-size: 0.7rem;
    opacity: 0.7;
    flex-shrink: 0;
  }
  .cp-foot span {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }

  kbd {
    font-family: var(--font-display);
    font-size: 0.65rem;
    font-weight: var(--w-semi);
    padding: 0.1rem 0.3rem;
    border: 1.5px solid var(--rule);
    border-radius: 4px;
    background: var(--ground-raised);
    line-height: 1.4;
  }

  @media (max-width: 600px) {
    .cp {
      top: 4vh;
      max-height: 84vh;
    }
    .cp-foot {
      display: none;
    }
  }
</style>
