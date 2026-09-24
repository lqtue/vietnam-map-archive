-- Migration 096 — data half of 095: series-sheet names, a duplicated location,
-- and the rights/language spelling variants 093 left for the next table.
--
-- All four collections in the corpus today are matched by a `like 'prefix%'`
-- guard rather than the full collection string, to avoid a transcription
-- mistake on the em-dash/accented characters those names carry — each prefix
-- is unique across the corpus (checked against a production snapshot,
-- 2026-09-23: 560 maps, 4 distinct non-null collections).
--
-- Rule order matters once, for one reason: the hyphen-spacing rule (2) has to
-- run AFTER the suffix-stripping rules (1, 3, 4), because two of the strings
-- those rules strip themselves contain a spaced hyphen — 'Huế - Việt Nam
-- 1:50,000 (Sheet 6541 IV)' and the three L909 titles' ' - Việt Nam City Maps
-- 1:12,500' suffix. Collapsing hyphen spacing first would change those exact
-- strings out from under the literal/anchored matches below. Applied in the
-- order 4, 1, 3, 2.

-- ────────────────────────────────────────────────────────────────────────────
-- maps.location — duplicates the series (Indochine / Tonkin collections)
-- ────────────────────────────────────────────────────────────────────────────

update public.maps
   set location = null
 where location in ('Indochine', 'Tonkin')
   and collection is not null;

-- ────────────────────────────────────────────────────────────────────────────
-- maps.name — series-sheet cleanup, collection is not null only. Standalone
-- maps (collection is null) are not renamed here — they still need the scans
-- to know what they are actually named.
-- ────────────────────────────────────────────────────────────────────────────

-- Rule 4a — L7014: strip the trailing ' (L7014 <sheet>[, ed. ...])' suffix.
-- The sheet code lives in maps.sheet_number (mig 095) now, not the name.
update public.maps
   set name = regexp_replace(name, '\s*\(L7014[^)]*\)\s*$', '')
 where collection like 'Series L7014%'
   and name ~ '\(L7014';

-- Rule 4b — the one L7014 row whose title never carried the "(L7014 ...)"
-- shape at all.
update public.maps
   set name = 'Huế'
 where name = 'Huế - Việt Nam 1:50,000 (Sheet 6541 IV)';

-- Rule 4c — L909: strip the trailing ' - Việt Nam City Maps 1:12,500'.
update public.maps
   set name = regexp_replace(name, '\s*-\s*Việt Nam City Maps 1:12,500\s*$', '')
 where collection like 'AMS L909%'
   and name ~ 'Việt Nam City Maps 1:12,500';

-- Rule 1 — Indochine 1:100,000: 'Est (E)' -> '(E)', 'Ouest (W)' -> '(W)'. The
-- half already lives in the suffix; the word was the series's own redundancy.
update public.maps
   set name = regexp_replace(name, ' Est \(E\)$', ' (E)')
 where collection like 'Indochine 1:100,000%'
   and name ~ ' Est \(E\)$';

update public.maps
   set name = regexp_replace(name, ' Ouest \(W\)$', ' (W)')
 where collection like 'Indochine 1:100,000%'
   and name ~ ' Ouest \(W\)$';

-- One sheet was catalogued 'Kralanh E (E)' — the half-letter belongs only in
-- the suffix.
update public.maps
   set name = 'Kralanh (E)'
 where name = 'Kralanh E (E)';

-- Rule 3 — Tonkin 1:25,000: three transcription fixes. Anchored + suffix-
-- preserving, so 'Phu Xyan Truong (E)' -> 'Phu Xuan Truong (E)' but the
-- already-correct 'Ha Chau (E)' / 'Nha Nam (W)' rows (capital-cased) are
-- untouched — the ~ operator is case-sensitive.
update public.maps
   set name = regexp_replace(name, '^Ha chau', 'Ha Chau')
 where collection like 'Indochine 1:25,000%'
   and name ~ '^Ha chau';

update public.maps
   set name = regexp_replace(name, '^Nha nam', 'Nha Nam')
 where collection like 'Indochine 1:25,000%'
   and name ~ '^Nha nam';

update public.maps
   set name = regexp_replace(name, '^Phu Xyan Truong', 'Phu Xuan Truong')
 where collection like 'Indochine 1:25,000%'
   and name ~ '^Phu Xyan Truong';

-- Rule 2 — all series sheets: hyphen spacing. Run last; see the header.
update public.maps
   set name = regexp_replace(name, '\s*-\s*', '-', 'g')
 where collection is not null
   and name ~ '\s-|-\s';

-- maps.slug is not touched by any of the above: maps_assign_slug (mig 088)
-- only mints when slug is '' — a plain UPDATE of name falls straight through.
-- Checked with a before/after diff on a copy of production data (303 names
-- changed, 0 slugs moved), not assumed.

-- ────────────────────────────────────────────────────────────────────────────
-- scout_candidates.rights / .language — same technique as mig 093: merge only
-- where the merged rows are verifiably the same fact, never two statements
-- with a different legal basis.
-- ────────────────────────────────────────────────────────────────────────────

-- rights: three spellings of the identical French phrase (case + one row with
-- a trailing space) collapse to the English form mig 093 already standardised
-- maps.rights on. 'Public Domain mark' is a distinct Rights Statements term
-- (rightsstatements.org's "Public Domain Mark"), not a spelling variant of
-- "public domain," and is left alone.
update public.scout_candidates
   set rights = 'Public domain'
 where rights in ('domaine public', 'Domaine public', 'Domaine public ');

-- One row is missing the trailing period the other 19 carry.
update public.scout_candidates
   set rights = 'Droits réservés. Nous contacter.'
 where rights = 'Droits réservés. Nous contacter';

-- language: mig 026 calls maps.language ISO 639-1; scout_candidates' scraped
-- values never were. Collapsed to the codes maps.language already uses.
-- 'nl' (1 row) is already correct; 'mul' (ISO 639-2 "multiple languages") is
-- already a real code, not a variant, and is left as-is. One row reads
-- 'English; ChinSpanishe' — garbled multi-value scrape data, not a spelling
-- variant of anything, and is left for whoever reviews that candidate by hand.
update public.scout_candidates set language = 'fr' where language in ('fre', 'French', 'français', 'french');
update public.scout_candidates set language = 'en' where language in ('English', 'english', 'eng');
update public.scout_candidates set language = 'zh' where language in ('chinese', 'chi');
update public.scout_candidates set language = 'la' where language in ('latin', 'lat');
update public.scout_candidates set language = 'vi' where language = 'Vietnamese';
update public.scout_candidates set language = 'es' where language = 'spanish';
update public.scout_candidates set language = 'nl' where language in ('dut', 'Dutch');
update public.scout_candidates set language = 'de' where language = 'ger';
update public.scout_candidates set language = 'pl' where language = 'Polish';
update public.scout_candidates set language = 'th' where language = 'thai';

-- ────────────────────────────────────────────────────────────────────────────
-- cell_printings.rights (sheet_sources, renamed 095)
-- ────────────────────────────────────────────────────────────────────────────

update public.cell_printings
   set rights = 'Copyright Expired'
 where rights = 'Copyright expired';
