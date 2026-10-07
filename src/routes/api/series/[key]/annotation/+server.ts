import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { dbError } from '$lib/server/http';

// ponytail: one storage download per sheet, so the page is capped. A 500-sheet series
// (L7014) would need the annotations merged ahead of time, not at request time.
const MAX_SHEETS = 60;

/**
 * One Georeference Annotation Page for every published, georeferenced sheet of a series,
 * so `viewer.allmaps.org/?url=<this>` shows the whole series at once. Published only:
 * no session path, unlike the per-map route.
 */
export const GET: RequestHandler = async ({ params }) => {
  const key = params.key;
  if (!/^[a-z0-9-]{1,120}$/.test(key)) throw error(400, 'Invalid series key');
  const admin = adminClient();
  const { data: maps, error: readError } = await admin
    .from('maps')
    .select('id')
    .eq('series_key', key)
    .eq('is_georeferenced', true)
    .in('status', ['public', 'featured'])
    .order('sheet_number', { nullsFirst: false })
    .limit(MAX_SHEETS);
  if (readError) dbError(readError, 'Could not read series');
  if (!maps?.length) throw error(404, 'No published georeferenced sheets in this series');

  const pages = await Promise.all(
    maps.map(async ({ id }) => {
      const { data: blob } = await admin.storage.from('annotations').download(`${id}.json`);
      return blob ? JSON.parse(await blob.text()) : null;
    })
  );
  const items = pages.flatMap((p) => (p ? (p.items ?? [p]) : []));
  return new Response(
    JSON.stringify({
      '@context': 'http://www.w3.org/ns/anno.jsonld',
      type: 'AnnotationPage',
      items,
    }),
    {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'X-Content-Type-Options': 'nosniff',
        'Cache-Control': 'public, max-age=300',
        'Access-Control-Allow-Origin': '*',
      },
    }
  );
};
