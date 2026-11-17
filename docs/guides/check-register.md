# Check register

**As of 2026-10-21.** One row per check, and what each has done. Written from the plans, journals
and the claim audit; nothing was re-run for it. The verdict columns are **proposed**; the owner
decides. Bet 2 (`review-events`). Rule for what counts as a check: `CONCEPT.md` §The rule.

**Question.** Are the checks we run on the map series worth it, and which of them could have failed?

**Answer.** For Indochine 1:100,000 series 561, the checks guard a sheet's *shape* well and its
*position* barely. Every check that runs on the 337 placed sheets tests shape or frame. Two tests have
read a second witness for position, the sheet's own printed ticks: the calibration fit on 7 sheets (one
confirmed catch) and the printed-tick audit on 11 (unproven). The one time we have a sheet
known to be wrong in position (Tri Binh W, off 509 m west and 544 m south), every per-sheet gate
passed it. The ticks caught it.

**So what.** Nothing here is worth dropping. The gap is that the position check does not run on every
sheet, and nobody records whether a check firing was right. Two jobs follow: finish and prove the
printed-tick audit, then take the random sample that gives an error rate (`paper-audit-100k`).

## 1. The seven stages: how far each check has got

From the stage table in `plans/digest-pipeline-plan.md`. Status words: *designed* (on paper), *built*
(code exists), *run* (a real sitting or batch), *number* (a rate or a time exists).

| Stage | Check | Designed | Built | Run | Number |
|---|---|---|---|---|---|
| Find | person approves or rejects each candidate | yes | scout exists | not checked here | no |
| Record | none by design; job timings only | yes | `ingest-auto-queue`, done and checked | waits on Tue (G1) and a Gallica 403 | no |
| Georeference | gates, printed-tick audit, random sample | yes | gates yes; audit on a branch | gates yes; sample no | none: no random sample has been read |
| Layout | person signs off | yes | not checked here | 80% of laid-out maps never signed off (2026-10-12) | the 80% is a gap, not a rate |
| OCR review | person validates; 50 re-read blind | yes | admin API route exists (`ocr-review`) | 70% of 15,206 labels unreviewed (2026-10-12) | none for accuracy |
| Features | person judges outline and class; 20% blind | yes | offline page (local, ports 8792/8793) | sittings wait on Tue | no |
| Link | person judges the match; 20% blind | yes | offline page | sittings wait on Tue | no |

Most of the table reads *designed, built, not run*. The recording tool (`work/review-kit/review_record.py`)
and migration 122 exist, so a sitting can now be timed; the in-app page is still to come.

## 2. Series 561: one row per check

Script: `scripts/indochine100k/indochine100k_georef.py` on `main`, except row 8. The column that sorts
the rows is whether the check has a **second witness independent of the catalogue**. Without one it
compares the catalogue extent with itself and shares the error it tests for.

| # | Check | Second witness independent of the catalogue? | Could it see Tri Binh's error? | Fired, on record | Right? | Proposed |
|---|---|---|---|---|---|---|
| 1 | Shape: ground aspect vs pixel aspect, 3% (`verdict`) | no | **no**: passed at 0.69% | not logged | – | keep: it tests shape |
| 2 | Axes agree: scale gap, 1.5% | no | **no**: passed | 1 hold, 1.8% (260923) | not recorded | keep |
| 3 | Corner-figure span: 0.36–0.43ᵍ by 0.48–0.53ᵍ | no | **no**: Tri Binh's span passed; it takes a large error | Quang Ngai (260930) | **yes**: ~9.2 km, read from ticks | keep |
| 4 | Edge fit: line residual, 15 px | no, image only | no | not logged | – | keep: tests the detector |
| 5 | Rim spread across the four sides, 12% | no, image only | no | 3 holds, 15–26% (260923) | not recorded | keep |
| 6 | Lattice (`check`): reprints, overlap, rim vs median | no | not tested; a 500 m shift would not reach the 40% overlap rule (reasoned from the code, not run) | 1 sheet dropped at n=4 (260923); 0 holds on 337 (2026-10-07) | not recorded | keep; test it with the Tri Binh case |
| 7 | **Calibration fit: printed ticks vs catalogue, 250 m** | **yes: printed ticks** | **yes**: 741.5 m | Tri Binh (260923) | **yes**: confirmed by a 3-tick re-read (260930) | keep; the only position check that fired |
| 8 | Printed-tick audit on every sheet (branch `indochine-printed-audit`, 280ed7d6) | yes: printed ticks | yes on the control (+509 m / +544 m) | census of 11: 9 fail, 2 pass | **unproven**: the fails look like reader noise; a calibration sheet failed against a written prediction | fix: two-sided reader check first (not yet approved) |
| 9 | Random sample of cleared sheets, tick-read by a person (`paper-audit-100k`) | yes: a person reads the ticks | yes | not run | – | build: the only row that gives an error rate |
| 10 | Series index (`check_series_index.mjs`) | n/a | n/a: tests coverage | 0 faults over 706 cells (2026-09-20) | – | keep |
| 11 | `regress`: detector change must not move cleared sheets | n/a | n/a: tests code | proved one change safe (2026-09-24); later run "never reported a result" | – | fix: run it, log it |
| 12 | Self-tests (`--self-test`, `--self-check`) | n/a | n/a: tests code | pass | – | keep |

Evidence: rows 1–2, 5, 7 from `journals/260923-indochine100k-georef.md` and `paper/figures.md:216-220`; row 3 from `journals/260930-series561-handoff.md`; rows 8, 11 from branch `indochine-printed-audit`
(280ed7d6; the audit code is on that branch only) and its handoff note, which is local and not in the repo;
rows 10, 12 from `paper/claim-audit.md`.

## 3. The two counts that matter

- **Checks that could see a position error like Tri Binh's:** 3 of 12 (rows 7, 8, 9). Only row 7 has
  fired. It read 7 sheets, against 337 placed.
- **Firings confirmed as true catches:** 2 (rows 3 and 7). The other firings on record were never
  written up as right or wrong. A firing nobody judged is not yet evidence that the check works.

The question "can each check say what it would catch" does not fail: all 12 can. The test that can
fail is whether a check could have seen a known error. Rows 1–6, the ones that run on every sheet,
could not (row 6 is reasoned from the code, not run).

## 4. How to keep this up to date

When a check fires, add one line to its row: the date, and whether it was right (a person or a
second source decided). When someone adds a check, add a row first, with the question "could it
have caught Tri Binh?" Series other than 561 (325, L7014, Tonkin) are not in this table yet.
