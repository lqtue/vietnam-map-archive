-- Migration 060 — one visibility model on maps (architecture step 9)
--
-- `maps` carried both `status` (draft/public/featured) and the booleans
-- `is_public`/`is_featured`, and different code paths gated on different ones.
-- docs/guides/db-guidelines.md has warned about this since migration 038; the enum
-- wins, because it is the one the API and the RLS policies already agree on.
--
-- Four policies read `maps.is_public`, so they are rewritten first — dropping
-- the column out from under them would leave the tables unreadable.

drop policy if exists "footprints_select" on public.footprint_submissions;
create policy "footprints_select"
  on public.footprint_submissions for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from public.maps
      where id = map_id and status in ('public', 'featured')
    )
  );

drop policy if exists "label_pins_select" on public.label_pins;
create policy "label_pins_select"
  on public.label_pins for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from public.maps
      where id = map_id and status in ('public', 'featured')
    )
  );

drop policy if exists "legend_submissions_select" on public.legend_submissions;
create policy "legend_submissions_select"
  on public.legend_submissions for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from public.maps
      where id = map_id and status in ('public', 'featured')
    )
  );

drop policy if exists "metadata_submissions_select" on public.metadata_submissions;
create policy "metadata_submissions_select"
  on public.metadata_submissions for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from public.maps
      where id = map_id and status in ('public', 'featured')
    )
  );

-- Anything the booleans said that the enum did not, before they go.
update public.maps set status = 'featured' where is_featured = true and status <> 'featured';
update public.maps set status = 'public'   where is_public = true and status = 'draft';

alter table public.maps
  drop column if exists is_public,
  drop column if exists is_featured;

-- story_points.quest / qr_payload: the adventure-mode fields from the hunt
-- feature dropped in migration 034. Nothing in src/ has read them since.
alter table public.story_points
  drop column if exists quest,
  drop column if exists qr_payload;
