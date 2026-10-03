# Two map series georeferenced without an Editor

**A technical note from the Vietnam Map Archive**
Le-Quang Tuệ · 18 September 2026 · <https://maparchive.vn>

Prepared for Bert Spaan, Jules Schoonman and Martijn Meijers. Every number below was
measured, not remembered, and each carries the date it was measured. Where something is
an assumption rather than a finding, it says so.

---

## Summary

Two series, 514 sheets between them, georeferenced by pipeline rather than by hand in an
Editor. Neither followed the path Allmaps normally expects, and the reasons differ:

| | **L7014** | **Indochine 1:25,000** |
|---|---|---|
| What | US Army Map Service, Vietnam 1:50,000 | Tonkin & Thanh Hóa, Service géographique de l'Indochine |
| Held by | Perry-Castañeda Library, UT Austin | Cartomundi (Aix-Marseille Université / CNRS) |
| Sheets | 452 of 535 published | 56 of 62 georeferenced |
| Dates | 1960s–70s | 1903–1927 |
| Why no Editor | Arrives georeferenced — every GeoPDF carries its own GCPs and neatline | Each sheet prints its own corner coordinates |
| Output | One PMTiles archive + a 36 kB sheet index | Georeference Annotations, all still `draft` |

The common thread is that for a *series*, the expensive part of georeferencing is often
already printed on the paper or shipped in the file. What is missing is not control
points. It is a way to say "this is a series" in the ecosystem at all.

---

## 1. L7014 — a series that arrives finished

452 of 535 sheets, each clipped to its printed neatline, warped, and combined into a
single PMTiles archive served straight off object storage. No tile server, no per-view
cost. Alongside it a 36 kB index: one outline per sheet with name, number, edition, date.

### The trap: Indian 1960

The printed graticule corners are on **Indian 1960**, not WGS 84. Take them at face value
and every sheet lands about **480 m northwest** of where it belongs — with no error
raised anywhere in the chain. The sheets look right individually. They are wrong
together, and consistently, which is the hardest kind of wrong to notice.

This is the failure mode worth naming in public, because it is silent by construction:
GDAL will happily accept the numbers, the warp will succeed, the tiles will render, and
the only symptom is that the map is in the wrong place by an amount small enough to look
like scan distortion.

We now probe for it rather than assume either way. See §2 for what happened when the same
question was asked of a different series and got a different answer.

### What the Allmaps CLI already does, and where it stops

`allmaps script geotiff`, given an Annotation Page with N maps, emits per sheet a
`gdal_translate -of vrt` carrying the GCPs and a `gdalwarp -cutline <resourceMask>
-crop_to_cutline`, then finishes with `gdalbuildvrt merged.vrt`.

**The series step already exists.** What is missing is turning that VRT into something a
browser opens — and both commands needed for that are already written down as a TODO in
`packages/io/src/output/geotiff.ts`, immediately after `generateGdalbuildvrtScript`.

A `--tiles pmtiles|xyz` option on that command is, as far as we can tell from having just
built it by hand, a short addition. We are glad to write it as a PR against `develop` if
it is wanted.

---

## 2. Indochine 1:25,000 — a series that indexes itself

62 sheets, uniform layout, one scale, printed frames, numbered. `year_label` 1903–1927.
This is MapEdge's case almost exactly — with one difference that matters.

### MapEdge's step 1 is free here

*Mapping the Edge* (Meijers & Schoonman, ICA Bologna 2024; e-Perimetron 20(1):12–24, 2025)
begins by digitising the sheet index so each sheet's four corners have known world
coordinates. For the Dutch series that took archival research and was published by hand
on Observable.

**These sheets print their own corners.** Verified on Như Trác (5232×3862 px, Août 1903):
both labelled corners carry coordinates in **grades, measured from the Paris meridian**.

| Corner | Printed | Degrees (Greenwich) |
|---|---|---|
| Top-left | `115ᵍ,20` · `22ᵍ,875` | 106.017 E · 20.5875 N |
| Bottom-right | `115ᵍ,40` · `22ᵍ,75` | 106.197 E · 20.475 N |

The conversion is `grades × 0.9 = degrees from Paris`, then `+ 2.3372` for Greenwich.

Two independent checks: the resulting ground box is 18.75 × 12.48 km, aspect **1.50**,
and the neatline measures about 4496 × 3014 px, aspect **1.49**; and Như Trác itself
(Lý Nhân, Hà Nam, ~20.55 N 106.05 E) falls inside the box. That gives ~4.2 m/px — a
75 × 50 cm sheet scanned at about 150 dpi.

So the whole route is four steps, and the first two are automatic:

1. Detect the inner neatline, fit four lines, intersect → four corners in pixels.
2. OCR four short strings, one just inside each corner → four corners in grades.
3. Convert: × 0.9, add the Paris offset.
4. Write the annotation.

### The detector, and the one substitution MapEdge needs here

`scripts/tonkin_georef.py` follows MapEdge's shape — low-resolution look, full-resolution
strips at the edges only, a trimmed line fit per side, intersect — with one change.

**The change is *which* line.** These sheets print, from the outside in: a thin line, a
thick neatline, a thin line, blank paper, the graticule band, a wider run of blank paper,
then a pair of thin lines at the rim of the map, then content. Our L7014 detector walks
inward from the blank margin until the paper stops being paper, which is right for a
single neat line. Run on Như Trác it stops at the graticule band — 40 px and 170 m short
— with residuals of 14–41 px and every edge rejected.

What works is to **anchor on the thick line and never look for the rim twice**. The thick
neatline is the darkest thing on the strip by a factor of three, so per patch it is
`argmax` with no threshold and no rule. That fit settles both where the side runs and how
far off square the scan was laid down. Only then is the strip de-tilted onto that fit and
averaged into one profile, in which the rim — faint in any single patch, and sitting
against map content that is not faint — is plain. The distance from thick line to rim is
a printed constant: on Như Trác, 83.2, 84.9, 83.5 and 83.9 px on the four sides.

Two things cost an hour each and would cost it again:

- **The rough pass must average a narrow band, not half the sheet.** These scans are laid
  on the glass up to 0.8° off square, which over half a sheet smears a 10 px line across
  30 and lets a weaker, shorter feature win the `argmax`. A half-width average put Như
  Trác's top neatline 35 px from where it is.
- **One sheet, one rotation.** Each side's slope is fitted from its own two dozen patches
  and lands within a thousandth of the others — but a thousandth over three thousand
  pixels is three, and four sides disagreeing by that much made opposite edges of the
  quad differ by 14 px where the projection says 4. Solve the angle once from all four
  sides; let each side keep only its own offset.

### Unresolved, and worth about 30 m

The rim is a *pair* of thin lines, 7 px apart, and we do not know which is the
quadrangle boundary. The inner one puts the two axes' ground scales 0.29% apart, the
outer 0.49%, so we take the inner — but the floor of that test is about 0.3% (paper
shrinkage across the grain is that size, and detection noise is not far below it), so it
separates them by less than it appears to. The inner line is also what a *mask* wants,
being the boundary of the drawn map.

Settling it properly means reading the graticule ticks printed in the band — `25'`,
`30'`, `35'` in centesimal minutes, 0.05 grade apart, with the meridians drawn down into
the sheet. That would also yield interior control points and a considerably better warp
than four corners. Not done.

### The datum question, asked again and answered differently

L7014 taught us to ask: take the printed graticule at face value, and does the sheet land
a few hundred metres from where it belongs? For L7014, 480 m northwest. **For this
series, on the one sheet measured, about 60 m — and the sign is the other way.**

Method: the sheet was warped onto a web-Mercator grid from its four detected corners,
Esri World Imagery fetched for the same grid, water masked out of both (blue ink on one
side, a green-minus-red index on the other). The Red River's channel is drawn on the 1903
sheet and visible in the imagery; for each of 794 rows the modern channel centre was
compared with the 1903 one.

```
median  +58 m east   (modern minus 1903)
spread  ±180 m, which is the river's own migration, not the georeference
```

**Three things this does not say.** It is one sheet. The channel runs north–south, so it
carries no north–south information at all — a full 2-D correlation put the peak against
the edge of its search window at z = 2.0, which is the aperture problem, not a result.
And the confluence at the sheet's south-east, the one point feature constraining both
axes, agrees to within about 100 m, which is reassurance rather than measurement.

Two approaches that did **not** work and should not be retried as-is. OSM place nodes are
useless here: of twenty village names read off the sheet, four returned a single hit, and
Vĩnh Trụ's `administrative` node is 1.1 km from the 1903 village core — the modern
district town grew along a road. And correlating 1903 ink density against modern red-roof
pixels gives a smooth, peakless surface; the masks' rectangular overlap dominates, and
band-passing was not tried.

**Our practical position:** treat the printed grades as WGS 84, record that as an
assumption rather than a finding, and keep any correction a single number. If a later
check finds a shift, it is one constant for all 62 sheets, not a per-sheet problem.

### The check that earned its place is the grid

Every sheet was read independently, and the series is a quadrangle lattice, so the
readings have to agree with each other whether or not anyone checks them. They do:

```
west edges    9 distinct, smallest step 0.200ᵍ, off the 0.20ᵍ lattice by 0.000
north edges  15 distinct,                        off the 0.125ᵍ lattice by 0.000
rim offset   84.2 px median, 58/58 sheets within 15% of it
sheet numbers 0 rows out of order
```

Zero drift on both axes across 58 sheets read one at a time is the strongest evidence we
have that the whole thing is right — and it cost nothing. **The series checks itself.**
We think this generalises: any quadrangle series is its own test set, and a lattice
residual is a cheaper and stronger signal than a per-sheet gate.

### One sheet passed every per-sheet test and was still wrong

`Ha Noi` (sheet 20, 1903) prints `115ᵍ,00'`–`115ᵍ,20'` and `22ᵍ,50'`–`22ᵍ,62'5"`. Its
four corners agree with each other. Its ground scale agrees with its pixels to 0.78%. Its
rim sits at the series offset. And the map it draws is unmistakably Hanoi — the red urban
core, the Fleuve Rouge, Bát Tràng, Thanh Trì.

At 22ᵍ,56 that sheet would sit at 20.3 N, **75 km south of the city it is named after**.
The longitude is right; the latitude is a clean 0.75ᵍ out, and the content it shows
belongs at 23ᵍ,25'–23ᵍ,37'5".

Nothing inside the sheet can catch this. What caught it is that it landed on Ninh Bình's
cell in the lattice — and two sheets cannot occupy the same quadrangle unless they are
two editions of one sheet. We hold both. A person now decides which is the engraver's
error and which is ours.

### Three sheets are a different edition

Gia Bình (Oct 1911), Phúc Nhạc (1906) and Quất Lâm are printed with a thin ruled frame
and narrow margins instead of the heavy neatline the detector anchors on — Phúc Nhạc also
carries a numbered kilometre grid in the margin. On those, the strongest thing in an edge
strip is map content: Phúc Nhạc's per-patch `argmax` scatters over 181–276 and the fit
lands at a 17 px residual, Quất Lâm at 26. They print their corner figures in the same
convention, so only the pixel corners need supplying by hand; everything downstream runs
unchanged. Thái Bình is held separately — its four sides disagree about the rim by 14%,
which is the one way a sheet can be shifted bodily and still look square.

### A practical note on the IIIF endpoint

Worth recording because the first read of it was wrong and the error message is
misleading. On this endpoint only exact tile-grid regions with a `w,h` size segment
resolve:

```
.../2048,0,2048,2048/256,256/0/default.jpg   200
.../full/1255,/0/default.jpg                 404  {"error":"Source not found"}
```

Scale factors 1–16 are present; 32 is not. A `404 Source not found` here reads like a
missing sheet and is not — it is a level-0-only server declining a size it cannot
compute.

---

## 3. Where this leaves us in the Allmaps ecosystem

Two questions we cannot answer from the outside.

**1. Is `navPlace` the right layer for a series like this?** Our L7014 sheet index is
already the exact shape `navPlace` wants, and the Allmaps `iiif-parser` reads `navPlace`
throughout — it appears in `classes/collection.ts`, `classes/manifest.ts`,
`classes/canvas.ts` and both presentation schemas. Publishing the series as a IIIF
Collection with `navPlace` per sheet appears to be free, and would make it discoverable
by your tools. But `navPlace` is explicitly *not* georeferencing, and the spec asks that
the areas be "bounded discrete areas". Is this the right use, or is there a better
pattern for a series that is already georeferenced?

**2. Can a Georeference Annotation target a plain image in practice?** The spec says the
target must be a single full IIIF resource or a region within one, and the Allmaps schema
(`packages/annotation/src/schemas/shared.ts`) spells out the permitted list:

```
ImageService1 · ImageService2 · ImageService3 · Canvas
```

`Canvas` is on that list, and a IIIF Canvas may paint a plain image with no Image API
service. So on paper, a sheet with no image server can still be described. In practice it
looks unsupported: every Allmaps app resolves the target by calling `fetchImageInfo(id)`
→ `${id}/info.json` (`packages/stdlib/src/fetch.ts`, used by viewer, editor and Here).

If it did work, a series like L7014 could live in IIIF without anyone standing up an
image server for 452 sheets. That is the difference between a series being publishable by
a small archive and not.

---

## 4. Measured GDAL behaviour worth upstreaming

GDAL 3.13.1, measured 13 September 2026. Offered because the CLI's generated commands sit
close to several of these.

- **`TILE_FORMAT=JPEG` on a sparse mosaic paints every hole pure black** — 21k–34k
  pure-black pixels per 256² tile in a two-sheet reproduction. Default or `AUTO`: zero.
  This one is worth a line in the generated script.
- **`ZOOM_LEVEL_STRATEGY=LOWER`** stops at the paper's own resolution instead of
  inventing a level above it.
- **`gdalbuildvrt -resolution highest`** when a series mixes scan resolutions, which most
  archival series do.
- **`-wo INIT_DEST=255,255,255,0`** so resampling does not draw a dark outline around
  every hole in the mosaic.
- **Not a problem, but it looks alarming:** `-of COG -co COMPRESS=JPEG -dstalpha` demotes
  alpha to 3 bands plus an internal mask. `gdalbuildvrt` carries the mask through and the
  PNG tiles come out with real alpha. No change needed to the existing `gdalwarp` line —
  recorded so the next person does not spend an afternoon on it as we did.

---

## 5. What is not established

Stated plainly, so nothing above is read as firmer than it is.

1. **The 1903 datum is measured east–west only, on one sheet.** North–south is
   unconstrained; the Red River cannot constrain it. Treated as an assumption.
2. **Which of the rim's two lines is the quadrangle boundary is unresolved** (~30 m,
   §2). The graticule ticks would settle it and have not been read.
3. **All 56 annotations are `draft`.** They warp for a signed-in reviewer and reach no
   visitor. Publication waits on a human eyeball pass, deliberately.
4. **`Ha Noi` vs `Ninh Binh` is undecided.** One of them is on the other's quadrangle and
   a person has to say which.
5. **Four sheets need hand-placed corners** — Gia Bình, Phúc Nhạc, Quất Lâm (thin-frame
   edition) and Thái Bình.
6. **83 L7014 sheets are not published**, of 535.

---

## Colophon

Vietnam Map Archive is an open archive of georeferenced historical maps of Saigon and
Vietnam, built on Allmaps and OpenLayers. Derived data — annotations, extractions,
footprints, gazetteer — is CC-BY-4.0. Scans remain under their holding institutions'
terms and are referenced by IIIF URL rather than redistributed.

Code and scripts referenced above: `scripts/tonkin_georef.py`, `scripts/l7014_mosaic.py`,
`scripts/l7014_neatline.py`.

Contact: lequangtuevn@gmail.com
