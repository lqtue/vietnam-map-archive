-- Migration 038 changed the accepted statuses but left 026's obsolete default.
-- Omitted status must create a valid draft without changing historical rows.
alter table public.maps alter column status set default 'draft';
comment on column public.maps.status is
  'Publication/archive lifecycle: draft workspace; public/featured anonymous visibility; archived retained for provenance. Default is draft.';
