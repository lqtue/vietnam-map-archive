-- Migration 092 — label_tasks UPDATE was open to anonymous callers
--
-- Migration 008 wrote the policy with a comment stating the intent directly:
-- "For now, allow authenticated users to update status". What it wrote was
-- `USING (true) WITH CHECK (true)`, which does not test authentication at all.
--
-- RLS is never consulted for `service_role`, so this granted the pipeline
-- nothing it did not already have. What it did was hand unrestricted UPDATE on
-- every row to every other role the table is granted to, `anon` included — the
-- same shape as the two INSERT policies 089 removed, arrived at from the
-- opposite direction: 089's were named as if the name were the guard, this one
-- had its guard written only in the comment.
--
-- It survived 83 migrations because nothing reads wrong at the call site. The
-- app updates a task it is already working on, so the gap is invisible until
-- someone talks to PostgREST directly.
--
-- The two clauses are deliberately not the same expression:
--
--   USING      gates which existing rows a caller may touch. A non-admin is
--              held to tasks still in play, so a settled task cannot be
--              reopened or rewritten by an ordinary signed-in user.
--   WITH CHECK gates what the row is permitted to become, and asks only for a
--              session. Repeating the status test here would make the policy
--              self-defeating: a task could never leave 'open'/'in_progress',
--              which is the one transition the labelling workflow exists to
--              perform.
--
-- The terminal states are 'consensus' and 'verified', per the CHECK constraint
-- in 008. There is no 'done'.

-- Verified 2026-09-20 on a throwaway PostgreSQL 17 cluster against a stub of
-- the three objects involved (auth.uid(), profiles, label_tasks + its read
-- policy). Docker was unavailable, so this is not a replay of the real
-- migration chain; CI runs that on the PR.
--
--   anon updates an open task                     blocked
--   anon rewrites every row                       blocked
--   anon reads                                    unchanged, 2 rows
--   signed-in user claims an open task            allowed
--   signed-in user takes open -> verified         allowed
--   signed-in user reopens a settled task         blocked
--   admin reopens a settled task                  allowed
--
-- Two counter-checks on the same cluster, both confirming what this replaces:
-- under 008's `USING (true) WITH CHECK (true)` an anonymous caller rewrote
-- every row in the table; and under the USING-only form proposed in Feb 2026
-- on claude/fix-rls-policy-label-tasks-6gF4R, a signed-in user finishing a task
-- did not merely fail to match but raised `new row violates row-level security
-- policy for table "label_tasks"`.

drop policy if exists "label_tasks_update" on public.label_tasks;

create policy "label_tasks_update"
  on public.label_tasks for update
  using (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'admin')
    or (auth.uid() is not null and status in ('open', 'in_progress'))
  )
  with check (auth.uid() is not null);
