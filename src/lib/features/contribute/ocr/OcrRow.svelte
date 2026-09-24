<!--
  OcrRow.svelte — one row of the /scan?mode=text review table.

  Extracted from `OcrSidebar`, which had grown to 928 lines with 145 of them
  being this row. It is the part that changes when the review changes — a new
  column, a new verdict, a different face for a printed line — and it was the
  part hardest to find.

  It owns no state. `ext` is the sidebar's own row object, edited in place
  through `bind:value` and committed by the parent on `commit`; `rowEl` and
  `inputEl` are bound back up so the controller can scroll to a row and put the
  cursor in it. The `_edit*` fields are the unsaved edit, `text`/`category` what
  the pipeline wrote, `*_validated` what a person last saved — the dot compares
  them to say whether there is anything to save.

  `printedView` is the Index job: a line of a printed table has a cell and a
  number where a mark on the map has a category and a confidence.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { OCR_CATEGORIES, STATUS_COLORS } from '../shared/constants';
  import type { EditableOcrExtraction } from '../shared/types';
  import type { LegendEntry, PrintedLine, SuspectReason } from './legendIndex';

  export let ext: EditableOcrExtraction;
  export let selected = false;
  /** Index job: show the printed cell and number instead of category + confidence. */
  export let printedView = false;
  /** What the sheet's own legend says this numeral names, if it names one. */
  export let entry: LegendEntry | null = null;
  /** Why the index disagrees with this numeral, if it does. */
  export let reasons: SuspectReason[] | undefined = undefined;
  /** The printed line this row is, when `printedView`. */
  export let line: PrintedLine | null = null;
  /** Bound up so the parent can scroll to the row and focus its field. */
  export let rowEl: HTMLTableRowElement | null = null;
  export let inputEl: HTMLInputElement | null = null;

  /* The categories the model infers from surrounding context. On a one- or
     two-character read there is no context to infer from, so its answer there
     is noise — a legend key-letter comes back `building 95%`. The derived
     classes (legend_ref, legend_entry, title) are not guesses and still show. */
  const GUESSED_CATS = ['street', 'place', 'building', 'institution', 'hydrology'];
  $: catIsGuesswork =
    (ext._editText ?? '').trim().length <= 2 && GUESSED_CATS.includes(ext._editCategory);

  const dispatch = createEventDispatcher<{
    select: { id: string };
    zoomToExtraction: { globalX: number; globalY: number; globalW: number; globalH: number };
    /** The edit is in `ext` already; the parent decides when it is written. */
    commit: void;
    verdict: { status: 'pending' | 'validated' | 'rejected' };
  }>();
</script>

<tr
  class="shape-tr status-{ext.status}"
  class:row-suspect={reasons}
  class:row-selected={selected}
  bind:this={rowEl}
  on:click={() => dispatch('select', { id: ext.id })}
  on:dblclick={() =>
    dispatch('zoomToExtraction', {
      globalX: ext.global_x,
      globalY: ext.global_y,
      globalW: ext.global_w,
      globalH: ext.global_h,
    })}
  title="Double-click to zoom"
>
  <td class="col-dot">
    {#if ext._saving}
      <span class="dot dot--saving" title="saving…"></span>
    {:else}
      <span
        class="dot"
        class:dot--dirty={ext._editText !== (ext.text_validated ?? ext.text) ||
          ext._editCategory !== (ext.category_validated ?? ext.category)}
        style="background:{STATUS_COLORS[ext.status]}"
        title={ext.status}
      ></span>
    {/if}
  </td>
  <td class="col-text">
    <input
      class="cell-input"
      type="text"
      bind:value={ext._editText}
      bind:this={inputEl}
      placeholder="Text…"
      title={ext._editText}
      on:blur={() => dispatch('commit')}
      on:keydown={(e) => {
        if (e.key === 'Enter') {
          dispatch('commit');
          (e.currentTarget as HTMLInputElement).blur();
        }
      }}
      aria-label="Extraction text"
    />
    {#if entry}
      <span class="ref-name" title={entry.grid ? `printed grid ${entry.grid}` : undefined}
        >{entry.name}{entry.grid ? ` · ${entry.grid}` : ''}</span
      >
    {/if}
    {#if reasons}
      <span class="ref-flag">{reasons.join(' · ')}</span>
    {/if}
  </td>
  <!--
    The dropdown is mounted for the selected row only. It is 15 of a
    row's ~29 DOM nodes — the select, its wrapper, ten options and a
    chevron — which on a full table was half the markup standing by
    for an edit that most rows never get. Clicking a row selects it,
    so the control is one click from wherever the eye already is.
  -->
  <td class="col-cat">
    {#if printedView}
      <span class="cell-grid">{line?.grid ?? ''}</span>
    {:else if selected}
      <div class="dropdown-wrap">
        <select
          class="cell-select"
          bind:value={ext._editCategory}
          on:change={() => dispatch('commit')}
          aria-label="Category"
        >
          {#each OCR_CATEGORIES as cat (cat)}
            <option value={cat}>{cat}</option>
          {/each}
        </select>
        <svg
          class="dropdown-chevron"
          width="10"
          height="10"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"><polyline points="4 6 8 10 12 6" /></svg
        >
      </div>
    {:else if catIsGuesswork}
      <span class="cell-cat">—</span>
    {:else}
      <span class="cell-cat">{ext._editCategory}</span>
    {/if}
  </td>
  {#if printedView}
    <td class="col-conf">
      <span class="cell-n">{line?.n ?? ''}</span>
    </td>
  {/if}
  <td class="col-actions">
    {#if ext._saving}
      <span class="saving-dot">…</span>
    {:else}
      <button
        type="button"
        class="row-action validate-action"
        on:click={() =>
          dispatch('verdict', { status: ext.status === 'validated' ? 'pending' : 'validated' })}
        title={ext.status === 'validated' ? 'Unvalidate' : 'Validate (✓)'}
        class:active-validate={ext.status === 'validated'}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg
        >
      </button>
      <button
        type="button"
        class="row-action reject-action"
        on:click={() =>
          dispatch('verdict', { status: ext.status === 'rejected' ? 'pending' : 'rejected' })}
        title={ext.status === 'rejected' ? 'Unreject' : 'Reject (✗)'}
        class:active-reject={ext.status === 'rejected'}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12" /></svg
        >
      </button>
    {/if}
  </td>
</tr>

<style>
  /* Column geometry is `shapes-table.css` — it has to reach the `<th>`s in the
     parent as well, and scoped CSS does not cross a component boundary. */

  .shape-tr.status-validated td {
    background: var(--tone-green-wash);
  }
  .shape-tr.status-rejected td {
    background: var(--tone-red-wash);
    opacity: 0.65;
  }
  .shape-tr.row-selected td {
    outline: 2px solid var(--color-blue);
    outline-offset: -1px;
    background: var(--tone-blue-wash) !important;
  }
  .shape-tr.row-suspect {
    box-shadow: inset 2px 0 0 var(--tone-red-ink);
  }
  .dot--dirty {
    background: var(--color-orange) !important;
    color: var(--color-on-accent);
    border-style: dashed;
    border-color: var(--tone-amber-ink);
  }
  .dot--saving {
    background: transparent !important;
    border: 1.5px dashed var(--color-gray-400);
    animation: pulse 0.8s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,
    100% {
      opacity: 0.4;
    }
    50% {
      opacity: 1;
    }
  }
  /* What the numeral names, from the sheet's own printed legend. Sits under the
     input rather than beside it: the column is ~90px and the names are long. */
  .ref-name {
    display: block;
    font-size: 0.62rem;
    color: var(--sb-text-meta);
    padding-left: 0.3rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ref-flag {
    display: inline-block;
    margin: 0.1rem 0 0 0.3rem;
    padding: 0 0.3rem;
    border-radius: 0.6rem;
    font-size: 0.58rem;
    font-weight: var(--font-bold);
    color: var(--tone-red-ink);
    background: var(--tone-red-pale);
  }
  /* Reads as the select it becomes: same box, same inset, no border. */
  .cell-cat {
    display: block;
    padding: 0.15rem 0.3rem;
    font-size: 0.65rem;
    color: var(--sb-text-meta);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* The two columns a printed block replaces its category and confidence with.
     Monospaced digits so a column of cells and a column of numbers line up the
     way they do on the paper. */
  .cell-grid,
  .cell-n {
    display: block;
    padding: 0.15rem 0.3rem;
    font-size: 0.68rem;
    font-variant-numeric: tabular-nums;
    color: var(--color-text);
  }
  .cell-n {
    text-align: right;
    opacity: 0.7;
  }
  .saving-dot {
    font-size: 0.75rem;
    color: var(--color-text);
    opacity: 0.4;
    padding-right: 0.4rem;
  }
  .validate-action:hover,
  .validate-action.active-validate {
    color: var(--tone-green-ink);
    background: var(--tone-green-pale);
  }
  .validate-action.active-validate {
    opacity: 1;
  }
  .reject-action:hover,
  .reject-action.active-reject {
    color: var(--tone-red-ink);
    background: var(--tone-red-pale);
  }
  .reject-action.active-reject {
    opacity: 1;
  }
</style>
