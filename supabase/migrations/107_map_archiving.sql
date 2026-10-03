-- Archive without deleting map identity, slug, annotation, or processing history.
alter table public.maps drop constraint if exists maps_status_check;
alter table public.maps add constraint maps_status_check
  check(status in ('draft','public','featured','archived'));
alter table public.maps add column if not exists duplicate_of_map_id uuid;
alter table public.maps add column if not exists archive_reason text;
alter table public.maps drop constraint if exists maps_duplicate_of_map_id_fkey;
alter table public.maps add constraint maps_duplicate_of_map_id_fkey
  foreign key(duplicate_of_map_id) references public.maps(id) on delete restrict;
create index if not exists maps_duplicate_of_map_id_idx on public.maps(duplicate_of_map_id) where duplicate_of_map_id is not null;
alter table public.maps drop constraint if exists maps_duplicate_not_self;
alter table public.maps add constraint maps_duplicate_not_self check(duplicate_of_map_id is null or duplicate_of_map_id<>id);
alter table public.maps drop constraint if exists maps_duplicate_requires_archive;
alter table public.maps add constraint maps_duplicate_requires_archive check(duplicate_of_map_id is null or status='archived');
alter table public.maps drop constraint if exists maps_archive_reason_required;
alter table public.maps add constraint maps_archive_reason_required
  check(status<>'archived' or length(btrim(coalesce(archive_reason,'')))>0);
comment on column public.maps.status is 'Publication/archive lifecycle: draft workspace; public/featured anonymous visibility; archived retained for provenance and excluded from public catalogue reads.';
comment on column public.maps.duplicate_of_map_id is 'Optional one-hop pointer from an archived duplicate to its reviewed surviving map. Self-links and chains are rejected.';
comment on column public.maps.archive_reason is 'Staff-authored explanation for archival; preserve provenance rather than deleting a map.';

create or replace function public.guard_map_archiving()
returns trigger language plpgsql security definer set search_path='' as $$
declare v_staff boolean := false;
begin
  if (select auth.role())='service_role' then
    v_staff := true;
  else
    select exists(select 1 from public.profiles p where p.id=(select auth.uid()) and p.role in ('admin','mod')) into v_staff;
  end if;
  if not v_staff and (
    (tg_op='INSERT' and (new.status='archived' or new.duplicate_of_map_id is not null or new.archive_reason is not null)) or
    (tg_op='UPDATE' and (new.status is distinct from old.status and new.status='archived'
      or new.duplicate_of_map_id is distinct from old.duplicate_of_map_id
      or new.archive_reason is distinct from old.archive_reason))
  ) then raise exception 'map archival fields are staff-controlled'; end if;

  if new.duplicate_of_map_id is not null then
    if new.status<>'archived' then raise exception 'duplicate target is valid only on archived maps'; end if;
    if exists(select 1 from public.maps target where target.id=new.duplicate_of_map_id
      and (target.status='archived' or target.duplicate_of_map_id is not null
        or new.printing_id is null or target.printing_id is null or new.printing_id<>target.printing_id
        or not exists(select 1 from public.sheet_printings p where p.id=new.printing_id and p.review_status='verified')
        or (new.series_id is not null and target.series_id is not null and new.series_id<>target.series_id)
        or (new.sheet_number is not null and target.sheet_number is not null and new.sheet_number<>target.sheet_number))) then
      raise exception 'duplicate target must be an active non-duplicate map';
    end if;
  end if;
  if tg_op='UPDATE' and exists(select 1 from public.maps d where d.duplicate_of_map_id=new.id
    and (new.status='archived' or new.duplicate_of_map_id is not null or new.printing_id is null
      or d.printing_id is distinct from new.printing_id
      or (d.series_id is not null and new.series_id is not null and d.series_id<>new.series_id)
      or (d.sheet_number is not null and new.sheet_number is not null and d.sheet_number<>new.sheet_number))) then
    raise exception 'map change would invalidate archived duplicate links';
  end if;
  if tg_op='UPDATE' and new.status='archived' and old.status is distinct from new.status
    and exists(select 1 from public.maps d where d.duplicate_of_map_id=new.id) then
    raise exception 'map with duplicate records cannot itself be archived';
  end if;
  return new;
end;
$$;
drop trigger if exists maps_guard_archiving on public.maps;
drop trigger if exists zz_maps_guard_archiving on public.maps;
create trigger zz_maps_guard_archiving before insert or update of status,duplicate_of_map_id,archive_reason,printing_id,series_id,series_key,sheet_number on public.maps
for each row execute function public.guard_map_archiving();
revoke all on function public.guard_map_archiving() from public,anon,authenticated;
grant execute on function public.guard_map_archiving() to service_role;
comment on function public.guard_map_archiving() is 'Staff-only archive writes; duplicate links are one-hop to a live survivor, preventing chains and cycles. Service-role writes remain available for trusted migrations/workflows.';
