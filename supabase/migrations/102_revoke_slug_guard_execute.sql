-- Migration 102 — the fifth trigger-only function 099 missed
--
-- 097 added `maps_guard_contributor_slug()` (SECURITY DEFINER, BEFORE INSERT/UPDATE
-- on maps) and it kept Postgres's default PUBLIC EXECUTE. 099 revoked the other
-- four trigger functions but not this one; the has_function_privilege sweep run
-- against production on 2026-09-30 returned it for both anon and authenticated.
-- Same reasoning as 099: a trigger runs as the function owner, so this changes
-- nothing about the guard itself, only the direct-call path.

revoke execute on function public.maps_guard_contributor_slug() from public, anon, authenticated;
