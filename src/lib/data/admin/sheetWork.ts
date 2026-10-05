import type { WorkFactsById } from '$lib/core/sheetWork';

/**
 * What has been done to each sheet, from `/api/admin/maps/work-state` (admin/mod
 * only). Pass a map uuid for just that sheet. Null when the call fails or the
 * reader is not staff — callers draw no chips rather than an error.
 */
export async function fetchSheetWork(mapId?: string): Promise<WorkFactsById | null> {
  try {
    const res = await fetch(
      '/api/admin/maps/work-state' + (mapId ? `?map=${encodeURIComponent(mapId)}` : '')
    );
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}
