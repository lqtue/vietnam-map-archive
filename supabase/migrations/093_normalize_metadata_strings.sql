-- Migration 093 — collapse spelling/language variants of the same fact
--
-- Found auditing `maps` alongside 092: three free-text columns carry the same
-- underlying fact under more than one spelling. None of these are filtered or
-- faceted on today, so nothing breaks silently the way 092's `collection` did —
-- this is standardizing ahead of the day something facets on them.
--
-- `language` — ISO 639-1 per mig 026's own comment; 2 rows used the 639-2 form.
update public.maps set language = 'fr' where language = 'fre';

-- `dc_publisher` — same institution, capitalization/word-order variants.
-- Verified against holding_institution + rights before merging: both pairs are
-- the same cohort (SGI/BnF rows and AMS/PCL rows respectively), not two
-- different publishers that happen to share a near-identical name.
update public.maps
   set dc_publisher = 'Service Géographique de l''Indochine'
 where dc_publisher = 'Service géographique de l''Indochine';

update public.maps
   set dc_publisher = 'U.S. Army Map Service'
 where dc_publisher = 'Army Map Service, U.S. Army';

-- `rights` — merge exact-meaning duplicates only. 'Public domain' and
-- 'Public domain — a work of the U.S. federal government.' stay separate: they
-- name different legal bases (age vs. federal-work statute), not a spelling
-- difference. Checked which institution each variant's rows carry before
-- merging: 'domaine public' is BnF/SGI rows, same cohort as the plain-English
-- 'Public domain' rows; 'Public domain (U.S. Government work)' is AMS/PCL rows,
-- same cohort as the longer federal-work phrasing.
update public.maps
   set rights = 'Public domain'
 where rights = 'domaine public';

update public.maps
   set rights = 'Public domain — a work of the U.S. federal government.'
 where rights = 'Public domain (U.S. Government work)';
