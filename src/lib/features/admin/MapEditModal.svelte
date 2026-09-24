<!--
  MapEditModal.svelte — shell for the admin map editor.

  Owns the form state, the tab strip, the always-visible quick bar and the
  Save / Delete actions. Each tab is its own component and binds the fields it
  edits back here; the save payload itself is assembled in mapEditPayload.ts.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { updateMap, deleteMap, type MapRow } from '$lib/data/admin/adminApi';
  import '$styles/components/admin-modals.css';
  import MapEditAboutTab from './MapEditAboutTab.svelte';
  import MapEditSourceTab from './MapEditSourceTab.svelte';
  import MapEditHostingTab from './MapEditHostingTab.svelte';
  import MapEditPipelineTab from './MapEditPipelineTab.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import { toMapEditPayload, labelConfigToForm } from '$lib/data/admin/mapEditPayload';

  export let map: MapRow;

  const dispatch = createEventDispatcher<{
    saved: MapRow;
    deleted: string;
    close: void;
  }>();

  // ── Form state ───────────────────────────────────────────────────────
  // About
  let name = map.name;
  let original_title = map.original_title || '';
  let year = map.year?.toString() || '';
  let year_label = map.date_label || '';
  let creator = map.creator || '';
  let dc_publisher = map.publisher || '';
  let location = map.location || '';
  let map_type = map.map_type || '';
  let dc_description = map.description || '';
  let physical_description = map.physical_description || '';
  let language = map.language || '';
  let extraPairs: { key: string; value: string }[] = Object.entries(
    (map.extra_metadata as Record<string, string>) || {}
  ).map(([k, v]) => ({ key: k, value: String(v ?? '') }));
  let sheet_number = map.sheet_number || '';
  let sheet_half = map.sheet_half || '';

  // Source
  let source_type = map.source_type || '';
  let holding_institution = map.holding_institution || '';
  let collection = map.collection || '';
  let shelfmark = map.shelfmark || '';
  let source_url = map.source_url || '';
  let rights = map.rights || '';

  // Hosting / georef
  let allmaps_id = map.allmaps_id ?? '';
  let annotation_url = map.annotation_url ?? '';

  // Quick bar + workflow flags. Visibility is the status select alone: the
  // is_public / is_featured checkboxes went with migration 060.
  let priority: number = map.priority ?? 0;
  let georef_done: boolean = map.is_georeferenced ?? false;
  let status: string = map.status ?? 'draft';

  // Label Studio config (edited on the Pipeline tab)
  const initialLabelConfig = labelConfigToForm(map.label_config);
  let labelLegendMode: 'simple' | 'list' = initialLabelConfig.mode;
  let labelLegendText = initialLabelConfig.legendText;
  let labelCategories = initialLabelConfig.categories;

  let saving = false;
  let deleting = false;
  let error = '';
  let successMsg = '';
  type EditTab = 'about' | 'source' | 'hosting' | 'pipeline';
  let activeTab: EditTab = 'about';

  const EDIT_TABS = [
    { key: 'about', label: 'About' },
    { key: 'source', label: 'Source' },
    { key: 'hosting', label: 'Hosting & Georef' },
    { key: 'pipeline', label: 'Pipeline' },
  ];

  /** Pipeline is the one tab with a cost, so it loads when it is opened. */
  function pickTab(key: string) {
    activeTab = key as EditTab;
    if (activeTab === 'pipeline' && map.iiif_image) pipelineTab?.loadOcrStatus();
  }
  let pipelineTab: MapEditPipelineTab | null = null;

  // Essentials — the fields that must be filled for a clean catalog listing.
  // Drives the completeness counter shown in the header.
  const ESSENTIAL_KEYS = [
    'name',
    'creator',
    'year_label',
    'source_type',
    'collection',
    'source_url',
    'rights',
    'dc_description',
  ];
  $: essentialValues = {
    name,
    creator,
    year_label,
    source_type,
    collection,
    source_url,
    rights,
    dc_description,
  } as Record<string, string>;
  $: essentialsFilled = ESSENTIAL_KEYS.filter((k) => essentialValues[k]?.toString().trim()).length;

  function flash(msg: string, ms = 2000) {
    successMsg = msg;
    setTimeout(() => (successMsg = ''), ms);
  }

  async function handleSave() {
    if (!name.trim()) {
      error = 'Name is required.';
      return;
    }
    saving = true;
    error = '';
    try {
      const payload = toMapEditPayload({
        name,
        original_title,
        year,
        year_label,
        creator,
        dc_publisher,
        location,
        map_type,
        dc_description,
        physical_description,
        language,
        extraPairs,
        sheet_number,
        sheet_half,
        source_type,
        holding_institution,
        collection,
        shelfmark,
        source_url,
        rights,
        allmaps_id,
        annotation_url,
        priority,
        georef_done,
        status,
        labelLegendMode,
        labelLegendText,
        labelCategories,
      });
      const updated = await updateMap(map.id, payload);
      flash('Saved!');
      dispatch('saved', updated);
    } catch (e: any) {
      error = e.message;
    } finally {
      saving = false;
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete "${map.name}"? This cannot be undone.`)) return;
    deleting = true;
    error = '';
    try {
      await deleteMap(map.id);
      dispatch('deleted', map.id);
    } catch (e: any) {
      error = e.message;
    } finally {
      deleting = false;
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if ((e.target as HTMLElement).classList.contains('modal-backdrop')) {
      dispatch('close');
    }
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="modal-backdrop" on:click={handleBackdropClick}>
  <div class="modal">
    <div class="modal-header">
      <h2 class="modal-title">
        Edit Map
        <span
          class="badge-chip is-sm"
          class:chip-green={essentialsFilled === ESSENTIAL_KEYS.length}
          class:chip-gray={essentialsFilled !== ESSENTIAL_KEYS.length}
          title="Essential fields filled"
        >
          {essentialsFilled}/{ESSENTIAL_KEYS.length}
        </span>
      </h2>
      <button class="btn is-icon is-sm" on:click={() => dispatch('close')} aria-label="Close"
        >✕</button
      >
    </div>

    <!-- Sticky toggle bar — always visible across tabs -->
    <div class="quick-bar">
      <label class="quick-status">
        Status:
        <select bind:value={status} class="status-select status-{status}">
          <option value="draft">Draft</option>
          <option value="public">Public</option>
          <option value="featured">Featured</option>
        </select>
      </label>
      <label class="quick-priority" title="Higher = surfaced first in tools">
        Priority
        <input type="number" bind:value={priority} class="priority-input" min="0" step="1" />
      </label>
    </div>

    <div class="tabs">
      <Tabs
        label="Map fields"
        tabs={EDIT_TABS}
        active={activeTab}
        on:change={(e) => pickTab(e.detail.key)}
      />
    </div>

    <div class="modal-body">
      {#if error}
        <div class="alert alert-error">{error}</div>
      {/if}
      {#if successMsg}
        <div class="alert alert-success">{successMsg}</div>
      {/if}

      {#if activeTab === 'about'}
        <MapEditAboutTab
          bind:name
          bind:original_title
          bind:year
          bind:year_label
          bind:creator
          bind:dc_publisher
          bind:location
          bind:map_type
          bind:dc_description
          bind:physical_description
          bind:language
          bind:extraPairs
          bind:sheet_number
          bind:sheet_half
        />
      {:else if activeTab === 'source'}
        <MapEditSourceTab
          bind:source_type
          bind:holding_institution
          bind:collection
          bind:shelfmark
          bind:source_url
          bind:rights
        />
      {:else if activeTab === 'hosting'}
        <MapEditHostingTab
          bind:map
          bind:allmaps_id
          bind:annotation_url
          bind:original_title
          bind:creator
          bind:year_label
          bind:shelfmark
          bind:rights
          bind:language
          bind:physical_description
          bind:source_url
          bind:holding_institution
          on:saved={(e) => dispatch('saved', e.detail)}
          on:notice={(e) => flash(e.detail, 3000)}
          on:error={(e) => (error = e.detail)}
        />
      {:else if activeTab === 'pipeline'}
        <MapEditPipelineTab
          bind:this={pipelineTab}
          mapId={map.id}
          iiifImage={map.iiif_image}
          bind:georef_done
          bind:labelLegendMode
          bind:labelLegendText
          bind:labelCategories
        />
      {/if}
    </div>

    <div class="modal-footer">
      <button class="btn is-danger" on:click={handleDelete} disabled={deleting}>
        {deleting ? 'Deleting...' : 'Delete'}
      </button>
      <div class="footer-right">
        <button class="btn" on:click={() => dispatch('close')}>Cancel</button>
        <button class="btn is-primary" on:click={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  </div>
</div>
