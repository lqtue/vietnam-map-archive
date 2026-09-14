/**
 * /catalog/series/<key>/<number> — one sheet of a survey.
 *
 * The record a sheet gets when it has no `maps` row: 452 of the L7014
 * 1:50,000's held sheets are cells of a pre-tiled mosaic, drawable on the map
 * and previously absent from every list, every search and every URL.
 *
 * A sheet the archive does not hold gets a page too, because "this survey
 * contains a sheet here and nobody has found a scan of it" is the most useful
 * thing this table knows — but those pages are `noindex` (see the component),
 * since 166 of L7014's 627 say exactly that and thin pages should not compete
 * in search with the sheets that exist.
 */

import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { adminClient } from '$lib/server/supabaseAdmin';
import { fetchSeriesSheet, cellCamera } from '$lib/data/maps/seriesSheets';

export const load: PageServerLoad = async ({ params }) => {
  const key = decodeURIComponent(params.key);
  const number = decodeURIComponent(params.number);
  const supabase = adminClient();

  const { data: series } = await supabase
    .from('map_series')
    .select('key,name,collection,first_year,last_year,published_sheets')
    .eq('key', key)
    .maybeSingle();
  if (!series || !series.published_sheets) throw error(404, 'No such series');

  const sheet = await fetchSeriesSheet(supabase, key, number);
  if (!sheet) throw error(404, 'That series contains no such sheet');

  // A sheet held as a `maps` row has a catalogue record of its own, and that is
  // the better page — this one exists for the cells that do not. Carry enough
  // to link there rather than duplicating it.
  //
  // EVERY record for the cell, not the one `series_sheets.map_id` happens to
  // point at. That column holds a single id, and a cell can be held more than
  // once for two unrelated reasons: two printings of the same sheet (Indochine
  // cells 2, 13 and 14, fourteen years apart), or the two half-sheets the
  // survey cut down the cell's middle meridian (cells 34, 37, 39, 67, 70 and
  // 73 bis). Following the single id gave every one of those a page that
  // silently hid its sibling — the west half of a cell, or an entire second
  // printing, reachable from nothing. The cell is the key here, so the query is
  // on the cell.
  // `collection` is the group key the view is built on, so in practice it is
  // always set — but it is nullable in the schema, and a null would widen the
  // query to every sheet numbered `number` in the archive rather than narrowing
  // it to this survey's.
  const { data: rows } = series.collection
    ? await supabase
        .from('maps')
        .select('id,name,year,status,extra_metadata')
        .eq('collection', series.collection)
        .eq('extra_metadata->>sheet_number', number)
        .in('status', ['public', 'featured'])
        .order('year', { ascending: true })
    : { data: [] };

  const maps = (rows ?? []).map((m) => ({
    id: m.id as string,
    name: m.name as string,
    year: m.year as number | null,
    // What distinguishes this record from its siblings: which half of the cell
    // it draws, or nothing when the cell is held whole and the year is the only
    // thing telling two records apart.
    half: ((m.extra_metadata as { sheet_half?: string } | null)?.sheet_half ?? null) as
      string | null,
  }));

  return {
    series,
    sheet,
    maps,
    camera: sheet.bbox ? cellCamera(sheet.bbox) : null,
  };
};
