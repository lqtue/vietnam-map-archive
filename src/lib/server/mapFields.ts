/**
 * The single allow-list of client-writable `maps` columns.
 *
 * `POST /api/admin/maps` and `PATCH /api/admin/maps/[id]` each maintained their
 * own copy and had already drifted — PATCH accepted `label_config`, `priority`,
 * `legend_done` and `help_needed` while POST silently dropped
 * them. This is the union of the two, with the coercion each field had.
 *
 * Server-set columns (`id`, `created_at`, `updated_at`, `search_vector`) are
 * deliberately absent: a client must never be able to write them.
 */

import type { Database } from '$lib/data/supabase/types';

type MapWrite = Database['public']['Tables']['maps']['Update'];

type Coerce = (v: unknown) => unknown;

const asIs: Coerce = (v) => v;
const orNull: Coerce = (v) => v || null;
const asBool: Coerce = (v) => Boolean(v);
const asYear: Coerce = (v) => (v ? Number(v) : null);
const asCount: Coerce = (v) => Number(v) || 0;
/** Only a flat object survives; anything else drops the field entirely. */
const asObject: Coerce = (v) =>
  typeof v === 'object' && v !== null && !Array.isArray(v) ? v : undefined;

export const MAP_WRITABLE_FIELDS: Record<string, Coerce> = {
  name: asIs,
  allmaps_id: asIs,
  annotation_url: orNull,
  location: orNull,
  year: asYear,
  date_label: orNull,
  description: orNull,
  publisher: orNull,
  thumbnail: orNull,
  // source / IIIF
  source_type: asIs,
  iiif_image: orNull,
  original_title: orNull,
  creator: orNull,
  language: orNull,
  rights: orNull,
  source_url: orNull,
  shelfmark: orNull,
  physical_description: orNull,
  holding_institution: orNull,
  collection: orNull,
  map_type: orNull,
  bbox: orNull,
  status: asIs,
  extra_metadata: asObject,
  label_config: asIs,
  triage: asObject,
  sheet_number: orNull,
  sheet_half: orNull,
  // contribution flags
  priority: asCount,
  is_georeferenced: asBool,
};

/**
 * Project a request body onto the writable columns. Absent keys stay absent so
 * a PATCH never clobbers a column the caller did not mention.
 */
export function pickMapFields(body: Record<string, unknown>): MapWrite {
  const out: Record<string, unknown> = {};
  for (const [field, coerce] of Object.entries(MAP_WRITABLE_FIELDS)) {
    if (body?.[field] === undefined) continue;
    const value = coerce(body[field]);
    if (value === undefined) continue;
    out[field] = value;
  }
  // The allow-list above is the type check; the keys are all real columns.
  return out as MapWrite;
}
