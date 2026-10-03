-- Distinguish bibliographic printings from institution catalogue items and
-- from map processing workspaces. Existing rows stay unresolved until reviewed.
create table if not exists public.sheet_printings (
  id uuid primary key default gen_random_uuid(),
  cell_id uuid not null references public.series_cells(id) on delete restrict,
  printed_title text,
  edition_statement text,
  edition_label text,
  issuing_agency text,
  content_year smallint,
  edition_year smallint,
  printing_year smallint,
  printing_month smallint check (printing_month is null or printing_month between 1 and 12),
  printer text,
  printing_statement text,
  part text check (part is null or part in ('whole','W','E','assemblage')),
  evidence jsonb not null default '{}'::jsonb check (jsonb_typeof(evidence)='object'),
  review_status text not null default 'unreviewed' check (review_status in ('unreviewed','verified','uncertain')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.sheet_printings drop constraint if exists sheet_printings_verified_has_evidence;
alter table public.sheet_printings add constraint sheet_printings_verified_has_evidence
  check(review_status<>'verified' or evidence<>'{}'::jsonb);
comment on table public.sheet_printings is 'Reviewed bibliographic identity for one printing of a survey cell. No uniqueness by year/edition: identity requires evidence, not a guessed composite key.';
comment on column public.sheet_printings.evidence is 'Evidence and review references supporting this printing identity; empty object means no evidence has been attached. A schema row alone is not evidence of a real printing.';
comment on column public.sheet_printings.review_status is 'unreviewed = assertion not checked; verified = evidence reviewed; uncertain = retained ambiguity. No existing printing identities are backfilled.';
comment on column public.sheet_printings.edition_statement is 'Verbatim edition wording from the printed sheet or a cited catalogue.';
comment on column public.sheet_printings.printing_statement is 'Verbatim printing/revision wording; do not infer it from year fields.';
alter table public.sheet_printings enable row level security;
drop policy if exists sheet_printings_read on public.sheet_printings;
create policy sheet_printings_read on public.sheet_printings for select
  using (review_status='verified' or (select auth.uid()) is not null);
drop policy if exists sheet_printings_staff_write on public.sheet_printings;
create policy sheet_printings_staff_write on public.sheet_printings for all
  using (exists(select 1 from public.profiles p where p.id=(select auth.uid()) and p.role in ('admin','mod')))
  with check (exists(select 1 from public.profiles p where p.id=(select auth.uid()) and p.role in ('admin','mod')));
grant select on public.sheet_printings to anon,authenticated,service_role;
grant insert,update,delete on public.sheet_printings to authenticated,service_role;
create or replace function public.sheet_printings_set_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at=now(); return new; end $$;
drop trigger if exists sheet_printings_updated_at on public.sheet_printings;
create trigger sheet_printings_updated_at before update on public.sheet_printings
for each row execute function public.sheet_printings_set_updated_at();

alter table public.maps add column if not exists printing_id uuid;
alter table public.cell_printings add column if not exists printing_id uuid;
alter table public.map_images add column if not exists source_item_id uuid;
alter table public.map_images add column if not exists width integer check(width is null or width>0);
alter table public.map_images add column if not exists height integer check(height is null or height>0);
alter table public.map_images add column if not exists content_sha256 text check(content_sha256 is null or content_sha256 ~ '^[0-9a-fA-F]{64}$');
alter table public.map_images add column if not exists asset_version uuid;
alter table public.maps drop constraint if exists maps_printing_id_fkey;
alter table public.maps add constraint maps_printing_id_fkey foreign key(printing_id) references public.sheet_printings(id) on delete set null;
alter table public.cell_printings drop constraint if exists cell_printings_printing_id_fkey;
alter table public.cell_printings add constraint cell_printings_printing_id_fkey foreign key(printing_id) references public.sheet_printings(id) on delete set null;
alter table public.map_images drop constraint if exists map_images_source_item_id_fkey;
alter table public.map_images add constraint map_images_source_item_id_fkey foreign key(source_item_id) references public.cell_printings(id) on delete set null;
create index if not exists maps_printing_id_idx on public.maps(printing_id) where printing_id is not null;
create index if not exists cell_printings_printing_id_idx on public.cell_printings(printing_id) where printing_id is not null;
create index if not exists map_images_source_item_id_idx on public.map_images(source_item_id) where source_item_id is not null;
comment on column public.maps.printing_id is 'Reviewed printing served by this map workspace; null while identity is unresolved.';
comment on column public.cell_printings.printing_id is 'Reviewed printing represented by this institution catalogue item; null for unresolved or out-of-index discoveries.';
comment on column public.map_images.source_item_id is 'Institution catalogue item that supplies this image, when known; independent of the map workspace.';
comment on column public.map_images.width is 'Pixel width for this image asset when confirmed; null means unknown, not zero.';
comment on column public.map_images.height is 'Pixel height for this image asset when confirmed; null means unknown, not zero.';
comment on column public.map_images.content_sha256 is 'SHA-256 of image content when measured; distinguishes changed pixels from a URL/hosting move.';
comment on column public.map_images.asset_version is 'Opaque UUID identity of this image asset version; rotate when its pixel coordinate frame changes.';

-- Keep resolved map and source-item links on the same indexed cell, series and
-- printing. Null links remain legal for discoveries and legacy rows.
create or replace function public.assert_catalog_link_consistency()
returns trigger language plpgsql set search_path=public as $$
declare
  v_cell public.series_cells%rowtype;
  v_printing public.sheet_printings%rowtype;
  v_item public.cell_printings%rowtype;
  v_map public.maps%rowtype;
  v_series_id uuid;
begin
  if tg_table_name='sheet_printings' then
    if tg_op='UPDATE' and new.cell_id is distinct from old.cell_id then
      if exists(select 1 from public.maps where printing_id=new.id) or exists(select 1 from public.cell_printings where printing_id=new.id) then
        raise exception 'cannot move a printing to another cell while resolved links exist';
      end if;
    end if;
    if tg_op='UPDATE' and new.review_status is distinct from old.review_status and new.review_status<>'verified'
      and exists(select 1 from public.maps d left join public.maps survivor on survivor.id=d.duplicate_of_map_id
        where d.duplicate_of_map_id is not null and (d.printing_id=new.id or survivor.printing_id=new.id)) then
      raise exception 'cannot unverify a printing used by an archived duplicate link';
    end if;
    return new;
  elsif tg_table_name='series_cells' then
    if tg_op='UPDATE' and (new.id is distinct from old.id or new.series_id is distinct from old.series_id
        or new.sheet_number is distinct from old.sheet_number)
      and exists(select 1 from public.sheet_printings p where p.cell_id=old.id) then
      raise exception 'cannot move a series cell while printing identities are attached';
    end if;
    return new;
  elsif tg_table_name='maps' then
    if new.printing_id is not null then
      select * into v_printing from public.sheet_printings where id=new.printing_id;
      select * into v_cell from public.series_cells where id=v_printing.cell_id;
      v_series_id := coalesce(new.series_id,(select id from public.series where key=new.series_key));
      if v_series_id is not null and v_series_id is distinct from v_cell.series_id then
        raise exception 'map series_id must match its printing cell';
      end if;
      if new.sheet_number is not null and new.sheet_number is distinct from v_cell.sheet_number then
        raise exception 'map sheet_number must match its printing cell';
      end if;
    end if;
    if exists(select 1 from public.map_images mi join public.cell_printings ci on ci.id=mi.source_item_id
      where mi.map_id=new.id and ((new.series_id is not null and ci.series_id is not null and new.series_id<>ci.series_id)
        or (new.sheet_number is not null and ci.sheet_number is not null and new.sheet_number<>ci.sheet_number)
        or (new.printing_id is not null and ci.printing_id is not null and new.printing_id<>ci.printing_id))) then
      raise exception 'existing image source item conflicts with map cell or printing';
    end if;
    return new;
  elsif tg_table_name='cell_printings' then
    if new.printing_id is not null then
      select * into v_printing from public.sheet_printings where id=new.printing_id;
      select * into v_cell from public.series_cells where id=v_printing.cell_id;
      v_series_id := coalesce(new.series_id,(select id from public.series where key=new.series_key));
      if v_series_id is not null and v_series_id is distinct from v_cell.series_id then
        raise exception 'source item series_id must match its printing cell';
      end if;
      if new.sheet_number is not null and new.sheet_number is distinct from v_cell.sheet_number then
        raise exception 'source item sheet_number must match its printing cell';
      end if;
    end if;
    if exists(select 1 from public.map_images mi join public.maps m on m.id=mi.map_id
      where mi.source_item_id=new.id and ((m.series_id is not null and new.series_id is not null and m.series_id<>new.series_id)
        or (m.sheet_number is not null and new.sheet_number is not null and m.sheet_number<>new.sheet_number)
        or (m.printing_id is not null and new.printing_id is not null and m.printing_id<>new.printing_id))) then
      raise exception 'source item update conflicts with linked map';
    end if;
    return new;
  elsif tg_table_name='map_images' and new.source_item_id is not null then
    select * into v_item from public.cell_printings where id=new.source_item_id;
    if new.map_id is not null then
      select * into v_map from public.maps where id=new.map_id;
      if v_map.series_id is not null and v_item.series_id is not null and v_map.series_id is distinct from v_item.series_id then
        raise exception 'image source item series must match map series';
      end if;
      if v_map.sheet_number is not null and v_item.sheet_number is not null and v_map.sheet_number is distinct from v_item.sheet_number then
        raise exception 'image source item cell must match map cell';
      end if;
      if v_map.printing_id is not null and v_item.printing_id is not null and v_map.printing_id is distinct from v_item.printing_id then
        raise exception 'image source item printing must match map printing';
      end if;
    end if;
    return new;
  end if;
  return new;
end;
$$;
drop trigger if exists maps_catalog_link_consistency on public.maps;
drop trigger if exists zz_maps_catalog_link_consistency on public.maps;
create trigger zz_maps_catalog_link_consistency before insert or update of series_id,series_key,sheet_number,printing_id on public.maps
for each row execute function public.assert_catalog_link_consistency();
drop trigger if exists cell_printings_catalog_link_consistency on public.cell_printings;
drop trigger if exists zz_cell_printings_catalog_link_consistency on public.cell_printings;
create trigger zz_cell_printings_catalog_link_consistency before insert or update of series_id,series_key,sheet_number,printing_id on public.cell_printings
for each row execute function public.assert_catalog_link_consistency();
drop trigger if exists map_images_catalog_link_consistency on public.map_images;
create trigger map_images_catalog_link_consistency before insert or update of map_id,source_item_id on public.map_images
for each row execute function public.assert_catalog_link_consistency();
drop trigger if exists sheet_printings_catalog_link_consistency on public.sheet_printings;
create trigger sheet_printings_catalog_link_consistency before update of cell_id,review_status on public.sheet_printings
for each row execute function public.assert_catalog_link_consistency();
drop trigger if exists zz_series_cells_catalog_link_consistency on public.series_cells;
create trigger zz_series_cells_catalog_link_consistency before update of id,series_id,sheet_number on public.series_cells
for each row execute function public.assert_catalog_link_consistency();
comment on function public.assert_catalog_link_consistency() is 'Rejects contradictory resolved series/cell/printing/source-item links. Unresolved nullable relationships and source discoveries remain valid.';

-- These relationship and asset-identity fields are curated facts. The broad
-- own-draft map update policy must not let contributors assign catalog UUIDs.
create or replace function public.guard_catalog_identity_writes()
returns trigger language plpgsql security definer set search_path='' as $$
declare v_staff boolean := false; v_changed boolean := false;
begin
  if (select auth.role())='service_role' then return new; end if;
  select exists(select 1 from public.profiles p where p.id=(select auth.uid()) and p.role in ('admin','mod')) into v_staff;
  if v_staff then return new; end if;
  if tg_table_name='maps' then
    v_changed := (tg_op='INSERT' and (new.series_id is not null or new.printing_id is not null))
      or (tg_op='UPDATE' and (new.series_id is distinct from old.series_id
        or (new.series_key is distinct from old.series_key and new.collection is not distinct from old.collection)
        or new.printing_id is distinct from old.printing_id));
  elsif tg_table_name='cell_printings' then
    v_changed := (tg_op='INSERT' and (new.series_id is not null or new.printing_id is not null))
      or (tg_op='UPDATE' and (new.series_id is distinct from old.series_id or new.series_key is distinct from old.series_key
        or new.printing_id is distinct from old.printing_id));
  elsif tg_table_name='map_images' then
    v_changed := (tg_op='INSERT' and (new.source_item_id is not null or new.width is not null or new.height is not null
      or new.content_sha256 is not null or new.asset_version is not null))
      or (tg_op='UPDATE' and (new.source_item_id is distinct from old.source_item_id or new.width is distinct from old.width
        or new.height is distinct from old.height or new.content_sha256 is distinct from old.content_sha256
        or new.asset_version is distinct from old.asset_version));
  elsif tg_table_name='series_cells' then
    v_changed := (tg_op='INSERT' and new.series_id is not null)
      or (tg_op='UPDATE' and (new.series_id is distinct from old.series_id or new.series_key is distinct from old.series_key));
  end if;
  if v_changed then raise exception 'catalog identity and asset links are staff-controlled'; end if;
  return new;
end;
$$;
drop trigger if exists maps_guard_catalog_identity on public.maps;
create trigger maps_guard_catalog_identity after insert or update of series_id,series_key,collection,printing_id on public.maps
for each row execute function public.guard_catalog_identity_writes();
drop trigger if exists cell_printings_guard_catalog_identity on public.cell_printings;
create trigger cell_printings_guard_catalog_identity after insert or update of series_id,series_key,printing_id on public.cell_printings
for each row execute function public.guard_catalog_identity_writes();
drop trigger if exists map_images_guard_catalog_identity on public.map_images;
create trigger map_images_guard_catalog_identity after insert or update of source_item_id,width,height,content_sha256,asset_version on public.map_images
for each row execute function public.guard_catalog_identity_writes();
drop trigger if exists series_cells_guard_catalog_identity on public.series_cells;
create trigger series_cells_guard_catalog_identity after insert or update of series_id,series_key on public.series_cells
for each row execute function public.guard_catalog_identity_writes();
revoke all on function public.guard_catalog_identity_writes() from public,anon,authenticated;
grant execute on function public.guard_catalog_identity_writes() to service_role;
comment on function public.guard_catalog_identity_writes() is 'Stops ordinary contributors bypassing the staff API to assign series, printing, institution-item or image asset identities. Service-role imports remain possible.';

-- Derived availability keeps institution rows and served maps separate. Every
-- count is by distinct printing identity, and the gate is explicit for service clients.
create or replace view public.series_printing_availability with (security_invoker=true) as
select s.id as series_id,s.key,s.name,
 count(distinct p.id) filter(where p.review_status='verified' or auth.uid() is not null) as printing_count,
 count(distinct p.id) filter(where (p.review_status='verified' or auth.uid() is not null)
   and exists(select 1 from public.cell_printings ci where ci.printing_id=p.id)) as item_linked_printing_count,
 coalesce(max(items.known_item_count),0) as known_item_count,
 count(distinct p.id) filter(where p.review_status='verified'
   and exists(select 1 from public.maps m where m.printing_id=p.id and m.status in ('public','featured'))) as publicly_served_printing_count
from public.series s join public.series_cells c on c.series_id=s.id
left join public.sheet_printings p on p.cell_id=c.id
left join (select series_id,count(distinct id) as known_item_count from public.cell_printings group by series_id) items on items.series_id=s.id
where auth.uid() is not null or exists(select 1 from public.maps m where m.series_id=s.id and m.status in ('public','featured'))
group by s.id,s.key,s.name;
comment on view public.series_printing_availability is 'Printing availability by stable series. Institution items, public availability and public served scans are separate counts; anonymous/service calls require public evidence.';
grant select on public.series_printing_availability to anon,authenticated,service_role;
