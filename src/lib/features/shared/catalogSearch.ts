/**
 * catalogSearch.ts — the single search/filter engine behind every catalog
 * surface in the app.
 *
 * `/api/search` does the heavy lifting (Postgres tsvector full-text search,
 * server-side role gating, the 2000-row safety ceiling). This module wraps it
 * in a Svelte store-factory so multiple UIs can share one implementation:
 *   - /archive            → CatalogUnifiedSearch.svelte (full facet rail)
 *   - /explore?mode=story, /scan     → CatalogSidebarPanel → CatalogUnifiedSearch (compact)
 *   - /explore map view   → ExploreBrowsePanel (compact, georef-only)
 *
 * Consumers bind `query`, read derived `results`/`facets`/`total`/`loading`,
 * and drive facet state via `toggleFacet` / `setSingle`. Call `start()` once
 * (in onMount) to kick the initial fetch and begin reacting to query changes.
 */
import { writable, derived, get, type Readable, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import { debounce } from '$lib/core/utils/debounce';

export interface PeriodDef {
  key: string;
  label: string;
  from?: number;
  to?: number;
}

/** Fallback until /api/search responds. Mirrors the server's PERIODS. */
const DEFAULT_PERIODS: PeriodDef[] = [
  { key: 'pre_colonial', label: 'Pre-colonial (≤1858)', from: 0, to: 1858 },
  { key: 'early_colonial', label: 'Early colonial (1859–1887)', from: 1859, to: 1887 },
  { key: 'indochina', label: 'French Indochina (1888–1939)', from: 1888, to: 1939 },
  { key: 'war_years', label: 'War years (1940–1954)', from: 1940, to: 1954 },
  { key: 'republic', label: 'Republic era (1955–1975)', from: 1955, to: 1975 },
  { key: 'reunification', label: 'Reunification+ (1976–)', from: 1976, to: 9999 },
];

/** Match /api/search's row cap; with no pagination UI we want the whole archive. */
const FETCH_LIMIT = 1000;
const DEBOUNCE_MS = 100;

type Row = Record<string, any>;
type Selected = Record<string, string[]>;

/** One OCR'd label matched inside a map — `/api/search?include=labels`. */
export interface LabelHit {
  id: string;
  map_id: string;
  map_name: string | null;
  year: number | null;
  text: string;
  category: string;
  bbox: [number, number, number, number];
  lng: number | null;
  lat: number | null;
}

export interface CatalogSearchController {
  /** Labels found *on* maps for the current query (empty when the query is blank). */
  labels: Readable<LabelHit[]>;
  query: Writable<string>;
  selected: Writable<Selected>;
  includeScout: Writable<boolean>;
  loading: Readable<boolean>;
  periods: Readable<PeriodDef[]>;
  rawMaps: Readable<Row[]>;
  rawScout: Readable<Row[]>;
  filteredMaps: Readable<Row[]>;
  filteredScout: Readable<Row[]>;
  results: Readable<Row[]>;
  facets: Readable<Record<string, Record<string, number>>>;
  total: Readable<{ maps: number; scout: number }>;
  /** Distinct areas/types present in the corpus, frequency-sorted (for dropdowns). */
  areaChoices: Readable<string[]>;
  typeChoices: Readable<string[]>;
  /** Periods that actually have a map, in chronological order (for dropdowns). */
  periodChoices: Readable<PeriodDef[]>;
  toggleFacet: (group: string, value: string) => void;
  clearGroup: (group: string) => void;
  /** Single-select helper for native <select> dropdowns. Empty value clears. */
  setSingle: (group: string, value: string) => void;
  /** Begin fetching + reacting to query/include changes. Call once in onMount. */
  start: () => void;
  /** Drop cached results and re-fetch (e.g. after an admin edit). */
  refresh: () => void;
}

// ── Pure helpers (shared by filtered* and facet derivations) ──────────────

export function statusOf(r: Row): 'scout' | 'map' | 'image' {
  if (r._table === 'scout') return 'scout';
  return r.georef_done ? 'map' : 'image';
}

function periodOfYear(year: number | null | undefined, defs: PeriodDef[]): string | null {
  if (year == null) return null;
  for (const p of defs) {
    const from = p.from ?? -Infinity;
    const to = p.to ?? Infinity;
    if (year >= from && year <= to) return p.key;
  }
  return null;
}

const passArea = (r: Row, sel: Selected) =>
  !sel.area?.length || sel.area.includes(String(r.location ?? ''));
const passType = (r: Row, sel: Selected) =>
  !sel.type?.length || sel.type.includes(String(r.map_type ?? ''));
const passStatus = (r: Row, sel: Selected) =>
  !sel.status?.length || sel.status.includes(statusOf(r));
const passPeriod = (r: Row, sel: Selected, defs: PeriodDef[]) => {
  if (!sel.period?.length) return true;
  const p = periodOfYear(r.year, defs);
  return p ? sel.period.includes(p) : false;
};
const passScoutCat = (r: Row, sel: Selected) =>
  !sel.category?.length || sel.category.includes(String(r._scout?.category ?? ''));

function tally(rows: Row[], key: string): Record<string, number> {
  const m: Record<string, number> = {};
  for (const r of rows) {
    const v = r?.[key];
    if (v == null || v === '') continue;
    m[String(v)] = (m[String(v)] ?? 0) + 1;
  }
  return m;
}

function distinct(rows: Row[], field: string, requireGeoref: boolean): string[] {
  const counts: Record<string, number> = {};
  for (const r of rows) {
    if (requireGeoref && !r.georef_done) continue;
    const v = r?.[field];
    if (v == null || v === '') continue;
    counts[String(v)] = (counts[String(v)] ?? 0) + 1;
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([name]) => name);
}

export interface CatalogSearchOptions {
  /** Restrict maps to georeferenced entries (the map view can only overlay those). */
  requireGeoref?: boolean;
}

export function createCatalogSearch(opts: CatalogSearchOptions = {}): CatalogSearchController {
  const requireGeoref = !!opts.requireGeoref;

  const query = writable('');
  const selected = writable<Selected>({});
  const includeScout = writable(false);
  const loading = writable(false);
  const rawMaps = writable<Row[]>([]);
  const rawScout = writable<Row[]>([]);
  const labels = writable<LabelHit[]>([]);
  const periods = writable<PeriodDef[]>(DEFAULT_PERIODS);

  const cache = new Map<
    string,
    { maps: Row[]; scout: Row[]; labels: LabelHit[]; periods: PeriodDef[] }
  >();
  let inflight: AbortController | null = null;
  let started = false;

  const cacheKey = (q: string, scout: boolean) => `${q.trim().toLowerCase()}|${scout ? 1 : 0}`;

  function buildQS(q: string, scout: boolean): string {
    const sp = new URLSearchParams();
    if (q.trim()) sp.set('q', q.trim());
    // Labels only mean something against a query; the server skips them otherwise.
    sp.set(
      'include',
      ['maps', ...(scout ? ['scout'] : []), ...(q.trim() ? ['labels'] : [])].join(',')
    );
    sp.set('limit', String(FETCH_LIMIT));
    return sp.toString();
  }

  async function doFetch() {
    const q = get(query);
    const scout = get(includeScout);
    const key = cacheKey(q, scout);
    const hit = cache.get(key);
    if (hit) {
      periods.set(hit.periods);
      rawMaps.set(hit.maps);
      rawScout.set(hit.scout);
      labels.set(hit.labels);
      loading.set(false);
      return;
    }
    if (inflight) inflight.abort();
    inflight = new AbortController();
    loading.set(true);
    try {
      const res = await fetch(`/api/search?${buildQS(q, scout)}`, { signal: inflight.signal });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      const entry = {
        maps: json.maps ?? [],
        scout: json.scout ?? [],
        labels: json.labels ?? [],
        periods: json.periods ?? DEFAULT_PERIODS,
      };
      cache.set(key, entry);
      periods.set(entry.periods);
      rawMaps.set(entry.maps);
      rawScout.set(entry.scout);
      labels.set(entry.labels);
    } catch (e: any) {
      if (e?.name !== 'AbortError') console.error('catalog search failed:', e);
    } finally {
      loading.set(false);
    }
  }

  const scheduleFetch = debounce(doFetch, DEBOUNCE_MS);

  function start() {
    if (started || !browser) return;
    started = true;
    // The immediate subscriber callback fires the initial fetch; subsequent
    // query/include changes re-trigger it (debounced + cached).
    query.subscribe(() => scheduleFetch());
    includeScout.subscribe(() => scheduleFetch());
  }

  /** Drop cached results and re-fetch — call after an edit changes the data. */
  function refresh() {
    cache.clear();
    doFetch();
  }

  const filteredMaps = derived([rawMaps, selected, periods], ([$maps, $sel, $periods]) =>
    $maps.filter(
      (r) =>
        passArea(r, $sel) &&
        passType(r, $sel) &&
        passPeriod(r, $sel, $periods) &&
        passStatus(r, $sel) &&
        (!requireGeoref || !!r.georef_done)
    )
  );

  const filteredScout = derived([rawScout, selected, periods], ([$scout, $sel, $periods]) =>
    $scout.filter(
      (r) =>
        passArea(r, $sel) &&
        passPeriod(r, $sel, $periods) &&
        passScoutCat(r, $sel) &&
        passStatus(r, $sel)
    )
  );

  // "All-but-this-dimension" facet tallies, so a chip shows the count you'd
  // get if you toggled it on.
  const facets = derived(
    [rawMaps, rawScout, selected, periods, includeScout],
    ([$maps, $scout, $sel, $periods, $scoutOn]) => {
      const mapsForArea = $maps.filter(
        (r) => passType(r, $sel) && passPeriod(r, $sel, $periods) && passStatus(r, $sel)
      );
      const mapsForType = $maps.filter(
        (r) => passArea(r, $sel) && passPeriod(r, $sel, $periods) && passStatus(r, $sel)
      );
      const mapsForStatus = $maps.filter(
        (r) => passArea(r, $sel) && passType(r, $sel) && passPeriod(r, $sel, $periods)
      );
      const mapsForPeriod = $maps.filter(
        (r) => passArea(r, $sel) && passType(r, $sel) && passStatus(r, $sel)
      );

      const periodCounts: Record<string, number> = {};
      for (const r of mapsForPeriod) {
        const p = periodOfYear(r.year, $periods);
        if (p) periodCounts[p] = (periodCounts[p] ?? 0) + 1;
      }
      const statusCounts: Record<string, number> = {};
      for (const r of mapsForStatus) {
        const s = statusOf(r);
        statusCounts[s] = (statusCounts[s] ?? 0) + 1;
      }
      const scoutForCat = $scout.filter((r) => passArea(r, $sel) && passPeriod(r, $sel, $periods));
      const scoutCatTally: Record<string, number> = {};
      for (const r of scoutForCat) {
        const c = r._scout?.category;
        if (c) scoutCatTally[c] = (scoutCatTally[c] ?? 0) + 1;
      }

      return {
        area: tally(mapsForArea, 'location'),
        map_type: tally(mapsForType, 'map_type'),
        period: periodCounts,
        status: statusCounts,
        scout_category: $scoutOn ? scoutCatTally : {},
      };
    }
  );

  const results = derived([filteredMaps, filteredScout], ([$m, $s]) => [...$m, ...$s]);
  const total = derived([filteredMaps, filteredScout], ([$m, $s]) => ({
    maps: $m.length,
    scout: $s.length,
  }));

  const areaChoices = derived(rawMaps, ($m) => distinct($m, 'location', requireGeoref));
  const typeChoices = derived(rawMaps, ($m) => distinct($m, 'map_type', requireGeoref));
  const periodChoices = derived([periods, rawMaps], ([$periods, $m]) => {
    const present = new Set(
      $m
        .filter((r) => !requireGeoref || r.georef_done)
        .map((r) => periodOfYear(r.year, $periods))
        .filter(Boolean)
    );
    return $periods.filter((p) => present.has(p.key));
  });

  function toggleFacet(group: string, value: string) {
    selected.update((s) => {
      const cur = new Set(s[group] ?? []);
      if (cur.has(value)) cur.delete(value);
      else cur.add(value);
      return { ...s, [group]: Array.from(cur) };
    });
  }
  function clearGroup(group: string) {
    selected.update((s) => ({ ...s, [group]: [] }));
  }
  function setSingle(group: string, value: string) {
    selected.update((s) => ({ ...s, [group]: value ? [value] : [] }));
  }

  return {
    query,
    selected,
    includeScout,
    loading,
    periods,
    rawMaps,
    rawScout,
    labels,
    filteredMaps,
    filteredScout,
    results,
    facets,
    total,
    areaChoices,
    typeChoices,
    periodChoices,
    toggleFacet,
    clearGroup,
    setSingle,
    start,
    refresh,
  };
}
