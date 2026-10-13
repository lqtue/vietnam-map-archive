/**
 * GET /api/press/image?oid=<id>&crop=<x,y,w,h>&w=<px>
 *
 * The National Library's image server answers on http only, and a browser on an
 * https page blocks an http image. This route fetches it server-side and hands
 * the bytes on, so `press.ts` thumbnails no longer depend on someone else's
 * proxy. The host is fixed and every param is matched against a pattern, so the
 * route cannot be pointed at another address.
 */

import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const IMAGES = 'http://baochi.nlv.gov.vn/baochi/cgi-bin/imageserver/imageserver.pl';
const OID_RE = /^[A-Za-z0-9._-]{1,64}$/;
const CROP_RE = /^\d{1,5},\d{1,5},\d{1,5},\d{1,5}$/;
const MAX_W = 2000;

export const GET: RequestHandler = async ({ url }) => {
  const oid = url.searchParams.get('oid') ?? '';
  if (!OID_RE.test(oid)) throw error(400, 'Invalid oid');

  const crop = url.searchParams.get('crop');
  if (crop !== null && !CROP_RE.test(crop)) throw error(400, 'Invalid crop');

  const w = Number(url.searchParams.get('w'));
  if (!Number.isInteger(w) || w < 1 || w > MAX_W) throw error(400, `w must be 1-${MAX_W}`);

  const upstream = new URL(IMAGES);
  upstream.searchParams.set('oid', oid);
  upstream.searchParams.set('area', '1');
  if (crop) upstream.searchParams.set('crop', crop);
  upstream.searchParams.set('width', String(w));
  upstream.searchParams.set('color', 'all');
  upstream.searchParams.set('ext', 'jpg');

  const res = await fetch(upstream, { signal: AbortSignal.timeout(15_000) }).catch(() => null);
  if (!res?.ok) throw error(502, 'Image unavailable');

  return new Response(res.body, {
    headers: {
      'Content-Type': 'image/jpeg', // upstream says the non-standard image/jpg
      // A newspaper page never changes; let the edge keep it.
      'Cache-Control': 'public, max-age=2592000',
    },
  });
};
