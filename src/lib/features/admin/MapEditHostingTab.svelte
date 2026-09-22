<!--
  MapEditHostingTab.svelte — "Hosting & Georef" tab of MapEditModal.

  Owns every async subsystem that touches where the image lives:
  manifest metadata auto-fill, the map_iiif_sources list + add form,
  mirror-to-R2, Allmaps-ID lookup, IA image upload and the GCP editor.

  Metadata fields filled from the manifest are bound back to the parent so
  they land in the save payload alongside the About/Source tabs' edits.
-->
<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import {
    uploadMapImage,
    fetchIIIFSources,
    addIIIFSource,
    setPrimaryIIIFSource,
    deleteIIIFSource,
    fetchIIIFMetadata,
    lookupAllmapsId,
    mirrorToR2,
    syncAllmaps,
    type MapRow,
    type IIIFSourceRow,
    type MirrorR2Result,
  } from '$lib/data/admin/adminApi';
  import NeatlineEditor from './NeatlineEditor.svelte';
  import { allmapsEditorSourceUrl } from '$lib/core/iiif/annotationUrl';
  import { fetchAnnotationSourceId } from '$lib/data/maps/georef';

  export let map: MapRow;

  // Bindable — committed by the parent's handleSave
  export let allmaps_id: string;
  export let annotation_url: string;
  export let original_title: string;
  export let creator: string;
  export let year_label: string;
  export let shelfmark: string;
  export let rights: string;
  export let language: string;
  export let physical_description: string;
  export let source_url: string;
  export let holding_institution: string;

  const dispatch = createEventDispatcher<{
    /** The row changed server-side (mirror-r2) — parent should refresh its list. */
    saved: MapRow;
    notice: string;
    error: string;
  }>();

  // ── IIIF sources ───────────────────────────────────────────────────
  let iiifSources: IIIFSourceRow[] = [];
  let loadingSources = false;
  let sourcesError = '';
  let showAddSource = false;
  let addingSource = false;
  let newManifestUrl = '';
  let newIiifImage = '';
  let newLabel = '';
  let newSourceType = '';
  let fetchingMeta = false;
  let fetchMetaError = '';

  async function loadSources() {
    loadingSources = true;
    sourcesError = '';
    try {
      iiifSources = await fetchIIIFSources(map.id);
    } catch (e: any) {
      sourcesError = e.message;
    } finally {
      loadingSources = false;
    }
  }

  onMount(loadSources);

  async function handleFetchMeta() {
    if (!newManifestUrl.trim()) return;
    fetchingMeta = true;
    fetchMetaError = '';
    try {
      const meta = await fetchIIIFMetadata(newManifestUrl.trim());
      if (meta.imageServiceUrl) newIiifImage = meta.imageServiceUrl;
      if (meta.title && !newLabel) newLabel = meta.title.slice(0, 60);
      if (!newSourceType) {
        const u = newManifestUrl.toLowerCase();
        if (u.includes('gallica.bnf.fr')) newSourceType = 'bnf';
        else if (u.includes('archive.org')) newSourceType = 'ia';
        else newSourceType = 'other';
      }
    } catch (e: any) {
      fetchMetaError = e.message;
    } finally {
      fetchingMeta = false;
    }
  }

  async function handleAddSource() {
    if (!newIiifImage.trim()) {
      fetchMetaError = 'IIIF image URL is required.';
      return;
    }
    addingSource = true;
    fetchMetaError = '';
    try {
      await addIIIFSource(map.id, {
        label: newLabel.trim() || undefined,
        source_type: newSourceType.trim() || undefined,
        iiif_manifest: newManifestUrl.trim() || undefined,
        iiif_image: newIiifImage.trim(),
        is_primary: iiifSources.length === 0,
      });
      newManifestUrl = '';
      newIiifImage = '';
      newLabel = '';
      newSourceType = '';
      await loadSources();
    } catch (e: any) {
      fetchMetaError = e.message;
    } finally {
      addingSource = false;
    }
  }

  async function handleSetPrimary(sourceId: string) {
    try {
      await setPrimaryIIIFSource(map.id, sourceId);
      await loadSources();
    } catch (e: any) {
      sourcesError = e.message;
    }
  }

  async function handleDeleteSource(sourceId: string) {
    if (!confirm('Remove this IIIF source?')) return;
    try {
      await deleteIIIFSource(map.id, sourceId);
      await loadSources();
    } catch (e: any) {
      sourcesError = e.message;
    }
  }

  // True when maps.iiif_image points to R2 but no map_iiif_sources row exists for it
  $: orphanR2 = !!(
    map.iiif_image?.includes('maparchive.vn') &&
    iiifSources.length > 0 &&
    !iiifSources.some((s) => s.iiif_image?.includes('maparchive.vn'))
  );

  // ── Auto-fill IIIF manifest metadata ───────────────────────────────
  let fetchingManifest = false;
  let fetchManifestStatus = '';

  async function handleFetchManifestMeta() {
    const manifestUrl = (
      map.iiif_manifest ||
      iiifSources.find((s) => !!s.iiif_image)?.iiif_image ||
      ''
    ).trim();
    if (!manifestUrl) {
      fetchManifestStatus = 'No IIIF manifest URL on this map.';
      return;
    }
    fetchingManifest = true;
    fetchManifestStatus = '';
    try {
      const meta = await fetchIIIFMetadata(manifestUrl);
      // Fill only empty fields — never overwrite existing curation
      const filled: string[] = [];
      const fill = (current: string, next: unknown, setter: (v: string) => void, label: string) => {
        if (!current.trim() && typeof next === 'string' && next.trim()) {
          setter(next.trim());
          filled.push(label);
        }
      };
      fill(original_title, meta.title, (v) => (original_title = v), 'title');
      fill(creator, meta.creator, (v) => (creator = v), 'creator');
      fill(year_label, meta.date, (v) => (year_label = v), 'date');
      fill(shelfmark, meta.shelfmark, (v) => (shelfmark = v), 'shelfmark');
      fill(rights, meta.rights, (v) => (rights = v), 'rights');
      fill(language, meta.language, (v) => (language = v), 'language');
      fill(
        physical_description,
        meta.physicalDescription,
        (v) => (physical_description = v),
        'physical'
      );
      fill(source_url, meta.sourceUrl, (v) => (source_url = v), 'source_url');
      // Derive holding_institution from attribution
      fill(holding_institution, meta.attribution, (v) => (holding_institution = v), 'holder');
      fetchManifestStatus = filled.length
        ? `✓ Filled: ${filled.join(', ')}. Review and Save.`
        : 'All fields already populated — nothing to fill.';
    } catch (e: any) {
      fetchManifestStatus = `✗ ${e.message?.slice(0, 200) || 'fetch failed'}`;
    } finally {
      fetchingManifest = false;
    }
  }

  // ── Mirror to R2 ───────────────────────────────────────────────────
  let mirrorLoading = false;
  let mirrorResult: MirrorR2Result | null = null;
  let mirrorError = '';
  $: isMirrored = !!annotation_url || !!map.annotation_url;

  /** Shared by both buttons: only the source of the annotation differs. */
  async function runMirror(fetchUpstream: boolean) {
    mirrorLoading = true;
    mirrorError = '';
    mirrorResult = null;
    try {
      const result = fetchUpstream ? await syncAllmaps(map.id) : await mirrorToR2(map.id);
      mirrorResult = result;
      annotation_url = result.annotation_url;
      // Update the row locally so the Georef section reflects it immediately
      map = {
        ...map,
        annotation_url: result.annotation_url,
        iiif_image: result.iiif_image,
        thumbnail: result.thumbnail || `${result.iiif_image}/full/256,/0/default.jpg`,
      };
      await loadSources();
      dispatch('saved', map); // Notify parent to refresh list
    } catch (e: any) {
      mirrorError = e.message;
    } finally {
      mirrorLoading = false;
    }
  }

  const handleMirrorToR2 = () => runMirror(false);
  const handleSyncAllmaps = () => runMirror(true);

  // ── Allmaps ID lookup ──────────────────────────────────────────────
  let lookingUpAllmaps = false;
  let lookupAllmapsStatus = '';

  async function handleLookupAllmapsId() {
    const iiif = (map.iiif_image || iiifSources.find((s) => s.is_primary)?.iiif_image || '').trim();
    if (!iiif) {
      lookupAllmapsStatus = 'No IIIF image URL set on this map.';
      return;
    }
    lookingUpAllmaps = true;
    lookupAllmapsStatus = '';
    try {
      const { allmapsId, hasAnnotation } = await lookupAllmapsId(iiif);
      allmaps_id = allmapsId;
      lookupAllmapsStatus = hasAnnotation
        ? `✓ Found georeferenced annotation. Click Save to persist.`
        : `Derived ID, but no georef yet on annotations.allmaps.org. Place GCPs in Allmaps Editor first.`;
    } catch (e: any) {
      lookupAllmapsStatus = `✗ ${e.message}`;
    } finally {
      lookingUpAllmaps = false;
    }
  }

  // ── IA image upload ────────────────────────────────────────────────
  let uploading = false;
  let uploadStatus = '';

  async function handleImageUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) return;

    uploading = true;
    uploadStatus = 'Uploading to Internet Archive...';
    try {
      const result = await uploadMapImage(map.id, input.files[0]);
      uploadStatus = `Uploaded! IIIF URL: ${result.iiif_url}`;
    } catch (e: any) {
      dispatch('error', e.message);
      uploadStatus = '';
    } finally {
      uploading = false;
      input.value = '';
    }
  }

  // ── Derived georef links ───────────────────────────────────────────
  // Self-hosted = an annotation_url override is set (typically by mirror-r2).
  $: isSelfHosted = !!annotation_url;
  // Effective annotation URL: override wins, else build from bare allmaps_id.
  $: annotationUrl =
    annotation_url || (allmaps_id ? `https://annotations.allmaps.org/images/${allmaps_id}` : '');
  // Ground truth for which source the annotation is really fit to — r2
  // included, since the District 4 series' GCPs are re-fit against their R2
  // mirror. Guarded against the map changing mid-fetch (the modal can be
  // reused for a different row without remounting).
  let verifiedSourceId: string | null = null;
  /* eslint-disable svelte/infinite-reactive-loop -- writes verifiedSourceId
     asynchronously, guarded by URL match; editorAllmapsUrl below only reads
     it and writes nothing back, so there is no real cycle. */
  $: if (annotationUrl) {
    const forUrl = annotationUrl;
    fetchAnnotationSourceId(forUrl).then((id) => {
      if (forUrl === annotationUrl) verifiedSourceId = id;
    });
  } else {
    verifiedSourceId = null;
  }
  /* eslint-enable svelte/infinite-reactive-loop */
  // Shared with the share page's "Fix georeference" link — see
  // $lib/data/maps/georef.ts for why an R2 source is skipped by default and
  // why an annotation URL must not take /info.json.
  $: editorAllmapsUrl = allmapsEditorSourceUrl(
    { ...map, annotation_url, allmaps_id },
    iiifSources,
    verifiedSourceId
  );
</script>

<div class="hosting-section">
  <!-- ── Auto-fill from IIIF manifest ─────────────────────── -->
  <div class="hosting-subsection hosting-autofill">
    <div class="subsection-heading autofill-heading">Auto-fill metadata from manifest</div>
    <p class="autofill-desc">
      Fetches the map's IIIF manifest and fills empty Metadata fields (title, creator, date,
      shelfmark, rights, language, source URL, holding institution). Existing values are never
      overwritten.
    </p>
    <button
      type="button"
      class="btn is-sm"
      on:click={handleFetchManifestMeta}
      disabled={fetchingManifest || !map.iiif_manifest}
    >
      {fetchingManifest ? 'Fetching…' : 'Fetch metadata from IIIF manifest'}
    </button>
    {#if !map.iiif_manifest}
      <span class="lookup-status lookup-status--dim">
        Set the IIIF manifest URL on this map first.
      </span>
    {/if}
    {#if fetchManifestStatus}
      <div class="lookup-status lookup-status--block">{fetchManifestStatus}</div>
    {/if}
  </div>

  <!-- ── Image Sources ─────────────────────────────────────── -->
  <div class="hosting-subsection">
    <div class="subsection-heading">Image Sources</div>

    {#if sourcesError}
      <div class="alert alert-error">{sourcesError}</div>
    {/if}
    {#if orphanR2}
      <div class="orphan-warning">
        ⚠ maps.iiif_image points to R2 but no R2 source row exists — click "Mirror to R2" below to
        re-sync.
      </div>
    {/if}

    {#if loadingSources}
      <p class="empty-state">Loading sources…</p>
    {:else}
      <div class="sources-list">
        {#each iiifSources as src (src.id)}
          <div class="source-row" class:source-row--primary={src.is_primary}>
            <div class="source-info">
              <div class="source-label-row">
                <span class="source-label">{src.label || src.source_type || 'source'}</span>
                {#if src.source_type}
                  <span class="badge-chip is-sm chip-gray">{src.source_type}</span>
                {/if}
                {#if src.is_primary}
                  <span class="primary-badge">★ PRIMARY</span>
                {/if}
              </div>
              <span class="source-url mono"
                >{src.iiif_image.slice(0, 72)}{src.iiif_image.length > 72 ? '…' : ''}</span
              >
            </div>
            <div class="source-actions">
              {#if !src.is_primary}
                <button class="btn is-sm" on:click={() => handleSetPrimary(src.id)}>
                  Set primary
                </button>
              {/if}
              <button class="btn is-danger is-sm" on:click={() => handleDeleteSource(src.id)}>
                Remove
              </button>
            </div>
          </div>
        {:else}
          <p class="empty-state">No IIIF sources yet.</p>
        {/each}
      </div>

      <button class="btn is-sm add-source-toggle" on:click={() => (showAddSource = !showAddSource)}>
        {showAddSource ? '− Hide form' : '+ Add source'}
      </button>

      {#if showAddSource}
        <div class="add-source-form">
          {#if fetchMetaError}
            <div class="alert alert-error">{fetchMetaError}</div>
          {/if}
          <div class="form-grid">
            <label class="form-label full-width">
              <span>Manifest URL</span>
              <div class="input-row">
                <input
                  type="url"
                  bind:value={newManifestUrl}
                  class="form-input mono"
                  placeholder="https://…/manifest.json"
                />
                <button class="btn" on:click={handleFetchMeta} disabled={fetchingMeta}>
                  {fetchingMeta ? '…' : 'Fetch'}
                </button>
              </div>
            </label>
            <label class="form-label full-width">
              <span>IIIF Image Service URL <span class="required">*</span></span>
              <input
                type="url"
                bind:value={newIiifImage}
                class="form-input mono"
                placeholder="https://…/iiif/ark:…/f1"
              />
            </label>
            <label class="form-label">
              <span>Label</span>
              <input
                type="text"
                bind:value={newLabel}
                class="form-input"
                placeholder="e.g. BnF Gallica"
              />
            </label>
            <label class="form-label">
              <span>Source Type</span>
              <select bind:value={newSourceType} class="form-input">
                <option value="">—</option>
                <option value="bnf">bnf</option>
                <option value="ia">ia</option>
                <option value="efeo">efeo</option>
                <option value="rumsey">rumsey</option>
                <option value="r2">r2</option>
                <option value="other">other</option>
              </select>
            </label>
          </div>
          <button
            class="btn is-primary"
            on:click={handleAddSource}
            disabled={addingSource || !newIiifImage}
          >
            {addingSource ? 'Adding…' : 'Add Source'}
          </button>
        </div>
      {/if}
    {/if}
  </div>

  <!-- ── R2 / Tiling ────────────────────────────────────────── -->
  <div class="hosting-subsection">
    <div class="subsection-heading">
      R2 / Tiling
      {#if isMirrored}
        <span class="badge-chip is-sm chip-green">Mirrored</span>
      {:else}
        <span class="badge-chip is-sm chip-gray">Not mirrored</span>
      {/if}
    </div>
    <p class="panel-note">
      Clones the Allmaps annotation to Supabase Storage and sets <code>iiif.maparchive.vn</code> as the
      primary tile source. After clicking, run the printed CLI command to upload tiles.
    </p>
    {#if mirrorError}
      <div class="alert alert-error">{mirrorError}</div>
    {/if}
    {#if mirrorResult}
      <div class="alert alert-success">Annotation saved. Run this to upload tiles:</div>
      <pre class="mirror-cmd">{mirrorResult.tile_command}</pre>
      {#if mirrorResult.download_url}
        <p class="panel-note">
          Source: <a href={mirrorResult.download_url} target="_blank" class="mono-link"
            >{mirrorResult.download_url}</a
          >
        </p>
      {/if}
    {/if}
    <button class="btn is-lg" on:click={handleMirrorToR2} disabled={mirrorLoading || !allmaps_id}>
      {mirrorLoading ? 'Mirroring…' : isMirrored ? 'Re-mirror to R2' : 'Mirror to R2'}
    </button>
    <button
      class="btn is-lg"
      on:click={handleSyncAllmaps}
      disabled={mirrorLoading || !allmaps_id}
      title="Re-read the annotation from allmaps.org after editing the georeference there. The current copy is kept as history."
    >
      {mirrorLoading ? 'Fetching…' : 'Fetch latest from Allmaps'}
    </button>
  </div>

  <!-- ── Georeference ───────────────────────────────────────── -->
  <div class="hosting-subsection">
    <div class="subsection-heading">Georeference</div>
    <label class="form-label full-width">
      <span>Allmaps ID <span class="required">*</span></span>
      <div class="allmaps-id-row">
        <input
          type="text"
          bind:value={allmaps_id}
          class="form-input mono"
          placeholder="16-char hex (auto-derived from IIIF URL)"
        />
        <button
          type="button"
          class="btn is-sm"
          on:click={handleLookupAllmapsId}
          disabled={lookingUpAllmaps || !map.iiif_image}
        >
          {lookingUpAllmaps ? 'Looking up…' : 'Fetch from Allmaps'}
        </button>
      </div>
      {#if lookupAllmapsStatus}<span class="lookup-status">{lookupAllmapsStatus}</span>{/if}
    </label>
    <label class="form-label full-width">
      <span
        >Annotation URL override <span class="dim">— optional, used when self-hosting via R2</span
        ></span
      >
      <input
        type="text"
        bind:value={annotation_url}
        class="form-input mono"
        placeholder="https://…/annotations/<map-id>.json (set automatically by Mirror to R2)"
      />
    </label>
    <div class="georef-links">
      <a href={annotationUrl} target="_blank" class="btn" class:is-disabled={!annotationUrl}>
        View Annotation ↗
      </a>
      <a
        href={editorAllmapsUrl
          ? `https://editor.allmaps.org/#/collection?url=${encodeURIComponent(editorAllmapsUrl)}`
          : undefined}
        target="_blank"
        class="btn"
        class:is-disabled={!editorAllmapsUrl}
      >
        Open in Allmaps Editor ↗
      </a>
    </div>
  </div>

  <!-- ── Image Upload ───────────────────────────────────────── -->
  <div class="hosting-subsection">
    <div class="subsection-heading">Image Upload (Internet Archive)</div>
    <label class="btn is-upload" class:is-disabled={uploading}>
      {uploading ? 'Uploading...' : 'Upload Image to IA'}
      <input
        type="file"
        accept="image/*"
        on:change={handleImageUpload}
        disabled={uploading}
        hidden
      />
    </label>
    {#if uploadStatus}
      <div class="upload-status">{uploadStatus}</div>
    {/if}
    {#if map.thumbnail}
      <div class="detail-row">
        <span class="detail-label">Thumbnail:</span>
        <span class="detail-value mono detail-value--xs">{map.thumbnail}</span>
      </div>
    {/if}
  </div>

  <!-- ── GCPs (only for self-hosted maps) ──────────────────── -->
  {#if isSelfHosted}
    <div class="hosting-subsection">
      <div class="subsection-heading">Ground Control Points</div>
      <p class="panel-note">Place GCPs to refine the georeferencing for this self-hosted map.</p>
      <NeatlineEditor
        mapId={map.id}
        annotationUrl={allmaps_id}
        on:saved={() => dispatch('notice', 'GCPs saved!')}
        on:error={(e) => dispatch('error', e.detail)}
      />
    </div>
  {/if}
</div>

<style>
  /* Placement only — the face is `.btn`. It was `.upload-btn` in
     admin-modals.css, a global name for two lines of local layout. */
  .is-upload {
    align-self: flex-start;
  }
</style>
