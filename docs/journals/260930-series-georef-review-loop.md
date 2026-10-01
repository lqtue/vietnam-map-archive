# Series georeferencing: what to change, a yes/no/fix review loop, and where the method stops

**2026-09-30.** A step back from `260923-indochine100k-georef.md` (the per-sheet record) to ask
three questions. How should the automated series pipeline change? What is the simplest
human-in-the-loop design? And what does this work add to "Blind by construction"
(`docs/paper/draft.md`)? The frame-and-corner method's limits are tested against two series it
cannot take: the *Plans des Arrondissements* raised with Allmaps (`docs/private/allmaps.md` §2),
and the 1971 South Vietnam province atlas (`~/Work/Maps/sources/1971 South Vietnam Admin Map`).
Literature was checked through scite and the web; every reference below was retrieved in this
session or is already verified in `docs/paper/related-work.md`. No code or data changed.

## 1. Where the 561 pipeline actually is

The numbers come from the 260930 handoff and the journal:

- **328 check-clean placements, zero lattice conflicts.** 337 is the expected but unconfirmed
  floor, since 9 later landings could not be re-checked because of the credential gap. 23 are held.
- **`DETECT_VERSION` went from 3 to 39 in seven days** (09-24 → 09-30). Almost every step was a
  gated retry or a registry entry, and each was justified on one to five sheets that someone
  inspected through crops.
- **The human judgement is real but unrecorded as data.** Each person-reviewed decision ends up as
  a hand edit to `SOURCE_REVIEWED_FRAMES` / `_BOUNDARIES` / `_RIMS` / `_CORRECTED_BOX` or
  `CALIBRATION_HOLDS`. That makes it impossible to say how often a reviewed decision is wrong.
- **Review has already been wrong once.** Version 29 landed two sheets on a kilometre-grid line
  about 52 px inside the true neatline. The grid line fit *straighter* (0.28–0.48 px) than the
  engraved frame (~3.2 px). Only a per-pixel profile caught it (`docs/lessons.md`, 2026-09-29).
- **314 sheets are public**: 135 on 09-24, and 179 more in the 09-29 backlog publish. All went out
  on geometry gates plus the lattice check. No one looked at them in `/explore`.
- **325 has not been started. Tonkin's 62 sheets still wait for `tonkin-review`.**

## 2. The shortfalls, stated plainly

1. **The detector is a tuning record, not yet a method.** Thirty-six versions of per-sheet rules
   with no held-out set is evidence that 561 can be cleared. It is not evidence that the procedure
   would clear another series. Series 325 is the obvious test, and nothing has been run on it.
2. **561 has no independent accuracy number.** Every gate is geometric self-consistency (aspect,
   axis scale, rim spread, lattice) or agreement with the catalogue. The catalogue also supplies
   the placement. The 189 m median between WKT centroids and placements measures the gap between
   two sources, not the error of either. This is the preprint's own "check shares the input"
   structure, applied to our own pipeline. The paper should say so.
3. **Humans review crops, but the review leaves no rate.** Without recorded accept/reject labels
   on a random sample, the clear set has no error estimate.
4. **The method assumes MapEdge's world.** That means a quadrangle cell, known corner coordinates
   and four straight neatlines (Meijers & Schoonman; `allmaps.md` §3). Four kinds of sheet break
   that assumption:
   - a printed grid with no sheet index (1971 atlas);
   - no grid and no index (Arrondissement plans; Meijers likened them to Dutch cadastral plans);
   - a projected kilometric grid instead of grades (Cao-Bang's Bonne edition, held on purpose);
   - several maps on one image (1971 insets).

## 3. Changes to the automated pipeline, in priority order

**3.1 Replace the retry cascade with candidate ranking.** The pipeline already *generates* every
candidate the retries consider: the `frame()` alt peak, inward-frame candidates, patch-supported
rims, and the direct seam boundary. Rank them in one pass instead of trying them in version order:

- **Per side:** enumerate the observed lines and score each with the test that generalised,
  *where paper ends* (a blank exterior strip against interior ink; lessons 2026-09-29). Add patch
  continuity (≥75% of 24 patches).
- **Jointly:** choose the four-side combination that best satisfies geometry (parallel opposite
  sides, consistent rim offsets, catalogue aspect). Keep a hold when no observed line supports a
  side. Never fill a side from the prior.

This is what MapEdge (fuzzy-ranked peak pairs) and Lenc et al. 2024 (candidate lines with
intersection refinement) do; our 09-25 entry already argued for it. Acceptance test: it reproduces
the current clear set with zero corners moving more than 2 px (snapshot diff, not `regress`), then
runs **unchanged** on 325. Report 325's clear rate as the generalisation number.

**3.2 Use the printed ticks as redundant interior control on every sheet, not only for
calibration.** Adding the printed graticule ticks (0.1 g spacing, already located against the
neatline for calibration) as GCPs changes what the fit's residual measures. The annotation is first-order (affine, 6
DOF), so four corners already overdetermine it by two. But that residual mostly measures how
rectangular the detected frame is, not whether the sheet is placed correctly. Tick positions carry
their own printed coordinates, so a residual over ticks tests *placement*, and does it without
the catalogue. It still shares the datum, and the taxonomy must name that. Burt et al. (2019) report 1–4 px RMSE from graticule intersections (as quoted by Luft
& Schiewe, 2021). Kuna et al. (2024) rectified each sheet on ~41 grid intersections. Tick reading
without Gemini already reached landing grade on the coastal family (09-30).

**3.3 Seam-content agreement between warped neighbours.** Roads and rivers should continue across
a shared edge. That is image evidence, independent of the catalogue. It shares only the datum,
because both neighbours use one. A normalised cross-correlation of the two edge strips after
warping is enough to rank seams for review. Build the cheap version first.

**3.4 Bind approvals to geometry.** Pursat's hold was lost to a version bump. The same failure,
applied to an approval, would publish new corners under an old "yes". Store each approval with its
corner coordinates (or a hash of them) and gate publishing on an exact match. Fold the five
`SOURCE_REVIEWED_*` / `CALIBRATION_HOLDS` dicts into one reviewed-decisions file or table keyed by
map id, which the loop in §4 writes.

## 4. Human in the loop: yes / no / fix

**Where it lives.** This extends a UI we already have. `/scan?mode=prepare` (triage accepted,
gated on `validated_at`) and `/scan?mode=shapes&tab=validate` (approve/reject plus Model feedback
tags keyed to `run_id`) already implement "the model proposes, you decide"
(`docs/digitalize-guide.md`). Add a georef tab that follows the same pattern.

**Two questions, not one.** A correct frame is not a correct placement. Placement comes from
catalogue coordinates plus the calibration offset. Quang Ngai (east edge about 9.2 km wrong in the
catalogue), Tri Binh and Phan Rang all had correct frames on wrong catalogue boxes, and a frame-only
"yes" would have passed each of them. That would repeat, in our own review, the shared-input
error the preprint describes. So the card asks both questions, and the audit reports two error
rates:

1. **Boundary:** is the line on the paper edge? Answered from the corner crops and profiles.
2. **Placement:** is the sheet where it belongs? Answered only from evidence the catalogue does
   not supply: the seam overlay against placed neighbours, plus two or three landmarks (a town or
   confluence on the sheet, checked against the gazetteer or OSM).

**The card, one sheet per screen, keyboard Y / N / F, one answer per question:**

- **Four corner crops at native resolution**, each with the proposed boundary drawn in. Beside each
  crop, show its **per-pixel profile strip** marking where the paper plateau ends. The profile is
  what caught v29; resized strips and fixed-window crops did not.
- **A small warped overlay** on the basemap with the already-placed neighbours, so the seams are
  visible. Seam continuity is the one judgement a human makes that shares nothing with the
  catalogue.

**The three answers:**

| Key | Meaning | Writes |
|---|---|---|
| **Y** | Correct: boundary on all four sides, or placement against seams and landmarks | Approval `{map_id, question, corners, detector_version, reviewer, at}`; publishing requires both approvals and the corners to still match |
| **N** | Wrong, and I can't fix it here | Hold + one tag: `interior line` · `decorative band` · `scale bar` · `catalogue wrong` · `distorted paper` · `other`. Tags are training data, as in shapes-validate |
| **F** | Boundary: click the correct line in the failing crop | **v1:** seed a local refit at the click, which is what a `SOURCE_REVIEWED_BOUNDARIES` entry does today. **v2** (after §3.1 persists per-side candidate lists): snap to the nearest observed candidate. Gates re-run: pass → approval; fail → hold with the fix recorded. Replaces hand-editing `SOURCE_REVIEWED_*` |

A placement problem has no one-click fix; it is an N tagged `catalogue wrong`, which feeds the
printed-tick reread that fixed Quang Ngai. Fixing by click keeps human input on the same footing
as the detector's, and costs one click instead of four GCPs.

**Routing (selective prediction).** Give each sheet one confidence: the smallest margin across its
gates, combined with the ratio of best to second-best candidate from §3.1.

- Low-confidence sheets are always reviewed.
- High-confidence sheets get a **random audit** of a fixed fraction, blind to the score.

From those labels, report risk against coverage (Geifman & El-Yaniv, 2017): the error rate among
auto-accepted sheets at each threshold, **separately for boundary and placement**. The placement
rate is the number §2.2 says is missing. The boundary rate alone would not be, because it shares
the catalogue. Smapshot validates volunteer georeferences on
pre-computed indicators such as GCP count, computed error and covered area (Ingensand et al.,
2022), and the British Library's Georeferencer ran crowdsourced placement at collection scale
(Kowal & Pridal 2012, via McAuliffe et al., 2017). Neither reports an error rate for its
automatic tier; that is the gap here.

**What to measure rather than assume:** seconds per Y, seconds per F, and the share of F clicks
that snap to an existing candidate. The last one tells us whether §3.1's candidate set is complete.

## 5. Series the method does not cover

### 5.1 The 1971 province atlas: grid-first, not frame-first

What the 44 scans show (contact sheet read this session): **one sheet per province, 1:150,000
stated, a printed 10 km military grid with 100 km square letters** (VS, WS, WR, XS, XR in the
margins). Everything else varies from sheet to sheet:

- frame size and aspect;
- orientation — 0001's pixels are stored upside down, about a dozen are 90° off, and there is
  **no EXIF orientation tag**;
- legend and table placement;
- insets: the Spratlys on 33, islands on 18, a second map panel on 15.

The scans are 19868 × 14031 JPGs, 748 MB in all, and not yet in IIIF/R2.

This is "grid, no index", which is the easier of the two non-quadrangle cases:

1. **Ingest first** (IIIF/R2). This is a precondition for any annotation.
2. **Detect grid lines** with Hough and post-processing, training-free. Baloun et al. (2022) won
   the MapSeg grid task this way and held up on cadastral sheets. Intersections give dozens of
   GCPs per sheet, so the fit has a real residual, as §3.2 wants.
3. **Label the grid once per sheet.** Two readings fix the whole lattice: the 100 km square and
   one easting/northing digit. For 44 sheets a person typing two labels is cheaper than building
   OCR. That is the "F" of §4 in a different form. Label reading also settles orientation.
4. **Masks:** the frame minus insets. An inset at a different scale (the Spratlys) is excluded or
   georeferenced on its own.

**Checks before trusting any output:**

- **Datum.** Read the margin note. Indian 1960 is plausible for this period, which is exactly the
  trap in the preprint.
- **UTM zone.** The zone 48/49 boundary is 108°E, and central-coast provinces lie east of it. Their
  square letters belong to zone 49.
- **Scale.** Measure grid pitch per sheet to confirm 1:150,000. The large highland provinces may
  differ.

### 5.2 Plans des Arrondissements: no grid, no index

Thirteen sheets. **Do them by hand in the Allmaps Editor.** A pipeline for 13 sheets does not pay
back. Two assists are cheap if the data already exists:

- GCPs suggested from toponyms our OCR gazetteer already holds (the toponym-assisted route; Kim et
  al., 2023, for text linking);
- a content-based match against modern roads and canals (Luft & Schiewe, 2021).

Pope & Frean (2025) match angle relations of cadastral line intersections at national scale; that
is the research route if the series ever grows. In the paper this is a **scope boundary**, not a
result.

### 5.3 Cao-Bang (Bonne kilometric edition)

This is the 1971 approach with a Bonne CRS instead of UTM. It needs SGI's Bonne parameters. Leave
it held until those are sourced.

## 6. What this adds to the preprint

"Blind by construction" is a verification taxonomy built on one documented failure (L7014) plus
the Indochine 1:25,000 cell collision. The only other preprint on record, 10.31223/X5NJ4B, is the
green-cover/LST paper, so this is the georef preprint. It has not been posted: the Zenodo box in
`submission.md` is open, and a web search on 2026-09-30 found no EarthArXiv listing. That leaves
an open choice. **Undecided, for the author:**

- **(a) Fold in before posting.** The taxonomy gains a third case: an automated pipeline that
  declares its own blind spots, with the audit as evidence. This is stronger, but posting waits on
  the audit, which is §7 step 3.
- **(b) Post as scoped now, and make this a second methods-and-audit paper that cites it.** This is
  faster, and the taxonomy stays the first paper's claim.

Either way, the material is:

1. **The taxonomy applied to our own automated pipeline.** Each 561 gate, with its committed
   inputs and blind spots (§2.2).
2. **Candidate ranking (§3.1), tested out of sample** on series 325, with 561 as development set.
3. **A blinded human audit with two labels.** The *boundary* error rate tests detection. The
   *placement* error rate, judged on seams and landmarks rather than the catalogue, is the
   independent number. Both are reported as risk-coverage curves (§4). Claim for each only what
   its label measures.
4. **Redundant interior control** (ticks for Indochine, grid intersections for 1971): a
   per-sheet residual that shares only the datum.
5. **Scope:** the three sheet types the frame method cannot take (§5), one handled grid-first, two
   left as stated limits.

What it must not claim: field priority for candidate ranking or grid detection (MapEdge; Lenc et
al.; Baloun et al.), or any accuracy number the audit has not produced.

## 7. Next steps, in dependency order

1. Commit or snapshot the uncommitted 561 work before touching the detector again.
2. Build the §4 review tab on the existing validate pattern, with the §3.4 approval binding and
   F v1 (a local refit at the click). The 314 already-public sheets are the first queue.
3. Run the random audit. That gives the first real error-rate number.
4. Consolidate into candidate ranking (§3.1), prove there is no movement on 561, then run on 325.
5. Ingest the 1971 atlas, read one sheet's datum note, and prototype grid-first on one sheet.

## References

- Baloun, J., Lenc, L., & Král, P. (2022). Robust grid detection in historical map images. *ICIP 2022*. https://doi.org/10.1109/icip46576.2022.9897721
- Burt, J. E., White, J., Allord, G. J., et al. (2019). Automated and semi-automated map georeferencing. *CaGIS*, 47(1), 46–66. https://doi.org/10.1080/15230406.2019.1604161
- Geifman, Y., & El-Yaniv, R. (2017). Selective classification for deep neural networks. arXiv. https://doi.org/10.48550/arxiv.1705.08500
- Ingensand, J., Lecorney, S., & Blanc, N. (2022). An open API for 3D-georeferenced historical pictures. *ISPRS Archives*, XLVIII-4/W1-2022, 217–222. https://doi.org/10.5194/isprs-archives-xlviii-4-w1-2022-217-2022
- Kim, J., Li, Z., Lin, Y., et al. (2023). The mapKurator system. *ACM SIGSPATIAL*. https://doi.org/10.1145/3589132.3625579
- Kuna, J., Panecki, T., & Zawadzki, M. (2024). Methodology of mosaicking and georeferencing for multi-sheet early maps with irregular cuts. *IJGI*, 13(7), 249. https://doi.org/10.3390/ijgi13070249
- Lenc, L., et al. (2024). *Towards historical map analysis using deep learning techniques* — local PDF, see `related-work.md`.
- Luft, J., & Schiewe, J. (2021). Automatic content-based georeferencing of historical topographic maps. *Transactions in GIS*, 25(6), 2888–2906. https://doi.org/10.1111/tgis.12794
- McAuliffe, C., Lage, K., & Mattke, R. (2017). Access to online historical aerial photography collections. *J. Map & Geography Libraries*, 13(2), 198–221. https://doi.org/10.1080/15420353.2017.1334252
- Meijers, M., & Schoonman, J. (2025). Mapping the edge. *e-Perimetron*, 20(1), 12–24 — see `allmaps.md` §3.
- Pope, R.-N.-A.-R., & Frean, M. (2025). Georeferencing historical maps at scale. *GIScience 2025*, LIPIcs 346, 11. https://doi.org/10.4230/lipics.giscience.2025.11
- DARPA/USGS AI for Critical Mineral Assessment, Map Georeferencing Challenge brief: https://criticalminerals.darpa.mil/Files/Georeferencing_Challenge_Details.pdf. Its lessons paper (ScienceDirect S2590197425000564) was not readable here (HTTP 403); no numbers are taken from it.
