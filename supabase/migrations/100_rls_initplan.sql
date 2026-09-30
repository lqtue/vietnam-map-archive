-- Migration 100 — wrap auth.<fn>() in RLS policies so Postgres evaluates it once per query
--
-- Every occurrence below is `auth.uid()`/`auth.role()` called bare inside a policy's
-- USING/WITH CHECK. Without a select wrapper, Postgres re-evaluates the call once per
-- row scanned rather than once per query (the advisor's auth_rls_initplan warning).
-- `(select auth.uid())` is semantically identical — same value, same access rules —
-- and lets the planner hoist it into an InitPlan. Generated from a diff of the live
-- pg_policies qual/with_check against the same text with every bare call wrapped;
-- nothing here changes who can read or write a row.

alter policy "Users can delete own favorites" on public.favorites
  using (((select auth.uid()) = user_id));

alter policy "Users can insert own favorites" on public.favorites
  with check (((select auth.uid()) = user_id));

alter policy "Users can read own favorites" on public.favorites
  using (((select auth.uid()) = user_id));

alter policy "footprints_delete_own_or_admin" on public.footprints
  using (((user_id = (select auth.uid())) OR (EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = 'admin'::text))))));

alter policy "footprints_select" on public.footprints
  using (((user_id = (select auth.uid())) OR (EXISTS ( SELECT 1
   FROM maps
  WHERE ((maps.id = footprints.map_id) AND (maps.status = ANY (ARRAY['public'::text, 'featured'::text])))))));

alter policy "footprints_update_own_or_mod" on public.footprints
  using (((user_id = (select auth.uid())) OR (EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['mod'::text, 'admin'::text])))))))
  with check ((((user_id = (select auth.uid())) AND (review_status = ANY (ARRAY['draft'::text, 'submitted'::text]))) OR (EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['mod'::text, 'admin'::text])))))));

alter policy "label_pins_delete_own" on public.label_pins
  using ((user_id = (select auth.uid())));

alter policy "label_pins_insert" on public.label_pins
  with check ((((select auth.uid()) IS NOT NULL) AND (user_id = (select auth.uid()))));

alter policy "label_pins_select" on public.label_pins
  using (((user_id = (select auth.uid())) OR (EXISTS ( SELECT 1
   FROM maps
  WHERE ((maps.id = label_pins.map_id) AND (maps.status = ANY (ARRAY['public'::text, 'featured'::text])))))));

alter policy "label_pins_update_own" on public.label_pins
  using ((user_id = (select auth.uid())));

alter policy "map_iiif_sources_delete_admin" on public.map_images
  using ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = 'admin'::text)))));

alter policy "map_iiif_sources_insert_admin" on public.map_images
  with check ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = 'admin'::text)))));

alter policy "map_iiif_sources_update_admin" on public.map_images
  using ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = 'admin'::text)))));

alter policy "map_slug_aliases_read_published_or_authed" on public.map_slug_aliases
  using ((((select auth.uid()) IS NOT NULL) OR (EXISTS ( SELECT 1
   FROM maps m
  WHERE ((m.id = map_slug_aliases.map_id) AND (m.status = ANY (ARRAY['public'::text, 'featured'::text])))))));

alter policy "map_opens_select_staff" on public.map_views
  using ((EXISTS ( SELECT 1
   FROM profiles p
  WHERE ((p.id = (select auth.uid())) AND (p.role = ANY (ARRAY['admin'::text, 'mod'::text]))))));

alter policy "maps_delete_admin" on public.maps
  using ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = 'admin'::text)))));

alter policy "maps_insert_auth" on public.maps
  with check ((((select auth.uid()) IS NOT NULL) AND ((status = 'draft'::text) OR (EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['mod'::text, 'admin'::text]))))))));

alter policy "maps_select_published_or_authed" on public.maps
  using (((status = ANY (ARRAY['public'::text, 'featured'::text])) OR ((select auth.uid()) IS NOT NULL)));

alter policy "maps_update_own_or_mod" on public.maps
  using (((created_by = (select auth.uid())) OR (EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['mod'::text, 'admin'::text])))))))
  with check ((((created_by = (select auth.uid())) AND (status = 'draft'::text)) OR (EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['mod'::text, 'admin'::text])))))));

alter policy "ocr_extractions_read_published_or_authed" on public.ocr_labels
  using ((((select auth.uid()) IS NOT NULL) OR (EXISTS ( SELECT 1
   FROM maps m
  WHERE ((m.id = ocr_labels.map_id) AND (m.status = ANY (ARRAY['public'::text, 'featured'::text])))))));

alter policy "ocr_extractions_service_write" on public.ocr_labels
  using (((select auth.role()) = 'service_role'::text))
  with check (((select auth.role()) = 'service_role'::text));

alter policy "ocr_extractions_staff_validate" on public.ocr_labels
  using ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['admin'::text, 'mod'::text]))))))
  with check ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['admin'::text, 'mod'::text]))))));

alter policy "profiles_update_own" on public.profiles
  using (((select auth.uid()) = id))
  with check (((select auth.uid()) = id));

alter policy "Admins can update scout candidates" on public.scout_candidates
  using ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['admin'::text, 'mod'::text]))))));

alter policy "Admins can view scout candidates" on public.scout_candidates
  using ((EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['admin'::text, 'mod'::text]))))));

alter policy "stories_delete_own" on public.stories
  using ((user_id = (select auth.uid())));

alter policy "stories_select" on public.stories
  using (((review_status = 'approved'::text) OR (user_id = (select auth.uid())) OR (EXISTS ( SELECT 1
   FROM profiles
  WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['mod'::text, 'admin'::text])))))));

alter policy "stories_update_own" on public.stories
  using ((user_id = (select auth.uid())))
  with check (((user_id = (select auth.uid())) AND (review_status = ANY (ARRAY['draft'::text, 'submitted'::text]))));

alter policy "story_points_select" on public.story_points
  using ((EXISTS ( SELECT 1
   FROM stories
  WHERE ((stories.id = story_points.story_id) AND ((stories.review_status = 'approved'::text) OR (stories.user_id = (select auth.uid())) OR (EXISTS ( SELECT 1
           FROM profiles
          WHERE ((profiles.id = (select auth.uid())) AND (profiles.role = ANY (ARRAY['mod'::text, 'admin'::text]))))))))));

alter policy "Users can create annotation sets" on public.user_layers
  with check (((select auth.uid()) = user_id));

alter policy "Users can delete own annotation sets" on public.user_layers
  using (((select auth.uid()) = user_id));

alter policy "Users can read own annotation sets" on public.user_layers
  using (((select auth.uid()) = user_id));

alter policy "Users can update own annotation sets" on public.user_layers
  using (((select auth.uid()) = user_id));
