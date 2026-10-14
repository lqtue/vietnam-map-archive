-- Migration 122 — the store behind the review page: tasks, items and one event per verdict
--
-- Four offline review pages (place links, then-now, river labels, the 100k audit) write one
-- `review_record` line per human verdict to a local file. The review page in the app
-- (docs/plans/review-page-plan.md) needs those lines in the database, with the same fields and
-- the same meaning, so that `review_sync.py pull` can write the file back byte for byte and
-- `sittings()`, `wilson()` and every task's scoring run on it unchanged. It also gives the in-app
-- tools (OCR review, footprint validate, legend) the table ROADMAP `review-events` asks for.
-- Plan §3 and §8 (PR 1).
--
-- * review_tasks    one row per kind of question ("What is this 1882 place today?"): its seed,
--                   its blind share, who may answer it, whether it is open.
-- * review_items    what is judged: `payload` is what the page shows on both arms, `proposal`
--                   what only the shown arm gets (the machine's candidates), `gold` the known
--                   answer for practice items. `bound` hashes exactly what is judged plus the
--                   method version, so a verdict can never approve newer geometry.
-- * review_events   one row per verdict or undo. INSERT-ONLY.
--
-- Decisions:
--
-- * review_events is insert-only by grant, not by trust. Nobody is granted UPDATE, DELETE or
--   TRUNCATE on it, service_role included; only the migration owner can. A verdict is evidence
--   (review_record: "appended, never rewritten; the last line for an item wins; undo appends"),
--   and the paper's numbers rest on it. The same reason keeps the rows it points at: the foreign
--   key from an event to its item is ON DELETE RESTRICT, so an item or a task that has events
--   cannot be deleted either. Retire an item with `active = false`. (Tests that write events
--   therefore cannot take them back out; they use a task key of their own and leave the rows.)
-- * `blind means blind` (plan §2.3): the proposal must never reach a client on the blind arm.
--   anon and authenticated get no grant at all on review_tasks or review_items, and no policy.
--   Every read of them is the API with the service role, which strips the proposal itself.
-- * A reviewer reads only their own events (RLS on `reviewer`). Writes are service_role only,
--   through the API, which takes the reviewer from the session and never from the request body.
--   They also never see what others decided: it would make the checks echo each other.
-- * `client_id` is the request's own id. The page generates it once per verdict and resends it on
--   a retry; the unique constraint is what makes "nothing is sent twice" true.
-- * `reviewer` is nullable and ON DELETE SET NULL: deleting an account must not delete the
--   evidence a person gave. The export labels such rows `deleted-user`.
-- * Deviations from docs/guides/db-guidelines.md, on purpose: review_tasks is keyed by its `key`
--   (a stable text name the offline files already carry as `task`), review_items by
--   (task, item_id) (the offline `item_id`, which is the source system's own id, e.g.
--   ocr_labels.id), and review_events by a bigint identity (a total order the export and its
--   pagination rely on, cheaper than a uuid for a table that only grows). `active` keeps the name
--   the plan and the API use, rather than `is_active`.
--
-- Deploy order: additive. The two /api/pipeline/review-* endpoints that read and write these
-- tables need this pushed first; no older code touches them. Not pushed to production yet.

-- --------------------------------------------------------------------------- tasks

create table if not exists public.review_tasks (
  key         text primary key check (key ~ '^[a-z0-9][a-z0-9-]{0,63}$'),
  title       text not null check (length(title) between 1 and 200),
  question    text not null check (length(question) between 1 and 500),
  question_vi text check (length(question_vi) between 1 and 500),
  method      text not null check (length(method) between 1 and 200),
  seed        integer not null,
  blind_frac  real not null default 0.2 check (blind_frac between 0 and 1),
  audience    text not null default 'staff' check (audience in ('staff', 'signed_in')),
  status      text not null default 'draft' check (status in ('draft', 'open', 'closed')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

comment on table public.review_tasks is
  'One kind of review question. Items live in review_items, verdicts in review_events. Migration 122.';
comment on column public.review_tasks.key is
  'The offline review_record `task` name (e.g. place-link). Lower-case, digits and hyphens.';
comment on column public.review_tasks.method is
  'Method version of the machine that made the items and proposals (e.g. name_today@23b04a70+place-link-v1). Also part of every item bound.';
comment on column public.review_tasks.seed is
  'Arm and order come from hash(seed, reviewer, item_id), so a reviewer''s blind set and order never drift. Do not change it once events exist; the push endpoint refuses.';
comment on column public.review_tasks.blind_frac is
  'Share of items with a proposal that show none. Fixed once events exist.';
comment on column public.review_tasks.audience is
  'Who may answer: staff (admin/mod) or any signed-in user.';
comment on column public.review_tasks.status is
  'Lifecycle: draft → open → closed. Only open tasks are offered to reviewers.';

create or replace function public.review_tasks_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger review_tasks_updated_at
  before update on public.review_tasks
  for each row execute function public.review_tasks_set_updated_at();

-- --------------------------------------------------------------------------- items

create table if not exists public.review_items (
  task       text not null references public.review_tasks(key) on delete cascade,
  item_id    text not null check (length(item_id) between 1 and 200),
  bound      text not null check (length(bound) between 1 and 128),
  payload    jsonb not null default '{}' check (jsonb_typeof(payload) = 'object'),
  proposal   jsonb check (jsonb_typeof(proposal) in ('object', 'array')),
  gold       jsonb check (jsonb_typeof(gold) in ('object', 'array')),
  active     boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (task, item_id)
);

comment on table public.review_items is
  'What is judged. payload = everything both arms see; proposal = what only the shown arm sees (null = nothing to show, never blind); gold = known answer for practice items. Never readable by anon or authenticated. Migration 122.';
comment on column public.review_items.item_id is
  'The source system''s own id (e.g. ocr_labels.id for place links); the offline review_record `item_id`.';
comment on column public.review_items.bound is
  'Hash of exactly what is judged plus the method version (review_record.bound). A verdict whose bound differs from this is stale and refused.';
comment on column public.review_items.active is
  'false retires an item without deleting it: events point at it and cannot be deleted.';

create or replace function public.review_items_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger review_items_updated_at
  before update on public.review_items
  for each row execute function public.review_items_set_updated_at();

-- --------------------------------------------------------------------------- events

create table if not exists public.review_events (
  id              bigint generated always as identity primary key,
  task            text not null,
  item_id         text not null,
  bound           text not null check (length(bound) between 1 and 128),
  reviewer        uuid references auth.users(id) on delete set null,
  order_idx       integer not null check (order_idx >= 0),
  shown_at        timestamptz not null,
  decided_at      timestamptz not null,
  received_at     timestamptz not null default now(),
  proposal_shown  boolean not null,
  verdicts        jsonb not null default '{}'
                    check (jsonb_typeof(verdicts) = 'object' and length(verdicts::text) <= 20000),
  readings        jsonb not null default '{}'
                    check (jsonb_typeof(readings) = 'object' and length(readings::text) <= 20000),
  note            text not null default '' check (length(note) <= 2000),
  client          jsonb not null default '{}'
                    check (jsonb_typeof(client) = 'object' and length(client::text) <= 4000),
  client_id       uuid not null default gen_random_uuid() unique,
  check (decided_at >= shown_at),
  foreign key (task, item_id) references public.review_items(task, item_id) on delete restrict
);

comment on table public.review_events is
  'One row per human verdict or undo, in the review_record fields. INSERT-ONLY: no UPDATE, DELETE or TRUNCATE grant for anyone but the migration owner. The last event for an item wins; an undo is an event whose verdicts = {"undone": true}. Migration 122.';
comment on column public.review_events.reviewer is
  'auth.users id, taken from the session by the API, never from the request body. Null after the account is deleted.';
comment on column public.review_events.shown_at is
  'When every view had loaded (review_record shown_at). Human time is decided_at - shown_at.';
comment on column public.review_events.decided_at is
  'The key press (review_record decided_at). Never before shown_at.';
comment on column public.review_events.received_at is
  'Server clock when the event arrived. Exported as review_record written_at.';
comment on column public.review_events.proposal_shown is
  'false on the blind arm: the reviewer saw no machine suggestion.';
comment on column public.review_events.readings is
  'Measurements beside the verdict, e.g. hidden_ms (time the tab was hidden).';
comment on column public.review_events.client is
  'Viewport and user agent, for diagnosing a slow sitting. Not exported.';
comment on column public.review_events.client_id is
  'Id the page makes once per verdict and resends on a retry; unique, so a retry cannot store the verdict twice.';

create index if not exists review_events_task_id_idx       on public.review_events (task, id);
create index if not exists review_events_task_reviewer_idx on public.review_events (task, reviewer, id);
create index if not exists review_events_task_item_idx     on public.review_events (task, item_id, id);

-- --------------------------------------------------------------------------- access

alter table public.review_tasks  enable row level security;
alter table public.review_items  enable row level security;
alter table public.review_events enable row level security;

-- Supabase's default privileges hand every new table to anon, authenticated and service_role.
-- Take them all back, then grant only what each role needs.
revoke all on public.review_tasks  from public, anon, authenticated, service_role;
revoke all on public.review_items  from public, anon, authenticated, service_role;
revoke all on public.review_events from public, anon, authenticated, service_role;

grant select, insert, update, delete on public.review_tasks to service_role;
grant select, insert, update, delete on public.review_items to service_role;

-- Insert-only: select and insert, never update, delete or truncate.
grant select, insert on public.review_events to service_role;
grant select on public.review_events to authenticated;

-- RLS gates rows for authenticated. service_role bypasses it, so its limits are the grants above.
drop policy if exists "review_events_select_own" on public.review_events;
create policy "review_events_select_own" on public.review_events for select to authenticated
  using (reviewer = (select auth.uid()));
