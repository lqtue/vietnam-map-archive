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

Every phase is resumable: it skips what it has already produced. `--limit N`
caps any phase, `--jobs N` sets concurrency.

Four traps, each of which otherwise yields a plausible, wrong map:

1. GDAL cannot map some NGA LGIDict datum codes (`IND-I`, `INF-A`) and silently
   falls back to WGS84 -- the whole sheet lands ~450 m off, and the warp still
   succeeds. So the CRS is rebuilt from the projection GDAL *did* parse (its
   central meridian names the UTM zone exactly) or from the sheet's XMP, and
   every sheet's registration is then checked against the graticule corners the
   XMP prints. `check` shows that check failing on purpose, because a check that
   cannot fail is not one.
2. The UTM zone must come from the sheet's CENTRE. Many sheets end at longitude
   108.000, exactly the 48/49 boundary, and taking an edge puts them one zone
   over -- a clean 6 degree error that reads like a datum fault and is not.
3. The COG driver cannot carry a fourth band through JPEG compression. It
   demotes the alpha to an internal mask, `gdalbuildvrt` drops the mask, and the
   mosaic loses its transparency silently -- every hole turns into an opaque
   rectangle over the basemap. Hence plain GTiff + DEFLATE for the intermediates.
4. Some NEATLINE polygons repeat their closing vertex or self-intersect, which
   gdalwarp rejects outright.

One honest limit: a few sheets declare Indian 1954 codes rather than Indian
1960, and this forces 1960 on all of them. The two differ by roughly 20 m here,
which the graticule check bounds and the series' own drafting accuracy exceeds.

Needs: GDAL with the PDF driver (`brew install gdal`), the `pmtiles` CLI, and
rclone with the `r2:` remote for `upload`.
"""

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import urllib.parse

from datetime import date
from pathlib import Path

from osgeo import gdal, ogr, osr

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

INDEX_URL = "https://maps.lib.utexas.edu/maps/topo/vietnam/"
WORK = Path("work/l7014")
SHEETS = WORK / "sheets.json"
PDF_DIR = WORK / "pdfs"
COG_DIR = WORK / "cogs"
BUILD = WORK / "build"

# The whole series is on Indian 1960; only the codes vary (IND, INS, IND-I).
INDIAN_1960 = 4131
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


def load_sheets():
    return json.loads(SHEETS.read_text()) if SHEETS.exists() else []


def save_sheets(rows):
    SHEETS.parent.mkdir(parents=True, exist_ok=True)
    SHEETS.write_text(json.dumps(rows, indent=2))


# ── index ────────────────────────────────────────────────────────────────────

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
        rows.append(
            {
                "file": href,
                "name": name.strip(),
                "sheet": sheet.strip().rstrip(","),
                # The ~35 JPGs carry no georeference at all. They are recorded
                # rather than dropped, so what the mosaic is missing is legible.
                "kind": "pdf" if href.lower().endswith(".pdf") else "jpg",
                "url": INDEX_URL + urllib.parse.quote(href),
            }
        )

    save_sheets(rows)
    pdfs = sum(1 for r in rows if r["kind"] == "pdf")
    print(f"index: {len(rows)} sheets -> {SHEETS}  ({pdfs} GeoPDF, {len(rows) - pdfs} JPG, no georeference)")


# ── fetch ────────────────────────────────────────────────────────────────────


def local_pdf(row):
    return PDF_DIR / (Path(row["file"]).stem.strip() + ".pdf")


def download(row):
    dest = local_pdf(row)
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
    rows = [r for r in load_sheets() if r["kind"] == "pdf"]
    if args.limit:
        rows = rows[: args.limit]
    PDF_DIR.mkdir(parents=True, exist_ok=True)
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
    forced.ImportFromEPSG(force_epsg or INDIAN_1960)
    forced.SetUTM(zone, True)
    return forced, False


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

    srs, trusted = sheet_crs(ds, meta)
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
    row["graticule_err"] = err
    note = " [CRS forced]" if not trusted else ""
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

PHASES = {
    "index": phase_index,
    "fetch": phase_fetch,
    "warp": phase_warp,
    "tile": phase_tile,
    "upload": phase_upload,
    "check": phase_check,
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("phase", choices=PHASES)
    p.add_argument("--limit", type=int, help="cap the sheets this phase touches")
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
