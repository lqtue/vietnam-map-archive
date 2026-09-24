/**
 * The `maps` write payload assembled by MapEditModal's Save button.
 *
 * Kept out of the component so the field list lives in one place instead of a
 * 33-line object literal inside `handleSave`, and so the trimming /
 * `label_config` parsing rules are testable on their own.
 */

/** Raw form state, straight off the tab components' `bind:value`s. */
export interface MapEditForm {
  // About
  name: string;
  original_title: string;
  year: string;
  year_label: string;
  creator: string;
  dc_publisher: string;
  location: string;
  map_type: string;
  dc_description: string;
  physical_description: string;
  language: string;
  extraPairs: { key: string; value: string }[];
  sheet_number: string;
  sheet_half: string;
  // Source
  source_type: string;
  holding_institution: string;
  collection: string;
  shelfmark: string;
  source_url: string;
  rights: string;
  // Hosting / georef
  allmaps_id: string;
  annotation_url: string;
  // Quick bar + pipeline flags. Visibility is `status` alone (mig 060).
  priority: number;
  georef_done: boolean;
  status: string;
  // Label Studio config (Pipeline tab)
  labelLegendMode: 'simple' | 'list';
  labelLegendText: string;
  labelCategories: string;
}

export interface LabelConfig {
  legend: (string | { val: string; label: string })[];
  categories: string[];
}

/** Column set PATCHed to `/api/admin/maps/[id]`. Mirrors `maps` Update. */
export interface MapEditPayload {
  name: string;
  allmaps_id: string;
  annotation_url?: string;
  location?: string;
  map_type?: string;
  year: number | null;
  description?: string;
  extra_metadata: Record<string, string>;
  source_type?: string;
  collection?: string;
  source_url?: string;
  original_title?: string;
  creator?: string;
  date_label?: string;
  language?: string;
  rights?: string;
  shelfmark?: string;
  physical_description?: string;
  publisher?: string;
  holding_institution?: string;
  sheet_number?: string;
  sheet_half?: string;
  label_config: LabelConfig;
  priority: number;
  is_georeferenced: boolean;
  status: string;
}

/** `''` → `undefined` so the API leaves the column alone rather than blanking it. */
const opt = (v: string): string | undefined => v.trim() || undefined;

/**
 * Reads the two `label_config` text inputs back into the stored JSON shape.
 * `simple` = comma-separated strings; `list` = one `value | label` pair per line.
 */
export function parseLabelConfig(
  mode: 'simple' | 'list',
  legendText: string,
  categoriesText: string
): LabelConfig {
  let legend: LabelConfig['legend'] = [];
  if (legendText.trim()) {
    legend =
      mode === 'simple'
        ? legendText
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean)
        : legendText
            .split('\n')
            .map((line) => {
              const parts = line.split('|');
              if (parts.length >= 2) return { val: parts[0].trim(), label: parts[1].trim() };
              return line.trim();
            })
            .filter(Boolean);
  }
  return {
    legend,
    categories: categoriesText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  };
}

/** Serialises the modal's form state into the PATCH body. */
export function toMapEditPayload(form: MapEditForm): MapEditPayload {
  const extra_metadata: Record<string, string> = {};
  for (const { key, value } of form.extraPairs) {
    if (key.trim()) extra_metadata[key.trim()] = value;
  }

  return {
    name: form.name.trim(),
    allmaps_id: form.allmaps_id.trim(),
    annotation_url: opt(form.annotation_url),
    location: opt(form.location),
    map_type: opt(form.map_type),
    year: form.year ? Number(form.year) : null,
    description: opt(form.dc_description),
    extra_metadata,
    source_type: opt(form.source_type),
    collection: opt(form.collection),
    source_url: opt(form.source_url),
    original_title: opt(form.original_title),
    creator: opt(form.creator),
    date_label: opt(form.year_label),
    language: opt(form.language),
    rights: opt(form.rights),
    shelfmark: opt(form.shelfmark),
    physical_description: opt(form.physical_description),
    publisher: opt(form.dc_publisher),
    holding_institution: opt(form.holding_institution),
    sheet_number: opt(form.sheet_number),
    sheet_half: opt(form.sheet_half),
    label_config: parseLabelConfig(
      form.labelLegendMode,
      form.labelLegendText,
      form.labelCategories
    ),
    priority: form.priority,
    is_georeferenced: form.georef_done,
    status: form.status,
  };
}

/** Reads the stored `label_config` JSON back into the two text inputs. */
export function labelConfigToForm(labelConfig: unknown): {
  mode: 'simple' | 'list';
  legendText: string;
  categories: string;
} {
  const cfg = (labelConfig ?? {}) as { legend?: unknown; categories?: unknown };
  const legend: unknown[] = Array.isArray(cfg.legend) ? cfg.legend : [];
  const structured = legend.length > 0 && typeof legend[0] === 'object';
  return {
    mode: structured ? 'list' : 'simple',
    legendText: structured
      ? legend
          .map((l) => {
            const entry = l as { val?: string; label?: string };
            return typeof l === 'string' ? l : `${entry.val} | ${entry.label}`;
          })
          .join('\n')
      : legend.join(', '),
    categories: Array.isArray(cfg.categories) ? cfg.categories.join(', ') : '',
  };
}
