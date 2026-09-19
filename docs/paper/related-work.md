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
| **Luft & Schiewe (2021)**, *Transactions in GIS* 25(6):2888–2906, `10.1111/tgis.12794` | Evaluates by comparing transformed map corners against **"the ground truth corner coordinates of the sheet boundaries"** from the series' sheet layout. And states the seam consequence in print: *"the alignment of corners also directly determines the ability to seamlessly join neighbouring transformed map sheets, which is a major concern for map users."* | **Closest. This is the lattice-as-evaluation-set idea, published.** |
| **Janata & Cajthaml (2020)**, *Applied Sciences* 11(1):299, `10.3390/app11010299` | Georeferences a multi-sheet series under **explicit sheet-adjacency constraints** in a least-squares adjustment, with IRLS / Huber M-estimate to downweight bad control points. 6,849 GCPs over 250 sheets of the First Military Survey. | Uses inter-sheet agreement as a **constraint**; we use the same information as a **diagnostic**. |
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

## Still to do in Phase 1

- [ ] Verify the remaining citations asserted in `work/deck-and-kg-2026-05/kg/AUDIT.md` and
      `docs/field-comparison.md` §Sources (mapKurator, ICDAR 2025 MapText, the GPT-4o legend paper,
      Bahgat & Runfola, Ingensand et al., the Jerusalem CaGIS 2025 paper, Tyagi & Dubey NCVPRIPG 2025).
- [ ] Read Luft & Schiewe (2021) *Transactions in GIS* in full — it is the nearest prior work and
      the paper's positioning depends on getting its claims exactly right.
- [ ] Read Janata & Cajthaml (2020) §Discussion — how they treat sheets whose corners cannot be read
      (23 excluded) against our four thin-frame sheets.
- [ ] Find MapEdge (Meijers & Schoonman, ICA Bologna 2024 / *e-Perimetron* 20(1):12–24, 2025) — not
      indexed in scite under these search terms; may need the e-Perimetron site directly.
- [ ] Decide whether §7 keeps the IIIF size-segment finding or it ships as its own note.
- [ ] `report_citations` with the full include/exclude set once the list is closed.
