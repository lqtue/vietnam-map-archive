#!/usr/bin/env python3
"""Read series 561's own printed frame against its per-record CartoMundi extent.

Only `annotate --apply` writes to the database; calibration and placement keep
local JSON records. No command publishes a map.

Run with the OCR virtualenv (google-genai is installed there):

    work/ocr/.venv/bin/python scripts/indochine100k_georef.py calibrate --count 12
    work/ocr/.venv/bin/python scripts/indochine100k_georef.py place <map-id>
    work/ocr/.venv/bin/python scripts/indochine100k_georef.py check
    work/ocr/.venv/bin/python scripts/indochine100k_georef.py annotate

`annotate --apply` is draft-only and requires an accepted calibration and a
clean lattice check. The first series-wide calibration failed those gates; see
docs/journals/260923-indochine100k-georef.md.
"""
import argparse
import hashlib
import json
import math
import os
import pickle
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "work/ocr/scripts"))
import iiif_tiles as T  # noqa: E402

WORK = Path("work/indochine-100k")
SOURCE = WORK / "sources/serie-561.json"
OFFSET_FILE = WORK / "catalogue-offset.json"
OBS_FILE = WORK / "calibration-observations.json"
REPORT_FILE = WORK / "calibration-report.json"
FIT_FILE = WORK / "calibration-fit.json"
CAL_VERSION = 1
# Increment when detection changes so place() revisits saved local placements.
DETECT_VERSION = 4
COLLECTION = "Indochine 1:100,000 — 2nd édition SGI (1947–1959)"
OV, PATCHES, SPAN = 1800, 24, (0.12, 0.88)
ACROSS, MAXIN, MINGAP, LIM, TRIM = (190, 300), 250, 10, 34, 3.0
# The overview peak already locates the thick frame line closely. A wider search
# can lock onto a neighbouring graticule/rim line 20-30 px away, making a sound
# rim appear to have an anomalous offset (Gia Ray, Kratié, Hà Giang).
NEAR, RESIDUAL = 12, 15.0
GRADE, PARIS = 0.9, 2.337229166666667
BUCKET = "annotations"
CORNERS = ("NW", "NE", "SE", "SW")
# This sheet's printed ticks were plausible but 741.5 m off the accepted
# latitude fit. Geometry alone cannot establish its geographic placement.
CALIBRATION_HOLDS = {
    "1f025a9f-ea9e-4816-ad35-edfba60bf518": "excluded calibration outlier; offset unverified",
    # Detects cleanly on every per-sheet gate; only check()'s cross-sheet series
    # median catches it. That check is stateful (it compares against whichever
    # sheets are currently placed), so a hold that lives only in check()'s
    # output does not survive a DETECT_VERSION bump -- place() just regenerates
    # a fresh, locally-clean JSON. Recorded here so it can't be silently wiped
    # again (2026-09-24: DETECT_VERSION 3->4 did exactly that).
    "7d1e6918-25a0-481b-b798-04b8df15aa57": "Pursat (E): rim offsets agree with each other but differ >15% from series median; different frame convention, unverified",
}

def darkness(img):
    return 255.0 - np.asarray(img.convert("L"), dtype=float)


def fit(points):
    """Least squares with the outliers trimmed away -- the part that matters."""
    if len(points) < max(6, PATCHES // 3):
        return None
    a = np.array([p[0] for p in points], float)
    b = np.array([p[1] for p in points], float)
    keep = np.ones(len(a), bool)
    for _ in range(8):
        m, c = np.polyfit(a[keep], b[keep], 1)
        r = np.abs(b - (m * a + c))
        med = float(np.median(r[keep])) or 1.0
        new = r < max(1.5, TRIM * med)
        if new.sum() < 5 or (new == keep).all():
            keep = new
            break
        keep = new
    m, c = np.polyfit(a[keep], b[keep], 1)
    res = float(np.median(np.abs(b[keep] - (m * a[keep] + c))))
    return float(m), float(c), res, int(keep.sum()), len(a)


def rim_in(p, thick, which):
    """Where the rim pair sits in an averaged, de-tilted cross-profile.

    Reading inward from the thick outer line the profile goes: a thin companion
    line, blank paper, the graticule band, a wider run of blank paper, the rim
    pair, then map content that never falls back to paper level. The second blank
    run is the landmark, and it is the *innermost* one -- the band is what a walk
    in from the paper margin finds first, and it is 40 px out, which is 170 m on
    the ground.

    Of the pair it is the inner line that bounds the mapped quadrangle. That is
    not a reading of the print but a measurement: on Nhu Trac the inner line puts
    the two axes' ground scales within 0.03% of each other (4.2595 against 4.2582
    m/px) and the outer line within 0.23%. Eight times better, on a sheet whose
    corner coordinates are known independently.
    """
    # Paper level from inside the window, not from the whole strip. Some scans
    # carry the scanner's own white background past the edge of the sheet, and a
    # low percentile over the strip then returns 0 rather than the tone of the
    # paper -- which puts the threshold below the margin itself, finds no blank
    # run anywhere, and reports a sheet with no rim. (Cam Ly, 1907.)
    hi = min(len(p), thick + MAXIN)
    paper = float(np.percentile(p[thick:hi], 25))
    thr = paper + max(6.0, 0.06 * (float(p.max()) - paper))
    gap, run, start = None, 0, None
    for i in range(thick, hi):
        if p[i] < thr:
            start = i if run == 0 else start
            run += 1
        else:
            if run >= MINGAP:
                gap = start + run
            run = 0
    if gap is None:
        return None
    lo, hi2 = gap, min(len(p), gap + LIM)
    if hi2 - lo < 4:
        return None
    # Peaks are picked on the whole profile, not on the window, so that a line
    # sitting at the window's first sample still has blank paper on its outer side
    # to be measured against. Prominence, not height: map content just inside the
    # rim sits well above paper and drifts, but it does not rise and fall in ten
    # pixels.
    floor = max(8.0, 0.25 * (float(p[lo:hi2].max()) - paper))
    picked = []
    for j in range(max(1, lo), min(len(p) - 1, hi2)):
        if not (p[j] >= p[j - 1] and p[j] > p[j + 1]):
            continue
        u, v = max(0, j - 10), min(len(p), j + 11)
        if p[j] - max(p[u:j + 1].min(), p[j:v].min()) >= floor:
            picked.append(j)
    if not picked:
        return None
    j = picked[-1] if which == "inner" else picked[0]
    u = v = j
    while u > 0 and p[u - 1] > thr and p[u - 1] <= p[u]:
        u -= 1
    while v < len(p) - 1 and p[v + 1] > thr and p[v + 1] <= p[v]:
        v += 1
    w = p[u:v + 1] - thr
    if w.sum() <= 0:
        return None
    return u + float((np.arange(len(w)) * w).sum() / w.sum())


def quad(c):
    P = c["corners"]
    top, bot = math.dist(P["NW"], P["NE"]), math.dist(P["SW"], P["SE"])
    lft, rgt = math.dist(P["NW"], P["SW"]), math.dist(P["NE"], P["SE"])
    d1, d2 = math.dist(P["NW"], P["SE"]), math.dist(P["NE"], P["SW"])
    return {"w": (top + bot) / 2, "h": (lft + rgt) / 2,
            "opp_x": abs(top - bot) / max(top, bot),
            "opp_y": abs(lft - rgt) / max(lft, rgt),
            "diag": abs(d1 - d2) / max(d1, d2),
            "aspect": ((top + bot) / 2) / ((lft + rgt) / 2)}


WGS84_A = 6378137.0
WGS84_E2 = 1 - (6356752.314245 / WGS84_A) ** 2


def metres_per_degree(lat):
    """Parallel and meridian scale on the WGS 84 ellipsoid."""
    p = math.radians(lat)
    q = 1 - WGS84_E2 * math.sin(p) ** 2
    return (math.pi / 180 * WGS84_A * math.cos(p) / math.sqrt(q),
            math.pi / 180 * WGS84_A * (1 - WGS84_E2) / q ** 1.5)


def north_metres(lat0, lat1):
    """Meridian arc via Simpson integration; checked against Geod to <1 mm."""
    mid = (lat0 + lat1) / 2
    return abs(lat1 - lat0) * (metres_per_degree(lat0)[1] +
                              4 * metres_per_degree(mid)[1] +
                              metres_per_degree(lat1)[1]) / 6


def ground(lon0, lat0, lon1, lat1):
    north = abs(lon1 - lon0) * metres_per_degree(lat0)[0]
    south = abs(lon1 - lon0) * metres_per_degree(lat1)[0]
    return (north + south) / 2, north_metres(lat0, lat1)


def annotation(iiif, w, h, got):
    """One georeference annotation, in the shape the Allmaps renderer reads.

    Same shape `scripts/l7014_annotate.py` writes, and for the same two reasons.
    The transformation is a first-order polynomial, not a projective: four corners
    fit a projective *exactly*, so a pixel of detection error would be reproduced
    faithfully as perspective instead of averaged away, and these sheets were
    measured as having no perspective to recover -- the rigid-rotation fit makes
    opposite edges agree by construction. And the mask is the rim quad, which is
    what stops the paper margin, the title block and the legend being painted over
    the neighbouring sheets.
    """
    px = {c: [round(got["corners"][c][0]), round(got["corners"][c][1])] for c in CORNERS}
    poly = " ".join(f"{px[c][0]},{px[c][1]}" for c in CORNERS)
    return {
        "type": "AnnotationPage",
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "items": [{
            "id": f"{iiif}/annotation",
            "type": "Annotation",
            "@context": [
                "http://iiif.io/api/extension/georef/1/context.json",
                "http://iiif.io/api/presentation/3/context.json",
            ],
            "motivation": "georeferencing",
            "target": {
                "type": "SpecificResource",
                "source": {"id": iiif, "type": "ImageService3", "width": w, "height": h},
                "selector": {"type": "SvgSelector",
                             "value": f'<svg width="{w}" height="{h}">'
                                      f'<polygon points="{poly}" /></svg>'},
            },
            "body": {
                "type": "FeatureCollection",
                "transformation": {"type": "polynomial", "options": {"order": 1}},
                "features": [
                    {"type": "Feature",
                     "properties": {"resourceCoords": px[c]},
                     "geometry": {"type": "Point",
                                  "coordinates": [round(got["wgs84"][c][0], 7),
                                                  round(got["wgs84"][c][1], 7)]}}
                    for c in CORNERS
                ],
            },
        }],
    }



def cached_crop(base, x, y, w, h, size):
    """Keep expensive IIIF strips reusable across calibration attempts."""
    cache = WORK / ".fetch_cache"
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{base}|{x}|{y}|{w}|{h}|{size}".encode()).hexdigest()
    path = cache / f"{key}.pkl"
    if path.exists():
        with path.open("rb") as f:
            image, stats = pickle.load(f)
        if stats.get("coverage") == 1:
            return image
    stats = {}
    image = T.fetch_crop_level0(base, x, y, w, h, size, stats=stats, max_workers=4)
    if stats.get("coverage") != 1:
        raise RuntimeError(f"crop has incomplete tile coverage: {base} {stats}")
    with path.open("wb") as f:
        pickle.dump((image, stats), f)
    return image


def frame(base, W, H):
    # Only the central cross contributes to these profiles. Fetching a whole
    # overview assembled ~150 IIIF tiles per sheet, then discarded most of it.
    # Both bands use the same pyramid level and rendered scale as that overview.
    overview_h = round(OV * H / W)
    x0 = round(int(OV * .46) * W / OV)
    x1 = round(int(OV * .54) * W / OV)
    y0 = round(int(overview_h * .46) * H / overview_h)
    y1 = round(int(overview_h * .54) * H / overview_h)
    with ThreadPoolExecutor(max_workers=2) as pool:
        horizontal = pool.submit(cached_crop, base, 0, y0, W, y1 - y0, OV)
        vertical = pool.submit(cached_crop, base, x0, 0, x1 - x0, H,
                               round(OV * (x1 - x0) / W))
        cols = darkness(horizontal.result()).mean(axis=0)
        vertical_img = vertical.result()
    # The narrow crop's rounded width can resize to a slightly different
    # height than the old whole-image overview. Align it before finding peaks.
    vertical_img = vertical_img.resize((vertical_img.width, overview_h), Image.Resampling.LANCZOS)
    rows = darkness(vertical_img).mean(axis=1)

    def ambiguous(profile, side):
        third = len(profile) // 3
        seg = profile[:third] if side == "T" else profile[-third:]
        strongest = int(np.argmax(seg))
        others = seg.copy()
        others[max(0, strongest - 12):min(len(seg), strongest + 13)] = -1
        return (seg[strongest] - others.max()) / max(seg[strongest], 1) < .07

    # On some scans two dark horizontal rules are nearly tied. A narrow crop
    # can reverse their order by a few grey levels; use the original overview
    # for those sheets rather than risking a different frame line.
    if ambiguous(rows, "T") or ambiguous(rows, "B"):
        full = darkness(cached_crop(base, 0, 0, W, H, OV))
        fh, fw = full.shape
        cols = full[int(fh * .46):int(fh * .54)].mean(axis=0)
        rows = full[:, int(fw * .46):int(fw * .54)].mean(axis=1)
    def alt_peak(seg, from_edge):
        """The next-outermost rule nearly as dark as the strongest one, if any.

        Used only as a fallback when the strongest peak turns out not to be the
        neatline: a bolder inner rim line can outscore a thinner outer frame
        line (Russey Chrum (E), Kompong Chhnang (W)), leaving nothing further
        inward for rim_in to find. Never used as the primary pick -- a comparably
        dark feature nearer the paper edge is at least as often a scanner
        background/mount artefact (Attopeu (E), Vinh (W) and 70 others regressed
        when this ran unconditionally), and those already succeed under argmax.
        """
        order = seg if from_edge else seg[::-1]
        strongest = int(np.argmax(order))
        baseline = float(np.percentile(order, 25))
        near = baseline + 0.85 * max(1.0, float(order[strongest]) - baseline)
        for i in range(1, strongest - 5):
            if order[i] >= near and order[i] >= order[i - 1] and order[i] >= order[i + 1]:
                return i if from_edge else len(seg) - 1 - i
        return None

    out = {}
    for side, prof, n, scale in (("L", cols, len(cols), W / len(cols)),
                                 ("R", cols, len(cols), W / len(cols)),
                                 ("T", rows, len(rows), H / len(rows)),
                                 ("B", rows, len(rows), H / len(rows))):
        third = n // 3
        seg = prof[:third] if side in "LT" else prof[-third:]
        strongest = int(np.argmax(seg))
        alt = alt_peak(seg, side in "LT")
        out[side] = (strongest + (0 if side in "LT" else n - third)) * scale
        if alt is not None:
            out[side + "_alt"] = (alt + (0 if side in "LT" else n - third)) * scale
    return out


def frame_strip(base, side, rough, W, H, full_along=False):
    c = rough[side]
    if side in "LR":
        a0, a1 = (0, H) if full_along else (int(H * SPAN[0]), int(H * SPAN[1]))
        x0 = max(0, int(c - (ACROSS[0] if side == "L" else ACROSS[1])))
        x1 = min(W, int(c + (ACROSS[1] if side == "L" else ACROSS[0])))
        d = darkness(cached_crop(base, x0, a0, x1 - x0, a1 - a0, x1 - x0))
        origin, step = (x0, 1) if side == "L" else (x1 - 1, -1)
    else:
        a0, a1 = (0, W) if full_along else (int(W * SPAN[0]), int(W * SPAN[1]))
        y0 = max(0, int(c - (ACROSS[0] if side == "T" else ACROSS[1])))
        y1 = min(H, int(c + (ACROSS[1] if side == "T" else ACROSS[0])))
        d = darkness(cached_crop(base, a0, y0, a1 - a0, y1 - y0, a1 - a0)).T
        origin, step = (y0, 1) if side == "T" else (y1 - 1, -1)
    return (d if step > 0 else d[:, ::-1]), origin, step, a0


def rim_relaxed(p, thick):
    hi = min(len(p), thick + MAXIN)
    paper = float(np.percentile(p[thick:hi], 25))
    thr = paper + max(6.0, 0.06 * (float(p.max()) - paper))
    gap, run, start = None, 0, None
    for i in range(thick, hi):
        if p[i] < thr:
            start = i if run == 0 else start
            run += 1
        else:
            if run >= MINGAP:
                gap = start + run
            run = 0
    if gap is None:
        return None
    lo, hi2 = gap, min(len(p), gap + LIM)
    if hi2 - lo < 4:
        return None
    floor = max(5.0, 0.12 * (float(p[lo:hi2].max()) - paper))
    picked = []
    for j in range(max(1, lo), min(len(p) - 1, hi2)):
        if p[j] >= p[j - 1] and p[j] > p[j + 1]:
            u, v = max(0, j - 10), min(len(p), j + 11)
            if p[j] - max(p[u:j + 1].min(), p[j:v].min()) >= floor:
                picked.append(j)
    if not picked:
        return None
    j = picked[-1]
    u = v = j
    while u > 0 and p[u - 1] > thr and p[u - 1] <= p[u]:
        u -= 1
    while v < len(p) - 1 and p[v + 1] > thr and p[v + 1] <= p[v]:
        v += 1
    weights = p[u:v + 1] - thr
    return u + float((np.arange(len(weights)) * weights).sum() / weights.sum()) if weights.sum() > 0 else None


def side_line(d, ref):
    edges = np.linspace(0, d.shape[0], PATCHES + 1).round().astype(int)
    patches = [((lo + hi) / 2, d[lo:hi].mean(axis=0)) for lo, hi in zip(edges, edges[1:]) if hi - lo >= 8]
    if len(patches) < 6:
        return None, "too few patches"
    lo, hi = max(0, int(ref) - NEAR), min(d.shape[1], int(ref) + NEAR)
    if hi <= lo:
        return None, "rough frame outside strip"
    consensus = lo + int(np.argmax(np.mean([p for _, p in patches], axis=0)[lo:hi]))
    def pick(prof, centre, width):
        a, b = max(0, int(centre - width)), min(len(prof), int(centre + width) + 1)
        return a + int(np.argmax(prof[a:b]))
    fitted = fit([(mid, float(pick(p, consensus, 12))) for mid, p in patches])
    if fitted is None:
        return None, "thick line would not fit"
    m, c, *_ = fitted
    fitted = fit([(mid, float(pick(p, m * mid + c, 8))) for mid, p in patches])
    if fitted is None:
        return None, "thick line would not refine"
    m, c, residual, kept, found = fitted
    if residual > RESIDUAL:
        return None, f"thick line residual {residual:.1f}px"
    anchor = float(np.mean([mid for mid, _ in patches]))
    ref2 = m * anchor + c
    grid = np.arange(d.shape[1], dtype=float)
    avg = np.mean([np.interp(grid, grid + (ref2 - (m * mid + c)), p) for mid, p in patches], axis=0)
    rim = rim_in(avg, int(round(ref2)), "inner")
    relaxed = rim is None
    if relaxed:
        rim = rim_relaxed(avg, int(round(ref2)))
    if rim is None:
        return None, "no rim found inside the thick line"
    return {"m": m, "c": c + rim - ref2, "res": residual, "kept": kept,
            "found": found, "offset": rim - ref2, "relaxed": relaxed}, None


# Frame-to-rim distance as a fraction of image height, pooled over every side
# NOT reached via the alt retry below (636 sides, 170 sheets that independently
# cleared every gate). min 0.0213, max 0.0262, median 0.0230, std 0.0006 -- a
# real printed-margin constant across the series, not a per-sheet fit. A side
# that lands outside this band picked the wrong line, not a differently-scaled
# rim (see its use in detect()).
RETRY_BAND = (0.019, 0.028)


def detect(base, W, H, verbose=False):
    rough = frame(base, W, H)
    lines = {}
    # Edge strips are independent IIIF tile sets; fetch them concurrently.
    with ThreadPoolExecutor(max_workers=4) as pool:
        strips = dict(zip("LRTB", pool.map(lambda side: frame_strip(base, side, rough, W, H), "LRTB")))
    for side in "LRTB":
        d, origin, step, a0 = strips[side]
        ref = (rough[side] - origin) * step
        got, err = side_line(d, ref)
        # Retried whenever the primary pick is suspect: it failed outright, its
        # offset falls outside RETRY_BAND (frame() locked onto the rim itself,
        # as on Russey Chrum (E)), or the rim search only found something via
        # rim_relaxed. A side that is already a clean, in-band, non-relaxed hit
        # never reaches this branch, so it cannot regress a sheet that already
        # places correctly.
        suspect = err is not None or got["relaxed"] or not (RETRY_BAND[0] <= got["offset"] / H <= RETRY_BAND[1])
        if suspect and f"{side}_alt" in rough:
            alt_val = rough[f"{side}_alt"]
            alt_ref = (alt_val - origin) * step
            if 0 <= alt_ref < d.shape[1]:
                alt_d, alt_origin, alt_step, alt_a0 = d, origin, step, a0
            else:
                # The alt peak can sit outside the strip already fetched for the
                # primary guess (Hon Quan (E), Kompong Chhnang (W)); fetch a strip
                # centred on it instead of silently skipping the retry.
                alt_d, alt_origin, alt_step, alt_a0 = frame_strip(
                    base, side, {**rough, side: alt_val}, W, H)
                alt_ref = (alt_val - alt_origin) * alt_step
            alt_got, alt_err = side_line(alt_d, alt_ref)
            if (alt_err is None and not alt_got["relaxed"]
                    and RETRY_BAND[0] <= alt_got["offset"] / H <= RETRY_BAND[1]):
                got, err, d, origin, step, a0 = alt_got, None, alt_d, alt_origin, alt_step, alt_a0
                got["alt"] = True
        if err:
            return None, f"{side}: {err}"
        got.setdefault("alt", False)
        m = got["m"] * step
        c = origin + step * (got["c"] - got["m"] * a0)
        mid = (H if side in "LR" else W) * sum(SPAN) / 2
        lines[side] = {**got, "m": m, "c": c, "anchor": [mid, m * mid + c]}
        if verbose:
            print(f"  {side}: offset {got['offset']:.1f}px, residual {got['res']:.1f}px, {got['kept']}/{got['found']}"
                  f" patches{' (alt)' if got['alt'] else ''}")
    ordinary = [v["offset"] for v in lines.values() if not v["relaxed"]]
    for side, v in lines.items():
        if v["relaxed"] and ordinary and abs(v["offset"] - float(np.median(ordinary))) > 5:
            return None, f"{side}: relaxed rim disagrees with ordinary sides"
    tan = float(np.mean([lines["T"]["m"], lines["B"]["m"], -lines["L"]["m"], -lines["R"]["m"]]))
    for side in "LRTB":
        m = -tan if side in "LR" else tan
        ax, ay = lines[side]["anchor"]
        lines[side]["m"], lines[side]["c"] = m, ay - m * ax
    def cross(v, hz):
        V, Z = lines[v], lines[hz]
        y = (Z["m"] * V["c"] + Z["c"]) / (1 - Z["m"] * V["m"])
        return [V["m"] * y + V["c"], y]
    corners = {k: cross(*sides) for k, sides in (("NW", ("L", "T")), ("NE", ("R", "T")),
                                                   ("SE", ("R", "B")), ("SW", ("L", "B")))}
    return {"corners": corners, "lines": lines, "rotation": tan}, None

def unimarc(value):
    m = re.fullmatch(r"([nsew])(\d{3})(\d{2})(\d{2})", str(value or "").strip(), re.I)
    if not m:
        return None
    deg = int(m[2]) + int(m[3]) / 60 + int(m[4]) / 3600
    return -deg if m[1].lower() in "sw" else deg


def catalogue():
    by_fkey = {}
    for records in json.loads(SOURCE.read_text())["cells"].values():
        for rec in records:
            key = str(rec["fkey"])
            if key in by_fkey:
                raise ValueError(f"duplicate CartoMundi fkey {key}")
            by_fkey[key] = rec
    return by_fkey


def record_box(row, records):
    """Use this maps row's fkey, never the unioned series_sheets bbox."""
    meta = row.get("extra_metadata") or {}
    keys = meta.get("cartomundi_fkeys") or []
    if len(keys) != 1:
        return None, "expected exactly one CartoMundi fkey"
    rec = records.get(str(keys[0]))
    if rec is None:
        return None, f"fkey {keys[0]} absent from serie 561"
    u = rec.get("unimarc") or {}
    vals = {side: unimarc(u.get(side)) for side in "wens"}
    if any(v is None for v in vals.values()):
        return None, f"fkey {keys[0]} has incomplete UNIMARC corners"
    box = {"west": vals["w"], "east": vals["e"], "north": vals["n"], "south": vals["s"], "fkey": keys[0]}
    if not (box["west"] < box["east"] and box["south"] < box["north"]):
        return None, f"fkey {keys[0]} has inverted bbox"
    lat_g = (box["north"] - box["south"]) / GRADE
    lon_g = (box["east"] - box["west"]) / GRADE
    if not (.48 <= lat_g <= .53 and .36 <= lon_g <= .43):
        return None, f"fkey {keys[0]} abnormal span {lon_g:.3f}g × {lat_g:.3f}g"
    return box, None


def rows():
    import requests
    load_dotenv(Path(".env"))
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    out = []
    offset = 0
    while True:
        response = requests.get(f"{url}/rest/v1/maps", headers=headers, timeout=30,
                                params={"select": "id,name,status,is_georeferenced,extra_metadata,iiif_image",
                                        "collection": f"eq.{COLLECTION}", "order": "id",
                                        "limit": 500, "offset": offset})
        response.raise_for_status()
        page = response.json()
        out.extend(page)
        if len(page) < 500:
            return out
        offset += 500


def sample_rows(all_rows, records, count=12):
    """Evenly spaced latitude ranks, excluding abnormal per-record extents."""
    candidates = []
    for row in all_rows:
        box, err = record_box(row, records)
        if not err and row["status"] == "draft":
            candidates.append(((box["north"] + box["south"]) / 2, row))
    candidates.sort(key=lambda x: (x[0], x[1]["id"]))
    if not candidates:
        return []
    indices = sorted({round(i * (len(candidates) - 1) / (min(count, len(candidates)) - 1))
                      for i in range(min(count, len(candidates)))}) if len(candidates) > 1 else [0]
    return [candidates[i][1] for i in indices]


def grades(value):
    if not value:
        return None
    m = re.search(r"(\d{1,3})\s*(?:[gGᵍ°º]|\^g)\s*(\d{1,4})", str(value))
    if m:
        return float(f"{m[1]}.{m[2]}")
    m = re.search(r"(\d{1,3})\s*\D{0,4}?\s*[,.]\s*(\d{1,4})", str(value))
    if m:
        return float(f"{m[1]}.{m[2]}")
    m = re.fullmatch(r"\s*(\d{1,3})\s*", str(value))
    return float(m[1]) if m else None


def locate_tick(d, approx_along, rim_across):
    """Find the short ink stroke extending outward from the measured neatline."""
    lo, hi = max(0, round(approx_along) - 180), min(d.shape[0], round(approx_along) + 181)
    if hi - lo < 20:
        return None
    scores = d[lo:hi, max(0, round(rim_across) - 22):round(rim_across) - 5].mean(axis=1)
    peak = int(np.argmax(scores))
    if scores[peak] < 45:
        return None
    return lo + peak


def tick_label(d, along, rim, axis, side):
    """Read the grade figure beside a detected tick from the cached edge strip."""
    import gemini_client as G
    if axis == "longitude":
        patch = d[max(0, along - 135):along + 135, max(0, round(rim) - 170):round(rim) + 30].T
        if side == "B":
            patch = patch[::-1]
    else:
        patch = d[max(0, along - 125):along + 125, max(0, round(rim) - 210):round(rim) + 30]
        if side == "R":
            patch = patch[:, ::-1]
    if min(patch.shape) < 40:
        return None
    image = Image.fromarray(np.clip(255 - patch, 0, 255).astype(np.uint8)).convert("RGB")
    image = image.resize((image.width * 2, image.height * 2))
    reply = G.extract_labels(
        image,
        system_prompt="Read only the printed grade coordinate beside the graticule tick in this crop.",
        user_prompt=(f"Read the {axis} grade value printed next to the short black tick. "
                     "It may appear as 112g00 or 11g90, where g is a superscript and the "
                     "digits after it are decimal grade digits. Return the entire value "
                     "without inference; return an empty string if absent or unclear."),
        schema={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
        model=G.DEFAULT_MODEL, cache_dir=WORK / "gemini_cache")
    print(f"    {side} {axis} tick OCR: {reply.get('value')!r}", flush=True)
    return grades(reply.get("value"))


def read_printed(base, W, H, measured, box):
    """Two ticks per axis determine both printed frame edges independently."""
    rough = frame(base, W, H)
    corners, lines = measured["corners"], measured["lines"]
    west_g, east_g = [(box[k] - PARIS) / GRADE for k in ("west", "east")]
    north_g, south_g = [box[k] / GRADE for k in ("north", "south")]
    def interior_ticks(low, high, step, inset):
        values = [round(i * step, 3)
                  for i in range(math.ceil(low / step), math.floor(high / step) + 1)
                  if inset <= (i * step - low) / (high - low) <= 1 - inset]
        return [values[0], values[-1]] if len(values) >= 2 else []
    targets = {
        "longitude": [interior_ticks(west_g, east_g, .1, .20),
                      interior_ticks(west_g, east_g, .2, .01)],
        "latitude": [list(reversed(interior_ticks(south_g, north_g, .1, .20))),
                     list(reversed(interior_ticks(south_g, north_g, .2, .01)))],
    }
    observations = {}
    used = {}
    for axis, sides in (("longitude", "TB"), ("latitude", "LR")):
        errors = []
        strips = {}
        for target_pair in targets[axis]:
            if len(target_pair) != 2:
                continue
            for side in sides:
                if side not in strips:
                    strips[side] = frame_strip(base, side, rough, W, H, full_along=True)
                d, origin, step, a0 = strips[side]
                pair = []
                start, end = (("NW", "NE") if side == "T" else ("SW", "SE") if side == "B"
                              else ("NW", "SW") if side == "L" else ("NE", "SE"))
                for target in target_pair:
                    fraction = ((target - west_g) / (east_g - west_g) if axis == "longitude"
                                else (north_g - target) / (north_g - south_g))
                    coordinate = 0 if axis == "longitude" else 1
                    approx = corners[start][coordinate] + fraction * (corners[end][coordinate] - corners[start][coordinate])
                    rim = lines[side]["m"] * approx + lines[side]["c"]
                    tick = locate_tick(d, approx - a0, (rim - origin) * step)
                    if tick is None:
                        errors.append(f"{side}: no tick near {target}g")
                        break
                    position = a0 + tick
                    rim_at_tick = lines[side]["m"] * position + lines[side]["c"]
                    value = tick_label(d, tick, (rim_at_tick - origin) * step, axis, side)
                    if value is None or abs(value - target) > .015:
                        errors.append(f"{side}: read {value}g at expected {target}g tick")
                        break
                    pair.append((position, value))
                if len(pair) == 2:
                    observations[axis] = pair
                    used[axis] = (side, start, end)
                    break
            if axis in observations:
                break
        if axis not in observations:
            return None, "; ".join(errors)
    (x1, lon1), (x2, lon2) = observations["longitude"]
    (y1, lat1), (y2, lat2) = observations["latitude"]
    if x2 - x1 < 500 or y2 - y1 < 500:
        return None, f"tick spacing too small: {observations}"
    lon_per_px = (lon2 - lon1) / (x2 - x1)
    lat_per_px = (lat2 - lat1) / (y2 - y1)
    lon_start, lon_end = used["longitude"][1:]
    lat_start, lat_end = used["latitude"][1:]
    p = {"west": lon1 + (corners[lon_start][0] - x1) * lon_per_px,
         "east": lon1 + (corners[lon_end][0] - x1) * lon_per_px,
         "north": lat1 + (corners[lat_start][1] - y1) * lat_per_px,
         "south": lat1 + (corners[lat_end][1] - y1) * lat_per_px}
    if not (p["west"] < p["east"] and p["south"] < p["north"]):
        return None, f"printed ticks imply inverted rectangle: {p}"
    return {"grades": p, "read": observations, "read_sides": used}, None


def calibration_observation(box, printed, row):
    p = printed["grades"]
    pw, pe = p["west"] * GRADE + PARIS, p["east"] * GRADE + PARIS
    ps, pn = p["south"] * GRADE, p["north"] * GRADE
    # A different-sized polygon is an anomaly, not an offset measurement.
    if abs((box["east"] - box["west"]) - (pe - pw)) > .006 or abs((box["north"] - box["south"]) - (pn - ps)) > .006:
        return None, "catalogue and printed spans disagree"
    lat = (pn + ps) / 2
    dx = (box["west"] - pw) * metres_per_degree(lat)[0]
    dy = (1 if box["south"] > ps else -1) * north_metres(ps, box["south"])
    return {"id": row["id"], "name": row["name"], "fkey": box["fkey"],
            "lat": lat, "dx": dx, "dy": dy, "printed_grades": p,
            "read": printed["read"], "read_sides": printed["read_sides"]}, None


def fit_calibration(observations):
    if len(observations) < 6 or max(o["lat"] for o in observations) - min(o["lat"] for o in observations) < 8:
        raise ValueError("need at least six valid printed sheets over an 8° latitude span")
    lat = np.array([o["lat"] for o in observations])
    dx = np.array([o["dx"] for o in observations])
    dy = np.array([o["dy"] for o in observations])
    # The geographic span is broad; allow both axes a latitude slope and report
    # each observation's residual instead of assuming Tonkin's coefficients.
    ex, ei = np.polyfit(lat, dx, 1)
    ny, ni = np.polyfit(lat, dy, 1)
    residuals = np.hypot(dx - (ei + ex * lat), dy - (ni + ny * lat))
    return {"n": len(observations), "lat_min": float(lat.min()), "lat_max": float(lat.max()),
            "east_intercept_m": float(ei), "east_slope_m_per_deg": float(ex),
            "north_intercept_m": float(ni), "north_slope_m_per_deg": float(ny),
            "residual_mean_m": float(residuals.mean()), "residual_max_m": float(residuals.max()),
            "observations": [{**o, "residual_m": float(r)} for o, r in zip(observations, residuals)],
            "note": "catalogue minus printed; negate to place catalogue on printed frame"}


def calibration_ready(cal):
    return (cal.get("n", 0) >= 6 and cal.get("lat_max", 0) - cal.get("lat_min", 0) >= 8
            and cal.get("residual_max_m", float("inf")) <= 250)


def calibrate(count=12, extras=()):
    records = catalogue()
    all_rows = rows()
    chosen = sample_rows(all_rows, records, count)
    by_row = {r["id"]: r for r in all_rows}
    for mid in extras:
        if mid not in by_row:
            raise ValueError(f"extra map {mid} is not in series 561")
        if mid not in {r["id"] for r in chosen}:
            chosen.append(by_row[mid])
    print(f"calibrating on {len(chosen)} latitude-stratified sheets", flush=True)
    saved = json.loads(OBS_FILE.read_text()) if OBS_FILE.exists() else []
    by_id = {o["id"]: o for o in saved}
    previous = json.loads(REPORT_FILE.read_text()) if REPORT_FILE.exists() else {}
    held = previous.get("held", {}) if previous.get("version") == CAL_VERSION else {}
    held = {mid: reason for mid, reason in held.items()
            if "incomplete tile coverage" not in reason and "ConnectionError" not in reason}
    for i, row in enumerate(chosen, 1):
        if row["id"] in by_id:
            print(f"{i}/{len(chosen)} {row['name']}: cached observation", flush=True)
            continue
        if row["id"] in held:
            print(f"{i}/{len(chosen)} {row['name']}: cached HOLD {held[row['id']]}", flush=True)
            continue
        box, err = record_box(row, records)
        if err:
            held[row["id"]] = err
            continue
        base = row["iiif_image"] or f"https://iiif.maparchive.vn/iiif/{row['id']}"
        print(f"{i}/{len(chosen)} {row['name']} {row['id']} lat {(box['north']+box['south'])/2:.2f}", flush=True)
        try:
            info = T.get_image_info(base)
            measured, err = detect(base, info["width"], info["height"])
            if not err:
                printed, err = read_printed(base, info["width"], info["height"], measured, box)
            if not err:
                obs, err = calibration_observation(box, printed, row)
            if err:
                held[row["id"]] = err
                print(f"  HOLD {err}", flush=True)
            else:
                by_id[row["id"]] = obs
                OBS_FILE.write_text(json.dumps(list(by_id.values()), indent=1))
                print(f"  catalogue − print: {obs['dx']:+.1f}m east, {obs['dy']:+.1f}m north", flush=True)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            # Tile and API transport failures are transient; keep their report,
            # but allow the next invocation to retry the sheet.
            if "incomplete tile coverage" not in failure and "ConnectionError" not in failure:
                held[row["id"]] = failure
            print(f"  FAIL {failure}", flush=True)
        REPORT_FILE.write_text(json.dumps({"version": CAL_VERSION,
                                           "selected": [r["id"] for r in chosen],
                                           "held": held}, indent=1))
    observations = [by_id[r["id"]] for r in chosen if r["id"] in by_id]
    lat_span = (max(o["lat"] for o in observations) - min(o["lat"] for o in observations)) if observations else 0
    if len(observations) < 6 or lat_span < 8:
        print(f"calibration rejected: {len(observations)} valid sheets over {lat_span:.2f}° latitude; need six over 8°")
        return None
    cal = fit_calibration(observations)
    print(f"residual mean {cal['residual_mean_m']:.1f}m, max {cal['residual_max_m']:.1f}m")
    print(f"latitude {cal['lat_min']:.2f}–{cal['lat_max']:.2f}°N")
    FIT_FILE.write_text(json.dumps(cal, indent=1))
    if calibration_ready(cal):
        OFFSET_FILE.write_text(json.dumps(cal, indent=1))
        print(f"accepted offset saved to {OFFSET_FILE}")
        return cal
    print(f"calibration rejected: maximum residual exceeds 250 m; exploratory fit saved to {FIT_FILE}")
    return None

def corrected_edges(box, cal):
    lat = (box["north"] + box["south"]) / 2
    east_m = -(cal["east_intercept_m"] + cal["east_slope_m_per_deg"] * lat)
    north_m = -(cal["north_intercept_m"] + cal["north_slope_m_per_deg"] * lat)
    west = box["west"] + east_m / metres_per_degree(lat)[0]
    east = box["east"] + east_m / metres_per_degree(lat)[0]
    south = box["south"] + north_m / metres_per_degree(box["south"])[1]
    north = box["north"] + north_m / metres_per_degree(box["north"])[1]
    return {"west": (west - PARIS) / GRADE, "east": (east - PARIS) / GRADE,
            "south": south / GRADE, "north": north / GRADE}


GATE = {"residual": RESIDUAL, "rim_spread": .12, "aspect": .03, "scale_gap": .015}


def verdict(got):
    bad = []
    if got["aspect_err"] > GATE["aspect"]:
        bad.append(f"shape off by {got['aspect_err']*100:.1f}%")
    worst = max(v["res"] for v in got["lines"].values())
    if worst > GATE["residual"]:
        bad.append(f"edge fit {worst:.1f}px")
    if got["rim_spread"] > GATE["rim_spread"]:
        bad.append(f"rim offsets spread {got['rim_spread']*100:.0f}%")
    if got["scale_gap"] > GATE["scale_gap"]:
        bad.append(f"axes disagree {got['scale_gap']*100:.1f}%")
    g = got["grades"]
    lon_span = g["SE"][0] - g["NW"][0]
    lat_span = g["NW"][1] - g["SE"][1]
    if not (.36 <= lon_span <= .43 and .48 <= lat_span <= .53):
        bad.append(f"corner figures span {lon_span:.3f}g × {lat_span:.3f}g")
    return bad


def finish(base, W, H, got, given):
    q = quad(got)
    west, east = given["west"] * GRADE + PARIS, given["east"] * GRADE + PARIS
    north, south = given["north"] * GRADE, given["south"] * GRADE
    gx, gy = ground(west, north, east, south)
    aspect_err = abs(gx / gy - q["aspect"]) / q["aspect"]
    mx, my = gx / q["w"], gy / q["h"]
    offs = [v["offset"] for v in got["lines"].values()]
    mean_off = sum(offs) / len(offs)
    got.update({"rim_spread": (max(offs) - min(offs)) / mean_off if mean_off else 0,
                "read": {}, "disagree": [], "aspect_err": aspect_err,
                "grades": {"NW": [given["west"], given["north"]],
                           "SE": [given["east"], given["south"]]},
                "wgs84": {"NW": [west, north], "NE": [east, north],
                          "SE": [east, south], "SW": [west, south]},
                "quad": q, "m_per_px": [mx, my],
                "scale_gap": abs(mx - my) / max(mx, my)})
    got["verdict"] = verdict(got)
    return got


def placement(row, records, cal):
    box, err = record_box(row, records)
    if err:
        return None, err
    base = row["iiif_image"] or f"https://iiif.maparchive.vn/iiif/{row['id']}"
    info = T.get_image_info(base)
    got, err = detect(base, info["width"], info["height"])
    if err:
        return None, err
    got = finish(base, info["width"], info["height"], got, corrected_edges(box, cal))
    got.update({"id": row["id"], "name": row["name"], "fkey": box["fkey"],
                "detector_version": DETECT_VERSION,
                "placed_from": "per-record CartoMundi UNIMARC, calibrated against printed corners"})
    if row["id"] in CALIBRATION_HOLDS:
        got["verdict"].append(CALIBRATION_HOLDS[row["id"]])
    return got, None


def place(map_id=None):
    if not OFFSET_FILE.exists():
        raise SystemExit("run calibrate and inspect its residuals before placement")
    cal = json.loads(OFFSET_FILE.read_text())
    if not calibration_ready(cal):
        raise SystemExit("calibration does not clear the six-sheet, 8° latitude, 250 m residual gate")
    records = catalogue()
    selected = [r for r in rows() if r["status"] == "draft" and not r["is_georeferenced"]
                and (map_id is None or r["id"] == map_id)]
    if map_id and not selected:
        raise SystemExit(f"no pending draft sheet {map_id}")
    WORK.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(selected, 1):
        path = WORK / f"{row['id']}.json"
        if path.exists() and json.loads(path.read_text()).get("detector_version") == DETECT_VERSION:
            print(f"{i}/{len(selected)} {row['name']}: cached")
            continue
        try:
            got, err = placement(row, records, cal)
        except Exception as exc:
            got, err = None, f"{type(exc).__name__}: {exc}"
        if err:
            print(f"{i}/{len(selected)} {row['name']}: HOLD {err}", flush=True)
            continue
        path.write_text(json.dumps(got, indent=1))
        print(f"{i}/{len(selected)} {row['name']}: {'HOLD ' + '; '.join(got['verdict']) if got['verdict'] else 'clear'}", flush=True)


def check():
    """Self-consistency of placements; return failure on conflicting records."""
    records = catalogue()
    dbrows = {r["id"]: r for r in rows()}
    cells, problems, offsets, footprints = {}, [], [], []
    for file in sorted(WORK.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f-]{36}", file.stem):
            continue
        got = json.loads(file.read_text())
        if got.get("verdict"):
            continue
        row = dbrows.get(got["id"])
        if not row:
            problems.append(f"{got['id']}: missing DB row")
            continue
        box, err = record_box(row, records)
        if err or str(box["fkey"]) != str(got.get("fkey")):
            problems.append(f"{got['id']}: fkey or span no longer matches row")
            continue
        w = got["wgs84"]
        key = (round(w["NW"][0], 3), round(w["NW"][1], 3),
               round(w["SE"][0], 3), round(w["SE"][1], 3))
        cell = (row["extra_metadata"].get("sheet_number"), row["extra_metadata"].get("sheet_half"))
        cells.setdefault(cell, []).append((key, got["id"]))
        footprints.append((cell, got["id"], (w["NW"][0], w["SE"][1],
                                              w["SE"][0], w["NW"][1])))
        offsets.append((np.mean([v["offset"] for v in got["lines"].values()]) / got["quad"]["h"], got["id"]))
    for cell, vals in cells.items():
        if len({key for key, _ in vals}) > 1:
            problems.append(f"cell {cell} reprints disagree: {vals}")
    # Different cells can touch, but they must not cover most of the same ground.
    for i, (cell_a, id_a, a) in enumerate(footprints):
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        for cell_b, id_b, b in footprints[i + 1:]:
            if cell_a == cell_b:
                continue
            overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            if overlap > .4 * min(area_a, area_b):
                problems.append(f"different cells overlap: {cell_a} {id_a} / {cell_b} {id_b}")
    if offsets:
        median = float(np.median([o for o, _ in offsets]))
        for offset, mid in offsets:
            if abs(offset / median - 1) > .15:
                problems.append(f"{mid}: rim offset differs >15% from series median")
    print(f"checked {sum(map(len, cells.values()))} placements in {len(cells)} half cells")
    for problem in problems:
        print("  HOLD " + problem)
    return not problems


def regress(tolerance=2.0):
    """Re-run detect() from cache against every saved clear placement's corners.

    The one thing any change to frame()/side_line()/rim_in() must not do is move
    a sheet that already places correctly -- this is what proved the alt-retry
    (added 2026-09-24) regression-free before it landed. Reads only cached IIIF
    crops; run place() first if a sheet's strips were never fetched.
    """
    bad = []
    n = 0
    for file in sorted(WORK.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f-]{36}", file.stem):
            continue
        saved = json.loads(file.read_text())
        if saved.get("verdict") or "lines" not in saved or "quad" not in saved:
            continue
        base = f"https://iiif.maparchive.vn/iiif/{saved['id']}"
        info = T.get_image_info(base)
        got, err = detect(base, info["width"], info["height"])
        n += 1
        if err:
            bad.append(f"{saved['name']}: now fails: {err}")
            continue
        for c in CORNERS:
            dx = got["corners"][c][0] - saved["corners"][c][0]
            dy = got["corners"][c][1] - saved["corners"][c][1]
            if math.hypot(dx, dy) > tolerance:
                bad.append(f"{saved['name']}: {c} moved {dx:.2f},{dy:.2f}px")
    print(f"checked {n} clear placements, {len(bad)} regressions")
    for msg in bad:
        print("  " + msg)
    return not bad


def annotate(write=False, only_new=True):
    """Prepare Allmaps annotations; --apply writes draft rows only."""
    import requests
    if not OFFSET_FILE.exists() or not calibration_ready(json.loads(OFFSET_FILE.read_text())):
        raise SystemExit("calibration has not cleared the residual and latitude gates")
    if not check():
        raise SystemExit("lattice check failed; no annotations prepared")
    load_dotenv(Path(".env"))
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    dbrows = {r["id"]: r for r in rows()}
    outdir = WORK / "annotations"
    outdir.mkdir(parents=True, exist_ok=True)
    done = held = 0
    for file in sorted(WORK.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f-]{36}", file.stem):
            continue
        got = json.loads(file.read_text())
        row = dbrows.get(got.get("id"))
        if (got.get("verdict") or not row or got.get("id") in CALIBRATION_HOLDS or
                row["status"] != "draft" or (only_new and row["is_georeferenced"])):
            held += 1
            continue
        mid = got["id"]
        iiif = row["iiif_image"] or f"https://iiif.maparchive.vn/iiif/{mid}"
        info = T.get_image_info(iiif)
        ann = annotation(iiif, info["width"], info["height"], got)
        (outdir / f"{mid}.json").write_text(json.dumps(ann, indent=1))
        w = got["wgs84"]
        bbox = [w["SW"][0], w["SW"][1], w["NE"][0], w["NE"][1]]
        if not write:
            print(f"{got['name']}: ready {bbox}")
            done += 1
            continue
        body = (outdir / f"{mid}.json").read_bytes()
        obj = f"{url}/storage/v1/object/{BUCKET}/{mid}.json"
        response = requests.post(obj, headers={**headers, "Content-Type": "application/json",
                                               "x-upsert": "true"}, data=body, timeout=60)
        if response.status_code == 400:
            response = requests.put(obj, headers={**headers, "Content-Type": "application/json",
                                                  "x-upsert": "true"}, data=body, timeout=60)
        response.raise_for_status()
        public = f"{url}/storage/v1/object/public/{BUCKET}/{mid}.json"
        response = requests.patch(f"{url}/rest/v1/maps?id=eq.{mid}&status=eq.draft&is_georeferenced=is.false",
                                  headers=headers, timeout=30,
                                  json={"annotation_url": public, "is_georeferenced": True, "bbox": bbox})
        response.raise_for_status()
        print(f"{got['name']}: written")
        done += 1
    print(f"{done} {'written' if write else 'ready'}, {held} held")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["calibrate", "candidates", "detect", "place", "check", "annotate", "regress"])
    parser.add_argument("map_id", nargs="?")
    parser.add_argument("--count", type=int, default=12, help="latitude-stratified calibration sample size")
    parser.add_argument("--extra", action="append", default=[], help="additional series-561 map id for calibration")
    parser.add_argument("--lat-min", type=float, default=19, help="candidates: minimum catalogue latitude")
    parser.add_argument("--lat-max", type=float, default=23.5, help="candidates: maximum catalogue latitude")
    parser.add_argument("--apply", action="store_true", help="annotate: write draft-only annotation and flag")
    args = parser.parse_args()
    if args.phase == "calibrate":
        if calibrate(args.count, args.extra) is None:
            raise SystemExit(1)
    elif args.phase == "candidates":
        records = catalogue()
        for row in rows():
            box, err = record_box(row, records)
            if not err and args.lat_min <= (box["north"] + box["south"]) / 2 <= args.lat_max:
                print(f"{(box['north'] + box['south']) / 2:5.2f} {row['id']} {row['name']}")
    elif args.phase == "place":
        place(args.map_id)
    elif args.phase == "check":
        if not check():
            raise SystemExit(1)
    elif args.phase == "annotate":
        annotate(args.apply)
    elif args.phase == "regress":
        if not regress():
            raise SystemExit(1)
    else:
        if not args.map_id:
            parser.error("detect requires map_id")
        base = f"https://iiif.maparchive.vn/iiif/{args.map_id}"
        info = T.get_image_info(base)
        got, err = detect(base, info["width"], info["height"], verbose=True)
        if err:
            raise SystemExit(err)
        print(json.dumps(got["corners"], indent=1))


if __name__ == "__main__":
    main()
