/** Institution directory derived from published maps and the existing source-item catalogue. */
import type { SupabaseClient } from '@supabase/supabase-js';
import { readAll } from '$lib/data/supabase/paged';
import { queryError } from '$lib/data/supabase/queryError';
import { cartomundiSeries } from './cartomundi';
import usgsHoldings from './usgsHoldings.json';
import { KNOWN, PLATFORM, institutionFor, institutionSlug } from './institutionRegistry';

export interface InstitutionEntry {
  slug: string;
  name: string;
  short: string;
  maps: { id: string; slug: string | null; name: string; year: number | null }[];
  sourceItems: number;
  series: { key: string; name: string }[];
  cartomundiSeries: { id: string; title: string }[];
  /** Series held but not indexed here (the USGS snapshot's "Other holdings"). */
  otherSeries: number;
}

export async function fetchInstitutionCatalog(db: SupabaseClient) {
  const [maps, sources, series] = await Promise.all([
    readAll((from, to) =>
      db
        .from('maps')
        .select('id,slug,name,year,holding_institution,source_url')
        .in('status', ['public', 'featured'])
        .order('id')
        .range(from, to)
    ),
    readAll((from, to) =>
      db.from('cell_printings').select('id,institution,series_key').order('id').range(from, to)
    ),
    db.from('series').select('key,name'),
  ]);
  if (maps.error) throw queryError('Institution maps', maps.error);
  if (sources.error) throw queryError('Institution source items', sources.error);
  if (series.error) throw queryError('Institution surveys', series.error);
  const seriesNames = new Map((series.data ?? []).map((item) => [item.key, item.name]));
  const entries = new Map<string, InstitutionEntry>();
  function entry(value: string) {
    const { slug, name, short } = institutionFor(value);
    if (!entries.has(slug))
      entries.set(slug, {
        slug,
        name,
        short: short ?? name,
        maps: [],
        sourceItems: 0,
        series: [],
        cartomundiSeries: [],
        otherSeries: 0,
      });
    return entries.get(slug)!;
  }
  for (const map of maps.data) {
    if (map.holding_institution?.trim() && !PLATFORM.test(map.holding_institution))
      entry(map.holding_institution).maps.push({
        id: map.id,
        slug: map.slug,
        name: map.name,
        year: map.year,
      });
  }
  for (const source of sources.data) {
    if (!source.institution?.trim()) continue;
    const institution = entry(source.institution);
    institution.sourceItems++;
    if (
      source.series_key &&
      seriesNames.has(source.series_key) &&
      !institution.series.some((item) => item.key === source.series_key)
    ) {
      institution.series.push({
        key: source.series_key,
        name: seriesNames.get(source.series_key) ?? source.series_key,
      });
    }
  }
  for (const series of cartomundiSeries()) {
    for (const holder of new Set(
      series.holdingInstitution
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    )) {
      entry(holder).cartomundiSeries.push({ id: series.id, title: series.title });
    }
  }
  entry('USGS').otherSeries = new Set(
    usgsHoldings.items.map((item) => item.series).filter((name) => name !== 'Other sheets')
  ).size;
  for (const institution of entries.values()) {
    institution.maps.sort((a, b) => a.name.localeCompare(b.name));
    institution.series.sort((a, b) => a.name.localeCompare(b.name));
  }
  const platforms = new Map<string, { name: string; maps: InstitutionEntry['maps'] }>();
  platforms.set('CartoMundi', { name: 'CartoMundi', maps: [] });
  platforms.set('Nakala', { name: 'Nakala', maps: [] });
  for (const map of maps.data) {
    if (/^Cartomundi/i.test(map.holding_institution ?? '')) {
      platforms
        .get('CartoMundi')!
        .maps.push({ id: map.id, slug: map.slug, name: map.name, year: map.year });
    }
    if (!map.source_url) continue;
    let host: string;
    try {
      const url = new URL(map.source_url);
      if (!['https:', 'http:'].includes(url.protocol)) continue;
      host = url.hostname.replace(/^www\./, '');
    } catch {
      continue;
    }
    if (host.endsWith('maparchive.vn')) continue;
    const label =
      {
        'gallica.bnf.fr': 'Gallica',
        'loc.gov': 'Library of Congress digital collections',
        'archive.org': 'Internet Archive',
        'humazur.univ-cotedazur.fr': 'Humazur',
        'davidrumsey.com': 'David Rumsey Map Collection',
        'doi.org': /^https?:\/\/doi\.org\/10\.34847\/nkl\./i.test(map.source_url)
          ? 'Nakala'
          : 'DOI links (resolver)',
        'vi.wikipedia.org': 'Wikimedia',
      }[host] ?? host;
    if (!platforms.has(label)) platforms.set(label, { name: label, maps: [] });
    if (!platforms.get(label)!.maps.some((item) => item.id === map.id)) {
      platforms
        .get(label)!
        .maps.push({ id: map.id, slug: map.slug, name: map.name, year: map.year });
    }
  }
  return {
    institutions: [...entries.values()].sort((a, b) => a.name.localeCompare(b.name)),
    platforms: [...platforms.values()].sort((a, b) => a.name.localeCompare(b.name)),
  };
}

export interface InstitutionItem {
  id: string;
  sheet: string;
  title: string | null;
  year: number | null;
  edition: string | null;
  url: string | null;
  /** The archive serves this very item: one of its map images was made from it. */
  served: boolean;
  /** Published archive maps of the same sheet, whatever their source. */
  maps: { slug: string; name: string }[];
}

export interface InstitutionSeries {
  key: string;
  name: string;
  items: InstitutionItem[];
}

/** A holding outside the series VMA indexes; only USGS has a snapshot so far. */
export interface OutsideHolding {
  series: string;
  title: string;
  scale: string;
  date: string;
  url: string;
  productUrl: string;
  georeferenced: boolean;
}

/** One institution: its published maps, its catalogue items by series, and what else it holds. */
export async function fetchInstitution(db: SupabaseClient, slug: string) {
  const mapsResult = await readAll((from, to) =>
    db
      .from('maps')
      .select(
        'id,slug,name,year,holding_institution,series_key,sheet_number,map_images(source_item_id)'
      )
      .in('status', ['public', 'featured'])
      .order('id')
      .range(from, to)
  );
  if (mapsResult.error) throw queryError('Institution maps', mapsResult.error);
  const allMaps = mapsResult.data ?? [];
  const cartomundiHolders = cartomundiSeries().flatMap((series) =>
    series.holdingInstitution
      .split(',')
      .map((holder) => holder.trim())
      .filter(Boolean)
      .map((holder) => ({ holder, id: series.id, title: series.title }))
  );
  let institution = KNOWN.find((i) => i.slug === slug) ?? null;
  if (!institution) {
    const holder =
      allMaps.find(
        (m) =>
          m.holding_institution &&
          !PLATFORM.test(m.holding_institution) &&
          institutionSlug(m.holding_institution) === slug
      )?.holding_institution ??
      cartomundiHolders.find((c) => institutionFor(c.holder).slug === slug)?.holder;
    if (!holder) return null;
    institution = institutionFor(holder);
  }
  const ownSlug = institution.slug;
  const cartomundi = [
    ...new Map(
      cartomundiHolders
        .filter((c) => institutionFor(c.holder).slug === ownSlug)
        .map((c) => [c.id, { id: c.id, title: c.title }])
    ).values(),
  ];
  const names = new Set([institution.name, ...institution.aliases]);
  const maps = allMaps
    .filter((m) => m.holding_institution && names.has(m.holding_institution.trim()))
    .map((m) => ({ id: m.id, slug: m.slug, name: m.name, year: m.year }))
    .sort((a, b) => a.name.localeCompare(b.name));

  const series: InstitutionSeries[] = [];
  if (institution.code) {
    const code = institution.code;
    const [items, seriesRows] = await Promise.all([
      readAll((from, to) =>
        db
          .from('cell_printings')
          .select('id,series_key,sheet_number,title,year,edition,url')
          .eq('institution', code)
          .order('id')
          .range(from, to)
      ),
      db.from('series').select('key,name'),
    ]);
    if (items.error) throw queryError('Institution source items', items.error);
    if (seriesRows.error) throw queryError('Institution series', seriesRows.error);
    const servedItems = new Set(
      allMaps.flatMap((m) =>
        ((m.map_images ?? []) as { source_item_id: string | null }[]).map((i) => i.source_item_id)
      )
    );
    const mapsByCell = new Map<string, { slug: string; name: string }[]>();
    for (const m of allMaps) {
      if (!m.series_key || !m.sheet_number) continue;
      const key = `${m.series_key}|${m.sheet_number}`;
      if (!mapsByCell.has(key)) mapsByCell.set(key, []);
      mapsByCell.get(key)!.push({ slug: m.slug ?? m.id, name: m.name });
    }
    const seriesName = new Map((seriesRows.data ?? []).map((s) => [s.key, s.name]));
    const bySeries = new Map<string, InstitutionItem[]>();
    for (const r of items.data ?? []) {
      if (!bySeries.has(r.series_key)) bySeries.set(r.series_key, []);
      bySeries.get(r.series_key)!.push({
        id: r.id,
        sheet: r.sheet_number,
        title: r.title,
        year: r.year,
        edition: r.edition,
        url: r.url,
        served: servedItems.has(r.id),
        maps: mapsByCell.get(`${r.series_key}|${r.sheet_number}`) ?? [],
      });
    }
    for (const [key, list] of bySeries)
      series.push({
        key,
        name: seriesName.get(key) ?? key,
        items: list.sort((a, b) => a.sheet.localeCompare(b.sheet, undefined, { numeric: true })),
      });
    series.sort((a, b) => a.name.localeCompare(b.name));
  }

  const outside: OutsideHolding[] = institution.code === 'USGS' ? usgsHoldings.items : [];
  return {
    institution,
    maps,
    series,
    cartomundi,
    outside,
    outsideCheckedAt: usgsHoldings.checkedAt,
  };
}
