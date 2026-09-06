// Unified search across `maps` and (admin-only) `scout_candidates`.
// Powers the upgraded /archive search bar + facet rail.
//
// GET /api/search?q=<text>&institution=<csv>&type=<csv>&period=<csv>&georef=<bool>&source=<csv>&include=maps,scout,labels,places&limit=60&offset=0
//
// `include=places` searches the gazetteer (mig 067's `place_names` view), so a
// place name resolves to its own /archive/place/<slug> page. Added Sept 2026 with the
// command palette: the gazetteer is server-rendered for search engines, and
// until then the only link to it in the whole app sat on /archive/<id>.
//
// `include=labels` searches *inside* the maps: OCR'd labels via the
// `search_labels` RPC (mig 065, trigram word-similarity), each warped to lng/lat
// through the map's georeference so the client can jump straight to the spot.
//
// Facets are computed against the search-applied set (q + admin gate) but
// BEFORE the facet filters themselves are applied — so each chip shows how
// many results you'd get if you toggled it on.

import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { tally } from '$lib/server/facets';
import { getTransformer } from '$lib/server/transformer';
import { placeKey } from '$lib/core/utils/placeKey';

/**
 * Distinct maps whose annotation we will fetch to warp label hits that have no
 * stored position yet. Small on purpose: since migration 066 the position is a
 * column, so this is a fallback for rows written before the warp reached them,
 * and an anonymous endpoint must not fan out to twenty upstream fetches per
 * keystroke-group. Hits beyond the cap still list, without coordinates.
 */
const MAX_UNWARPED_MAPS = 4;
const LABEL_LIMIT = 60;
const PLACE_LIMIT = 20;

/** One gazetteer entry — `/api/search?include=places`. */
export interface PlaceHit {
  /** The gazetteer key; the URL slug is this with spaces turned into hyphens. */
  key: string;
  name: string;
  /** How many times the archive's maps name it. */
  mentions: number;
  first_year: number | null;
  last_year: number | null;
  lng: number | null;
  lat: number | null;
}

export interface LabelHit {
  id: string;
  map_id: string;
  map_name: string | null;
  year: number | null;
  text: string;
  category: string;
  /** Source-image pixel bbox [x, y, w, h]. */
  bbox: [number, number, number, number];
  /** Null when the map has no usable annotation. */
  lng: number | null;
  lat: number | null;
}

// No pagination UI on the catalog/sidebar yet, so the page slice must be able
// to hold the whole archive. Raw queries keep their own 2000-row safety ceiling.
const MAX_LIMIT = 1000;
const DEFAULT_LIMIT = 60;

const PERIODS: { key: string; label: string; from: number; to: number }[] = [
  { key: 'pre_colonial', label: 'Pre-colonial (≤1858)', from: 0, to: 1858 },
  { key: 'early_colonial', label: 'Early colonial (1859–1887)', from: 1859, to: 1887 },
  { key: 'indochina', label: 'French Indochina (1888–1939)', from: 1888, to: 1939 },
  { key: 'war_years', label: 'War years (1940–1954)', from: 1940, to: 1954 },
  { key: 'republic', label: 'Republic era (1955–1975)', from: 1955, to: 1975 },
  { key: 'reunification', label: 'Reunification+ (1976–)', from: 1976, to: 9999 },
];

function csvParam(v: string | null): string[] {
  return v
    ? v
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    : [];
}

function periodOf(year: number | null | undefined): string | null {
  if (year == null) return null;
  for (const p of PERIODS) if (year >= p.from && year <= p.to) return p.key;
  return null;
}

export const GET: RequestHandler = async ({ locals, url }) => {
  const role = await getRole(locals);
  const supabase = adminClient();

  const q = (url.searchParams.get('q') || '').trim();
  const institution = csvParam(url.searchParams.get('institution'));
  const type = csvParam(url.searchParams.get('type'));
  const period = csvParam(url.searchParams.get('period'));
  const source = csvParam(url.searchParams.get('source')); // source_type (ia, bnf, …)
  const scoutSource = csvParam(url.searchParams.get('scoutSource')); // scout.source (humazur, gallica, …)
  const category = csvParam(url.searchParams.get('category')); // scout category
  const georef = url.searchParams.get('georef'); // 'yes' | 'no' | null
  const includeReq = csvParam(url.searchParams.get('include'));
  // parseInt('abc') is NaN, and a NaN limit slices to an empty page with a 200 —
  // a bad param should fall back to the default, not look like an empty archive.
  const intParam = (name: string, fallback: number) => {
    const n = parseInt(url.searchParams.get(name) ?? '');
    return Number.isFinite(n) && n >= 0 ? n : fallback;
  };
  const limit = Math.min(intParam('limit', DEFAULT_LIMIT), MAX_LIMIT);
  const offset = intParam('offset', 0);
  // `fields=slim` is the command palette: it shows a title and a year for six
  // rows and has no facet rail to feed, so Postgres can apply the limit instead
  // of us fetching up to 2000 rows per keystroke-group to tally facets nobody
  // reads. (The column list stays whole — the PostgREST types parse that string
  // literally, and the row count was the expensive half.)
  const slim = url.searchParams.get('fields') === 'slim';

  const includeScout = (role === 'admin' || role === 'mod') && includeReq.includes('scout');
  const includeMaps = !includeReq.length || includeReq.includes('maps');
  const includeLabels = !!q && includeReq.includes('labels');
  const includePlaces = !!q && includeReq.includes('places');

  // ---------- MAPS ----------
  // We fetch a broad set (search applied; facet filters NOT applied) so we can tally facets,
  // then apply facet filters in JS for the page slice. Catalog ceiling is ~10k rows so this
  // stays cheap; if maps ever grows past that we'd push facets server-side.
  let mapsRows: Record<string, unknown>[] = [];
  if (includeMaps) {
    let qMaps = supabase
      .from('maps')
      .select(
        'id,name,location,map_type,dc_description,thumbnail,year,year_label,collection,source_type,status,bbox,extra_metadata,iiif_image,allmaps_id,annotation_url,georef_done,creator,holding_institution,original_title,dc_publisher,shelfmark,physical_description,rights,language,source_url'
      );
    if (role !== 'admin' && role !== 'mod') {
      // Public users only see public/featured.
      qMaps = qMaps.in('status', ['public', 'featured']);
    }
    if (q) qMaps = qMaps.textSearch('search_vector', q, { config: 'simple', type: 'plain' });
    // Slim callers get no facets, so there is nothing to tally the broad set
    // for — Postgres can do the cutting. Everyone else fetches broadly and
    // filters in JS, because a facet count needs the unfiltered set.
    qMaps = qMaps.limit(slim ? Math.min(limit + offset, MAX_LIMIT) : 2000);
    const { data, error: err } = await qMaps;
    if (err) dbError(err, 'Map search failed');
    mapsRows = (data as Record<string, unknown>[]) || [];
  }

  // ---------- SCOUT ----------
  let scoutRows: Record<string, unknown>[] = [];
  if (includeScout) {
    let qScout = supabase
      .from('scout_candidates')
      .select(
        'id,title,creator,publisher,date,year,holding_institution,collection,source,external_id,source_url,manifest_url,thumbnail,score,category,status,rights,language'
      )
      .neq('status', 'ingested'); // ingested rows already show up under maps
    if (q) qScout = qScout.textSearch('search_vector', q, { config: 'simple', type: 'plain' });
    qScout = qScout.limit(2000);
    const { data, error: err } = await qScout;
    if (err) dbError(err, 'Scout search failed');
    scoutRows = (data as Record<string, unknown>[]) || [];
  }

  // ---------- PLACES ----------
  // Match on `name_key` only, with the query folded through the *same* rule that
  // built it (`place_key`, migration 067 — unaccent, lowercase, punctuation to
  // single spaces). Two reasons this is not an `.or()` across the display name:
  //
  //   1. A raw `q` inside `.or()` is a parse hazard. PostgREST splits that
  //      string on commas, so "rue catinat, saigon" became three malformed
  //      conditions and 500'd the whole search — maps and labels with it.
  //   2. Folding is what makes places agree with labels. `search_labels`
  //      unaccents its query; matching the display name did not, so
  //      "Khanh-Hoi" found the label on the sheet but not its place page.
  //
  // `placeKey` strips every character PostgREST treats as syntax, so the
  // pattern needs no further escaping.
  const places: PlaceHit[] = [];
  const placeNeedle = includePlaces ? placeKey(q) : '';
  if (placeNeedle.length >= 2) {
    const { data, error: err } = await supabase
      .from('place_names')
      .select('name_key,name,mentions,first_year,last_year,lng,lat')
      .ilike('name_key', `%${placeNeedle}%`)
      .order('mentions', { ascending: false })
      .limit(PLACE_LIMIT);
    if (err) dbError(err, 'Place search failed');
    for (const r of data ?? []) {
      if (!r.name_key || !r.name) continue;
      places.push({
        key: r.name_key,
        name: r.name,
        mentions: r.mentions ?? 0,
        first_year: r.first_year,
        last_year: r.last_year,
        lng: r.lng,
        lat: r.lat,
      });
    }
  }

  // ---------- LABELS ----------
  // Fuzzy match on the OCR text, one row per (map, label). Draft maps are gated
  // in the RPC for public callers; staff see everything, like the maps block.
  const labels: LabelHit[] = [];
  if (includeLabels) {
    const { data: hits, error: err } = await supabase.rpc('search_labels', {
      p_q: q,
      p_public_only: role !== 'admin' && role !== 'mod',
      p_limit: LABEL_LIMIT,
    });
    if (err) dbError(err, 'Label search failed');

    const mapIds = [...new Set((hits ?? []).map((h) => h.map_id))];
    if (mapIds.length) {
      const { data: labelMaps } = await supabase
        .from('maps')
        .select('id, name, year, allmaps_id, annotation_url')
        .in('id', mapIds);
      const byId = new Map((labelMaps ?? []).map((m) => [m.id, m]));

      // The RPC returns the stored position where one exists. Only the maps
      // that returned none need their annotation fetched, and only a few of
      // those — the rest list without coordinates rather than costing a
      // request each.
      const unwarped = [
        ...new Set((hits ?? []).filter((h) => h.lng === null).map((h) => h.map_id)),
      ].slice(0, MAX_UNWARPED_MAPS);
      const transformers = new Map(
        await Promise.all(
          unwarped.map(async (id) => {
            const m = byId.get(id);
            return [id, m ? await getTransformer(m.allmaps_id, m.annotation_url) : null] as const;
          })
        )
      );

      for (const h of hits ?? []) {
        const m = byId.get(h.map_id);
        if (!m) continue;
        let lng = h.lng;
        let lat = h.lat;
        if (lng === null) {
          const t = transformers.get(h.map_id);
          if (t) {
            try {
              [lng, lat] = t.transformer.transformToGeo([h.x + h.w / 2, h.y + h.h / 2]);
            } catch {
              /* a GCP set that cannot warp this point: leave null, the hit still lists */
            }
          }
        }
        labels.push({
          id: h.id,
          map_id: h.map_id,
          map_name: m.name,
          year: m.year,
          text: h.label,
          category: h.category,
          bbox: [h.x, h.y, h.w, h.h],
          lng,
          lat,
        });
      }
    }
  }

  // ---------- FACETS (pre-filter) ----------
  // Each facet group tallies against everything-except-the-current-dimension so that
  // toggling a chip shows realistic post-toggle counts.
  const passInstitution = (r: Record<string, unknown>) =>
    !institution.length || institution.includes(String(r.holding_institution ?? ''));
  const passType = (r: Record<string, unknown>) =>
    !type.length || type.includes(String(r.map_type ?? ''));
  const passPeriod = (r: Record<string, unknown>) => {
    if (!period.length) return true;
    const p = periodOf(r.year as number | null);
    return p ? period.includes(p) : false;
  };
  const passSource = (r: Record<string, unknown>) =>
    !source.length || source.includes(String(r.source_type ?? ''));
  const passGeoref = (r: Record<string, unknown>) =>
    !georef || (georef === 'yes' ? !!r.allmaps_id : !r.allmaps_id);

  // For maps, build the "all but X" subsets.
  const mapsForInstitutionFacet = mapsRows.filter(
    (r) => passType(r) && passPeriod(r) && passSource(r) && passGeoref(r)
  );
  const mapsForTypeFacet = mapsRows.filter(
    (r) => passInstitution(r) && passPeriod(r) && passSource(r) && passGeoref(r)
  );
  const mapsForPeriodFacet = mapsRows.filter(
    (r) => passInstitution(r) && passType(r) && passSource(r) && passGeoref(r)
  );
  const mapsForSourceFacet = mapsRows.filter(
    (r) => passInstitution(r) && passType(r) && passPeriod(r) && passGeoref(r)
  );
  const mapsForGeorefFacet = mapsRows.filter(
    (r) => passInstitution(r) && passType(r) && passPeriod(r) && passSource(r)
  );

  // Period counts need bucketing.
  const periodCounts: Record<string, number> = {};
  for (const r of mapsForPeriodFacet) {
    const p = periodOf(r.year as number | null);
    if (p) periodCounts[p] = (periodCounts[p] ?? 0) + 1;
  }

  const georefCounts = {
    yes: mapsForGeorefFacet.filter((r) => !!r.allmaps_id).length,
    no: mapsForGeorefFacet.filter((r) => !r.allmaps_id).length,
  };

  // Scout facets (when scout included): scoutSource + category.
  const passScoutSource = (r: Record<string, unknown>) =>
    !scoutSource.length || scoutSource.includes(String(r.source ?? ''));
  const passCategory = (r: Record<string, unknown>) =>
    !category.length || category.includes(String(r.category ?? ''));
  const passScoutInstitution = (r: Record<string, unknown>) =>
    !institution.length || institution.includes(String(r.holding_institution ?? ''));
  const passScoutPeriod = (r: Record<string, unknown>) => {
    if (!period.length) return true;
    const p = periodOf(r.year as number | null);
    return p ? period.includes(p) : false;
  };

  const scoutForSourceFacet = scoutRows.filter(
    (r) => passCategory(r) && passScoutInstitution(r) && passScoutPeriod(r)
  );
  const scoutForCategoryFacet = scoutRows.filter(
    (r) => passScoutSource(r) && passScoutInstitution(r) && passScoutPeriod(r)
  );

  const facets = {
    institution: tally(mapsForInstitutionFacet, 'holding_institution'),
    map_type: tally(mapsForTypeFacet, 'map_type'),
    source_type: tally(mapsForSourceFacet, 'source_type'),
    period: periodCounts,
    georef: georefCounts,
    scout_source: includeScout ? tally(scoutForSourceFacet, 'source') : {},
    scout_category: includeScout ? tally(scoutForCategoryFacet, 'category') : {},
  };

  // ---------- APPLY FILTERS + PAGINATE ----------
  const filteredMaps = mapsRows.filter(
    (r) => passInstitution(r) && passType(r) && passPeriod(r) && passSource(r) && passGeoref(r)
  );
  const filteredScout = scoutRows.filter(
    (r) => passScoutSource(r) && passCategory(r) && passScoutInstitution(r) && passScoutPeriod(r)
  );

  // Stable ordering: when q is present, supabase preserves rank order; otherwise by year then name.
  if (!q) {
    filteredMaps.sort((a, b) => {
      const ay = (a.year as number) ?? 9999,
        by = (b.year as number) ?? 9999;
      return ay !== by ? ay - by : String(a.name ?? '').localeCompare(String(b.name ?? ''));
    });
    filteredScout.sort((a, b) => ((b.score as number) ?? 0) - ((a.score as number) ?? 0));
  }

  // Shape rows for the client. Use the MapListItem shape so the result card can render both.
  const mapsOut = filteredMaps.slice(offset, offset + limit).map((r) => ({
    id: r.id,
    name: r.name,
    location: r.location,
    map_type: r.map_type,
    dc_description: r.dc_description,
    thumbnail: r.thumbnail,
    isFeatured: r.status === 'featured',
    year: r.year,
    year_label: r.year_label,
    collection: r.collection,
    source_type: r.source_type,
    status: r.status,
    bbox: r.bbox,
    extra_metadata: r.extra_metadata,
    iiif_image: r.iiif_image,
    allmaps_id: r.allmaps_id,
    annotation_url: r.annotation_url,
    georef_done: r.georef_done,
    creator: r.creator,
    holding_institution: r.holding_institution,
    original_title: r.original_title,
    dc_publisher: r.dc_publisher,
    shelfmark: r.shelfmark,
    physical_description: r.physical_description,
    rights: r.rights,
    language: r.language,
    source_url: r.source_url,
    _table: 'maps' as const,
  }));

  const scoutOut = filteredScout.slice(0, limit).map((r) => ({
    id: `scout:${r.id}`,
    name: r.title,
    year: r.year,
    year_label: r.date,
    collection: r.collection,
    thumbnail: r.thumbnail,
    creator: r.creator,
    holding_institution: r.holding_institution,
    _table: 'scout' as const,
    _score: r.score,
    _scout: {
      id: r.id,
      source: r.source,
      category: r.category,
      score: r.score,
      status: r.status,
      source_url: r.source_url,
      manifest_url: r.manifest_url,
      publisher: r.publisher,
      year: r.year,
      date: r.date,
    },
  }));

  return json({
    maps: mapsOut,
    scout: scoutOut,
    labels,
    places,
    total: {
      maps: filteredMaps.length,
      scout: filteredScout.length,
      labels: labels.length,
      places: places.length,
    },
    limit,
    offset,
    facets,
    periods: PERIODS,
    role,
  });
};
