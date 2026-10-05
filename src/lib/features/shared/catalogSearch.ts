/**
 * catalogSearch.ts — the single search/filter engine behind every catalog
 * surface in the app.
 *
 * `/api/search` does the heavy lifting (Postgres tsvector full-text search,
 * server-side role gating, the 5000-row ceiling). This module wraps it
 * in a Svelte store-factory so multiple UIs can share one implementation:
 *   - /catalog            → CatalogUnifiedSearch.svelte (full facet rail)
 *   - /explore?mode=story, /scan → CatalogSidebarPanel → CatalogUnifiedSearch (compact)
 *   - /explore map view   → ExploreBrowsePanel (compact, georef-only)
 *
 * Consumers bind `query`, read derived `results`/`facets`/`total`/`loading`,
 * and drive facet state via `toggleFacet` / `setSingle`. Call `start()` once
 * (in onMount) to kick the initial fetch and begin reacting to query changes.
 */
import { writable, derived, get, type Readable, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import { debounce } from '$lib/core/utils/debounce';
import { matchesSeriesFacet } from '$lib/data/maps/seriesFacet';
import {
  decadeBins,
  isSurvey,
  passArea,
  passInstitution,
  passKind,
  passType,
  passYear,
  type Row,
  type Selected,
} from './catalogFilters';

/** Match /api/search's row cap; with no pagination UI we want the whole archive. */
const FETCH_LIMIT = 5000;
const DEBOUNCE_MS = 100;

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
  /** Further sheets carrying the same name, collapsed into this row by /api/search. */
  other_sheets: number;
}

export interface CatalogSearchController {
  /** Labels found *on* maps for the current query (empty when the query is blank). */
  labels: Readable<LabelHit[]>;
  query: Writable<string>;
  selected: Writable<Selected>;
  includeScout: Writable<boolean>;
  loading: Readable<boolean>;
  rawMaps: Readable<Row[]>;
  rawScout: Readable<Row[]>;
  filteredMaps: Readable<Row[]>;
  filteredScout: Readable<Row[]>;
  results: Readable<Row[]>;
  facets: Readable<Record<string, Record<string, number>>>;
  /**
   * `maps` is the number of map rows on screen, drafts included — it has to
   * match the list under it. `drafts` says how many of those are unpublished,
   * which is zero for a reader (the API only returns published rows to one)
   * and non-zero for staff. Without it the toolbar called 153 rows "in
   * archive" while /about said 103, and both were right.
   */
  total: Readable<{ maps: number; drafts: number; scout: number }>;
  /** Distinct areas/types present in the corpus, frequency-sorted (for dropdowns). */
  areaChoices: Readable<string[]>;
  typeChoices: Readable<string[]>;
  institutionChoices: Readable<string[]>;
  /** Rows per decade, counted against every other facet — the histogram under the year range. */
  yearBins: Readable<{ decade: number; count: number }[]>;
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

const passStatus = (r: Row, sel: Selected) =>
  !sel.status?.length || sel.status.includes(statusOf(r));
/**
 * The series dimension matches the durable `series_key`; collection is mutable
 * descriptive text and remains a separate display field. Choices come from
 * `map_series`, and the caller passes
 * the list down. A filter that derived "is this collection a survey?" on the
 * client would be the view's rule spelled a second time, in a place nothing
 * would notice going stale.
 *
 * Note what it does not narrow to: `map_series` counts only georeferenced,
 * numbered sheets, but this matches every row in the collection. That is
 * deliberate — a survey's image-only sheets are still sheets of the survey,
 * and a reader who picks L7014 wants what the archive holds of it, not what
 * the map can draw. (/explore's copy of the engine drops them anyway, via
 * `requireGeoref`, because it can only overlay what is warped.)
 */
const passSeries = (r: Row, sel: Selected) => matchesSeriesFacet(r, sel.series_key ?? []);
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

  const cache = new Map<string, { maps: Row[]; scout: Row[]; labels: LabelHit[] }>();
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
      };
      cache.set(key, entry);
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

  // Every dimension, so a tally can skip its own: `passExcept(sel, 'area')` is "everything but area".
  const mapTests: Record<string, (r: Row, sel: Selected) => boolean> = {
    area: passArea,
    type: passType,
    series_key: passSeries,
    year: passYear,
    institution: passInstitution,
    kind: passKind,
    status: passStatus,
  };
  const passExcept = (sel: Selected, skip?: string) => (r: Row) =>
    Object.entries(mapTests).every(([k, test]) => k === skip || test(r, sel));

  const filteredMaps = derived([rawMaps, selected], ([$maps, $sel]) =>
    $maps.filter((r) => passExcept($sel)(r) && (!requireGeoref || !!r.georef_done))
  );

  const filteredScout = derived([rawScout, selected], ([$scout, $sel]) =>
    $scout.filter(
      (r) => passArea(r, $sel) && passYear(r, $sel) && passScoutCat(r, $sel) && passStatus(r, $sel)
    )
  );

  // "All-but-this-dimension" facet tallies, so a chip shows the count you'd
  // get if you toggled it on.
  const facets = derived(
    [rawMaps, rawScout, selected, includeScout],
    ([$maps, $scout, $sel, $scoutOn]) => {
      const but = (skip: string) => $maps.filter(passExcept($sel, skip));
      const statusCounts: Record<string, number> = {};
      for (const r of but('status')) {
        const st = statusOf(r);
        statusCounts[st] = (statusCounts[st] ?? 0) + 1;
      }
      const kindRows = but('kind');
      const scoutCatTally: Record<string, number> = {};
      for (const r of $scout.filter((r) => passArea(r, $sel) && passYear(r, $sel))) {
        const c = r._scout?.category;
        if (c) scoutCatTally[c] = (scoutCatTally[c] ?? 0) + 1;
      }

      return {
        area: tally(but('area'), 'location'),
        map_type: tally(but('type'), 'map_type'),
        series_key: tally(but('series_key'), 'series_key'),
        institution: tally(but('institution'), 'holding_institution'),
        kind: {
          surveys: kindRows.filter(isSurvey).length,
          plans: kindRows.filter((r) => !isSurvey(r)).length,
        },
        status: statusCounts,
        scout_category: $scoutOn ? scoutCatTally : {},
      };
    }
  );

  const results = derived([filteredMaps, filteredScout], ([$m, $s]) => [...$m, ...$s]);
  const total = derived([filteredMaps, filteredScout], ([$m, $s]) => ({
    maps: $m.length,
    drafts: $m.filter((r) => r.status === 'draft').length,
    scout: $s.length,
  }));

  const areaChoices = derived(rawMaps, ($m) => distinct($m, 'location', requireGeoref));
  const typeChoices = derived(rawMaps, ($m) => distinct($m, 'map_type', requireGeoref));
  const institutionChoices = derived(rawMaps, ($m) =>
    distinct($m, 'holding_institution', requireGeoref)
  );
  const yearBins = derived([rawMaps, selected], ([$maps, $sel]) =>
    decadeBins(
      $maps.filter((r) => passExcept($sel, 'year')(r) && (!requireGeoref || !!r.georef_done))
    )
  );

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
    institutionChoices,
    yearBins,
    toggleFacet,
    clearGroup,
    setSingle,
    start,
    refresh,
  };
}
