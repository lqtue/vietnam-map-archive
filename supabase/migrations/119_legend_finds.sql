-- Migration 119 — the search that found a legend entry's place today
--
-- A staff editor placing a numbered legend entry on the map (the Legend tab's
-- editor, SheetLegendPanel) often finds the spot by searching OpenStreetMap
-- first: "Bệnh viện Grall" turns up today's Nhi Đồng 2, and the printed number
-- is clicked beside it. That pairing — what the sheet called a place, what a
-- person typed to find it, and which modern feature it turned out to be — is
-- ground truth the gazetteer has nowhere else (`attested-variants`,
-- `gazetteer-guided-ocr` in docs/ROADMAP.md). One row per entry per save that
-- placed its point after a Find pick; nothing is overwritten, so a later
-- correction is a second row and the newest is current.
--
-- * query     what was typed, as typed — the old or new name the editor tried.
-- * osm_*     the Nominatim result picked: its OSM object and display name, and
--             where it sits. The entry's own point stays in ocr_labels.notes
--             (`px=`, image pixels); this is where the *search* landed.
--
-- Staff-only: written and read with the service role by
-- /api/admin/maps/[id]/legend-points. No anon/authenticated access until a page
-- needs one.

create table if not exists public.legend_finds (
  id         uuid primary key default gen_random_uuid(),
  label_id   uuid not null references public.ocr_labels(id) on delete cascade,
  map_id     uuid not null references public.maps(id) on delete cascade,
  query      text not null check (length(query) between 1 and 500),
  osm_type   text check (osm_type in ('node', 'way', 'relation')),
  osm_id     bigint check (osm_id > 0),
  osm_name   text check (length(osm_name) <= 1000),
  osm_lng    double precision check (osm_lng between -180 and 180),
  osm_lat    double precision check (osm_lat between -90 and 90),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  check ((osm_type is null) = (osm_id is null))
);

create index if not exists legend_finds_label_id_idx on public.legend_finds (label_id, created_at desc);
create index if not exists legend_finds_map_id_idx on public.legend_finds (map_id);

comment on table public.legend_finds is
  'The place search that led a staff editor to a legend entry''s point: the text typed and the OSM result picked. Append-only, newest per label_id is current. Migration 119.';
comment on column public.legend_finds.query is
  'The search as typed — an old or a modern name.';
comment on column public.legend_finds.osm_name is
  'Nominatim display_name of the picked result, at the time of the search.';

alter table public.legend_finds enable row level security;
revoke all on public.legend_finds from anon, authenticated;
