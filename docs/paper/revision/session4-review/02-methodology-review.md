## Methodology Review Report (Peer Reviewer 1)

### Reviewer Identity
Photogrammetry/geodesy specialist working on datum-transformation QA for national mapping agencies, focused on accuracy-assessment protocols for scanned cartographic archives (Configuration Card #2).

### Overall Recommendation
Minor Revision

### Confidence Score
4

### Calibration Status
`NOT_CALIBRATED`

### Criterion-Bound Judgements
| Dimension / criterion | Criterion source | Judgement | Evidence anchors | Rationale | Uncertainty or scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Correctness of the datum/CRS technical account | field-general geodetic practice | MEETS | `text: "even a sheet explicitly labelled Indian_1960 could fail: the EPSG:4131 to EPSG:4326 operation returns the input unchanged outside its area of use."` (§7.4) | This is a well-known and correctly described PROJ/GDAL area-of-use failure mode; the mechanism is technically accurate | none identified | yes |
| Denominator/population bookkeeping | field-general | MEETS | `text: "The series index names 627 cells. 510 of those are held as GeoPDFs... 448 reach the graticule check after 62 files are excluded... The check rejects 11, leaving 437"` (§3) | Arithmetic is internally consistent (627→510→448→437) and cross-checked against Figure 3/Figure 6 | none identified | yes |
| Statistical reporting adequacy (descriptive, non-inferential) | `references/statistical_reporting_standards.md` — applied proportionally: this is a descriptive engineering audit, not an inferential-statistics paper | PARTLY_MEETS | `text: "These are descriptive comparisons within one series. Edges share sheets and are not independent replicates"` (§7.3) | The paper correctly avoids treating non-independent seam medians as inferential estimates with confidence intervals — appropriate restraint. But no dispersion measure beyond range/±spread is given for several key numbers (e.g., the 455 m median has a stated 395–528 m range but no IQR or count-weighted distribution shown in-text) | A full distribution likely exists in the underlying figures/scripts even if not narrated in prose; this is a reporting-completeness question, not a validity question | no — clarity improvement, not decision-bearing |
| Reproducibility of the core A/B comparison | field-general | MEETS | `text: "controlled A/B on one flag (l7014_mosaic.py warp --no-datum-shift)"` (claim-audit.md, corroborated by draft §7.6 dry-run description) | Single-flag controlled reproduction is a sound design for isolating the datum-shift effect specifically | Only verifiable from the companion `claim-audit.md`, which is not part of the manuscript itself — the manuscript should state the controlled-flag design explicitly | yes |
| Arithmetic recompute (GRIM/GRIMMER/p-from-statistic/n-from-df applicability) | `references/statistical_reporting_standards.md` § Bounded Arithmetic Recompute Procedures | NOT_ASSESSED — `no_recomputable_statistics` | — | The paper reports no p-values, test statistics, means with independently stated N for a bounded scale, or degrees of freedom subject to the four bounded recompute procedures; it reports raw counts, medians and ranges over enumerated populations, which are not covered by GRIM/GRIMMER/p-recompute/n-from-df | This paper's evidentiary structure is closer to a system audit than a hypothesis test; the recompute procedures are simply out of scope here, which is itself worth noting so a reader does not expect them | no |

### Summary Assessment
The core technical claim — that a geographic-CRS-internal graticule check cannot detect a downstream datum-transformation fault because both operands share the untested transformation — is mechanistically sound and precisely stated (§7.4, Figure 1). The specific failure modes described (an unmapped NGA `LGIDict` datum label falling back to WGS 84 silently; `EPSG:4131`→`EPSG:4326` returning inputs unchanged outside PROJ's area of use; a subsequent axis-order transposition bug that then rejected 370/437 *correctly* re-datumed sheets) are all real, well-known classes of GIS pipeline defect, described with enough operational detail (`CloneGeogCS`, explicit Helmert parameters, quarter-degree snapping fallback) to be credible and largely reproducible in principle. The population bookkeeping (627→510→448→437, and the parallel Indochine 79→75→62/58/83 chain) is internally consistent across the text, Table/Figure captions, and cross-referenced figures. The paper is appropriately restrained about statistical inference given non-independent, small, enumerated populations — it does not manufacture confidence intervals or significance tests it cannot support, which is the correct choice for this evidentiary structure. The main methodological gaps are: (1) the controlled single-flag A/B design that underlies the central before/after comparison is described in the companion `claim-audit.md` but not stated explicitly in the manuscript itself, which is where a methodology reviewer needs to find it; and (2) the `pick_crs` 150 m threshold (§7.5) is stated but its derivation/sensitivity is not discussed — is 150 m calibrated against anything, or a round-number choice?

### Strengths
1. **Precise, falsifiable mechanism statement**: Figure 1's "add the same shift to both quantities and their difference does not change" is stated both intuitively and then demonstrated with a real numeric exhibit (`2.167e-12` at A Lưới). `equation: Figure 1 caption + text: "returns 2.167e-12 on a sheet it places correctly (§7.4)"`
2. **Self-correcting methodology narrated transparently**: The paper reports its own second-order bug (the axis-order transposition rejecting 370/437 corrected sheets) rather than only the headline result. `text: "370 of 437 sheets were rejected — the datum fix thrown out by the check it was meant to supersede"` (§7.4)
3. **Appropriate statistical restraint**: Explicit refusal to treat non-independent seam-edge samples as independent replicates. `text: "Edges share sheets and are not independent replicates; their distances do not measure absolute accuracy or content alignment."` (§7.3)
4. **Matched-pair design for the before/after seam comparison**: Matching by unordered sheet-ID pair to separate geometry change from population-membership change is a sound control. `text: "we matched edges by their unordered sheet-ID pair. All 715 corrected edges occur in the faulty census."` (§7.3)

### Weaknesses
1. **A/B controlled-design statement is missing from the manuscript itself**: The single-flag reproduction design (`l7014_mosaic.py warp --no-datum-shift`) that underlies the entire before/after comparison in §7.3/§7.6 is documented in the companion `claim-audit.md` but not stated in the manuscript text. A reader of the paper alone cannot verify that "faulty" vs. "corrected" differ by exactly one isolated variable rather than by an unstated bundle of changes.
   - **Severity**: Major | **Evidence Anchor**: `absence: §5/§7.6 — expected an explicit statement of the controlled-comparison design (single flag, no other pipeline changes); checked §5 (method description), §7.3, §7.6 (before/after results)` | **Confidence**: 4 — directly comparing manuscript text against the corroborating audit file
2. **`pick_crs`'s 150 m acceptance threshold is unmotivated**: §7.5 states the candidate is selected "only if that score is at most 150 m," with no stated derivation, sensitivity analysis, or comparison against the roughly-15-m index-to-outline agreement figure reported two sentences later — an order-of-magnitude gap between the acceptance threshold and the reported agreement scale that the text does not explain.
   - **Severity**: Minor | **Evidence Anchor**: `text: "It selects the candidate with the smaller score only if that score is at most 150 m."` (§7.5)` — **Confidence**: 3 — plausible the threshold is a conservative safety margin rather than a defect, but the paper does not say so
3. **No sensitivity/robustness check on the seam census's 25-sample-point, 10–90%-of-length design**: §7.3 states the sampling scheme precisely (25 points, avoiding corner junctions) but does not report whether the reported medians are stable under a different sample count or window — a minor robustness gap for a measurement that carries most of the paper's before/after evidentiary weight.
   - **Severity**: Minor | **Evidence Anchor**: `absence: §7.3 — expected a stated sensitivity check on the 25-point / 10–90% sampling design; checked §7.3 method description in full` | **Confidence**: 3

### Detailed Comments

#### Research Questions & Hypotheses
Implicit rather than stated as formal hypotheses, which is appropriate for this genre (documented-incident + taxonomy paper, not a controlled experiment testing a stated hypothesis).

#### Research Design
Sound: a real production failure, a controlled single-variable reproduction, and a second independent series (Indochine) providing complementary evidence (lattice collision rather than datum shift) for the general taxonomic claim.

#### Sampling Strategy
The L7014 population is the full available corpus (627 cells, not a sample), which is appropriate — this is a census, not a survey, and the paper correctly treats it as such.

#### Data Collection
Embedded GCPs, printed graticule coordinates, and OCR'd corner labels are all well-specified. The Indochine OCR + grades-to-degrees conversion (§6) is described with enough precision (0.9 multiplier, 2.3372° Paris offset) to be checked independently.

#### Analysis Methods
Descriptive statistics over enumerated, non-independent populations — appropriate given the evidentiary structure; see Criterion-Bound Judgements row on statistical reporting.

#### Results Presentation
Complete and non-selective: §8 ("Negative results") is an unusually thorough disclosure of checks that did not pan out (river-position correlation, toponym lookup, ink-density correlation), which is a strength worth naming explicitly here even though it belongs formally under Strengths above.

#### Reproducibility
Code and derived data are promised (§11) but not yet deposited at draft time — see the Journal-Fit Reviewer's Weakness 1, which this reviewer corroborates from the methodology side: reproducibility of the actual numbers cannot currently be independently checked by an external methodology reviewer.

#### Methodological Fallacies Detected
None of the checklist fallacies (p-hacking, ecological fallacy, Simpson's paradox, survivorship bias, confirmation bias, overfitting, reverse causation, multicollinearity, endogeneity) apply cleanly to this paper's evidentiary structure; it is a systems audit, not a hypothesis-testing study, and the paper does not misuse inferential-statistics framing to claim more than a census supports.

### Questions for Authors
1. Can the manuscript state explicitly, in §5 or §7.6, that the faulty/corrected comparison isolates exactly one pipeline flag (`--no-datum-shift`) with no other concurrent change?
2. What determined the `pick_crs` 150 m acceptance threshold — is it calibrated against the archive's own measurement noise floor, or a conservative round number?

### Minor Issues
- §7.5: "at most 150 m" and the later "approximately 15 m scale of the reported index-to-outline agreement" would benefit from one explicit sentence connecting the two numbers (why the gate is ~10x looser than the typical agreement observed).
