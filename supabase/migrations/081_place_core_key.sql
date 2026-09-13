-- Migration 081 — the gazetteer groups by the proper name, not the spelling
--
-- Measured on the corpus before this ran: 2554 entries, of which "Khánh Hội",
-- "Village de Khanh-Hoi" and "Vge de Khánh Hồi" were three. The command palette
-- offered all three as separate places, and every outside lookup we make — the
-- Gallica SRU calls in `press.ts`, the NLV decade facet — was billed once per
-- spelling for what is one place. Grouping on the proper name alone takes the
-- gazetteer to 1796 entries (-29.7%, 582 groups merged), which is the same cut
-- off the per-name call count.
--
-- `place_key` (migration 067) already unaccents, lowercases and collapses
-- punctuation to single spaces. It is not enough for grouping, because the
-- generic word in front of the name is the part the corpus is least consistent
-- about: `Boulevard` / `Boul.d` / `Bould.` / `Bd` / `R.` / `Rue`, and on the
-- Vietnamese sheets `Đường` / `Bến` / `Rạch` for the same feature. That word
-- carries almost no identity and it is exactly what the period press drops:
-- `"Bình Tây"` is 60 hits in the NLV archive where `"Chợ Bình Tây"` is 4.
--
-- Two guards, both learned from the corpus rather than reasoned:
--   * A core under four characters is rejected and the full key kept. Without
--     it "Chợ Lớn" strips to "lon" and collects every other name ending in Lớn —
--     Vietnamese names are short syllables and the generic word is a bigger
--     fraction of them than it is of "Rue Catinat".
--   * Only leading generics and trailing articles are stripped. `Grand`,
--     `Ancienne`, `Ngã` and the like are deliberately NOT in the list: they
--     read as generic and are name-bearing.
--
-- Known ceiling, accepted: 47 of the 582 groups merge across categories, which
-- is `Rạch Lò Gốm` (the canal), `Quai de Lò Gốm` (the quay) and `Đường Bến Lò
-- Gốm` (the road) landing on one page. In Saigon the quay is named for the
-- canal, so one page is usually right — but if a split is ever wanted, the
-- upgrade is to group by (feature class, core_key) rather than core_key, where
-- the class buckets the stripped word (way / water / settlement) instead of
-- discarding it. Do not use `category` for that: it is per-extraction and noisy,
-- so a miscategorised sheet would split a place that is one today.
--
-- `name_key` keeps its meaning as far as every caller is concerned: it is still
-- one row's stable key and still the slug `/catalog/place/[name]` renders. It is
-- now the most-attested *spelling's* key rather than the group's identity, so
-- the URL stays readable — `/catalog/place/boulevard-charner`, not `/charner`.
-- `core_key` is the identity, and the loader resolves any variant's slug
-- through it, so every link minted before this migration still lands.

-- The generic words, in one place. `place_key` has already unaccented, so these
-- are the ASCII forms: `duong` is Đường, `rach` is Rạch, `cho` is Chợ.
create or replace function public.place_generic_words()
returns text
language sql immutable parallel safe
as $$ select
  'rue|r|ruelle|boulevard|boul|bould|bd|blvd|avenue|av|ave|quai|quay|impasse|imp|'
  'place|pl|chemin|ch|route|rte|passage|village|vge|vlge|hameau|marche|pont|canal|'
  'arroyo|riviere|riv|fleuve|faubourg|duong|dg|pho|hem|rach|song|kenh|cho|ap|xom|'
  'cau|ben|khu|phuong|quan|xa|thon|lang|de|du|des|d|le|la|les|l|au|aux' $$;

create or replace function public.place_core_key(p_text text, p_validated text)
returns text
language sql immutable parallel safe
as $$
  with k as (select public.place_key(p_text, p_validated) as v),
       s as (
         select v,
                regexp_replace(
                  regexp_replace(v, '^((' || public.place_generic_words() || ') )+', ''),
                  ' (de|du|des|d|le|la|les|l)$', '')                        as core
           from k
       )
  select case when length(core) >= 4 then core else v end from s
$$;

comment on function public.place_core_key(text, text) is
  'Gazetteer identity: place_key with the leading generic word (Rue / Bd / Đường / Rạch …) and trailing articles removed. Kept whole when what is left is under four characters.';

-- The view, regrouped. Column order is unchanged and `core_key` is appended,
-- which is the only shape `create or replace view` accepts.
create or replace view public.place_names
with (security_invoker = true)
as
  select
    -- The most-attested spelling's key. Unique per group by construction: two
    -- rows sharing a place_key share a core_key and so share a group.
    mode() within group (order by public.place_key(e.text, e.text_validated))  as name_key,
    mode() within group (order by coalesce(e.text_validated, e.text))          as name,
    array_agg(distinct coalesce(e.text_validated, e.text))                     as variants,
    array_remove(array_agg(distinct m.year), null)                             as years,
    min(m.year)                                                                as first_year,
    max(m.year)                                                                as last_year,
    array_agg(distinct e.map_id)                                               as map_ids,
    count(*)                                                                   as mentions,
    mode() within group (order by coalesce(e.category_validated, e.category))  as category,
    extensions.st_y(
      extensions.st_centroid(
        extensions.st_collect(e.geom::extensions.geometry))::extensions.geometry) as lat,
    extensions.st_x(
      extensions.st_centroid(
        extensions.st_collect(e.geom::extensions.geometry))::extensions.geometry) as lng,
    max(e.geom_rmse)                                                           as geom_rmse,
    public.place_core_key(e.text, e.text_validated)                            as core_key
    from public.ocr_extractions e
    join public.maps m on m.id = e.map_id
    -- The visibility gate, said out loud. `security_invoker` alone was the
    -- whole story until now, and it is no story at all for the callers that
    -- matter: /catalog/place/[name] and /api/search both read this view on the
    -- service client, which bypasses RLS. A draft sheet's labels therefore
    -- reached the aggregate — not the sheet list, which the loader filters by
    -- status itself, but `mentions`, `years` and `first_year`, so an
    -- unpublished map moved a public page's dates. `auth.uid()` is null for a
    -- service-key caller and set for a signed-in browser one, which is exactly
    -- the line migration 063 draws.
   where (m.status in ('public', 'featured') or auth.uid() is not null)
     and e.status <> 'rejected'
     and coalesce(e.category_validated, e.category)
         in ('street', 'hydrology', 'place', 'building', 'institution')
     and length(public.place_key(e.text, e.text_validated)) >= 2
   group by public.place_core_key(e.text, e.text_validated);

comment on view public.place_names is
  'Gazetteer of attested place names, grouped by core_key (the proper name) from ocr_extractions. security_invoker, so draft maps stay gated by migration 065.';

grant select on public.place_names to anon, authenticated, service_role;
