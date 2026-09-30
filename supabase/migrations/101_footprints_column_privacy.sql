-- Migration 101 — hide reviewer-only footprint columns from anon; tighten the
-- two draft-visibility policies nothing signed-in-but-non-staff depends on.
--
-- Two audit findings.
--
-- ── A. two of the four "any signed-in reader" gates have no flow behind them
-- ────────────────────────────────────────────────────────────────────────────
--
-- Migration 063's `status in ('public','featured') or auth.uid() is not null`
-- reads as "draft = private", but signup is open (no allowlist, contradicting
-- 063's own "there is no /signup" — see 079's header, which already corrects
-- it), so the real gate is "not anonymous": any freshly created account
-- passes. Checked every non-staff client read against the four tables that
-- carry this pattern (`maps`, `ocr_labels`, `map_images`, `map_slug_aliases`):
--
--   * `maps` — genuinely needed. `/scan?mode=inspect` ("unlisted — the plain
--     look at a draft scan", `src/routes/CLAUDE.md`) has no role gate at all:
--     `InspectPage.svelte` calls `fetchMaps(supabase)` on mount with no
--     `requireRole`/session check, listing every map including other users'
--     drafts. `/contribute/georef`'s queue is the same:
--     `fetchGeorefQueue(supabase)` (`src/lib/data/maps/georef.ts`) selects
--     every `status = 'draft'` row for any signed-in visitor
--     (`src/routes/(editorial)/contribute/georef/+page.svelte` calls it
--     unconditionally, before the page even knows the caller's role).
--   * `ocr_labels` — genuinely needed. `fetchLabelMaps` (`src/lib/data/
--     supabase/footprints.ts`) feeds `ToolMapPicker.svelte`, mounted by
--     `/scan?mode=prepare|text|shapes` for any signed-in contributor, and
--     queries `ocr_labels.select('map_id')` across every map with no owner
--     filter to badge which sheets already have OCR.
--   * `map_images` — NOT needed. The only cross-user read is
--     `fetchGeorefFixList` (same file), and its one caller
--     (`contribute/georef/+page.svelte`) only invokes it
--     `if (role === 'admin' || role === 'mod')`. A client-side role check is
--     not a security boundary by itself (079's whole point), but it does mean
--     the *feature* only needs staff to reach another user's draft images —
--     exactly what the staff branch below already grants. Narrowed.
--   * `map_slug_aliases` — NOT needed. Its only reader is `/catalog/[id]`'s
--     loader, which runs on the service client and filters status itself
--     (`src/routes/(editorial)/catalog/[id]/+page.server.ts`). Narrowed.
--
-- `maps` and `ocr_labels` keep 063/065's wording — narrowing them would break
-- the two flows above. This is a reported conflict, not a fix: if the wider
-- surface (any signed-in reader on any draft) is not the risk the audit meant
-- to close, apply the same creator-or-staff shape used below to those two
-- policies, and gate `/scan?mode=inspect` and `fetchGeorefQueue` to something
-- narrower first. The same "published or signed-in" gate also lives, inlined
-- rather than as an RLS policy, in three `security_invoker` views —
-- `place_names` (081), `map_series` (082, recreated 084/095) — read through
-- `adminClient` today (`/catalog/place/[name]`, `/catalog/series/[key]`,
-- `/api/search`, all service-client callers where `auth.uid()` is null) but
-- exposed to a direct authenticated PostgREST call the same way `maps` is;
-- they would need to move with `maps` if that policy ever narrows.
--
-- Both narrowed policies use the shape `footprints_select`/
-- `maps_update_own_or_mod` already established: published, the row's own
-- creator, or staff. Staff-ness routes through `profiles.role`, which 097's
-- `profiles_select_own` already hides from an AAL1 session, so both inherit
-- the MFA requirement for free.

drop policy if exists "map_iiif_sources_select_all" on public.map_images;
drop policy if exists "map_images_select_visible_parent" on public.map_images;
create policy "map_images_select_visible_parent" on public.map_images for select
  using (
    exists (
      select 1 from public.maps m
       where m.id = map_images.map_id
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

drop policy if exists "map_slug_aliases_read_published_or_authed" on public.map_slug_aliases;
create policy "map_slug_aliases_read_visible_parent" on public.map_slug_aliases for select
  using (
    exists (
      select 1 from public.maps m
       where m.id = map_slug_aliases.map_id
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

-- ── B. footprints: anon got every column, including the reviewer's private
-- notes ──────────────────────────────────────────────────────────────────────
--
-- `footprints_select` (079, initplan-wrapped by 100) already row-gates
-- correctly — a public map's rows, or your own — but RLS has no column
-- granularity. Postgres RLS decides which *rows* a role sees; a plain
-- `grant select on table` (Supabase's default for every new table) still
-- hands over every column of those rows. So the anon key, calling
-- `/api/export/footprints` (`select('*, maps(...)')`) or the
-- `footprint_submissions` compat view directly, got `review_note`,
-- `review_tags`, `reviewed_by` and `user_id` on any row it could otherwise
-- see — a public map's rows in any review_status, including `rejected` and
-- `needs_review`, not only `approved`. `review_note` is reviewer prose about a
-- specific contributor's or the model's mistake; `reviewed_by`/`user_id` are
-- auth.users ids. None of that belongs in an anonymous export. The pattern is
-- 079's: narrow the anon grant to the columns that pass, exactly like
-- `profiles.role`.
--
-- Authenticated keeps every column, unchanged — a signed-in contributor
-- already sees their own `review_note` through the review UI, and
-- `footprints_select`'s row gate (own row, or a published map) is the real
-- boundary for them. `src/lib/data/supabase/footprints.ts` picks up the one
-- app-side read this breaks: `fetchMapFootprints`/`fetchSubmittedFootprints`
-- run unauthenticated too (`/scan?mode=shapes` has no sign-in gate on the
-- draw/validate tabs) and named `user_id` in their select list — now
-- conditional on a session existing.

revoke select on public.footprints from anon;
grant select (
  id, map_id, pixel_polygon, name, category, feature_type, source,
  review_status, valid_from, valid_to, confidence, temporal_status,
  created_at, updated_at, reviewed_at, run_id, geom, geom_src, geom_rmse,
  iiif_canvas
) on public.footprints to anon;

-- Same treatment for the mig-095 compat view: `security_invoker = true` means
-- the row gate is inherited correctly, but its own column list still repeats
-- `review_tags`, `review_note`, `reviewed_by`, `user_id`, and it is granted to
-- anon just like the table was. Nothing in src/ reads the old name (grepped
-- 2026-09-30); this only closes the same hole the compat view still offers.
revoke select on public.footprint_submissions from anon;
grant select (
  id, pixel_polygon, name, status, created_at, feature_type, map_id,
  iiif_canvas, source, valid_from, valid_to, confidence, temporal_status,
  category, updated_at, reviewed_at, run_id, geom, geom_src, geom_rmse
) on public.footprint_submissions to anon;
