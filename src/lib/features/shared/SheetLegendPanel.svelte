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
  import LegendEntryEditor, { type LegendDraft } from './LegendEntryEditor.svelte';

  /** Same zoom a label hit lands at — `LABEL_ZOOM` in explore/exploreUrl.ts,
   *  which this shared panel can't import (feature isolation). */
  const LABEL_ZOOM = 17;

  const dispatch = createEventDispatcher<{
    toggleLegendPoints: void;
    pickLocation: { lat: number; lng: number; label: string; zoom?: number };
    clearFocus: void;
  }>();

  export let mapId: string | null = null;
  export let showLegendPoints = false;
  export let mapActions = true;
  /** The row the reader last flew to — bound by the caller so Escape can clear it. */
  export let selectedN: number | null = null;

  type LegendPoint = {
    src?: 'manual' | 'grid' | 'numeral' | null;
    id?: string;
    n: number;
    name: string | null;
    vn: string | null;
    grid: string | null;
    lng: number | null;
    lat: number | null;
    accuracy_m?: number;
  };

  let drafts: Record<string, LegendDraft> = {};
  let savingDrafts = false;
  let saveMessage = '';
  let saveErrors: { id: string; message: string }[] = [];
  let legend: LegendPoint[] = [];
  function applyDraft(point: LegendPoint, draft: LegendDraft): LegendPoint {
    return {
      ...point,
      name: draft.name,
      vn: draft.vn,
      grid: draft.grid,
      lng: draft.coordinateOverride ? draft.lng : point.src === 'manual' ? null : draft.lng,
      lat: draft.coordinateOverride ? draft.lat : point.src === 'manual' ? null : draft.lat,
      src: draft.coordinateOverride ? 'manual' : point.src === 'manual' ? null : point.src,
    };
  }
  function keepDraft(draft: LegendDraft) {
    drafts = { ...drafts, [draft.id]: draft };
    editingId = null;
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
      const response = await fetch(`/api/admin/maps/${id}/legend-points`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entries: submitted.map((draft) => ({
            id: draft.id,
            name: draft.name,
            vn: draft.vn,
            grid: draft.grid,
            lng: draft.coordinateOverride ? draft.lng : null,
            lat: draft.coordinateOverride ? draft.lat : null,
          })),
        }),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(result.message ?? result.error ?? 'Could not save the legend drafts.');
      if (destroyed) return;
      const saved = new Set<string>(result.saved ?? submitted.map((draft) => draft.id));
      const submittedById = new Map(submitted.map((draft) => [draft.id, draft]));
      if (mapId === id) {
        legend = legend.map((point) =>
          point.id && saved.has(point.id) && submittedById.has(point.id)
            ? applyDraft(point, submittedById.get(point.id)!)
            : point
        );
        saveErrors = result.failed ?? [];
        saveMessage = saved.size
          ? `Saved ${saved.size} ${saved.size === 1 ? 'entry' : 'entries'}.`
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
  let editingId: string | null = null;
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
    editingId = null;
    saveMessage = '';
    saveErrors = [];
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

  function flyToLegend(p: LegendPoint) {
    if (p.lng == null || p.lat == null) return;
    // Tap the lit row again to put it out — the same gesture that lit it.
    if (selectedN === p.n) {
      selectedN = null;
      dispatch('clearFocus');
      return;
    }
    selectedN = p.n;
    // A legend number is a point on the sheet, so it lands at a label hit's
    // zoom rather than a Nominatim place's wider 15.
    dispatch('pickLocation', {
      lat: p.lat,
      lng: p.lng,
      label: p.name ?? `№${p.n}`,
      zoom: LABEL_ZOOM,
    });
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
    <button
      type="button"
      class="sb-btn is-sm is-block"
      disabled={savingDrafts || !!editingId}
      on:click={saveAll}
      >{savingDrafts ? 'Saving drafts…' : `Save all (${pendingDrafts.length})`}</button
    >
    {#if editingId}<p class="sb-empty">
        Keep or cancel the open edit before saving all drafts.
      </p>{/if}
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
  <ul class="lg-list">
    {#each legendRows as p (p.n)}
      <li>
        {#if mapActions && p.lng != null && p.lat != null}
          <button
            type="button"
            class="lg-row"
            class:is-on={selectedN === p.n}
            aria-current={selectedN === p.n ? 'true' : undefined}
            title={selectedN === p.n
              ? 'Clear this highlight'
              : p.accuracy_m
                ? `Within about ${p.accuracy_m} m`
                : 'Fly to this place'}
            on:click={() => flyToLegend(p)}
          >
            <span class="lg-n">{p.n}</span>
            <span class="lg-name">
              {p.name ?? '—'}{#if p.vn}<em> · {p.vn}</em>{/if}
            </span>
            {#if p.grid}<span class="lg-grid">{p.grid}</span>{/if}
          </button>
        {:else}
          <span class="lg-row"
            ><span class="lg-n">{p.n}</span><span class="lg-name"
              >{p.name ?? '—'}{#if p.vn}<em> · {p.vn}</em>{/if}</span
            >{#if p.grid}<span class="lg-grid">{p.grid}</span>{/if}</span
          >
        {/if}
        {#if canEdit && p.id && mapId}
          <button
            type="button"
            class="sb-btn is-sm"
            disabled={savingDrafts}
            on:click={() => (editingId = editingId === p.id ? null : (p.id ?? null))}
            >Edit text / point{drafts[p.id] ? ' · draft' : ''}</button
          >
          {#if drafts[p.id]}
            <span class="lg-draft-point"
              >{drafts[p.id].coordinateOverride
                ? `Draft manual point · ${drafts[p.id].lng}, ${drafts[p.id].lat}`
                : 'Draft automatic point'}</span
            >
          {/if}
          {#if editingId === p.id}
            {#key `${mapId}:${p.id}`}
              <LegendEntryEditor
                entry={{ ...p, id: p.id }}
                draft={drafts[p.id] ?? null}
                on:draft={(event) => keepDraft(event.detail)}
                on:close={() => (editingId = null)}
              />
            {/key}
          {/if}
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .lg-draft-point {
    display: block;
    font-size: 0.68rem;
    color: var(--sb-text-meta);
  }
  .lg-list {
    list-style: none;
    margin: 0.4rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  .lg-row {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    width: 100%;
    padding: 0.25rem 0.2rem;
    background: none;
    border: 0;
    border-top: var(--sb-border);
    text-align: left;
    font-size: 0.78rem;
    color: var(--sb-text);
    cursor: pointer;
  }
  .lg-row:hover {
    background: var(--sb-row-hover);
  }
  /* Same yellow as the map's pulse ring, so the row and the spot read as one. */
  .lg-row.is-on {
    background: var(--sb-accent-yellow);
  }
  .lg-n {
    flex: 0 0 1.4rem;
    font-family: var(--sb-font-display);
    font-weight: 800;
    font-size: 0.72rem;
    color: var(--sb-text-meta);
  }
  .lg-name {
    flex: 1;
    min-width: 0;
  }
  .lg-name em {
    font-style: normal;
    color: var(--sb-text-meta);
  }
  .lg-grid {
    flex: 0 0 auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.68rem;
    color: var(--sb-text-meta);
  }
</style>
