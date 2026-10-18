# Now — what matters this month, and why

**Read this first, every session.** It holds the goal, the bets that serve it, what only Tue can
do, and who is working on what. `ROADMAP.md` is the backlog behind it; nothing here repeats its
detail. Keep this file under 70 lines: when a bet closes, replace it, and when an idea arrives, put
it through the gate before it gets a branch. Updated 2026-10-18. Public repo: no application dates,
referees or contacts here — those live in `docs/private/`.

## Goal

Show that historical maps which never agree can still be **linked** — map to map, map to source,
map to today — with a machine that proposes and a person who decides; **measure** what that costs
and how often it is right; and show **which checks are independent of what they check** (a real
check, not an echo). That measured, linked record is the product (VMA) and the PhD pitch
(information science) at once.

## Bets

| Bet | So what | Done when |
|---|---|---|
| **1a. Place links, 1882** (`place-links`, `then-now-blocks`) | One owner sitting gives a measured linkage result now. | Owner-confirmed links with measured accuracy and seconds per item. Plan: `plans/digest-pipeline-plan.md` |
| **2. Measured gates** (`review-events`, `paper-audit-100k`) | Turns "it works" into numbers: error rate with an interval, seconds per item. The paper's contribution. | The baseline's "unmeasured" cells have numbers |
| **1b. 1882 full extraction** — parcels → roads → lots | The worked example every claim points to. Needs owner reference tracing and a GPU run. | **Later**, after 1a and 2. Plan: `plans/image-processing-1882-plan.md`. Code parked on `1882-extraction` (one commit, unreviewed; mig 120–121 not applied) |
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
| Review page in the app (bet 2, `review-events`) | Claude | PR #82 `review-store` (PR 1: store + endpoints); `review-web` pushed | Review and merge #82, then PR 2 (`docs/plans/review-page-plan.md` §8) |
| Admin bounds by machine (experiment) | Claude | PR #83 `admin-lines` | Review: idea gate, then merge or park |
| Concept: one page on what VMA is | Claude | PR #84 `concept` | Review and merge |
| Data model plans + model dedup 1–2 (mig 123–124) | Claude | PR #85 `model-dedup` | Review; 123/124 not applied |

## Parked

Ideas with a plan but no current bet. Reopen by moving one into a bet, not by starting it.

- City reconstruction / 3D (`city-reconstruction-plan.md`, only on branch `docs/city-reconstruction-plan`), with 3D landmark models and the Favre panorama (`panorama-match`, killed at 131 m) — after the 1882 layer ships.
- Names over time / Vietnam admin gazetteer · Walk (`plans/walk-plan.md`) · Gallica text harvest · street-name pairs.
