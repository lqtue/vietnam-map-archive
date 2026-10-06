<!--
  MapEditAboutTab.svelte — "About" tab of MapEditModal.
  Pure form: descriptive metadata + free-form custom fields. Every field is
  bindable so the parent's handleSave sees the edits.
-->
<script lang="ts">
  import { MAP_TYPES, MAP_SUBJECTS, DEPICTED_STATES } from '$lib/core/mapTaxonomy';
  import { onMount } from 'svelte';
  import SheetPrintingReview from './SheetPrintingReview.svelte';
  export let name: string;
  export let original_title: string;
  export let year: string;
  export let year_label: string;
  export let creator: string;
  export let dc_publisher: string;
  export let location: string;
  export let map_type: string;
  export let map_subjects: string[] = [];
  export let depicted_state = 'unknown';
  export let classification_note = '';
  export let classification_source_url = '';
  export let dc_description: string;
  export let physical_description: string;
  export let language: string;
  export let extraPairs: { key: string; value: string }[];
  export let sheet_number: string;
  export let sheet_half: string;
  export let edition: string;
  export let series_id: string;
  export let printing_id: string;
  export let duplicate_of_map_id: string;
  export let archive_reason: string;
  type SeriesOption = {
    id: string;
    key: string;
    name: string;
    code: string | null;
    scale_denominator: number | null;
  };
  let seriesOptions: SeriesOption[] = [];
  onMount(async () => {
    try {
      const response = await fetch('/api/admin/series');
      if (response.ok) seriesOptions = await response.json();
    } catch {
      /* keep the current linkage visible if the lookup is unavailable */
    }
  });
  function changeSeries(value: string) {
    if (series_id !== value) {
      series_id = value;
      printing_id = '';
      duplicate_of_map_id = '';
    }
  }
</script>

<!-- ── Title & Date ───────────────────────────── -->
<div class="section-heading">Title & date</div>
<div class="form-grid">
  <label class="form-label full-width">
    <span>Display name <span class="required">*</span></span>
    <input type="text" bind:value={name} class="form-input" />
  </label>
  <label class="form-label full-width">
    <span>Original title <span class="field-hint">as printed on the map</span></span>
    <input
      type="text"
      bind:value={original_title}
      class="form-input"
      placeholder="Full original map title"
    />
  </label>
  <label class="form-label">
    <span>Year <span class="field-hint">numeric, single year</span></span>
    <input type="number" bind:value={year} class="form-input" placeholder="e.g. 1890" />
  </label>
  <label class="form-label">
    <span>Date <span class="field-hint">range or fuzzy</span></span>
    <input
      type="text"
      bind:value={year_label}
      class="form-input"
      placeholder="e.g. 1882 or 1882–1885"
    />
  </label>
</div>

<div class="section-heading">Series and printing identity</div>
<div class="form-grid">
  <label class="form-label">
    <span>Series <span class="field-hint">leave unresolved when identity is unknown</span></span>
    <select
      value={series_id}
      on:change={(e) => changeSeries(e.currentTarget.value)}
      class="form-input"
    >
      <option value="">Unresolved</option>
      {#each seriesOptions as item (item.id)}
        <option value={item.id}
          >{item.name} · {item.key}{item.scale_denominator
            ? ` · 1:${item.scale_denominator.toLocaleString()}`
            : ''}</option
        >
      {/each}
    </select>
  </label>
  <label class="form-label">
    <span>Printing identity</span>
    <input type="text" value={printing_id || 'Unresolved'} class="form-input" readonly />
  </label>
  <label class="form-label">
    <span
      >Duplicate target <span class="field-hint"
        >Public survivor with the same verified printing</span
      ></span
    >
    <input type="text" bind:value={duplicate_of_map_id} class="form-input" />
  </label>
  <label class="form-label full-width">
    <span>Archive reason</span>
    <textarea bind:value={archive_reason} class="form-input" rows="2"></textarea>
  </label>
</div>
{#if series_id && sheet_number}
  {#key `${series_id}:${sheet_number}`}
    <SheetPrintingReview
      seriesId={series_id}
      sheetNumber={sheet_number}
      on:selected={(event) => (printing_id = event.detail)}
    />
  {/key}
{/if}

<!-- ── Authorship ───────────────────────────── -->
<div class="section-heading">Authorship</div>
<div class="form-grid">
  <label class="form-label">
    <span>Creator <span class="field-hint">cartographer / surveyor</span></span>
    <input
      type="text"
      bind:value={creator}
      class="form-input"
      placeholder="Cartographer or author"
    />
  </label>
  <label class="form-label">
    <span>Publisher</span>
    <input
      type="text"
      bind:value={dc_publisher}
      class="form-input"
      placeholder="e.g. Service Géographique de l'Indochine"
    />
  </label>
</div>

<!-- ── What it shows ───────────────────────────── -->
<div class="section-heading">What it shows</div>
<div class="form-grid">
  <label class="form-label">
    <span>Location <span class="field-hint">city / region</span></span>
    <input
      type="text"
      bind:value={location}
      class="form-input"
      placeholder="e.g. Saigon, Hanoi, Hue"
    />
  </label>
  <label class="form-label">
    <span>Map type</span>
    <select bind:value={map_type} class="form-input">
      <option value="">— unknown —</option>
      {#each MAP_TYPES as type (type.key)}
        <option value={type.key}>{type.en}</option>
      {/each}
    </select>
  </label>
  <label class="form-label">
    <span>Subjects <span class="field-hint">optional, multiple</span></span>
    <select multiple bind:value={map_subjects} class="form-input">
      {#each MAP_SUBJECTS as subject (subject.key)}
        <option value={subject.key}>{subject.en}</option>
      {/each}
    </select>
  </label>
  <label class="form-label">
    <span>Depicted state</span>
    <select bind:value={depicted_state} class="form-input">
      {#each DEPICTED_STATES as state (state)}
        <option value={state}>{state}</option>
      {/each}
    </select>
  </label>
  <label class="form-label">
    <span>Classification evidence</span>
    <textarea bind:value={classification_note} class="form-input" rows="3"></textarea>
  </label>
  <label class="form-label">
    <span>Classification source URL</span>
    <input type="url" bind:value={classification_source_url} class="form-input" />
  </label>
  <label class="form-label">
    <span>Sheet number <span class="field-hint">series cell, e.g. 6330-4</span></span>
    <input type="text" bind:value={sheet_number} class="form-input" placeholder="e.g. 6330-4" />
  </label>
  <label class="form-label">
    <span>Sheet half</span>
    <select bind:value={sheet_half} class="form-input">
      <option value="">— whole / not applicable —</option>
      <option value="E">East (E)</option>
      <option value="W">West (W)</option>
      <option value="whole">Whole</option>
    </select>
  </label>
  <label class="form-label">
    <span>Edition <span class="field-hint">as printed, e.g. 2-AMS</span></span>
    <input type="text" bind:value={edition} class="form-input" placeholder="e.g. 5-DMA" />
  </label>
</div>

<!-- ── Description ───────────────────────────── -->
<div class="section-heading">Description</div>
<div class="form-grid">
  <label class="form-label full-width">
    <span>Summary</span>
    <textarea
      bind:value={dc_description}
      class="form-textarea"
      rows="4"
      placeholder="Brief description of what this map shows, who made it, and why it matters."
    ></textarea>
  </label>
</div>

<!-- ── Physical ───────────────────────────── -->
<div class="section-heading">Physical & language</div>
<div class="form-grid">
  <label class="form-label">
    <span>Physical description <span class="field-hint">size, medium</span></span>
    <input
      type="text"
      bind:value={physical_description}
      class="form-input"
      placeholder="e.g. 67 × 57 cm, colour lithograph"
    />
  </label>
  <label class="form-label">
    <span>Language</span>
    <input
      type="text"
      bind:value={language}
      class="form-input"
      placeholder="e.g. français, English"
    />
  </label>
</div>

<!-- ── Custom fields ───────────────────────────── -->
<div class="section-heading">
  Custom fields <span class="field-hint">e.g. mirrors_original_for</span>
</div>
<div class="extra-meta-section">
  {#each extraPairs as pair, i (pair)}
    <div class="extra-pair">
      <input class="form-input extra-key" bind:value={pair.key} placeholder="Field name" />
      <input class="form-input extra-val" bind:value={pair.value} placeholder="Value" />
      <button
        type="button"
        class="btn is-xs is-danger"
        on:click={() => (extraPairs = extraPairs.filter((_, j) => j !== i))}>×</button
      >
    </div>
  {/each}
  <button
    type="button"
    class="btn is-xs is-success add-pair"
    on:click={() => (extraPairs = [...extraPairs, { key: '', value: '' }])}>+ Add field</button
  >
</div>
