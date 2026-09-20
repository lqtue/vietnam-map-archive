# Field Analysis Report

## Paper Basic Information
- **Title**: Blind by construction: verifying a georeferenced map series when the check shares the error
- **Abstract length**: ~220 words
- **Full text length**: ~7,900 words (body, excluding references)
- **Number of references**: 16 (all DOI-bearing except one; author states all screened for editorial notices 2026-09-20)

## Field Analysis

| Dimension | Analysis Result |
|-----------|----------------|
| Primary Discipline | Geographic Information Science — spatial data quality / cartographic verification |
| Secondary Disciplines | Historical cartography & digital map archives; geodesy/photogrammetry (datum transformation); software reliability / incident postmortem practice |
| Research Paradigm | Case study with quantitative reproduction, developed into a conceptual taxonomy |
| Methodology Type | Documented system-failure case study + controlled A/B reproduction (`--no-datum-shift` flag) + comparative taxonomy (Table 1) |
| Target Venue | Posted to **EarthArXiv** (Earth Sciences preprint server; no formal peer-review target confirmed in the supplied materials — `submission.md` names EarthArXiv fields only, no journal target). Per SKILL.md §5, no author-confirmed #683 Review Target Context was supplied, so this panel discloses `criteria_binding_unavailable` throughout and makes no venue-specific acceptance claim. Field-general judgement only. |
| Paper Maturity | Pre-submission — near-complete draft with an internal claim-audit (`claim-audit.md`), a figures ledger, and a submission checklist (`submission.md`) with one unchecked item (Zenodo deposit) |

## Recommended Target Journals (Top 3, field-general — not a confirmed target)
1. *Transactions in GIS* — closest topical match; the paper's primary interlocutor (Luft & Schiewe 2021) was published here, and the venue regularly carries geospatial-data-quality methodology papers.
2. *e-Perimetron* (International Society for the History of the Earth Sciences / old-maps cartometry) — carries the Heitzler et al. (2018) and Meijers & Schoonman (2025) papers this draft engages most closely; free, cartometry-focused, comfortable with this depth of methodological self-audit.
3. *ISPRS International Journal of Geo-Information* — open access, has carried several of the cited multi-sheet georeferencing papers (Kuna et al. 2024, Milleville et al. 2022, Uhl et al. 2018); good fit for a reproducible-methods contribution.

## Reviewer Configuration Cards

### Reviewer Configuration Card #1 — Journal-Fit Reviewer
**Role**: EIC (internal) / **Display role**: Journal-Fit Reviewer
**Identity Description**: A GIScience preprint-server screening editor with a secondary appointment reviewing for *Transactions in GIS* and *ISPRS IJGI*, specializing in spatial-data-quality methodology and historical-map digitization pipelines.
**Review Focus**:
  1. Whether the paper's contribution is legible and appropriately scoped for a EarthArXiv Earth Sciences / GIScience readership, absent a confirmed journal target
  2. Whether the paper over- or under-claims novelty relative to the extensive related-work engagement it already does
  3. Structural coherence: title → abstract → conclusion consistency, and whether the "taxonomy" framing is earned by the evidence
**Will particularly care about**: Whether a reader skimming only the abstract and Table 1 would come away with an accurate, non-inflated understanding of what was actually measured versus what is a structural/logical claim (`D`-labelled in the paper's own audit).
**Possible blind spots**: Deep datum-transformation/geodesy correctness (deferred to R1); domain-specific historical-cartography literature completeness (deferred to R2).

### Reviewer Configuration Card #2 — Peer Reviewer 1 (Methodology)
**Role**: Peer Reviewer 1 / **Display role**: Peer Reviewer 1
**Identity Description**: A photogrammetry/geodesy specialist working on datum transformation QA for national mapping agencies, with a research focus on accuracy assessment protocols for scanned cartographic archives.
**Review Focus**:
  1. Whether the CRS/datum reasoning (§7.4–7.5, the `EPSG:4131`→`EPSG:4326` area-of-use failure, the axis-order transposition bug) is technically sound and precisely described
  2. Whether the reported statistics (medians, ranges, matched-pair comparisons) are reported with adequate rigor for a descriptive (non-inferential) engineering study
  3. Reproducibility: whether the corrected-build "dry run" (§7.6) is adequately distinguished from the live serving state, and whether the promised Zenodo deposit is a live blocker
**Will particularly care about**: Whether the paper's own claim that its checks are "descriptive... not independent replicates" (§7.3) is honored throughout, i.e., no smuggled inferential claim riding on medians of non-independent seam measurements.
**Possible blind spots**: Historical-cartography domain framing and literature completeness (R2); readership/venue fit (Journal-Fit Reviewer).

### Reviewer Configuration Card #3 — Peer Reviewer 2 (Domain)
**Role**: Peer Reviewer 2 / **Display role**: Peer Reviewer 2
**Identity Description**: A historical-cartography and map-librarianship researcher working on digital archives of colonial and Cold-War-era topographic series, familiar with IIIF-based digitization infrastructure and prior georeferencing-of-series literature.
**Review Focus**:
  1. Completeness and accuracy of the related-work engagement (§2), especially whether the paper's central "shared-input blindness" framing is fairly attributed against Luft & Schiewe (2021) and Janata & Cajthaml (2020)
  2. Whether the archive-modelling contribution (§4: cell / served-sheet / printing) is a genuine conceptual contribution or a restatement of standard library/archive cataloguing practice
  3. Historical/institutional accuracy: dating, provenance and institutional attribution (Perry-Castañeda Library, Cartomundi/Aix-Marseille) of the two source series
**Will particularly care about**: Whether "the archive models three related but non-interchangeable things" (§4) is presented with appropriate modesty relative to existing archival-science and library cataloguing frameworks (e.g., FRBR-style work/manifestation/item distinctions), which the draft does not cite.
**Possible blind spots**: Statistical/geodetic technical correctness (R1); software-engineering/reproducibility framing (R3).

### Reviewer Configuration Card #4 — Peer Reviewer 3 (Cross-disciplinary/Practical)
**Role**: Peer Reviewer 3 / **Display role**: Peer Reviewer 3
**Identity Description**: A software-reliability engineering researcher working on incident postmortems and verification/test-oracle blindness in production systems (outside GIScience), brought in because the paper's central mechanism — "a check that shares an assumption with what it is checking" — is a well-known failure mode in software testing (the "oracle problem" / "tautological test") that this draft does not connect to that literature.
**Review Focus**:
  1. Whether framing this as a general "test-oracle-shares-the-fault" problem (familiar from software testing / metamorphic testing literature) would strengthen or is already implicitly present
  2. Practical, operational stakeholder view: what does a small single-maintainer archive project realistically do with Table 1's ordering advice (§9), given resource constraints acknowledged nowhere in the paper
  3. Self-audit credibility: the paper is a single author auditing and publicly disclosing their own system's failure — is this framed with the rigor a reader would expect of an independent audit, or does it read as after-the-fact rationalization dressed as taxonomy
**Will particularly care about**: Whether the paper's honest, unusually self-critical tone ("our `graticule_error` was shipped, trusted, and silent... the worst row in the table") is matched by equally rigorous treatment of *why* the original design decision was made and what organizational/process failure (not just algorithmic blindness) let it ship.
**Possible blind spots**: Deep geodetic technical detail (R1); cartographic-archive domain literature completeness (R2).

## Review Strategy Recommendations
- This is a single-author, self-reported incident paper: R3 and the Devil's Advocate should independently probe self-audit credibility and conflict-of-interest framing, since neither the Journal-Fit Reviewer nor R1/R2 are configured to focus there — expect corroboration rather than redundancy if multiple seats raise it.
- No confirmed venue target exists; all seats disclose `criteria_binding_unavailable` and stay field-general per SKILL.md §5, rather than fabricating EarthArXiv- or journal-specific acceptance criteria.
- The paper's own `claim-audit.md` already runs an unusually disciplined evidence-labelling exercise (A/B/C/D/R) — reviewers should treat this as evidence of authorial rigor, not substitute it for their own verification of the manuscript text.
