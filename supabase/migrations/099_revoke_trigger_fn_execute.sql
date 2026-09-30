-- Migration 099 — stop anon/authenticated from calling trigger-only functions directly
--
-- Postgres grants EXECUTE to PUBLIC by default on every new function. These four
-- are SECURITY DEFINER and only ever meant to run as triggers (AFTER INSERT on
-- auth.users, BEFORE INSERT/UPDATE on maps) — a trigger runs as the function
-- owner regardless of the invoking role's grants, so revoking PUBLIC execute
-- does not touch trigger behaviour. It only stops the advisor-flagged path of
-- calling them directly via RPC.

revoke execute on function public.handle_new_user() from public, anon, authenticated;
revoke execute on function public.maps_assign_slug() from public, anon, authenticated;
revoke execute on function public.maps_demote_bare_slug() from public, anon, authenticated;
revoke execute on function public.enqueue_publish_jobs() from public, anon, authenticated;
