import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { readAll } from '$lib/data/supabase/paged';
import { legendNumber, manualLegendPoint } from '$lib/server/legendEntry';

/**
 * Per sheet: how many numbered legend entries were read, and how many of them
 * have a staff-placed pixel position. One paged read over every sheet, for the
 * /scan?mode=legend map picker. Same placed rule as the staff GET: `px=` only,
 * a legacy ground `point=` still reads as unplaced there.
 */
export const GET: RequestHandler = async ({ locals }) => {
  await requireRole(locals, ['admin', 'mod']);
  const { data, error: readError } = await readAll((from, to) =>
    adminClient()
      .from('ocr_labels')
      .select('id,map_id,text,text_corrected,notes')
      .eq('category', 'legend_entry')
      .neq('review_status', 'rejected')
      .order('id')
      .range(from, to)
  );
  if (readError) dbError(readError, 'Could not read legend progress');
  const byMap = new Map<string, Map<number, boolean>>();
  for (const row of data) {
    const n = legendNumber(row.text_corrected ?? row.text, row.notes);
    if (!row.map_id || n == null) continue;
    const entries = byMap.get(row.map_id) ?? new Map<number, boolean>();
    const point = manualLegendPoint(row.notes);
    entries.set(n, (entries.get(n) ?? false) || (!!point && 'px' in point));
    byMap.set(row.map_id, entries);
  }
  return json(
    Object.fromEntries(
      [...byMap].map(([id, entries]) => [
        id,
        { total: entries.size, placed: [...entries.values()].filter(Boolean).length },
      ])
    ),
    { headers: { 'Cache-Control': 'private, no-store' } }
  );
};
