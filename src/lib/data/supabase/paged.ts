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
