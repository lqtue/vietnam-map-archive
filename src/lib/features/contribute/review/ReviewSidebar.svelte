<!--
  ReviewSidebar.svelte — the review queue for one sheet: every polygon awaiting
  a verdict, with approve / reject.

  Selection is the ordinary list convention — click replaces, ctrl/cmd toggles,
  shift extends from the anchor — because a sheet's polygons usually deserve the
  same verdict and deciding 46 of them one at a time is the reason nobody did.
  The parent owns the selection; this only reports the click and its modifier.

  Emits 'select', 'approve', 'reject', 'approveSelected', 'rejectSelected'.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { SamFootprint } from '$lib/data/supabase/footprints';
  import { FEATURE_TYPE_COLORS, FEATURE_TYPE_LABELS } from '$lib/data/maps/footprintTypes';
  import { REVIEW_TAGS, REVIEW_NOTE_MAX } from '$lib/core/reviewTags';

  export let footprints: SamFootprint[] = [];
  export let selectedId: string | null = null;
  /** Every row in the selection. `selectedId` is the anchor and the open editor. */
  export let selectedIds: string[] = [];
  export let total = 0;
  export let reviewed = 0;
  export let approving: string | null = null; // id currently being saved
  /** Pipeline mutation state — owned by ReviewPage, mirrored here for the button. */
  export let markingReviewed = false;
  export let markReviewedError = '';
  export let reviewTags: string[] = [];
  export let reviewNote = '';

  const dispatch = createEventDispatcher<{
    select: { id: string; mode: 'replace' | 'toggle' | 'range' };
    approve: { id: string };
    reject: { id: string };
    approveSelected: void;
    rejectSelected: void;
    selectAll: void;
    clearSelection: void;
    retype: { id: string; featureType: string };
    feedback: { id: string; tags: string[]; note: string };
    markReviewed: void;
  }>();

  /** metaKey so this reads the same on a Mac as ctrl does elsewhere. */
  function clickMode(e: MouseEvent): 'replace' | 'toggle' | 'range' {
    if (e.shiftKey) return 'range';
    if (e.ctrlKey || e.metaKey) return 'toggle';
    return 'replace';
  }

  $: selected = new Set(selectedIds);
  $: multiple = selectedIds.length > 1;
  $: busy = approving !== null;

  /** The cadastral classes this queue also sees, on top of the feature types.
      Swatches are data, not theme: they identify a class on the canvas. */
  const CLASS_COLORS: Record<string, string> = {
    particulier: '#d2956e',
    communal: '#7cb87c',
    militaire: '#7ba0c8',
    local_svc: '#9c9c9c',
    non_affect: '#e8e0d0',
    ...FEATURE_TYPE_COLORS,
  };

  const ALL_TYPE_LABELS: Record<string, string> = {
    particulier: 'Particulier',
    communal: 'Communal',
    militaire: 'Militaire',
    local_svc: 'Service Local',
    non_affect: 'Non Affecté',
    ...FEATURE_TYPE_LABELS,
  };

  function classColor(ft: string) {
    return CLASS_COLORS[ft] ?? CLASS_COLORS.other;
  }

  function changeTags(id: string, tag: string) {
    const tags = reviewTags.includes(tag)
      ? reviewTags.filter((value) => value !== tag)
      : [...reviewTags, tag];
    dispatch('feedback', { id, tags, note: reviewNote });
  }

  function changeNote(id: string, note: string) {
    dispatch('feedback', { id, tags: reviewTags, note });
  }
</script>

<div class="review-panel">
  <div class="sb-row is-strip">
    <span class="sb-grow progress-label">Progress</span>
    <span class="progress-pill">{reviewed} / {total} done</span>
  </div>

  {#if multiple}
    <div class="sb-row is-strip bulk-bar">
      <span class="sb-grow bulk-count">{selectedIds.length} selected</span>
      <button class="link-btn" type="button" on:click={() => dispatch('selectAll')}>All</button>
      <button class="link-btn" type="button" on:click={() => dispatch('clearSelection')}
        >None</button
      >
    </div>
    <div class="bulk-actions">
      <button
        class="sb-btn is-success is-sm"
        disabled={busy}
        on:click={() => dispatch('approveSelected')}
      >
        {busy ? 'Saving…' : `✓ Approve ${selectedIds.length}`}
      </button>
      <button
        class="sb-btn is-danger is-sm"
        disabled={busy}
        on:click={() => dispatch('rejectSelected')}
      >
        ✕ Reject {selectedIds.length}
      </button>
    </div>
  {/if}

  {#if footprints.length === 0}
    <p class="empty-state is-block">All done for this map.</p>
    {#if total > 0}
      <div class="mark-reviewed-block">
        <button
          class="sb-btn is-success is-block"
          disabled={markingReviewed}
          on:click={() => dispatch('markReviewed')}
        >
          {markingReviewed ? 'Saving…' : 'Mark seg reviewed'}
        </button>
        {#if markReviewedError}
          <p class="empty-state error">{markReviewedError}</p>
        {/if}
      </div>
    {/if}
  {:else}
    <ul class="fp-list">
      {#each footprints as fp (fp.id)}
        <li
          class="fp-item"
          class:selected={selected.has(fp.id)}
          class:anchor={fp.id === selectedId}
        >
          <!-- The row itself is the select control, so it is a real button. -->
          <button
            type="button"
            class="fp-main"
            aria-pressed={selected.has(fp.id)}
            on:click={(e) => dispatch('select', { id: fp.id, mode: clickMode(e) })}
          >
            <span class="swatch" style="background:{classColor(fp.featureType)}"></span>
            <span class="fp-class">{fp.featureType}</span>
          </button>

          <!-- The editor belongs to the anchor alone: retyping is per-row, and a
               bulk selection has no single type to show. -->
          {#if fp.id === selectedId && !multiple}
            <div class="fp-extra">
              <select
                class="type-select"
                value={fp.featureType}
                on:change={(e) =>
                  dispatch('retype', { id: fp.id, featureType: e.currentTarget.value })}
              >
                {#each Object.entries(ALL_TYPE_LABELS) as [value, label] (value)}
                  <option {value}>{label}</option>
                {/each}
              </select>
              <fieldset class="feedback">
                <legend>Model feedback <span>(optional)</span></legend>
                <div class="tag-list">
                  {#each REVIEW_TAGS as [value, label] (value)}
                    <label class="tag-option">
                      <input
                        type="checkbox"
                        checked={reviewTags.includes(value)}
                        on:change={() => changeTags(fp.id, value)}
                      />
                      <span>{label}</span>
                    </label>
                  {/each}
                </div>
                <label class="note-label" for={`review-note-${fp.id}`}
                  >What should the next run learn?</label
                >
                <textarea
                  id={`review-note-${fp.id}`}
                  rows="3"
                  maxlength={REVIEW_NOTE_MAX}
                  value={reviewNote}
                  placeholder="e.g. hatch lines are being read as a building"
                  on:input={(e) => changeNote(fp.id, e.currentTarget.value)}></textarea>
              </fieldset>
              <div class="fp-actions">
                <button
                  class="sb-btn is-success is-sm"
                  disabled={approving === fp.id}
                  on:click={() => dispatch('approve', { id: fp.id })}
                >
                  {approving === fp.id ? '…' : '✓ Approve'}
                </button>
                <button
                  class="sb-btn is-danger is-sm"
                  disabled={approving === fp.id}
                  on:click={() => dispatch('reject', { id: fp.id })}
                >
                  ✕ Reject
                </button>
              </div>
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  /* `.panel` (ToolSidebarShell) owns the frame; this is only the body. */
  .review-panel {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    font-family: var(--font-family-base);
  }

  /* `.sb-row.is-strip` (sidebar.css) carries the padded divider band; this is
     only the small meta label `.tool-label` used to supply. */
  .progress-label {
    font-size: 0.72rem;
    color: var(--sb-text-meta);
  }

  .progress-pill {
    font-size: 0.75rem;
    font-weight: var(--font-semibold);
    background: var(--color-gray-100);
    color: var(--color-gray-500);
    border-radius: var(--radius-pill);
    padding: 0.15rem 0.6rem;
    white-space: nowrap;
  }

  .fp-list {
    list-style: none;
    padding: 0;
    margin: 0;
    overflow-y: auto;
    flex: 1;
  }

  .fp-item {
    border-bottom: 1px solid var(--color-gray-300);
    transition: background 0.1s;
  }

  .fp-item:hover {
    background: var(--color-gray-100);
  }
  .fp-item.selected {
    background: var(--tone-blue-wash);
  }

  /* The anchor is what shift extends from and what the editor belongs to, so it
     stays distinguishable inside a selection rather than merging into it. */
  .fp-item.anchor {
    box-shadow: inset 2px 0 0 var(--color-orange);
  }

  .bulk-count {
    font-size: 0.72rem;
    font-weight: var(--font-semibold);
    color: var(--sb-text-meta);
  }

  .link-btn {
    background: none;
    border: none;
    padding: 0 0.3rem;
    font: inherit;
    font-size: 0.72rem;
    color: var(--color-orange);
    cursor: pointer;
    text-decoration: underline;
  }

  .bulk-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
    padding: 0.5rem 1rem 0.625rem;
    border-bottom: 1px solid var(--color-gray-300);
  }

  .fp-main {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    width: 100%;
    padding: 0.625rem 1rem;
    background: none;
    border: none;
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: pointer;
  }

  .swatch {
    width: 12px;
    height: 12px;
    border-radius: var(--sb-radius-sm);
    flex-shrink: 0;
    margin-top: 3px;
    border: 1px solid color-mix(in srgb, var(--color-border) 15%, transparent);
  }

  .fp-class {
    flex: 1;
    font-size: 0.8125rem;
    font-weight: var(--font-semibold);
    color: var(--color-text);
  }

  .fp-extra {
    display: flex;
    flex-direction: column;
    padding: 0 1rem 0.625rem;
  }

  /* Grid, not flex: the two buttons share the row evenly without either of
     them needing a `flex` of its own on top of `.sb-btn`. */
  .fp-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
    padding-top: 0.5rem;
  }

  .feedback {
    border: 0;
    border-top: 1px solid var(--color-gray-300);
    margin: 0.7rem 0 0;
    padding: 0.65rem 0 0;
  }

  .feedback legend {
    padding: 0;
    font-size: 0.72rem;
    font-weight: var(--font-semibold);
    color: var(--sb-text-meta);
  }

  .feedback legend span {
    font-weight: var(--font-normal);
  }
  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.45rem;
  }

  .tag-option {
    display: inline-flex;
    align-items: center;
    gap: 0.22rem;
    font-size: 0.7rem;
    color: var(--color-gray-500);
    cursor: pointer;
  }

  .tag-option input {
    margin: 0;
    accent-color: var(--color-orange);
  }

  .note-label {
    display: block;
    margin-top: 0.6rem;
    font-size: 0.7rem;
    color: var(--sb-text-meta);
  }

  textarea {
    box-sizing: border-box;
    width: 100%;
    resize: vertical;
    margin-top: 0.25rem;
    padding: 0.35rem 0.4rem;
    border: 1px solid var(--color-gray-300);
    border-radius: var(--sb-radius-sm);
    background: var(--color-white);
    color: var(--color-text);
    font: inherit;
    font-size: 0.75rem;
  }

  textarea:focus {
    outline: 1px solid var(--color-orange);
    outline-offset: -1px;
  }

  .type-select {
    width: 100%;
    background: var(--color-white);
    color: var(--color-text);
    border: 1px solid var(--color-gray-300);
    border-radius: var(--sb-radius-sm);
    font-size: 0.75rem;
    font-family: inherit;
    padding: 0.3rem 0.4rem;
    cursor: pointer;
    margin-top: 0.35rem;
  }

  .type-select:focus {
    outline: 1px solid var(--color-orange);
    outline-offset: -1px;
  }

  .mark-reviewed-block {
    padding: 0.75rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
</style>
