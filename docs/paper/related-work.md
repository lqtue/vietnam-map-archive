# Related work — verified references, and the verdict on the gap claim

**Started 2026-09-19.** Phase 1 of the paper plan. Every entry was retrieved through scite on the
date given; nothing here is cited from memory. Status of this file: **item 3 (the gap claim) is
answered; items 1 and 2 (full audit verification, 25–35 paper depth) are in progress.**

---

## THE HEADLINE: the gap claim as planned does not survive

The plan proposed testing this sentence before committing to it:

> **nobody uses the series' own lattice as the evaluation set.**

**It is false.** Four published papers already do some form of it, and two of them are by people
already in `docs/private/network.md` whose most relevant work was evidently not read. Stating it
as planned would have been the kind of error a reviewer finds in ten minutes.

| paper | what it already does | how close to C3 |
|---|---|---|
| **Luft & Schiewe (2021)**, *Transactions in GIS* 25(6):2888–2906, `10.1111/tgis.12794` | Evaluates by comparing transformed map corners against **"the ground truth corner coordinates of the sheet boundaries"** from the series' sheet layout. And states the seam consequence in print: *"the alignment of corners also directly determines the ability to seamlessly join neighbouring transformed map sheets, which is a major concern for map users."* | **Closest. This is the lattice-as-evaluation-set idea, published.** Read in full 2026-09-19 — see §2 below |
| **Janata & Cajthaml (2020)**, *Applied Sciences* 11(1):299, `10.3390/app11010299` | Georeferences a multi-sheet series under **explicit sheet-adjacency constraints** in a least-squares adjustment, with IRLS / Huber M-estimate to downweight bad control points. 6,849 GCPs over 250 sheets of the First Military Survey. | Uses inter-sheet agreement as a **constraint**; we use the same information as a **diagnostic**. Read in full 2026-09-19 — see §3 below |
| **Uhl, Leyk & Chiang (2018)**, `10.20944/preprints201803.0021.v2` | Computes displacement vectors between each GCP's known world coordinates (graticule intersections) and its post-transformation position, explicitly *"to identify anomalies … where users should be careful with respect to further information extraction from such map sheets."* | Per-sheet georeferencing-quality anomaly detection across a whole archive. |
| **Gede & Varga (2021)**, *Proceedings of the ICA* 4:38, `10.5194/ica-proc-4-38-2021` | Detects map-content corners, OCRs the sheet identifier, derives the quadrangle extent from the ID, uses the corners as GCPs. 1,147 sheets at ~4 s each. **"False detection of the corners is automatically filtered by geometric analysis of the detected GCPs."** Corner error < 1% of sheet size on 89%, < 2% on 99%; sheet-ID recognition 75.9%. | **Closest to C2** — and it already has a geometric self-filter. |

Also relevant and already engaged with by the above: **Heitzler et al. (2018)** and **Burt et al.
(2020)** use printed marginal information and graticule intersections, with Burt et al. reaching
1–4 px RMSE on neatline corners and graticule intersections; **Kuna, Panecki & Zawadzki (2024)**,
`10.3390/ijgi13070249`, mosaic 60 irregular-cut sheets with a section titled *"rectification of
sheets and seam adjustment"*.

### What this costs, and what survives

**Cost.** C3 can no longer be framed as inventing series self-validation. The lattice must be
presented as **confirming and extending established practice**, with Luft & Schiewe and Janata &
Cajthaml cited as the prior art they are.

**Survives, and is still worth a paper.** Five claims, none of which appears in the work above:

1. **A self-consistency check can be blind by construction.** `graticule_error` reads the sheet's
   control points into the sheet's *own* datum and compares them against the graticule the sheet
   prints — so **both sides move together when the datum is wrong**, and it returns `2e-12` on a
   470 m fault. Every paper above validates geometry within an assumed frame. None reports the case
   where the frame itself is the error and the check is therefore silent. **This is the sharpest
   surviving claim and it generalises well past this corpus.**
2. **The silent-failure chain in the tooling**, measured: GDAL cannot map every NGA LGIDict code,
   so on `IND-I`/`INF-A` it warns, falls back to WGS 84, **and the warp still succeeds**; and PROJ
   via `EPSG:4131` **returns the input unchanged** for a point outside the transformation's area of
   use rather than failing — non-uniformly, `106.00,16.00` moves 470 m while `109.25,13.25` moves 0,
   so which sheets come back unshifted is not predictable from where they are. 285 of 437 shipped
   that way. This is infrastructure behaviour, not method, and nobody in this literature reports it.
3. **Lattice *collision*, not lattice *residual*.** Corner-displacement evaluation measures how far
   a sheet is from where it should be. It does not detect **two sheets claiming the same cell** —
   which is what caught `Ha Noi`, a sheet 75 km out that passes every per-sheet check (corners
   mutually consistent, ground scale to 0.78%, rim at the series offset, content unmistakably
   Hanoi). A distinct check with a distinct failure class.
4. **Printed corner coordinates in an obsolete angular frame as the GCP source.** Gede & Varga
   derive the extent from the sheet ID against a known series layout. These sheets print their own
   corners **in grades from the Paris meridian**, and there is no ID→extent table for the series.
   Reading the figures off the paper is the step that replaces the lookup.
5. **C1 — the survey / cell / printing model** is untouched by any of this literature.

### The reframing this forces

From *"the lattice is a novel test set"* to:

> **The checks that look like they should work are blind by construction, and what replaces them is
> an outside opinion.**

The lattice becomes supporting evidence and a confirmation of Luft & Schiewe, not the thesis. The
thesis becomes the failure taxonomy — which check can see which class of error, and why the
intuitive one sees nothing. That is a better paper and a more defensible one.

---

## Verified citations, running list

Retrieved through scite; `editorialNotices` checked and clean unless noted.

### Georeferencing — series and sheets

| ref | key figures | DOI |
|---|---|---|
| Luft & Schiewe (2021), *Transactions in GIS* | Karte des Deutschen Reiches 1:100,000; content-based via map symbols cross-referenced to OSM; **96% correct location predictions, median georeferencing error 101 m** | `10.1111/tgis.12794` |
| Luft & Schiewe (2021), *Proc. ICA* | CBIR over worldwide VGI-derived image features; KDR100 657 sheets in a regular grid; a skip heuristic saves ~⅓ of compute for 18 extra failures; a USGS 1:100,000 set of 197 quadrangles also tested | `10.5194/ica-proc-4-69-2021` |
| Gede & Varga (2021), *Proc. ICA* | Hungary 1:25,000; OpenCV + Tesseract + GDAL; 1,147 sheets at ~4 s/sheet; corner error < 1% of sheet size on 89%, < 2% on 99%; sheet-ID recognition **75.9%** | `10.5194/ica-proc-4-38-2021` |
| Janata & Cajthaml (2020), *Applied Sciences* | First Military Survey, Bohemia; LSM with sheet-adjacency constraints + IRLS/Huber; **6,849 GCPs over 250 sheets, ~27 per sheet**; 23 marginal sheets excluded because corners could not be read | `10.3390/app11010299` |
| Kuna, Panecki & Zawadzki (2024), *IJGI* | TKKP 1:126,000 (1843), 60 sheets, irregular cuts; TPS/adjust with a generated 10′×10′ grid, 20–60 points per sheet; prior work reported topographic-point deviations **reaching 500 m** | `10.3390/ijgi13070249` |
| Uhl, Leyk & Chiang (2018) | USGS topographic + Sanborn archives; GCP displacement vectors as an **anomaly** measure across sheets and time | `10.20944/preprints201803.0021.v2` |

### Segmentation / vectorization

| ref | key figures | DOI |
|---|---|---|
| Chen, Chazalon & Carlinet (2024), *PLOS ONE* | Paris atlases; **COCO Panoptic Quality throughout, no F1 reported**. Best pipeline **51.1% PQ** (U-Net + contrast + TPS augmentation); 46.7% pre-augmentation; 47.1 → 45.1 mini-U-Net ablation. Protocol follows ICDAR 2021 MapSeg Task 1 | `10.1371/journal.pone.0298217` |
| ICDAR 2021 Competition on Historical Map Segmentation | the protocol the above follows | `10.1007/978-3-030-86337-1_46` |
| Xia, Balestriero, Zhang et al. (2025), MapSAM2 | memory attention **+14.3 IoU vineyard, +16.1 railway**, 10-shot, Table 2 — verified. **"+12.8% F1 for prompt quality" could not be verified**: full text not indexed, arXiv record not open through scite. Cites YOLO (`10.1109/cvpr.2016.91`) from its Methods, so the shape is plausible; do not quote the number | `10.48550/arxiv.2510.27547` |

**Authorship flag.** MapSAM2's first three authors are **Xue Xia, Randall Balestriero, Tao Zhang**.
`network.md` §4f's premise — approaching ETH IKG as "the group whose code we run" — assumes Hurni /
Yizi Chen / Sidi Wu. Check the full author list and affiliations before that outreach is sent.

---

## §2 Related Work — the Luft & Schiewe paragraph

**Read in full 2026-09-19** (`read_fulltext`, 53,561 chars, six pages, `source: "fulltext"`).
`editorialNotices` clean. Everything below is quoted from that read.

### What the full read established

| | |
|---|---|
| **method** | Segment blue water symbols in CIE Lab (global threshold, negative b\*); rasterise OSM water into each candidate sheet's bounding box; FAST corners + pixel-patch descriptors; cross-correlation matching; RANSAC affine; pick the sheet with the most surviving matches; assign that sheet's bounding-box coordinates; fine-align the content with ECC registration; crop to the neatline for stitching |
| **corpus** | KDR100 1:100,000. The series is 674 original + 236 additional sheets; **the experiment uses 56** from Wikimedia at 400 ppi, mixed editions 1861–1913 |
| **localisation** | Two failures, named: sheet 12 (early hand-coloured, rivers not coloured) and sheet 79a (Helgoland, coastline only). Reported as **96%** |
| **accuracy** | median **101 m**, mean **168 m**, best 59 m (sheets 431, 333), worst >1,000 m. In pixels: mean RMSE 31.84 px, median 15.92 px, against Howe et al. (2019) 50.8 px mean / 46.1 px median (TPS) |
| **floor** | The affine model cannot rectify the trapezoid sheet shape: an expected minimum of 10–15 px at the corners, 7.5 px in the best case |
| **evaluation** | Corners annotated by hand on the **unwarped** original; template-matched in the warped output; their coordinates interpolated from the embedded spatial reference; compared against "the ground truth corner coordinates of the sheet boundaries"; both sides reprojected to WGS 84; geodetic distance; four corners averaged to one number per sheet |

Three quotations the positioning rests on:

> "For line-preserving transformations, any transformation error will interpolate linearly across
> the image. Consequently, the points of highest error will always be on one of the map corners.
> Therefore, it is sufficient to analyse the displacement of the transformed map corners from their
> expected positions in the series' sheet layout. Conveniently, the alignment of corners also
> directly determines the ability to seamlessly join neighbouring transformed map sheets, which is
> a major concern for map users."

> "Because neatlines are the first thing constructed and have the least projection error, they can
> be assumed to be drawn at the 'correct' place."

> "Location and extent for each sheet in the series are represented as sheet bounding boxes. The
> complete set of bounding boxes was constructed in advance from the map series' metadata."

**Count discrepancy inside the paper, noted so we never quote the raw fraction.** §4 says the method
"predicted the correct bounding box … for 53 of the 55 input maps"; §5 says "we located 96% (54 of
56) sheets correctly"; Figure 8's caption says 53 maps. Two failures either way, 96% either way.
**Quote "96%", never "53 of 55" or "54 of 56".**

**Also load-bearing for C4.** They do not need a neatline or graticule in the image, but they do
need the frame as prior knowledge: "Approximate geographic coordinates of each map's boundaries
need to be known. Those can usually be read from the map's margins." Their own Future Work names
relaxing exactly this — "the map sheets' coordinates" — as the open problem.

### The draft paragraph

> The nearest prior work is Luft and Schiewe (2021), who georeference sheets of the *Karte des
> Deutschen Reiches* 1:100,000 from their content: they segment the blue water symbols, match the
> resulting binary mask against OpenStreetMap water rasterised into each candidate sheet's bounding
> box, take the sheet with the most RANSAC-consistent patch matches, and finish with an ECC
> registration of content against reference. They report 96% correct sheet identification over 56
> sheets and a median georeferencing error of 101 m. What concerns us is not the matcher but the
> yardstick. Because a line-preserving transform spreads its error linearly, the extreme always
> falls at a corner, so they hold the transformed corners against "their expected positions in the
> series' sheet layout", and they state the consequence in print: "the alignment of corners also
> directly determines the ability to seamlessly join neighbouring transformed map sheets, which is
> a major concern for map users." Using the series' own lattice as the standard against which a
> sheet is judged is therefore established practice. The check we describe in §X confirms it on a
> second series and a different frame; it does not introduce it.
>
> Two properties of that construction bound what the yardstick can see, and both are this paper's
> subject. The first is that the sheet-layout bounding boxes are prior knowledge — "constructed in
> advance from the map series' metadata" — and are used twice: once to give the output image its
> spatial reference, and once as the ground truth the transformed corners are measured against. The
> number that results is the residual of the image registration *inside an assumed frame*. Should
> the frame itself be wrong — the datum, not the alignment — both sides of the comparison move
> together and the residual does not move at all. Luft and Schiewe are explicit that the corner
> metric is designed to exclude one class of error: corners are used because "neatlines are the
> first thing constructed and have the least projection error, [so] they can be assumed to be drawn
> at the 'correct' place", which keeps surveying and drawing error out of the measurement. It keeps
> datum error out of it too. §X reports a 470 m datum fault affecting 285 of 437 published sheets,
> on which a check of exactly this shape returns 2e-12.
>
> The second is that the seam is asserted rather than measured. Corner displacement is computed per
> sheet against the layout and averaged over four corners into a single value; no two neighbours are
> ever compared to each other. A per-sheet residual cannot separate a sheet that sits slightly off
> its cell from two sheets that claim the same cell — the failure that caught `Ha Noi`, 75 km from
> its cell while satisfying every per-sheet check (§Y). Inter-sheet agreement as a *constraint* is
> well established: Janata and Cajthaml (2020) adjust a 250-sheet series under explicit adjacency
> conditions. As a *diagnostic run across a whole archive*, it is not.

**Placeholders.** `§X` is the blind-check section, `§Y` the lattice-collision section; neither is
numbered yet. Resolve both before the preprint.

---

## §3 Related Work — the Janata & Cajthaml paragraph

**Read in full 2026-09-19** (`read_fulltext`, 35,112 chars, five pages, `source: "fulltext"`).
`editorialNotices` clean. Everything below is quoted from that read.

### What the full read established

| | |
|---|---|
| **corpus** | First Military Survey of the Habsburg monarchy, Bohemia, mapped 1764–1767 **à la vue** by officers on horseback — *"created with no geodetic basis"*, so no projection to invert. 273 sheets, 61.8 × 40.8 cm at 1:28,800, held as 400 dpi 24-bit TIFF, over 300 MB each |
| **method** | Affine (6 dof) or second-degree polynomial (12 dof) per sheet, with **every sheet adjusted jointly** by least squares under *condition equations* that force shared edges to coincide. Robustified by IRLS with Huber's M-estimate, `c = 1.5` (4% expected contamination), iterating until RMSE moves less than 0.1%. Own software, MultiGeoref (C++/Qt) |
| **scale** | 6,849 GCPs over 250 sheets, >27 per sheet → 13,698 measurement rows; 1,500 unknowns affine, 3,000 polynomial |
| **exclusion** | 250 of 273 sheets adjusted. **23 excluded** — marginal sheets whose corners cannot be read and which carry too few GCPs — with reattachment by individual polynomial transformation named as the remedy |
| **accuracy** | Best RMSE **280 m** (polynomial + IRLS); modal deviation 100–300 m |
| **external check** | ~50 control GCPs, deliberately disjoint from the adjustment set. Median positional deviation **~250 m for both** their mosaic and Mapire.eu's. Theirs never exceeds ~1,300 m; Mapire.eu passes that in four cases and reaches 2 km |
| **verdict on their own check** | *"it is not possible to unambiguously decide which dataset is better adjusted"* |
| **a published null** | GCP weighting by object category (churches / farmsteads / mills / crossings) — *"the existence of a correlation between this categorization and the achieved mean errors was not reliably proven"* |

Quotations the positioning rests on:

> "The map sheets have a marked map frame on the north and east sides only. The northeast corner
> is, thus, clearly identifiable. For others, finding the exact point is problematic, most, of
> course, in the southwest corner, where it is only possible to infer its position according to the
> map drawing."

> "Out of 273 map sheets, only 250 were selected to create the mosaic. The remaining 23 map sheets
> are marginal areas where it is not possible to read the corners of the sheets well and the
> numbers of GCPs are insufficient on them. Therefore, they were excluded from these calculations.
> Their addition to the resulting mosaic is possible after individual georeferencing using a
> polynomial transformation."

> "In our case, the conditions define the identity of the corresponding edges. … After applying
> them to the image data, the adjacent edges fit exactly together."

### The finding this read produced, which was not the one it was opened for

The read was opened to answer a narrow question — how they treat sheets whose corners cannot be
read. It answered it, and then gave up something better.

**Their seam is zero by construction, and therefore carries no information.** Edge identity is not
an outcome of their adjustment, it is a *condition equation inside* it. After the adjustment "the
adjacent edges fit exactly together" because they were required to, and a residual that was
consumed as a constraint cannot afterwards be read as a diagnostic. Our seam census — 750 seams,
median 19 m, 56 over 300 m, all 33 sheet↔hand-georeferenced seams at 447–504 m — measures
something only because those seams were left free.

**This is the second independent instance of the paper's own thesis in the nearest prior work, and
the mechanism is different from the first.** Luft & Schiewe are blind to a datum fault because the
frame is prior knowledge standing on both sides of the comparison (§2). Janata & Cajthaml are blind
to a seam fault because the seam was spent as a constraint. Neither is an error; both are the
ordinary consequence of a reasonable design. **That is the argument** — "blind by construction" is
not a criticism of these two papers but a description of a recurring structure they exhibit, which
is a far more defensible thing to put in front of their authors than a claim of novelty.

**And their control-point check reaching no verdict is a precedent worth citing in §8**, not a
weakness to pass over: they built an independent 50-point set specifically to decide between two
mosaics and reported in print that it could not, because 50 points do not cover Bohemia. A metric
that cannot see its own subject, published as such, by the nearest prior work.

### On the 23 excluded sheets — the question this read was opened for

Their exclusion rate is **23 of 273 = 8.4%**; ours is **4 of 58 = 6.9%** — Gia Bình, Phúc Nhạc,
Quất Lâm (thin-frame edition) and Thái Bình, which need hand-placed corners
(`allmaps-series-note.md` §5.5). The rates are close enough that neither side should be presented
as the tidier one, and the cause is the same in both: a sheet whose frame the detector cannot
anchor on.

The difference is in what the two frames offer. The First Military Survey sheets carry **a printed
frame on two sides only**, so their worst corner (southwest) is not detected but *inferred from the
drawing* — there is nothing there to detect. Our four are thin-frame printings of a series that
does draw four sides; the frame exists and the `argmax` anchor, which depends on the neatline being
the darkest thing on the strip by ~3×, does not clear on a thin one. Theirs is missing information;
ours is an anchor whose assumption fails. Worth saying precisely, because it is the honest version
of "our detector also has a failure set."

**Their remedy is the one to adopt and cite**: exclude from the joint solution, then reattach by
individual transformation afterwards. It keeps a hard case out of a global adjustment without
dropping the sheet from the archive — which is the same instinct as `pick_crs` refusing rather than
warping in at the smaller miss.

### The draft paragraph

> Inter-sheet agreement has been used before, as a constraint. Janata and Cajthaml (2020) adjust
> 250 sheets of the First Military Survey of Bohemia in a single least-squares solution — 6,849
> control points, more than 27 per sheet — in which the coincidence of shared sheet edges enters as
> a set of condition equations, robustified by iteratively reweighted least squares under Huber's
> M-estimate. The series was mapped *à la vue* and has no geodetic basis, so no projection can be
> inverted and the sheet edges are the only geometry available a priori; using them is the right
> move, and their best solution reaches 280 m RMSE on a corpus whose own drafting is far coarser
> than that. The consequence for verification is structural rather than accidental. Once edge
> identity is imposed as a condition, "the adjacent edges fit exactly together" by construction,
> and the seam residual is identically zero however the mosaic as a whole is placed. Information
> spent as a constraint cannot be spent again as a diagnostic. The seam census we report in §Y —
> 750 adjacent seams, median 19 m, with all 33 seams between the mosaic and an independently
> georeferenced sheet falling in a 447–504 m band that turned out to be a datum fault — is legible
> only because no adjacency condition was applied.
>
> This is the same shape as the limit described in §2, arrived at by a different route, and neither
> is a defect in the work that exhibits it: Luft and Schiewe cannot see a frame error because the
> frame stands on both sides of their metric, and Janata and Cajthaml cannot see a seam error
> because the seam is an input to their solution. What the two have in common is that the quantity
> a reader would most naturally reach for as evidence of correctness is, in each case, the quantity
> the method has already committed to. We take this as the general statement of the problem rather
> than as a gap in the literature.
>
> Both papers also report the limits of their own instruments, which is the register this one
> adopts. Janata and Cajthaml assembled roughly fifty control points, held out from the adjustment,
> to decide whether their mosaic or the Mapire.eu layer was better placed, and reported that "it is
> not possible to unambiguously decide which dataset is better adjusted" — the medians agree at
> about 250 m and fifty points do not cover Bohemia. They separately report a null on weighting
> control points by object category. We report comparable nulls in §8.

**Placeholder.** `§Y` is the seam-census section, still unnumbered — same as §2's `§X`/`§Y`.
Resolve all three before the preprint.

### Discipline note — a second internal count discrepancy

As with Luft & Schiewe's 53/54/55/56, this paper states its control set twice and differently:
Results says *"a new control layer of **more than 50** GCPs"*, Discussion says *"A group of **50**
control GCPs"*. Immaterial to the argument, but **write "about fifty", never a fraction or an exact
count.** Two of the four nearest papers having a countable inconsistency is itself a small argument
for the figures-file discipline this project runs on.

---

## Still to do in Phase 1

- [ ] Verify the remaining citations asserted in `work/deck-and-kg-2026-05/kg/AUDIT.md` and
      `docs/field-comparison.md` §Sources (mapKurator, ICDAR 2025 MapText, the GPT-4o legend paper,
      Bahgat & Runfola, Ingensand et al., the Jerusalem CaGIS 2025 paper, Tyagi & Dubey NCVPRIPG 2025).
- [x] **Read Luft & Schiewe (2021) *Transactions in GIS* in full — done 2026-09-19. Notes and the
      drafted §2 paragraph are in *§2 Related Work* above.**
- [x] **Read Janata & Cajthaml (2020) in full — done 2026-09-19.** Notes, the 23-vs-4 exclusion
      comparison and the drafted §3 paragraph are in *§3 Related Work* above. The read also produced
      the second blind-by-construction instance (the seam spent as a constraint), which is a
      stronger result than the question it was opened for.
- [ ] Find MapEdge (Meijers & Schoonman, ICA Bologna 2024 / *e-Perimetron* 20(1):12–24, 2025) — not
      indexed in scite under these search terms; may need the e-Perimetron site directly.
- [ ] Decide whether §7 keeps the IIIF size-segment finding or it ships as its own note.
- [ ] `report_citations` with the full include/exclude set once the list is closed.
