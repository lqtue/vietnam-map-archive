<!--
  MapEditAboutTab.svelte — "About" tab of MapEditModal.
  Pure form: descriptive metadata + free-form custom fields. Every field is
  bindable so the parent's handleSave sees the edits.
-->
<script lang="ts">
  export let name: string;
  export let original_title: string;
  export let year: string;
  export let year_label: string;
  export let creator: string;
  export let dc_publisher: string;
  export let location: string;
  export let map_type: string;
  export let dc_description: string;
  export let physical_description: string;
  export let language: string;
  export let extraPairs: { key: string; value: string }[];
  export let sheet_number: string;
  export let sheet_half: string;
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
      <option value="cadastral">Cadastral</option>
      <option value="topographic">Topographic</option>
      <option value="city_plan">City Plan</option>
      <option value="panorama">Panorama</option>
      <option value="other">Other</option>
    </select>
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
  Custom fields <span class="field-hint">e.g. edition, mirrors_original_for</span>
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
