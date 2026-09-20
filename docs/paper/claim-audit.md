# Claim and evidence audit

**Audit date:** 2026-09-20. This is an authoring record, not paper prose. It prevents a useful
archive incident from becoming an unwarranted priority or generalisation claim.

## Evidence labels

| label | meaning |
|---|---|
| A | reproduced in this audit from the current repository or production service |
| B | recorded run and source file exist, but the result was not reproduced in this environment |
| C | checked against a retrieved publication, including editorial-notice screening in Scite |
| D | logical statement under explicitly stated inputs; not an empirical prevalence claim |
| R | revise, qualify, or remove before submission |

## Reproduction ledger

| claim or number | status | current evidence | consequence for draft |
|---|---|---|---|
| catalog: 274 maps, 252 published, 174 IIIF sources, 160 jobs, 21 queued | A | `node --env-file=.env scripts/catalog_audit.mjs --quiet`, 2026-09-20 | Reproduced live totals; do not substitute them for the older OCR/gazetteer/footprint counts. |
| L7014 461 held/627; Indochine 75/79; 0 adrift/dangling/unindexed over 706 cells | A | `node --env-file=.env scripts/check_series_index.mjs`, 2026-09-20 | Reproducible live coverage. |
| 274 maps and 253 usable GCP sets | A | `node --env-file=.env scripts/geo_audit.mjs --quiet`, 2026-09-20 | Reproduces a current inventory only. |
| L7014 A/B: 437 denominator, fault population, displacement, seam census | A — **resolved 2026-09-20 (ARS round 1)** | re-run 2026-09-20, `work/l7014/regen/REGEN.md`; controlled A/B on one flag (`l7014_mosaic.py warp --no-datum-shift`) | Reproduced, but several numbers move: fault population **276** (`fit`) / **269** (CRS displacement), not 285; displacement **395–528 m, median 455**, not "~470"; seams **717**, median **9.2 m**, **97** over 300 m, not 750 / 19 m / 56. Draft now states the full 510→62→448→11→437 denominator chain (F1) and the matched-pair 189→0 result (F4). |
| revised hand-to-mosaic seam census | A — **resolved 2026-09-20 (ARS round 1)** | `scripts/l7014_hand.py` + `regen/seams-faulty-hand.csv`, 2026-09-20 | The earlier claim does not reproduce. **36** such seams span **1.8–446.2 m**, none in the 447–504 m band. A seam returns only the component normal to the shared edge: median **438.0 m** E/W, **133.7 m** N/S, recombining to **457.9 m** against a median CRS displacement of 454.9 m. Draft §7.3 now reports the revised result. The 25 JPG/JPG seams (0.0–0.6 m) are no longer treated as free-seam evidence (F3): `l7014_hand.py` derives both sides from the same lattice ground corners. |
| hand sheets are not a free seam | A | `corners` writes the lattice cell as the ground half of every hand control point | A `jpg / pdf` seam measures the PDF sheet's departure from its cell, so it is not the independent join §7.3 opens with. The free comparisons include 715 `pdf / pdf` and 25 `jpg / jpg` (**0.0–0.6 m**). Draft §7.3 identifies the distinction. |
| A Lưới `graticule_error = 2e-12` | B + D | recorded in `docs/pipelines.md`; zero mechanism follows when the same datum translation is applied to both operands | Case-study exhibit, not evidence of prevalence elsewhere. |
| Indochine lattice, `Ha Noi` collision, neatline/rim readings | B | `allmaps-series-note.md`, surfaced by `figures.md` | Include provenance artifacts in the release package. |
| fixture and geometry invariants | A | `catalog_audit --self-check`, `check_series_index --self-check`, `geo_audit --self-test`, `georef_error.py --self-check` all passed | These validate code behavior, not production measurements. |

## Claims that survive, claims that need limits

| location | claim | status | required wording |
|---|---|---|---|
| §1/§3 | 514 processed sheets | B — **resolved 2026-09-20 (ARS round 1)** | State it is the recorded run ledger and distinguish it from current annotation availability. Draft now marks the 452 L7014 count as a hand-maintained publication constant, not verified against a serving manifest (F5). |
| §2.1/§7.4 | common frame error is invisible to a self-check using that same frame | D | State the common-input condition; do not say every lattice check is blind. |
| §2.2 | an imposed seam has zero residual in its fitted representation | D | It says nothing by itself about independent external accuracy. |
| §2.3 | “most developed” per-sheet battery | A | Removed: the review cannot establish field priority. |
| §7.1 | `∅` “cannot fail by construction” | D | The draft states the shared-input condition; this is not a universal assertion about all implementations. |
| §7.2 | duplicate occupancy | D | A review flag; it may be an intentional alternative edition, a printed anomaly, or a transcription error. |
| §7.3 | “first inexpensive indication” | B | Limited to “first ... in this archive.” A free seam detects differential disagreement, not a common translation. |
| §9 | “pattern generalises” | D | Replaced with “reasoning may apply where stated structural conditions hold.” |
| §10 | Zenodo release | B | Explicitly prospective until the DOI and artifacts exist. |

## Literature screen and novelty boundary

The targeted review covered multi-sheet registration, accuracy evaluation, independent
control/landmark checks, reference frames, and sheet boundaries. It is a focused review, **not an
exhaustive systematic review** and therefore cannot prove absence of prior conceptual work.

- Lattice/corner and adjacency information are already used in series georeferencing and adjustment
  (Luft & Schiewe, 2021; Janata & Cajthaml, 2020) [C].
- Independent control/landmark or reference-frame evaluation is established practice; this paper
  does not invent it (Bozzano et al., 2024; Ingensand et al., 2022; Xu et al., 2026) [C].
- Recent work reports gaps, overlaps, and persistent feature misalignment after georeferencing
  (Piškinaitė & Veteikis, 2023; Wang et al., 2022) [C].
- Kuna et al. (2024) closely supports the narrower point that good geometric parameters do not by
  themselves establish a correct reference-frame relationship [C].

The contribution that survives the screen is a documented archive case with a large shared datum
displacement and a self-check predictably silent under named shared inputs, plus a compact taxonomy
of check scope, already-committed inputs, detectable faults, and blind spots. It is not the first
use of lattices, seams, independent checkpoints, or external validation, nor evidence that the
observed magnitude or frequency applies generally.

## Reference metadata verification, 2026-09-20

All thirteen DOI-bearing entries in the draft's reference list were resolved against stored
publisher metadata and screened for editorial notices. **None carries a retraction, correction or
expression of concern.** Three defects were found and fixed:

| defect | detail |
|---|---|
| wrong title on the most-used reference | Luft & Schiewe (2021) was cited as "Automatic georeferencing of historical maps by content-based image retrieval"; the published title is "Automatic content-based georeferencing of historical topographic maps". The first author's initial was also wrong (T. → J.). |
| a named work with no reference | §2.4 named the ICDAR MapText competition with no entry. Added Li et al. (2024), `10.1007/978-3-031-70552-6_22`. |
| an entry cited by system name only | mapKurator appeared without an author-year, leaving Kim et al. (2023) listed but never cited. Now cited in text. |

**The Janata & Cajthaml year is resolved, and 2020 is correct.** The doubt was that *Applied
Sciences* 11(1) is a 2021 volume, and MDPI's house citation style accordingly prints "Appl. Sci.
2021, 11, 299". That is a volume-year display convention, not a publication date. The publisher's
own Crossref deposit records `issued` and `published-online` as **2020-12-30** and carries no print
date at all, and Crossref's APA formatter returns the year 2020 directly. OpenAlex, Semantic
Scholar, Unpaywall and Scite all resolve the same date, and a reader following the DOI arrives at
an article stamped 30 December 2020. The draft already reads 2020 in all six places — the four
in-text mentions, the Table 1 row and the reference entry — so nothing changed.

## Submission requirement

Before submission, deposit immutable or regenerable versions of the L7014 lattice, mosaic GeoJSON,
source-manifest hashes, raw seam table, `fit` and correction dry-run outputs, and exact commit /
environment commands. Until then, label B rows as recorded runs.
