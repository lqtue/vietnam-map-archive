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
  } from './legendStage';
  import '$styles/layouts/tool-page.css';
  import { INK } from '$lib/core/ink';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchMaps } from '$lib/data/maps/service';
  import { invalidateLegend } from '$lib/data/maps/legendRevision';
  import type { MapGrid } from '$lib/core/geo/mapGrid';
  import type { MapListItem } from '$lib/data/maps/types';
  import { NO_WORK, legendReadiness, readSummary, type WorkFactsById } from '$lib/core/sheetWork';
  import { fetchSheetWork } from '$lib/data/admin/sheetWork';
  import type { LabelMapInfo } from '$lib/data/supabase/footprints';

  const { supabase } = getSupabaseContext();

  $: statusOptions = [
    { key: 'all', label: $t('All sheets') },
    { key: 'todo', label: `${$t('To do')} · ${statusCounts.todo}` },
    { key: 'doing', label: `${$t('In progress')} · ${statusCounts.doing}` },
    { key: 'done', label: `${$t('Done')} · ${statusCounts.done}` },
    { key: 'ready', label: `${$t('Legend found, not read')} · ${readyCount}` },
    { key: 'unlocated', label: `${$t('No legend located')} · ${unlocatedCount}` },
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
  let query = '';

  // ── Progress per sheet, for the picker ─────────────────────────────────────
  let stats: LegendStats = {};
  let work: WorkFactsById = {};
  let statusFilter: MapStatus | 'ready' | 'unlocated' | 'all' = 'all';
  let saving = false;
  let message = '';
  /** "Add another point" is armed: the next click on the scan adds a point to the open entry. */
  let addingMore = false;

  $: view = rows.map((row) => staged[row.id] ?? row);
  // A detected numeral that could name an unplaced entry, and the subset that
  // also sits in the entry's index cell — safe to take in one go.
  $: suggestions = new Map(
    view.flatMap((row) => {
      const c = row.x == null ? bestCandidate(candidates, row.n) : null;
      return c ? [[row.n, c] as const] : [];
    })
  );
  // A number printed twice on the sheet is a choice for a person, not for a bulk
  // accept: only an entry with exactly one candidate that could be it is taken.
  $: matching = [...suggestions.values()].filter(
    (c) =>
      c.inCell === true && candidates.filter((k) => k.n === c.n && k.inCell !== false).length === 1
  );
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
  // A sheet whose legend has no entries yet: is there a region to read, or not even that.
  $: unread = maps.filter((m) => !liveStats[m.id]?.total);
  $: readyCount = unread.filter((m) => legendReadiness(work[m.id]) === 'ready').length;
  $: unlocatedCount = unread.filter((m) => legendReadiness(work[m.id]) === 'unlocated').length;
  $: railMaps = maps
    .filter(
      (m) =>
        !!m.iiif_image &&
        (statusFilter === 'all' ||
          (statusFilter === 'ready' || statusFilter === 'unlocated'
            ? !liveStats[m.id]?.total && legendReadiness(work[m.id]) === statusFilter
            : mapStatus(liveStats[m.id]) === statusFilter))
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
      badge: liveStats[m.id]
        ? `${liveStats[m.id].placed}/${liveStats[m.id].total}`
        : readSummary(work[m.id]),
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
    addingMore = false;
  }

  /** A position for an entry: its first, or — Shift held, or "Add another point" armed —
   *  one more, for a number printed on several plots. */
  function put(row: LegendRow, x: number, y: number, extra: boolean) {
    if ((extra || addingMore) && row.x != null) stage(row.id, { more: [...row.more, [x, y]] });
    else stage(row.id, { x, y });
    addingMore = false;
  }

  function place(x: number, y: number, extra: boolean) {
    if (selected) put(selected, x, y, extra);
  }

  function acceptCandidate(c: LegendCandidate, extra = false) {
    const row = view.find((r) => r.n === c.n);
    if (!row) return;
    selectedId = row.id;
    put(row, c.x, c.y, extra);
  }

  function movePoint(n: number, index: number, x: number, y: number) {
    const row = view.find((r) => r.n === n);
    if (!row) return;
    if (index < 0) stage(row.id, { x, y });
    else
      stage(row.id, {
        more: row.more.map((p, i) => (i === index ? ([x, y] as [number, number]) : p)),
      });
  }

  function removeMore(id: string, index: number) {
    const row = view.find((r) => r.id === id);
    if (row) stage(id, { more: row.more.filter((_, i) => i !== index) });
  }

  function acceptMatching() {
    for (const c of matching) {
      const row = view.find((r) => r.n === c.n);
      if (row) stage(row.id, { x: c.x, y: c.y });
    }
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
    } else if (e.key === 'Escape') {
      if (addingMore) addingMore = false;
      else selectedId = null;
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && selected)
      stage(selected.id, { x: null, y: null, more: [] });
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
            more: r.more,
          })),
        }),
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(result.message ?? `HTTP ${res.status}`);
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
    } catch (err) {
      // The server's reason, so a failed save says why (MFA, a bad entry, a 500).
      message = `${$t('Could not save the legend.')} ${err instanceof Error ? err.message : ''}`;
    } finally {
      saving = false;
    }
  }

  $: noLegend = !!(currentMap && work[currentMap.id]?.noLegend);

  /** "This sheet prints no legend" — one merged key in `maps.triage`, so regions are untouched. */
  async function setNoLegend(on: boolean) {
    if (!currentMap || saving) return;
    const id = currentMap.id;
    saving = true;
    message = '';
    try {
      const res = await fetch(`/api/admin/maps/${id}/triage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ legend: on ? 'none' : null }),
      });
      if (!res.ok) throw new Error('save');
      work = { ...work, [id]: { ...(work[id] ?? NO_WORK), noLegend: on } };
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

  async function loadWork() {
    work = (await fetchSheetWork()) ?? {};
  }

  onMount(async () => {
    void loadStats();
    void loadWork();
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
        extraActive={statusFilter === 'all' ? 0 : 1}
        bind:imageOpacity
        onCollapse={() => (sidebarCollapsed = true)}
        on:select={(e) => selectMap(maps.find((m) => m.id === e.detail.map.id)!)}
        on:toggle={(e) => (show = { ...show, [e.detail.id]: e.detail.on })}
      >
        <select slot="filters" bind:value={statusFilter} aria-label={$t('Sheet status')}>
          {#each statusOptions as option (option.key)}
            <option value={option.key}>{option.label}</option>
          {/each}
        </select>
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
          <div class="no-legend">
            <label>
              <input
                type="checkbox"
                checked={noLegend}
                disabled={saving}
                on:change={(e) => setNoLegend(e.currentTarget.checked)}
              />
              {$t('No legend on this sheet')}
            </label>
            {#if message}<p role="alert">{message}</p>{/if}
          </div>
        {:else}
          <LegendSidebar
            rows={view}
            {selectedId}
            bind:filter
            bind:query
            suggested={new Set(suggestions.keys())}
            matching={matching.length}
            staged={stagedIds}
            {failures}
            {saving}
            {message}
            on:select={(e) => select(e.detail.id)}
            on:edit={(e) => edit(e.detail.id, e.detail.field, e.detail.value)}
            on:reset={(e) => stage(e.detail.id, { x: null, y: null, more: [] })}
            {addingMore}
            on:addMore={() => (addingMore = !addingMore)}
            on:removeMore={(e) => removeMore(e.detail.id, e.detail.index)}
            on:accept={(e) => {
              const row = view.find((r) => r.id === e.detail.id);
              const c = row && suggestions.get(row.n);
              if (c) acceptCandidate(c);
            }}
            on:acceptMatching={acceptMatching}
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
          on:place={(e) => place(e.detail.x, e.detail.y, e.detail.extra)}
          on:pick={(e) => {
            const row = view.find((r) => r.n === e.detail.n);
            if (row) selectedId = row.id;
          }}
          on:move={(e) => {
            movePoint(e.detail.n, e.detail.index, e.detail.x, e.detail.y);
          }}
          on:candidate={(e) => {
            const c = candidates.find((k) => k.labelId === e.detail.labelId);
            if (c) acceptCandidate(c, e.detail.extra);
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
  .no-legend {
    padding: 0 0.75rem;
    font-size: 0.8rem;
  }
  .no-legend p {
    margin: 0.3rem 0 0;
    color: var(--sb-text-meta);
  }
</style>
