/** Only the additive grouping schema may fall back; other DB failures stay errors. */
export function missingTextGroupColumns(err: { code?: string; message?: string } | null): boolean {
  return (
    !!err &&
    ['42703', 'PGRST204'].includes(err.code ?? '') &&
    /\b(is_text_group|text_group_id|text_group_order)\b/.test(err.message ?? '')
  );
}
