# Allmaps — relationship, findings, and outbound drafts

The working file for everything we send to, ask of, or contribute to the Allmaps
project. Drafts live here until they are sent; findings live here so the next
draft does not re-derive them. Update it in place — it is not a journal entry.

Related: `docs/pipelines.md` (our own OCR/seg pipelines), `scripts/l7014_mosaic.py`
(the series pipeline this correspondence is mostly about).

---

## 1. Who

| Person | Role | Where |
|---|---|---|
| **Bert Spaan** | Allmaps co-founder, lead developer | hello@bertspaan.nl |
| **Jules Schoonman** | Allmaps co-founder; digital curator, TU Delft Library | j.a.schoonman@tudelft.nl |
| **Martijn Meijers** | Assistant professor, GIS technology, TU Delft; author of MapEdge | b.m.meijers@tudelft.nl |

GitHub: `lqtue` is our account. Repo `allmaps/allmaps` (monorepo — `cli`,
`tileserver`, `data-export` are archived and folded in). PRs go against
**`develop`**, never `main`.

## 2. History

- **14 May 2026** — cold email to Bert. He replies same day, CCs Jules.
- **19 May 2026** — video call, Bert. He offers an introduction to Martijn for
  map-series work, and suggests Protomaps for the basemap (we took that
  advice — see `basemapStyle.ts`).
- **26 May 2026** — we reply: two topographic series fit sheet edges cleanly;
  a third (*Cochinchine Française, Plans des Arrondissements*, 13 sheets) has no
  straight seams and will need mask automation. Also flag wanting help with
  OCR + vectorising the Saigon sheets.
- **11 Jun 2026** — Bert introduces Martijn. Martijn replies the same day:
  *"The maps of the provinces look a lot like cadastral plans for The
  Netherlands, also quite difficult to automate the georeferencing for, I feel."*
  He offers Tue 23 June morning, or a 1:1 at another time.
- **Then nothing.** Whether the 23 June call happened is not recorded here —
  check before sending anything that assumes it did.
- **13 Sep 2026** — L7014 series published (452 sheets, one PMTiles archive).
  Drafts below written.

## 3. Verified findings

Everything here was checked against source or measured, not remembered. Dates
are when checked.

### Allmaps CLI already does most of a series (13 Sep 2026)

`allmaps script geotiff`, given an Annotation Page with N maps, emits per sheet a
`gdal_translate -of vrt` carrying the GCPs and a `gdalwarp -cutline <resourceMask>
-crop_to_cutline`, then finishes with `gdalbuildvrt merged.vrt`. The series step
exists. What is missing is turning that VRT into something a browser opens — and
the two commands are written down as a TODO in
`packages/io/src/output/geotiff.ts`, right after `generateGdalbuildvrtScript`.

### A Georeference Annotation cannot target a plain image (13 Sep 2026)

Spec: *"The value for `target` must either be a single and full IIIF resource, or
a single region within a IIIF resource."* Allmaps' own schema
(`packages/annotation/src/schemas/shared.ts`) spells the permitted list out:

```
ImageService1 · ImageService2 · ImageService3 · Canvas
```

**But `Canvas` is on that list**, and a IIIF Canvas may paint a plain image with
no Image API service. So on paper a sheet with no image server can still be
described. In practice it looks unsupported: every Allmaps app resolves the
target by calling `fetchImageInfo(id)` → `${id}/info.json` (`packages/stdlib/src/fetch.ts`,
used by viewer, editor and Here). That is the question in the email.

### navPlace is the free outward layer (13 Sep 2026)

The IIIF **navPlace** extension attaches a GeoJSON FeatureCollection to a
Collection, Manifest, Range or Canvas. Our `l7014-<date>.geojson` is already that
shape. **Allmaps' `iiif-parser` reads navPlace** — it appears in `classes/collection.ts`,
`classes/manifest.ts`, `classes/canvas.ts` and both presentation schemas.

The limit, in the spec's own words: the areas *"should be bounded discrete areas
… akin to extents"*, and the extension explicitly excludes *"Georeferencing and
map warping"*. So navPlace makes a series **findable**, not **viewable**.

### MapEdge — Meijers & Schoonman (13 Sep 2026)

*"Mapping the Edge: A Novel Approach to Georeferencing Historical Map Series"*,
ICA Bologna 2024; e-Perimetron 20(1):12–24, 2025.
Code: <https://github.com/bmmeijers/mapedge/> (Python, OpenCV + NumPy + Requests).

1. Digitize the sheet index so each sheet's four corners have known world coordinates.
2. Fetch a low-res overview over IIIF; 1D black-pixel histograms per axis; fuzzy-rank
   peak pairs to locate the frame roughly.
3. Fetch **high-res strips around those edges only**.
4. Per patch, find the frame line; RANSAC-fit one straight line per side; intersect
   the four lines.
5. The four intersections are both the GCPs **and** the mask corners.
6. Checks: point counts, opposite sides equal, diagonals equal, expected size from
   cm × dpi, residual spread to detect bent paper.

Tested on 65 / 184 / 308-sheet series, ~15 s per sheet. On the 184-sheet
Waterstaatskaart, 3 sheets had missing neat lines and went to manual; masks needed
hand-correction where content spilled outside the frame. Stated wish-list includes
integrating it into Allmaps Editor and contributing annotations back to the source
repositories.

**Overlap with us:** MapEdge's step 1 is our `corners` phase. We reconstructed a
535-sheet index and hit the trap that the printed graticule corners are Indian 1960,
not WGS 84 — taken at face value every sheet lands ~480 m northwest. They
reconstructed the Dutch indices by hand and published them on Observable.

**Fit for the arrondissement plans: poor.** MapEdge assumes a quadrangle grid with
known corner coordinates and four straight neat lines. That series has neither. Its
*mask* half may still apply if the printed frame is rectangular even where the
mapped content is not. Related: `geor-tudelft/iiifmap` (TU Delft × Allmaps MSc
project) whose phase 2 uses CNN feature matching plus a geocoder — the direction
for series with no index.

### Our own un-georeferenced corpus is one uniform series (13 Sep 2026)

`maps` holds 110 rows. **`allmaps_id` is not evidence of georeferencing** — it is
derived from the IIIF URL, so every row has one. The honest column is `georef_done`:
**48 done, 62 not**, and all 62 are the same series:

> **Indochine 1:25,000 — Tonkin & Thanh Hóa**, Cartomundi (Aix-Marseille Université /
> CNRS). All `draft`. Added 2026-05-14. Every sheet carries
> `extra_metadata.sheet_number` — 55 distinct values in 0..75, four numbers used twice
> (42, 13, 02, 14 — presumably second editions). `year_label` 1903–1927.

Uniform layout, one scale, printed frames, numbered sheets: this is MapEdge's case,
and a much better fit than the 13 arrondissement plans.

**The pixels are there — the addressing is level 0 only.** `full/1255,/0/default.jpg`
returns `{"error":"Source not found"}`, which reads like a missing sheet and is not.
Only exact tile-grid regions with a `w,h` size segment resolve:

```
.../2048,0,2048,2048/256,256/0/default.jpg   200
.../full/1255,/0/default.jpg                 404  "Source not found"
```

Scale factors 1–16 are present, 32 is not. `work/ocr/scripts/iiif_tiles.py` already has
`fetch_crop_level0`, so the pipeline can read these sheets unchanged.

**Each sheet carries its own sheet index.** Verified on Như Trác (5232×3862, Août 1903):
both corners print their coordinates in **grades, from the Paris meridian**.

| corner | printed | degrees |
|---|---|---|
| top-left | `115ᵍ,20` · `22ᵍ,875` | 106.017 E · 20.5875 N |
| bottom-right | `115ᵍ,40` · `22ᵍ,75` | 106.197 E · 20.475 N |

`grades × 0.9 = degrees from Paris`, `+ 2.3372 = Greenwich`. Two independent checks: the
ground box is 18.75 × 12.48 km, aspect **1.50**, and the neatline measures about
4496 × 3014 px, aspect **1.49**; and Như Trác (Lý Nhân, Hà Nam, ~20.55 N 106.05 E) falls
inside the box. So ~4.2 m/px, a 75 × 50 cm sheet scanned at ~150 dpi.

The frame is a **double neatline** — thick outer line, thin inner line, graticule band
between — which is the "pair of lines at the rim" variant MapEdge explicitly added
support for.

**The route, and it is short:**

1. Detect the inner neatline, fit four lines, intersect → four corners in pixels.
2. OCR four short strings, one just inside each corner → four corners in grades.
3. Convert: × 0.9, add the Paris offset.
4. Write the annotation; check all 62 in Allmaps Editor.

Steps 1 and 2 are both automatic. **MapEdge's step 1 is free here** — the step that
needed archival research for the Dutch series is printed on these sheets. That is the
finding worth sending to Bert and Martijn.

**The trap.** Grades, Paris meridian, and a 1903 datum that is almost certainly not
WGS 84. The first two are verified on one sheet; the datum is not. Same class as Indian
1960 in L7014 — take the printed numbers at face value and every sheet lands a few
hundred metres off with no error anywhere. Check one sheet against a known point before
trusting the batch.

### The corner detector, and what the sheets actually print (13 Sep 2026)

`scripts/tonkin_georef.py`. Two phases, `detect` (where the corners are, in the
scan's own pixels) and `read` (what the two labelled corners say), and between
them the annotation is arithmetic.

**MapEdge's shape, one substitution.** Low-resolution look, full-resolution strips
at the edges only, a trimmed line fit per side, intersect. What could not be
carried over is *which line*. `scripts/l7014_neatline.py` walks inward from the
blank margin until the paper stops being paper, which is right for L7014's single
neat line; run on Nhu Trac it gives residuals of 14-41 px and every edge rejected.
These sheets print, from the outside in: a thin line, a thick neatline, a thin
line, blank paper, the graticule band, **a wider run of blank paper**, then a pair
of thin lines at the rim of the map, then content. A walk in from the margin stops
at the band, 40 px and 170 m short.

**What works is to anchor on the thick line and never look for the rim twice.**
The thick neatline is the darkest thing on the strip by a factor of three, so per
patch it is `argmax` with no threshold and no rule; that fit settles where the side
runs *and* how far off square the scan was laid down. Only then is the strip
de-tilted onto that fit and averaged into one profile, in which the rim -- faint in
any single patch, and sitting against map content that is not faint -- is plain.
The distance from the thick line to it is a printed constant: measured on Nhu Trac
it is 83.2, 84.9, 83.5 and 83.9 px on the four sides.

Two things that cost an hour each and would cost it again:

- **The rough pass must average a narrow band, not half the sheet.** These scans
  are laid on the glass up to 0.8 degrees off square, which over half a sheet
  smears a 10 px line across 30 and lets a weaker, shorter feature win the argmax.
  A half-width average put Nhu Trac's top neatline 35 px from where it is.
- **One sheet, one rotation.** Each side's slope is fitted from its own two dozen
  patches and lands within a thousandth of the others -- but a thousandth over three
  thousand pixels is three, and four sides disagreeing by that much made opposite
  edges of the quad differ by 14 px where the projection says 4. Solve for the
  angle once from all four sides and let each side keep only its own offset.

**Which of the rim's two lines is unresolved, and it is worth 30 m.** They are 7 px
apart. The inner one puts the two axes' ground scales 0.29% apart, the outer 0.49%,
so the inner is taken -- but the floor of that test is about 0.3% (paper shrinkage
across the grain is that size, and the detection noise is not far below it), so it
separates them by less than it looks. The inner line is also what a *mask* wants,
being the boundary of the drawn map. Settling it properly means reading the
graticule ticks printed in the band -- `25'`, `30'`, `35'` in centesimal minutes,
0.05 grade apart, with the meridians drawn down into the sheet -- which would also
give interior control points and a much better warp than four corners. Not done.

### The 1903 datum is not the Indian 1960 trap (13 Sep 2026, measured on Nhu Trac)

The question the L7014 work taught us to ask: take the printed graticule at face
value and does the sheet land a few hundred metres from where it belongs? For
L7014 the answer was 480 m northwest. **For this series, on the one sheet
measured, it is about 60 m and the sign is the other way.**

Method, and its limits. The sheet was warped onto a web-Mercator grid from its
four detected corners, Esri World Imagery fetched for the same grid, and water
masked out of both -- blue ink on one side, a green-minus-red index on the other.
The Red River's channel is drawn on the 1903 sheet and visible on the imagery; for
each of 794 rows the modern channel's centre was compared with the 1903 one.

    median  +58 m east   (modern minus 1903)
    spread  +/-180 m, which is the river's own migration, not the georeference

So a several-hundred-metre systematic shift is ruled out **east-west**. Three
things this does not say. It is one sheet. The channel runs north-south, so it
carries no north-south information at all -- a full 2-D correlation put the peak
against the edge of its search window at z = 2.0, which is the aperture problem
and not a result. And the confluence at the sheet's south-east, the one point
feature available that constrains both axes, agrees to within about 100 m, which
is reassurance rather than measurement.

Two things that did **not** work and should not be retried as-is. OSM place nodes
are useless here: of twenty village names read off the sheet, four returned a
single hit, and Vinh Tru's `administrative` node is 1.1 km from the 1903 village
core -- the modern district town grew along a road. And correlating 1903 ink
density against modern red-roof pixels gives a smooth, peakless surface: the
masks' rectangular overlap dominates, and band-passing was not tried.

**Practical position.** Treat the printed grades as WGS 84, record that as an
assumption rather than a finding, and keep the correction a single number: if a
later check finds a shift it is one constant for all 62 sheets, not a per-sheet
problem.

### The series, placed (13 Sep 2026)

56 of 62 sheets written: `annotation_url`, `georef_done`, `bbox`. All still `draft`,
so they warp on /explore for a signed-in reviewer and reach no visitor.

**The check that earned its place is the grid, not the gate.** Every sheet was read
independently, and the series is a quadrangle lattice, so the readings have to agree
with each other whether or not anyone checks. They do:

    west edges   9 distinct, smallest step 0.200g, off the 0.20g lattice by 0.000
    north edges  15 distinct,                      off the 0.125g lattice by 0.000
    rim offset   84.2 px median, 58/58 sheets within 15% of it
    sheet numbers 0 rows out of order

Zero drift on both axes over 58 sheets read one at a time is the strongest evidence
we have that the whole thing is right, and it cost nothing -- the series checks itself.

**One sheet passed every per-sheet test and was still wrong.** `Ha Noi` (sheet 20,
1903) prints `115g,00'`-`115g,20'` and `22g,50'`-`22g,62'5"`. Its four corners agree
with each other, its ground scale agrees with its pixels to 0.78%, its rim sits at the
series offset -- and the map it draws is Hanoi, with the red urban core, the Fleuve
Rouge, Bat Trang and Thanh Tri. At 22g,56 that sheet would sit at 20.3 N, 75 km south
of the city it is named after. The longitude is right; the latitude is a clean **0.75g**
out, and the content it should be at is 23g,25'-23g,37'5". Nothing inside the sheet can
tell: what caught it is that it landed on Ninh Binh's cell in the lattice, and two
sheets cannot be the same quadrangle unless they are two editions of one sheet. Both
are held; a person decides which is the engraver's error and which is ours.

**Three sheets are a different edition.** Gia Binh (Oct 1911), Phuc Nhac (1906) and
Quat Lam are printed with a thin ruled frame and narrow margins instead of the heavy
neatline the detector anchors on -- Phuc Nhac also carries a numbered kilometre grid in
the margin. On those the strongest thing in an edge strip is map content: Phuc Nhac's
per-patch argmax scatters over 181-276 and the fit lands at a 17 px residual, Quat Lam
at 26. They print their corner figures in the same convention, so only the pixel
corners need supplying; `place` takes them from a person and runs everything downstream
unchanged. Thai Binh is held separately -- its four sides disagree about the rim by 14%,
which is the one way a sheet can be shifted bodily and still look square.

### Measured GDAL behaviour worth contributing (13 Sep 2026, GDAL 3.13.1)

- `TILE_FORMAT=JPEG` on a sparse mosaic paints every hole **pure black** — 21k–34k
  pure-black px per 256² tile in a two-sheet repro. Default or `AUTO`: zero.
- `ZOOM_LEVEL_STRATEGY=LOWER` stops at the paper's own resolution.
- `gdalbuildvrt -resolution highest` when a series mixes scan resolutions.
- `-wo INIT_DEST=255,255,255,0` so resampling does not draw a dark outline around
  every hole.
- Non-issue, but it looks alarming: `-of COG -co COMPRESS=JPEG -dstalpha` demotes
  alpha to a 3-band + internal mask; `gdalbuildvrt` carries the mask through and the
  PNG tiles come out with real alpha. No change needed to their `gdalwarp` line.

## 4. Draft — email (not sent)

**To** Bert · **Cc** Jules, Martijn
**Subject** Re: Integrating Allmaps into an AI + human workflow for the Vietnam Map Archive

> Hi Bert, Jules, Martijn,
>
> Apologies for the long gap — head down building. Something concrete to show, and
> one question I can't answer myself.
>
> **What we built.** Our first full map series is live: the US Army Map Service's
> L7014, Vietnam 1:50,000, from the Perry-Castañeda Library. 452 of 535 sheets, each
> clipped to its printed neatline, warped, and combined into a single PMTiles archive
> served straight off object storage — no tile server, no per-view cost. Alongside it,
> a 36 kB index: one outline per sheet with name, number, edition and date.
>
> **The question.** This series arrives *already georeferenced* — every GeoPDF carries
> its own control points and neatline. There's no IIIF image, no manifest, and nothing
> for the Editor to do. The georeference exists before Allmaps would normally enter,
> and I'm unsure where that leaves such material in your ecosystem.
>
> Two specific things:
>
> 1. Our sheet index is already the exact shape `navPlace` wants, and your IIIF parser
>    reads `navPlace` throughout. Publishing the series as a IIIF Collection with
>    `navPlace` per sheet looks free, and would make it discoverable — but `navPlace`
>    is explicitly not georeferencing. Right layer for a series like this, or is there
>    a better pattern?
> 2. The Georeference Extension allows an annotation to target a Canvas, and a Canvas
>    may paint a plain image with no Image API service. Does Allmaps support that in
>    practice? Every app I looked at fetches `<resource id>/info.json`, which suggests
>    not. If it did, a series like ours could live in IIIF without anyone hosting an
>    image server for 452 sheets.
>
> **Martijn** — I finally read *Mapping the Edge*, and it turns out we built your step
> one independently: reconstructing the sheet index for a 535-sheet series, with the
> trap that the printed graticule corners are on Indian 1960 rather than WGS 84 — take
> them at face value and every sheet lands 480 m northwest. Happy to share that if it's
> useful. Two questions from the paper: can MapEdge's mask half be used on its own,
> when the printed frame is rectangular but the mapped content inside is not? And for a
> series with no index and no grid — the 13 arrondissement plans I mentioned in May —
> is feature matching where you'd go now, or still research rather than practice?
>
> Another call? I'm flexible, and glad to demo the series and the OCR pipeline end to end.
>
> Best,
> Tuệ

## 5. Draft — GitHub discussion (not posted)

**Repo** `allmaps/allmaps` · **Category** *Ideas for Apps: Editor, Viewer, …*
(`DIC_kwDOHeVsJ84CeJ0J`; repo id `R_kgDOHeVsJw`)
**Title** `Map series → PMTiles: adding a tiling tail to allmaps script geotiff`

Body: the PR proposal — what we ran (L7014, 452 sheets, one archive), what the CLI
already does (`gdalbuildvrt merged.vrt`), the TODO in `packages/io/src/output/geotiff.ts`,
the proposed `--tiles pmtiles|xyz` option, the four measured GDAL findings in §3, and
the closing question about whether a *series* is something Allmaps wants to model.
Full text was drafted 13 Sep 2026 — regenerate from §3 rather than keeping a second
copy here.

## 6. Open questions and next actions

- [ ] Confirm whether the 23 June 2026 call happened before sending anything.
- [ ] Send the email (§4).
- [ ] Post the discussion (§5).
- [ ] If they welcome it: PR against `develop` adding `--tiles` to `script geotiff`.
- [ ] Decide whether to publish L7014 as a IIIF Collection with `navPlace`
      (free; makes the series discoverable by their tools).
- [ ] Offer our L7014 sheet-index work to Martijn as a MapEdge step-1 case study.
- [x] Verify the 1903 datum on one sheet — done, §3: about 60 m east-west, no
      Indian-1960-class trap. North-south still unmeasured.
- [x] Build the corner detector + corner-text OCR — `scripts/tonkin_georef.py`.
- [ ] Read the band's `25'` / `30'` / `35'` graticule ticks: settles which of the
      rim's two lines is the quadrangle, and gives interior control points.
- [x] Emit Georeference Annotations and write them back — 56 of 62 done, all still
      `draft`. Publishing (`status='public'`) is deliberately not done: it waits on
      the eyeball pass.
- [ ] Decide `Ha Noi` vs `Ninh Binh`: one of them is on the other's quadrangle.
- [ ] Hand-place Gia Binh, Phuc Nhac, Quat Lam (thin-frame edition) via `place`,
      and Thai Binh, whose rim offsets spread 14%.
- [ ] Constrain the datum north-south: needs an east-west feature, which the Red
      River is not.

## 7. Log

- **2026-09-13** — File created. Researched Allmaps monorepo, the Georeference
  Extension, navPlace and MapEdge; measured the GDAL behaviours in §3; drafted the
  email and the discussion post. Nothing sent.
- **2026-09-13** — Audited our own corpus: 62 of 110 maps are un-georeferenced and all
  belong to one series (Indochine 1:25,000, Cartomundi). First read of the IIIF endpoint
  was wrong: the pixels are mirrored, the worker is level 0, and only exact tile-grid
  addresses resolve. Decoded the printed corner coordinates on Như Trác — grades from the
  Paris meridian — and cross-checked them two ways. Section 3.
- **2026-09-13** — Built `scripts/tonkin_georef.py`: corner detection and corner-text
  OCR for the Indochine 1:25,000 series, end to end on Nhu Trac. Measured the datum
  against satellite imagery rather than assuming it. Section 3.
- **2026-09-13** — Ran the series: 56 of 62 sheets georeferenced and written as drafts.
  The lattice check came back exact on both axes over 58 sheets. It also caught the one
  sheet that passed everything else and was still 75 km out. Section 3.
