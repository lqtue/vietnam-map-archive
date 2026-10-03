-- Stable series identities. collection remains a display label; membership
-- follows the FK and survives label edits.
create table if not exists public.series (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  name text not null,
  code text,
  scale_denominator integer check (scale_denominator is null or scale_denominator > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
comment on table public.series is 'Stable survey identities. key is durable; name is a mutable display label. Code and scale are optional curated metadata.';
alter table public.series enable row level security;
drop policy if exists series_read on public.series;
create policy series_read on public.series for select using (true);
drop policy if exists series_staff_write on public.series;
create policy series_staff_write on public.series for all
  using (exists(select 1 from public.profiles p where p.id=(select auth.uid()) and p.role in ('admin','mod')))
  with check (exists(select 1 from public.profiles p where p.id=(select auth.uid()) and p.role in ('admin','mod')));
grant select on public.series to anon, authenticated, service_role;
grant insert,update,delete on public.series to authenticated,service_role;
create or replace function public.series_set_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at=now(); return new; end $$;
drop trigger if exists series_updated_at on public.series;
create trigger series_updated_at before update on public.series for each row execute function public.series_set_updated_at();
create or replace function public.guard_series_key_immutable()
returns trigger language plpgsql as $$
begin
  if new.key is distinct from old.key then raise exception 'series key is immutable'; end if;
  return new;
end;
$$;
drop trigger if exists series_key_immutable on public.series;
create trigger series_key_immutable before update of key on public.series
for each row execute function public.guard_series_key_immutable();
comment on column public.series.key is 'Stable route/data key. Immutable after creation; edit name for display changes.';

-- Include keys present only in the index or source-item catalogue. No printing
-- identities are inferred by this migration.
insert into public.series(key,name)
select k.key, coalesce(min(nullif(btrim(m.collection),'')),k.key)
from (select series_key as key from public.maps where series_key is not null
      union select series_key from public.series_cells
      union select series_key from public.cell_printings) k
left join public.maps m on m.series_key=k.key
group by k.key on conflict(key) do nothing;

alter table public.series_cells add column if not exists id uuid default gen_random_uuid();
alter table public.series_cells add column if not exists series_id uuid;
alter table public.maps add column if not exists series_id uuid;
alter table public.cell_printings add column if not exists series_id uuid;
update public.series_cells c set series_id=s.id from public.series s where s.key=c.series_key and c.series_id is null;
update public.maps m set series_id=s.id from public.series s where s.key=m.series_key and m.series_id is null;
update public.cell_printings p set series_id=s.id from public.series s where s.key=p.series_key and p.series_id is null;
alter table public.series_cells alter column id set not null;
alter table public.series_cells alter column series_id set not null;
alter table public.cell_printings alter column series_id set not null;
alter table public.series_cells drop constraint if exists series_cells_id_key;
alter table public.series_cells add constraint series_cells_id_key unique(id);
alter table public.series_cells drop constraint if exists series_cells_series_id_fkey;
alter table public.series_cells add constraint series_cells_series_id_fkey foreign key(series_id) references public.series(id) on delete restrict;
alter table public.series_cells drop constraint if exists series_cells_series_sheet_key;
alter table public.series_cells add constraint series_cells_series_sheet_key unique(series_id,sheet_number);
alter table public.maps drop constraint if exists maps_series_id_fkey;
alter table public.maps add constraint maps_series_id_fkey foreign key(series_id) references public.series(id) on delete set null;
alter table public.cell_printings drop constraint if exists cell_printings_series_id_fkey;
alter table public.cell_printings add constraint cell_printings_series_id_fkey foreign key(series_id) references public.series(id) on delete restrict;
create index if not exists maps_series_id_sheet_number_idx on public.maps(series_id,sheet_number);
create index if not exists cell_printings_series_id_sheet_number_idx on public.cell_printings(series_id,sheet_number);
comment on column public.series_cells.id is 'Stable UUID identity for this survey cell; the legacy composite primary key remains for compatibility.';
comment on column public.series_cells.series_id is 'Stable survey identity. series_key is a compatibility copy synchronized from this FK.';
comment on column public.maps.series_id is 'Stable survey membership. Editing maps.collection changes display text only and cannot re-file this map.';
comment on column public.cell_printings.series_id is 'Stable survey membership for this institution item; series_key remains for legacy readers.';

create or replace function public.sync_series_identity_keys()
returns trigger language plpgsql set search_path=public as $$
begin
  if tg_table_name='maps' then
    if tg_op='UPDATE' and new.series_id is distinct from old.series_id then
      new.series_key := (select key from public.series where id=new.series_id);
      return new;
    elsif tg_op='UPDATE' and new.series_key is distinct from old.series_key then
      select id into new.series_id from public.series where key=new.series_key;
      if new.series_id is not null then new.series_key := (select key from public.series where id=new.series_id); end if;
      return new;
    elsif tg_op='UPDATE' and new.collection is distinct from old.collection and new.series_id is null then
      new.series_key := public.series_key(new.collection);
      select id into new.series_id from public.series where key=new.series_key;
      return new;
    elsif tg_op='INSERT' and new.series_id is null and new.series_key is not null then
      select id into new.series_id from public.series where key=new.series_key;
    elsif tg_op='INSERT' and new.series_id is null and new.collection is not null then
      new.series_key := public.series_key(new.collection);
      select id into new.series_id from public.series where key=new.series_key;
    end if;
  else
    if tg_op='UPDATE' and new.series_id is distinct from old.series_id then
      new.series_key := (select key from public.series where id=new.series_id);
      return new;
    elsif tg_op='UPDATE' and new.series_key is distinct from old.series_key then
      select id into new.series_id from public.series where key=new.series_key;
      if new.series_id is not null then new.series_key := (select key from public.series where id=new.series_id); end if;
      return new;
    elsif new.series_id is null and new.series_key is not null then
      select id into new.series_id from public.series where key=new.series_key;
    end if;
  end if;
  if new.series_id is not null then new.series_key := (select key from public.series where id=new.series_id); end if;
  return new;
end;
$$;
drop trigger if exists maps_sync_series_identity on public.maps;
create trigger maps_sync_series_identity before insert or update of series_id,series_key,collection on public.maps
for each row execute function public.sync_series_identity_keys();
drop trigger if exists series_cells_sync_series_identity on public.series_cells;
create trigger series_cells_sync_series_identity before insert or update of series_id,series_key on public.series_cells
for each row execute function public.sync_series_identity_keys();
drop trigger if exists cell_printings_sync_series_identity on public.cell_printings;
create trigger cell_printings_sync_series_identity before insert or update of series_id,series_key on public.cell_printings
for each row execute function public.sync_series_identity_keys();
comment on function public.sync_series_identity_keys() is 'Keeps legacy series_key columns synchronized from stable series_id. A collection-only rename never changes an existing maps.series_id; explicit null series_id clears the compatibility key. Unknown legacy keys may remain unlinked until curated.';

-- Remove only the generated expression; retain maps.series_key and its indexes
-- for existing readers. map_series is rebuilt with its original columns.
drop view if exists public.map_series;
alter table public.maps alter column series_key drop expression;
comment on column public.maps.series_key is 'Legacy key retained for existing readers; synchronized from series_id. Do not use as identity.';
create or replace view public.map_series with (security_invoker=true) as
with idx as (select series_id,count(*) as survey_sheets from public.series_cells group by series_id)
select s.key as key,min(m.collection) as collection,s.name as name,
 count(distinct m.sheet_number) as sheets,
 count(distinct m.sheet_number) filter(where m.status in ('public','featured')) as published_sheets,
 i.survey_sheets,min(m.year) as first_year,max(m.year) as last_year,
 array[min(m.bbox[1]),min(m.bbox[2]),max(m.bbox[3]),max(m.bbox[4])]::float8[] as bounds
from public.maps m join public.series s on s.id=m.series_id
left join idx i on i.series_id=s.id
where (m.status in ('public','featured') or auth.uid() is not null)
 and m.is_georeferenced and m.bbox is not null and array_length(m.bbox,1)=4 and m.sheet_number is not null
 and m.status<>'archived'
group by s.id,s.key,s.name,i.survey_sheets having count(distinct m.sheet_number)>1;
comment on view public.map_series is 'One row per stable series with georeferenced map sheets. Preserves legacy columns and explicit published-or-signed-in gate, including service-role callers.';
grant select on public.map_series to anon,authenticated,service_role;

create or replace view public.series_cell_coverage with (security_invoker=true) as
select s.id as series_id,s.key,s.name,count(distinct c.id) as cell_count,
 count(distinct c.id) filter(where exists(select 1 from public.maps m where m.series_id=s.id and m.sheet_number=c.sheet_number and m.status in ('public','featured'))) as publicly_held_cell_count,
 count(distinct c.id) filter(where exists(select 1 from public.maps m where m.series_id=s.id and m.sheet_number=c.sheet_number
   and (m.status in ('public','featured') or (auth.uid() is not null and m.status='draft')))) as held_cell_count
from public.series s join public.series_cells c on c.series_id=s.id
where auth.uid() is not null or exists(select 1 from public.maps m where m.series_id=s.id and m.status in ('public','featured'))
group by s.id,s.key,s.name;
comment on view public.series_cell_coverage is 'Distinct-cell coverage. Anonymous callers count only public/featured maps; signed-in callers may see draft availability. Explicit gate protects service-role queries.';
grant select on public.series_cell_coverage to anon,authenticated,service_role;

create or replace view public.series_cell_coverage_detail with (security_invoker=true) as
select s.id as series_id,s.key,c.sheet_number,
 exists(select 1 from public.maps m where m.series_id=s.id and m.sheet_number=c.sheet_number and m.status in ('public','featured')) as publicly_held,
 exists(select 1 from public.maps m where m.series_id=s.id and m.sheet_number=c.sheet_number
   and (m.status in ('public','featured') or (auth.uid() is not null and m.status='draft'))) as held,
 (select m.id from public.maps m where m.series_id=s.id and m.sheet_number=c.sheet_number and m.status in ('public','featured')
   order by (m.status='featured') desc,m.id limit 1) as public_map_id,
 (nullif(btrim(c.source),'') is not null or exists(select 1 from public.cell_printings ci
   where ci.series_id=s.id and ci.sheet_number=c.sheet_number and nullif(btrim(ci.url),'') is not null)) as known_source
from public.series s join public.series_cells c on c.series_id=s.id
where (auth.uid() is not null or exists(select 1 from public.maps m where m.series_id=s.id and m.status in ('public','featured')));
comment on view public.series_cell_coverage_detail is 'One row per indexed cell with served-map availability and preferred public map id derived from non-archived maps; known_source means a nonblank legacy cell source reference or a matching institution item with a digitized-copy URL. A catalogue item URL null alone is not availability evidence. Does not trust series_cells.held_by/map_id snapshots, so legacy raster-layer holdings without a normalized source-item/map link are not counted until such a relation exists; public/service queries are explicitly gated.';
grant select on public.series_cell_coverage_detail to anon,authenticated,service_role;
