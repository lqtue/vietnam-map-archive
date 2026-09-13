// ---- Maps module — type definitions ----

export type MapSourceType = 'ia' | 'bnf' | 'efeo' | 'gallica' | 'rumsey' | 'self' | 'other';

export type MapStatus = 'draft' | 'public' | 'featured';

/** Full map record as stored in the database. */
export interface MapRecord {
  id: string;
  name: string; // display name (set by admin)
  location?: string; // city / region (renamed from `type`)
  original_title?: string; // title as in source / on the map
  creator?: string;
  year?: number;
  year_label?: string; // e.g. "c. 1882", "1898–1902"
  language?: string; // ISO 639-1
  rights?: string;
  dc_description?: string; // dc:description (migrated from `summary`)
  thumbnail?: string;

  // Source
  source_type?: MapSourceType;
  source_url?: string; // canonical URL at institution
  collection?: string; // e.g. "BnF Gallica", "EFEO"
  ia_identifier?: string; // Internet Archive item ID

  // IIIF
  iiif_manifest?: string; // manifest URL
  iiif_image?: string; // image service base URL

  // Georeferencing
  allmaps_id?: string; // 16-char Allmaps image ID (from @allmaps/id over canonical IIIF URL)
  annotation_url?: string; // Optional override URL to W3C annotation JSON (set by mirror-r2 → Supabase Storage)

  // Classification
  map_type?: string;
  bbox?: [number, number, number, number]; // [west, south, east, north]

  // Flexible custom metadata (schema-free JSONB)
  extra_metadata?: Record<string, string>;

  // Lifecycle
  status: MapStatus;

  created_at: string;
  updated_at?: string;
}

/** Lightweight item used in catalog lists and map selector dropdowns. */
export interface MapListItem {
  id: string; // maps.id (uuid)
  allmaps_id?: string; // 16-char Allmaps image ID (or null until derived)
  annotation_url?: string; // Optional override URL to the annotation JSON
  name: string;
  location?: string; // city / region (renamed from `type`)
  map_type?: string; // cartographic type: cadastral, topographic, city_plan, panorama
  dc_description?: string; // dc:description (migrated from `summary`)
  thumbnail?: string;
  isFeatured?: boolean;
  year?: number;
  year_label?: string;
  collection?: string;
  source_type?: MapSourceType;
  status?: MapStatus;
  bbox?: [number, number, number, number]; // DB column maps.bbox
  bounds?: [number, number, number, number]; // Runtime-enriched in useMapList; equivalent to bbox once resolved.
  extra_metadata?: Record<string, string>;
  iiif_image?: string; // IIIF image service base URL (present once ingested)
  georef_done?: boolean; // DB column maps.georef_done — an Allmaps annotation exists.
  // Distinguishes a map that can be laid on the world from one that is only viewable
  // as a scan; `allmaps_id` is not the same test, since every map carries one.
  creator?: string; // present in search results
  holding_institution?: string; // present in search results
  source_url?: string; // the holding library's own page for this sheet
  // Contribute-pass progress, set only by ToolMapPicker. Over a 39-sheet pass
  // "which have I already done?" is the column that decides what to open next,
  // so the picker shows it; nothing else sets or reads these.
  _triaged?: boolean;
  _ocrd?: boolean;
  // Search-result-only enrichment (only set by /api/search responses)
  _table?: 'maps' | 'scout';
  _score?: number;
  _snippet?: string; // ts_headline HTML (already sanitized to allow only <b>)
  _scout?: {
    // when _table === 'scout'
    id: string;
    source: string;
    category?: string;
    score?: number;
    status: string;
    source_url?: string;
    manifest_url?: string;
    publisher?: string;
    year?: number;
    date?: string;
  };
}

/** Metadata extracted from a IIIF manifest. */
export interface IIIFManifestMeta {
  title?: string; // actual descriptive title (from description/metadata["Title"])
  shelfmark?: string; // archival call number (BnF label / metadata["Shelfmark"])
  creator?: string;
  date?: string;
  language?: string;
  rights?: string;
  attribution?: string; // holding institution (manifest.attribution / BnF "Repository")
  sourceUrl?: string; // canonical item page URL (manifest.related for BnF)
  physicalDescription?: string; // format/dimensions from metadata["Format"]
  thumbnail?: string;
  imageServiceUrl?: string; // IIIF image service base URL
  manifestVersion: 2 | 3;
}

/**
 * Saved OCR triage for one sheet — `maps.triage` (migration 069).
 *
 * Lives here rather than beside the digitalize UI because `data` cannot import
 * from `features`: `fetchLabelMaps` returns it, and the enqueue script spreads
 * it straight into a job payload, so the shape is domain, not screen. Keys are
 * snake_case to match what `POST /api/admin/maps/[id]/ocr` already takes.
 */
import type { LayoutRegion } from './triageTypes';

export type StoredTriage = {
  neatline: [number, number, number, number];
  tile_size: number;
  overlap: number;
  /** Keyed `"x_y_w_h"` in source pixels; absent means normal (full-res). */
  tile_overrides: Record<string, 'skip' | 'low_res'>;
  /** The layout pass (migration 070): what the sheet is made of. Written by the
   *  `layout` job and corrected on the digitalize canvas. */
  regions?: LayoutRegion[];
  regions_at?: string;
  saved_at?: string;
};

/**
 * One sheet series, from the `map_series` view (migration 082) — a collection
 * of numbered sheets that /explore can put on the map as a single layer.
 * `sheets` and `bounds` count only what the reader is allowed to see.
 */
export interface MapSeries {
  key: string;
  collection: string;
  name: string;
  /** Distinct cells held as `maps` rows — not rows, which double-count editions. */
  sheets: number;
  publishedSheets: number;
  /** What the survey contains, from its own index (mig 083). Null: never imported. */
  surveySheets?: number;
  firstYear?: number;
  lastYear?: number;
  bounds: [number, number, number, number];
}
