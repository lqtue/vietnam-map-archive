# Review page — requirements, design and interaction

Status: proposal, 2026-10-14. Nothing built. Serves bet 2 (`review-events`) and bet 1a (`place-links`).

**Question.** Can the offline review pages (`work/review-kit/`) move into the VMA web app, so that
anyone we invite can judge items, without changing what a verdict means or how its time is measured?

**Answer wanted.** Yes, if one sitting of 20 place-link items on the web page gives the same seconds
per item as the offline page, and its export scores the same with the code we already have.

**So what.** One review engine for every task (place links, then-now blocks, river labels, the
100k audit), one table that also gives the in-app tools their missing human time (baseline §4),
and a page we can open to contributors later.

## 1. What exists

Four offline pages, each a Python server on a local port: `place-links/confirm.py` (8792),
`then-now/review.py` (8793), `river-reference/label.py`, and the 100k audit. Three are built on
`work/review-kit/review_page.py`; all write `work/review-kit/review_record.py` lines. What they share
is the contract this plan keeps:

| Rule | Why |
|---|---|
| One record per verdict, appended, never rewritten; the last line for an item wins; undo appends | A verdict is evidence; editing it destroys the record |
| `bound` = hash of exactly what was judged plus the method version | An old verdict can never approve new geometry |
| `shown_at` when the images have loaded, `decided_at` at the key press | Human time is measured, not guessed |
| A fixed blind arm (~20% of items that have a proposal show none) | The shown-vs-blind gap tells agreement from accuracy |
| Order and arms fixed by seed, never drift; resume at the first item without a verdict | A sitting can stop and restart without bias |
| The question stated above every item; "See today" links built from the item, not the proposal | Lessons from the first sittings |

## 2. Requirements

**Must, for the first test (v1):**

1. **Same record.** Every verdict stores the `review_record` fields unchanged: task, item_id, bound,
   reviewer, order_idx, shown_at, decided_at, proposal_shown, verdicts, readings, note.
2. **Same export.** A script writes `verdicts.jsonl` from the database, line for line in the
   `review_record` format, so `sittings()`, `wilson()` and each task's scoring run unchanged.
3. **Blind means blind.** On the blind arm the server never sends the proposal. Hiding it in the
   page is not enough once strangers use it.
4. **Arms and order per reviewer, with no stored session.** Arm and order come from
   `hash(task seed, reviewer, item)`, so each reviewer gets their own fixed blind set and order,
   nothing can drift, and adding items does not reshuffle the old ones.
5. **Stale is refused.** A verdict whose `bound` no longer matches the item is rejected (409); the
   page says so and loads the next item.
6. **Time stays honest.** `shown_at` starts when every view has loaded. Time with the tab hidden is
   counted and stored in `readings.hidden_ms`, so idle time is known, not cut at 300 s by guess.
   The server also stamps `received_at`; a verdict with `decided_at` in the future or before
   `shown_at` is refused.
7. **Keys and buttons.** The offline keys work unchanged, and every key has a visible button with
   the key shown on it, so a mouse user can do everything.
8. **Staff only.** v1 is open to `admin` and `mod`. The reviewer is taken from the session, never
   from the request body.
9. **Items come from the offline pipeline.** Python still makes the machine's proposals and the
   crops. It uploads items through the worker-token API, the same way the worker writes today.

**Should, before contributors (v2):** Vietnamese text for every task; a short first-run guide with
5 practice items whose answer is known; per-reviewer progress and seconds per item on `/profile`;
any signed-in user, rate-limited like `/api/contribute/*`; a queue where Tue settles items two
reviewers disagree on.

**Won't, for now:** zoom and pan in the views (it changes the measured condition; a link opens the
sheet in `/catalog/[id]` instead); phones; scores, ranks or a leaderboard; showing a reviewer what
others decided (it makes the checks echo each other, which the goal rules out).

## 3. Data

Three tables, one migration (next free number after Codex's unpushed 120–121, so 122).

```
review_tasks   key text pk, title, question, question_vi, method, seed int, blind_frac real,
               audience ('staff' | 'signed_in'), status ('draft' | 'open' | 'closed'), created_at

review_items   task → review_tasks, item_id text, bound text, payload jsonb, proposal jsonb null,
               gold jsonb null, active bool, updated_at;  pk (task, item_id)

review_events  id bigint pk, task, item_id, bound, reviewer uuid → auth.users, order_idx int,
               shown_at, decided_at, received_at default now(), proposal_shown bool,
               verdicts jsonb, readings jsonb, note text, client jsonb  (viewport, user agent)
```

- `payload` is everything the page shows on both arms; `proposal` is what only the shown arm gets.
- `review_events` is insert-only: no update or delete grant, not even for staff. Writes go through
  the API with the service role; RLS lets a reviewer read only their own rows.
- The same table is what ROADMAP `review-events` asks for, so the in-app tools (OCR review, footprint
  validate, legend) can write to it later with their own `task` names.

Crops: the build script renders each view **plain** (no overlay) at the size the method fixes and
uploads it to R2 next to the item. The page draws the label box, candidate markers, outlines, north
arrow and scale bar as SVG over the image from `payload` and `proposal`. One image serves both arms,
and nothing machine-made is baked into the pixels. (Arbitrary IIIF region requests are not used: the
IIIF worker serves only its stored tiles, and other regions fall back to slow origin hosts.)

## 4. Routes

| Route | Who | Does |
|---|---|---|
| `/review` | staff (v1) | The open tasks, each with items left for you and your last sitting |
| `/review/[task]` | staff (v1) | The review page |
| `GET /api/review/[task]/next` | session | The next item for this reviewer, proposal stripped on the blind arm |
| `POST /api/review/[task]/verdict` | session | Validate and insert one event |
| `POST /api/review/[task]/undo` | session | Append the undo event for your last live verdict |
| `GET /api/review/[task]/search?item=&q=` | session | Place-link only: search the item's 300 m pool |
| `POST /api/pipeline/review-items` | worker token | Upsert items for a task (from Python) |
| `GET /api/pipeline/review-events?task=` | worker token | All events for the export |

The page uses the tool register (full-bleed under the nav). A row goes in the `Tools ▾` staff group,
`paletteDestinations.ts` and `/directory`.

## 5. Page design

One item fills the screen. The views take the left, the decision takes a fixed 360 px column on
the right. Design tokens only (`docs/guides/design-system.md`): sheet ground, ink borders, blue for
selected, ochre for hover, red once for the error line.

```
┌ VMA  Catalog · About · Blog                                  Tools ▾  (avatar) ┐
├────────────────────────────────────────────────────────────────────────────────┤
│ Place links · 1882 Plan Cadastral        38 / 92 ▓▓▓▓▓▓▓░░░░░   12 s   ⏸ hidden │
├──────────────────────────────────────────────┬─────────────────────────────────┤
│ CLOSE (≈ 200 m)          CONTEXT (≈ 700 m)    │ What is this 1882 place today?  │
│ ┌──────────────────┐ ┌──────────────────┐    │                                 │
│ │                  │ │                  │    │ « Marché central »              │
│ │    [label box]   │ │       ·          │    │ See today: o over today ·       │
│ │   ①      ②       │ │                  │    │   v satellite · w street        │
│ │        ③         │ │                  │    │                                 │
│ │ ━ 50 m       (N) │ │ ━ 200 m      (N) │    │ 1 ▌Chợ Bến Thành   OSM · 140 m  │
│ └──────────────────┘ └──────────────────┘    │ 2 ▌Saigon Square   OSM ·  90 m  │
│                                              │ 3 ▌Tax Trade Ctr   OSM · 120 m  │
│                                              │ / search within 300 m …         │
│                                              │                                 │
│                                              │ Picked: 1 Chợ Bến Thành         │
│                                              │ How does it relate?             │
│                                              │ [s same building] [n same site] │
│                                              │ [m moved] [g gone] [x none]     │
│                                              │ [? unsure]                      │
│                                              │ t note …                        │
│                                              │ u undo last · Open sheet ↗      │
└──────────────────────────────────────────────┴─────────────────────────────────┘
```

- **Header bar:** task name, progress (done / total and a bar), the live timer for this item, and
  a "hidden" mark when the tab was left. The timer is for the reviewer's own pacing; the stored time
  comes from the timestamps.
- **Views:** fixed size per the method, scaled down together only when the window is narrower than
  both. Below 1280 px wide they stack. Candidate markers carry their number as well as their colour.
- **Decision column:** question first, then the item, then the proposal (shown arm) or the
  no-suggestion line (blind arm and items without candidates), then the verdict buttons, the note,
  undo and a link to open the sheet.
- **Blind arm** looks like an item with no candidates: "No suggestions here. Press / and type a
  name you know, or g gone, x none, ? unsure." The reviewer is not told which arm they are on.

## 6. Interaction

**States.** loading → ready (timer runs) → picked → saving → next item.
Side states: stale (409), offline or server error, all done, not signed in, not allowed.

| Input | Does | Notes |
|---|---|---|
| `1` `2` `3` or click a candidate | Pick it; again to unpick | Shown arm only |
| `/` | Focus search; typing filters the 300 m pool; `Enter` picks the first hit; `Esc` leaves | |
| `s` `n` `m` | Send with that relation | Refused with a message until something is picked |
| `g` `x` `?` | Send with that relation | No pick needed; `x` clears a pick |
| `t` | Focus the note; `Enter` or `Esc` leaves | Keys do nothing while a field has focus |
| `u` | Undo your last live verdict and show that item again | |
| `o` `v` `w` | Open today's view: 1882 over today, satellite, street view | New tab, from the item's own position |

- **Send is one key, no confirm step.** A wrong verdict is fixed with `u`, as offline. This keeps
  seconds per item comparable.
- **Saving:** the buttons lock and the next item loads when the server answers. The next item's
  timer starts only when its views have loaded, so a slow network adds no human time.
- **Stale (409):** "This item changed since it was loaded; your verdict was not saved." Next item.
- **Network error:** the verdict stays on screen with Retry; nothing is lost and nothing is sent twice
  (the request carries a client id the server treats as a unique key).
- **All done:** the count, your median seconds per item, and a link back to `/review`.
- **Accessibility:** every key has a button with `aria-keyshortcuts`; focus is visible; the result of
  each send is announced in a polite live region; colour is never the only cue.

## 7. A task is one small definition

As with `review_page.py`, a task is configuration plus at most one overlay component:

```ts
// src/lib/features/review/tasks/placeLink.ts
export const placeLink: ReviewTask = {
  key: 'place-link',
  question: 'What is this 1882 place today?',
  views: ['close', 'context'],
  keys: { s: 'same_building', n: 'same_site_new_building', m: 'moved', g: 'gone', x: 'none', '?': 'unsure' },
  needsPick: ['same_building', 'same_site_new_building', 'moved'],
  overlay: PlaceLinkOverlay, // draws box, markers, outlines from payload + proposal
};
```

The shared frame (header, views, timer, keys, undo, states, the send) lives once in
`src/lib/features/review/`. Then-now is a second definition with two verdicts per item (V1 outlines,
V2 class), which the frame supports as steps.

## 8. Build order

| PR | Contents | Size |
|---|---|---|
| 1. Store | Migration 122, the two pipeline endpoints, `work/review-kit/review_sync.py` (`push` items, `pull` → verdicts.jsonl), round-trip self-check | ~½ day |
| 2. Page | `/review`, `/review/[task]`, the frame, the place-link task, the four session endpoints | ~1 day |
| 3. Test | Tue's 20-item sitting; compare with the offline baseline; journal | 1 hour of Tue, ½ hour scoring |
| 4. Contributors | v2 list in §2 | after 3 passes |

**Smallest test.** Tue finishes the offline place-link sitting first (87 items left) as the
baseline. Then 20 new items on the web page. Pass: median seconds per item within 25% of offline,
and the exported file scores identically when fed through `confirm.py`'s scoring.
**Kill:** the web page is more than 50% slower per item, or the export does not round-trip.

## 9. Open questions

1. Route: `/review` (proposed) or under `/contribute/`?
2. Should contributors see the "See today" links to Google? (They make the task easier, and every
   reviewer sees the same thing, so the measure stays fair.)
3. Does a contributor's verdict count toward the paper's numbers, or only Tue's? (Proposed: the
   paper reports each reviewer group separately.)
