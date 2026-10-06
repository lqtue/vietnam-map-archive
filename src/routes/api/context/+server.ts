/**
 * GET /api/context?lng=&lat=&radius=&year_from=&year_to=&limit=
 *
 * Everything the archive knows about a spot: the maps that cover it, the OCR'd
 * labels and reviewed footprints near it, and any story point standing there.
 * The place-time index behind it is `context_at` (migration 066); design notes
 * in `docs/platform-design.md` §0.
 *
 * Public. Anonymous callers see published maps and approved stories only; that
 * gate lives in the RPC, because this route runs on the service client and
 * already knows the caller's role — the same arrangement as `search_labels`.
 *
 * `legend` is added here, not in the RPC: a legend point is an image-pixel
 * position warped per request (`warpLegend`), never stored. It covers only the
 * public maps the RPC returned that have legend entries, within `radius`, and
 * inherits its map's year — the RPC has already applied the year window.
 *
 * Every item carries `distance_m` and `geom_rmse`, so a caller can tell a
 * metre-accurate 1923 cadastral plan from a 1799 sketch with three GCPs. Rows
 * whose map has no georeference are absent by construction: they have no
 * position to report, and guessing one would be worse than saying nothing.
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { mapsWithLegend, readWarpedLegend } from '$lib/server/legendRead';
import { haversineDistance } from '$lib/core/geo/geo';

const DEFAULT_RADIUS_M = 150;
const MAX_RADIUS_M = 5000;
const DEFAULT_LIMIT = 50; // context_at's own default, and its cap is 200

function num(raw: string | null): number | null {
  if (raw === null || raw.trim() === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export const GET: RequestHandler = async ({ locals, url }) => {
  const lng = num(url.searchParams.get('lng'));
  const lat = num(url.searchParams.get('lat'));
  if (lng === null || lat === null || Math.abs(lng) > 180 || Math.abs(lat) > 90) {
    throw error(400, 'lng and lat are required, in degrees');
  }

  const radius = Math.min(
    Math.max(num(url.searchParams.get('radius')) ?? DEFAULT_RADIUS_M, 1),
    MAX_RADIUS_M
  );
  const role = await getRole(locals);

  const supabase = adminClient();
  const limit = Math.min(Math.max(num(url.searchParams.get('limit')) ?? DEFAULT_LIMIT, 1), 200);
  const { data, error: err } = await supabase.rpc('context_at', {
    p_lng: lng,
    p_lat: lat,
    p_radius_m: radius,
    p_year_from: num(url.searchParams.get('year_from')) ?? undefined,
    p_year_to: num(url.searchParams.get('year_to')) ?? undefined,
    p_public_only: role !== 'admin' && role !== 'mod',
    p_limit: limit,
  });
  if (err) dbError(err, 'Context lookup failed');

  const ctx = data as unknown as { maps?: { id: string; year: number | null; status: string }[] };
  const maps = (ctx.maps ?? []).filter((m) => m.status === 'public' || m.status === 'featured');
  const withLegend = await mapsWithLegend(
    supabase,
    maps.map((m) => m.id)
  );
  const { data: rows } = withLegend.size
    ? await supabase
        .from('maps')
        .select('id, allmaps_id, annotation_url, triage')
        .in('id', [...withLegend])
    : { data: [] };
  const warped = await Promise.all(
    (rows ?? []).map(async (row) => {
      const year = maps.find((m) => m.id === row.id)?.year ?? null;
      return (await readWarpedLegend(supabase, row)).flatMap((p) => {
        const distance_m = Math.round(haversineDistance([lng, lat], [p.lng, p.lat]) * 10) / 10;
        return distance_m > radius
          ? []
          : [
              {
                map_id: row.id,
                year,
                n: p.n,
                name: p.name,
                vn: p.vn,
                lng: p.lng,
                lat: p.lat,
                src: p.src,
                distance_m,
              },
            ];
      });
    })
  );
  const legend = warped.flat().sort((a, b) => a.distance_m - b.distance_m);

  return json({ ...ctx, legend: legend.slice(0, limit) });
};
