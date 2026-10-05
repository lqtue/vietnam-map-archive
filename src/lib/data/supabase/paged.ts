/**
 * Every row of a query, a page at a time. One PostgREST response stops at `max_rows`
 * (supabase/config.toml: 1000) with no error, so a list that grows past it comes back
 * short and looks complete. The query must have a total order (end it with `.order('id')`),
 * or pages overlap and rows repeat or go missing.
 */
const PAGE = 1000;

export async function readAll<T>(
  page: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: unknown }>
): Promise<{ data: T[]; error: unknown }> {
  const rows: T[] = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await page(from, from + PAGE - 1);
    if (error) return { data: rows, error };
    rows.push(...(data ?? []));
    if ((data ?? []).length < PAGE) return { data: rows, error: null };
  }
}

/**
 * `readAll` with the first two pages in flight together. The archive is a little over one page, so
 * the sequential version always paid two round trips back to back; this pays one, and goes on one
 * page at a time only if the second page is also full. Same contract: end the query with `.order('id')`. `page` must build a fresh query on every call — a
 * query builder is mutable, and two calls on one builder race to set its range.
 */
export async function readAllParallel<T>(
  page: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: unknown }>
): Promise<{ data: T[]; error: unknown }> {
  const [a, b] = await Promise.all([page(0, PAGE - 1), page(PAGE, 2 * PAGE - 1)]);
  if (a.error) return { data: [], error: a.error };
  const rows: T[] = [...(a.data ?? [])];
  if (rows.length < PAGE) return { data: rows, error: null };
  if (b.error) return { data: rows, error: b.error };
  rows.push(...(b.data ?? []));
  if ((b.data ?? []).length < PAGE) return { data: rows, error: null };
  for (let from = 2 * PAGE; ; from += PAGE) {
    const { data, error } = await page(from, from + PAGE - 1);
    if (error) return { data: rows, error };
    rows.push(...(data ?? []));
    if ((data ?? []).length < PAGE) return { data: rows, error: null };
  }
}
