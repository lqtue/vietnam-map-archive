#!/usr/bin/env python3
"""AMS Series L7014 (Vietnam 1:50,000) -> one PMTiles raster mosaic on R2.

The Perry-Castaneda Library publishes the series as GeoPDFs, and each one
carries its own georeference: eight NGA control points in pixel space, the
printed neatline as a polygon, and an XMP block with the sheet's title, edition
and date. So there is nothing to georeference by hand -- clip each sheet to its
neatline, warp to Web Mercator, and tile the lot as a single archive served the
way `basemap/vietnam-*.pmtiles` already is.

    python3 scripts/l7014_mosaic.py index      # scrape the PCL index
    python3 scripts/l7014_mosaic.py fetch      # download the GeoPDFs
    python3 scripts/l7014_mosaic.py warp       # clip to neatline, reproject
    python3 scripts/l7014_mosaic.py tile       # mosaic -> MBTiles -> PMTiles
    python3 scripts/l7014_mosaic.py upload     # rclone to r2:vma-tiles
    python3 scripts/l7014_mosaic.py check      # prove the graticule check fails
    python3 scripts/l7014_mosaic.py pinned     # warp the hand-pinned JPG sheets
    python3 scripts/l7014_mosaic.py meta       # re-read each PDF's XMP + graticule check
    python3 scripts/l7014_mosaic.py corners    # ground GCPs for the plain-JPG sheets
    python3 scripts/l7014_mosaic.py manifest   # one outline per sheet in the mosaic
    python3 scripts/l7014_mosaic.py residuals  # how well each sheet's GCPs actually fit
    python3 scripts/l7014_mosaic.py fit        # where every warped sheet actually landed

Every phase is resumable: it skips what it has already produced. `--limit N`
caps any phase, `--jobs N` sets concurrency.

Five traps, each of which otherwise yields a plausible, wrong map:

1. The datum is where a plausible wrong map comes from, twice over. GDAL cannot
   map some NGA LGIDict codes (`IND-I`, `INF-A`) and silently falls back to
   WGS84; and even a sheet that says Indian 1960 plainly gets no shift at all,
   because PROJ's EPSG:4131 -> 4326 pipeline covers only part of the country and
   returns the input UNCHANGED outside it rather than failing. Either way the
   sheet lands ~470 m northwest and the warp reports success. So the projection
   is rebuilt from what GDAL *did* parse (the central meridian names the UTM
   zone exactly), the datum shift is spelled out as a Helmert (INDIAN_1960_PROJ4)
   and never looked up, and `pick_crs` chooses between the sheet's declaration
   and that reading by measuring both against the 15' lattice -- an outside
   opinion, since the sheet's own graticule check cannot see this fault at all
   (see `lattice_error`). `fit` is the same measurement over a built archive and
   exits 1, so it belongs between `tile` and `upload`. `check` shows the
   graticule test failing on purpose, because a check that cannot fail is not one.
2. The UTM zone must come from the sheet's CENTRE. Many sheets end at longitude
   108.000, exactly the 48/49 boundary, and taking an edge puts them one zone
   over -- a clean 6 degree error that reads like a datum fault and is not.
3. The COG driver cannot carry a fourth band through JPEG compression. It
   demotes the alpha to an internal mask, `gdalbuildvrt` drops the mask, and the
   mosaic loses its transparency silently -- every hole turns into an opaque
   rectangle over the basemap. Hence plain GTiff + DEFLATE for the intermediates.
4. Some NEATLINE polygons repeat their closing vertex or self-intersect, which
   gdalwarp rejects outright.
5. A georeference annotation declares its own transformation, and warping it
   with a different one is invisible from both ends -- the fit still looks
   right in the Allmaps Editor, the warp still succeeds here. So `warp_flags`
   refuses a type gdalwarp cannot spell rather than falling back to an affine,
   and the mask is pushed through the very GCPs gdalwarp is handed, so the crop
   and the warp cannot disagree. `residuals` is the check that runs before any
   of it.

One honest limit: a few sheets declare Indian 1954 codes rather than Indian
1960, and this forces 1960 on all of them. The two differ by roughly 20 m here,
which the graticule check bounds and the series' own drafting accuracy exceeds.

Needs: GDAL with the PDF driver (`brew install gdal`), the `pmtiles` CLI, and
rclone with the `r2:` remote for `upload`.
"""

import argparse
import concurrent.futures as cf
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse

from datetime import date
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

INDEX_URL = "https://maps.lib.utexas.edu/maps/topo/vietnam/"
# PCL publishes the series twice: a flat alphabetical list and a clickable
# sheet diagram. Neither is complete -- the diagram is missing 37 sheets the
# list has, and the list is missing two the diagram has (6331-3 Ben Cat and
# 6331-4 Xom Ruong, both immediately north of Saigon). So both are read.
INDEX_MAP_URL = INDEX_URL + "vietnam_index.html"
WORK = Path("work/l7014")
SHEETS = WORK / "sheets.json"
PDF_DIR = WORK / "pdfs"
JPG_DIR = WORK / "jpgs"
COG_DIR = WORK / "cogs"
BUILD = WORK / "build"

# The whole series is on Indian 1960; only the codes vary (IND, INS, IND-I).
INDIAN_1960 = 4131
# ...and EPSG:4131 is not how to spell it. PROJ picks a transformation to WGS 84
# whose area of use covers only part of the country, and for a point outside it
# GDAL returns the input UNCHANGED rather than failing -- so the sheet warps,
# reports success and lands ~470 m northwest. Measured on the 20260913 archive:
# 314 of 437 GeoPDFs had come through with no datum shift at all, including 252
# that declared Indian 1960 outright. The Helmert is spelled out instead, the
# same one `corners` already uses: Everest 1830 (1937 Adjustment) and the
# Vietnam shift, no grid to fall off.
INDIAN_1960_PROJ4 = "+a=6377276.345 +rf=300.8017 +towgs84=198,881,317 +no_defs"
# How far a warped neatline may sit from the 15' lattice cell the sheet is
# named for. The fault this catches is ~470 m and the lattice itself is good to
# ~15 m, so anything in between is a comfortable place to draw the line.
LATTICE_TOL = 150.0
# Control points must land on the printed graticule to within this, in degrees.
# 5e-4 is ~55 m: loose enough for the sheets that genuinely sit a little off
# their declared cell (the worst measured is 31 m), tight enough that the datum
# mix-up this exists to catch -- 157 m on the sheet it was measured on -- is
# still rejected by a factor of three.
GRATICULE_TOL = 5e-4
# PCL sits behind a bot check that challenges anything claiming to be a browser
# and waves curl's own user agent through, so both fetches shell out to curl
# rather than dressing urllib up as Chrome.
CURL = ["curl", "-sL", "--fail", "--retry", "3", "--retry-delay", "2"]


# ── the 15' lattice ──────────────────────────────────────────────────────────

# The ArcGIS index (Vietnam_50k_L7014.mpk, 627 sheets) draws every sheet as an
# exact 15' x 15' cell and labels the layer WGS 84. It is not: those corners are
# the printed graticule, which is Indian 1960. Shifted, they reproduce a
# GeoPDF's own NEATLINE to 4-17 m -- which is what makes them usable as an
# outside opinion on where a sheet belongs.
#
#   ogr2ogr -f GeoJSON work/l7014/index.geojson <extracted>.gdb Vietnam_50k_L7014
INDEX_GEOJSON = WORK / "index.geojson"
ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}
_LATTICE = None


def wgs84():
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def indian_1960_geog():
    """Indian 1960 as lat/lon, with the datum shift written out rather than
    looked up. See INDIAN_1960_PROJ4 for why a lookup is not an option."""
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat " + INDIAN_1960_PROJ4)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def ground_metres(a, b):
    """Distance between two lon/lat pairs, locally. Degrees would understate
    the east-west miss by the cosine of the latitude and could not be held
    against a sheet's own ground resolution, which is the only number that
    says whether a fit is good enough."""
    return math.hypot((a[0] - b[0]) * 111320.0 * math.cos(math.radians(a[1])),
                      (a[1] - b[1]) * 110540.0)


def lattice_cells():
    """Every sheet's cell, keyed `6441IV`, as (west, south, east, north, name).
    Coordinates are Indian 1960, straight off the index -- `cell_corners`
    shifts them."""
    global _LATTICE
    if _LATTICE is None:
        if not INDEX_GEOJSON.exists():
            sys.exit(f"{INDEX_GEOJSON} missing -- see the comment above lattice_cells")
        cells = {}
        for f in json.loads(INDEX_GEOJSON.read_text())["features"]:
            ring = f["geometry"]["coordinates"][0][0]
            lons = [x for x, _ in ring]
            lats = [y for _, y in ring]
            cells[f["properties"]["Sheet_no"].replace(" ", "")] = (
                min(lons), min(lats), max(lons), max(lats), f["properties"]["Sheet_name"])
        _LATTICE = cells
    return _LATTICE


def sheet_keys(cells):
    """`6441IV` back to `6441-4`, which is how every other file spells it."""
    back = {v: k for k, v in ROMAN.items()}
    for key in cells:
        num, roman = key[:4], key[4:]
        if roman in back:
            yield f"{num}-{back[roman]}"


def cell_of(sheet, cells=None):
    """A sheet's raw index row, keyed `6441-4` -> `6441IV`. None if not indexed."""
    cells = cells if cells is not None else lattice_cells()
    num, _, quad = sheet.partition("-")
    return cells.get(num + ROMAN.get(quad, ""))


def cell_corners(sheet, cells=None):
    """A sheet's four cell corners in WGS 84, NW NE SE SW. None if not indexed."""
    cell = cell_of(sheet, cells)
    if not cell:
        return None
    w, s_, e, n, _ = cell
    to_wgs = osr.CoordinateTransformation(indian_1960_geog(), wgs84())
    # A transform that quietly does nothing is the failure this whole module is
    # most exposed to, so it has to be able to fail.
    if abs(to_wgs.TransformPoint(106.5, 10.75)[0] - 106.5) < 1e-4:
        sys.exit("the Indian 1960 datum shift is not being applied")
    return [to_wgs.TransformPoint(lon, lat)[:2]
            for lon, lat in ((w, n), (e, n), (e, s_), (w, s_))]


def load_sheets():
    return json.loads(SHEETS.read_text()) if SHEETS.exists() else []


def save_sheets(rows):
    SHEETS.parent.mkdir(parents=True, exist_ok=True)
    SHEETS.write_text(json.dumps(rows, indent=2))


# ── index ────────────────────────────────────────────────────────────────────

FILE_SHEET = re.compile(r"(\d{4})[-_](\d)\s*\.(?:pdf|jpg)$", re.I)

AREA = re.compile(r'<area[^>]*href="[^"]*/([^"/]+\.(?:pdf|jpg))"', re.I)

ENTRY = re.compile(
    r'<a href="([^"]+\.(?:pdf|jpg))"\s*>([^<]+)</a>[^<]*?Sheet\s+([0-9][\w-]*)',
    re.I,
)


def phase_index(args):
    res = subprocess.run(CURL + ["--max-time", "90", INDEX_URL], capture_output=True)
    if res.returncode:
        sys.exit(f"index: curl failed ({res.returncode})")
    html = res.stdout.decode("utf-8", "replace")
    if "not a bot" in html:
        sys.exit("index: PCL served its bot challenge; try again shortly")

    rows, seen = [], set()
    for href, name, sheet in ENTRY.findall(html):
        href = href.strip()
        key = href.lower()
        if key in seen:
            continue
        seen.add(key)
        # The index page's own "Sheet NNNN-N" text has typos (5654-1 printed as
        # 5641-1, 5949-3 as 5943-3). The filename is the one PCL actually serves,
        # so it wins wherever it parses. Nothing in the warp cares -- each GeoPDF
        # carries its own georeference -- but the join to the ArcGIS index does.
        m = FILE_SHEET.search(href)
        rows.append(
            {
                "file": href,
                "name": name.strip(),
                "sheet": f"{m.group(1)}-{m.group(2)}" if m else sheet.strip().rstrip(","),
                # The ~35 JPGs carry no georeference at all. They are recorded
                # rather than dropped, so what the mosaic is missing is legible.
                "kind": "pdf" if href.lower().endswith(".pdf") else "jpg",
                "url": INDEX_URL + urllib.parse.quote(href),
            }
        )

    res = subprocess.run(CURL + ["--max-time", "90", INDEX_MAP_URL], capture_output=True)
    for href in AREA.findall(res.stdout.decode("utf-8", "replace")):
        href = urllib.parse.unquote(href).strip()
        m = FILE_SHEET.search(href)
        # The diagram carries no sheet name, and one href is doubly suffixed
        # (don_duong-6732-4.pdf.pdf). A row without a parseable number is noise.
        if not m or href.lower() in seen or href.lower().count(".pdf") > 1:
            continue
        seen.add(href.lower())
        rows.append({
            "file": href,
            "name": Path(href).stem.rsplit("-", 2)[0].replace("_", " ").title(),
            "sheet": f"{m.group(1)}-{m.group(2)}",
            "kind": "pdf" if href.lower().endswith(".pdf") else "jpg",
            "url": INDEX_URL + urllib.parse.quote(href),
        })

    # Merge onto what is already recorded. `warp` writes year, edition,
    # crs_forced and graticule_err back onto these rows -- the audit trail
    # behind the datum trap -- and a plain overwrite here discards all of it
    # for every sheet that is not re-warped, silently and irrecoverably.
    known = {r["file"].lower(): r for r in load_sheets()}
    for r in rows:
        prev = known.get(r["file"].lower())
        if prev:
            r.update({k: v for k, v in prev.items() if k not in r})

    save_sheets(rows)
    pdfs = sum(1 for r in rows if r["kind"] == "pdf")
    print(f"index: {len(rows)} sheets -> {SHEETS}  ({pdfs} GeoPDF, {len(rows) - pdfs} JPG, no georeference)")


# ── fetch ────────────────────────────────────────────────────────────────────


def local_pdf(row):
    return PDF_DIR / (Path(row["file"]).stem.strip() + ".pdf")


def local_src(row):
    """Where a sheet's scan lands. The JPGs are fetched too -- they are the ones
    that need hand-georeferencing, and QGIS needs the file, not the URL."""
    if row["kind"] == "jpg":
        return JPG_DIR / (Path(row["file"]).stem.strip() + ".jpg")
    return local_pdf(row)


def download(row):
    dest = local_src(row)
    if dest.exists() and dest.stat().st_size > 0:
        return None
    tmp = dest.with_suffix(".part")
    res = subprocess.run(CURL + ["--max-time", "900", "-o", str(tmp), row["url"]],
                         capture_output=True, text=True)
    if res.returncode:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"curl {res.returncode}: {res.stderr.strip()[-120:]}")
    tmp.rename(dest)
    return f"{dest.name} {dest.stat().st_size // 1048576}MB"


def phase_fetch(args):
    rows = load_sheets()
    if args.limit:
        rows = rows[: args.limit]
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    JPG_DIR.mkdir(parents=True, exist_ok=True)
    done = skipped = failed = 0
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for row, res in zip(rows, pool.map(lambda r: _safe(download, r), rows)):
            if isinstance(res, Exception):
                failed += 1
                print(f"  FAIL {row['file']}: {res}")
            elif res is None:
                skipped += 1
            else:
                done += 1
    print(f"fetch: {done} downloaded, {skipped} already present, {failed} failed")


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception as e:  # noqa: BLE001 - reported per sheet, never fatal
        return e


# ── warp ─────────────────────────────────────────────────────────────────────


def xmp_fields(ds):
    raw = ds.GetMetadata("xml:XMP")
    if not raw:
        return {}
    return dict(re.findall(r"<pdfx:(\w+)>([^<]*)</pdfx:\w+>", raw[0]))


def sheet_crs(ds, meta, force_epsg=None):
    """The sheet's projected CRS, and whether GDAL supplied it.

    `force_epsg` exists for `check`: it lets a deliberately wrong geographic CRS
    be pushed through, to prove the graticule test rejects it.
    """
    got = osr.SpatialReference()
    wkt = ds.GetGCPProjection() or ds.GetProjection()
    if wkt:
        got.ImportFromWkt(wkt)
    if force_epsg is None and wkt and got.GetAttrValue("DATUM") not in (None, "unknown"):
        return got, True

    # GDAL failing on the datum code does not mean it failed on the projection:
    # it usually parsed the Transverse Mercator parameters fine and only the
    # geodetic datum came out "unknown". When the central meridian is there, it
    # names the zone exactly -- no guessing from a corner.
    cm = got.GetProjParm("central_meridian") if wkt else 0
    if cm:
        zone = int(round((cm + 183) / 6))
    else:
        # Otherwise the sheet's CENTRE, never an edge: plenty of sheets end at
        # ur_long 108.000, exactly the 48/49 boundary, and taking the east edge
        # throws those into the next zone -- a clean 6 degree error that looks
        # like a datum problem and is not.
        west = float((meta.get("ll_long") or "0").lstrip("+") or 0)
        east = float((meta.get("ur_long") or "0").lstrip("+") or 0)
        lon = (west + east) / 2 if west and east else (east or west)
        if not lon:
            raise ValueError("no usable projection and no XMP longitude to rebuild one")
        zone = int((lon + 180) // 6) + 1

    forced = osr.SpatialReference()
    if force_epsg:
        forced.ImportFromEPSG(force_epsg)
        forced.SetUTM(zone, True)
    else:
        forced.ImportFromProj4(f"+proj=utm +zone={zone} +units=m {INDIAN_1960_PROJ4}")
    return forced, False


def indian_1960_utm(srs):
    """The same projection, re-declared on Indian 1960 with the shift spelled out.

    Datum codes on these sheets are a mess -- IND, INS, IND-I, and GDAL warns
    `Unhandled value for Datum` and defaults to WGS84 on some of them -- so the
    declared datum is not evidence. What it is good for is the projection: the
    zone came out of the same WKT either way. `pick_crs` decides between this
    and the declaration by measurement rather than by trusting either.
    """
    zone = srs.GetUTMZone()
    if not zone:
        cm = srs.GetProjParm("central_meridian")
        zone = int(round((cm + 183) / 6)) if cm else 0
    if not zone:
        return None
    out = osr.SpatialReference()
    out.ImportFromProj4(f"+proj=utm +zone={abs(zone)} +units=m {INDIAN_1960_PROJ4}")
    return out


def lattice_error(ds, srs, sheet, cells=None):
    """Mean metres from the sheet's registration to its 15' lattice cell.

    This is the check `graticule_error` cannot be. That one reads the sheet's
    control points into the sheet's OWN datum and compares them with the
    graticule the sheet itself prints -- both sides move together when the
    datum is wrong, so it returns ~0 for exactly the fault it looks like it is
    guarding. The lattice is outside the sheet, in WGS 84, and does not move.

    None when the sheet is not in the ArcGIS index (93 of them are not).
    """
    cells = cells if cells is not None else lattice_cells()
    corners = cell_corners(sheet, cells)
    if not corners:
        return None
    pts = registration_points(ds)
    if not pts:
        return None
    to_wgs = osr.CoordinateTransformation(srs, wgs84())
    got = [to_wgs.TransformPoint(x, y)[:2] for x, y in pts]
    return sum(min(ground_metres(g, c) for g in got) for c in corners) / len(corners)


def pick_crs(ds, meta, sheet, cells=None):
    """The CRS whose warp actually lands on the sheet's cell, and its miss.

    Two candidates, ~470 m apart: what the PDF declares, and the same
    projection on Indian 1960 with the Helmert written out. The lattice is a
    third party to both, so this is a measurement and not a preference -- and
    it can fail, which is the whole point: a sheet that misses on both readings
    is refused rather than warped into the archive at whichever miss is smaller.
    """
    declared, trusted = sheet_crs(ds, meta)
    candidates = [(declared, "declared" if trusted else "forced")]
    alt = indian_1960_utm(declared)
    if alt is not None and not alt.IsSame(declared):
        candidates.append((alt, "indian1960"))
    scored = []
    for srs, label in candidates:
        err = lattice_error(ds, srs, sheet, cells)
        scored.append((float("inf") if err is None else err, srs, label))
    # No cell to check against: nothing to choose with, so keep the declaration
    # and let graticule_error be the only guard, as it was for these all along.
    if all(e == float("inf") for e, _, _ in scored):
        return declared, ("declared" if trusted else "forced"), None
    err, srs, label = min(scored, key=lambda t: t[0])
    if err > LATTICE_TOL:
        raise ValueError(f"no reading of the CRS lands on cell {sheet}: "
                         + ", ".join(f"{l} {e:.0f} m" for e, _, l in scored))
    return srs, label, err


def registration_points(ds):
    """Projected points whose extent should be the sheet's graticule cell.

    The control points when the sheet has them; otherwise the neatline's own
    vertices, since the printed border *is* the cell. Not the raster corners --
    those sit about a kilometre outside it, in the collar.
    """
    if ds.GetGCPs():
        return [(g.GCPX, g.GCPY) for g in ds.GetGCPs()]
    neat = ds.GetMetadata().get("NEATLINE")
    if not neat:
        return []
    ring = ogr.CreateGeometryFromWkt(neat).GetGeometryRef(0)
    return [ring.GetPoint_2D(i) for i in range(ring.GetPointCount())]


def graticule_error(ds, srs, meta):
    """How far the sheet's registration sits from the graticule it prints.

    In degrees, in the sheet's own datum. None when the XMP omits the corners.
    """
    to_geo = osr.CoordinateTransformation(srs, srs.CloneGeogCS())
    lons, lats = [], []
    for x, y in registration_points(ds):
        lat, lon = to_geo.TransformPoint(x, y)[:2]
        lons.append(lon)
        lats.append(lat)
    if not lons:
        return None
    got = (min(lons), min(lats), max(lons), max(lats))

    need = ("ll_lat", "ll_long", "ur_lat", "ur_long")
    if all(k in meta for k in need):
        want = tuple(float(meta[k].lstrip("+")) for k in ("ll_long", "ll_lat", "ur_long", "ur_lat"))
    else:
        # A few sheets carry no XMP at all. The series is a regular 15' lattice,
        # so the cell the sheet *should* occupy is its own extent snapped to the
        # nearest quarter degree -- which a wrong datum misses by its whole
        # shift, because that shift is an order of magnitude wider than the
        # snap. Weaker than the printed corners, still a real check.
        want = tuple(round(v / 0.25) * 0.25 for v in got)

    return max(abs(a - b) for a, b in zip(got, want))


def write_cutline(ds, srs, path):
    """The NEATLINE, repaired. Duplicate closing vertices are common and fatal."""
    neat = ds.GetMetadata().get("NEATLINE")
    if not neat:
        return None
    geom = ogr.CreateGeometryFromWkt(neat)
    if not geom.IsValid():
        geom = geom.MakeValid() or geom.Buffer(0)
    if not geom or geom.IsEmpty():
        return None
    path.unlink(missing_ok=True)
    src = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    layer = src.CreateLayer("cutline", srs, ogr.wkbPolygon)
    feat = ogr.Feature(layer.GetLayerDefn())
    feat.SetGeometry(geom)
    layer.CreateFeature(feat)
    src = None
    return path


def warp_one(row):
    pdf = local_pdf(row)
    out = COG_DIR / (pdf.stem + ".tif")
    if out.exists():
        return "skip", f"{pdf.stem}: already warped"
    if not pdf.exists():
        return "miss", f"{pdf.stem}: not downloaded"

    ds = gdal.Open(str(pdf))
    meta = xmp_fields(ds)
    # A handful of sheets carry a geotransform and a neatline but no control
    # points; those still place, and still get checked, off the neatline. What
    # is unusable is a sheet with neither -- a plain scan wearing a .pdf.
    if not ds.GetGCPs() and ds.GetGeoTransform(can_return_null=True) is None:
        return "nogeo", f"{pdf.stem}: no georeference of any kind"

    try:
        srs, crs_src, lat_err = pick_crs(ds, meta, row["sheet"])
    except ValueError as e:
        return "offcell", f"{pdf.stem}: {e}"
    trusted = crs_src == "declared"
    err = graticule_error(ds, srs, meta)
    if err is not None and err > GRATICULE_TOL:
        return "offgrid", f"{pdf.stem}: control points {err:.5f} deg off the printed graticule"

    cut = write_cutline(ds, srs, out.with_suffix(".cutline.gpkg"))
    # -s_srs cannot override a dataset that already claims a CRS, so when GDAL
    # guessed wrong the corrected one is re-declared on a VRT first.
    vrt = out.with_suffix(".src.vrt")
    gdal.Translate(str(vrt), ds, format="VRT", outputSRS=srs)
    ds = None

    cmd = [
        "gdalwarp", "-t_srs", "EPSG:3857", "-r", "cubic", "-dstalpha",
        # White, not black, under the transparent margin. Nothing *shows* those
        # pixels, but every resampling step averages them into the visible edge,
        # and black there draws a dark outline around every hole in the mosaic.
        "-wo", "INIT_DEST=255,255,255,0",
        # GTiff + DEFLATE rather than COG + JPEG: the COG driver cannot carry a
        # fourth band through JPEG, so it demotes the alpha to an internal mask
        # -- which `gdalbuildvrt` then drops, and the mosaic loses its
        # transparency without a word.
        "-of", "GTiff", "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=2",
        "-co", "TILED=YES", "-co", "BIGTIFF=IF_SAFER",
        "-multi", "-overwrite",
    ]
    if cut:
        cmd += ["-cutline", str(cut), "-cl", "cutline", "-crop_to_cutline"]
    cmd += [str(vrt), str(out)]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode:
        out.unlink(missing_ok=True)
        return "fail", f"{pdf.stem}: {res.stderr.strip()[-200:]}"

    row["year"] = (meta.get("pri_date") or "")[:4] or None
    row["edition"] = meta.get("edition")
    row["crs_forced"] = not trusted
    row["crs_src"] = crs_src
    row["graticule_err"] = err
    row["lattice_err"] = lat_err
    note = "" if trusted else f" [CRS {crs_src}]"
    if lat_err is not None:
        note += f" [cell {lat_err:.0f} m]"
    return "ok", f"{pdf.stem}: {out.stat().st_size // 1048576}MB{note}"


def phase_warp(args):
    all_rows = load_sheets()
    rows = [r for r in all_rows if r["kind"] == "pdf"]
    if args.limit:
        rows = rows[: args.limit]
    COG_DIR.mkdir(parents=True, exist_ok=True)

    tally = {}
    # Threads are enough: the work happens in the gdalwarp subprocess.
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for status, msg in pool.map(_warp_safe, rows):
            tally[status] = tally.get(status, 0) + 1
            if status not in ("ok", "skip"):
                print(f"  {status.upper()} {msg}")
    # `rows` holds the same objects as `all_rows`, so the year and edition
    # warp_one read off each sheet are already in place.
    save_sheets(all_rows)
    print("warp: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    if tally.get("offgrid"):
        print("  offgrid sheets were left out of the mosaic rather than placed wrongly.")


def _warp_safe(row):
    try:
        return warp_one(row)
    except Exception as e:  # noqa: BLE001
        return "fail", f"{row['file']}: {e}"


# ── tile ─────────────────────────────────────────────────────────────────────


def run(cmd, **kw):
    res = subprocess.run(cmd, **kw)
    if res.returncode:
        sys.exit(f"failed: {' '.join(str(c) for c in cmd)}")
    return res


def phase_tile(args):
    cogs = sorted(COG_DIR.glob("*.tif"))
    if not cogs:
        sys.exit("tile: no COGs; run warp first")
    BUILD.mkdir(parents=True, exist_ok=True)
    vrt, mb, pm = BUILD / "mosaic.vrt", BUILD / "mosaic.mbtiles", BUILD / f"{args.key}.pmtiles"

    # `-resolution highest` keeps the 300 dpi sheets sharp; the default average
    # would quietly downsample them to the 150 dpi ones.
    run(["gdalbuildvrt", "-q", "-overwrite", "-resolution", "highest", str(vrt)]
        + [str(c) for c in cogs])

    mb.unlink(missing_ok=True)
    # WEBP, not JPEG: the mosaic has holes (missing sheets, the JPG-only ones),
    # and a JPEG tile has no alpha, so every gap would paint black over the
    # basemap. LOWER stops at native resolution instead of inventing a zoom
    # level that quadruples the archive for no detail.
    #
    # WEBP's one cost: it discards the RGB under fully transparent pixels, so
    # the white this pipeline puts there is gone by the time `gdaladdo` averages
    # a half-covered edge, leaving a thin dark line around every hole. PNG keeps
    # it and the line goes away -- for nine times the bytes, on every tile a
    # reader pans across (35 GB against 3 GB, measured). Hence the flag, not a
    # different default.
    run(["gdal_translate", "-q", "-of", "MBTILES", str(vrt), str(mb),
         "-co", f"TILE_FORMAT={args.tile_format}", "-co", f"QUALITY={args.quality}",
         "-co", "ZOOM_LEVEL_STRATEGY=LOWER"])
    run(["gdaladdo", "-q", "-r", "average", str(mb)])

    pm.unlink(missing_ok=True)
    run(["pmtiles", "convert", str(mb), str(pm)])
    print(f"tile: {len(cogs)} sheets -> {pm} ({pm.stat().st_size // 1048576} MB)")
    run(["pmtiles", "show", str(pm)])


# ── upload ───────────────────────────────────────────────────────────────────


def phase_upload(args):
    pm = BUILD / f"{args.key}.pmtiles"
    if not pm.exists():
        sys.exit(f"upload: {pm} not found; run tile first")
    key = f"overlay/{args.key}.pmtiles"
    run(["rclone", "copyto", str(pm), f"r2:vma-tiles/{key}", "--s3-no-check-bucket",
         "--progress"])
    print(f"uploaded: https://tiles.maparchive.vn/{key}")

    # The sheet index rides the same dated key: pixels and the outlines that
    # address them are one release, or a reader clicks a sheet the archive
    # does not hold.
    gj = BUILD / f"{args.key}.geojson"
    if gj.exists():
        run(["rclone", "copyto", str(gj), f"r2:vma-tiles/overlay/{args.key}.geojson",
             "--s3-no-check-bucket"])
        print(f"uploaded: https://tiles.maparchive.vn/overlay/{args.key}.geojson")
    else:
        print("no sheet manifest built (run `manifest`) — uploading pixels only")

    print("Now point L7014_PMTILES_URL in src/lib/map/basemapStyle.ts at that URL.")


# ── check ────────────────────────────────────────────────────────────────────


def phase_check(args):
    """Prove the graticule test can fail.

    A check that shares its subject's blind spot passes on a broken sheet. This
    feeds a real sheet through the wrong datum -- WGS84, which is exactly what
    GDAL falls back to on an `IND-I` code -- and asserts the error it reports is
    both large and larger than the tolerance, then asserts the right datum
    passes. Needs one fetched sheet; run `fetch --limit 1` first.
    """
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit("check: no PDFs; run `fetch --limit 1` first")

    ds = gdal.Open(str(pdfs[0]))
    meta = xmp_fields(ds)
    if not ds.GetGCPs():
        sys.exit(f"check: {pdfs[0].name} has no control points; try another sheet")

    right, _ = sheet_crs(ds, meta)
    good = graticule_error(ds, right, meta)
    assert good is not None, "XMP carries no graticule corners to check against"
    assert good <= GRATICULE_TOL, f"correct datum should pass, got {good}"

    # 4326 = the WGS84 fallback. Same UTM zone, wrong ellipsoid.
    wrong, _ = sheet_crs(ds, meta, force_epsg=4326)
    bad = graticule_error(ds, wrong, meta)
    assert bad > GRATICULE_TOL, f"wrong datum should fail, got {bad}"
    assert bad > good * 10, f"wrong datum should be far worse, got {bad} vs {good}"

    print(f"check: {pdfs[0].name}")
    print(f"  Indian 1960 : {good:.6f} deg  <= {GRATICULE_TOL}  pass")
    print(f"  WGS84       : {bad:.6f} deg  >  {GRATICULE_TOL}  rejected ({bad * 111320:.0f} m out)")
    print("check: ok - the graticule test rejects the datum GDAL falls back to")


# ── cli ──────────────────────────────────────────────────────────────────────

# ── corners ──────────────────────────────────────────────────────────────────

# `corners` is a crib sheet for hand-georeferencing the sheets PCL publishes as
# plain JPGs: the ground half of each GCP, off the lattice (see lattice_cells).
# The pixel half is four clicks per sheet in QGIS's Georeferencer -- a scan's
# collar and skew are not in any index.
CORNERS_CSV = WORK / "corners.csv"
# Every cell's four WGS 84 corners, written for readers outside this script --
# `scripts/geo_audit.mjs` checks the archive's warped sheets against it. It is
# an artifact rather than a second implementation on purpose: the datum shift
# is the thing that goes wrong here, and a JS copy of the Helmert would be one
# more place for it to go wrong differently.
LATTICE_JSON = WORK / "lattice.json"
GCP_DIR = WORK / "gcp"
# Mean neatline inset (left, top, right, bottom) as a fraction of the page,
# measured over 36 georeferenced sheets. sd is 0.013 of the width -- ~700 m --
# so this positions a marker to drag, never a control point to trust.
INSET = (0.0333, 0.0326, 0.9629, 0.7788)


def phase_corners(args):
    cells = lattice_cells()
    sheets = load_sheets()
    # Phu Vang 6542-3 is published both ways. The GeoPDF is already in the
    # mosaic, so its JPG needs no hand work -- and any future overlap likewise.
    as_pdf = {r["sheet"] for r in sheets if r["kind"] == "pdf"}
    rows = [r for r in sheets if r["kind"] == "jpg" and r["sheet"] not in as_pdf]
    if args.limit:
        rows = rows[: args.limit]
    out = ["sheet,name,corner,lon,lat"]
    missing = []
    for r in rows:
        pts = cell_corners(r["sheet"], cells)
        if not pts:
            missing.append(r["sheet"])
            continue
        name = cell_of(r["sheet"], cells)[4]
        for corner, (x, y) in zip(CORNERS, pts):
            out.append(f'{r["sheet"]},"{name or r["name"]}",{corner},{x:.6f},{y:.6f}')
    CORNERS_CSV.write_text("\n".join(out) + "\n")

    # ...and one QGIS Georeferencer .points file per sheet, so the ground half
    # is already typed in and the operator only drags each of the four markers
    # onto the neatline corner it belongs to. The pixel positions are a guess
    # from the mean neatline inset measured over 36 georeferenced sheets; that
    # mean is worth +/-700 m, which is useless as an answer and fine as a place
    # to start dragging from. QGIS writes image rows negative, hence -y.
    GCP_DIR.mkdir(parents=True, exist_ok=True)
    for r in rows:
        src = local_src(r)
        if not src.exists():
            continue
        ds = gdal.Open(str(src))
        w, h = ds.RasterXSize, ds.RasterYSize
        ds = None
        pts = cell_corners(r["sheet"], cells)
        if not pts:
            continue
        guess = {"NW": (INSET[0] * w, INSET[1] * h), "NE": (INSET[2] * w, INSET[1] * h),
                 "SE": (INSET[2] * w, INSET[3] * h), "SW": (INSET[0] * w, INSET[3] * h)}
        lines = ["#CRS: EPSG:4326",
                 "mapX,mapY,sourceX,sourceY,enable,dX,dY,residual"]
        for corner, (x, y) in zip(CORNERS, pts):
            px, py = guess[corner]
            lines.append(f"{x:.7f},{y:.7f},{px:.1f},{-py:.1f},1,0,0,0")
        (GCP_DIR / f"{r['sheet']}.points").write_text("\n".join(lines) + "\n")

    LATTICE_JSON.write_text(json.dumps({
        "note": "Sheet cell corners, NW NE SE SW, WGS 84. Written by "
                "`l7014_mosaic.py corners` from work/l7014/index.geojson, which is "
                "Indian 1960 -- do not re-derive, the shift is the trap.",
        "cells": {sheet: [[round(x, 7), round(y, 7)] for x, y in pts]
                  for sheet in sorted(sheet_keys(cells))
                  if (pts := cell_corners(sheet, cells))},
    }, indent=0))

    print(f"{CORNERS_CSV}: {len(rows) - len(missing)} sheets x 4 corners")
    print(f"{LATTICE_JSON}: {len(json.loads(LATTICE_JSON.read_text())['cells'])} cells")
    print(f"{GCP_DIR}/: one .points per sheet, ground filled in, corners to drag")
    if missing:
        print("not in the index:", ", ".join(missing))


# ── meta ─────────────────────────────────────────────────────────────────────


def meta_one(row):
    """Everything `warp` records about a sheet, minus the warp. Reads the PDF
    only, so re-deriving the whole series is a couple of minutes rather than a
    couple of hours -- which is what makes a lost audit trail recoverable."""
    pdf = local_pdf(row)
    if not pdf.exists():
        return "miss"
    ds = gdal.Open(str(pdf))
    m = xmp_fields(ds)
    if not ds.GetGCPs() and ds.GetGeoTransform(can_return_null=True) is None:
        row["graticule_err"] = None
        return "nogeo"
    srs, trusted = sheet_crs(ds, m)
    row["year"] = (m.get("pri_date") or "")[:4] or None
    row["edition"] = m.get("edition")
    row["crs_forced"] = not trusted
    row["graticule_err"] = graticule_error(ds, srs, m)
    return "ok"


def phase_meta(args):
    rows = [r for r in load_sheets() if r["kind"] == "pdf"]
    if args.limit:
        rows = rows[: args.limit]
    tally = {}
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for status in pool.map(lambda r: _safe(meta_one, r) or "fail", rows):
            tally[status] = tally.get(status, 0) + 1
    save_sheets(load_sheets_merged(rows))
    print("meta: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))


def load_sheets_merged(updated):
    by_file = {r["file"].lower(): r for r in updated}
    return [by_file.get(r["file"].lower(), r) for r in load_sheets()]


# ── gcps ─────────────────────────────────────────────────────────────────────

PINS = WORK / "pins.json"
CITY = {"6330-4", "6330-1", "6330-2", "6330-3", "6329-1", "6329-4",
        "6541-4", "6641-3", "6350-4"}
CORNERS = ("NW", "NE", "SE", "SW")


def warp_flags(transformation):
    """gdalwarp flags for the transformation an annotation declares.

    Silence here is the trap. An annotation that says thinPlateSpline, warped
    with this script's old hardcoded affine, fits beautifully in the Allmaps
    Editor and lands wrong in the archive with no error on either side. So an
    unmappable type is refused rather than approximated: gdalwarp has -order
    and -tps and nothing else, which leaves helmert and projective with no
    honest spelling.
    """
    t = (transformation or {}).get("type", "polynomial").lower()
    order = int(((transformation or {}).get("options") or {}).get("order", 1))
    if t == "thinplatespline":
        return ["-tps"], "tps"
    if t == "polynomial" and order in (1, 2, 3):
        return ["-order", str(order)], f"order {order}"
    raise ValueError(f"transformation {t!r} order {order} has no gdalwarp equivalent")


def parse_gcp_text(text):
    """GCPs from either text format the Allmaps GCP box accepts.

    QGIS .points is CSV with a header and the ground pair first, and its
    sourceY is NEGATIVE -- QGIS measures the georeferencer's y up from the
    image top. The GDAL form is bare whitespace columns, pixel pair first, y
    already down. They are told apart by the header rather than by looking at
    the numbers: a column-order guess reads a longitude as a pixel on any
    sheet wider than 105 px, which is all of them.
    """
    pts = []
    qgis = "sourceX" in text
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("mapX"):
            continue
        f = [x for x in re.split(r"[,\s]+", line) if x]
        if len(f) < 4:
            continue
        try:
            a, b, c, d = (float(x) for x in f[:4])
        except ValueError:
            continue
        pts.append((c, -d, a, b) if qgis else (a, b, c, d))
    return pts


def gcps_from_annotation(path):
    """Control points, transformation and mask out of a georeference annotation."""
    doc = json.loads(path.read_text())
    items = doc.get("items") if doc.get("type") == "AnnotationPage" else [doc]
    if len(items or []) != 1:
        raise ValueError(f"{path.name}: {len(items or [])} annotations, expected one")
    anno = items[0]
    body = anno.get("body") or {}
    pts = []
    for feat in body.get("features") or []:
        px, py = feat["properties"]["resourceCoords"]
        lon, lat = feat["geometry"]["coordinates"]
        pts.append((float(px), float(py), float(lon), float(lat)))
    if len(pts) < 3:
        raise ValueError(f"{path.name}: {len(pts)} control points, need 3")
    flags, label = warp_flags(body.get("transformation"))
    sel = (((anno.get("target") or {}).get("selector")) or {}).get("value") or ""
    hit = re.search(r'points="([^"]+)"', sel)
    mask = [tuple(float(v) for v in p.split(",")) for p in hit.group(1).split()] if hit else None
    return {"pts": pts, "flags": flags, "label": label, "mask": mask, "src": path.name}


def load_gcps(sheet, pins=None):
    """A sheet's control points, from the most recently approved source it has.

    An annotation wins because it is the only one of the three a person has
    watched warp. pins.html's four dragged corners come next, and the .points
    `corners` writes is last: its ground is real but its pixels are a guess,
    placed there to be dragged.
    """
    anno = GCP_DIR / f"{sheet}.json"
    if anno.exists():
        return gcps_from_annotation(anno)
    pin = (pins or {}).get(sheet)
    if pin:
        pts = [(*pin["pixels"][c], *pin["ground"][c]) for c in CORNERS]
        ground = [tuple(pin["ground"][c]) for c in CORNERS]
        return {"pts": pts, "flags": ["-order", "1"], "label": "order 1",
                "mask": None, "ground_quad": ground, "src": "pins.json"}
    pf = GCP_DIR / f"{sheet}.points"
    if pf.exists():
        pts = parse_gcp_text(pf.read_text())
        if len(pts) >= 3:
            return {"pts": pts, "flags": ["-order", "1"], "label": "order 1",
                    "mask": None, "src": pf.name}
    return None


# ── residuals ────────────────────────────────────────────────────────────────


def fit_residuals(pts, order):
    """Per-point miss, in local metres, for a least-squares fit of this order.

    Metres and not degrees: a degree of longitude here is ~109 km against
    latitude's 110.5, so a residual left in degrees understates the east-west
    error by the cosine of the latitude and cannot be held against the sheet's
    own ground resolution -- which is the only number that says whether a fit
    is good enough.
    """
    P = np.array([[p[0], p[1]] for p in pts], float)
    G = np.array([[p[2], p[3]] for p in pts], float)
    mx = 111320.0 * math.cos(math.radians(G[:, 1].mean()))
    M = np.c_[(G[:, 0] - G[:, 0].mean()) * mx, (G[:, 1] - G[:, 1].mean()) * 110540.0]
    x, y = P[:, 0], P[:, 1]
    A = (np.c_[x, y, np.ones(len(P))] if order == 1
         else np.c_[x, y, np.ones(len(P)), x * y, x * x, y * y])
    if len(P) < A.shape[1]:
        return None, None
    coef, *_ = np.linalg.lstsq(A, M, rcond=None)
    res = np.hypot(*(M - A @ coef).T)
    # Singular values of the linear block are the fit's own metres per pixel,
    # one per axis. Taking them from the fit rather than from the sheet's
    # declared scale means a residual in pixels stays honest on the city sheets,
    # which are ~1.3 m/px against the series' 4.2.
    mpp = float(np.linalg.svd(coef[:2], compute_uv=False).mean())
    return res, mpp


def phase_residuals(args):
    """What the control points say before anything is warped."""
    pins = json.loads(PINS.read_text()) if PINS.exists() else {}
    rows = [r for r in load_sheets() if not args.sheet or r["sheet"] == args.sheet]
    if args.limit:
        rows = rows[: args.limit]
    seen = 0
    for row in rows:
        try:
            gcp = load_gcps(row["sheet"], pins)
        except ValueError as e:
            print(f"{row['sheet']:9s} ERROR {e}")
            seen += 1
            continue
        if not gcp:
            continue
        seen += 1
        r1, mpp = fit_residuals(gcp["pts"], 1)
        line = (f"{row['sheet']:9s} n={len(gcp['pts']):3d}  {gcp['src']:22s} "
                f"{gcp['label']:8s} rms {r1.mean():6.1f} m ({r1.mean() / mpp:4.1f} px)"
                f"  max {r1.max():6.1f} m")
        r2, _ = fit_residuals(gcp["pts"], 2)
        if r2 is not None:
            line += f"  [order 2: rms {r2.mean():5.1f} m]"
        print(line)
        # Two different faults, and they want different fixes. One point far
        # outside the spread is a misplaced click -- order 2 will not rescue it,
        # which is exactly how you tell the two apart. A high rms that order 2
        # halves is the paper itself, and the annotation should say so.
        worst = int(r1.argmax())
        if r1.max() > 3 * r1.mean() and len(r1) > 4:
            px, py, lon, lat = gcp["pts"][worst]
            print(f"          ^ point {worst + 1} at px({px:.0f},{py:.0f}) misses by "
                  f"{r1.max():.1f} m, {r1.max() / r1.mean():.1f}x the rest — check it")
        elif r2 is not None and r2.mean() < 0.5 * r1.mean():
            print(f"          ^ order 2 halves the rms — real distortion; "
                  f"set the annotation's transformation rather than leaving it order 1")
        elif r1.mean() / mpp > 2:
            print(f"          ^ rms is {r1.mean() / mpp:.1f} px — loose for a warp")
    print(f"residuals: {seen} sheets with control points")


# ── pinned ───────────────────────────────────────────────────────────────────


def warp_pinned_one(row, gcp):
    """A hand-pinned JPG, warped like any other sheet.

    Four corners and an affine was all pin.html could give, and the sheets were
    measured as having no perspective a richer transform could recover. An
    Allmaps annotation can carry more points and declares its own
    transformation, so the flags come from `gcp` rather than from here.

    The cutline is the annotation's own mask, pushed through the very GCPs
    gdalwarp is about to use -- via gdal.Transformer on the VRT rather than a
    second fit of our own, so the crop and the warp cannot disagree. Without a
    mask it is the ground quad of the four corners, and with neither it is
    refused: where the paper ends is not a thing to guess.
    """
    src = JPG_DIR / (Path(row["file"]).stem.strip() + ".jpg")
    out = COG_DIR / (Path(row["file"]).stem.strip() + ".tif")
    if out.exists():
        return "skip", f"{row['sheet']}: already warped"
    if not src.exists():
        return "miss", f"{row['sheet']}: {src.name} not downloaded"

    flat = []
    for px, py, lon, lat in gcp["pts"]:
        flat += ["-gcp", f"{px}", f"{py}", f"{lon}", f"{lat}"]

    vrt = out.with_suffix(".src.vrt")
    res = subprocess.run(["gdal_translate", "-of", "VRT", "-a_srs", "EPSG:4326",
                          *flat, str(src), str(vrt)], capture_output=True, text=True)
    if res.returncode:
        return "fail", f"{row['sheet']}: translate: {res.stderr.strip()[-160:]}"

    if gcp.get("mask"):
        ds = gdal.Open(str(vrt))
        method = (["METHOD=GCP_TPS"] if "-tps" in gcp["flags"]
                  else ["METHOD=GCP_POLYNOMIAL", f"MAX_GCP_ORDER={gcp['flags'][1]}"])
        tr = gdal.Transformer(ds, None, method)
        ground = []
        for px, py in gcp["mask"]:
            ok, pt = tr.TransformPoint(0, float(px), float(py))
            if not ok:
                return "fail", f"{row['sheet']}: mask point ({px},{py}) would not transform"
            ground.append((pt[0], pt[1]))
        ds = None
    elif gcp.get("ground_quad"):
        ground = list(gcp["ground_quad"])
    else:
        return "fail", (f"{row['sheet']}: {gcp['src']} has no mask and is not four "
                        f"corners — give it a mask in the Allmaps Editor")

    cut = out.with_suffix(".cutline.gpkg")
    cut.unlink(missing_ok=True)
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for lon, lat in ground + [ground[0]]:
        ring.AddPoint_2D(lon, lat)
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(cut))
    layer = ds.CreateLayer("cutline", srs, ogr.wkbPolygon)
    feat = ogr.Feature(layer.GetLayerDefn())
    feat.SetGeometry(poly)
    layer.CreateFeature(feat)
    ds = None

    cmd = ["gdalwarp", "-t_srs", "EPSG:3857", "-r", "cubic", "-dstalpha",
           *gcp["flags"],
           # The same white-under-transparent and GTiff+DEFLATE as the GeoPDF
           # path, for the same two reasons: black bleeds into every hole edge
           # through resampling, and the COG driver silently drops the alpha.
           "-wo", "INIT_DEST=255,255,255,0",
           "-of", "GTiff", "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=2",
           "-co", "TILED=YES", "-co", "BIGTIFF=IF_SAFER",
           "-cutline", str(cut), "-cl", "cutline", "-crop_to_cutline",
           "-multi", "-overwrite", str(vrt), str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode:
        out.unlink(missing_ok=True)
        return "fail", f"{row['sheet']}: warp: {res.stderr.strip()[-160:]}"
    return "ok", f"{row['sheet']}: {gcp['label']}, {len(gcp['pts'])} gcps, {out.stat().st_size // 1048576}MB"


def phase_pinned(args):
    pins = json.loads(PINS.read_text()) if PINS.exists() else {}
    rows = [r for r in load_sheets() if r["kind"] == "jpg" and r["sheet"] not in CITY]
    if args.sheet:
        rows = [r for r in rows if r["sheet"] == args.sheet]
    todo = []
    for row in sorted(rows, key=lambda r: r["sheet"]):
        try:
            gcp = load_gcps(row["sheet"], pins)
        except ValueError as e:
            print(f"  FAIL {row['sheet']}: {e}")
            continue
        if gcp:
            todo.append((row, gcp))
    if not todo:
        sys.exit(f"no control points — save an annotation to {GCP_DIR}/<sheet>.json, "
                 f"or the pins from pin.html to {PINS}")
    if args.limit:
        todo = todo[: args.limit]
    COG_DIR.mkdir(parents=True, exist_ok=True)
    tally = {}
    for row, gcp in todo:
        status, msg = _safe(lambda a: warp_pinned_one(*a), (row, gcp)) or ("fail", "?")
        if isinstance(status, Exception):
            status, msg = "fail", str(status)
        tally[status] = tally.get(status, 0) + 1
        if status != "ok":
            print(f"  {status.upper()} {msg}")
    print("pinned: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    print(f"  ({len(CITY)} city sheets are left out — they go through Allmaps)")


# ── manifest ─────────────────────────────────────────────────────────────────

# A sheet is registered by a name, a number and an outline -- not by a second
# copy of its pixels. Those live once, in the archive `tile` builds. So the
# manifest is one feature per sheet actually in that archive, sharing its dated
# key so the two cannot drift apart.
MANIFEST_PROPS = ("sheet", "name", "year", "edition", "kind", "url")
# Generous box around the series. A footprint outside it means the transform
# put the sheet somewhere Vietnam is not -- which is what an axis-order slip
# looks like, and it throws no error on the way past.
MANIFEST_BOUNDS = (100.0, 5.0, 112.0, 25.0)


def sheet_outline(tif):
    """A sheet's outline in WGS 84: its cutline if it has one, else its extent.

    The cutline is the printed neatline, which is what the mosaic actually
    shows. The extent is that neatline's bounding box in Web Mercator, so
    falling back to it overstates a sheet by its own rotation -- a few hundred
    metres at the corners. Only sheets warped without a NEATLINE take it.
    """
    wgs84 = osr.SpatialReference()
    wgs84.ImportFromEPSG(4326)
    wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    cut = tif.with_suffix(".cutline.gpkg")
    if cut.exists():
        ds = ogr.Open(str(cut))
        layer = ds.GetLayer()
        src = layer.GetSpatialRef().Clone()
        # `feat` has to outlive the GetGeometryRef() borrow: chaining the two
        # frees the feature first and the reference comes back invalid.
        feat = layer.GetNextFeature()
        geom = feat.GetGeometryRef().Clone()
        ds = None
    else:
        img = gdal.Open(str(tif))
        gt = img.GetGeoTransform()
        w, h = img.RasterXSize, img.RasterYSize
        src = osr.SpatialReference(wkt=img.GetProjection())
        img = None
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for px, py in ((0, 0), (w, 0), (w, h), (0, h), (0, 0)):
            ring.AddPoint_2D(gt[0] + px * gt[1] + py * gt[2],
                             gt[3] + px * gt[4] + py * gt[5])
        geom = ogr.Geometry(ogr.wkbPolygon)
        geom.AddGeometry(ring)

    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geom.Transform(osr.CoordinateTransformation(src, wgs84))
    return geom


def phase_manifest(args):
    tifs = sorted(COG_DIR.glob("*.tif"))
    if not tifs:
        sys.exit("manifest: no warped sheets; run warp first")
    if args.limit:
        tifs = tifs[: args.limit]
    rows = {Path(r["file"]).stem.strip(): r for r in load_sheets()}
    BUILD.mkdir(parents=True, exist_ok=True)

    features, unknown, astray = [], [], []
    for tif in tifs:
        row = rows.get(tif.stem)
        if not row:
            unknown.append(tif.stem)
            continue
        geom = sheet_outline(tif)
        c = geom.Centroid()
        x0, y0, x1, y1 = MANIFEST_BOUNDS
        if not (x0 < c.GetX() < x1 and y0 < c.GetY() < y1):
            astray.append(f"{row['sheet']} at {c.GetX():.3f},{c.GetY():.3f}")
            continue
        features.append({
            "type": "Feature",
            # 5 decimals is ~1 m, an order finer than a 1:50,000 sheet's own
            # drafting error, and a third of the bytes of the default 15.
            "geometry": json.loads(geom.ExportToJson(options=["COORDINATE_PRECISION=5"])),
            "properties": {k: row.get(k) for k in MANIFEST_PROPS},
        })

    out = BUILD / f"{args.key}.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                              separators=(",", ":")))
    print(f"manifest: {len(features)} sheets -> {out} ({out.stat().st_size // 1024} kB)")
    print(f"  {len(rows) - len(features)} of {len(rows)} indexed sheets are not in the mosaic")
    for stem in unknown:
        print(f"  UNKNOWN {stem}: warped but not in sheets.json — re-run index")
    for msg in astray:
        print(f"  ASTRAY  {msg}: outside the series' own bounds")
    if astray:
        sys.exit("manifest: refused to write a sheet that lands outside Vietnam")


# ── fit ──────────────────────────────────────────────────────────────────────


def phase_fit(args):
    """Where every sheet in the built archive actually landed.

    `manifest` writes one outline per sheet in the mosaic; the lattice says
    where each of those outlines belongs. The two are independent, which is
    what `graticule_error` never was -- it reads the sheet's control points
    into the sheet's own datum and compares them with the graticule the sheet
    itself prints, so a wrong datum moves both sides together and the check
    returns ~0 for the one fault it looks like it is guarding. That is how 314
    of 437 sheets reached the 20260913 archive ~470 m northwest of their cells
    with nothing in the log.

    Exit 1 when any sheet misses by more than LATTICE_TOL, so this can stand
    between `tile` and `upload`.
    """
    path = BUILD / f"{args.key}.geojson"
    if not path.exists():
        sys.exit(f"{path} missing -- run `manifest --key {args.key}` first")
    cells = lattice_cells()
    rows, unindexed = [], []
    for feat in json.loads(path.read_text())["features"]:
        sheet = feat["properties"]["sheet"]
        corners = cell_corners(sheet, cells)
        if not corners:
            unindexed.append(sheet)
            continue
        geom = feat["geometry"]
        polys = (geom["coordinates"] if geom["type"] == "MultiPolygon"
                 else [geom["coordinates"]])
        ring = [v for poly in polys for v in poly[0]]
        # Nearest outline vertex to each cell corner, not the outline's own
        # bounding box: a sheet's paper is a little bigger than its cell and a
        # little rotated, so the box corners sit outside the neatline by more
        # than the fault being measured.
        miss = [min(ground_metres(v, c) for v in ring) for c in corners]
        rows.append((sum(miss) / 4, max(miss), sheet, feat["properties"]["kind"],
                     feat["properties"]["name"]))
    rows.sort(reverse=True)
    bad = [r for r in rows if r[0] > LATTICE_TOL]
    for mean, worst, sheet, kind, name in (bad or rows[:10]):
        print(f"  {sheet:9s} {kind:3s} mean {mean:7.0f} m  worst {worst:7.0f} m  {name}")
    good = sorted(r[0] for r in rows if r[0] <= LATTICE_TOL)
    if good:
        print(f"fit: {len(good)} sheets on cell, median {good[len(good) // 2]:.0f} m, "
              f"worst {good[-1]:.0f} m")
    if unindexed:
        print(f"  {len(unindexed)} not in the index, unchecked: "
              + ", ".join(sorted(unindexed)[:12]) + ("..." if len(unindexed) > 12 else ""))
    if bad:
        sys.exit(f"fit: {len(bad)} of {len(rows)} sheets more than {LATTICE_TOL:.0f} m "
                 f"off their cell -- do not upload this archive")


PHASES = {
    "index": phase_index,
    "fetch": phase_fetch,
    "warp": phase_warp,
    "tile": phase_tile,
    "upload": phase_upload,
    "pinned": phase_pinned,
    "meta": phase_meta,
    "corners": phase_corners,
    "manifest": phase_manifest,
    "residuals": phase_residuals,
    "check": phase_check,
    "fit": phase_fit,
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("phase", choices=PHASES)
    p.add_argument("--limit", type=int, help="cap the sheets this phase touches")
    p.add_argument("--sheet", help="one sheet number, e.g. 6150-2")
    p.add_argument("--jobs", type=int, default=6, help="concurrency (default 6)")
    p.add_argument("--quality", type=int, default=80, help="WEBP/JPEG quality (default 80)")
    p.add_argument("--tile-format", default="WEBP", choices=["WEBP", "PNG", "PNG8", "JPEG"],
                   help="tile encoding (default WEBP; PNG removes the dark hole "
                        "outline at ~9x the size)")
    p.add_argument("--key", default=f"l7014-{date.today():%Y%m%d}",
                   help="archive name; the build date is part of it because the "
                        "R2 domain caches hard and a rebuilt archive needs a new name")
    args = p.parse_args()
    PHASES[args.phase](args)


if __name__ == "__main__":
    main()
