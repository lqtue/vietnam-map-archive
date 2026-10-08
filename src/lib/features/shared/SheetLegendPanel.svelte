<!--
  SheetLegendPanel.svelte — the Legend tab body shared by /explore's right
  rail and Studio: fetches a sheet's numbered-legend references and lists
  them, each a fly-to. Extracted from ExploreRightSidebar (Sept 2026) so a
  second right-side tab strip does not re-fetch or re-derive this itself.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { legendRevision, invalidateLegend } from '$lib/data/maps/legendRevision';
  import LegendTable from './LegendTable.svelte';
  import LegendEntryEditor from './LegendEntryEditor.svelte';
  import {
    accuracyBbox,
    applyDraft,
    forgetStoredDrafts,
    readStoredDrafts,
    saveDrafts,
    writeStoredDrafts,
    type Bbox,
    type LegendDraft,
    type LegendPoint,
  } from './legendDrafts';

  /** Same zoom a label hit lands at — `LABEL_ZOOM` in explore/exploreUrl.ts,
   *  which this shared panel can't import (feature isolation). */
  const LABEL_ZOOM = 17;

  const dispatch = createEventDispatcher<{
    toggleLegendPoints: void;
    pickLocation: { lat: number; lng: number; label: string; zoom?: number; bbox?: Bbox };
    clearFocus: void;
  }>();

  export let mapId: string | null = null;
  export let showLegendPoints = false;
  export let mapActions = true;
  /** The row the reader last selected — bound by the caller so Escape can clear it.
   *  For an editor it is also the open row. */
  export let selectedN: number | null = null;

  let drafts: Record<string, LegendDraft> = {};
  let savingDrafts = false;
  let saveMessage = '';
  let saveErrors: { id: string; message: string }[] = [];
  let legend: LegendPoint[] = [];
  function keepDraft(draft: LegendDraft) {
    drafts = { ...drafts, [draft.id]: draft };
    // The open editor is always this sheet's, so `legendFor` is the key's owner.
    if (mapId && mapId === legendFor) writeStoredDrafts(mapId, drafts);
    saveMessage = '';
    saveErrors = saveErrors.filter((error) => error.id !== draft.id);
  }
  async function saveAll() {
    if (!mapId || savingDrafts || !pendingDrafts.length) return;
    const id = mapId;
    const submitted = pendingDrafts;
    savingDrafts = true;
    saveMessage = '';
    saveErrors = [];
    try {
      const { saved, failed, warning } = await saveDrafts(id, submitted);
      // Whatever became of the panel meanwhile, those entries are no longer drafts.
      forgetStoredDrafts(id, saved);
      if (destroyed) return;
      const submittedById = new Map(submitted.map((draft) => [draft.id, draft]));
      if (mapId === id) {
        legend = legend.map((point) =>
          point.id && saved.has(point.id) && submittedById.has(point.id)
            ? applyDraft(point, submittedById.get(point.id)!)
            : point
        );
        saveErrors = failed;
        saveMessage = saved.size
          ? `Saved ${saved.size} ${saved.size === 1 ? 'entry' : 'entries'}.${warning ? ` ${warning}` : ''}`
          : '';
      }
      drafts = Object.fromEntries(
        Object.entries(drafts).filter(([entryId]) => !saved.has(entryId))
      );
      if (saved.size) {
        if (mapId === id) loadedRevision = (get(legendRevision)[id] ?? 0) + 1;
        invalidateLegend(id);
      }
    } catch (error) {
      if (!destroyed && mapId === id)
        saveMessage = error instanceof Error ? error.message : 'Could not save the legend drafts.';
    } finally {
      if (!destroyed) savingDrafts = false;
    }
  }

  let canEdit = false;
  let loadVersion = 0;
  let loadedRevision = -1;
  let destroyed = false;
  onDestroy(() => {
    destroyed = true;
    loadVersion += 1;
  });
  let legendFor = '';
  let legendLoading = false;
  let legendError = '';

  async function loadLegend(id: string, revision: number) {
    const version = ++loadVersion;
    selectedN = null;
    saveMessage = '';
    saveErrors = [];
    // Drafts belong to one sheet: never carry them over to the next.
    if (legendFor !== id) drafts = {};
    legendFor = id;
    loadedRevision = revision;
    legendLoading = true;
    legendError = '';
    try {
      const res = await fetch(`/api/maps/${id}/legend-points`);
      if (!res.ok) throw new Error('Could not load this sheet’s legend.');
      const data = await res.json();
      if (destroyed || version !== loadVersion || mapId !== id) return;
      canEdit = data?.canEdit === true;
      legend = (canEdit ? (data.entries ?? []) : (data?.points ?? [])) as LegendPoint[];
      // A reload or a closed tab leaves drafts in storage; an editor gets them back
      // (and they win over the server's row until saved). A reader never does.
      if (canEdit)
        drafts = {
          ...readStoredDrafts(
            id,
            legend.flatMap((point) => (point.id ? [point.id] : []))
          ),
          ...drafts,
        };
    } catch {
      if (!destroyed && version === loadVersion && mapId === id) {
        legend = [];
        canEdit = false;
        legendError = 'Could not load this sheet’s legend.';
      }
    } finally {
      if (!destroyed && version === loadVersion) legendLoading = false;
    }
  }

  $: currentRevision = mapId ? ($legendRevision[mapId] ?? 0) : 0;
  $: if (
    mapId &&
    (mapId !== legendFor ||
      (currentRevision !== loadedRevision && !savingDrafts && !pendingDrafts.length))
  )
    void loadLegend(mapId, currentRevision);
  $: pendingDrafts = legend
    .filter((point) => point.id && drafts[point.id])
    .map((point) => drafts[point.id!]);
  $: legendRows =
    mapId && mapId === legendFor
      ? legend.map((point) =>
          point.id && drafts[point.id] ? applyDraft(point, drafts[point.id]) : point
        )
      : [];

  $: editing = canEdit && !savingDrafts ? legendRows.find((p) => p.n === selectedN && p.id) : null;
  const placed = (p: LegendPoint) => p.lng != null && p.lat != null;

  function selectRow(p: LegendPoint) {
    // Tap the lit row again to put it out — the same gesture that lit it.
    if (selectedN === p.n) {
      selectedN = null;
      dispatch('clearFocus');
      return;
    }
    if (!canEdit && !placed(p)) return;
    selectedN = p.n;
    if (p.lng == null || p.lat == null) return;
    const label = p.name ?? `№${p.n}`;
    // A point read off the grid reference is the middle of a cell, so frame the
    // cell; a precise one is a point on the sheet and lands at a label hit's
    // zoom rather than a Nominatim place's wider 15.
    if (p.accuracy_m)
      dispatch('pickLocation', {
        lat: p.lat,
        lng: p.lng,
        label,
        bbox: accuracyBbox(p.lng, p.lat, p.accuracy_m),
      });
    else dispatch('pickLocation', { lat: p.lat, lng: p.lng, label, zoom: LABEL_ZOOM });
  }
</script>

{#if !mapId}
  <p class="sb-empty">{$t('Add a map layer to read its legend.')}</p>
{:else if legendLoading}
  <p class="sb-empty">{$t('Reading the legend…')}</p>
{:else if legendError}
  <p class="sb-empty" role="alert">{legendError}</p>
  <button
    type="button"
    class="sb-btn is-sm"
    on:click={() => mapId && loadLegend(mapId, currentRevision)}>Retry</button
  >
{:else if legendRows.length === 0}
  <p class="sb-empty">{$t('This sheet has no numbered legend.')}</p>
{:else}
  {#if canEdit && pendingDrafts.length}
    <button type="button" class="sb-btn is-sm is-block" disabled={savingDrafts} on:click={saveAll}
      >{savingDrafts ? 'Saving drafts…' : `Save all (${pendingDrafts.length})`}</button
    >
  {/if}
  {#if saveMessage}<p class="sb-empty" role="status">{saveMessage}</p>{/if}
  {#each saveErrors as failure (failure.id)}<p class="sb-empty" role="alert">
      №{legend.find((point) => point.id === failure.id)?.n ?? ''}: {failure.message}
    </p>{/each}
  {#if canEdit}
    <a class="sb-btn is-sm is-block" href={`/scan?mode=legend&map=${mapId}`}
      >{$t('Open legend tool')}</a
    >
  {/if}
  {#if mapActions}
    <button
      type="button"
      class="sb-btn is-sm is-block"
      class:is-on={showLegendPoints}
      on:click={() => dispatch('toggleLegendPoints')}
      title={$t('Show numbered legend references on the map')}
    >
      {showLegendPoints ? 'Legend points on' : 'Show legend points'}
    </button>
  {/if}
  <LegendTable
    rows={legendRows}
    {selectedN}
    actionable={(p) => canEdit || (mapActions && placed(p))}
    rowTitle={(p) =>
      selectedN === p.n
        ? canEdit
          ? 'Close this entry'
          : 'Clear this highlight'
        : canEdit
          ? 'Edit this entry'
          : mapActions && placed(p)
            ? p.accuracy_m
              ? `Within about ${p.accuracy_m} m`
              : 'Fly to this place'
            : undefined}
    on:select={(e) => {
      const point = legendRows.find((p) => p.n === e.detail.n);
      if (point) selectRow(point);
    }}
  >
    <svelte:fragment slot="extra" let:row={p}>
      {#if editing && editing.n === p.n && editing.id}
        {#key `${mapId}:${editing.id}`}
          <LegendEntryEditor
            entry={{ ...editing, id: editing.id }}
            draft={drafts[editing.id] ?? null}
            on:draft={(event) => keepDraft(event.detail)}
            on:locate={(event) =>
              dispatch('pickLocation', {
                ...event.detail,
                ...(!event.detail.bbox && { zoom: LABEL_ZOOM }),
              })}
          />
        {/key}
      {:else if p.id && drafts[p.id]}
        <span class="lg-draft-point">Unsaved draft</span>
      {/if}
    </svelte:fragment>
  </LegendTable>
{/if}

<style>
  .lg-draft-point {
    display: block;
    font-size: 0.68rem;
    color: var(--sb-text-meta);
  }
</style>
