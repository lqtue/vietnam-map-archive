-- Migration 092 — "Vietnam Map Archive" is not a collection
--
-- `maps.collection` means "series/sub-collection at the holder" (mig 044, 082):
-- `series_key()` derives a survey's identity from it, and `series_sheets` /
-- `sheet_sources` key real surveys off that derived key. 35 rows instead carry
-- the literal string 'Vietnam Map Archive' — the archive's own name, used as a
-- filler for "this map belongs to no series." Mig 082's header already says as
-- much: those 35 are unrelated sheets across every scale, not a survey.
--
-- The string was live, not inert: `mirrorAnnotation` (src/lib/server/annotationMirror.ts)
-- wrote it unconditionally on every annotation re-mirror, which meant re-mirroring
-- a sheet that DOES belong to a real series (Indochine, L7014, L909) silently
-- stripped it out of that series. That write is removed in the same change as
-- this migration. This backfill clears the placeholder already on disk.
--
-- NULL is the right value, not a new bucket, because `map_series` (082) and the
-- catalog's series facet (`catalogSearch.ts`) already skip null `collection` —
-- "no series" needs no sentinel.

update public.maps
   set collection = null
 where collection = 'Vietnam Map Archive';
