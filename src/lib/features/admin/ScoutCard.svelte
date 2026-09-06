<!--
  ScoutCard.svelte — one candidate tile in the /admin?tab=scout review grid.
  Presentational: selection and status changes are dispatched to the page.
-->
<script lang="ts" context="module">
  export type ScoutCandidate = {
    id: string;
    source: string;
    external_id: string;
    source_url: string | null;
    manifest_url: string | null;
    thumbnail: string | null;
    title: string;
    creator: string | null;
    year: number | null;
    date: string | null;
    rights: string | null;
    language: string | null;
    holding_institution: string | null;
    collection: string | null;
    score: number;
    category: string | null;
    reasons: string | null;
    status: 'pending' | 'approved' | 'rejected' | 'ingested';
  };
</script>

<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let candidate: ScoutCandidate;
  export let selected = false;
  /** The keyboard cursor is on this card (page-level j/k). */
  export let focused = false;

  let el: HTMLElement | undefined;
  $: if (focused && el) el.scrollIntoView({ block: 'nearest' });

  const dispatch = createEventDispatcher<{
    toggle: string;
    status: { id: string; status: 'approved' | 'rejected' | 'pending' };
  }>();

  /** Source-initial placeholder used when there is no thumbnail, or it 404s. */
  function placeholderThumb(c: ScoutCandidate): string {
    return `data:image/svg+xml;utf8,${encodeURIComponent(
      `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 150'><rect width='200' height='150' fill='%23222'/><text x='100' y='80' text-anchor='middle' fill='%23888' font-family='sans-serif' font-size='14'>${c.source}</text></svg>`
    )}`;
  }

  $: scoreBand =
    candidate.score >= 60
      ? 'high'
      : candidate.score >= 40
        ? 'mid'
        : candidate.score >= 0
          ? 'low'
          : 'neg';
</script>

<article class="card" class:selected class:focused bind:this={el}>
  <label class="card-select">
    <input
      type="checkbox"
      checked={selected}
      on:change={() => dispatch('toggle', candidate.id)}
      aria-label="Select {candidate.title}"
    />
  </label>
  <a
    href={candidate.source_url || candidate.manifest_url || '#'}
    target="_blank"
    rel="noopener"
    class="thumb-link"
  >
    <img
      src={candidate.thumbnail || placeholderThumb(candidate)}
      alt={candidate.title}
      loading="lazy"
      on:error={(e) => {
        (e.target as HTMLImageElement).src = placeholderThumb(candidate);
      }}
    />
  </a>
  <div class="card-body">
    <h3 class="title" title={candidate.title}>{candidate.title}</h3>
    <div class="meta">
      <span class="chip score" data-score={scoreBand}>★ {candidate.score}</span>
      <span class="chip cat">{candidate.category || '?'}</span>
      <span class="chip source">{candidate.source}</span>
      {#if candidate.year}<span class="chip year">{candidate.year}</span>{/if}
    </div>
    <div class="holder">{candidate.holding_institution || '?'}</div>
    {#if candidate.creator}<div class="creator">{candidate.creator}</div>{/if}
    <div class="actions">
      {#if candidate.status === 'pending'}
        <button
          class="btn-good"
          on:click={() => dispatch('status', { id: candidate.id, status: 'approved' })}
          >Approve</button
        >
        <button
          class="btn-bad"
          on:click={() => dispatch('status', { id: candidate.id, status: 'rejected' })}
          >Reject</button
        >
      {:else}
        <span class="status-badge {candidate.status}">{candidate.status}</span>
        <button
          class="btn-link"
          on:click={() => dispatch('status', { id: candidate.id, status: 'pending' })}
          >↺ Revert</button
        >
      {/if}
    </div>
  </div>
</article>
