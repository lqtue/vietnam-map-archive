# AMS Series L7014

For whoever touches the L7014 pipeline. Kind: record — the mosaic was retired 2026-10-03; its
build and datum traps are kept here.
Moved here from `docs/guides/pipelines.md` on 2026-10-17, word for word.

## AMS Series L7014 mosaic (`scripts/l7014/l7014_mosaic.py`)

The US Army Map Service's 1:50,000 coverage of Vietnam, as **one raster PMTiles
archive** rather than 509 catalogue rows. It is served exactly the way the
street basemap is — an object in `vma-tiles` behind `tiles.maparchive.vn`, read
by byte range — but it is a **layer, not a basemap**: it joins the overlay stack
as the raster `part` of one `SeriesRef`, sharing its opacity, eye and position
with the nine warped city sheets that fill its Saigon-shaped hole, and is
switched on from the **Series** row of the map controls. A basemap was the first attempt and
was wrong in two ways — a sheet series is one thing among the archive's others
and wants an opacity slider, and underneath it the ~99 missing sheets showed the
*basemap*, which in dark mode is near-black, so every gap read as a hole punched
in the page.

```bash
python3 scripts/l7014/l7014_mosaic.py index           # scrape the PCL index
python3 scripts/l7014/l7014_mosaic.py fetch --jobs 4  # download the GeoPDFs (~4 GB)
python3 scripts/l7014/l7014_mosaic.py warp            # clip to neatline, reproject
python3 scripts/l7014/l7014_mosaic.py tile            # mosaic -> MBTiles -> PMTiles
python3 scripts/l7014/l7014_mosaic.py upload          # rclone to r2:vma-tiles/overlay/
python3 scripts/l7014/l7014_mosaic.py manifest         # one outline per sheet in the archive
python3 scripts/l7014/l7014_mosaic.py fit             # where every warped sheet actually landed
python3 scripts/l7014/l7014_mosaic.py check           # prove the datum check can fail
```

> **Deleted from R2 2026-10-29, never rebuilt** (not served since 2026-10-03; the exact bytes are
> kept offline in `../vma-snapshots/261029-l7014-overlay/`). What follows is its state when served.
> **The archive `l7014-20260913` is wrong.** 285 of
> its 437 GeoPDF sheets shipped without the Indian 1960 datum shift and sit
> ~470 m northwest of where they belong; `fit` reports 341 of 452 sheets more
> than 150 m off their cell. The cause and the fix are trap 1 below. The fix is
> committed and `fit` now fails on the shipped archive, but nothing has been
> re-warped or re-uploaded — do that before trusting a measurement taken off
> these tiles. The 24 hand-georeferenced sheets are **not** affected: their
> control points fit to 2.3–19.0 m rms (`residuals`), and the ~460 m step a
> reader sees where one of them meets the mosaic is the mosaic edge moving.

Every phase is resumable — it skips what it already produced — so a failed run
is re-run, not restarted. Needs GDAL with the PDF driver, the `pmtiles` CLI,
and rclone's `r2:` remote. Wall clock for the full series is roughly two hours,
most of it the download.

**Why there is nothing to georeference by hand.** Each PCL GeoPDF carries eight
NGA control points in pixel space, its printed neatline as a polygon, and an XMP
block with the sheet's title, edition, date and graticule corners. The pipeline
clips each sheet to its own neatline (which is what removes the collar, so
sheets butt together instead of overlapping their margins), warps it to Web
Mercator, and tiles the lot. Where two sheets were warped the same way their
edges agree to **2.5–14 m** — inside the series' own ±25 m drafting accuracy,
and grid lines and streams run unbroken across a join. What *is* visible at such
a seam is tone: the scans differ in brightness sheet to sheet.

That "warped the same way" is load-bearing, and it is how the datum fault above
was found. Over all **750** adjacent seams in `l7014-20260913` the median is
19 m, but **56 are over 300 m** — those are the joins where an unshifted sheet
meets a shifted one — and **every one of the 33 seams where a hand-georeferenced
sheet meets the mosaic measures 447–504 m**. A seam is the cheapest measurement
here because it needs no outside data at all, only two sheets that claim to
share an edge; four sheets is not enough of them to notice a fault that splits
the corpus 285/151.

**Five things that will silently produce a plausible wrong result.** All five
are handled; all five are worth knowing before editing this script. Every one of
them was found by looking at the output, not by reading the code.

1. **The datum, twice over, and the second one shipped.** GDAL cannot map every
   NGA LGIDict code: on `IND-I` and `INF-A` it emits a warning, falls back to
   WGS84, and *the warp still succeeds* — putting the sheet ~450 m off with no
   error anywhere. So the projection is rebuilt from what GDAL did parse (its
   central meridian names the UTM zone exactly) or, failing that, the sheet's
   XMP.

   That is only half of it, and the other half reached production. **A sheet
   that says `Indian_1960` plainly gets no shift either**, because PROJ's
   `EPSG:4131` → `EPSG:4326` pipeline has an area of use covering part of the
   country and, for a point outside it, GDAL returns the input **unchanged**
   rather than failing. Probed: `106.00,16.00` moves 470 m, `109.25,13.25`
   moves 0. `phase_corners` already spelled the Helmert out by hand for exactly
   this reason; `warp` did not, and 285 of 336 sheets that declare Indian 1960
   in their own PDF shipped with the shift silently skipped. The shift is now
   `INDIAN_1960_PROJ4` — Everest 1830 (1937 Adjustment) plus
   `+towgs84=198,881,317` — and is never looked up.

   **The check that was supposed to catch this could not.** `graticule_error`
   reads the sheet's control points into the sheet's *own* datum and compares
   them with the graticule the sheet itself prints. Both sides move together
   when the datum is wrong, so it returns ~0 for precisely the fault it looks
   like it is guarding — A Luoi's `graticule_err` is `2e-12` — and it is blind
   by construction, not by accident. What replaces it is an **outside opinion**:
   `pick_crs` warps the neatline under both readings, the sheet's declaration
   and Indian 1960 with the Helmert, and keeps whichever lands on the sheet's
   15′ lattice cell. That is a measurement between two candidates ~470 m apart
   against a third party good to ~15 m, so the choice is never close; a sheet
   that misses on **both** readings is refused rather than warped in at the
   smaller miss. Dry-run over all 437: median miss 430 m → **0 m**, p95 9 m,
   max 115 m, none over 150. `fit` is the same measurement over a built archive
   and exits 1, so it belongs between `tile` and `upload`. `check` still runs a
   real sheet through WGS84 on purpose and asserts the graticule test rejects
   it — that test is fine at what it does see, which is a wrong zone.
2. **The UTM zone must come from the sheet's centre, never an edge.** Many
   sheets end at longitude 108.000, exactly the zone 48/49 boundary; taking the
   east edge puts them a zone over. That is a clean 6.00001° error, and it looks
   like a datum fault rather than the off-by-one it is.
3. **The COG driver cannot carry a fourth band through JPEG compression.** Ask
   for `-dstalpha` with `-of COG -co COMPRESS=JPEG` and GDAL quietly demotes the
   alpha to an internal mask; `gdalbuildvrt` then drops the mask, and the mosaic
   loses its transparency without a word — every hole becomes an opaque
   rectangle sitting on the basemap. Plain GTiff + DEFLATE for the
   intermediates, which cost ~41 MB a sheet (~21 GB for the series, deletable
   once tiled).
4. **The pixels nothing ever shows still get averaged.** `-dstalpha` leaves the
   area outside the neatline black at alpha 0. Invisible — until every
   resampling step blends it into the visible edge and draws a dark outline
   around each hole. `-wo INIT_DEST=255,255,255,0` puts white there instead.
5. **`TILE_FORMAT=JPEG` has no alpha**, so the holes would paint black over the
   basemap; and **`ZOOM_LEVEL_STRATEGY=UPPER` invents a zoom level** past the
   scans' own resolution, quadrupling the archive for detail that is not in the
   paper. WEBP and `LOWER`.

Also: `gdalbuildvrt` defaults to **average** resolution, which would quietly
downsample the 300 dpi sheets to match the 150 dpi ones. `-resolution highest`.

**The one flaw left, and its price.** WEBP discards the RGB under fully
transparent pixels, so the white from trap 4 is gone by the time `gdaladdo`
averages a half-covered edge, and a thin dark line survives around each hole.
`--tile-format PNG` removes it completely and costs **nine times the bytes** —
35 GB against 3 GB, measured on the same four sheets — on every tile a reader
pans across. Hence a flag rather than a different default.

**On the browser side**, `PMTilesRasterSource` returns an empty `Uint8Array` for
a tile the archive does not hold, and a sparse archive is mostly misses. The
canvas renderer throws on array data outright; the WebGL one paints it black,
hiding the street basemap underneath. `SparsePMTilesSource` in `basemapStyle.ts`
wraps the loader and substitutes a transparent canvas — **at the archive's own
tile size**, because a `DataTileSource` assumes every tile is the size its grid
declares, and a 512 px blank where the grid says 256 renders the neighbouring
tiles as black bands.

**The hole over Saigon.** 25 of the 534 sheets are published as plain JPGs with
no georeference at all, and they are the ones that matter most here — Thành phố
Hồ Chí Minh (6330-4), Biên Hòa, Nhơn Trạch, Cần Giuộc, Cần Giờ, Gò Công, Huế,
Đà Nẵng, Hải Phòng. They are recorded in `work/l7014/sheets.json` with
`kind: "jpg"` so what the mosaic is missing stays legible. Their geographic
corners are *not* unknown — the series is a regular 15′ lattice, so any sheet
number's cell is computable exactly from its neighbours' XMP. What is missing is
the four neatline corners in each JPG's pixel space, which is four clicks a
sheet, twenty-five times.

PCL sits behind a bot check that challenges anything claiming to be a browser
and waves curl's own user agent through, which is why both fetches shell out to
curl instead of dressing `urllib` up as Chrome.

The predecessor of this script was `scripts/l7014_pipeline.py` (deleted in
`27f8e79f`, with `pipeline_sheets` dropped in migration 036). It scraped corner
coordinates from Texas Tech's Virtual Vietnam Archive, guessed every sheet's
neatline from one hand-calibrated set of fractions, and uploaded each sheet to
the Internet Archive for a IIIF service. None of that is needed once the PDF
carries its own control points.
