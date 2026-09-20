## Domain Review Report (Peer Reviewer 2)

### Reviewer Identity
Historical-cartography and map-librarianship researcher working on digital archives of colonial and Cold-War-era topographic series, familiar with IIIF-based digitization infrastructure and the georeferencing-of-series literature (Configuration Card #3).

### Overall Recommendation
Minor Revision

### Confidence Score
4

### Calibration Status
`NOT_CALIBRATED`

### Criterion-Bound Judgements
| Dimension / criterion | Criterion source | Judgement | Evidence anchors | Rationale | Uncertainty or scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Literature coverage of series-georeferencing precedent | field-general (§2 self-review against named literature) | MEETS | `text: "The nearest prior work is Luft and Schiewe (2021)..."` (§2.1) through §2.4 | §2 is unusually thorough: it engages seven+ distinct prior studies by mechanism, not just by citation, and explicitly locates this paper's contribution relative to each one's own stated limits | none identified | yes |
| Attribution accuracy of quoted claims | field-general | MEETS | `text: "neatlines are the first thing constructed and have the least projection error, [so] they can be assumed to be drawn at the 'correct' place"` (§2.1, attributed to Luft & Schiewe) | Spot-checked quotations are presented as direct quotes with correct attribution and are used to support exactly the point the paper makes about them | Full verification against the cited sources' original text was not independently performed by this reviewer; assessed for internal consistency and plausibility only | no |
| Archive-modelling contribution's relation to archival/library science precedent | field-general library & information science practice | PARTLY_MEETS | `text: "The archive models three related but non-interchangeable things: a survey cell, a sheet the archive can serve, and a physical printing held by an institution."` (§4) | This is a coherent and useful conceptual model for the paper's purposes, but its resemblance to established library-science entity models (e.g., FRBR's Work/Expression/Manifestation/Item distinction, or bibliographic edition/copy separation) is not acknowledged or cited | The paper may be independently motivated by the archive's operational needs rather than derived from library science; either way, a domain reader familiar with FRBR will notice the parallel is uncited | yes |
| Historical/institutional provenance accuracy | field-general | MEETS | `text: "held as GeoPDFs by the Perry-Castañeda Library at the University of Texas at Austin"`, `text: "held by Cartomundi at Aix-Marseille Université/CNRS"` (§3) | Institutional attributions are specific and plausible; consistent with known public digitization programs (PCL's map collection, Cartomundi's colonial cartography holdings) | Not independently verified against the institutions' own catalogues by this reviewer | no |

### Summary Assessment
The related-work section is the strongest domain-facing element of the paper: it does not merely list prior work but reads each cited paper for what its own design commits to, and several of the paper's best insights are framed as extensions of remarks the cited authors themselves made in passing (e.g., Luft & Schiewe's own justification for using corners, or Meijers & Schoonman's own acknowledged graticule-vs-neatline confound). This is domain scholarship of a high standard and gives the central taxonomic claim (Table 1) real interpretive weight rather than treating it as an a priori framework imposed on the literature. The two-series corpus (a Cold-War US military series and a French colonial series) is well chosen for the paper's argument because the series differ in how they supply spatial evidence (embedded GCPs vs. printed corner coordinates), which is exactly the axis the paper's taxonomy needs to vary. The one significant domain gap is that the archive-modelling contribution in §4 — cell / served-sheet / printing as three non-interchangeable entities — resembles established bibliographic and archival entity-relationship models (most directly FRBR-style Work/Manifestation/Item separation, and standard archival "item vs. copy" distinctions) without acknowledging that lineage; as presented it reads as though the distinction is being introduced fresh to the field, when a domain reader would recognize it as a reapplication of a well-established archival-science pattern to spatial-cell semantics specifically. This does not undermine the model's usefulness for the paper's argument, but the novelty framing should be adjusted.

### Strengths
1. **Related work read for mechanism, not just cited for topic**: The paper repeatedly extracts the precise structural reason a prior check is blind to a given fault, rather than summarizing prior work at the level of "also studied georeferencing." `text: "Two properties of that construction bound what the yardstick can see, and both are this paper's subject."` (§2.1)
2. **Honest positioning against near-identical prior remarks**: Rather than claiming priority, the paper explicitly identifies where a cited author already stated the same insight in passing. `text: "Luft and Schiewe say as much about a third study, and the remark is the clearest statement of this paper's thesis we have found in the prior literature."` (§2.1)
3. **Well-matched two-series corpus for the paper's argument**: Choosing one GCP-bearing series and one printed-corner series lets the paper demonstrate its taxonomy across two different evidentiary structures rather than generalizing from a single case. `text: "The two series are deliberately unlike in how they supply spatial evidence."` (§3)

### Weaknesses
1. **Archive-modelling framing (§4) does not acknowledge established archival/library-science precedent**: The cell/served-sheet/printing distinction closely parallels FRBR-style Work/Manifestation/Item separation and standard archival edition/copy distinctions, which are well-established in library and information science. The paper presents this as though it is a contribution specific to this project's needs, without situating it against that literature. `[FIELD-NORM UNVERIFIED]` is not applicable here — this is a literature-coverage gap, not a field-norm severity question, so it is graded on its own evidentiary weight.
   - **Severity**: Minor | **Evidence Anchor**: `absence: §4 — expected acknowledgment of established entity-relationship models (e.g., FRBR) or archival item/copy distinctions; checked §4 in full` | **Confidence**: 3 — this reviewer's competence is historical-cartography/archives, not formal library science; a library-science specialist would carry higher confidence on this specific point
2. **No engagement with digital-humanities/DH cartography literature on colonial map series specifically**: The Indochine series is a colonial-era French cadastral/topographic product with its own historiography (French colonial cartography, Indochina survey history), which the paper does not engage beyond the bare institutional/date facts in §3. This is not central to the paper's technical argument, but a domain reader would expect at least one sentence situating the Indochine series' historical production context beyond "dates from 1903–1927."
   - **Severity**: Minor | **Evidence Anchor**: `absence: §3, §6 — expected minimal historiographic context for the Indochine series' production; checked §3 (corpus description) and §6 (method B)` | **Confidence**: 3

### Detailed Comments

#### Literature Review
- **Coverage**: Strong for the georeferencing-methodology literature specifically named in §2; no obviously missing recent (2023–2026) content-based or OCR-based georeferencing papers were noticed. The mapKurator/ICDAR MapText/multimodal-LLM lineage (§2.4) is appropriately current.
- **Integration quality**: Genuinely critical synthesis, not enumeration — see Strengths above.
- **Research gap argument**: Persuasive and appropriately modest; the paper argues for a taxonomic/documentary gap, not a methods gap, and defends that framing consistently.

#### Theoretical Framework
- **Appropriateness**: Table 1's scope/committed-inputs framework is well-suited to organizing the paper's evidence and is applied consistently across all seven+ discussed checks.
- **Application depth**: Genuinely applied, not superficially cited — each `∅` cell in Table 1 is explained by tracing the specific shared-input mechanism (§7.1).
- **Alternative frameworks**: An explicit connection to the software-testing "oracle problem" / metamorphic-testing literature (test oracles that share an assumption with the system under test) is absent and would strengthen the framework's generality claim — flagged here and corroborated independently by R3 from the cross-disciplinary side.

#### Academic Argument Quality
- **Factual accuracy**: No factual errors identified in the spot-checked domain claims (institutional holdings, series dating, coordinate-conversion constants).
- **Argument logic**: Consistent; no unsupported logical leaps identified.
- **Terminology precision**: Precise throughout — "residual," "seam," "lattice," "collision" are each defined before use and used consistently.

#### Contribution to the Field
- **Incremental contribution**: A documented real-world incident plus a taxonomy that organizes seven-plus prior methods by diagnostic scope — a genuine, if modest, contribution.
- **Positioning**: Clearly and repeatedly distinguished from prior work's own claims (see Strengths).
- **Overclaiming**: Not observed; if anything the paper under-claims (see Journal-Fit Reviewer's note on the abstract's "reproducible account" phrasing pending the Zenodo deposit).

#### Missing Key References
- A citation to FRBR (Functional Requirements for Bibliographic Records, IFLA) or a comparable archival entity-relationship model would strengthen §4's framing. `[UNVERIFIED]` — this reviewer can attest the FRBR model exists and is the standard reference for this kind of entity separation in library/information science, but cannot confirm without a literature search which specific FRBR citation (report year/edition) the authors should use.
- A brief citation situating the Indochine series' colonial production context (a general history of the Service géographique de l'Indochine, if one exists in accessible literature) — phrased as a search lead: `[UNVERIFIED]` — literature on French Indochina survey history, e.g. work from historians of colonial cartography in Southeast Asia.

### Questions for Authors
1. Was the cell/served-sheet/printing model in §4 developed independently from archival-science entity models, or informed by them? Either answer is fine, but the framing should say which.
2. Is there a brief historiographic source for the Indochine series' original production (survey dates, administrative purpose) that could anchor §3's institutional description?

### Minor Issues
- §3: "Its holdings, digitisation quality and availability follow the decisions of the contributing institutions" is a good caveat; consider one clause naming what those institutional decisions were (e.g., selective digitization priorities) if known, to make the caveat concrete rather than generic.
