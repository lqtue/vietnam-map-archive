# Digest pipeline — plan (2026-10-12)

How a map moves from "found" to "linked" with the machine doing the work and a person deciding,
and how every decision is timed and tied to what it judged. This is the engineering plan; the
measured starting point is `docs/journals/261012-manual-baseline.md`, and the paper it feeds is
`docs/paper/draft.md` (§9, B0152). Open items are in `docs/ROADMAP.md` under *Measured pipeline*.

## Why

The baseline found the machines are not the bottleneck. Layout runs in half a minute and OCR in
five; then a person takes days or weeks, or never. 70% of 15,206 OCR labels are unreviewed, 80% of
laid-out maps were never signed off, none of the 1,430 outlines carries a review date, and nothing
anywhere records how long a person spent. The front of the chain (find, credibility, record) runs
on one-off scripts — 55 of 71 — rather than on its own tools.

So the work is not "automate more". It is: let the machine propose at every stage, put one
person's decision at a named gate, and record that decision so that time and accuracy become
numbers instead of guesses.

## One rule for every gate

Every review page writes one line per verdict through `work/review-kit/review_record.py`:

| Field | Why |
|---|---|
| `bound` | Hash of exactly what was judged (geometry, corners, candidate list) plus the method version. A later version changes the hash, so an old approval can never pass new geometry. This is the binding B0152 asks for. |
| `shown_at`, `decided_at` | Human time as a measurement. Gaps over 5 minutes are dropped and counted. |
| `proposal_shown` | False on the blind arm: one item in five shows no machine suggestion. The gap between the two arms separates agreeing with the machine from being right. |
| `order_idx` | Position in the sitting, for the learning curve. |

A random share of already-approved items is re-checked blind. That re-check, not the approval
count, is the accuracy number.

## The stages

| Stage | Machine proposes | Person decides | Bound to | Audit | Paper hook |
|---|---|---|---|---|---|
| Find | scout loads candidates; derives the image link (Gallica's own IIIF server) | approve / reject, with a reason | candidate record | — | — |
| Record | ingest queues `layout`, then `ocr` (branch `ingest-auto-queue`) | nothing until georeference | — | job timings | — |
| Georeference | series routes (paper §5–6); junction matching gives an independent error field | V-frame: boundary on the printed edge. V-place: sheet in the right place | corner hash + detector version | random sample of *cleared* sheets | §9 audit, the first rate (`paper-audit-100k`) |
| Layout | title, legend, map body boxes | sign-off | regions + layout version | — | — |
| OCR review | labels | validate / correct | label text + run | 50 validated labels re-read blind | — |
| Features | then-now blocks, classed unchanged / reshaped / split / merged / complex / gone / new | V1 outline right; V2 class right | both outlines + method version | 20% blind on V2 | B0141: positions not made by the transform |
| Link | "what stands here today" by position, name and kind | same building / same site, new building / moved / gone / none | label px + candidate list + suggester version | 20% blind | — |

## Rules this plan keeps

- **The 27 editor picks are a dev set.** `name_today.py` was tuned on them
  (`work/image-processing/results/prior/eval-freeze.json`). Accuracy is scored on independent sets:
  `landmarks_1882.csv`, finds made after the freeze, and the blind arm.
- **Control points are not checks.** Anything within 30 m of one of a sheet's control points is
  `in_fit` and stays out of accuracy numbers (`results/prior/<map>/gcps-1882.json`).
- **Machine text is never recorded as human input.** `legend_finds.query` stays what a person typed.
- **Block differences stay offline** until a person has gated them. 1882 block outlines can become
  `parcel` proposals only through the parcel work's own flow (migration 120).
- **One sheet gives cases, not rates.** The 1882 results can illustrate the method; the rate comes
  from the random sample of cleared Indochine 1:100,000 sheets.
- **Predictions go in the docstring before the first run**, and every disagreement is reported.
- **Source on every row.** The owner treats the 2023 HCMC building and topo data as public
  (2026-10-12); every derived row says where it came from, so it can be traced or pulled.

## Phases and gates

| Phase | Work | Owner gate after it |
|---|---|---|
| 0 | eval freeze, control-point file, review-record contract, licence line | — |
| 1 | place links (offline, port 8792); then-now blocks and field (offline, port 8793); Gallica image links on the ingest branch | **G1**: merge and deploy `ingest-auto-queue`, ingest the four approved Gallica maps |
| 2 | owner sittings on the two review pages, plus the blind OCR re-check; results journal | — |
| 3 | `scripts/paper_audit_100k.py`, pre-registered and committed before the draw; review; paper blocks B0158+ | — |
| 4 | `place_links` table (next free migration; 120 and 121 are the 1882 footprint work), public read, "Today" on `/explore`; `review_events` in the existing review tools | **G2** migration push, **G3** deploy |

Phase 4 starts only if the Phase 2 numbers justify it.

**Priority (`docs/NOW.md`, 2026-10-12):** the Phase 2 sittings and the Phase 3 audit come first,
because they produce the measured results. G1 and Phase 4 are product work and wait for them.

## The ingest decision

The approved Gallica maps arrive with only a small preview picture, so the automatic layout and OCR
steps have nothing full-size to read. Pointing them at Gallica's own image server is one URL rule
(the 1942 maps already work this way); our own R2 copy still gets made automatically when a map is
published (migration 058). The cost is that a slow or refused Gallica request must fail the job,
never read as "no text".
