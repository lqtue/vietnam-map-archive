# CLAUDE.md — the paper

*Blind by construction: verifying a georeferenced map series when the check shares the error.*
Loads when you open a file in `docs/paper/`. Repo-wide rules are in the root `CLAUDE.md`.

## Source of truth

- **`draft.md` is the only hand-edited manuscript.** `blind-by-construction.tex` and `.pdf` are
  generated; `submission.md` is generated from the draft so its abstract cannot drift. Never edit
  them by hand.
- Rebuild: `node scripts/render-paper.mjs`, then `cd docs/paper && tectonic blind-by-construction.tex`.
  The render also rewrites `figures/*.pdf` (needs `rsvg-convert`), so expect those in the diff.
- Every paragraph carries `<!--block:Bnnnn-->`. New blocks take the next free id (last used:
  **B0157**) and are not yet in `revision/draft.block-manifest.json`.
- The abstract, and any number it states, changes only through the ARS integrity chain recorded in
  `revision/` (issue list → authorization → patch → apply report). Do not edit it directly.

## Every number has a ledger row

`claim-audit.md` is the authoring record. A new or changed number gets a row with an evidence label:
**A** reproduced now from the repo · **B** recorded run, not reproduced · **C** checked against a
retrieved publication · **D** logical statement under stated inputs · **R** revise or remove.
Read `docs/lessons.md` before any pass that produces a number.

## Claim discipline (what reviewers have already pushed on)

- **Cases, not rates.** The paper reports documented cases and now synthetic fault injection. No
  prevalence claim without a random sample; §7.8 and §9 say what that sample would be.
- **`∅` is conditional.** It means "this fault cannot disturb this comparison under these shared
  inputs", and for `graticule_error` it holds for a datum *translation* only (§7.9).
- **Frame-relative, not absolute.** The adopted Helmert and the lattice built from it are the
  reference, so results show what a check detects against that frame. The corrected result is
  self-verified; do not call it validated or independent.
- **Say who ran it.** Checks and injections written and run by the author are labelled as such.
- **Predictions before runs.** Write what a test should show, in the script, before the first run,
  and report every cell that disagrees.

## Scripts and data

- `scripts/paper_fault_injection.py` → `fault-injection.json` (§7.9). `scripts/paper-seam-pairs.mjs`
  → the matched seam analysis (§7.3). Both are reproducible from `work/l7014/`.
- `work/l7014/` PDFs are gitignored and local only; the Zenodo deposit is not yet minted, so
  reproducibility is prospective until it is (§11, `submission.md`).
- Read the WGS 84 lattice from `work/l7014/lattice.json`. `series_cells.bbox` in the database holds
  the unshifted Indian 1960 corners (ROADMAP `series-sheets-bbox-datum`) and is wrong by 448–498 m.
- A sheet outline is a **MultiPolygon with slivers**; use every ring (`s.rings`), not the first.

## Before posting

Zenodo DOI minted and pasted into §11, render and tectonic re-run, PDF re-read. Open must-fix items
and the Session 4 review are in `revision/session4-review/editorial-decision.md`.
