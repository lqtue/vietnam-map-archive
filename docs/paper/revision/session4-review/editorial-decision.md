# Editorial Decision Package

## Calibration Resolution

`calibration_status: NOT_CALIBRATED`

## Part 1: Editorial Decision Letter

Dear Author,

Thank you for submitting "Blind by construction: verifying a georeferenced map series when the check shares the error" for review ahead of its planned EarthArXiv posting. Your manuscript was reviewed through 5 role-separated seats — a Journal-Fit Reviewer, three Peer Reviewers (Methodology, Domain, Perspective), and a Devil's Advocate — each committing independently before this synthesis, per SKILL.md Iron Rule #2 (peer-output blinding). No confirmed venue target was supplied (no #683 Review Target Context), so every seat disclosed `criteria_binding_unavailable` and reviewed against field-general GIScience/spatial-data-quality practice rather than a specific journal's criteria. Per the session scope, this review ran single-family (no cross-model Reviewer 2 track, #540) and treated the manuscript as posted to EarthArXiv (a preprint server), so venue-blinding concerns did not apply.

### Decision: Minor Revision

### Consensus Analysis

#### Reviewer Summary Matrix

| Dimension | Journal-Fit Reviewer | R1 (Methodology) | R2 (Domain) | R3 (Perspective) |
|-----------|----------------------|-------------------|-------------|------------------|
| Overall Recommendation | Minor Revision | Minor Revision | Minor Revision | Minor Revision |
| Confidence | 4 | 4 | 4 | 3 |
| Key Strengths | Claim-scope discipline; honest novelty framing | Precise mechanism statement; transparent self-correction; matched-pair design | Related work read for mechanism, not topic; well-matched two-series corpus | Mechanism maps to software-testing oracle problem; candid algorithmic account; strong negative-results section |
| Key Weaknesses | → Step 1b | → Step 1b | → Step 1b | → Step 1b |
| # of Questions | 2 | 2 | 2 | 2 |
| # of Minor Issues | 0 | 1 | 1 | 0 |

#### Weakness Sub-Claim Inventory

| sub_claim_id | parent_weakness | reviewer_id | position | evidence_pointer | severity | confidence |
|--------------|-----------------|-------------|----------|------------------|----------|------------|
| SC-1 | Reproducibility claim (abstract) not yet backed by deposited data | EIC | raised | §11 / `absence` anchor, EIC W1 | major | 4 |
| SC-1 | (same) | DA | corroborated (M2) | Abstract vs. §11 text comparison | major | 4 |
| SC-1 | (same) | R1 | not-mentioned | — | — | — |
| SC-1 | (same) | R2 | not-mentioned | — | — | — |
| SC-2 | Controlled A/B design (single-flag isolation) not stated in manuscript text | R1 | raised | `absence` anchor, R1 W1 | major | 4 |
| SC-2 | (same) | EIC | not-mentioned | — | — | — |
| SC-2 | (same) | R2 | not-mentioned | — | — | — |
| SC-2 | (same) | DA | not-mentioned | — | — | — |
| SC-3 | No independent (non-author) verification of the corrected Helmert-parameter dry run | DA | raised (M1) | §7.5/§7.6 `absence` anchor | major | 4 |
| SC-3 | (same) | EIC | not-mentioned (adjacent: EIC's SC-1 is about deposit existence, not independent verification of the fix specifically) | — | — | — |
| SC-4 | Table 1's generality validated on only one partially-independent second case (same archive, same author) | DA | raised (M3) | Abstract vs. §9 hedge | major | 3 |
| SC-4 | (same) | EIC | not-mentioned (EIC's originality judgement (PARTLY_MEETS) is adjacent but not this specific sub-claim) | — | — | — |
| SC-5 | `pick_crs` 150 m threshold unmotivated / not reconciled with ~15 m reported agreement scale | R1 | raised | §7.5 text anchor, R1 W2 | minor | 3 |
| SC-6 | No seam-census sampling-design sensitivity check | R1 | raised | §7.3 `absence` anchor, R1 W3 | minor | 3 |
| SC-7 | Archive cell/served-sheet/printing model (§4) does not acknowledge FRBR/archival-science precedent | R2 | raised | §4 `absence` anchor, R2 W1 | minor | 3 |
| SC-8 | No historiographic context for the Indochine series' colonial production | R2 | raised | §3/§6 `absence` anchor, R2 W2 | minor | 3 |
| SC-9 | No connection to the software-testing oracle-problem / metamorphic-testing literature | R3 | raised | §2/§9 `absence` anchor, R3 W1 | minor | 3 |
| SC-10 | No process/organizational reflection on how the original shared-input design shipped | R3 | raised | multiple-section `absence` anchor, R3 W2 | minor | 3 |
| SC-11 | §9 practitioner advice not reconciled with the fact the authoring project did not follow it in advance | R3 | raised | §9 text anchor, R3 W3 | minor | 2 |

No sub-claim carries `position = disputed` — there is no [SPLIT] in this round; all four card-backed seats and the DA converge on direction (revision, not rejection), and no reviewer contradicted another's factual claim.

#### Points of Agreement (Consensus)
- No [CONSENSUS-4] or [CONSENSUS-3] items — every substantive weakness in this round is either a single-reviewer finding (SC-2 through SC-11) or corroborated by exactly 2 of the 5 seats (SC-1, corroborated by the DA as M2; the DA is tracked separately from the 4-reviewer consensus count per SKILL.md, so SC-1 remains a 1/4 single-reviewer finding among the card-backed panel, independently corroborated by DA). This reflects genuine perspective diversity rather than a poorly-specified paper: each seat's configured focus (journal fit, methodology, domain, cross-disciplinary practice) surfaced a distinct, non-overlapping set of concerns, which is the intended effect of the panel's angle diversification (field_analyst_agent Configuration Principles).

#### Points of Disagreement
- None requiring arbitration. No reviewer disputed another's finding's existence, severity, or recommended remedy.

### Decision Rationale
[247 words] All five seats — four independently configured card-backed reviewers plus the Devil's Advocate — converge on Minor Revision, and this converges for the right reason: every reviewer found the paper's core argument (a verification check can be structurally blind to an error class it shares an assumption with) well-evidenced, precisely stated, and honestly scoped, with no reviewer identifying a defect that undermines that core claim. The Devil's Advocate's most sustained adversarial effort (self-verification of the "fix," M1; the abstract's reproducibility framing running ahead of the deposited-data state, M2) produced no CRITICAL finding — every MAJOR-severity issue the DA raised is corrigible by procedural steps (complete the Zenodo deposit before posting; state plainly that the corrected Helmert parameters are self-verified, not yet independently reproduced) rather than by re-arguing the paper's evidence or design. The two Major-severity findings that recur across seats — the not-yet-deposited data (EIC SC-1, corroborated by DA M2) and the undocumented A/B isolation design (R1 SC-2) — are exactly the kind of "supplementation or clarification, not core restructuring" that defines Minor Revision under `references/editorial_decision_standards.md`. The remaining findings (SC-5 through SC-11) are Minor-severity clarity and framing improvements distributed across methodology, domain, and cross-disciplinary angles, none decision-bearing on its own. No reviewer recommended Major Revision or Reject, and no reviewer's Accept-leaning judgement was contradicted by another's evidence. This is therefore a clean Minor Revision: address the reproducibility-timing gap, document the controlled-comparison design explicitly, and the manuscript is ready.

### Blocking Issues (0–3, immutable source order)

| Transport ref | Blocking issue | Source reviewer(s) | Evidence anchor | Resolving roadmap item |
|---------------|----------------|--------------------|-----------------|------------------------|
| R1 | Reproducibility claim in the abstract ("a reproducible account") is not yet supported: the Zenodo derived-data deposit is unminted and the live production manifest 404s | EIC, DA (SC-1) | `absence: §11 — expected a minted Zenodo DOI or interim data availability statement` | REV-1 |
| R2 | The controlled A/B isolation design underlying the before/after comparison (§7.3/§7.6) is documented only in the companion `claim-audit.md`, not in the manuscript itself | R1 (SC-2) | `absence: §5, §7.6 — expected an explicit single-flag isolation statement` | REV-2 |
| R3 | The corrected dry-run result has not been independently (non-author) verified before the reproducibility-claiming posting | DA (SC-3) | `absence: §7.5, §7.6 — expected disclosure of self-verification-only status or an independent re-run` | REV-3 |

---

## Part 2: Revision Roadmap

> The `Sub-Claim(s)` column carries the Step 1b `sub_claim_id`(s) each item traces to.

### Required Revisions (Must Fix)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| R1 | Complete the Zenodo deposit and paste the DOI into §11 before posting to EarthArXiv, OR replace the current §11 placeholder with an explicit interim data-availability statement (code repository link + "deposit in progress") and soften the abstract's "reproducible account" phrasing until the deposit exists | SC-1 | major | `absence: §11` | 4 | EIC, DA | must_fix | sentence (§11) + abstract clause | if unaddressed: readers cannot verify the paper's central numbers at posting time, undermining the abstract's own framing |
| R2 | Add one explicit sentence in §5 or §7.6 stating that the faulty/corrected comparison isolates a single pipeline flag (`--no-datum-shift`) with no other concurrent change | SC-2 | major | `absence: §5, §7.6` | 4 | R1 | must_fix | sentence | if unaddressed: a methodology reviewer cannot confirm the before/after comparison is a clean single-variable control |
| R3 | Add a sentence in §7.5 or §7.6 explicitly stating that the corrected Helmert-parameter result is self-verified (same author/pipeline) and has not yet been independently reproduced, distinguishing this clearly from "validated" in the ordinary peer-review sense | SC-3 | major | `absence: §7.5, §7.6` | 4 | DA | must_fix | sentence (§7.6 heading/text) | if unaddressed: a reader may over-trust the corrected result as independently confirmed when it is not |

### Suggested Revisions (Should Fix)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| S1 | Add one sentence distinguishing "explains two cases from one project well" from "generalizes broadly" near the abstract's taxonomy claim, consistent with §9's existing hedge | SC-4 | major | `text: Abstract vs. §9` | 3 | DA | should_fix | sentence (Abstract) | clarity of generality claim |
| S2 | State the basis (or acknowledge the absence of one) for the `pick_crs` 150 m acceptance threshold, and note its relation to the ~15 m reported index-to-outline agreement scale | SC-5 | minor | `text: §7.5` | 3 | R1 | should_fix | sentence (§7.5) | minor clarity gap |
| S3 | Note whether the seam-census 25-point / 10–90%-of-length sampling design was checked for sensitivity to sample count or window | SC-6 | minor | `absence: §7.3` | 3 | R1 | consider | sentence (§7.3) | robustness transparency |
| S4 | Acknowledge established archival/library-science entity-relationship precedent (e.g., FRBR-style Work/Manifestation/Item separation) when framing the §4 cell/served-sheet/printing model | SC-7 | minor | `absence: §4` | 3 | R2 | should_fix | sentence (§4) | novelty-framing accuracy |
| S5 | Add minimal historiographic context (one sentence) for the Indochine series' colonial-era production in §3 or §6 | SC-8 | minor | `absence: §3, §6` | 3 | R2 | consider | sentence (§3 or §6) | domain-reader expectation |
| S6 | Connect the paper's central mechanism to the software-testing "oracle problem" / metamorphic-testing literature (§2 or §9) | SC-9 | minor | `absence: §2, §9` | 3 | R3 | consider | sentence + citation (§9) | broadens cross-disciplinary reach |
| S7 | Add a brief process-level reflection on how the original shared-input check design shipped (not just the algorithmic mechanism of its blindness) | SC-10 | minor | `absence: §7.1, §7.4, §9, §10` | 3 | R3 | consider | paragraph (§9 or §10) | strengthens practical/transferable lesson |
| S8 | Reconcile §9's prescriptive practitioner ordering with the fact the authoring project did not follow it in advance (frame as a retrospective lesson) | SC-11 | minor | `text: §9` | 2 | R3 | consider | sentence (§9) | practical-applicability framing |

### Source-Traceability Checklist

- [ ] R1 — obligation `must_fix`: Zenodo deposit or interim data-availability statement; soften abstract's "reproducible account" phrasing until resolved
- [ ] R2 — obligation `must_fix`: state the single-flag A/B isolation design explicitly in the manuscript
- [ ] R3 — obligation `must_fix`: disclose the corrected result as self-verified, not independently reproduced
- [ ] S1 — obligation `should_fix`: distinguish "explains two cases well" from "generalizes broadly" near the abstract
- [ ] S2 — obligation `should_fix`: motivate or acknowledge the unmotivated `pick_crs` 150 m threshold
- [ ] S3 — obligation `consider`: note seam-census sampling-design sensitivity status
- [ ] S4 — obligation `should_fix`: acknowledge archival/library-science precedent for the §4 model
- [ ] S5 — obligation `consider`: minimal Indochine historiographic context
- [ ] S6 — obligation `consider`: connect to software-testing oracle-problem literature
- [ ] S7 — obligation `consider`: add process-level reflection on the original design decision
- [ ] S8 — obligation `consider`: reconcile §9 advice with the project's own prior non-adherence

### Response Letter Template
Use `templates/revision_response_template.md`-style R→A→C format to respond to each item above when preparing the next draft.

---

## Part 3: Reviewer Report Summary (Appendix)

### Journal-Fit Review Report Summary
- Recommendation: Minor Revision | Confidence: 4
- Key Point: Well-scoped, honestly-novel, structurally coherent draft; main gap is that the abstract's reproducibility claim outruns the not-yet-deposited data.

### Reviewer 1 (Methodology) Summary
- Recommendation: Minor Revision | Confidence: 4
- Key Point: Technically sound datum/CRS account and consistent population bookkeeping; the controlled A/B isolation design needs to be stated explicitly in the manuscript, not only in the companion audit file.

### Reviewer 2 (Domain) Summary
- Recommendation: Minor Revision | Confidence: 4
- Key Point: Related-work engagement is unusually strong (read for mechanism, not topic); the archive-modelling contribution in §4 should acknowledge its resemblance to established archival/library-science entity models.

### Reviewer 3 (Perspective) Summary
- Recommendation: Minor Revision | Confidence: 3
- Key Point: The core mechanism is a direct instance of the software-testing "oracle problem," unconnected to that literature; the paper explains its failure algorithmically but not organizationally/procedurally.

### Devil's Advocate Summary
- Recommendation: N/A — findings only
- Key Challenge: No CRITICAL finding survives adversarial pressure — the manuscript's own hedging discipline pre-empts most standard attacks. The most substantive residual risk is that the corrected result is verified only by the same author/pipeline that produced the original fault, and the abstract's "reproducible account" framing runs ahead of the not-yet-deposited data (both MAJOR, both corrigible by disclosure rather than re-analysis).
