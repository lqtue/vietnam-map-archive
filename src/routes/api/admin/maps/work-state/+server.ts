import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { requireRole } from '$lib/server/auth';
import { adminClient } from '$lib/server/supabaseAdmin';
import { assertUuid, dbError } from '$lib/server/http';
import { readAll } from '$lib/data/supabase/paged';
import { NO_WORK, type WorkFacts } from '$lib/core/sheetWork';
import { triageState, type SavedTriage } from '$lib/data/maps/triageTypes';

/**
 * Per sheet: what has been done to it, for the catalog table, the record page
 * and the /scan?mode=legend picker. Derived on every call — triage from
 * `maps.triage`, found regions likewise, read kinds from `ocr_labels.category`,
 * OCR / segmentation / human checks from `map_pipeline_status`. Nothing is
 * stored, so it cannot disagree with the data. `?map=<uuid>` narrows to one.
 *
 * Index pass is not here: it writes ordinary `street` rows, so the category
 * cannot tell it from the body pass.
 */
const BODY = new Set(['street', 'place', 'building', 'institution', 'hydrology', 'other']);

export const GET: RequestHandler = async ({ locals, url }) => {
  await requireRole(locals, ['admin', 'mod']);
  const db = adminClient();
  const only = url.searchParams.get('map');
  if (only) assertUuid(only);

  const [maps, labels, stages] = await Promise.all([
    readAll((from, to) =>
      (only
        ? db
            .from('maps')
            .select(
              'id,regions:triage->regions,neatline:triage->neatline,validated:triage->validated_at,legend:triage->legend,triage_reviewed_at'
            )
            .eq('id', only)
        : db
            .from('maps')
            .select(
              'id,regions:triage->regions,neatline:triage->neatline,validated:triage->validated_at,legend:triage->legend,triage_reviewed_at'
            )
      )
        .order('id')
        .range(from, to)
    ),
    readAll((from, to) =>
      (only
        ? db.from('ocr_labels').select('id,map_id,category').eq('map_id', only)
        : db.from('ocr_labels').select('id,map_id,category')
      )
        .neq('review_status', 'rejected')
        .order('id')
        .range(from, to)
    ),
    readAll((from, to) =>
      (only
        ? db
            .from('map_pipeline_status')
            .select('map_id,reviewed_at,seg_reviewed_at,ocr_finished_at,seg_finished_at')
            .eq('map_id', only)
        : db
            .from('map_pipeline_status')
            .select('map_id,reviewed_at,seg_reviewed_at,ocr_finished_at,seg_finished_at')
      )
        .order('map_id')
        .range(from, to)
    ),
  ]);
  if (maps.error) dbError(maps.error, 'Could not read triage');
  if (labels.error) dbError(labels.error, 'Could not read OCR labels');
  if (stages.error) dbError(stages.error, 'Could not read pipeline status');

  const out: Record<string, WorkFacts> = {};
  const facts = (id: string) =>
    (out[id] ??= {
      ...NO_WORK,
      found: { ...NO_WORK.found },
      read: { ...NO_WORK.read },
    });

  for (const m of maps.data as {
    id: string;
    regions: { category?: string; source?: string }[] | null;
    neatline: number[] | null;
    validated: string | null;
    legend: string | null;
    triage_reviewed_at: string | null;
  }[]) {
    const regions = Array.isArray(m.regions) ? m.regions : [];
    const triage = triageState({
      regions,
      neatline: m.neatline,
      validated_at: m.validated ?? m.triage_reviewed_at,
    } as unknown as SavedTriage);
    // A sheet nobody has touched keeps no row: absent means "nothing done".
    if (triage === 'needs_layout' && !regions.length && m.legend !== 'none') continue;
    const f = facts(m.id);
    f.triage = triage;
    // A person's "no legend", or a layout a person accepted in which the scout found none.
    if (
      m.legend === 'none' ||
      (triage === 'ready' && !regions.some((r) => r.category === 'legend'))
    )
      f.noLegend = true;
    for (const r of regions) {
      if (r.category === 'title') f.found.title = true;
      // The model's legend guess is not trusted (see WorkFacts); only a person's region counts.
      else if (r.category === 'legend' && r.source !== 'model') f.found.legend = true;
      else if (r.category === 'name_list') f.found.index = true;
    }
  }
  for (const l of labels.data) {
    if (!l.map_id) continue;
    const read = facts(l.map_id).read;
    if (l.category === 'title') read.title = true;
    else if (l.category === 'legend_entry') read.legend = true;
    else if (BODY.has(l.category)) read.body = true;
  }
  for (const s of stages.data) {
    if (!s.map_id) continue;
    if (!(s.reviewed_at || s.seg_reviewed_at || s.ocr_finished_at || s.seg_finished_at)) continue;
    const f = facts(s.map_id);
    f.textReviewed = !!s.reviewed_at;
    f.shapesReviewed = !!s.seg_reviewed_at;
    f.ocrRan = !!s.ocr_finished_at;
    f.segRan = !!s.seg_finished_at;
  }
  return json(out, { headers: { 'Cache-Control': 'private, no-store' } });
};
