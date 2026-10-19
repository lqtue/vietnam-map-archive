import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import { LIST_COLUMNS, toMapListItem, type DbRow } from '$lib/data/maps/service';
import type { MapListItem } from '$lib/data/maps/types';
import { queryError } from '$lib/data/supabase/queryError';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// PostgREST filter values are quoted, including names containing commas/parentheses.
const quoted = (value: string) => `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;

/** Resolve one reference, optionally moving one place through the archive's year order. */
export async function readExploreMap(
  db: SupabaseClient<Database>,
  ref: string,
  staff: boolean,
  direction: -1 | 0 | 1 = 0
): Promise<MapListItem | null> {
  function visible() {
    const query = db.from('maps').select(LIST_COLUMNS).neq('status', 'archived');
    return staff ? query : query.in('status', ['public', 'featured']);
  }
  const filters = [`slug.eq.${quoted(ref)}`, `allmaps_id.eq.${quoted(ref)}`];
  if (UUID.test(ref)) filters.push(`id.eq.${ref}`);
  const { data, error } = await visible().or(filters.join(',')).limit(1).maybeSingle();
  if (error) throw queryError('readExploreMap', error);
  if (!data) return null;
  const current = data as unknown as DbRow;
  if (!direction) return toMapListItem(current);
  if (!current.allmaps_id && !current.annotation_url) return null;

  const comparison = direction === 1 ? 'gt' : 'lt';
  const name = quoted(current.name);
  const afterName = `or(name.${comparison}.${name},and(name.eq.${name},id.${comparison}.${current.id}))`;
  let boundary: string;
  if (current.year == null) {
    boundary =
      direction === 1
        ? `and(year.is.null,${afterName})`
        : `year.not.is.null,and(year.is.null,${afterName})`;
  } else {
    boundary = `year.${comparison}.${current.year},and(year.eq.${current.year},${afterName})`;
    if (direction === 1) boundary += ',year.is.null';
  }
  const { data: next, error: nextError } = await visible()
    .or(
      'and(allmaps_id.not.is.null,allmaps_id.neq.""),and(annotation_url.not.is.null,annotation_url.neq."")'
    )
    .or(boundary)
    .order('year', { ascending: direction === 1, nullsFirst: direction === -1 })
    .order('name', { ascending: direction === 1 })
    .order('id', { ascending: direction === 1 })
    .limit(1)
    .maybeSingle();
  if (nextError) throw queryError('readExploreMap step', nextError);
  return next ? toMapListItem(next as unknown as DbRow) : null;
}
