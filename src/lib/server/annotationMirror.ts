/**
 * Self-hosting a map's georeference.
 *
 * Decision 5 in `docs/architecture-target.md`: Allmaps stays the georeferencing
 * tool, but nothing at runtime may depend on allmaps.org being up. So the
 * annotation is copied into Supabase Storage with its IIIF source rewritten to
 * our R2 worker, and `maps.annotation_url` points at that copy.
 *
 * Storage has no object versioning, so each mirror writes twice: the stable
 * `annotations/{mapId}.json` the app reads, and `annotations/{mapId}/{ISO}.json`
 * as history. Path *is* the version.
 */

import { error } from '@sveltejs/kit';
import { adminClient } from './supabaseAdmin';
import { uploadJson } from './storage';
import { r2MirrorBase, sourceSizeMismatch } from '$lib/core/iiif/sourceSize';

const R2_BASE = 'https://iiif.maparchive.vn/iiif';
const ANNOTATIONS_BUCKET = 'annotations';
const ALLMAPS_ANNOTATIONS = 'https://annotations.allmaps.org/images';

/**
 * Walks an Allmaps annotation (single Annotation or AnnotationCollection)
 * and returns the first IIIF image service URL found in the target source.
 */
function extractSourceUrl(annotation: any): string | null {
  const items: any[] =
    annotation.type === 'Annotation' ? [annotation] : (annotation.items ?? annotation.maps ?? []);

  for (const item of items) {
    const target = item.target;
    if (!target) continue;
    const source = typeof target === 'string' ? target : (target.source ?? target);
    const id = typeof source === 'string' ? source : source?.id;
    if (id && typeof id === 'string' && id.startsWith('http')) return id;
  }
  return null;
}

/** Replace every occurrence of `oldUrl` with `newUrl` throughout the JSON. */
function rewriteSourceUrl(annotation: any, oldUrl: string, newUrl: string): any {
  const raw = JSON.stringify(annotation);
  const oldBase = oldUrl.replace(/\/+$/, '');
  const newBase = newUrl.replace(/\/+$/, '');
  const updated = raw.replaceAll(oldBase + '/', newBase + '/').replaceAll(oldBase, newBase);
  return JSON.parse(updated);
}

export type MirrorResult = {
  iiif_image: string;
  annotation_url: string;
  history_url: string;
  thumbnail: string;
  old_source_url: string | null;
  download_url: string | null;
  tile_command: string;
};

/**
 * Fetch, rewrite and store a map's annotation, then point the map row at the
 * stored copy and make R2 its primary IIIF source.
 *
 * `fromAllmaps` ignores any existing `annotation_url` override and goes back to
 * the Allmaps annotation server — that is the "fetch latest" path, for when the
 * georeference has been edited upstream.
 */
export async function mirrorAnnotation(
  mapId: string,
  { fromAllmaps = false }: { fromAllmaps?: boolean } = {}
): Promise<MirrorResult> {
  const supabase = adminClient();

  const { data: map } = await supabase
    .from('maps')
    .select('id, name, allmaps_id, annotation_url, iiif_image')
    .eq('id', mapId)
    .single();

  if (!map) throw error(404, 'Map not found');
  if (!map.allmaps_id && !map.annotation_url) {
    throw error(400, 'Map has no allmaps_id or annotation_url — cannot fetch annotation');
  }
  if (fromAllmaps && !map.allmaps_id) {
    throw error(400, 'Map has no allmaps_id — nothing upstream to re-fetch');
  }

  const sourceUrl =
    fromAllmaps || !map.annotation_url
      ? `${ALLMAPS_ANNOTATIONS}/${map.allmaps_id}`
      : map.annotation_url;

  const annotationRes = await fetch(sourceUrl + '?_t=' + Date.now(), {
    headers: { Accept: 'application/json' },
  });
  if (!annotationRes.ok) {
    throw error(502, `Failed to fetch annotation: ${annotationRes.statusText}`);
  }
  const annotation = await annotationRes.json();

  const oldSourceUrl = extractSourceUrl(annotation);
  const newIiifBase = r2MirrorBase(map.iiif_image, `${R2_BASE}/${mapId}`);
  const updated = oldSourceUrl
    ? rewriteSourceUrl(annotation, oldSourceUrl, newIiifBase)
    : annotation;

  const mismatch = await sourceSizeMismatch(updated, newIiifBase);
  if (mismatch) throw error(409, mismatch);

  // History first: if the second write fails, we have still kept the version.
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const historyUrl = await uploadJson(ANNOTATIONS_BUCKET, `${mapId}/${stamp}.json`, updated);
  const publicAnnotationUrl = await uploadJson(ANNOTATIONS_BUCKET, `${mapId}.json`, updated);

  // Keep allmaps_id intact — it is the bare image ID, not a URL.
  await supabase
    .from('maps')
    .update({
      iiif_image: newIiifBase,
      annotation_url: publicAnnotationUrl,
      thumbnail: `${newIiifBase}/full/800,/0/default.jpg`,
      collection: 'Vietnam Map Archive',
    })
    .eq('id', mapId);

  await upsertR2Source(mapId, newIiifBase);

  // Use the non-R2 source as the proxy origin, so the worker cannot loop.
  let originalIiifImage: string | null = null;
  if (map.iiif_image && !map.iiif_image.includes('maparchive.vn')) {
    originalIiifImage = map.iiif_image;
  } else if (oldSourceUrl && !oldSourceUrl.includes('maparchive.vn')) {
    originalIiifImage = oldSourceUrl;
  }

  const downloadUrl = originalIiifImage
    ? originalIiifImage.includes('gallica.bnf.fr')
      ? `${originalIiifImage.replace(/\/$/, '')}/full/full/0/native.jpg`
      : `${originalIiifImage.replace(/\/$/, '')}/full/max/0/default.jpg`
    : null;

  return {
    iiif_image: newIiifBase,
    annotation_url: publicAnnotationUrl,
    history_url: historyUrl,
    thumbnail: `${newIiifBase}/full/800,/0/default.jpg`,
    old_source_url: originalIiifImage,
    download_url: downloadUrl,
    // Third arg makes tile_map.sh write sources/{mapId} to R2.
    tile_command: `./scripts/tile_map.sh ${mapId} "${downloadUrl ?? '<source-image-url>'}" "${originalIiifImage ?? ''}"`,
  };
}

/** Make the R2 URL this map's primary IIIF source, creating the row if needed. */
async function upsertR2Source(mapId: string, newIiifBase: string): Promise<void> {
  const supabase = adminClient();

  const { data: existingSources } = await supabase
    .from('map_iiif_sources')
    .select('id, iiif_image, sort_order')
    .eq('map_id', mapId);

  const r2Source = (existingSources ?? []).find((s) => s.iiif_image?.includes('maparchive.vn'));

  // One primary per map is a partial unique index, so demote before promoting.
  await supabase
    .from('map_iiif_sources')
    .update({ is_primary: false })
    .eq('map_id', mapId)
    .eq('is_primary', true);

  if (r2Source) {
    const { error: upErr } = await supabase
      .from('map_iiif_sources')
      .update({ iiif_image: newIiifBase, is_primary: true })
      .eq('id', r2Source.id);
    if (upErr) throw error(500, 'IIIF source update failed');
    return;
  }

  const maxOrder = (existingSources ?? []).reduce((max, s) => Math.max(max, s.sort_order ?? 0), 0);
  const { error: insErr } = await supabase.from('map_iiif_sources').insert({
    map_id: mapId,
    label: 'Cloudflare R2',
    source_type: 'r2',
    iiif_image: newIiifBase,
    is_primary: true,
    sort_order: maxOrder + 1,
  });
  if (insErr) throw error(500, 'IIIF source insert failed');
}
