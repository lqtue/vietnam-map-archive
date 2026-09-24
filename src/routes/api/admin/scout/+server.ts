// /api/admin/scout — list candidates (paginated, filtered) + bulk ingest
import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';
import { tally } from '$lib/server/facets';

export const GET: RequestHandler = async ({ locals, url }) => {
  await requireRole(locals, ['admin', 'mod']);
  const supabase = adminClient();

  const status = url.searchParams.get('status') || 'pending';
  const source = url.searchParams.get('source');
  const category = url.searchParams.get('category');
  const minScore = parseInt(url.searchParams.get('minScore') || '0');
  const search = url.searchParams.get('q')?.trim();
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '60'), 200);
  const offset = parseInt(url.searchParams.get('offset') || '0');
  const orderBy = url.searchParams.get('order') || 'score';
  const orderDir = url.searchParams.get('dir') === 'asc' ? 'asc' : 'desc';

  // `status` stays the response field name (the admin Scout UI's own
  // vocabulary) — `*` gives every real column, the alias adds `status`
  // alongside `review_status` (mig 095).
  let q = supabase.from('scout_candidates').select('*, status:review_status', { count: 'exact' });
  if (status !== 'all') q = q.eq('review_status', status);
  if (source) q = q.eq('source', source);
  if (category) q = q.eq('category', category);
  if (minScore) q = q.gte('score', minScore);
  if (search) q = q.ilike('title', `%${search}%`);
  q = q.order(orderBy, { ascending: orderDir === 'asc' }).range(offset, offset + limit - 1);

  const { data, error: err, count } = await q;
  if (err) dbError(err, 'Could not list scout candidates');

  // Facet counts (lightweight — only when offset=0)
  let facets: Record<string, Record<string, number>> | undefined;
  if (offset === 0) {
    const facetBase = supabase.from('scout_candidates');
    const [bySource, byCategory, byStatus] = await Promise.all([
      facetBase.select('source').eq('review_status', status),
      facetBase.select('category').eq('review_status', status),
      facetBase.select('status:review_status'),
    ]);
    const opts = { emptyLabel: '(none)' };
    facets = {
      source: tally(bySource.data, 'source', opts),
      category: tally(byCategory.data, 'category', opts),
      status: tally(byStatus.data, 'status', opts),
    };
  }

  return json({ rows: data, total: count, limit, offset, facets });
};

// POST: bulk ingest approved candidates → maps rows
export const POST: RequestHandler = async ({ locals, request }) => {
  const { user } = await requireRole(locals, ['admin', 'mod']);
  const supabase = adminClient();
  const body = await request.json();
  const ids: string[] = body.ids || [];
  if (!ids.length) throw error(400, 'ids[] required');

  const { data: cands, error: fetchErr } = await supabase
    .from('scout_candidates')
    .select('*')
    .in('id', ids)
    .eq('review_status', 'approved');
  if (fetchErr) dbError(fetchErr, 'Could not load scout candidates');

  const results: { id: string; map_id?: string; error?: string }[] = [];
  for (const c of cands ?? []) {
    try {
      // Mig 062 only constrains published maps, so a candidate with no image
      // source would insert happily as a draft and then be unusable. Say so
      // instead, and leave the candidate approved so it can be fixed and retried.
      const imageUrl = (c.raw as { iiif_image?: string } | null)?.iiif_image ?? null;
      if (!c.manifest_url && !imageUrl)
        throw new Error('No IIIF manifest or image URL — cannot ingest');

      const holdingInst = c.holding_institution ?? '';
      const insertPayload = {
        name: (c.title || '(untitled)').slice(0, 240),
        year: c.year ?? null,
        date_label: c.date ?? null,
        status: 'draft',
        source_type: holdingInst.includes('David Rumsey')
          ? 'rumsey'
          : holdingInst.includes('Bibliothèque nationale')
            ? 'bnf'
            : 'other',
        holding_institution: c.holding_institution ?? null,
        collection: c.collection ?? null,
        original_title: c.title ?? null,
        creator: c.creator ?? null,
        publisher: c.publisher ?? null,
        language: c.language ?? null,
        rights: c.rights ?? null,
        // A source with no reachable Presentation manifest can still expose an
        // Image API endpoint; scoutDerive.mjs parks it here (LoC is the case).
        iiif_image: imageUrl,
        source_url: c.source_url ?? null,
        thumbnail: c.thumbnail ?? null,
        extra_metadata: {
          scout_source: c.source,
          scout_external_id: c.external_id,
          scout_category: c.category,
          scout_found_via: c.found_via,
          scout_candidate_id: c.id,
        },
      };
      const { data: newMap, error: insErr } = await supabase
        .from('maps')
        .insert(insertPayload)
        .select('id')
        .single();
      if (insErr) throw new Error(insErr.message);
      const mapId = newMap.id;

      // The manifest now lives per-source, on map_images (was map_iiif_sources,
      // mig 095) rather than on maps directly. map_images.iiif_image is
      // NOT NULL, so a manifest-only candidate (no Image API endpoint) has
      // nothing to record here — its source can still be added by hand in the
      // Hosting tab.
      if (c.manifest_url && imageUrl) {
        await supabase.from('map_images').insert({
          map_id: mapId,
          iiif_manifest: c.manifest_url,
          iiif_image: imageUrl,
          is_primary: true,
        });
      }

      await supabase
        .from('scout_candidates')
        .update({
          review_status: 'ingested',
          map_id: mapId,
          reviewed_by: user.id,
          reviewed_at: new Date().toISOString(),
        })
        .eq('id', c.id);

      results.push({ id: c.id, map_id: mapId });
    } catch (e) {
      results.push({ id: c.id, error: (e as Error).message.slice(0, 200) });
    }
  }

  return json({
    results,
    ok: results.filter((r) => !r.error).length,
    failed: results.filter((r) => r.error).length,
  });
};
