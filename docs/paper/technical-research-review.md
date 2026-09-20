# Technical paper: evidence audit and proposed revision

20 September 2026. ARS-Codex argument/evidence analysis, executed inline. This is an advisory research and revision proposal, not an independent review panel, venue-alignment verdict, or completed ARS integrity gate. No target venue was inferred.

## Main finding

The central case survives a stricter test: the large seam-displacement tail disappears on the same edges, not merely after two edges disappear from the corrected build. However, the draft overstates the independence of its CRS-selection check. The reference lattice and the alternative candidate share Helmert parameters. The paper should distinguish improved internal agreement, consistency with an adopted frame, and independently established absolute accuracy.

The current manuscript and PDF have not been changed. The exact replacements below are also stored in [technical-revision-proposal.json](technical-revision-proposal.json), bound to draft SHA-256 `fd3efd18fa2e7c576270459e156068aa9378aa686c707b3bea16442c3e1a0eda`. Author decisions are pending; no approval was inferred or fabricated.

## New analysis: matched seams

Executed `node scripts/paper-seam-pairs.mjs` on the saved CSVs. Complete measurements and input hashes are in [seam-paired-analysis.json](seam-paired-analysis.json). A separate Python CSV calculation reproduced the overlap, thresholds, medians and excluded pairs.

| Quantity | Faulty | Corrected |
| --- | ---: | ---: |
| Full-build PDF/PDF edges | 717 | 715 |
| Matched PDF/PDF edges | 715 | 715 |
| Matched edges above 100 m | 189 | 0 |
| Matched edges above 300 m | 97 | 0 |
| Median of matched edge medians | 9.1843 m | 6.7831 m |
| Largest matched edge median | 519.2661 m | 72.4066 m |

The two faulty-only pairs are `6145-1 / 6146-2` (3.6184 m) and `6146-2 / 6146-3` (15.6022 m). All corrected edges occur in the faulty census. Excluding these two small distances cannot explain disappearance of the tail.

The median paired change is only −0.0335 m. This is a different statistic from subtracting the cohort medians; do not describe 9.2 minus 6.8 as the typical per-edge improvement. The result is concentrated in the large tail. Edges share sheets, so no independent-observation confidence interval or significance test is claimed. No warps were rerun.

## Findings requiring manuscript corrections

### Rejection denominator

`work/l7014/regen/warp-faulty.log` ends with `nogeo=62, offgrid=11, ok=437`. Of 510 inputs, 448 reach the graticule gate; 11 fail and 437 survive. “Rejected 11 of 437” is false. The input ledger and faulty manifest separately confirm that all 269 displaced probe rows are among the 437 retained sheets; their recorded displacement range is 394.79–527.72 m.

### Reference independence

In `scripts/l7014_mosaic.py`, both `indian_1960_geog` (used by `cell_corners`) and `indian_1960_utm` (the alternative in `pick_crs`) use `INDIAN_1960_PROJ4`. The lattice is separate from each PDF declaration but shares the alternative's datum transformation. It cannot validate those parameters independently. An independent checkpoint study remains necessary for an absolute-accuracy claim; no such study was performed here.

The implementation scores registration points, not two newly warped rasters: for each expected corner it finds the nearest transformed registration point, then averages those distances. It chooses the minimum candidate score if at most 150 m. When all scores are unavailable it keeps the declared/fallback CRS. The existing prose's unconditional refusal claim misses this case.

### Hand-sheet joins

`scripts/l7014_hand.py:ground_quad` reads the control points' ground coordinates (or supplied ground quad); it does not measure independently warped image boundaries. Both JPG/PDF and JPG/JPG joins therefore inherit the lattice-derived control. The 0.0–0.6 m JPG/JPG result is consistency of the supplied boundaries, not free image-registration evidence. The earlier `REGEN.md` interpretation calling JPG/JPG free is superseded by this code inspection; retain it as a historical run note, not current evidentiary authority.

### What the seam statistic measures

`scripts/l7014_seams.py:measure_edge` samples 25 positions along the central 80% of an expected shared edge, compares nearest outline points, and reports the median and maximum. Census summaries use each edge's median. This measures outline agreement, not matching roads or buildings. The normal-component explanation is appropriate for nearly straight parallel edges, not a universal displacement estimator.

### Published population and method-comparison claims

The missing live manifest prevents the 269/437 reproduction result from being treated as an exact census of published sheets. The reported 514 total includes the unverified 452 publication constant. Keep those publication claims distinct from the measured build populations.

No evidence inspected here establishes that MapEdge was run on Ha Noi. The comparison can explain why internal geometric agreement is insufficient, but cannot report an observed pass from that implementation. An independent expected-cell reference can detect individual misplacement; “per-sheet” alone does not imply blindness.

## External documentation checked

[PROJ's operation-selection documentation](https://proj.org/en/stable/operations/operations_computation.html) explains that selection depends on available operations, areas of use, grids and runtime coordinates, and may include ballpark operations. The draft's coordinate probes should be reported as results for its recorded environment, not a universal promise about every EPSG:4131 transformation. [GDAL's coordinate-system tutorial](https://gdal.org/en/stable/tutorials/osr_api_tut.html) is the primary reference for axis mapping. No fresh full-bibliography or retraction screening was performed in this pass.

## Application and remaining work

Approve, revise or decline the exact replacements below before manuscript mutation. On approval, replay them against the bound draft, update the affected figure/number ledger and submission abstract, regenerate the existing TeX/PDF, and inspect the output. Figure 5 can keep its existing full-build bars; its proposed caption explicitly adds the matched analysis.

Further items remain before submission: audit every conditional Table 1 capability against its stated inputs; document an independent absolute-reference protocol if absolute accuracy is claimed; retain dated serving-state observations rather than replacing them with an unperformed live audit; complete the immutable evidence deposit. The proposal does not claim submission readiness.

ARS authority requirement: the installed [SKILL.md](/Users/airm1/.codex/skills/academic-research-suite/SKILL.md) states, “Only an explicit author adjudication may authorize exact choices or integrity-correction targets.” These are scientific-claim changes, so this file supplies reviewable exact replacements without manufacturing that adjudication.

## Exact proposed replacements

Each item replaces one uniquely matched span in the current draft. The JSON retains both old and new bytes; this reading copy shows the proposed text and reason.

### R1

Correct the rejection denominator; make the matched-edge result central; bound the CRS-independence claim and remove the unverified 514-sheet headline.

```markdown
Historical map series often supply their own georeferencing control, but agreement with that
control does not independently establish placement. We examine this problem through a documented
Vietnam Map Archive failure and a controlled reproduction on US Army Map Service L7014 GeoPDFs.
Of 510 source files, 62 lacked usable control, 11 failed the graticule check, and 437 entered the
faulty build. All 269 sheets with reproduced CRS displacements of 395–528 m (median 455 m)
passed that check. The check evaluates registration in the sheet's own geographic CRS and cannot
validate the subsequent datum transformation to WGS 84. Comparing the same 715 PDF/PDF edges
before and after correction, the number with median outline separation above 100 m falls from
189 to zero. This establishes improved inter-sheet agreement, not independent absolute accuracy:
the CRS-selection check and comparison lattice share the adopted Helmert parameters. A second
case, from the Service géographique de l'Indochine 1:25,000 series, shows why coherent corner
readings can still assign two sheets to the same cell. Together these cases support a taxonomy of
verification scope, committed inputs, detectable faults, and blind spots. The contribution is a
reproducible account of how checks can remain silent under specific shared assumptions, with
explicit separation of source control, build measurements, and serving-state evidence.
```

### R2

Separate reported holdings/publication totals from observed experimental populations.

```markdown
The corpus comprises a Cold-War and a colonial Vietnamese sheet series. L7014 is the US Army
Map Service 1:50,000 coverage of Vietnam, held as GeoPDFs by the Perry-Castañeda Library at the
University of Texas at Austin. The second is the Service géographique de l'Indochine 1:25,000
coverage of Tonkin and Thanh Hóa, held by Cartomundi at Aix-Marseille Université/CNRS. The archive
previously reported a combined total of 514 sheets, comprising a 452-sheet L7014 publication
count and 62 pipeline-georeferenced Indochine sheets. Because the 452 is a hand-maintained
publication constant that cannot be checked against the missing serving manifest (§7.6), the sum
is an archive-reported total, not a verified count of processed or currently served sheets. The
measured populations below supply the denominators for the results. The L7014 material dates from
the 1960s–70s; the Indochine material from 1903–1927.
```

### R3

510 minus 62 is 448; the 11 rejected files are outside the 437 retained files. OFFGRID is a graticule verdict, not the separate cell-fit verdict.

```markdown
**448** reach the graticule check after 62 files are excluded for missing control. The check rejects
11, leaving **437** successfully warped files in the faulty build, and
```

### R4

Specify the actual estimator, sampling, distance approximation, threshold status and observational unit.

```markdown
### 7.3 The seam census

The census measures outline agreement rather than continuity of roads or other map content.
The lattice identifies shared edges but does not constrain the PDF outlines. For each edge,
`l7014_seams.py` samples 25 equally spaced positions between 10% and 90% of its length,
avoiding corner junctions. At each position it finds the nearest point on each outline and measures
their separation using a local longitude/latitude-to-metre approximation. The edge statistic is
the median of these distances; the reported census median is the median across edges. The 100 m
and 300 m cutoffs summarize the observed tail, rather than define independently calibrated
acceptance thresholds. For nearly straight parallel edges the distance principally reflects
normal separation; it need not recover along-edge displacement or a full displacement vector.


```

### R5

The hand manifest does not independently warp raster content; the inherited REGEN note's JPG/JPG independence claim conflicts with code.

```markdown
The hand-sheet comparisons must be distinguished from the free PDF/PDF comparisons. The hand
workflow supplies lattice-derived ground corners, and the hand manifest is assembled from those
ground coordinates rather than independently measured warped image boundaries. A JPG/PDF join
therefore compares a PDF outline with a lattice-derived boundary. A JPG/JPG join compares two
such boundaries. The 25 JPG/JPG distances of 0.0–0.6 m describe consistency of those ground
coordinates, not an independent validation of either image registration. Only the PDF/PDF cohort
is used as free-seam evidence here.
```

### R6

New independently cross-checked matched-edge analysis rules out attrition as explanation for tail disappearance.

```markdown
The two builds differ in the CRS-selection flag and in which files survive the checks. The faulty
build contains 717 PDF/PDF seams, of which 189 exceed 100 m and 97 exceed 300 m. The corrected
build contains 715, none above 100 m (Figure 5). To separate change in geometry from change in
membership, we matched edges by their unordered sheet-ID pair. All 715 corrected edges occur in
the faulty census. On these same edges, 189 fall from above 100 m to at most 100 m, with no
crossings in the opposite direction; the maximum corrected edge median is 72.4 m. The two
faulty-only edges measure 3.6 m and 15.6 m, so their exclusion cannot explain disappearance of
the large-displacement tail. Matched-cohort medians are 9.2 m before and 6.8 m after correction.

These are descriptive comparisons within one series. Edges share sheets and are not independent
replicates; their distances do not measure absolute accuracy or content alignment. The matched
analysis, input hashes and excluded pairs are reproducible with `scripts/paper-seam-pairs.mjs`.
```

### R7

Preserve Figure 5's full-build bars while connecting them to the matched analysis.

```markdown
A matched analysis of the 715 common edges also gives 189 versus zero above 100 m (§7.3).
A small median (9.2 m before, 6.8 m after) alone would obscure the faulty build’s large tail.
```

### R8

Correct the incompatible rejection and retained-build denominators.

```markdown
Our existing `graticule_error` check did not report it. In the faulty pass, 448 files reached
the check after 62 were excluded for missing control. It rejected 11 and retained 437, including
all 269 with reproduced CRS displacements of 395–528 m.
```

### R9

Describe code rather than treating shared translation as a literal universal implementation model.

```markdown
The implementation converts registration coordinates into the candidate CRS's own geographic
coordinate system (`CloneGeogCS`) and compares their extrema with the sheet's graticule
metadata, or with quarter-degree snapping when those metadata are absent. That calculation does
not independently test the subsequent transformation to WGS 84. It can reject inconsistent
registration while remaining insensitive to the omitted datum transformation at issue here.
The `∅` in Table 1 denotes this fault's inability to disturb the comparison; it does not mean
the check must return zero when other errors are present.
```

### R10

Direct code inspection reveals shared Helmert parameters, nearest-registration score, 150 m cutoff and no-score fallback.

```markdown
### 7.5 CRS selection against an adopted frame

The corrected route adds `pick_crs` before the graticule check. It scores the declared or
fallback CRS and, where available, an Indian 1960 alternative with explicit Everest 1830
(1937 Adjustment) Helmert parameters. For each candidate, it transforms the registration
coordinates to WGS 84 and averages, over the expected cell corners, the distance to the nearest
transformed registration point. Registration coordinates come from embedded GCPs, with neatline
vertices as the fallback. It selects the candidate with the smaller score only if that score
is at most 150 m. If every available candidate exceeds that threshold, it rejects the sheet.
If no score can be computed, however, the implementation retains the declared or fallback CRS;
this case is not verified by the lattice decision.

The reference is external to an individual GeoPDF declaration, but it is not independent of the
adopted datum transformation. `cell_corners` transforms the index coordinates with the same
explicit Helmert parameters used by the alternative candidate. Agreement therefore tests
consistency with the adopted frame and can expose a missing transformation, while a shared
error in those parameters could remain undetected. The result does not establish absolute
accuracy at the approximately 15 m scale of the reported index-to-outline agreement. Testing
that claim would require appropriately distributed reference positions whose coordinates were
not generated by the same transformation.

This distinction preserves the useful result without giving the selection rule a broader
authority than its inputs support. Refusal catches cases outside the scored alternatives;
agreement identifies a compatible interpretation conditional on the adopted frame.
```

### R11

External accuracy evidence is not supplied by shared-parameter lattice selection.

```markdown
Use reference positions independent of the adopted transformation when absolute placement is
the claim to be tested. The `pick_crs` decision provides a narrower consistency check (§7.5).
```

### R12

Do not equate a local reproduction with a verified live publication count or claim all displaced sheets had a measured zero residual.

```markdown
A controlled reproduction of the archive's faulty route retained 437 sheets, including 269 with
CRS displacements of 395–528 m that passed the graticule check. That check cannot independently
validate the transformation from the sheet's geographic CRS to WGS 84. On the same 715 PDF/PDF
edges, correction reduced the number above 100 m from 189 to zero. The comparison establishes
improved outline agreement. CRS selection against the lattice supplies a separate test of
consistency with the adopted Helmert transformation, whose absolute accuracy remains to be
independently assessed. These build measurements do not establish the exact population or
accuracy of the serving archive.
```

### R13

Capability matrix is conditional, not a measured sensitivity benchmark or universal guarantee.

```markdown
Legend: **✓** can flag it under the stated inputs · **·** not established as a diagnostic here ·
**—** not applicable · **∅** the specified fault cannot disturb the constrained or shared-input
comparison ·
```

### R14

Actual implementation scores points, shares datum parameters and has a missing-score fallback.

```markdown
| **`pick_crs`** — registration points scored against the adopted cell (§7.5) | per-sheet + index | · | **✓ ‡** | · | · | — |
```

### R15

Carry the reference-dependence qualification directly with Table 1.

```markdown
**‡** Detects disagreement with the adopted frame when a cell score is available. The candidate
and reference cell share Helmert parameters; the decision does not validate those parameters
against independent absolute control. Table entries describe diagnostic scope, not measured
detection rates from running the published methods on this corpus.

Three cells carry the argument, and each is sourced to a different paper's own design.
```

### R16

Propagate the corpus qualification into the introduction.

```markdown
The archive reports 514 sheets across these routes, but that total includes an unverified
publication constant (§3). We therefore report each audit's measured population separately.
```

### R17

Distinguish a structural comparison from a benchmark that was not run.

```markdown
These checks concern per-sheet geometry. Our §7.2 example has internally coherent readings
while occupying another sheet's cell. We did not run the MapEdge implementation on that sheet;
the comparison concerns the scope of internal geometric checks, not an observed MapEdge verdict.
```

### R18

Remove categorical claims excluding independent per-sheet reference checks.

```markdown
Third, the internal per-sheet checks listed here do not establish unique occupancy.
The `Ha Noi` example has coherent internal readings but conflicts with another sheet's
cell assignment (§7.2). This is a scope argument, not a measured result from running
MapEdge on `Ha Noi`. A check supplied with an independently verified sheet-to-cell assignment
could detect a misplaced sheet individually; internal geometry alone cannot establish that assignment.
```

### R19

Propagate the unrun-method qualification into the case study.

```markdown
These observations establish the limits of internal consistency, without claiming an observed
pass from the MapEdge implementation described in §2.3.
```

### R20

Replace an unmeasured prevalence claim with the supported conditional claim.

```markdown
> A verification instrument can remain insensitive to an error shared by its inputs or removed
> from its residual by an imposed constraint. Interpreting its residual therefore requires
> stating the comparison, the committed assumptions, and the faults capable of disturbing it.
```

### R21

The difference between marginal counts is not itself an individually matched transition count.

```markdown
with a net increase of 273 on-cell sheets across the two builds.
```

---

## Applied — 2026-09-20

All 21 operations above (R1–R21) were accepted and applied through the ARS integrity-correction
chain, run natively via the Claude Code plugin (ARS 3.22.0). The author adjudicated by family, not
by individual operation:

| Family | Ops | Verdict |
|---|---|---|
| F1 · Rejection denominator | R3, R8, R16 | Accept |
| F2 · CRS-selection independence | R9, R10, R11, R14, R15 | Accept |
| F3 · Hand-seam independence | R5 | Accept |
| F4 · Seam statistic + matched analysis | R4, R6, R7, R21 | Accept |
| F5 · Population and unrun methods | R2, R13, R17, R18, R19, R20 | Accept |

All four families feeding R1 (abstract) and R12 (conclusion) were accepted, so both composite spans
applied verbatim — no hand-rewrite was needed.

- Base draft: `fd3efd18fa2e7c576270459e156068aa9378aa686c707b3bea16442c3e1a0eda`
- Applied draft: `468fabf99cc49091b607ee1d81386e820855f0800da4a2ed56bc5bbd0420316d`
- Chain evidence: `docs/paper/revision/integrity-issue-list.json` (20 corrections bundling the 21
  ops — R8/R9 share one correction, targeting the same source block),
  `integrity-authorization-round1.json`, `revision-patch.json`, `draft.r1.apply-report.json`
  (22 patch ops after R10's heading+2-paragraph span split into replace+delete+delete; 114/136
  blocks preserved byte-identical).
- The applier's §3.6 structural checkpoint fired on two heading-touching ops (R4's block-local
  insert, R10's actual section rename from "The outside opinion" to "CRS selection against an
  adopted frame") and was acknowledged — section count was unchanged and touched-ratio (0.16) was
  well under the 0.6 threshold.
- `check_revision_token_conservation.py` ran as an advisory pass only; all deltas were expected
  denominator/threshold numbers, nothing flagged as unconserved.
- `docs/paper/technical-revision-proposal.json` now records `status: APPLIED`.

Session 1 (adjudication) and Session 2 (apply) of `/Users/airm1/.claude/plans/use-ars-to-improve-spicy-papert.md`
are complete. Next: Session 3 — propagate to `figures.md`, `submission.md`, `visual-plan.md`,
`claim-audit.md`, then rebuild the PDF.
