-- Migration 088 — a sheet's address is its name, not its uuid
--
-- `/catalog/787439c7-8015-496d-a458-df61b89a4391` is the URL a reader is asked
-- to paste into a message, and it says nothing about what is on the other end.
-- This adds `maps.slug`, the readable half of that address, and the alias table
-- that keeps every URL the archive has ever minted pointing somewhere real.
--
-- ── the rule, and why the tie-break is the year ──────────────────────────────
--
-- Measured on the corpus 2026-09-14: 147 of 153 names are already unique, so
-- almost every sheet gets its own name and nothing else. All six colliding
-- groups are the SAME PLACE IN A DIFFERENT YEAR:
--
--     Vinh Yen                    1906 · 1919
--     Hoai Duc Phu                1911 · 1925
--     Phu Tu Son                  1911 · 1925
--     Plan de la ville de Hanoï   1929 · 1942
--     Plan de la ville de Saigon  1799 · 1878
--     Quang Yen                   1904 · 1904   ← the only true tie
--
-- So the disambiguator is `year`, not a counter. `vinh-yen-1906` tells a reader
-- which sheet they are looking at; `vinh-yen-2` tells them only that they were
-- second in the door. A bare `-2` is the last resort, and on today's corpus it
-- applies to exactly one row.
--
-- **When a name collides, neither sheet keeps the bare slug.** Both take the
-- year. Three reasons, and the third is the one that matters over time:
--
--   1. There is no honest basis for picking a winner between two sheets that
--      share a name. Whichever is crowned, the other is demoted for a reason no
--      reader could reconstruct.
--   2. The bare URL would be a lie. If `/catalog/vinh-yen` is the 1906 sheet,
--      someone linking to "Vinh Yen" believes they have linked to *the* Vinh Yen
--      map, and they have not.
--   3. It stays stable as the archive grows. A third Vinh Yen renames nothing.
--      Under a first-one-wins rule the clean URL is decided by upload order, and
--      every later sheet inherits a meaningless number for good.
--
-- The incumbent's bare slug is not destroyed when it is demoted — it moves to
-- `map_slug_aliases` and still lands, which is what makes rule 3 affordable.
--
-- ── a slug is minted once ────────────────────────────────────────────────────
--
-- Renaming a map does NOT re-address it. A title is edited for a typo or a
-- fuller transcription; a URL that moved every time would break links people
-- had already shared, silently and after the fact. Re-addressing is deliberate:
-- set `slug` to null and the trigger mints a fresh one, and the old one becomes
-- an alias rather than a 404.

-- ── 1. the slug itself ───────────────────────────────────────────────────────

alter table public.maps add column if not exists slug text;

comment on column public.maps.slug is
  'Readable address: /catalog/<slug>. Minted once from the name (migration 088), '
  'never changed by a rename. Retired slugs live in map_slug_aliases and still resolve.';

-- The name, folded the way the gazetteer folds a place name — `f_unaccent`
-- (migration 065) is the same primitive `place_key` uses, so `Hanoï` and `Đông`
-- reduce here exactly as they do there. Hyphens rather than spaces, because
-- this one is spent in a URL.
--
-- 80 characters, cut before the trailing hyphens are stripped so a cut that
-- lands mid-word cannot leave one dangling. The longest name in the corpus is
-- 101 characters ("Bâtiments civils — le plan du colonel du génie Paul
-- Coffyn…"), and the ninetieth percentile is 32: the cut is for the handful of
-- catalogue titles that are a sentence, not for ordinary sheets.
create or replace function public.map_slug_base(p_name text)
returns text
language sql immutable parallel safe
as $$
  select nullif(
    regexp_replace(
      left(
        regexp_replace(lower(public.f_unaccent(coalesce(p_name, ''))), '[^a-z0-9]+', '-', 'g'),
        80),
      '(^-+|-+$)', '', 'g'),
    '')
$$;

comment on function public.map_slug_base(text) is
  'Map name → URL stem: unaccented, lowercased, every run of non-alphanumerics a single hyphen, 80 chars. Null when nothing usable is left.';

-- ── 2. retired slugs ─────────────────────────────────────────────────────────

create table if not exists public.map_slug_aliases (
  slug       text primary key,
  map_id     uuid not null references public.maps(id) on delete cascade,
  created_at timestamptz default now()
);

comment on table public.map_slug_aliases is
  'Addresses /catalog/<slug> has answered on before: a demoted bare slug, or one retired by a deliberate re-mint. The loader 301s them to the map''s current slug, so no link the archive has published ever dies.';

create index if not exists map_slug_aliases_map_id_idx on public.map_slug_aliases(map_id);

alter table public.map_slug_aliases enable row level security;

-- Same visibility as the map it points at. An alias is a title fragment, and a
-- draft's title is not public — the share loader runs on the service client and
-- filters status itself, so nothing here depends on this policy being generous.
drop policy if exists "map_slug_aliases_read_published_or_authed" on public.map_slug_aliases;
create policy "map_slug_aliases_read_published_or_authed"
  on public.map_slug_aliases for select
  using (
    auth.uid() is not null
    or exists (
      select 1 from public.maps m
       where m.id = map_slug_aliases.map_id
         and m.status in ('public', 'featured')
    )
  );

-- ── 3. minting ───────────────────────────────────────────────────────────────

-- Both namespaces at once. A canonical slug and a retired one cannot collide,
-- or a 301 would point at a page that is no longer there.
create or replace function public.map_slug_taken(p_slug text, p_except uuid)
returns boolean
language sql stable
as $$
  select exists (select 1 from public.maps m
                  where m.slug = p_slug and m.id is distinct from p_except)
      or exists (select 1 from public.map_slug_aliases a
                  where a.slug = p_slug and a.map_id is distinct from p_except)
$$;

-- name → free slug, applying the rule in the header: name, else name-year, else
-- name-year-N. `p_except` is the row being minted for, so re-minting a map does
-- not collide with itself.
--
-- `p_forbid` is the one slug this mint may not return even though the row
-- already holds it. Demotion is the caller that needs it: an incumbent giving up
-- the bare name is, by `p_except`, the very row that makes the bare name look
-- free, so without this it would be handed straight back what it came to give up.
create or replace function public.map_slug_mint(
  p_name text, p_year int, p_except uuid, p_forbid text default null)
returns text
language plpgsql
as $$
declare
  v_base text := coalesce(public.map_slug_base(p_name), 'sheet');
  v_stem text;
  v_n    int := 2;
begin
  if v_base is distinct from p_forbid and not public.map_slug_taken(v_base, p_except) then
    return v_base;
  end if;

  -- The year earns its place only if it is both known and free. A sheet with no
  -- year falls straight through to the counter, which is the honest outcome:
  -- there is nothing to tell the two apart with.
  v_stem := v_base;
  if p_year is not null then
    if v_base || '-' || p_year::text is distinct from p_forbid
       and not public.map_slug_taken(v_base || '-' || p_year::text, p_except) then
      return v_base || '-' || p_year::text;
    end if;
    v_stem := v_base || '-' || p_year::text;
  end if;

  while v_stem || '-' || v_n::text is not distinct from p_forbid
        or public.map_slug_taken(v_stem || '-' || v_n::text, p_except) loop
    v_n := v_n + 1;
  end loop;
  return v_stem || '-' || v_n::text;
end;
$$;

-- ── 4. backfill ──────────────────────────────────────────────────────────────
--
-- Nothing has been minted yet, so the whole corpus gets the fair reading of the
-- rule at once: a name that appears twice leaves BOTH sheets carrying a year,
-- and neither holds the bare slug. Ordering is `created_at, id` so the counter
-- of last resort is at least deterministic across replays of this migration.
with base as (
  select id,
         coalesce(public.map_slug_base(name), 'sheet') as stem,
         year, created_at
    from public.maps
   where coalesce(slug, '') = ''
),
ruled as (
  select id, created_at,
         case
           when count(*) over (partition by stem) = 1 then stem
           when year is not null                      then stem || '-' || year::text
           else stem
         end as cand
    from base
),
-- Two sheets can still land on one candidate: the true tie (same name, same
-- year) and the vanishing case where one map's name is literally another's
-- name-year. Both resolve here rather than in two places.
numbered as (
  select id, cand,
         row_number() over (partition by cand order by created_at, id) as dup
    from ruled
)
update public.maps m
   set slug = case when n.dup = 1 then n.cand else n.cand || '-' || n.dup::text end
  from numbered n
 where m.id = n.id;

-- ── 5. the constraint, once the data satisfies it ────────────────────────────

alter table public.maps alter column slug set not null;

-- The empty string as a default looks odd on a NOT NULL unique column, and is
-- load-bearing for exactly one reason: `supabase gen types` marks a NOT NULL
-- column with no default as REQUIRED in the generated `Insert` type. `slug` is
-- filled by the trigger below, not by callers, so a required field would force
-- every insert site — and every future one — to compute a slug client-side,
-- which is the duplicated rule this migration exists to avoid.
--
-- '' is never a value the mint can return (`map_slug_base` yields null for a
-- name with nothing usable in it, and the mint coalesces that to 'sheet'), so it
-- is a sentinel rather than a real address. If the trigger were ever disabled,
-- the first row through would take '' and the second would fail the unique index
-- — loudly, which is the right failure for a silently unaddressable sheet.
alter table public.maps alter column slug set default '';

create unique index if not exists maps_slug_key on public.maps(slug);

-- ── 6. keeping it true ───────────────────────────────────────────────────────

-- Mints on insert, and on an update that deliberately clears `slug`. A rename
-- alone changes nothing: `slug` is already set, so this falls through.
create or replace function public.maps_assign_slug()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  -- '' as well as null: the column's default is '' (see above), so an insert
  -- that names no slug arrives here holding the sentinel, not a null.
  if coalesce(new.slug, '') = '' then
    new.slug := public.map_slug_mint(new.name, new.year, new.id);
  end if;

  -- A slug that has just stopped being canonical becomes an alias, so the URL
  -- it used to answer on still lands. Deleting the incoming slug from the alias
  -- table first keeps the two namespaces disjoint: one address, one meaning.
  if tg_op = 'UPDATE' and coalesce(old.slug, '') <> '' and old.slug is distinct from new.slug then
    delete from public.map_slug_aliases where slug = new.slug;
    insert into public.map_slug_aliases (slug, map_id)
    values (old.slug, new.id)
    on conflict (slug) do update set map_id = excluded.map_id;
  end if;

  return new;
end;
$$;

drop trigger if exists maps_assign_slug on public.maps;
create trigger maps_assign_slug
  before insert or update on public.maps
  for each row execute function public.maps_assign_slug();

-- Rule 3 from the header, enforced at the moment it first applies: a new sheet
-- that had to take a year because an older one holds the bare name sends that
-- older one to a year of its own. The bare slug becomes an alias pointing at the
-- incumbent, so links already published still land on the sheet they meant.
--
-- No recursion: the update below sets `slug` to a non-null value, so the BEFORE
-- trigger's mint branch is skipped, and this trigger is INSERT-only.
--
-- One wart, confined to a true tie. When the contested name cannot be split by
-- year (same year, or no year at all) the newcomer has already taken `-1904` by
-- the time the incumbent is demoted, so the older sheet lands on `-1904-2` and
-- the newer on `-1904`. The numbers are arbitrary either way — neither encodes
-- anything a reader could use — so this is not worth a swap and the machinery
-- one would need. The backfill above does not share it: it sees the whole group
-- at once and orders by `created_at`.
create or replace function public.maps_demote_bare_slug()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
declare
  v_stem text := coalesce(public.map_slug_base(new.name), 'sheet');
  v_incumbent public.maps%rowtype;
begin
  if new.slug = v_stem then
    return null;  -- took the bare name, so nothing was contested
  end if;

  select * into v_incumbent
    from public.maps
   where slug = v_stem and id is distinct from new.id;

  if not found then
    return null;  -- bare name is retired or was never held; leave it be
  end if;

  -- `v_stem` is forbidden explicitly: the incumbent still holds it at this
  -- point, so `p_except` alone would report it free and hand it back.
  update public.maps
     set slug = public.map_slug_mint(
                  v_incumbent.name, v_incumbent.year, v_incumbent.id, v_stem)
   where id = v_incumbent.id;

  return null;
end;
$$;

drop trigger if exists maps_demote_bare_slug on public.maps;
create trigger maps_demote_bare_slug
  after insert on public.maps
  for each row execute function public.maps_demote_bare_slug();
