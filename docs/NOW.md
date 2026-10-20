# Now — what matters this month, and why

**Read this first, every session.** It holds the bets that serve the goal, what only Tue can do,
and who is working on what. What VMA is, and the goal itself, is `CONCEPT.md`. `ROADMAP.md` is the
backlog behind it; nothing here repeats its detail. Keep this file under 70 lines: when a bet closes, replace it, and when an idea arrives, put
it through the gate before it gets a branch. Updated 2026-10-18. Public repo: no application dates,
referees or contacts here — those live in `docs/private/`.

## Goal

**Link** maps that never agree, **measure** what it costs and how often it is right, and count only
**checks that could have failed**. Full text: `CONCEPT.md` §The goal.

## Bets

| Bet | So what | Done when |
|---|---|---|
| **1a. Place links, 1882** (`place-links`, `then-now-blocks`) | One owner sitting gives a measured linkage result now. | Owner-confirmed links with measured accuracy and seconds per item. Plan: `plans/digest-pipeline-plan.md` |
| **2. Measured gates** (`review-events`, `paper-audit-100k`) | Turns "it works" into numbers: error rate with an interval, seconds per item. The paper's contribution. | The baseline's "unmeasured" cells have numbers |
| **1b. 1882 full extraction** — parcels → roads → lots | The worked example every claim points to. Needs owner reference tracing and a GPU run. | **Later**, after 1a and 2. Plan: `plans/image-processing-1882-plan.md`. Code parked on `1882-extraction` (one commit, unreviewed; mig 120–121 not applied; renumber past 126 before it merges) |
| **1c. Admin units and a city's states, Saigon** (test) | The link applied to units, and the 2025 reform made into data: the first record beyond the 1882 sheet (`CONCEPT.md` §What it makes). Widened to one plan led by the map series: names and boundaries (decrees, books, printed names), who or what stood at a place on a date (directories), and which map is drawn from which, so agreement counts only between independent witnesses. | Test: trace one small Saigon area from 2025 to the 1882 topographic plan (`plan-topographique-du-20e-arrondissement-et-ses-environs`; villages and cantons, not the cadastral city plan), each step a typed link with its source; count the steps with an independent source. Area: Khánh Hội and Vĩnh Hội (Quận 4), chosen 2026-10-19 because Xuân Hòa was too thin: three villages on the 1882 sheet and dated acts from 1880 to 1959. Kill: 1976–2004 rests on one printed book or on Wikipedia alone → Saigon only, nation parked; most sheets state no source → infer from content and label it. Plan: `plans/series-admin-saigon-plan.md`. Groundwork: `experiments/admin-lines/` (#83) |
| **3. Corpus to link against** — series georef, OCR drain | Serves the product, not the next weeks. | **Later**, after 1a and 2. ROADMAP *Do next* |

## Tue only — the bottleneck

1. Place-links and then-now sittings (local pages on ports 8792 / 8793)
2. G1: merge and deploy `ingest-auto-queue`
3. 1971 series: credit line and scan date — `.claude/handoff-series-georef.md`
4. Look at the 15 placed L909 sheets (merged in #59)
5. 1882 river: ship the approved water, or park it — `feat/1882-1898-processing`; crops in `../vma-snapshots/261017-1882-river-crops/`

## The idea gate

Before an idea gets a branch, answer three lines:

1. **Which bet does it serve?**
2. **Smallest test** — one afternoon, one sheet, one number.
3. **Kill result** — what outcome means stop?

No bet → it goes to *Parked* below, not into code. A finished experiment's journal opens with
**Question → Answer → So what** (which bet moved, and how).

## Board

One row per open stream. Owner is Tue or Claude. Prune when merged.

| Stream | Owner | Where | Next step |
|---|---|---|---|
| Place links + then-now (offline, ports 8792/8793) | Claude | merged (#64); `work/image-processing/experiments/{place-links,then-now}/` | Tue's sittings, then Opus scores |
| paper-audit-100k (§9 audit) | Claude/Sonnet | `paper-audit-100k` (pushed, no worktree) | Rebase onto main (scripts moved in #77), then Tue's sittings |
| Paper: claim-audit R rows 23 and 99 | Claude | `paper-claim-rows` (1 commit), worktree `.claude/worktrees/agent-a3289…` | Rebase, review, merge |
| Ingest auto-queue | Claude (Sonnet) | `ingest-auto-queue` @ a57c8746, `.claude/worktrees/agent-…` | Done and checked; waits on Tue (G1) and Gallica 403 |
| Indochine 100k printed-tick audit | Claude | `indochine-printed-audit` (pushed, no worktree) | Two-sided reader check — `.claude/handoff-indochine100k.md` |
| OCR ingest sizing | Claude | merged; next step local | Cap tiles by pixel target — `.claude/handoff-ocr-ingest.md` |
| Home "How it works" · press image proxy | **Tue** | `home-how-it-works`, `press-image-proxy` | Idea gate, then PR or park |
| L909 sources (USGS GeoPDFs, other institutions) | Claude | `l909-sources` (pushed, no worktree) | Rebase onto main (#77), then PR: scripts and records only |
| Review page in the app (bet 2, `review-events`) | Claude | PR 1 merged (#82; mig 122 live 2026-10-18); `review-web` pushed | PR 2: the page (`docs/plans/review-page-plan.md` §8) |
| Data model: activities (bets 1a, 2) | Claude | plans and dedup 1–2 merged (#85; mig 123–124 live 2026-10-18) | `activities` table, per `plans/data-model-target.md` |
| Corpus: every map of Vietnam we know of (bet 3, feeds 1c) | Claude | `corpus-sources`, worktree `.claude/worktrees/corpus-sources`; Rumsey 52 → 243 in the queue 2026-10-21 | Step 2 of `plans/corpus-plan.md`: check each scout reads all its pages |
| Two map books as series (bet 3, feeds 1c) | Claude | `cochinchina-1889-atlas` (PR #99); 27 draft rows live 2026-10-19/20 (12 Cochinchina 1881–89, 15 Tonkin 1950), plus the 2 public 1882 sheets in the Cochinchina series | Georeference by chaining from the placed 1882 plans (idea gate first); only Tan An prints a graticule; Tan An year 1887 |

## Parked

Ideas with a plan but no current bet. Reopen by moving one into a bet, not by starting it.

- Walk (`plans/walk-plan.md`): first ask people for photo sets of standing buildings (place, date, CC BY); 3D later, from those sets. Test: one landmark, two weeks. Kill: under ~5 usable sets, or no clear licence.
- The 4D city, behind Walk (`CONCEPT.md` §The horizon; `city-reconstruction-plan.md` only on branch `docs/city-reconstruction-plan`; `panorama-match` killed at 131 m) · admin units for all of Vietnam (after 1c; name key: the 1950 Tonkin book, Rumsey 14320, 1:100k, public domain, ingested as drafts 2026-10-20; Hà Nội patch, one reader: 23 of 50 names fully readable, 50 of 50 at least partly, the misses are tone marks, so match without them; a second reader would firm it up; also needs a line-type model for 1:25k bounds — test: trace one Sơn Tây tile per legend class, train, score a second tile; kill: commune dots unreadable at scan resolution; `experiments/admin-lines/`) · Gallica text harvest · street-name pairs.
