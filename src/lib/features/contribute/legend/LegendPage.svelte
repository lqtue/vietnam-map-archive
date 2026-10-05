<!--
  /scan?mode=legend — place a sheet's numbered legend on the scan, in pixels.
  URL: /scan?mode=legend&map=<uuid>   (staff: the API refuses anyone else)

  Left rail: which sheet and what is drawn. Right sidebar: the legend list.
  Stage: ImageShell + LegendTool. Select an entry, then click the scan to place
  it, or click a numeral pin to take that reading. Edits are staged in `staged`
  (a full row per entry) and go out in one batch PATCH; an entry the server
  refuses stays staged with its message.

  Keys (ignored while typing in a field):
    n       next unplaced entry        Enter   accept the best numeral for it
    click a pin selects it; drag moves it
    Esc     deselect                   Delete or Backspace (a Mac's delete key)  reset its position
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { t } from '$lib/core/i18n';
  import ToolLayout from '$lib/map/shell/ToolLayout.svelte';
  import ImageShell from '$lib/map/shell/ImageShell.svelte';
  import ScanLeftRail from '$lib/features/contribute/shared/ScanLeftRail.svelte';
  import ToolSidebarShell from '$lib/features/contribute/shared/ToolSidebarShell.svelte';
  import EmptyPanel from '$lib/features/contribute/shared/EmptyPanel.svelte';
  import LegendTool from './LegendTool.svelte';
  import LegendSidebar from './LegendSidebar.svelte';
  import {
    bestCandidate,
    mapStatus,
    nextUnplaced,
    type LegendCandidate,
    type LegendRow,
    type LegendStats,
    type MapStatus,
    type RowFilter,
    type RowSort,
  } from './legendStage';
  import '$styles/layouts/tool-page.css';
  import { INK } from '$lib/core/ink';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchMaps } from '$lib/data/maps/service';
  import { invalidateLegend } from '$lib/data/maps/legendRevision';
  import type { MapGrid } from '$lib/core/geo/mapGrid';
  import type { MapListItem } from '$lib/data/maps/types';
  import type { LabelMapInfo } from '$lib/data/supabase/footprints';

  const { supabase } = getSupabaseContext();

  $: statusChips = [
    { key: 'all', label: $t('All') },
    { key: 'todo', label: $t('To do') },
    { key: 'doing', label: $t('In progress') },
    { key: 'done', label: $t('Done') },
  ] as const;

  let maps: MapListItem[] = [];
  let currentMap: MapListItem | null = null;
  let iiifInfoUrl: string | null = null;
  let mapsError = '';

  let sidebarCollapsed = false;
  let rightSidebarCollapsed = false;
  let isMobile = false;
  let imageOpacity = 1;
  let show = { placed: true, candidates: true, grid: true };

  // ── The legend, as the server has it ───────────────────────────────────────
  let rows: LegendRow[] = [];
  let candidates: LegendCandidate[] = [];
  let grid: MapGrid | null = null;
  let rects: { x: number; y: number; w: number; h: number }[] = [];
  let loadError = '';
  let loadSeq = 0;

  // ── Work in progress ───────────────────────────────────────────────────────
  let staged: Record<string, LegendRow> = {};
  let failures: Record<string, string> = {};
  let selectedId: string | null = null;
  let filter: RowFilter = 'all';
  let sort: RowSort = 'n';
  let query = '';

  // ── Progress per sheet, for the picker ─────────────────────────────────────
  let stats: LegendStats = {};
  let statusFilter: MapStatus | 'all' = 'all';
  let saving = false;
  let message = '';

  $: view = rows.map((row) => staged[row.id] ?? row);
  $: selected = view.find((row) => row.id === selectedId) ?? null;
  $: stagedIds = new Set(Object.keys(staged));
  $: railLayers = [
    { id: 'placed', label: $t('Placed points'), on: show.placed, color: INK.blue },
    { id: 'candidates', label: $t('Numeral candidates'), on: show.candidates, color: INK.green },
    { id: 'grid', label: $t('Index grid'), on: show.grid, color: INK.purple },
  ];
  // The open sheet's own counts beat the loaded ones, so a save moves its badge.
  $: liveStats =
    currentMap && rows.length
      ? {
          ...stats,
          [currentMap.id]: { total: rows.length, placed: rows.filter((r) => r.x != null).length },
        }
      : stats;
  $: statusCounts = maps.reduce(
    (acc, m) => ({ ...acc, [mapStatus(liveStats[m.id])]: acc[mapStatus(liveStats[m.id])] + 1 }),
    { todo: 0, doing: 0, done: 0, none: 0 } as Record<MapStatus, number>
  );
  $: railMaps = maps
    .filter(
      (m) =>
        !!m.iiif_image && (statusFilter === 'all' || mapStatus(liveStats[m.id]) === statusFilter)
    )
    .map((m): LabelMapInfo => ({
      id: m.id,
      name: m.name,
      allmapsId: m.allmaps_id ?? '',
      iiifImage: m.iiif_image,
      legend: [],
      categories: [],
      triage: null,
      year: m.year,
      location: m.location,
      description: m.dc_description,
      badge: liveStats[m.id] ? `${liveStats[m.id].placed}/${liveStats[m.id].total}` : undefined,
    }));

  async function loadLegend(id: string) {
    const seq = ++loadSeq;
    rows = [];
    candidates = [];
    grid = null;
    rects = [];
    staged = {};
    failures = {};
    selectedId = null;
    message = '';
    loadError = '';
    try {
      const res = await fetch(`/api/admin/maps/${id}/legend-points`);
      if (seq !== loadSeq) return;
      if (!res.ok) throw new Error(res.status === 401 || res.status === 403 ? 'staff' : 'failed');
      const data = await res.json();
      if (seq !== loadSeq) return;
      rows = data.entries;
      candidates = data.candidates;
      grid = data.grid;
      rects = data.legendRects;
    } catch (err) {
      if (seq === loadSeq)
        loadError =
          err instanceof Error && err.message === 'staff'
            ? $t('The legend tool is for staff.')
            : $t('Could not load this sheet’s legend.');
    }
  }

  function selectMap(map: MapListItem) {
    if (currentMap?.id === map.id) return;
    currentMap = map;
    iiifInfoUrl = map.iiif_image ? map.iiif_image + '/info.json' : null;
    void loadLegend(map.id);
  }

  function stage(id: string, change: Partial<LegendRow>) {
    const base = staged[id] ?? rows.find((row) => row.id === id);
    if (!base) return;
    staged = { ...staged, [id]: { ...base, ...change } };
    const { [id]: _drop, ...rest } = failures;
    failures = rest;
    message = '';
  }

  function edit(id: string, field: 'name' | 'vn' | 'grid', value: string) {
    const text = value.trim();
    if (field === 'name') {
      if (text) stage(id, { name: text });
    } else stage(id, { [field]: text || null });
  }

  function select(id: string | null) {
    selectedId = id === selectedId ? null : id;
  }

  function place(x: number, y: number) {
    if (selected) stage(selected.id, { x, y });
  }

  function acceptCandidate(c: LegendCandidate) {
    const row = view.find((r) => r.n === c.n);
    if (!row) return;
    selectedId = row.id;
    stage(row.id, { x: c.x, y: c.y });
  }

  function onKey(e: KeyboardEvent) {
    const el = e.target as HTMLElement | null;
    if (el?.closest('input, textarea, select, [contenteditable]') || e.metaKey || e.ctrlKey) return;
    if (e.key === 'n') {
      const next = nextUnplaced(view, selectedId);
      if (next) selectedId = next.id;
    } else if (e.key === 'Enter' && selected) {
      const c = bestCandidate(candidates, selected.n);
      if (c) acceptCandidate(c);
    } else if (e.key === 'Escape') selectedId = null;
    else if ((e.key === 'Delete' || e.key === 'Backspace') && selected)
      stage(selected.id, { x: null, y: null });
    else return;
    e.preventDefault();
  }

  async function save() {
    if (!currentMap || saving || !stagedIds.size) return;
    const id = currentMap.id;
    const sent = Object.values(staged);
    saving = true;
    message = '';
    try {
      const res = await fetch(`/api/admin/maps/${id}/legend-points`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entries: sent.map((r) => ({
            id: r.id,
            name: r.name,
            vn: r.vn,
            grid: r.grid,
            x: r.x,
            y: r.y,
          })),
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.message ?? 'save');
      if (currentMap?.id !== id) return;
      const saved = new Set<string>(result.saved ?? []);
      const sentById = new Map(sent.map((row) => [row.id, row]));
      rows = rows.map((row) =>
        saved.has(row.id) ? { ...sentById.get(row.id)!, validated: true } : row
      );
      // An entry edited again while the save was in flight keeps its newer, unsent edit.
      staged = Object.fromEntries(
        Object.entries(staged).filter(([k, row]) => !saved.has(k) || row !== sentById.get(k))
      );
      failures = Object.fromEntries(
        (result.failed ?? []).map((f: { id: string; message: string }) => [f.id, f.message])
      );
      message = $t('Saved {N}.', { N: saved.size });
      if (saved.size) invalidateLegend(id);
    } catch {
      message = $t('Could not save the legend.');
    } finally {
      saving = false;
    }
  }

  async function loadStats() {
    try {
      const res = await fetch('/api/admin/maps/legend-stats');
      if (res.ok) stats = await res.json();
    } catch {
      // The picker still works without badges.
    }
  }

  onMount(async () => {
    void loadStats();
    try {
      maps = await fetchMaps(supabase, { includeArchived: true });
    } catch (err: any) {
      mapsError = err?.message ?? 'Failed to load maps';
    }
    const paramId = $page.url.searchParams.get('map');
    const match = paramId ? maps.find((m) => m.id === paramId) : null;
    if (match) selectMap(match);
  });
</script>

<svelte:window on:keydown={onKey} />

<svelte:head>
  <title>{currentMap ? `${currentMap.name} — ` : ''}{$t('Legend')} — Vietnam Map Archive</title>
</svelte:head>

<div class="tool-page">
  <ToolLayout
    bind:sidebarCollapsed
    bind:rightSidebarCollapsed
    bind:isMobile
    hasRightSidebar
    tabOrder={['browse', 'controls']}
  >
    <svelte:fragment slot="sidebar">
      <ScanLeftRail
        maps={railMaps}
        requireGeoref={false}
        layers={railLayers}
        selectedMapId={currentMap?.id ?? null}
        bind:imageOpacity
        onCollapse={() => (sidebarCollapsed = true)}
        on:select={(e) => selectMap(maps.find((m) => m.id === e.detail.map.id)!)}
        on:toggle={(e) => (show = { ...show, [e.detail.id]: e.detail.on })}
      >
        <div slot="picker-head" class="status-chips" role="group" aria-label={$t('Sheet status')}>
          {#each statusChips as chip (chip.key)}
            <button
              type="button"
              class="chip"
              class:is-on={statusFilter === chip.key}
              on:click={() => (statusFilter = chip.key)}
              >{chip.label}{chip.key === 'all' ? '' : ` ${statusCounts[chip.key]}`}</button
            >
          {/each}
        </div>
      </ScanLeftRail>
    </svelte:fragment>

    <svelte:fragment slot="right-sidebar">
      <ToolSidebarShell title={$t('Legend')} onCollapse={() => (rightSidebarCollapsed = true)}>
        {#if !currentMap}
          <EmptyPanel message={$t('Pick a map to place its legend.')} />
        {:else if loadError}
          <EmptyPanel message={loadError} />
        {:else if !rows.length}
          <EmptyPanel message={$t('This sheet has no numbered legend.')} />
        {:else}
          <LegendSidebar
            rows={view}
            {selectedId}
            bind:filter
            bind:sort
            bind:query
            staged={stagedIds}
            {failures}
            {saving}
            {message}
            on:select={(e) => select(e.detail.id)}
            on:edit={(e) => edit(e.detail.id, e.detail.field, e.detail.value)}
            on:reset={(e) => stage(e.detail.id, { x: null, y: null })}
            on:save={save}
          />
        {/if}
      </ToolSidebarShell>
    </svelte:fragment>

    {#if currentMap && iiifInfoUrl}
      <ImageShell {iiifInfoUrl} {imageOpacity}>
        <LegendTool
          placed={view}
          {candidates}
          {grid}
          {rects}
          selectedN={selected?.n ?? null}
          showPlaced={show.placed}
          showCandidates={show.candidates}
          showGrid={show.grid}
          on:place={(e) => place(e.detail.x, e.detail.y)}
          on:pick={(e) => {
            const row = view.find((r) => r.n === e.detail.n);
            if (row) selectedId = row.id;
          }}
          on:move={(e) => {
            const row = view.find((r) => r.n === e.detail.n);
            if (row) stage(row.id, { x: e.detail.x, y: e.detail.y });
          }}
          on:candidate={(e) => {
            const c = candidates.find((k) => k.labelId === e.detail.labelId);
            if (c) acceptCandidate(c);
          }}
        />
      </ImageShell>
    {:else}
      <div class="empty-stage">
        {#if mapsError}<p class="empty-state error">{mapsError}</p>{/if}
      </div>
    {/if}
  </ToolLayout>
</div>

<style>
  .status-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }
</style>
