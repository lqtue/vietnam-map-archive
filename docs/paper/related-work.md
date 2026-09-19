# Related work — verified references, and the verdict on the gap claim

**Started 2026-09-19.** Phase 1 of the paper plan. Every entry was retrieved through scite on the
date given, or (§7.1, §7.5) through a direct fetch of a genuinely open copy when scite would not
serve one — flagged individually where that happened. Nothing here is cited from memory. Status of
this file: **item 3 (the gap claim) is answered; item 1 (full audit verification) is now complete —
all 7 asserted citations checked, plus the three §6 papers' `editorialNotices`; item 2 (25–35 paper
depth) is still in progress.**

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
> sheet is judged is therefore established practice. The check we describe in §7.2 confirms it on a
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
> datum error out of it too. §7.4 reports a 470 m datum fault affecting 285 of 437 published sheets,
> on which a check of exactly this shape returns 2e-12.
>
> The second is that the seam is asserted rather than measured. Corner displacement is computed per
> sheet against the layout and averaged over four corners into a single value; no two neighbours are
> ever compared to each other. A per-sheet residual cannot separate a sheet that sits slightly off
> its cell from two sheets that claim the same cell — the failure that caught `Ha Noi`, 75 km from
> its cell while satisfying every per-sheet check (§7.2). Inter-sheet agreement as a *constraint* is
> well established: Janata and Cajthaml (2020) adjust a 250-sheet series under explicit adjacency
> conditions. As a *diagnostic run across a whole archive*, it is not.

**Numbered 2026-09-19** against `outline.md`. Note the two `§X`s were *different sections* and a
blanket substitution would have merged them: the first is the lattice confirming Luft & Schiewe
(**§7.2**), the second is the blind self-check (**§7.4**). `§Y` is the lattice collision (**§7.2**).

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
> spent as a constraint cannot be spent again as a diagnostic. The seam census we report in §7.3 —
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

**Numbered 2026-09-19** against `outline.md`: the seam census is **§7.3**.

### Discipline note — a second internal count discrepancy

As with Luft & Schiewe's 53/54/55/56, this paper states its control set twice and differently:
Results says *"a new control layer of **more than 50** GCPs"*, Discussion says *"A group of **50**
control GCPs"*. Immaterial to the argument, but **write "about fifty", never a fraction or an exact
count.** Two of the four nearest papers having a countable inconsistency is itself a small argument
for the figures-file discipline this project runs on.

---

## §4 Related Work — MapEdge, found outside scite

**Found and read in full 2026-09-19.** Not through scite — **e-Perimetron mints no DOIs**, which is
why every search term tried in this Phase 1 pass returned nothing and why the handoff recorded it as
unresolved. It is a free PDF at `e-perimetron.org`. Record that reason next to the citation so
nobody re-runs the search.

> Meijers, M. & Schoonman, J. (2025). **Mapping the Edge: A Novel Approach to Georeferencing
> Historical Map Series.** *e-Perimetron* 20(1):12–24. ISSN 1790-3769.
> <http://www.e-perimetron.org/Vol_20_1/Meijers_et_al.pdf> · code
> <https://github.com/bmmeijers/mapedge/>

**Note the title.** It is *"Mapping the Edge: A Novel Approach to…"*, not *"A Novel Approach to…"* —
the short form is what a search engine returns. **Authorship confirmed correct**, unlike MapSAM2's:
Martijn Meijers (assistant professor, GIS technology, TU Delft) and Jules Schoonman (digital
curator, TU Delft Library), two authors, in that order.

### What the full read established

| | |
|---|---|
| **corpus** | Three series, **557 sheets**: Topografisch Militaire Kaart (TU Delft, 65 sheets, ±1850), North Korea (Stanford, 308, ±1916), Waterstaatskaart 1st ed. (Utrecht, 184, ±1860). All 1:50,000 |
| **method** | Low-res overview → binarise → **1D histogram of black pixels along each axis** → threshold → peak candidates → pairs ranked by a **fuzzy metric** (Zadeh) on pair separation and proximity to a user-stated expected position → approximate rectangle. Then high-res edge strips only, subdivided into **non-overlapping patches**; per patch a 1D histogram again, peaks ranked against a **user-supplied fuzzy width prior** ("best match between 6 and 8 pixels, but we also accept peaks between 4 and 10 pixels wide"); **RANSAC** line fit per side; intersect the four lines → corners, which serve as both the GCPs and the mask |
| **inputs required** | A digitised sheet index linking sheet geometry to world coordinates. For both Dutch series this **did not exist and had to be reconstructed from historical documentation** |
| **cost** | ~15 s per sheet including image transfer. Python, OpenCV, NumPy, Requests |
| **accuracy reported** | **No metric error figure anywhere in the paper.** The only numbers: on the TMK, opposite-side length differences of ~10 px horizontally and ~6 px vertically on sheets of 12,500 × 14,800 px at 600 dpi; corners "exact (pixel perfect)" in some cases, "a minor offset of a few pixels" in others, attributed to paper distortion and scanning |
| **failures** | 3 of 184 Waterstaatskaart sheets had neat lines missing around part of the frame, corners could not be deduced, and were done by hand in Allmaps Editor; masks hand-corrected where the map fragment stuck out past the frame |
| **an index error caught by the checks** | On 3 further sheets the checks revealed that **sheet-size exceptions had been digitised wrongly in their own sheet index**, and the index was corrected afterwards |

**Their five consistency checks**, which are the most developed per-sheet battery in this
literature and matter to §7:

1. enough points sampled along each rim, and enough RANSAC inliers;
2. **internal** — opposite sides equal, diagonals equal; the ratio of smaller to larger should be 1;
3. **external** — documented sheet size in cm × scan dpi → expected size in pixels, compared against
   the measured sides;
4. the distribution of inlier perpendicular distances against the fitted line, which detects **paper
   bulging or caving**;
5. a visual contact sheet of every detected corner with its IIIF crop, for browsing.

They do **not** compare a sheet to its neighbours, to a lattice, or to any external reference
geometry. There is no ground truth in the paper and no accuracy claim against one.

### Correction this read forces — and it was in our own figures file

`docs/paper/figures.md` §2 carried the row:

> | where MapEdge's inward walk stops here | at the graticule band — 40 px / 170 m short, residuals
> 14–41 px, every edge rejected |

**MapEdge has no inward walk.** The inward walk is *ours* — `scripts/l7014_neatline.py`, which walks
in from the blank margin until the paper stops being paper. `allmaps-series-note.md:109` and
`docs/private/allmaps.md:195` both say so correctly; the figures file compressed the sentence and
moved the method from us to them. Fixed in this commit.

This is worth dwelling on for one line, because it is the exact failure the figures file exists to
prevent, found inside the figures file: a claim that would have put a method Meijers never wrote
into his mouth, **in a paper we plan to send him**, sourced to a row that looked checked.

### What MapEdge actually differs from us in

Both methods take 1D black-pixel profiles over full-resolution edge strips cut into patches, fit a
line per side and intersect. **The difference is peak selection.** MapEdge ranks candidate peaks
against a user-declared fuzzy width prior and a threshold. We take `argmax` with no threshold and no
rule, because on these sheets the thick neatline is the darkest thing on the strip by a factor of
three. Ours needs no prior and cannot be tuned; theirs is adaptable to layouts ours would fail on.
That is the honest statement of the trade, and it is a much smaller and more defensible claim than
the one the figures file implied.

### The graticule failure is *their* stated limitation, which strengthens our position

Their Discussion, verbatim:

> "confusion can still occur, for instance, when map features inside the map fragment close to the
> rim share similar characteristics with the rim side. For example, **linear features, such as
> graticule lines, can occupy the same number of black pixels as the neat line.**"

That is precisely our Như Trác failure — the walk stopping on the graticule band, 40 px and 170 m
short, residuals 14–41 px, every edge rejected. **So this is not a gap we found in MapEdge; it is a
limitation its authors state in print, on which we have a worked case and a concrete answer.** Same
reframing as §2 and §3: cite it as taking up their stated open problem, never as a deficiency
discovered. It is also, straightforwardly, the most useful thing we can offer them.

### A measurement against their future work

Their Discussion also proposes:

> "Considering each neat line as two separate halves and estimating the location of the straight
> line for each half separately could potentially reduce the influence of distant points (that
> reside near the opposite corners)."

We have measurements in the same neighbourhood, and they carry a warning their framing does not
anticipate: averaging over half a sheet is exactly what fails when the scan is off square. Up to
0.8° of skew smears a 10 px line across 30 and lets a weaker, shorter feature win the `argmax`; a
half-width average put Như Trác's top neatline **35 px** from where it is. And fitting each side
independently — four rotations rather than one — made opposite edges of the quad differ by **14 px**
where the projection says 4.

**State this carefully.** Their proposal is per-half fitting to cut leverage from distant points;
ours is evidence that the tilt must be solved once, globally, before any averaging. The two are
compatible and the second constrains the first. Do not write it as a refutation.

### `Ha Noi` against their five checks — the §7 paragraph this read makes possible

The sharpest use of this paper is not in Related Work at all. MapEdge's battery is the most complete
set of per-sheet checks published, and our `Ha Noi` sheet — 75 km from the city it names — survives
it:

| their check | `Ha Noi` |
|---|---|
| 1 · enough rim points and inliers | passes; normally detected sheet |
| 2 · internal — opposite sides and diagonals equal | passes; "corners agree with each other" |
| 3 · external — sheet cm × dpi vs measured pixels | passes; **ground scale agrees with pixels to 0.78%** |
| 4 · inlier residuals → paper bulge or cave | passes, and **cannot fail**: a flatness test is structurally incapable of seeing a translation |
| 5 · visual browse of corner crops | passes; the content is unmistakably Hanoi |

Nothing here is a criticism of the battery, which does what it claims. The point is that **all five
are per-sheet**, and a sheet sitting on another sheet's cell is not a per-sheet property. It took a
lattice collision to catch it. This is the third and cleanest instance of the paper's thesis: §2's
frame stands on both sides of the metric, §3's seam is spent as a constraint, and §4's checks are
each individually sound and collectively blind to one class of error by virtue of their scope.

### Two bibliographic notes

- **Burt et al.** — our running list says *(2020)*; MapEdge's reference list gives *Burt, J. E.,
  White, J., Allord, G., Then, K. M., and Zhu, A.-X. (2019). Automated and semi-automated map
  georeferencing. Cartography and Geographic Information Science, 47(1):46–66.* CaGIS 47(1) is a
  2020 issue with 2019 online-first. Pick one form and use it consistently; check before citing.
- MapEdge cites Luft & Schiewe (2021), Gede et al. (2022) and Heitzler et al. (2018) — **we are in
  the right neighbourhood and these four papers already cite each other.** A submission to
  e-Perimetron lands in the middle of an existing conversation rather than beside it.

---

## §5 Two citations verified from the audit's asserted list

Partial progress on Phase 1 item 1. Two of the seven taken; the other five are listed as still
open at the bottom of this file, deliberately un-fudged.

### Tyagi & Dubey — real, correctly attributed, and **its numbers cannot be quoted**

The plan calls this *"the closest published work to C2"* and says it must be engaged directly. The
record resolves and the attribution is sound:

> Tyagi, P. & Dubey, V. **Automated Georeferencing of Topographic Maps via OCR and In-Context
> Multimodal LLM Reasoning.** Springer Nature Switzerland, pp. 99–113.
> `10.1007/978-3-032-08511-5_8`

| | |
|---|---|
| authors | Pallavi Tyagi, Vishal Dubey — **as our notes say**, unlike MapSAM2 |
| venue | NCVPRIPG 2025 proceedings, published by Springer; scite dates the volume **2026** |
| access | **closed.** `contentDenied: true`, `oaStatus: "closed"`, no full text and no abstract served. Orderable at about $37.95 |

**The problem.** `docs/field-comparison.md` and the plan attribute specific figures to it — *internal
RMSE < 5 m, validation < 30 m on 11 of 12 sheets, < 350 s per sheet*. **None of those can be
verified**, because nothing of the paper's body is readable through scite and the abstract was not
served either. They are in the same position the MapSAM2 "+12.8% F1" claim was in, and they get the
same treatment:

> **Do not quote Tyagi & Dubey's numbers.** Cite the work as the nearest published approach to C2 —
> printed graticule coordinates read by OCR plus multimodal LLM reasoning — and attribute no figure
> to it until someone has read it.

**This is a decision for Tue, not one to default.** It is the single closest paper to our own method
and it is the one paper in the set we cannot read for free. Either $37.95 buys the ability to
position C2 honestly against it, or C2 is written to engage it by method and not by number. The
second is defensible; the first is better. Worth resolving before Phase 3, not during it.

### The GPT-4o legend paper — verified, and it is Paper 2's, not Paper 1's

> Kirsanova, S., Chiang, Y.-Y. & Duan, W. (2025). **Detecting Legend Items on Historical Maps Using
> GPT-4o with In-Context Learning.** arXiv. `10.48550/arxiv.2510.08385` — open access, green.

| | |
|---|---|
| method | LayoutLMv3 for layout detection + GPT-4o with in-context learning, linking legend items to their descriptions by bounding-box prediction |
| figures | **88% F-1 and 85% IoU**, GPT-4 with structured JSON prompts against their baseline |
| reported to affect performance | prompt design, number of examples, layout alignment |
| context | part of **DIGMAPPER**, under the DARPA **CriticalMAAS** programme |
| Yao-Yi Chiang | also an author of Uhl, Leyk & Chiang (2018) already in our list — same group, two of our references |

Relevant to us because **structured JSON prompting beating a baseline, and prompt design mattering
independently of the model, is the same result as Paper 2's "model moves the boxes, prompt moves the
reading"** on one square. Cite it there. It has nothing to say about Paper 1 and should not be
padded into §2.

---

## §6 Three papers read from PDF, 2026-09-19

Supplied by Tue (two in `~/Downloads`, one arXiv link) rather than found through scite. **Read from
the PDFs directly**, so the figures below are quoted from the papers themselves — but note the
provenance difference: `editorialNotices` were **not** checked through scite for these three, unlike
every entry in the running list above. Do that before the preprint ships.

### 6.1 Milleville, Verstockt & Van de Weghe (2022) — the other automatic route, with a number

> **Automatic Georeferencing of Topographic Raster Maps.** *ISPRS Int. J. Geo-Inf.* 11(7):387.
> `10.3390/ijgi11070387` · MDPI, open access · received 24 May 2022, published 11 July 2022.

| | |
|---|---|
| **method** | Fully automatic, no GCP placement: recognise the text on the map → geocode the toponyms through public geocoders → cluster the matches → filter outliers with RANSAC → refined ROI → final prediction |
| **corpus A** | M834 Belgium, **16 adjacent sheets** around Ghent, 2nd edition 1980–87, NGI. 225 dpi (6300 × 4900 px), 1:25,000, mean diagonal **18.94 km** |
| **corpus B** | TOP50raster Netherlands, **9 adjacent sheets**, 2018, PDOK. 508 dpi (8000 × 10,000 px), 1:50,000, mean diagonal **32.06 km** |
| **ground truth** | **External and independent** — the official NGI metadata polygon for A, the GeoTIFF's own corners for B, both converted to WGS84 |
| **result** | Mean error **316 m (1.67% of diagonal)** on A, max 631 m (3.33%); **287 m (0.90%)** on B, max 438 m (1.37%). Centre errors 179 m and 162 m. Mean of three runs |
| **the pipeline's own ladder** | A: prefilter 138 km → initial ROI 17.4 km → refined ROI 710 m → **final 316 m**. The filtering is almost all of the accuracy |
| **distribution** | 15 of 16 M834 sheets under 500 m mean error; 11 of 16 under 200 m centre error |

**A published metric caution, and it is our §8's exact shape:**

> "the center error is not a good indicator of overall accuracy. As we only compared the predicted
> and ground truth center; there is no indication of the relative scale of the predicted area.
> Without filtering, the geolocation algorithm consistently predicted much larger areas than the
> actual map."

A metric that agrees with the truth at the centre while being wrong about the extent — reported by
the authors against their own result. Third such precedent in this file, after Janata & Cajthaml's
undecidable control set and Luft & Schiewe's stated floor.

**The gap, and it is a clean one.** They have **16 adjacent sheets and 9 adjacent sheets**. They
have a series. **Adjacency is never used** — not as a constraint (Janata & Cajthaml), not as a
diagnostic (ours). Every sheet is scored independently against external ground truth, and the
neighbours are right there. This is the strongest single piece of evidence that inter-sheet
agreement as a *free* check is genuinely underused, because here is a paper that had it for nothing
and did not reach for it.

**It is also Paper 2's nearest prior work.** The plan's Paper 2 is a toponym-assisted georeferencing
benchmark; this is that, done, with a number. **Paper 2's target to beat is 316 m at 1:25,000.**
That belongs in the plan, not just here.

### 6.2 Wijegunarathna, Stock & Jones (2025) — an LMM reading a map, and an infrastructure fault

> **Large Multi-modal Model Cartographic Map Comprehension for Textual Locality Georeferencing.**
> GIScience 2025, LIPIcs. `10.4230/LIPIcs.GIScience.2025.12` · arXiv:2507.08575 · Massey University
> and Cardiff.

Different task from ours: georeferencing **textual locality descriptions** from natural history
collections, not map sheets. A labelled square grid is superimposed on a map excerpt and an LMM
(`gpt-4o-2024-08-06`) is asked which cell the description denotes. Zero-shot.

| method | avg distance | @1 km | @3 km |
|---|---|---|---|
| GEOLocate (text, ±region) | 107.23 km | 16.0% | 28.0% |
| ChatGPT text | 10.91 km | 8.0% | 16.0% |
| ChatGPT text+region | **10.12 km** | 8.0% | 16.0% |
| GPT-4o text | 155.82 km | 4.0% | 16.0% |
| GPT-4o text+region | 39.98 km | 0% | 12.0% |
| **theirs** (centroid) | **1.03 km** | **60.0%** | 96.0% |

32% of predictions land in exactly the right grid cell. Self-described as preliminary, on a small
manually annotated set.

**The finding worth taking, and it is not the headline.** ChatGPT-in-a-browser scores 10.91 km and
*the same model through the API* scores 155.82 km — a 14× difference from the access path, which
they diagnose:

> "The stark difference in performance between the browser versions and the same model accessed via
> the API raise an important issue: the inability to browse the web in the API versions
> significantly hinders the quality of georeferencing."

**A published number that depends on undocumented infrastructure rather than on method.** This is
precisely the class our repo keeps finding — GDAL falling back to WGS 84 and succeeding, PROJ
returning the input unchanged, `_cached_tile` writing a different key than it reads, PostgREST
capping at 1,000 rows and reporting nothing. Cite it in §8 or in Paper 2 as outside evidence that
the class is real and is not our local bad luck.

### 6.3 Namgung & Chiang (2022) — post-OCR using where the words sit

> **Incorporating Spatial Context for Post-OCR in Map Images.** GeoAI '22 (5th ACM SIGSPATIAL
> International Workshop on AI for Geographic Knowledge Discovery), Seattle, 1 Nov 2022.
> `10.1145/3557918.3565864`

BART fine-tuned to correct map OCR, where word-level text is first assembled into pseudo-sentences
by **spatial clustering** (K-means) rather than by reading order — so "Mississippi" and "River" are
joined because of where they sit, not because a language model expects them. Trained on
automatically generated synthetic maps.

Recall improves **26% (Illinois) and 32.1% (Minnesota)** on synthetic maps, against the best lexical
method's 4% and 7%.

**Paper 2, not Paper 1.** It is the nearest prior work to our syllable-aware Vietnamese dedupe —
same problem (map text is not a sentence and must not be treated as one), opposite direction (they
assemble neighbours into phrases; we had to *stop* a bare `Đường` chaining 43 streets into one
cluster). Worth engaging directly there. **Yao-Yi Chiang is now on three papers in our set** — this,
the GPT-4o legend paper (§5), and Uhl, Leyk & Chiang (2018).

### `editorialNotices` check, 2026-09-19 — the item this read left open

Closing the gap the read-from-PDF provenance note above flags. All three fetched through scite by
DOI (`search_literature`, metadata-only call, no `term`); none returned an `editorialNotices` field,
which is how a clean record reads through this tool (contrast the retraction/correction/concern
fields scite populates when a notice exists). **All three clean.**

| DOI | result |
|---|---|
| `10.3390/ijgi11070387` (Milleville et al.) | clean |
| `10.4230/LIPIcs.GIScience.2025.12` (Wijegunarathna et al.) | clean |
| `10.1145/3557918.3565864` (Namgung & Chiang) | clean |

### What the three add to Paper 1 — the error ladder

Stated carefully, because the comparison is easy to make dishonestly:

| | reported error |
|---|---|
| Automatic, content-based — Luft & Schiewe (2021) | **101 m** median |
| Automatic, toponym-based — Milleville et al. (2022) | **316 m** / **287 m** mean |
| LMM on locality descriptions — Wijegunarathna et al. (2025) | **~1.03 km** |
| **Our human-placed GCPs** | **9.0 m to 1,415.9 m** RMSE across the 274-sheet archive; the 1882 sheet at **12.7 m**, and **65% of all extractions sit on a sheet with a bad stated limit or none** |
| **The L7014 datum fault we shipped** | **~470 m** |

> **note 2026-09-19 — this row read "**2.3–19.0 m** rms; the 1882 sheet at **11.3 m** RMSE".**
> Both figures were wrong. 11.3 m is the superseded spherical-earth conversion, now 12.7 m geodetic
> (`docs/worked-example-1882.md:44`). The 2.3–19.0 m range is worse than superseded — it understated
> the archive's ceiling by nearly 4×. Measuring all six District 4 sheets through one code path
> (`work/analysis/district4/georef_error.md`) puts **1942 at 72.3 m RMSE, worst point 193.7 m**, on
> the sheet carrying 31.7% of all extractions. Two of the six cannot be measured from their own GCPs
> at all.
>
> **The archive-wide pass has since run** — all 274 sheets, one code path
> (`work/analysis/georef_coverage.md`). It is worse than District 4 suggested. Eight sheets are worse
> than 1942; the worst is 1,415.9 m. **1922 (Carte routière des environs de Saïgon) is at 456.9 m and
> is the archive's third most-extracted sheet** (1,420 rows). 35 of 274 sheets cannot be measured
> from their own control points at all. Counted by extraction row rather than by sheet, **65.0%
> (8,796 of 13,525) sit on a sheet whose stated limit is bad or absent.**

**The only honest comparison in this table is the last two rows against the middle ones**, and it is
worth one sentence in §1:

> The displacement we published without noticing is larger than the total georeferencing error that
> the automatic literature reports as a success.

What must **not** be written is that our 11 m beats their 101 m or 316 m. Those methods georeference
a sheet from nothing; ours are human-placed control points. `field-comparison.md` §6 already says
*"not competing — we use humans"*, and that row is right. The ladder's purpose is to size the fault,
not to rank the methods.

---

## §7 The five remaining verifications, 2026-09-19

mapKurator, ICDAR 2025 MapText, Bahgat & Runfola, Ingensand et al., and the Jerusalem CaGIS 2025
paper — the five left open at the bottom of this file. All five are real, correctly attributed
(one correction below), and clean of editorial notices. Access and number-verification differ per
paper and are called out individually.

### 7.1 mapKurator — real, correctly attributed, numbers confirmed via an open duplicate

> Kim, J., Li, Z., Lin, Y., Namgung, M., Jang, L., & Chiang, Y.-Y. (2023). **The mapKurator System:
> A Complete Pipeline for Extracting and Linking Text from Historical Maps.** ACM SIGSPATIAL '23
> (demo). `10.1145/3589132.3625579` — closed, purchase ~$37.95 via Article Galaxy, `contentDenied:
> true`. An identical-title arXiv preprint exists: `10.48550/arxiv.2306.17059` (green OA,
> CC BY-NC-ND) — also `contentDenied` through scite's `read_fulltext`, but genuinely open, so read
> directly from arXiv instead.

| | |
|---|---|
| authors | **Yao-Yi Chiang is confirmed on the author list** — scite's author-filtered search returns him first (Chiang, Kim, Li…), the unfiltered call returns Kim, Li, Lin first; both are the same six-author set (Kim, Li, Lin, Namgung, Jang, Chiang). `network.md`'s "mapKurator via the Knowledge Computing lab" attribution to Chiang is **correct** — unlike the MapSAM2 case, where the same kind of assumption was wrong |
| figures | Read from the arXiv PDF directly (`arxiv.org/abs/2306.17059`): **"over 60,000 maps"** and **"over 100 million text/place names"**, both from the David Rumsey Historical Map collection — matches `field-comparison.md`'s "60,000+ maps, 100M+ text labels" exactly |
| not confirmed | The **"~57,000 georeferenced maps processed"** sub-figure in `field-comparison.md` — the arXiv abstract page didn't surface it and a full-PDF fetch timed out. Not contradicted, just not independently reread; treat as unverified rather than wrong |
| editorialNotices | clean on both DOIs |
| access | ACM version closed; arXiv preprint open — cite the arXiv DOI as the accessible copy |

### 7.2 ICDAR 2025 MapText — real, a misattribution found and corrected, numbers confirmed

> Lin, Y., Tual, S., Li, Z., et al. (25 authors). **ICDAR 2025 Competition on Historical Map Text
> Detection, Recognition, and Linking.** *ICDAR 2025*, Springer. `10.1007/978-3-032-04630-7_33` —
> nominally green OA per scite metadata, but `read_fulltext` returned `contentDenied` and both the
> Springer chapter page (login redirect) and the EPFL infoscience handle (405) blocked direct fetch.

**A misattribution found and fixed.** `docs/image-processing-record.md:219` cited this as **"(Zou et
al. 2025)"**. scite gives the first author as **Yijun Lin** (confirmed independently by the
competition's own site, `rrc.cvc.uab.es/?ch=32`, which lists the full 25-name organiser roster —
Lin, Tual, Li, Jang, Chiang, Weinman, Chazalon, Carlinet, Perret, Abadie, Duménieu, Chan, Liao, Su,
**Zou**, Dai, Petitpierre, Vaienti, Kaplan, di Lenardo, Baek, Hentschel, Nakagome, Shuta, Lee,
Choi). Mengjie Zou is on the list, far from the front — not the lead author. **Corrected to "Lin et
al. 2025" in `image-processing-record.md`, dated note left in place** (old wording quoted there).
Worth flagging: Beatrice Vaienti, Frédéric Kaplan and Isabella di Lenardo — the Jerusalem CaGIS
authors, §7.5 below — are also on this competition's organiser list.

**Figures**, confirmed via the competition's own site rather than the paper's fulltext (which scite
would not serve and direct fetches were blocked): **seven teams, 25+ submissions, four tasks, three
datasets** — Rumsey, expanded French Land Registers, and a **new Taiwanese dataset with Chinese
characters**; **"detection performance is strong... recognition and linking remain difficult."**
Matches `field-comparison.md`'s "7 teams, 25+ submissions, 4 tasks, 3 datasets… detection strong,
recognition and linking still hard" exactly. editorialNotices clean.

### 7.3 Bahgat & Runfola (2021) — real, correctly attributed, one figure in our docs could not be found in the paper and is now corrected

> Bahgat, K. & Runfola, D. M. (2021). **Toponym-assisted map georeferencing: Evaluating the use of
> toponyms for the digitization of map collections.** *PLOS ONE* 16(11):e0260039.
> `10.1371/journal.pone.0260039` — gold OA, CC-BY, `contentDenied: false`. editorialNotices clean.

**Read in full** (45,297 chars, all pages, `source: "fulltext"`). Authors and venue match our
citation exactly. Two things checked and confirmed:

- **"usable for data extraction… in nearly half of cases"** is a near-verbatim echo of the abstract:
  *"sufficiently accurate to be used for data extraction purposes in nearly half of all cases."*
  Their real-world sample: 40% of maps at <5% error (their high-accuracy bar), 44% at <1% error;
  their simulated sample's true success rate at <1% error is 12.6%.
- **"≥ ~10 toponyms"** matches: *"As few as 10 toponyms was shown to be sufficient… accuracy
  dropping from about 80%… to 40% with smaller numbers of toponyms."*

**One figure could not be found and appears to be wrong.** `field-comparison.md:145` read *"affine
RMSE elsewhere reported 16.9–84.2 px, i.e. sometimes too imprecise."* Nothing in the paper's full
text supports it: the paper never uses the word "affine" — it compares **1st/2nd/3rd-order
polynomial transforms** (1st order used in 69% of maps) — and it never reports error in raw pixels
anywhere; every accuracy figure is a **percentage of map radius** (`trueMax`, `modelMax`, `modelMax
LOO`). No "16.9" or "84.2" appears in any of the six 8,000-char pages read. **Corrected in
`field-comparison.md` 2026-09-19**: the cell now quotes the real figures above and flags the old
pixel range as unsupported rather than repeating it.

### 7.4 Ingensand, Lecorney & Blanc (2022) — real, correctly attributed, no number in our docs to check

> Ingensand, J., Lecorney, S. & Blanc, N. (2022). **An open API for 3D-georeferenced historical
> pictures.** *Int. Arch. Photogramm. Remote Sens. Spatial Inf. Sci.* XLVIII-4/W1-2022:217–222.
> `10.5194/isprs-archives-xlviii-4-w1-2022-217-2022` — diamond OA, CC-BY, `contentDenied: false`.
> editorialNotices clean.

Authors, volume and pages match `260912-postgrad-route.md`'s reference exactly. Our docs cite this
conceptually — "the host owns the image, the dataset owns the geometry" (`network.md`), "the
rights-separation model `smapshot` uses" (`260912-postgrad-route.md:22`) — rather than by number, so
there is no figure to verify against the text. As a sanity check: the abstract describes an open API
onto **Smapshot**, an existing database of **200,000 3D-georeferenced images** contributed by **over
800 volunteers** via monoplotting, which is consistent with — though not a direct statement of — the
rights-separation framing our docs attribute to it.

### 7.5 The Jerusalem CaGIS 2025 paper — real, correctly attributed, numbers corroborated independently (not via scite fulltext)

> Vaienti, B., di Lenardo, I. & Kaplan, F. (2025). **Georeferencing historical maps using local
> feature matching and Delaunay consistency.** *Cartography and Geographic Information Science*,
> published online 2025-11-06. `10.1080/15230406.2025.2566789` — hybrid OA, CC-BY per scite
> metadata, but `read_fulltext` returned `contentDenied` (nothing indexed) and direct fetches to
> Taylor & Francis (403) and the `getft.io` redirect both failed. **Not read in full**; everything
> below is corroborated through an independent secondary source (web search over the paper's
> abstract/summary as indexed elsewhere), not scite's own fulltext.

| | |
|---|---|
| authors | Beatrice Vaienti, Isabella di Lenardo, **Frédéric Kaplan** — Kaplan is the EPFL DHLAB
director `network.md` names, so the attribution there is directionally correct |
| method | confirmed: **SuperPoint + SuperGlue** for feature matching, **RANSAC** plus a
**Delaunay-based consistency check** to discard erroneous matches — matches "SuperPoint + SuperGlue
+ Delaunay consistency" in `field-comparison.md` |
| headline number | confirmed: **RMSE below 1% of the map diagonal for 71 of 86** georeferenced
historical maps of Jerusalem — matches `field-comparison.md`'s "RMSE < 1% of map diagonal on 71 of
86 maps" exactly. 71/86 = 82.6%, which is also where `field-knowledge-graph.md` and `AUDIT.md`'s
"83% of 86 Jerusalem maps" comes from — **not an internal contradiction**, the same fact in two
units, unlike the Luft & Schiewe / Janata & Cajthaml cases |
| corpus note | the pipeline was separately applied to 113 non-georeferenced maps, of which 86 were
successfully georeferenced past a keypoint-count threshold — a different "86" from the evaluation
set above; not something our docs currently quote, flagged here so it isn't conflated later |
| editorialNotices | clean (scite metadata) |

**Caveat, stated plainly.** Every other paper in this file with a quoted number was either read in
full through scite (`source: "fulltext"`) or, for the closed-access cases, explicitly marked
unverifiable. This one sits in between: genuinely open access, but not served by scite and blocked
on direct fetch, so the confirmation above rests on a secondary source rather than the primary text.
Treat the numbers as corroborated, not scite-verified, and read the paper directly before the
preprint ships if the 71/86 figure needs to survive review.

### Bibliographic note found in passing

`docs/private/network.md:102` describes Kaplan's relevant work as **"their Jerusalem 1840–1940 4D
paper"** — a description that may point at a different EPFL DHLAB Jerusalem publication (there is
at least one more, on planimetric distortion clustering, `10.3390/ijgi14030132`) rather than this
CaGIS 2025 local-feature-matching paper. Not corrected here — `network.md` is outside this file's
scope and the checklist item named "the Jerusalem CaGIS 2025 paper," which is what §7.5 verifies —
but worth checking before that outreach goes out.

---

## Still to do in Phase 1

- [x] Verify the remaining citations asserted in `work/deck-and-kg-2026-05/kg/AUDIT.md` and
      `docs/field-comparison.md` §Sources. **7 of 7 done 2026-09-19 — see §5 and §7 above.**
      - [x] **Tyagi & Dubey** — DOI and authorship verified; **closed access, numbers unverifiable**,
            and a decision is pending on whether to buy it (§5).
      - [x] **The GPT-4o legend paper** — verified as Kirsanova, Chiang & Duan (2025), 88% F-1 /
            85% IoU. Belongs to Paper 2, not Paper 1 (§5).
      - [x] **mapKurator** — real, Chiang's authorship confirmed, 60,000+ maps / 100M+ labels
            confirmed via an open arXiv duplicate of the closed ACM paper (§7.1).
      - [x] **ICDAR 2025 MapText** — real; **misattribution found and fixed** (was "Zou et al.",
            first author is Yijun Lin); 7 teams / 25+ submissions / 4 tasks / 3 datasets confirmed
            via the competition's own site (§7.2).
      - [x] **Bahgat & Runfola** — real, correctly attributed; **the "affine RMSE 16.9–84.2 px"
            figure in `field-comparison.md` does not appear anywhere in the paper and has been
            corrected** — the paper reports percentage-of-radius accuracy only, never pixel RMSE,
            and never uses the word "affine" (§7.3).
      - [x] **Ingensand et al.** — real, correctly attributed; our docs cite it conceptually, no
            number to verify (§7.4).
      - [x] **The Jerusalem CaGIS 2025 paper** — real, correctly attributed; method and the "71 of
            86 maps" figure corroborated, though through a secondary source rather than scite
            fulltext (closed to both scite and direct fetch) — flagged as such (§7.5).
- [x] **Read Luft & Schiewe (2021) *Transactions in GIS* in full — done 2026-09-19. Notes and the
      drafted §2 paragraph are in *§2 Related Work* above.**
- [x] **Read Janata & Cajthaml (2020) in full — done 2026-09-19.** Notes, the 23-vs-4 exclusion
      comparison and the drafted §3 paragraph are in *§3 Related Work* above. The read also produced
      the second blind-by-construction instance (the seam spent as a constraint), which is a
      stronger result than the question it was opened for.
- [x] **Find and read MapEdge — done 2026-09-19.** Full read, notes and the drafted material are in
      *§4 Related Work* above. It is not in scite because **e-Perimetron mints no DOIs**; the PDF is
      free at `e-perimetron.org`. The read corrected a misattribution in `figures.md`, and produced
      the `Ha Noi`-against-their-five-checks table, which belongs in §7 rather than §2.
- [x] Check `editorialNotices` through scite for the three papers in §6 — done 2026-09-19, all
      three clean. See the "`editorialNotices` check" note inside §6.
- [ ] Move "Paper 2's target to beat is 316 m at 1:25,000" (§6.1) into the plan's Paper 2 entry.
- [ ] Decide whether §7 keeps the IIIF size-segment finding or it ships as its own note.
- [ ] `report_citations` with the full include/exclude set once the list is closed.
