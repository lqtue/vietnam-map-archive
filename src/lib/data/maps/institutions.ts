/** Institution directory derived from published maps and the existing source-item catalogue. */
import type { SupabaseClient } from '@supabase/supabase-js';
import { readAll } from '$lib/data/supabase/paged';
import { queryError } from '$lib/data/supabase/queryError';
import { cartomundiSeries } from './cartomundi';

const names: Record<string, string> = {
  PCL: 'Perry-Castañeda Library Map Collection, University of Texas at Austin',
  TTU: 'Texas Tech',
  ANU: 'ANU',
  IGN: "IGN (Institut national de l'information géographique et forestière)",
};

export interface InstitutionEntry {
  name: string;
  maps: { id: string; slug: string | null; name: string; year: number | null }[];
  sourceItems: number;
  series: { key: string; name: string }[];
  cartomundiSeries: { id: string; title: string }[];
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
    db.from('map_series').select('key,name,published_sheets').gt('published_sheets', 0),
  ]);
  if (maps.error) throw queryError('Institution maps', maps.error);
  if (sources.error) throw queryError('Institution source items', sources.error);
  if (series.error) throw queryError('Institution surveys', series.error);
  const seriesNames = new Map((series.data ?? []).map((item) => [item.key, item.name]));
  const entries = new Map<string, InstitutionEntry>();
  function entry(value: string) {
    const name = names[value.trim()] ?? value.trim();
    if (!entries.has(name))
      entries.set(name, {
        name,
        maps: [],
        sourceItems: 0,
        series: [],
        cartomundiSeries: [],
      });
    return entries.get(name)!;
  }
  for (const map of maps.data) {
    if (
      map.holding_institution?.trim() &&
      !/^(Cartomundi|Wikimedia Commons)/i.test(map.holding_institution)
    )
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
