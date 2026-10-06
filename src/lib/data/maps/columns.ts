/**
 * The `maps` columns every list of maps reads, under their own names.
 *
 * `LIST_COLUMNS` (service.ts), the search API's full set and its slim set were three hand-kept
 * strings that drifted: `slug` was missing from one until a link 404'd. Each now spreads this and
 * adds only what it alone needs. A column every list wants goes here.
 */
export const MAP_BASE_COLUMNS =
  'id,slug,name,location,region,regions,regions_2025,map_type,map_subjects,depicted_state,classification_status,thumbnail,year,collection,series_key,source_type,status,bbox,iiif_image,allmaps_id,annotation_url,holding_institution,source_url';
