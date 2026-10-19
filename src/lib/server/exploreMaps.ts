import { CATALOG_REGIONS } from '$lib/core/catalogRegions';
import { canonicalMapType } from '$lib/core/mapTaxonomy';
import { foldForSearch } from '$lib/core/utils/unaccent';
import { MAP_BASE_COLUMNS } from '$lib/data/maps/columns';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const groups = ['area', 'region', 'type', 'institution', 'series_key', 'kind', 'status', 'year'];
export function exploreMapsParameters(params: URLSearchParams, staff: boolean) {
  const parse = (key: string, fallback: unknown) => {
    const value = params.get(key);
    return value === null ? fallback : JSON.parse(value);
  };
  const input = parse('filters', {});
  if (!input || typeof input !== 'object' || Array.isArray(input))
    throw new Error('Invalid filters');
  const filters: Record<string, string[]> = {};
  for (const key of groups) {
    const values = input[key];
    if (values === undefined) continue;
    if (
      !Array.isArray(values) ||
      values.length > 100 ||
      values.some((v) => typeof v !== 'string' || v.length > 200)
    )
      throw new Error('Invalid filters');
    filters[key] = values;
  }
  if (filters.type) filters.type = filters.type.map((v) => canonicalMapType(v) ?? '__invalid__');
  if (filters.year) {
    if (filters.year.length > 2 || filters.year.some((v) => v !== '' && !/^-?\d{1,6}$/.test(v)))
      throw new Error('Invalid year');
    if (filters.year.every((v) => v === '')) delete filters.year;
  }
  const cursor = parse('cursor', null);
  if (
    cursor !== null &&
    (typeof cursor !== 'object' ||
      Array.isArray(cursor) ||
      typeof cursor.id !== 'string' ||
      typeof cursor.name !== 'string' ||
      !UUID.test(cursor.id) ||
      cursor.name.length > 10000 ||
      (cursor.year !== null &&
        (!Number.isInteger(cursor.year) || cursor.year < -2147483648 || cursor.year > 2147483647)))
  )
    throw new Error('Invalid cursor');
  const point = parse('point', null);
  if (
    point !== null &&
    (!Array.isArray(point) ||
      point.length !== 2 ||
      !point.every(Number.isFinite) ||
      Math.abs(point[0]) > 180 ||
      Math.abs(point[1]) > 90)
  )
    throw new Error('Invalid point');
  const ids = parse('ids', null);
  if (
    ids !== null &&
    (!Array.isArray(ids) ||
      ids.length > 1000 ||
      ids.some((v) => typeof v !== 'string' || !UUID.test(v)))
  )
    throw new Error('Invalid ids');
  const q = (params.get('q') ?? '').trim().slice(0, 500);
  const tokens = foldForSearch(q)
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean)
    .map((t) => (/^\d{3}0s$/.test(t) ? t.slice(0, 3) : t));
  const limit = Number(params.get('limit') ?? 60);
  return {
    p_query: /^\d{4}-\d$/.test(q) ? q : tokens.map((t) => `${t}:*`).join(' & '),
    p_filters: filters,
    p_regions: Object.fromEntries(CATALOG_REGIONS.map((r) => [r.key, r.provinces])),
    p_staff: staff,
    p_limit: Number.isFinite(limit) ? Math.max(1, Math.min(100, Math.floor(limit))) : 60,
    p_cursor: cursor,
    p_point: point,
    p_ids: ids,
    p_sources: params.get('sources') === '1',
  };
}

const fields = [
  ...MAP_BASE_COLUMNS.split(','),
  'series_id',
  'printing_id',
  'creator',
  'sheet_number',
  'sheet_half',
  'original_title',
  'shelfmark',
  'language',
];
export function shapeExploreMaps(payload: any) {
  return {
    ...payload,
    maps: (payload.maps ?? []).map((row: Record<string, unknown>) => ({
      ...Object.fromEntries(fields.map((key) => [key, row[key]])),
      year_label: row.date_label,
      georef_done: row.is_georeferenced,
      dc_publisher: row.publisher,
      isFeatured: row.status === 'featured',
      _table: 'maps',
    })),
    nextCursor: payload.nextCursor ? JSON.stringify(payload.nextCursor) : null,
  };
}
