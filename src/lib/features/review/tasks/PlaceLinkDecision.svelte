<!--
  PlaceLinkDecision.svelte — the right-hand column for a place-link item: the question, the label,
  the machine's candidates (shown arm only), the pool search, the six relations, the note.

  The page mounts this once per item (`{#key}`), so a new item starts with an empty search and note.
  The reviewer is never told which arm they are on: the blind and no-candidate arms both get the
  same "No suggestions here" line. Search reads the 300 m pool through the API, so it works the
  same on every arm and never marks or ranks the machine's candidates.
-->
<script lang="ts">
  import { onDestroy } from 'svelte';
  import { debounce } from '$lib/core/utils/debounce';
  import type { ReviewSession, SessionState } from '../reviewSession';
  import type { ReviewTaskDef } from './placeLink';
  import type { SearchHit } from '../types';

  export let task: ReviewTaskDef;
  export let session: ReviewSession;
  export let state: SessionState;
  /** Pool search for this item; the page binds it to the API. */
  export let search: (q: string) => Promise<SearchHit[]>;

  const COLOURS = ['var(--color-primary)', 'var(--color-blue)', 'var(--color-green)'];

  let query = '';
  let hits: SearchHit[] = [];
  let searchFailed = false;
  let searchInput: HTMLInputElement;
  let noteInput: HTMLInputElement;

  $: item = state.item;
  $: busy = state.phase !== 'ready';
  $: picked = state.hit?.name ?? (state.pick && item ? item.proposal[state.pick - 1]?.name : null);
  /** Called by the page for `/` and `t`. */
  export function focusSearch() {
    searchInput?.focus();
    void runSearch();
  }
  export function focusNote() {
    noteInput?.focus();
  }

  async function runSearch() {
    try {
      hits = await search(query);
      searchFailed = false;
    } catch {
      hits = [];
      searchFailed = true;
    }
  }
  const onQuery = debounce(runSearch, 200);
  onDestroy(onQuery.cancel);

  function choose(hit: SearchHit) {
    session.chooseHit(hit);
    searchInput?.blur();
    hits = [];
  }

  function onSearchKey(e: KeyboardEvent) {
    if (e.key === 'Enter' && hits[0]) {
      e.preventDefault();
      choose(hits[0]);
    } else if (e.key === 'Escape') searchInput.blur();
  }

  function onNoteKey(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === 'Escape') noteInput.blur();
  }

  $: lat = item?.payload.lat;
  $: lon = item?.payload.lon;
</script>

{#if item}
  <div class="decision" aria-busy={busy}>
    <p class="question">{state.question}</p>
    <h2 class="label">« {item.payload.text} »</h2>
    <p class="see-today">
      See today:
      <a
        target="_blank"
        rel="noopener"
        aria-keyshortcuts="o"
        href="/explore?map={item.payload.sheet.map_id}&at={lon},{lat}"
        >1882 over today <kbd>o</kbd></a
      >
      ·
      <a
        target="_blank"
        rel="noopener"
        aria-keyshortcuts="v"
        href="https://www.google.com/maps/@{lat},{lon},19z/data=!3m1!1e3">satellite <kbd>v</kbd></a
      >
      ·
      <a
        target="_blank"
        rel="noopener"
        aria-keyshortcuts="w"
        href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
        >street view <kbd>w</kbd></a
      >
    </p>

    {#if item.proposal.length}
      <ul class="cands">
        {#each item.proposal as cand, k (cand.id)}
          <li>
            <button
              type="button"
              class="cand"
              class:selected={state.pick === k + 1}
              style:--cand={COLOURS[k % 3]}
              aria-pressed={state.pick === k + 1}
              aria-keyshortcuts={String(k + 1)}
              disabled={busy}
              on:click={() => session.pickCandidate(k + 1)}
            >
              <span class="num">{k + 1}</span>
              <span class="name">{cand.name}</span>
              <span class="meta"
                >{cand.source} · {cand.dist_m} m{cand.wikidata ? ` · ${cand.wikidata}` : ''}</span
              >
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="none">
        No suggestions here. Press <kbd>/</kbd> and type a name you know, or <kbd>g</kbd> gone,
        <kbd>x</kbd> none, <kbd>?</kbd> unsure.
      </p>
    {/if}

    <div class="search">
      <input
        bind:this={searchInput}
        bind:value={query}
        class="sb-search"
        type="search"
        placeholder="/  search a place within 300 m"
        aria-label="Search a place within 300 m"
        autocomplete="off"
        disabled={busy}
        on:input={onQuery}
        on:keydown={onSearchKey}
      />
      {#if searchFailed}
        <p class="meta" role="status">Search failed. Try again.</p>
      {/if}
      {#if hits.length}
        <ul class="hits">
          {#each hits as hit (hit.id)}
            <li>
              <button type="button" class="hit" on:click={() => choose(hit)}>
                <span class="name">{hit.name}</span>
                <span class="meta">{hit.source} · {hit.dist_m} m</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <p class="picked">Picked: <b>{picked ?? 'nothing'}</b></p>

    <p class="how">How does it relate?</p>
    <div class="relations">
      {#each task.relations as r (r.key)}
        <button
          type="button"
          class="btn is-sm"
          aria-keyshortcuts={r.key}
          disabled={busy}
          on:click={() => session.send(r.relation)}>{r.label} <kbd>{r.key}</kbd></button
        >
      {/each}
    </div>

    <label class="note">
      <span class="meta">note <kbd>t</kbd></span>
      <input
        bind:this={noteInput}
        type="text"
        class="sb-search"
        value={state.note}
        maxlength="2000"
        disabled={busy}
        on:input={(e) => session.setNote(e.currentTarget.value)}
        on:keydown={onNoteKey}
      />
    </label>

    <p class="message" role="status" aria-live="polite">{state.message}</p>

    <p class="foot">
      <button
        type="button"
        class="btn is-sm"
        aria-keyshortcuts="u"
        disabled={busy}
        on:click={() => session.undo()}>undo last <kbd>u</kbd></button
      >
      <a href="/catalog/{item.payload.sheet.map_id}" target="_blank" rel="noopener">Open sheet ↗</a>
    </p>
  </div>
{/if}

<style>
  .decision {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .question {
    margin: 0;
    font-weight: var(--font-semibold);
  }
  .label {
    margin: 0;
    font-size: var(--text-xl);
  }
  .see-today,
  .none,
  .how,
  .picked,
  .foot,
  .message {
    margin: 0;
    font-size: var(--text-sm);
  }
  .meta {
    font-size: var(--text-xs);
    color: var(--color-gray-500);
  }
  .message {
    min-height: 1.4em;
    color: var(--color-error-600);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .cand,
  .hit {
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: var(--space-2);
    width: 100%;
    text-align: left;
    padding: var(--space-2) var(--space-3);
    background: var(--color-bg);
    color: var(--color-text);
    border: var(--border-thin) solid var(--color-border);
    cursor: pointer;
  }
  .cand {
    border-left: 6px solid var(--cand);
  }
  .cand.selected {
    background: var(--color-gray-100);
    outline: 2px solid var(--color-blue);
  }
  .cand .meta,
  .hit .meta {
    grid-column: 2;
  }
  .hit {
    grid-template-columns: 1fr;
  }
  .hit .meta {
    grid-column: 1;
  }
  .num {
    font-weight: var(--font-bold);
  }
  .cand:hover:not(:disabled),
  .hit:hover {
    background: var(--color-gray-50);
  }
  .search input,
  .note input {
    width: 100%;
  }
  .relations {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .note {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  kbd {
    font-family: var(--font-family-base);
    font-size: var(--text-xs);
    padding: 0 var(--space-1);
    border: var(--border-thin) solid var(--color-border);
    border-radius: var(--radius-sm);
  }
  .foot {
    display: flex;
    gap: var(--space-4);
    align-items: center;
  }
</style>
