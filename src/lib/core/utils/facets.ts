/**
 * facets.ts — filter, count and group any list of rows, described once.
 *
 * Maps, OCR labels and shapes are three lists a reader narrows the same way: a
 * search box, a few facets (status, category, series…), and a way of grouping
 * what is left. Each had its own `filterX` state, its own count rule and its
 * own idea of what "reset" means. A caller now declares its facets and gets all
 * three; `features/shared/FacetFilters.svelte` draws them.
 *
 * Three rules hold the shape together:
 *
 *  - **Choosing nothing is no constraint.** An empty selection passes every row,
 *    so "show pending and validated" is two chips on, and "show everything" is
 *    none on. A facet's *default* may still be a non-empty choice (a job's
 *    categories), which is why reset goes to `defaults`, not to empty.
 *  - **A facet's counts ignore itself.** The number on a chip is what choosing
 *    it would show given every *other* choice and the search — otherwise
 *    picking `pending` would turn `validated` to 0 and hide the very rows a
 *    reviewer turned it on to compare. `facetCounts` does it in one pass.
 *  - **Selection is plain data** (`Record<string, string[]>`): it reassigns
 *    cleanly in legacy Svelte and could be written to a URL or storage as is.
 */

export type Selection = Record<string, string[]>;

export type Facet<T> = {
  key: string;
  label: string;
  /** The row's one value on this facet. For `min`, a number as a string. */
  value: (row: T) => string;
  /** `many` toggle chips (any of) · `one` a select · `min` a floor slider. */
  kind: 'many' | 'one' | 'min';
  /** The values offered, in order. Default: those the rows hold, most first. */
  values?: string[];
  valueLabel?: (value: string) => string;
  /** A tint for a chosen chip. */
  color?: (value: string) => string | undefined;
  /** On the always-visible line rather than behind the Filters disclosure. */
  primary?: boolean;
  /** `min` only: the slider's range, and how its number reads. */
  min?: number;
  max?: number;
  step?: number;
  format?: (n: number) => string;
};

export type Search<T> = { query: string; text: (row: T) => string };

export type Choice = { value: string; label: string; count: number; color?: string };

const passes = <T>(row: T, f: Facet<T>, chosen: string[] | undefined): boolean => {
  if (!chosen?.length) return true;
  return f.kind === 'min'
    ? Number(f.value(row)) >= Number(chosen[0])
    : chosen.includes(f.value(row));
};

const hits = <T>(row: T, s?: Search<T>): boolean => {
  const q = s?.query.trim().toLowerCase();
  return !q || s!.text(row).toLowerCase().includes(q);
};

export function filterRows<T>(
  rows: T[],
  facets: Facet<T>[],
  selected: Selection,
  search?: Search<T>
): T[] {
  return rows.filter((r) => hits(r, search) && facets.every((f) => passes(r, f, selected[f.key])));
}

/**
 * Per facet, per value: how many rows choosing it would leave, given the
 * search and every other facet's choice. One pass: a row that fails nothing
 * counts everywhere; one that fails exactly one facet counts only in *that*
 * facet's tally (drop that choice and it returns); two or more, or a miss on
 * the search, count nowhere.
 */
export function facetCounts<T>(
  rows: T[],
  facets: Facet<T>[],
  selected: Selection,
  search?: Search<T>
): Record<string, Record<string, number>> {
  const out: Record<string, Record<string, number>> = {};
  for (const f of facets) out[f.key] = {};
  for (const r of rows) {
    if (!hits(r, search)) continue;
    const failed = facets.filter((f) => !passes(r, f, selected[f.key]));
    if (failed.length > 1) continue;
    for (const f of failed.length ? failed : facets) {
      if (f.kind === 'min') continue;
      const v = f.value(r);
      out[f.key][v] = (out[f.key][v] ?? 0) + 1;
    }
  }
  return out;
}

/**
 * What a facet offers as choices. `totals` overrides the tallied count when the
 * caller knows better (the server's whole-sheet status counts, when the rows
 * loaded are only the statuses already chosen). A value the facet names in
 * `values` is always offered; one it only found in the rows is left out when it
 * has nothing to show, unless it is chosen, so a chip never vanishes under the
 * finger that just pressed it. An empty value is no value (a flag that is
 * either `'suspect'` or `''` offers one chip, not two).
 */
export function facetChoices<T>(
  f: Facet<T>,
  tally: Record<string, number>,
  chosen: string[],
  totals?: Record<string, number>
): Choice[] {
  const count = (v: string) => totals?.[v] ?? tally[v] ?? 0;
  const held = Object.keys(totals ?? tally);
  const order = f.values ?? held.sort((a, b) => count(b) - count(a) || a.localeCompare(b));
  const values = [...order, ...chosen.filter((c) => !order.includes(c))];
  return values
    .filter((v) => v && (f.values?.includes(v) || count(v) > 0 || chosen.includes(v)))
    .map((v) => ({
      value: v,
      label: f.valueLabel?.(v) ?? v,
      count: count(v),
      color: f.color?.(v),
    }));
}

const same = (a: string[] = [], b: string[] = []) =>
  a.length === b.length && a.every((v) => b.includes(v));

/** True when a facet is where reset would put it. */
export const isDefault = <T>(f: Facet<T>, selected: Selection, defaults: Selection = {}) =>
  same(selected[f.key], defaults[f.key]);

/** Facets behind the disclosure whose choice differs from its default — the number on the summary. */
export function activeCount<T>(
  facets: Facet<T>[],
  selected: Selection,
  defaults: Selection = {}
): number {
  return facets.filter((f) => !f.primary && !isDefault(f, selected, defaults)).length;
}

export type Group<T> = { key: string; rows: T[] };

/**
 * Rows in groups, each group's rows in the order they came in. Groups run in
 * `order` when one is given (status reads pending → validated → rejected, not
 * whichever the sort met first), else by first appearance.
 */
export function groupRows<T>(rows: T[], keyOf: (row: T) => string, order?: string[]): Group<T>[] {
  const m = new Map<string, T[]>();
  for (const r of rows) {
    const k = keyOf(r) || '—';
    const list = m.get(k);
    if (list) list.push(r);
    else m.set(k, [r]);
  }
  const groups = [...m.entries()].map(([key, list]) => ({ key, rows: list }));
  if (!order) return groups;
  const at = (k: string) => (order.includes(k) ? order.indexOf(k) : order.length);
  return groups.sort((a, b) => at(a.key) - at(b.key));
}
