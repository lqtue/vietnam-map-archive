\set ON_ERROR_STOP on
-- Disposable local fixture, transaction rolls back all schema and seeded rows.
begin;
-- The guarded runner permits only the dedicated local fixture database.
drop schema public cascade;
create schema public;
create extension if not exists unaccent with schema public;
create or replace function public.f_unaccent(text) returns text language sql immutable as $$ select public.unaccent($1) $$;
do $$ begin
 if not exists(select 1 from pg_roles where rolname='anon') then create role anon; end if;
 if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
 if not exists(select 1 from pg_roles where rolname='service_role') then create role service_role; end if;
end $$;
create table public.maps (
 id uuid primary key, name text, year integer, status text, is_georeferenced boolean,
 regions text[], regions_2025 text[], region text, original_title text, creator text, publisher text,
 holding_institution text, collection text, location text, shelfmark text, date_label text,
 sheet_number text, sheet_half text, series_key text, map_type text, bbox float8[],
 annotation_url text, allmaps_id text, extra_metadata jsonb
);
\ir ../../supabase/migrations/126_explore_maps_page.sql
