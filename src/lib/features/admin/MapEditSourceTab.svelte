<!--
  MapEditSourceTab.svelte — "Source" tab of MapEditModal.
  Provenance fields only; no async work. Every field is bindable so the
  parent's handleSave sees the edits.
-->
<script lang="ts">
  export let source_type: string;
  export let holding_institution: string;
  export let collection: string;
  export let shelfmark: string;
  export let source_url: string;
  export let rights: string;
</script>

<!-- ── Provenance ───────────────────────────── -->
<div class="section-heading">Provenance</div>
<div class="form-grid">
  <label class="form-label">
    <span>Source type <span class="field-hint">holding institution</span></span>
    <select bind:value={source_type} class="form-input">
      <option value="">— unknown —</option>
      <option value="bnf">BnF Gallica</option>
      <option value="ia">Internet Archive</option>
      <option value="efeo">EFEO</option>
      <option value="gallica">Gallica</option>
      <option value="rumsey">David Rumsey</option>
      <option value="self">Self-hosted</option>
      <option value="other">Other</option>
    </select>
  </label>
  <label class="form-label">
    <span>Holding institution <span class="field-hint">where the original lives</span></span>
    <input
      type="text"
      bind:value={holding_institution}
      class="form-input"
      placeholder="e.g. Bibliothèque nationale de France"
    />
  </label>
  <label class="form-label">
    <span>Collection <span class="field-hint">sub-collection at the holder</span></span>
    <input
      type="text"
      bind:value={collection}
      class="form-input"
      placeholder="e.g. Département Cartes et plans"
    />
  </label>
  <label class="form-label">
    <span>Identifier <span class="field-hint">shelfmark / call number</span></span>
    <input
      type="text"
      bind:value={shelfmark}
      class="form-input mono"
      placeholder="e.g. GE D-10312"
    />
  </label>
  <label class="form-label full-width">
    <span>Source URL <span class="field-hint">canonical record at the institution</span></span>
    <input
      type="url"
      bind:value={source_url}
      class="form-input mono"
      placeholder="https://gallica.bnf.fr/ark:…"
    />
  </label>
  <label class="form-label full-width">
    <span>Rights <span class="field-hint">license / copyright</span></span>
    <input
      type="text"
      bind:value={rights}
      class="form-input"
      placeholder="e.g. Public domain, CC BY-SA 4.0"
    />
  </label>
</div>
