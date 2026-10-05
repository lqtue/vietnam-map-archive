/**
 * catalogTableModel.ts — which column holds what, and the grouping, for
 * CatalogTable (full) and ArchiveMapRows (the same table, four columns fewer).
 *
 * The sorting itself is `$lib/core/utils/tableSort.ts`, shared with every other
 * `.data-table`. This file carried its own copy until Sept 2026 — a `cmp`, a
 * `sortRows`, a `nextSort` and a `SortDir` of `'asc' | 'desc'` where the shared
 * one has a boolean. The behaviour was the same bar one thing worth keeping:
 * `numeric` collation, which is now what every table gets.
 */
import { statusOf } from '$lib/features/shared/catalogSearch';
import { applySort, type SortState } from '$lib/core/utils/tableSort';
import { STATE_LABEL, overallState, type WorkFactsById } from '$lib/core/sheetWork';

export type SortKey =
  | 'name'
  | 'year'
  | 'location'
  | 'region'
  | 'map_type'
  | 'collection'
  | 'holding_institution'
  | 'status';
export type GroupKey = 'none' | Exclude<SortKey, 'status'>;

/**
 * `work` is set for staff: sorting by Status then orders by the sheet's overall
 * work state (done / in progress / not yet). Without it Status is
 * Map/Image/Scout, as it is for every other reader.
 */
export type WorkContext = WorkFactsById | null;

export interface TableGroup<T> {
  label: string | null;
  rows: T[];
}

/** Display casing for the shared status rule; sort/group keys read this. */
const STATUS_LABEL = { scout: 'Scout', map: 'Map', image: 'Image' } as const;

export function keyOf(
  item: any,
  k: SortKey | GroupKey,
  work: WorkContext = null
): string | number | null {
  if (k === 'name') return item.name;
  if (k === 'year') return item.year;
  if (k === 'location') return item.location;
  if (k === 'region') return item.region;
  if (k === 'map_type') return item.map_type;
  if (k === 'collection') return item.collection;
  if (k === 'holding_institution') return item.holding_institution;
  if (k === 'status') {
    if (!work || statusOf(item) === 'scout') return STATUS_LABEL[statusOf(item)];
    return STATE_LABEL[overallState(work[item.id])];
  }
  return null;
}

export function sortRows<T>(items: T[], sort: SortState<SortKey>, work: WorkContext = null): T[] {
  return applySort(items, sort, (item, k) => keyOf(item, k, work));
}

export function groupRows<T>(
  sorted: T[],
  groupBy: GroupKey,
  work: WorkContext = null
): TableGroup<T>[] {
  if (groupBy === 'none') return [{ label: null, rows: sorted }];
  const m = new Map<string, T[]>();
  for (const r of sorted) {
    const v = keyOf(r, groupBy, work);
    const key = v == null || v === '' ? '—' : String(v);
    if (!m.has(key)) m.set(key, []);
    m.get(key)!.push(r);
  }
  return [...m.entries()].map(([label, rows]) => ({ label, rows }));
}
