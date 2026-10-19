-- Aggregate the public index tally before transferring it to catalog/Explore.
-- Deploy this additive view BEFORE the app that reads series_index_summary.
-- Reuse coverage detail so its explicit service-role gate, RLS, source evidence,
-- and distinct-cell semantics remain the sole definition of availability.
create or replace view public.series_index_summary with (security_invoker=true) as
select key,
 count(*) as total,
 count(*) filter (where publicly_held) as held,
 count(*) filter (where not publicly_held and known_source) as obtainable,
 count(*) filter (where not publicly_held and not known_source) as no_scan
from public.series_cell_coverage_detail
group by key;
comment on view public.series_index_summary is 'One public-availability tally per readable series. Drafts never count as publicly held; the underlying coverage detail preserves caller visibility and excludes archived holdings.';
grant select on public.series_index_summary to anon, authenticated, service_role;
