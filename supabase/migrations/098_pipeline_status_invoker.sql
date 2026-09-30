-- Migration 098 — silence the Security Definer View advisory on map_pipeline_status
--
-- The view (056) has no security_invoker setting, so it defaults to running
-- with its owner's privileges rather than the querying role's — the shape the
-- advisor flags as CRITICAL. 097 already revoked select from public/anon/
-- authenticated, leaving only service_role able to query it, and service_role
-- bypasses RLS regardless, so this was already low-risk. security_invoker
-- makes that explicit instead of implicit.

alter view public.map_pipeline_status set (security_invoker = true);
