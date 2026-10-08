-- Migration 118 — how a georeference was made, from what, and whether a person looked
--
-- `georef_versions` (mig 103) says *who* placed the points (`origin`: script,
-- allmaps, neatline ...) but not how, so "made by VMA from the printed grid" and
-- "copied from Allmaps" and "derived from the PCL GeoPDF" were the same row. These
-- columns are the provenance a researcher follows back from a sheet to the holder's
-- record of the scan; the holder itself stays in `maps.source_url` and
-- `holding_institution`.
--
-- All nullable: the rows already stored (and every Allmaps pull) predate them.
-- `scripts/georef_write.mjs` refuses to store a new version without `method`.
--
-- * method          what anchored the placement.
-- * method_ref      the script that made it, `scripts/vn1971/place.py@abc1234`.
-- * datum           the transform applied to the printed coordinates, or `none`.
-- * derived_from    URL of an upstream georef this one copies or derives from
--                   (the USGS GeoPDF, or annotations.allmaps.org/maps/<id>).
-- * allmaps_map_id  the Allmaps *map* id (not the image id in `allmaps_id`) once this
--                   version has been pushed to live.allmaps.org.
-- * review          the outcome of a person's look: auto-pass, sampled-ok, flagged-fixed.
--
-- Append-only still holds for the placement: the GCPs, transformation and `geom_src`
-- of a row never change. `allmaps_map_id` and `review` are the two facts that only
-- exist *after* the row does (the push result, a human verdict), so the service-role
-- writers set them once, in place; nothing else is updated.
--
-- `series.dataset_doi` is the Zenodo concept DOI of a series' dataset (one per series).
-- The table, not the `map_series` view, so the view's definition (mig 117) is untouched;
-- exposing it on the series page is the dataset-package session's job.

alter table public.georef_versions
  add column if not exists method         text check (method in (
    'utm-grid', 'printed-corners', 'catalogue+calibration', 'geopdf', 'hand', 'allmaps-editor')),
  add column if not exists method_ref     text,
  add column if not exists datum          text,
  add column if not exists derived_from   text,
  add column if not exists allmaps_map_id text,
  add column if not exists review         text check (review in (
    'auto-pass', 'sampled-ok', 'flagged-fixed'));

comment on column public.georef_versions.method is
  'What anchored the placement: utm-grid, printed-corners, catalogue+calibration, geopdf, hand, allmaps-editor. Null on versions stored before migration 118.';
comment on column public.georef_versions.method_ref is
  'The script that made the version and its git short sha, e.g. scripts/vn1971/place.py@abc1234.';
comment on column public.georef_versions.datum is
  'The datum transform applied to the printed coordinates (e.g. Indian1960 towgs84=198,881,317), or none.';
comment on column public.georef_versions.derived_from is
  'URL of an upstream georeference this one copies or derives from (a GeoPDF URL, or annotations.allmaps.org/maps/<id>).';
comment on column public.georef_versions.allmaps_map_id is
  'The Allmaps map id (live.allmaps.org/maps/<id>) this version was pushed as. Set after the push; allmaps_id is the image id and means something else.';
comment on column public.georef_versions.review is
  'A person''s verdict on the version. Set after the row is written.';

alter table public.series
  add column if not exists dataset_doi text check (dataset_doi is null or dataset_doi ~ '^10\.\d{4,9}/\S+$');

comment on column public.series.dataset_doi is
  'Concept DOI of the series'' published dataset (Zenodo). One per series; a re-version keeps the concept DOI.';
