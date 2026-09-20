#!/usr/bin/env python3
"""Place the 74 unplaced L7014 sheets automatically, and prove it in pixels.

Every one of these sheets already failed `l7014_mosaic.py warp` for a
documented reason -- NOGEO (no georeference at all), OFFCELL (one, but it
lands 0.6-9 km from the cell), OFFGRID (one, whose control points miss the
printed graticule). `l7014_neatline.py` already finds a sheet's printed
neatline in pixels, for the JPG scans that have no georeference to trust in
the first place. The gap for these 74 PDFs is the same: their own
georeference is missing or wrong, but the printed neatline is still on the
page, and four detected corners plus the sheet's known 15' lattice cell is
enough to warp without it.

The honesty problem. Every GCP this script builds has the lattice cell as its
ground half -- the same source `l7014_hand.py.ground_quad` uses for the hand
sheets -- so a placed sheet's *outline* is the cell by construction. Running
`l7014_seams.py` against these sheets would measure nothing: the trap its own
docstring documents for the hand-to-mosaic seams (see REGEN.md "do not
reproduce"). What a bad neatline detection actually produces is the right
frame around content that is shifted or scaled *inside* it. So `seams` here
does not touch outlines at all -- it warps each candidate a second time
without cropping to the cell, so real content can fall on either side of the
shared edge with an already-placed neighbour, and cross-correlates a window
straddling that edge to find the pixel offset that best lines the two up.

    python3 scripts/l7014_autoplace.py sweep    # detect + classify -> regen/autoplace-detect.json, .csv
    python3 scripts/l7014_autoplace.py place    # warp what clears GATE_LOOSE -> cogs-auto/
    python3 scripts/l7014_autoplace.py seams    # pixel cross-correlation vs corrected neighbours
    python3 scripts/l7014_autoplace.py --self-check

Reads work/l7014/regen/warp-fixed.log for the 74 rejects (do not re-derive --
that log is the warp run's own record of why each one failed). Writes only to
work/l7014/regen/, work/l7014/cogs-auto/ and work/l7014/cogs-ref/ (a scratch
copy of the *corrected* warp for whichever neighbours `seams` needs -- the
real work/l7014/cogs/ currently holds the faulty-datum pass and is not
touched, per REGEN.md's own warning).
"""

import argparse
import concurrent.futures as cf
import json
import math
import re
import sys

from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

sys.path.insert(0, str(Path(__file__).parent))

import l7014_mosaic as M
from l7014_neatline import GATE, corners as detect_corners

CORNERS = M.CORNERS

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

WORK = Path("work/l7014")
REGEN = WORK / "regen"
COG_AUTO = WORK / "cogs-auto"       # the placement this script produces
COG_REF = WORK / "cogs-ref"         # scratch: corrected-warp neighbours, for `seams` only
COG_CHECK = WORK / "cogs-check"     # scratch: candidates warped *unclipped*, for `seams` only
DETECT_JSON = REGEN / "autoplace-detect.json"
SWEEP_CSV = REGEN / "autoplace-sweep.csv"
PLACED_JSON = REGEN / "autoplace-placed.json"
SEAMS_CSV = REGEN / "autoplace-seams.csv"
SUMMARY_JSON = REGEN / "autoplace-summary.json"

# Detection is run once, with a gate that accepts everything, so which of the
# two candidate lines wins a side is decided purely by fit quality (the
# `score` tuple's second term) and never by an accept/reject threshold that
# might change between experiments. GATE_DEFAULT and GATE_LOOSE are then
# applied after the fact to the same (residual, inliers, found) numbers --
# see cmd_sweep.
GATE_ACCEPT_ALL = {"residual": 1e9, "inliers": 0.0, "found": 0.0}
GATE_DEFAULT = GATE
# Measured, not guessed -- see AUTOPLACE.md "Choosing GATE_LOOSE" for the
# derivation. Restricting to the 196 edges with res < 2.0 (residual is not
# the problem, so it is left at the default's value) and splitting on the
# *other* two conditions individually rather than as one combined pass/fail
# finds a clean gap in each: inliers 0.193-0.230 (nothing in between, 43
# edges above it, 4 below) and found 0.427-0.632 (43 above, the same 4
# below). Both gates sit in the middle of their gap. The 4 left behind
# (inliers <=0.19, found <=0.43 on every one) are a qualitatively weaker
# population, not the near-miss one this gate exists to rescue.
GATE_LOOSE = {"residual": 2.0, "inliers": 0.20, "found": 0.45}

EDGE_SIDE_OF = {"NW": ("L", "T"), "NE": ("R", "T"), "SE": ("R", "B"), "SW": ("L", "B")}
# Buffer around a candidate's true cell, warped *without* a cutline, so real
# content that a bad affine pushed past the true neatline is still on the
# raster to be compared. Large enough to catch the fault this series
# actually has (hundreds of metres, per REGEN.md); small enough that the
# warp stays cheap.
CHECK_BUFFER_M = 600.0
SAMPLE_POINTS = 7
EDGE_MARGIN = 0.12        # keep samples off the corners, like l7014_seams.py
PASS_M = 25.0            # the series' own drafting accuracy


# ── shared geometry ─────────────────────────────────────────────────────────


def wgs84_srs():
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def merc_srs():
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3857)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


_TO_MERC = None


def to_merc(lon, lat):
    global _TO_MERC
    if _TO_MERC is None:
        _TO_MERC = osr.CoordinateTransformation(wgs84_srs(), merc_srs())
    x, y, _ = _TO_MERC.TransformPoint(lon, lat)
    return x, y


def merc_scale(lat):
    """Ground metres per Web Mercator map unit at this latitude.

    Web Mercator inflates ground distance by 1/cos(lat) to keep bearings
    correct, so a map-unit offset has to be scaled back down by cos(lat) to
    read as a real distance -- otherwise every seam in this series (5-16 N)
    would be reported 2-4% too big.
    """
    return math.cos(math.radians(lat))


def lattice_cells():
    return json.loads((WORK / "lattice.json").read_text())["cells"]


def unplaced_rows():
    """The 74 rejects, each with its sheets.json row (for the PDF path)."""
    log = (REGEN / "warp-fixed.log").read_text()
    reject = {m.group(2): m.group(1) for m in
               re.finditer(r"^  (NOGEO|OFFCELL|OFFGRID) (\S+): ", log, re.M)}
    by_stem = {Path(r["file"]).stem.strip(): r for r in M.load_sheets() if r["kind"] == "pdf"}
    out = []
    for stem, kind in reject.items():
        row = by_stem.get(stem)
        if row:
            out.append((row, kind))
    return out


def expect_aspect(sheet, cells):
    """Width/height the cell must have, from the lattice -- not the sheet's
    own XMP. These 74 are exactly the sheets whose self-reported geodata is
    missing or wrong, so the lattice is the only trustworthy source left, the
    same reasoning `pick_crs`/`lattice_error` already apply to the CRS choice."""
    pts = cells.get(sheet)
    if not pts:
        return None
    lat = sum(y for _, y in pts) / 4
    return math.cos(math.radians(lat)) * 111320 / 110540


# ── sweep: detect once, classify twice ──────────────────────────────────────


def _detect_one(args):
    row, reject = args
    pdf = WORK / "pdfs" / (Path(row["file"]).stem.strip() + ".pdf")
    cells = lattice_cells()
    if not pdf.exists():
        return row["sheet"], reject, {"error": "pdf missing"}
    try:
        got = detect_corners(pdf, expect_aspect(row["sheet"], cells), gate=GATE_ACCEPT_ALL)
    except Exception as e:  # noqa: BLE001
        return row["sheet"], reject, {"error": str(e)[:200]}
    if not got:
        return row["sheet"], reject, {"error": "no answer"}
    c, lines, W, H, (qok, why) = got
    return row["sheet"], reject, {
        "size": [W, H], "quad_ok": bool(qok), "quad_why": why,
        "corners": {k: [round(v["px"][0], 1), round(v["px"][1], 1)] for k, v in c.items()},
        "edges": {k: {"res": round(v["res"], 3), "inliers": round(v["inliers"], 3),
                      "found": round(v["found"], 3), "m": v["m"], "c": v["c"]}
                  for k, v in lines.items()},
    }


def edge_ok(e, gate):
    return e["res"] < gate["residual"] and e["inliers"] > gate["inliers"] and e["found"] > gate["found"]


def classify(rec, gate):
    """Which corners are usable under `gate`, given the (gate-independent)
    quad check already run. Mirrors corners()'s own rule: a corner needs both
    its edges, and a failed quad blanks every corner regardless of edge gate."""
    if "error" in rec or not rec["quad_ok"]:
        return {k: False for k in CORNERS}
    edges = rec["edges"]
    edge_pass = {k: edge_ok(edges[k], gate) for k in "LRTB"}
    return {k: all(edge_pass[s] for s in EDGE_SIDE_OF[k]) for k in CORNERS}


def cmd_sweep(args):
    rows = unplaced_rows()
    print(f"sweep: {len(rows)} unplaced sheets from {REGEN / 'warp-fixed.log'}")
    detect = {}
    # GDAL's PDF driver deadlocks when several workers render at once -- the
    # pool itself is fine, the driver is not. `--jobs 1` skips the pool rather
    # than working around the driver, and is also what makes a hang debuggable.
    runner = (map(_detect_one, rows) if args.jobs == 1
              else cf.ProcessPoolExecutor(max_workers=args.jobs).map(_detect_one, rows))
    if True:
        for sheet, reject, rec in runner:
            detect[sheet] = dict(rec, reject=reject)
            tag = "quad_ok" if rec.get("quad_ok") else rec.get("quad_why", rec.get("error", "?"))
            print(f"  {sheet:9s} {reject:8s} {tag}")

    DETECT_JSON.parent.mkdir(parents=True, exist_ok=True)
    DETECT_JSON.write_text(json.dumps(detect, indent=1))

    lines = ["sheet,reject,quad_ok,quad_why,default_corners,default_edges,loose_corners,loose_edges"]
    tally = {"quad_ok": 0, "default4": 0, "loose4": 0}
    by_reject = {}
    for sheet, rec in sorted(detect.items()):
        reject = rec["reject"]
        by_reject.setdefault(reject, {"n": 0, "quad_ok": 0, "default4": 0, "loose4": 0})
        by_reject[reject]["n"] += 1
        qok = rec.get("quad_ok", False)
        tally["quad_ok"] += qok
        by_reject[reject]["quad_ok"] += qok
        dflt = classify(rec, GATE_DEFAULT) if "error" not in rec else {k: False for k in CORNERS}
        loose = classify(rec, GATE_LOOSE) if "error" not in rec else {k: False for k in CORNERS}
        n_dflt, n_loose = sum(dflt.values()), sum(loose.values())
        tally["default4"] += n_dflt == 4
        tally["loose4"] += n_loose == 4
        by_reject[reject]["default4"] += n_dflt == 4
        by_reject[reject]["loose4"] += n_loose == 4
        edges = rec.get("edges", {})
        pat = lambda gate: "".join(s if ("error" not in rec and edge_ok(edges[s], gate)) else "."
                                    for s in "LRTB")
        lines.append(f"{sheet},{reject},{int(qok)},{rec.get('quad_why','')},"
                     f"{n_dflt},{pat(GATE_DEFAULT) if 'error' not in rec else '....'},"
                     f"{n_loose},{pat(GATE_LOOSE) if 'error' not in rec else '....'}")
    SWEEP_CSV.write_text("\n".join(lines) + "\n")

    print(f"\n{len(detect)} sheets -> {DETECT_JSON}, {SWEEP_CSV}")
    print(f"quad_ok: {tally['quad_ok']}   full 4/4 @ default gate: {tally['default4']}"
          f"   full 4/4 @ loose gate: {tally['loose4']}")
    for reject, t in sorted(by_reject.items()):
        print(f"  {reject:8s} n={t['n']:2d}  quad_ok={t['quad_ok']:2d}  "
              f"default4={t['default4']:2d}  loose4={t['loose4']:2d}")


# ── place: warp what clears the chosen gate ─────────────────────────────────


def build_gcps(sheet, corners_px, cells):
    ground = cells[sheet]  # NW NE SE SW, matches CORNERS order
    return [(corners_px[k][0], corners_px[k][1], ground[i][0], ground[i][1])
            for i, k in enumerate(CORNERS)]


def warp_affine(pdf, gcps, out, bounds=None, buffer_m=0.0):
    """Order-1 affine from four corners -- the same recipe `warp_pinned_one`
    uses for the hand-pinned JPGs, just sourced from the PDF's own raster
    instead of a scan. `bounds` (west,south,east,north in WGS84) with no
    cutline is the *check* warp: it lets real content fall outside the cell
    the GCPs claim, which is exactly what a bad detection would produce and a
    cutline would hide. Without `bounds` it crops to the ground quad, like
    every other sheet in the mosaic.
    """
    vrt = out.with_suffix(".src.vrt")
    flat = []
    for px, py, lon, lat in gcps:
        flat += ["-gcp", f"{px}", f"{py}", f"{lon}", f"{lat}"]
    import subprocess
    res = subprocess.run(["gdal_translate", "-of", "VRT", "-a_srs", "EPSG:4326",
                          *flat, str(pdf), str(vrt)], capture_output=True, text=True)
    if res.returncode:
        return "fail", f"translate: {res.stderr.strip()[-160:]}"

    cmd = ["gdalwarp", "-t_srs", "EPSG:3857", "-r", "cubic", "-dstalpha",
           "-order", "1", "-wo", "INIT_DEST=255,255,255,0",
           "-of", "GTiff", "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=2",
           "-co", "TILED=YES", "-multi", "-overwrite"]
    if bounds:
        w, s, e, n = bounds
        if buffer_m:
            dlon = buffer_m / (111320 * math.cos(math.radians((s + n) / 2)))
            dlat = buffer_m / 110540
            w, s, e, n = w - dlon, s - dlat, e + dlon, n + dlat
        (wx0, wy0), (wx1, wy1) = to_merc(w, s), to_merc(e, n)
        cmd += ["-te", f"{wx0}", f"{wy0}", f"{wx1}", f"{wy1}"]
    else:
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for lon, lat in [(gcps[i][2], gcps[i][3]) for i in (0, 1, 2, 3, 0)]:
            ring.AddPoint_2D(lon, lat)
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        cut = out.with_suffix(".cutline.gpkg")
        cut.unlink(missing_ok=True)
        srs = wgs84_srs()
        ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(cut))
        layer = ds.CreateLayer("cutline", srs, ogr.wkbPolygon)
        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetGeometry(poly)
        layer.CreateFeature(feat)
        ds = None
        cmd += ["-cutline", str(cut), "-cl", "cutline", "-crop_to_cutline"]
    cmd += [str(vrt), str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode:
        out.unlink(missing_ok=True)
        return "fail", f"warp: {res.stderr.strip()[-160:]}"
    return "ok", str(out)


def placeable_sheets(gate_name="loose"):
    detect = json.loads(DETECT_JSON.read_text())
    gate = {"default": GATE_DEFAULT, "loose": GATE_LOOSE}[gate_name]
    out = []
    for sheet, rec in detect.items():
        if "error" in rec:
            continue
        ok = classify(rec, gate)
        if all(ok.values()):
            out.append(sheet)
    return sorted(out)


def cmd_place(args):
    if not DETECT_JSON.exists():
        sys.exit(f"{DETECT_JSON} missing -- run `sweep` first")
    detect = json.loads(DETECT_JSON.read_text())
    cells = lattice_cells()
    rows = {r["sheet"]: r for r in M.load_sheets() if r["kind"] == "pdf"}
    candidates = placeable_sheets(args.gate)
    print(f"place: {len(candidates)} sheets clear quad_ok + 4/4 corners @ gate={args.gate}")

    COG_AUTO.mkdir(parents=True, exist_ok=True)
    COG_CHECK.mkdir(parents=True, exist_ok=True)
    placed = []
    for sheet in candidates:
        row = rows[sheet]
        stem = Path(row["file"]).stem.strip()
        pdf = WORK / "pdfs" / f"{stem}.pdf"
        gcps = build_gcps(sheet, detect[sheet]["corners"], cells)

        out = COG_AUTO / f"{stem}.tif"
        if not out.exists():
            status, msg = warp_affine(pdf, gcps, out)
            print(f"  {sheet:9s} place  {status:5s} {msg}")
            if status != "ok":
                continue
        else:
            print(f"  {sheet:9s} place  skip  already warped")

        chk = COG_CHECK / f"{stem}.tif"
        if not chk.exists():
            ground = cells[sheet]
            w = min(x for x, _ in ground); e = max(x for x, _ in ground)
            s_ = min(y for _, y in ground); n = max(y for _, y in ground)
            status, msg = warp_affine(pdf, gcps, chk, bounds=(w, s_, e, n), buffer_m=CHECK_BUFFER_M)
            print(f"  {sheet:9s} check  {status:5s} {msg}")
            if status != "ok":
                continue
        placed.append(sheet)

    PLACED_JSON.write_text(json.dumps({"gate": args.gate, "sheets": placed}, indent=1))
    print(f"\nplaced: {len(placed)} -> {COG_AUTO}/  (+ {COG_CHECK}/ for the seam check)")


# ── seams: cross-correlate content, not outlines ────────────────────────────


EDGES = (("N", 0, 1), ("E", 1, 2), ("S", 2, 3), ("W", 3, 0))


def edge_key(a, b):
    return tuple(sorted((tuple(round(v, 7) for v in a), tuple(round(v, 7) for v in b))))


def shared_edges(cells, present):
    by_edge = {}
    for sheet in sorted(present):
        pts = cells.get(sheet)
        if not pts:
            continue
        for side, i, j in EDGES:
            by_edge.setdefault(edge_key(pts[i], pts[j]), []).append((sheet, side, pts[i], pts[j]))
    for holders in by_edge.values():
        if len(holders) == 2:
            yield sorted(holders)


def ensure_neighbour_ref(sheet, kind):
    """The *corrected* warp of an already-placed neighbour, in cogs-ref/ --
    never cogs/, which currently holds the faulty-datum pass (REGEN.md).
    Reuses l7014_mosaic's own warp functions unmodified, just redirected."""
    rows = M.load_sheets()
    row = next((r for r in rows if r["sheet"] == sheet and r["kind"] == kind), None)
    if row is None:
        return None
    stem = Path(row["file"]).stem.strip()
    out = COG_REF / f"{stem}.tif"
    if out.exists():
        return out
    old_cog_dir = M.COG_DIR
    M.COG_DIR = COG_REF
    COG_REF.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "pdf":
            status, msg = M.warp_one(row)
        else:
            pins = json.loads(M.PINS.read_text()) if M.PINS.exists() else {}
            gcp = M.load_gcps(sheet, pins)
            if not gcp:
                return None
            status, msg = M.warp_pinned_one(row, gcp)
    finally:
        M.COG_DIR = old_cog_dir
    if status not in ("ok", "skip"):
        print(f"    neighbour {sheet} ({kind}): {status} {msg}")
        return None
    return out if out.exists() else None


# ── the first design, and why it was replaced ───────────────────────────────
#
# The first cut of this measurement cross-correlated a raw-grayscale window
# straddling the edge, candidate against neighbour, and searched a wide pixel
# range for the shift that maximised correlation. Run over the 26 real
# candidates it returned a "FAIL" on *every single edge*, at offsets that
# clustered suspiciously close to the search radius (SEARCH_M) rather than
# anywhere data-dependent. Diagnosis, on the worst case (6144-3/6144-2, a
# sheet with a clean quad and sub-pixel residuals on all four edges): at zero
# shift, with full valid overlap, the correlation was *negative* -- there was
# never a real signal to find. The reason is physical, not a threshold bug:
# a correctly warped candidate's buffer (see CHECK_BUFFER_M) is blank page
# margin, because the printed neatline genuinely is where the map content
# stops (confirmed by `l7014_neatline.py`'s own INSET measurement). Blank
# margin has no texture to correlate against the neighbour's real content at
# *any* shift, so normalized cross-correlation over a shrinking, noisy
# sample count did what it always does when there is no true peak: it
# reported the shift with the most overfit sample, which is the edge of the
# search window. Every "FAIL" was that artifact, not a placement fault.
#
# What actually has signal: not "does this pixel value match that one", but
# "where does each sheet's *own* real content stop". That is exactly what
# `l7014_neatline.py` already detects on the page -- so this reruns the same
# paper/content classification, not on the page, but on the warped output,
# in a strip straddling the shared cell edge. A correctly placed candidate's
# content should stop within noise of the lattice edge (normal-distance 0);
# a candidate whose neatline was detected on the wrong line -- the "right
# frame, shifted content" failure this whole script exists to catch --
# stops measurably short of or past it. The neighbour's own stopping point
# is read off its alpha channel instead of re-classifying its pixels: its
# raster is production-cropped to its own NEATLINE via `write_cutline`, so
# the alpha edge *is* its measured border, no reclassification needed.
PROFILE_SPAN_M = 250.0    # how far each profile reaches from the lattice edge
PROFILE_ALONG_M = 200.0   # the strip's width along the edge, averaged down to 1-D
PROFILE_RES_M = 3.0
RUN_BINS = 3               # consecutive bins a transition must hold, like crossings()'s RUN


def extract_profile(tif, x0, y0, ax, nx, res=PROFILE_RES_M):
    """RGB, alpha and each pixel's signed distance along `nx` from (x0, y0),
    for a strip PROFILE_ALONG_M wide (along `ax`) and 2*PROFILE_SPAN_M long
    (along `nx`), centred on the point -- the same window for every raster
    this is called on, so bin `i` means the same ground strip in both."""
    half_along = PROFILE_ALONG_M / 2
    corners_m = [(x0 + a * ax[0] + n * nx[0], y0 + a * ax[1] + n * nx[1])
                 for a in (-half_along, half_along) for n in (-PROFILE_SPAN_M, PROFILE_SPAN_M)]
    xs = [c[0] for c in corners_m]; ys = [c[1] for c in corners_m]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    ds = gdal.Warp("", str(tif), format="MEM", outputBounds=(minx, miny, maxx, maxy),
                   xRes=res, yRes=res, dstSRS="EPSG:3857", resampleAlg="bilinear")
    if ds is None or ds.RasterXSize < 4 or ds.RasterYSize < 4:
        return None
    arr = ds.ReadAsArray().astype(float)
    if arr.ndim != 3 or arr.shape[0] < 4:
        return None
    rgb, alpha = arr[:3].transpose(1, 2, 0), arr[3]
    h, w = alpha.shape
    gx, gy = np.meshgrid(np.linspace(minx + res / 2, maxx - res / 2, w),
                         np.linspace(maxy - res / 2, miny + res / 2, h))
    normal_dist = (gx - x0) * nx[0] + (gy - y0) * nx[1]
    return rgb, alpha, normal_dist


def binned_profile(signal, valid, normal_dist, res=PROFILE_RES_M, span=PROFILE_SPAN_M):
    """`signal` averaged into normal-distance bins, using only `valid` pixels
    -- one number per bin, however many along-edge rows/columns fed it."""
    bins = np.arange(-span, span + res, res)
    idx = np.digitize(normal_dist.ravel(), bins)
    centers = np.concatenate([[bins[0] - res / 2], (bins[:-1] + bins[1:]) / 2, [bins[-1] + res / 2]])
    prof = np.full(len(centers), np.nan)
    sig, val = signal.ravel(), valid.ravel()
    for i in range(len(centers)):
        sel = (idx == i) & val
        if sel.sum() > 3:
            prof[i] = sig[sel].mean()
    return centers, prof


def find_crossing(centers, prof, direction, threshold=0.5, run=RUN_BINS):
    """Sub-pixel normal-distance where `prof` drops below `threshold` and
    stays there for `run` consecutive (valid) bins, scanning from the end
    that starts high. `direction` +1 walks centers increasing (use when the
    trusted, high side is the near/negative end), -1 walks them decreasing.
    None if the profile never makes a sustained drop -- no edge is visible in
    this window at all, on this raster."""
    order = range(len(prof)) if direction > 0 else range(len(prof) - 1, -1, -1)
    order = [i for i in order if not np.isnan(prof[i])]
    streak, prev_above = [], None
    for i in order:
        if prof[i] < threshold:
            streak.append(i)
            if len(streak) >= run:
                if prev_above is None:
                    return centers[streak[0]]
                v0, v1 = prof[prev_above], prof[streak[0]]
                c0, c1 = centers[prev_above], centers[streak[0]]
                t = 0.5 if v1 == v0 else (threshold - v0) / (v1 - v0)
                return c0 + t * (c1 - c0)
        else:
            streak, prev_above = [], i
    return None


def measure_sample(cand_tif, ref_tif, point, normal, lat):
    """Ground-metre gap, along the shared edge's normal, between where the
    candidate's own printed content stops and where the neighbour's
    production crop already stops. ~0 for a correctly placed candidate; the
    detected-neatline error (scaled by the affine) otherwise. `normal` points
    from the candidate's cell into the neighbour's."""
    x0, y0 = to_merc(*point)
    ax = -normal[1], normal[0]
    al = math.hypot(*ax)
    ax = (ax[0] / al, ax[1] / al) if al else (1.0, 0.0)
    nl = math.hypot(*normal)
    nx = (normal[0] / nl, normal[1] / nl) if nl else (0.0, 1.0)

    cand = extract_profile(cand_tif, x0, y0, ax, nx)
    ref = extract_profile(ref_tif, x0, y0, ax, nx)
    if cand is None or ref is None:
        return None
    cand_rgb, cand_alpha, cand_nd = cand
    ref_rgb, ref_alpha, ref_nd = ref

    # The candidate has no cutline (COG_CHECK is unclipped), so its alpha is
    # opaque throughout -- "content" has to come from re-running the same
    # paper/colour/texture classification `l7014_neatline.py` uses on the
    # page, just aimed at the warped output instead.
    import l7014_neatline as N
    paper = N.paper_mask(cand_rgb)
    if paper is None:
        return None
    content = (N.colour_mask(cand_rgb) | N.busy_mask(cand_rgb)).astype(float)
    c_centers, c_prof = binned_profile(content, cand_alpha > 128, cand_nd)
    cand_edge = find_crossing(c_centers, c_prof, direction=+1)  # near (candidate interior) -> far

    # The neighbour *is* cutline-cropped, so its own border is already
    # exactly its alpha edge -- no reclassification needed or wanted.
    r_centers, r_prof = binned_profile((ref_alpha > 128).astype(float),
                                        np.ones_like(ref_alpha, bool), ref_nd)
    ref_edge = find_crossing(r_centers, r_prof, direction=-1)  # far (neighbour interior) -> near

    if cand_edge is None or ref_edge is None:
        return None
    offset = cand_edge - ref_edge
    return abs(offset) * merc_scale(lat), offset


def cmd_seams(args):
    if not PLACED_JSON.exists():
        sys.exit(f"{PLACED_JSON} missing -- run `place` first")
    placed_info = json.loads(PLACED_JSON.read_text())
    candidates = set(placed_info["sheets"])
    cells = lattice_cells()

    hand = json.loads((WORK / "build" / "l7014-fixed-hand.geojson").read_text())
    already = {f["properties"]["sheet"]: f["properties"]["kind"] for f in hand["features"]}
    print(f"seams: {len(candidates)} candidates against {len(already)} already-placed sheets")

    # Every candidate starts in `no_edge` and is promoted as evidence shows up,
    # so a sheet with nothing to test against is reported as unverified rather
    # than silently missing from the tally -- it is placed, not proven.
    no_edge = set(candidates)
    has_edge_no_signal = set()
    rows_out = []
    for a, b in shared_edges(cells, candidates | set(already)):
        sheet_a, side_a, start, end = a
        sheet_b, side_b, _, _ = b
        cand_is_a = sheet_a in candidates and sheet_b in already
        cand_is_b = sheet_b in candidates and sheet_a in already
        if not (cand_is_a or cand_is_b):
            continue  # candidate/candidate or already/already -- not this check
        cand, cand_side, neigh = (sheet_a, side_a, sheet_b) if cand_is_a else (sheet_b, side_b, sheet_a)
        no_edge.discard(cand)

        cand_row = next(r for r in M.load_sheets() if r["sheet"] == cand and r["kind"] == "pdf")
        cand_tif = COG_CHECK / f"{Path(cand_row['file']).stem.strip()}.tif"
        ref_tif = ensure_neighbour_ref(neigh, already[neigh])
        if not cand_tif.exists() or ref_tif is None:
            print(f"  SKIP {cand}/{neigh}: raster missing")
            has_edge_no_signal.add(cand)
            continue

        lat = (start[1] + end[1]) / 2
        # Outward normal for the candidate's side of this edge -- points from
        # its cell centre through the edge midpoint, into the neighbour.
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        c_pts = cells[cand]
        centroid = (sum(p[0] for p in c_pts) / 4, sum(p[1] for p in c_pts) / 4)
        mx0, my0 = to_merc(*mid); cx0, cy0 = to_merc(*centroid)
        normal = (mx0 - cx0, my0 - cy0)

        offsets = []
        for i in range(SAMPLE_POINTS):
            f = EDGE_MARGIN + (1 - 2 * EDGE_MARGIN) * i / (SAMPLE_POINTS - 1)
            pt = (start[0] + f * (end[0] - start[0]), start[1] + f * (end[1] - start[1]))
            m = measure_sample(cand_tif, ref_tif, pt, normal, lat)
            if m:
                offsets.append(m)
        if not offsets:
            print(f"  {cand} / {neigh} ({cand_side}): no signal (no usable content near the seam)")
            rows_out.append((cand, neigh, cand_side, "", "", 0))
            has_edge_no_signal.add(cand)
            continue
        offs = sorted(o[0] for o in offsets)
        median = offs[len(offs) // 2]
        verdict = "PASS" if median < PASS_M else "FAIL"
        print(f"  {cand} / {neigh} ({cand_side}): median {median:6.1f} m over {len(offsets)} samples  {verdict}")
        rows_out.append((cand, neigh, cand_side, f"{median:.1f}", ",".join(f"{o[0]:.1f}" for o in offsets), len(offsets)))
        has_edge_no_signal.discard(cand)  # at least one edge on this sheet did measure

    with SEAMS_CSV.open("w") as fh:
        fh.write("candidate,neighbour,edge,median_m,samples_m,n\n")
        for r in rows_out:
            fh.write(",".join(str(x) for x in r) + "\n")

    measured = [r for r in rows_out if r[3]]
    passed = [r for r in measured if float(r[3]) < PASS_M]
    failed = [r for r in measured if float(r[3]) >= PASS_M]
    measured_candidates = {r[0] for r in measured}
    failed_candidates = {r[0] for r in failed}
    # A candidate counts as verified-pass only if EVERY edge measured against
    # it passed -- one bad seam is enough to withhold the sheet, the same way
    # one bad edge withholds a corner in `classify`.
    pass_candidates = measured_candidates - failed_candidates
    unverified = no_edge | (has_edge_no_signal - measured_candidates)

    print(f"\n{len(rows_out)} candidate/neighbour edges, {len(measured)} measured "
          f"({len(passed)} pass, {len(failed)} fail) -> {SEAMS_CSV}")
    print(f"candidates: {len(candidates)} placed, {len(pass_candidates)} verified <{PASS_M:.0f} m "
          f"on every measured edge, {len(failed_candidates)} fail at least one edge, "
          f"{len(unverified)} unverified (no already-placed neighbour, or no usable content at the ones it has)")
    if no_edge:
        print(f"  no shared edge with any already-placed sheet: {sorted(no_edge)}")
    if has_edge_no_signal - measured_candidates - no_edge:
        print(f"  had a neighbour but no usable content at any shared edge: "
              f"{sorted(has_edge_no_signal - measured_candidates - no_edge)}")
    if failed_candidates:
        print("  failing: " + ", ".join(f"{r[0]}/{r[1]} {r[3]}m ({r[2]})" for r in failed))

    SUMMARY_JSON.write_text(json.dumps({
        "candidates": sorted(candidates), "pass": sorted(pass_candidates),
        "fail": sorted(failed_candidates), "unverified": sorted(unverified),
    }, indent=1))


# ── self-check ───────────────────────────────────────────────────────────────


def self_check():
    # shared_edges: two adjacent synthetic cells share exactly one edge.
    cells = {"A": [[106.0, 10.1], [106.1, 10.1], [106.1, 10.0], [106.0, 10.0]],
             "B": [[106.1, 10.1], [106.2, 10.1], [106.2, 10.0], [106.1, 10.0]],
             "C": [[106.0, 10.0], [106.1, 10.0], [106.1, 9.9], [106.0, 9.9]]}
    pairs = list(shared_edges(cells, {"A", "B", "C"}))
    assert len(pairs) == 2, pairs
    got_sheets = {tuple(sorted((p[0][0], p[1][0]))) for p in pairs}
    assert got_sheets == {("A", "B"), ("A", "C")}, got_sheets
    print("self-check: shared_edges finds A/B and A/C, not B/C (not adjacent)")

    # classify: a failed quad blanks every corner even if edges look fine;
    # a passed quad needs both edges of a corner to individually clear the gate.
    good_edge = {"res": 0.3, "inliers": 0.9, "found": 0.9}
    # Tiny residual, thin evidence: below GATE_DEFAULT's 0.55/0.60 but above
    # GATE_LOOSE's 0.20/0.45 -- exactly the population the loosened gate exists for.
    bad_edge = {"res": 0.3, "inliers": 0.35, "found": 0.50}
    rec_fail_quad = {"quad_ok": False, "edges": {s: good_edge for s in "LRTB"}}
    assert classify(rec_fail_quad, GATE_DEFAULT) == {k: False for k in CORNERS}
    rec_mixed = {"quad_ok": True, "edges": {"L": good_edge, "R": good_edge,
                                            "T": bad_edge, "B": good_edge}}
    c = classify(rec_mixed, GATE_DEFAULT)
    # T is bad: it touches NW and NE (EDGE_SIDE_OF), not SE or SW.
    assert c == {"NW": False, "NE": False, "SE": True, "SW": True}, c
    c_loose = classify(rec_mixed, GATE_LOOSE)
    assert c_loose == {k: True for k in CORNERS}, c_loose
    print("self-check: classify blanks a failed quad; a loose gate admits a thin-evidence "
          "edge a tight one rejects, without touching residual")

    # merc_scale: a degree of longitude near the equator should read close to
    # 111.32 km once the projection's own inflation is divided back out.
    lat = 10.0
    x0, _ = to_merc(106.0, lat)
    x1, _ = to_merc(107.0, lat)
    ground_km = (x1 - x0) * merc_scale(lat) / 1000
    assert abs(ground_km - 111.32 * math.cos(math.radians(lat))) < 0.5, ground_km
    print(f"self-check: 1 deg longitude at {lat} N reads back as {ground_km:.2f} km "
          "after the Mercator scale correction")

    # find_crossing: a clean step function's crossing is recovered exactly,
    # regardless of scan direction, and a run of one noisy bin below
    # threshold does not fire it early (the RUN_BINS guard).
    centers = np.arange(-30, 30, 3.0) + 1.5
    prof = np.where(centers < 9.0, 1.0, 0.0)  # high near end, true crossing at 9.0
    assert abs(find_crossing(centers, prof, direction=+1) - 9.0) < 1e-9
    prof_far = np.where(centers > -9.0, 1.0, 0.0)  # high far end, true crossing at -9.0
    assert abs(find_crossing(centers, prof_far, direction=-1) - (-9.0)) < 1e-9
    noisy = prof.copy()
    noisy[len(noisy) // 4] = 0.0  # one early low bin, deep in the "high" region
    assert find_crossing(centers, noisy, direction=+1) is not None
    assert abs(find_crossing(centers, noisy, direction=+1) - 9.0) < 1e-9, \
        "one noisy bin should not move the crossing"
    flat = np.ones_like(prof)
    assert find_crossing(centers, flat, direction=+1) is None, "no drop, no crossing"
    print("self-check: find_crossing recovers a step's true position from either "
          "direction, and a lone noisy bin doesn't move it")

    # binned_profile: pixels bucket by their normal-distance, and an invalid
    # pixel is excluded from its bin's mean. 6 samples in each of two bins --
    # binned_profile requires more than 3 valid samples before it trusts a bin.
    nd = np.array([[-5.0] * 6, [5.0] * 6])
    signal = np.array([[1.0] * 5 + [999.0], [0.0] * 5 + [999.0]])
    valid = np.array([[True] * 5 + [False], [True] * 5 + [False]])
    c, p = binned_profile(signal, valid, nd, res=10.0, span=10.0)
    near_bin = int(np.argmin(np.abs(c - -5.0)))
    far_bin = int(np.argmin(np.abs(c - 5.0)))
    assert abs(p[near_bin] - 1.0) < 1e-9, p  # the masked 999.0 must not pull this up
    assert abs(p[far_bin] - 0.0) < 1e-9, p
    print("self-check: binned_profile buckets by normal-distance and honours the valid mask")

    print("self-check: ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", nargs="?", default="sweep",
                        choices=["sweep", "place", "seams"])
    parser.add_argument("--gate", default="loose", choices=["default", "loose"])
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    {"sweep": cmd_sweep, "place": cmd_place, "seams": cmd_seams}[args.cmd](args)


if __name__ == "__main__":
    main()
