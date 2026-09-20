## Journal-Fit Review Report

### Reviewer Identity
GIScience preprint-server screening editor / secondary reviewer for *Transactions in GIS* and *ISPRS IJGI*, specializing in spatial-data-quality methodology and historical-map digitization pipelines (Configuration Card #1).

### Overall Recommendation
Minor Revision

### Confidence Score
4 — high confidence; outside deep geodetic/statistical technical review, which is R1's remit.

### Calibration Status
`NOT_CALIBRATED`

### Criterion-Bound Judgements
| Dimension / criterion | Criterion source | Judgement | Evidence anchors | Rationale | Uncertainty or scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Topical fit for an Earth Sciences / GIScience preprint readership | field-general (`criteria_binding_unavailable`, no confirmed venue) | MEETS | `text: "Historical maps are increasingly available as scans, but a scan becomes spatially useful only when it can be placed, queried and compared with other maps."` (§1) | Squarely within spatial-data-quality / cartographic verification | none identified | yes |
| Structural coherence (title→abstract→conclusion) | field-general | MEETS | `text: "It is the bookkeeping: a verification check has a scope and a set of inputs it has already committed to"` (§10) | Conclusion directly restates and narrows the abstract's claim; no over-promise/under-deliver gap found | none identified | yes |
| Originality relative to cited prior work | field-general | PARTLY_MEETS | `text: "Our claim is deliberately narrow. Series self-consistency is not new, and neither are lattice or adjacency checks."` (§1) | The paper is unusually candid that its individual instruments are not novel; the claimed contribution is the *taxonomy* + a documented real-world failure. This is a legitimate but modest contribution class | Whether "documented a real failure + built a taxonomy" clears a given venue's novelty bar is venue-specific and cannot be assessed without a confirmed target | yes |
| Readiness for submission (completeness, polish) | field-general | PARTLY_MEETS | `absence: §11 Data and code availability — expected a minted Zenodo DOI; checked §11 text and submission.md checklist` | §11 explicitly states the DOI "is intentionally not fabricated in this draft and will be inserted only after the archive record is minted"; `submission.md` has an unchecked box for exactly this | This is a known, already-tracked pre-submission gap, not a newly discovered defect | yes |

### Summary Assessment
The paper is well-scoped for an Earth Sciences / GIScience readership and reads as unusually mature for a pre-submission draft: it carries its own internal claim-audit, a figures ledger, and a submission checklist. Title, abstract and conclusion agree with one another, and the central claim — that a verification check can be structurally blind to an error class because it shares an assumption with the thing being checked — is stated with consistent scope-discipline throughout (the paper repeatedly refuses to generalize past what it measured). Novelty is modest and honestly disclosed: the individual instruments (lattice residual, seam census, CRS-selection scoring) are each acknowledged as non-novel, and the contribution rests on the taxonomy (Table 1) plus the documented real-world incident. That is a legitimate, if narrower, contribution class for a methods/practice paper, and the self-disclosure of one's own system's fault gives the paper an evidentiary weight that a purely synthetic demonstration would lack. The main readiness gap is procedural rather than intellectual: the manuscript's own reproducibility claims (abstract: "a reproducible account") rest on a Zenodo deposit that does not yet exist, and the live production archive is described as currently unmeasurable ("its sheet manifest returns 404," §7.6) — a state the draft is honest about, but one that should not ship to a preprint server before the deposit lands, per the paper's own unchecked submission checklist.

### Strengths
1. **Consistent claim-scope discipline**: Every major numeric claim is paired with an explicit boundary statement (e.g., §7.3: "These are descriptive comparisons within one series... their distances do not measure absolute accuracy"). `text: "These are descriptive comparisons within one series. Edges share sheets and are not independent replicates; their distances do not measure absolute accuracy or content alignment."` (§7.3)
2. **Honest novelty framing**: The paper repeatedly cites the closest prior work as already exhibiting the phenomenon it studies, rather than claiming to have discovered it first. `text: "Luft and Schiewe say as much about a third study, and the remark is the clearest statement of this paper's thesis we have found in the prior literature."` (§2.1)
3. **Title/abstract/conclusion alignment**: The conclusion (§10) neither over-promises past nor falls short of the abstract's claims.

### Weaknesses
1. **Reproducibility claim not yet backed by a public artifact**: The abstract markets "a reproducible account," but §11 and `submission.md` confirm the derived-data Zenodo deposit is not yet minted, and the live serving archive is currently unauditable (404 manifest). Posting to EarthArXiv in this state means early readers cannot reproduce the central numbers.
   - **Severity**: Major | **Evidence Anchor**: `absence: §11 — expected a minted Zenodo DOI or interim data availability statement; checked §11 text and submission.md checklist` | **Confidence**: 4 — directly stated in the paper's own §11 and tracked in `submission.md`
2. **No confirmed venue target makes "taxonomy" contribution claim harder to calibrate**: Without knowing whether this targets a cartometry venue (e-Perimetron), a GIScience journal (Transactions in GIS, ISPRS IJGI), or stays an EarthArXiv-only preprint, the Journal-Fit Reviewer cannot fully assess whether the contribution clears a specific bar — this is a disclosure limit on this review, not a paper defect per se.
   - **Severity**: Minor | **Evidence Anchor**: `absence: submission.md — expected a named target journal beyond the EarthArXiv posting; checked submission.md Fields section` | **Confidence**: 5 — directly observable from the supplied materials

### Detailed Comments

#### Journal Fit
Strong fit for EarthArXiv's Earth Sciences / GIS subject area as self-declared in `submission.md`. If a journal submission follows, *Transactions in GIS* or *e-Perimetron* are the closest matches given the paper's direct engagement with work published in both.

#### Originality
Modest and honestly scoped: the contribution is the taxonomy (Table 1) and the documented incident, not any individual check. This is acceptable for the field but should be stated even more explicitly in the abstract, which currently reads slightly more novel ("Together these cases support a taxonomy...") than the body's repeated "not new" qualifications would suggest to a skimming reader.

#### Significance
The documented real-world failure (455 m median displacement passing every existing check) is a genuinely useful cautionary case for anyone building or auditing similar pipelines, independent of the taxonomy's generality.

#### Structural Coherence
No over-promising detected; the paper is if anything under-promising relative to its own evidence, which is a defensible register for this genre.

#### Title & Abstract
Both accurate. The abstract's final sentence ("The contribution is a reproducible account...") should be softened or footnoted pending the Zenodo deposit (see Weakness 1).

#### Conclusion
Directly addresses the paper's stated research question and does not introduce new claims.

### Questions for Authors
1. Is a specific journal submission planned after the EarthArXiv posting, and if so, which — this would let a future review calibrate novelty/significance against that venue's actual bar rather than field-general judgement.
2. Can an interim data-availability statement (e.g., "code available at [repo URL], data deposit in progress") replace the current placeholder in §11 until the Zenodo DOI is minted, so the preprint is not published claiming reproducibility it cannot yet deliver?

### Minor Issues
- None beyond those already captured as Weaknesses.
