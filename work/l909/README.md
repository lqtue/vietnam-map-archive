# L909 catalogue-backed city index

The source snapshot records PCL’s explicitly labelled L909 city-map items from
https://maps.lib.utexas.edu/maps/vietnam.html, checked 2026-10-06. It contains 21
items for 19 distinct cities; the Nha Trang and Qui Nhon versos belong to their
existing city cells. PCL’s two Saigon sheets are L9012 and are excluded.

The existing served Sài Gòn L909 scan adds a twentieth known city. The additive
import `scripts/oneoff/import_l909_series_cells.mjs` created 20 `series_cells`
and 21 PCL `cell_printings` records in production on 2026-10-06. Read-back:
3 publicly served cities, 17 other cities with a known external source. A
second apply added zero records. No maps, rights, printing identities or
geographic extents were changed or inferred. Source editions and dates remain
catalogue assertions, including null years where the catalogue says `196-`.
Hà Nội and Huế source edition labels differ from existing map metadata; review
of the collars remains open.

This is a partial catalogue inventory, not the complete historical survey.
`src/lib/core/seriesIndexScope.ts` carries that qualification into the catalog,
coverage page and explore list. Retain it until a complete source-backed
historical inventory has been established. `l909-index` remains on ROADMAP for
that work and for catalogue cell extents.

## Ingesting the indexed scans

`node --env-file=.env scripts/oneoff/ingest_l909_pcl.mjs` prints the missing-image
plan. `--download` stages and decodes the source JPEGs locally; `--apply`
mirrors them and inserts draft map/source records. The source URL and a local
journal make retries reuse the same map UUID. Existing maps are excluded from
writes. Native JPEG bytes are retained under the IIIF service's native-width
full-image key, alongside its tile pyramid, thumbnails and 2048px overview.
Read-back checks the native JPEG SHA-256, service dimensions, overview,
thumbnail and a pyramid tile before adding each map and source link.

The two verso indexes are separate scan workspaces with the same city sheet
identifier and `scan_side = verso`; they do not add city cells or infer a
reviewed printing identity. Catalogue editions/dates remain assertions until
reviewed. Ingest leaves maps as drafts, with no georeference or OCR job queued.

## Ingest result — 6 October 2026

All 19 previously missing indexed scans were ingested as drafts: 17 city-map
rectos and the Nha Trang / Qui Nhon versos. The series now has 22 scan
workspaces across its 20 indexed cities: 3 existing public maps and 19 new
drafts. All new images have a source-item link, dimensions, native JPEG
SHA-256 and an opaque asset-version UUID. Native image checksums, 800px
thumbnails, 2048px overviews and representative pyramid tiles passed for
every image. The original three map records are unchanged. A repeat dry run
found zero remaining indexed source images.

The local source images total 183,239,795 bytes. The checked record/asset
manifest is `work/l909/ingested-scans.json`. Preparation and georeferencing
remain to be done before publishing the new drafts.

## USGS GeoPDFs — the same printings, larger and georeferenced

USGS sells NGA's digital edition of 18 of these cities as GeoPDFs
(`https://store.usgs.gov/assets/MOD/StoreFiles/NGA/L909X<CODE>_geo.pdf`). Each
PDF's edition (its Keywords field and XMP) matches the PCL scan already held, so
they are the same printings, recto only, at 300 dpi throughout — larger than
every PCL scan (Nha Trang 6518×8776 against 3820×5235) — and each carries eight
NGA control points in its UTM grid and its printed neatline.

`scripts/oneoff/ingest_l909_usgs.mjs` (dry run by default; `--download` fetches
the PDFs and runs the datum check; `--apply` writes) does three things:

1. **`cell_printings`, institution `USGS`, for all 18** — `source_ref`
   `L909X<CODE>_geo.pdf`, upserted on `(institution, source_ref)`. Title,
   edition and year are the PDF's own metadata (XMP `title`, Keywords,
   `pri_date`'s year); nothing is inferred.
2. **For the 16 PCL draft rectos, the GeoPDF raster becomes the primary image.**
   Rendered at the embedded 300 ppi (GDAL's default reads two PDFs at 150 dpi),
   tiled to the versioned service `iiif/<map>/v2` — the PCL tiles at the
   unversioned prefix are untouched — and linked to the USGS item by
   `map_images.source_item_id`. The PCL image row stays, demoted. Maps stay
   draft. Read-back: native JPEG SHA-256, `info.json` id and size, 800/2048
   overviews, two pyramid tiles.
3. **Georeference from the PDF**, written the way the L7014 PDF sheets were
   (`l7014_annotate_pdf.py`): the control points' affine sampled 5×5 across the
   neatline, second-order polynomial, neatline as mask; history file +
   `georef_versions` + live `annotations/<map>.json`, then `annotation_url`,
   `is_georeferenced`, `bbox`.

The geometry is `scripts/oneoff/l909_usgs_georef.py`. **The datum is the L7014
trap again** (`docs/pipelines.md` §AMS Series L7014, trap 1): GDAL reads these
PDFs either as `Indian_1960` — an EPSG lookup that shifts some sheets and leaves
others exactly where they were — or, for `IND-I` (Nha Trang, Huế), as `unknown`
on the WGS84 ellipsoid. Neither is used. The CRS is built: UTM zone from the
sheet centre (checked against the PDF's central meridian) on
`INDIAN_1960_PROJ4`. The readings differ by 530 m (zone 48) to 600 m (zone 49).

**The datum check is an outside opinion, not self-consistency.** Hà Nội and Huế
are public sheets a person georeferenced by hand against a modern basemap (an
earlier edition, 2, so the images are registered by SIFT + RANSAC, 2,800+
inliers each). At the hand-placed control points:

| | explicit Indian 1960 | WGS84, unshifted | GDAL's own reading |
|---|---|---|---|
| Hà Nội (6 hand points, Helmert, 31 m self-RMS) | **69 m** | 587 m | 497 m |
| Huế (3 hand points, Helmert, 10 m self-RMS) | **29 m** | 516 m | 516 m |

The Indian 1960 residuals point in different directions on the two sheets
(Hà Nội 38 m E / 52 m S, Huế 4 m W / 24 m N), which is hand-fit error rather
than a datum bias. No georeference is written unless both choose Indian 1960.

**Gates, per sheet** (any failure holds the georeference; the image still
moves): control points within 10 m of an affine; square ground pixels at the
printed scale; neatline within 150 m of the XMP's graticule (a zone check —
blind to datum by construction); neatline aspect within 3% of the graticule
rectangle's; a dark printed frame line found within 6 px of the PDF's neatline
on ≥60% of samples (verified to fail on a 15 px shift); the city's centre
inside the warped sheet. One XMP erratum is overridden by what the sheet
prints: Nha Trang's XMP says 12°11′10″ N, both bottom corners print 12°11′40″.

## USGS result — 6 October 2026

Applied once, and a repeat dry run plans nothing. 18 USGS `cell_printings` were
written. All 16 PCL draft rectos now have the GeoPDF raster as their primary
image at `iiif/<map>/v2`, with the PCL image kept as a non-primary row. **14 are
georeferenced.** Two keep the new image but have no georeference: **Hải Phòng**
(control point 26 m off the affine) and **Quảng Ngãi** (37 m off). On both
sheets the outlying NGA control point sits exactly on its printed graticule
cross, and the affine puts that cross 20–35 px away. The paper is not affine
there, so an affine annotation would carry the error. They need more control
points and a transformation that bends, such as a thin-plate spline through
hand-checked crosses. The reason is recorded in `maps.extra_metadata.georef_held`.
Hà Nội and Huế got catalogue rows only; their public maps (and Sài Gòn's) were
read back unchanged. Per-sheet numbers: `work/l909/usgs-geopdfs.json`. Maps
stay draft. Nothing is queued.

## Other institutions — 6 October 2026

`work/l909/other-institutions.json` records what could be opened at institutions other
than PCL and USGS; `scripts/oneoff/import_l909_other_institutions.mjs` wrote two
`cell_printings` rows in production (no cells, maps or images; a second apply adds
zero): Princeton, Vinh và Bến Thủy, Edition 3-TPC, 1970 (Figgy scan, IIIF + PDF,
No Known Copyright) and Texas Tech, Sài Gòn, 1-AMS (FE), December 1964 (item
MAP12060301; its second file MAP12060301B is not described as a verso). Rights are null where the
catalogue is silent. `Princeton` is a new institution code and has a label in
`institutions.ts` and `sheetSources.ts`.

Not written, and why. The Library of Congress holds Sài Gòn 1963, An Túc (An Khê)
2-TPC 1970, Huế Ed. 4 1971 and Đồ Sơn 1-TPC 1970 (SRU records), but loc.gov is
403 to scripts, so digitisation is unverified; An Túc and Đồ Sơn would be new city
cells. NLA's `nla.obj-234148923` (a search snippet reports three digitised Saigon
editions) is behind a bot challenge. MONRE eLib timed out. Texas Tech's search is
captcha-gated and its item pages started answering captchas after a sequential
sweep, so none of the eight supplied object ids is L909 and no other TTU sheet was
confirmed. Virtual Saigon's "Biên Hòa 2-TPC 1968" points to PCL's file, not TTU's.
Princeton's Đà Lạt record is print only. No verso beyond PCL's Nha Trang and Qui Nhon
was found.
