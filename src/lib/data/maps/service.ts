// ---- Maps module — Supabase service ----
// Public-facing read functions for the catalog and map selector.
// Admin write operations live in adminApi.ts (server-side only).

import type { SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '$lib/data/supabase/types';
import type { MapListItem, MapSeries, MapSourceType, MapStatus } from './types';
import { looksValidBbox } from '$lib/core/geo/mapBounds';

export type DbRow = Database['public']['Tables']['maps']['Row'];

/**
 * Exactly the columns `toMapListItem` reads. `select('*')` sent 120 KB of row
 * for the catalog (37 KB over the wire), most of it `extra_metadata` and the
 * long source fields no list ever renders; this is 9 KB. `fetchMapRow` still
 * takes the whole row — the admin editor writes back columns no list carries.
 */
const LIST_COLUMNS =
  'id,allmaps_id,annotation_url,name,location,map_type,dc_description,thumbnail,status,year,year_label,collection,holding_institution,source_url,source_type,bbox,iiif_image,georef_done';

function toMapListItem(row: DbRow): MapListItem {
  return {
    id: row.id,
    allmaps_id: row.allmaps_id ?? undefined,
    annotation_url: row.annotation_url ?? undefined,
    name: row.name,
    location: row.location ?? undefined,
    map_type: row.map_type ?? undefined,
    dc_description: row.dc_description ?? undefined,
    thumbnail: row.thumbnail ?? undefined,
    isFeatured: row.status === 'featured',
    year: row.year ?? undefined,
    year_label: row.year_label ?? undefined,
    collection: row.collection ?? undefined,
    holding_institution: row.holding_institution ?? undefined,
    source_url: row.source_url ?? undefined,
    source_type: (row.source_type ?? undefined) as MapSourceType | undefined,
    status: (row.status ?? 'draft') as MapStatus,
    bbox: (row.bbox ?? undefined) as [number, number, number, number] | undefined,
    iiif_image: row.iiif_image ?? undefined,
    georef_done: row.georef_done ?? false,
  };
}

/** All maps (published). For catalog page. */
export async function fetchMaps(supabase: SupabaseClient<Database>): Promise<MapListItem[]> {
  const { data, error } = await supabase.from('maps').select(LIST_COLUMNS).order('name');

  if (error) {
    console.error('fetchMaps:', error);
    return [];
  }
  return (data as unknown as DbRow[]).map(toMapListItem);
}

/** Featured maps only, sorted by year. For home page hero. */
export async function fetchFeaturedMaps(
  supabase: SupabaseClient<Database>
): Promise<MapListItem[]> {
  const { data, error } = await supabase
    .from('maps')
    .select(LIST_COLUMNS)
    .eq('status', 'featured')
    .order('year', { ascending: true, nullsFirst: false });

  if (error) {
    console.error('fetchFeaturedMaps:', error);
    return [];
  }
  return (data as unknown as DbRow[]).map(toMapListItem);
}

/**
 * How many maps a reader can actually see. `head: true` asks for the count and
 * no rows at all — the front page quoted this number by fetching the whole
 * catalog and reading `.length`.
 */
export async function fetchPublishedMapCount(supabase: SupabaseClient<Database>): Promise<number> {
  const { count, error } = await supabase
    .from('maps')
    .select('id', { count: 'exact', head: true })
    .in('status', ['public', 'featured']);

  if (error) {
    console.error('fetchPublishedMapCount:', error);
    return 0;
  }
  return count ?? 0;
}

/** The named maps, in one query. For a list of ids you already hold — favorites. */
export async function fetchMapsByIds(
  supabase: SupabaseClient<Database>,
  ids: string[]
): Promise<MapListItem[]> {
  if (!ids.length) return [];

  const { data, error } = await supabase.from('maps').select(LIST_COLUMNS).in('id', ids);

  if (error) {
    console.error('fetchMapsByIds:', error);
    return [];
  }
  return (data as unknown as DbRow[]).map(toMapListItem);
}

/** Maps that have been georeferenced (have allmaps_id OR annotation_url). For view/overlay mode. */
export async function fetchGeoreferencedMaps(
  supabase: SupabaseClient<Database>
): Promise<MapListItem[]> {
  const { data, error } = await supabase
    .from('maps')
    .select(LIST_COLUMNS)
    .or('allmaps_id.not.is.null,annotation_url.not.is.null')
    .order('year', { ascending: true, nullsFirst: false });

  if (error) {
    console.error('fetchGeoreferencedMaps:', error);
    return [];
  }
  return (data as unknown as DbRow[]).map(toMapListItem);
}

/**
 * One full `maps` row by id. Used where the list-item projection isn't enough
 * (the admin editor writes back columns the search result never carried).
 */
export async function fetchMapRow(
  supabase: SupabaseClient<Database>,
  id: string
): Promise<DbRow | null> {
  const { data, error } = await supabase.from('maps').select('*').eq('id', id).single();
  if (error || !data) {
    console.error('fetchMapRow:', error);
    return null;
  }
  return data as DbRow;
}

/** One printing of a sheet: what tells two rows of the same cell apart. */
export interface SheetEdition {
  id: string;
  name: string;
  year?: number;
  status: MapStatus;
  /** As printed on the sheet — "5-DMA", "2-AMS (29 ETB)", "3". */
  edition?: string;
  /** When the paper says it was printed, which is not always its content date. */
  printing?: string;
  /** Both carried so the row can go straight onto the layer stack. */
  allmaps_id?: string;
  annotation_url?: string;
  thumbnail?: string;
  /**
   * Whether the sheet can actually be drawn. Not `allmaps_id != null`: the
   * bulk uploader derives that id from the IIIF URL for every self-hosted
   * scan, georeferenced or not, so the loose test calls a sheet warped the
   * moment it is tiled and the layer draws nothing.
   */
  georef_done: boolean;
}

/**
 * The other printings of the same sheet.
 *
 * A sheet is `(series, sheet_number)` and an edition is a row, so this needs no
 * join table — the dropped `pipeline_sheets` (mig 012, `UNIQUE (series,
 * sheet_number)`) is the reminder of why not: it asserted one scan per cell,
 * which the corpus does not honour. Cell 6330-4 alone is SÀI GÒN 1965 and
 * THÀNH PHỐ HỒ CHÍ MINH 1984.
 *
 * The series half of that key is **`collection`**, not `extra_metadata.series`.
 * Collection is what makes a series a series everywhere else — `series_key()`
 * (mig 082) and `series_sheets` (083) are both built on it — and the metadata
 * spelling is a second name for the same fact that only some rows carry: all
 * 62 Indochine 1:25,000 rows have a sheet number and none has a `series`, so
 * keying on it hid the three cells that survey holds in two editions.
 *
 * Two round trips because PostgREST has no subquery: the row's own key, then
 * its siblings. RLS decides what comes back, which is the whole visibility
 * story — anonymous readers see published editions, a signed-in one also sees
 * drafts (mig 063). Nothing here filters by status.
 */
export async function fetchSheetEditions(
  supabase: SupabaseClient<Database>,
  mapId: string
): Promise<SheetEdition[]> {
  const { data: self, error: selfError } = await supabase
    .from('maps')
    .select('extra_metadata, collection')
    .eq('id', mapId)
    .single();
  if (selfError || !self) return [];

  const meta = (self.extra_metadata ?? {}) as Record<string, unknown>;
  const sheet = typeof meta.sheet_number === 'string' ? meta.sheet_number : null;
  const series = self.collection;
  if (!sheet || !series) return [];

  const { data, error } = await supabase
    .from('maps')
    .select('id,name,year,status,extra_metadata,allmaps_id,annotation_url,thumbnail,georef_done')
    .eq('extra_metadata->>sheet_number', sheet)
    .eq('collection', series)
    .neq('id', mapId)
    .order('year', { ascending: true });
  if (error || !data) {
    console.error('fetchSheetEditions:', error);
    return [];
  }

  return data.map((row) => {
    const rowMeta = (row.extra_metadata ?? {}) as Record<string, unknown>;
    return {
      id: row.id,
      name: row.name,
      year: row.year ?? undefined,
      status: (row.status ?? 'draft') as MapStatus,
      edition: typeof rowMeta.edition === 'string' ? rowMeta.edition : undefined,
      printing: typeof rowMeta.printing === 'string' ? rowMeta.printing : undefined,
      allmaps_id: row.allmaps_id ?? undefined,
      annotation_url: row.annotation_url ?? undefined,
      thumbnail: row.thumbnail ?? undefined,
      georef_done: row.georef_done ?? false,
    };
  });
}

/**
 * Every georeferenced sheet in one series, as annotation sources.
 *
 * The `SheetsRef` on the overlay stack stores only the collection name, so this
 * is what turns that into something drawable. `annotation_url` (the R2 mirror)
 * wins over the bare Allmaps id, the same precedence `toHistoricalRef` uses.
 *
 * RLS decides what comes back. A series still in `draft` resolves to its sheets
 * for a signed-in reader and to nothing at all for an anonymous one — which
 * draws an empty layer rather than an error, so the caller is the one that has
 * to decide whether to offer the row.
 */
export async function fetchSeriesSheets(
  supabase: SupabaseClient<Database>,
  collection: string
): Promise<{ id: string; source: string; bbox?: [number, number, number, number] }[]> {
  const { data, error } = await supabase
    .from('maps')
    .select('id, allmaps_id, annotation_url, bbox')
    .eq('collection', collection)
    .eq('georef_done', true)
    .order('year', { ascending: true });

  if (error || !data) {
    console.error('fetchSeriesSheets:', error);
    return [];
  }

  // `bbox` comes along because it is what lets the layer fetch the annotations
  // of the sheets on screen and no others. It is four numbers in a row already
  // being read; without it a 56-sheet series costs 56 round trips to draw four.
  return data
    .map((row) => ({
      id: row.id,
      source: row.annotation_url ?? row.allmaps_id ?? '',
      bbox: looksValidBbox(row.bbox) ? (row.bbox as [number, number, number, number]) : undefined,
    }))
    .filter((s) => s.source !== '');
}

/**
 * Every sheet series the archive holds, from the `map_series` view (mig 082).
 *
 * The view is the definition: a collection whose sheets carry a sheet number,
 * has more than one distinct one georeferenced, and that this reader is allowed
 * to see. `sheets` counts cells rather than rows (mig 084), so a survey holding
 * two printings of one sheet is one sheet, and `surveySheets` is the survey's
 * own denominator from `series_sheets`. That last clause is why there is no `draft` flag anywhere in the UI — a
 * wholly-unpublished series simply has no row for an anonymous reader, so the
 * list is already the list of series worth offering.
 */
export async function fetchMapSeries(supabase: SupabaseClient<Database>): Promise<MapSeries[]> {
  const { data, error } = await supabase
    .from('map_series')
    .select(
      'key, collection, name, sheets, published_sheets, survey_sheets, first_year, last_year, bounds'
    )
    .order('first_year', { ascending: true });

  if (error || !data) {
    console.error('fetchMapSeries:', error);
    return [];
  }

  return data.flatMap((row) => {
    // `bounds` is built by the view as four aggregates, so a null can only mean
    // a sheet slipped through with a malformed bbox. Without four numbers the
    // row cannot answer "zoom to this layer", which is the one thing the stack
    // needs from it.
    const b = row.bounds;
    if (!Array.isArray(b) || b.length !== 4 || b.some((n) => typeof n !== 'number')) return [];
    return [
      {
        key: row.key as string,
        collection: row.collection as string,
        name: (row.name as string) ?? (row.collection as string),
        sheets: Number(row.sheets ?? 0),
        publishedSheets: Number(row.published_sheets ?? 0),
        // Null where the survey's index was never imported (mig 083), which is
        // not the same as zero — a caller showing a denominator has to fall
        // back to `sheets` rather than print "9 of 0".
        surveySheets: row.survey_sheets == null ? undefined : Number(row.survey_sheets),
        firstYear: row.first_year ?? undefined,
        lastYear: row.last_year ?? undefined,
        bounds: b as [number, number, number, number],
      },
    ];
  });
}
