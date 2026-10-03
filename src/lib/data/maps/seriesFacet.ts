/** Match the durable series identity; mutable collection labels are not keys. */
export function matchesSeriesFacet(
  row: { series_key?: string | null; collection?: string | null },
  selectedKeys: readonly string[]
) {
  return (
    selectedKeys.length === 0 ||
    (row.series_key != null &&
      row.series_key !== '' &&
      selectedKeys.includes(String(row.series_key)))
  );
}
