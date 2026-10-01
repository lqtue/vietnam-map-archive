-- Migration 103 — the georeference as a database object
--
-- Until now a georeference existed only as a file: `annotations/<map>.json` for
-- the live one, `annotations/<map>/<stamp>.json` for history. The database saw
-- two copies of it, `geom_src` and `geom_rmse`, stamped onto every derived label
-- and polygon. So "which version is live, and which rows were warped against an
-- older one" could only be answered by downloading and hashing JSON. On
-- 2026-10-01 that was how five maps' stale geometry was found, and how the 1942
-- control point that a script removed and an Allmaps sync put back was found.
--
-- One row per stored version, i.e. per history file: `stamp` is the file's key,
-- so `GET /api/maps/<id>/annotation?version=<stamp>` serves the row's JSON.
-- Plan: docs/knowledge-system-plan.md §5 (`georef-versions`).
--
-- Decisions (the first three changed the plan's first draft):
--
-- * No "current version" pointer on `maps`. The live version is the newest
--   stamp, and `map_georef_current` derives it. A pointer would be one more
--   snapshot nothing maintains (`held-by-derived` is that bug on series_cells).
-- * No `image_id` foreign key. `map_images` rows are rewritten in place
--   (`upsertR2Source` repoints the R2 row), so a uuid there does not pin which
--   pixels the GCPs were placed on. The annotation's own `source_id` plus its
--   declared width and height do, and that is what the size check compares.
-- * `origin` says who placed the points: `allmaps` (pulled from the editor),
--   `neatline` (the four-corner PATCH), `script`, `pipeline`, or `mirror` (an
--   existing version re-stored: a re-mirror that rewrites the image source, or
--   the PATCH's snapshot of what it replaces — same points as the row before
--   it, when there is one). A row is a stored file, not a change: a listing
--   that wants changes collapses consecutive rows with equal `geom_src`.
--   It includes `script` and `unrecorded` on purpose. The 1942 regression was
--   script → Allmaps sync → script; without `script` the table cannot show it.
--   `unrecorded` is for versions found in storage that no recording writer
--   wrote (the backfill, and the Python pipeline until it records its own).
-- * `geom_src` is computed in TypeScript (`$lib/core/georef/version.ts`), the
--   same function that stamps labels and polygons, never re-implemented here.
--
-- Append-only: no `updated_at`. Writers use the service key; there is no
-- insert policy, so RLS refuses every other role.

create table if not exists public.georef_versions (
  id             uuid primary key default gen_random_uuid(),
  map_id         uuid not null references public.maps(id) on delete cascade,
  stamp          text not null check (stamp ~ '^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z$'),
  geom_src       text not null,
  transformation text not null check (transformation in (
                   'straight', 'helmert', 'polynomial', 'polynomial1', 'polynomial2',
                   'polynomial3', 'projective', 'thinPlateSpline')),
  gcp_count      integer not null check (gcp_count >= 0),
  rmse_m         real,
  rmse_method    text not null,
  source_id      text,
  source_width   integer,
  source_height  integer,
  origin         text not null check (origin in (
                   'allmaps', 'mirror', 'neatline', 'script', 'pipeline', 'unrecorded')),
  allmaps_id     text,
  user_id        uuid references auth.users(id) on delete set null,
  created_at     timestamptz not null default now(),
  unique (map_id, stamp)
);

comment on table public.georef_versions is
  'One row per stored georeference version (annotations/<map_id>/<stamp>.json). Live = newest stamp; see map_georef_current. Migration 103.';
comment on column public.georef_versions.geom_src is
  'gcpSrcHash of the GCP set ($lib/core/georef/version.ts). A label or polygon whose geom_src differs from its map''s current one was warped against an older version.';
comment on column public.georef_versions.rmse_method is
  'Names the RMSE measure (evidence-chain invariant 8). gcp-roundtrip-rms reads ~0 for a thin-plate spline by construction.';
comment on column public.georef_versions.allmaps_id is
  'The Allmaps image id the version was pulled from, when origin = allmaps. maps.allmaps_id can change after a rescan; this does not.';

alter table public.georef_versions enable row level security;

-- Same visibility as map_images (mig 101): published, the map's creator, or staff.
drop policy if exists "georef_versions_select_visible_parent" on public.georef_versions;
create policy "georef_versions_select_visible_parent" on public.georef_versions for select
  using (
    exists (
      select 1 from public.maps m
       where m.id = georef_versions.map_id
         and (
           m.status in ('public', 'featured')
           or m.created_by = (select auth.uid())
           or exists (
             select 1 from public.profiles p
              where p.id = (select auth.uid()) and p.role in ('admin', 'mod')
           )
         )
    )
  );

-- The live version per map. Stamps are fixed-width ISO, so text order is time order.
create or replace view public.map_georef_current
  with (security_invoker = true) as
select distinct on (map_id) *
  from public.georef_versions
 order by map_id, stamp desc;
