#!/usr/bin/env python3
"""Georeference the Indochine 1:25,000 Tonkin & Thanh Hoa series from what it prints.

Every sheet in this series carries its own sheet index. The top-left and
bottom-right corners of the mapped area print their own coordinates, in grades
from the Paris meridian, so the step that needed archival research for the Dutch
series MapEdge was built for is free here: there is nothing to reconstruct, only
to read.

What is left is two halves --

    detect   where the four corners are in the scan's own pixels
    read     what the two printed corners say

-- and then the annotation is arithmetic.

    python3 scripts/tonkin_georef.py detect <map-id>
    python3 scripts/tonkin_georef.py detect --all

Detection follows MapEdge in shape: a low-resolution look to find the frame
roughly, then full-resolution strips at the edges only, a line fit per side,
intersect. What differs is which line it locks onto. These sheets print a *pair*
of thin lines at the rim of the map with a graticule band outside them, so "walk
in from the blank margin until it stops being paper" -- which is what
scripts/l7014_neatline.py does, and it was tried here first -- stops at the band,
40 px and 170 m short.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "work/ocr/scripts"))
import iiif_tiles as T  # noqa: E402

WORK = Path("work/tonkin")
OV = 1800            # overview width for the rough pass
PATCHES = 24         # samples per side
SPAN = (0.12, 0.88)  # sample this much of each edge, away from the corners
ACROSS = (190, 150)  # strip reaches this far outside / inside the thick outer line
MAXIN = 110          # the rim cannot be further inside the thick line than this
MINGAP = 10          # blank paper at least this wide separates the band from the rim
LIM = 34             # the rim pair sits within this of that blank run
TRIM = 3.0

# The sheets print their corners in grades from the Paris meridian: 400 grades to
# the turn, so 0.9 degrees each, and Paris is 2 20' 14.025" east of Greenwich.
GRADE = 0.9
PARIS = 2.337229166666667


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


def rough_frame(base, W, H):
    """The thick outer neatline on each side, from one low-resolution look.

    It only has to be close enough to aim a full-resolution strip at. The band it
    is measured over is narrow on purpose: the frame is printed straight but these
    scans are laid down as much as 0.8 degrees off square, and over half a sheet
    that smears a 10 px line across 30 and lets a weaker, shorter feature win the
    argmax -- measured on Nhu Trac, where a half-width average put the top
    neatline 35 px from where it is.
    """
    img = T.fetch_crop_level0(base, 0, 0, W, H, OV)
    d = darkness(img)
    h, w = d.shape
    sc = W / w
    cols = d[int(h * 0.46):int(h * 0.54)].mean(axis=0)
    rows = d[:, int(w * 0.46):int(w * 0.54)].mean(axis=1)
    out = {}
    for side, prof, n, s in (("L", cols, w, sc), ("R", cols, w, sc),
                             ("T", rows, h, H / h), ("B", rows, h, H / h)):
        third = n // 3
        seg = prof[:third] if side in "LT" else prof[-third:]
        i = int(np.argmax(seg)) + (0 if side in "LT" else n - third)
        out[side] = i * s
    return out


def strip(base, side, frame, W, H):
    """One full-resolution band along a side, oriented outside -> inside.

    Returns the band as (along, across), plus what it takes to put a position in
    that band back into the scan's own coordinates.
    """
    lo, hi = SPAN
    c = frame[side]
    if side in "LR":
        a0, a1 = int(H * lo), int(H * hi)
        x0 = int(c - (ACROSS[0] if side == "L" else ACROSS[1]))
        x1 = int(c + (ACROSS[1] if side == "L" else ACROSS[0]))
        x0, x1 = max(0, x0), min(W, x1)
        d = darkness(T.fetch_crop_level0(base, x0, a0, x1 - x0, a1 - a0, x1 - x0))
        origin, step = (x0, 1) if side == "L" else (x1 - 1, -1)
    else:
        a0, a1 = int(W * lo), int(W * hi)
        y0 = int(c - (ACROSS[0] if side == "T" else ACROSS[1]))
        y1 = int(c + (ACROSS[1] if side == "T" else ACROSS[0]))
        y0, y1 = max(0, y0), min(H, y1)
        d = darkness(T.fetch_crop_level0(base, a0, y0, a1 - a0, y1 - y0, a1 - a0)).T
        origin, step = (y0, 1) if side == "T" else (y1 - 1, -1)
    if step < 0:
        d = d[:, ::-1]
    return d, origin, step, a0


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


def side_line(d, which):
    """One strip -> the rim line, in that strip's own coordinates.

    Two passes, and the split is the point. The **thick outer neatline** is the
    strongest thing on the strip by a factor of three and is found by argmax alone,
    per patch, with no threshold -- so the geometry (where the side runs, and how
    far off square this scan was laid down) is settled on the one feature that
    cannot be mistaken for another.

    Only then is the strip de-tilted onto that fit and averaged down to a single
    profile. The rim is faint in any one patch and sits against map content that is
    not faint at all; in the average of two dozen aligned patches it is plain, and
    the distance from the thick line to it is a printed constant that does not need
    finding twice.
    """
    n = d.shape[0]
    edges = np.linspace(0, n, PATCHES + 1).round().astype(int)
    mids, peaks, profiles = [], [], []
    for k in range(PATCHES):
        lo, hi = edges[k], edges[k + 1]
        if hi - lo < 8:
            continue
        prof = d[lo:hi].mean(axis=0)
        mids.append((lo + hi) / 2.0)
        peaks.append(float(np.argmax(prof)))
        profiles.append(prof)
    f = fit(list(zip(mids, peaks)))
    if f is None:
        return None, "the thick line would not fit"
    m, c, res, keep, tot = f
    if res > 3.0:
        return None, f"thick line residual {res:.1f}px"
    ref = m * float(np.mean(mids)) + c
    grid = np.arange(d.shape[1], dtype=float)
    avg = np.mean([np.interp(grid, grid + (ref - (m * mid + c)), prof)
                   for mid, prof in zip(mids, profiles)], axis=0)
    r = rim_in(avg, int(round(ref)), which)
    if r is None:
        return None, "no rim found inside the thick line"
    return {"m": m, "c": c + (r - ref), "res": res, "kept": keep, "found": tot,
            "offset": r - ref}, None


def cut_side(base, W, H, side, tan, frame):
    """The one edge of a half-sheet that was never printed as a frame.

    Most of this survey was issued as two half-sheets, cut down the middle
    meridian of the cell, and a few whole-cell sheets stop where the survey
    stopped. On that edge there is no thick neatline, no thin companion, no
    graticule band -- just paper, one thin rim line, and the kilometre-grid
    figures printed OUTSIDE it. `side_line` cannot work there: its whole design
    is to anchor on the thick line, which is the strongest thing on a normal
    strip by a factor of three, and then find the rim at a printed distance in
    from it. With no anchor it reports "no rim found inside the thick line".

    What replaces it is the one thing that edge does have: the rim runs the full
    height of the sheet and nothing else there does. So the rotation is taken
    from the three real sides -- it is a property of how the scan was laid on the
    glass, not of any one edge -- the search window is de-tilted onto it and
    averaged down the whole span, and in that average a continuous line stands up
    while grid numerals (a few patches tall) and map content (irregular) average
    away. No anchor, no offset, no second pass: the line found IS the rim.

    The window is wide because `rough_frame`'s guess for this side is worthless
    -- its argmax over a narrow central band picks whatever is darkest in the
    outer third, which on a cut edge may be a grid numeral or a patch of ink, and
    that is what produced the 58 px and 97 px "thick line residual" failures.
    """
    search = max(300, int(0.16 * W))
    lo, hi = SPAN
    a0, a1 = int(H * lo), int(H * hi)
    x0, x1 = (0, search) if side == "L" else (W - search, W)
    d = darkness(T.fetch_crop_level0(base, x0, a0, x1 - x0, a1 - a0, x1 - x0))
    origin, step = (x0, 1) if side == "L" else (x1 - 1, -1)
    if step < 0:
        d = d[:, ::-1]

    n = d.shape[0]
    edges = np.linspace(0, n, PATCHES + 1).round().astype(int)
    mids, profiles = [], []
    for k in range(PATCHES):
        u, v = edges[k], edges[k + 1]
        if v - u < 8:
            continue
        mids.append((u + v) / 2.0)
        profiles.append(d[u:v].mean(axis=0))
    if len(mids) < 6:
        return None, "cut edge: too few patches"
    # De-tilt onto the rotation the framed sides already settled. `tan` is dy/dx
    # for a horizontal side; along a vertical strip the across-position moves by
    # -tan per unit of along-position, and the strip was flipped for R so that
    # both sides read outside-inward.
    slope = -tan * step
    ref = float(np.mean(mids))
    grid = np.arange(d.shape[1], dtype=float)
    avg = np.mean([np.interp(grid, grid + slope * (ref - mid), prof)
                   for mid, prof in zip(mids, profiles)], axis=0)

    # The strongest prominent peak, ignoring the outermost sliver where the scan
    # carries the edge of the paper and sometimes the scanner's own backing.
    paper = float(np.percentile(avg, 25))
    best, bestp = None, 0.0
    for j in range(12, len(avg) - 1):
        if not (avg[j] >= avg[j - 1] and avg[j] > avg[j + 1]):
            continue
        u, v = max(0, j - 12), min(len(avg), j + 13)
        prom = avg[j] - max(avg[u:j + 1].min(), avg[j:v].min())
        if prom > bestp:
            best, bestp = j, prom
    if best is None or bestp < max(8.0, 0.12 * (float(avg.max()) - paper)):
        return None, "cut edge: no continuous line found"
    # Centroid of the line, as rim_in does, so the position is sub-pixel.
    thr = paper + bestp * 0.25
    u = v = best
    while u > 0 and avg[u - 1] > thr and avg[u - 1] <= avg[u]:
        u -= 1
    while v < len(avg) - 1 and avg[v + 1] > thr and avg[v + 1] <= avg[v]:
        v += 1
    w = avg[u:v + 1] - thr
    if w.sum() <= 0:
        return None, "cut edge: line has no weight"
    r = u + float((np.arange(len(w)) * w).sum() / w.sum())

    m = slope * step
    c = origin + step * r - m * a0
    mid = H * (SPAN[0] + SPAN[1]) / 2
    return {"m": m, "c": c, "anchor": [mid, m * mid + c], "res": 0.0,
            "kept": len(mids), "found": len(mids), "offset": 0.0,
            "cut": True}, None


def detect(base, W, H, which="inner", verbose=False, cut=None):
    frame = rough_frame(base, W, H)
    lines = {}
    for side in "LRTB":
        if side == cut:
            continue
        d, origin, step, a0 = strip(base, side, frame, W, H)
        got, err = side_line(d, which)
        if err:
            return None, f"{side}: {err}"
        m = got["m"] * step
        c = origin + step * (got["c"] - got["m"] * a0)
        mid = (H if side in "LR" else W) * (SPAN[0] + SPAN[1]) / 2
        lines[side] = {"m": m, "c": c, "anchor": [mid, m * mid + c],
                       "res": got["res"], "kept": got["kept"],
                       "found": got["found"], "offset": got["offset"]}

    # One sheet, one rotation. Each side's slope is fitted from its own two dozen
    # patches and comes out within a thousandth of the others -- but a thousandth
    # over three thousand pixels is three, and the four sides disagreeing by that
    # much made opposite edges of the quad differ by 14 px when the projection says
    # they differ by 4. The scan was laid on the glass at one angle; solve for it
    # once, from all four sides, and let each side keep only the offset its own rim
    # measurement gives. This is the difference between telling the rim's two lines
    # apart -- they are 7 px apart -- and not being able to.
    # A cut side contributes no slope -- there is nothing there fitted well
    # enough to trust with it -- so the angle comes from the three real sides and
    # is then handed to the cut side, which is the only reason its single faint
    # line can be found at all.
    tan = float(np.mean([s * lines[k]["m"] for k, s in
                         (("T", 1), ("B", 1), ("L", -1), ("R", -1))
                         if k != cut]))
    if cut:
        got, err = cut_side(base, W, H, cut, tan, frame)
        if err:
            return None, f"{cut}: {err}"
        lines[cut] = got
    for side in "LRTB":
        m = -tan if side in "LR" else tan
        ax, ay = lines[side]["anchor"]
        lines[side]["m"], lines[side]["c"] = m, ay - m * ax
        if verbose:
            print(f"  {side}: rim {lines[side]['offset']:5.1f}px inside the thick "
                  f"line  fit residual {lines[side]['res']:.2f}px  "
                  f"{lines[side]['kept']}/{lines[side]['found']} patches")
    if verbose:
        print(f"  scan rotation {math.degrees(math.atan(tan)):+.3f} deg")

    def cross(v, hz):
        V, Hz = lines[v], lines[hz]
        y = (Hz["m"] * V["c"] + Hz["c"]) / (1.0 - Hz["m"] * V["m"])
        return [V["m"] * y + V["c"], y]

    corners = {k: cross(*ab) for k, ab in
               (("NW", ("L", "T")), ("NE", ("R", "T")),
                ("SE", ("R", "B")), ("SW", ("L", "B")))}
    return {"corners": corners, "lines": lines, "rotation": tan, "cut": cut}, None


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


PAD, INSET = 280, 70

_CORNER_SCHEMA = {
    "type": "object",
    "properties": {
        "longitude": {"type": "string"},
        "latitude": {"type": "string"},
    },
    "required": ["longitude", "latitude"],
}

_CORNER_SYSTEM = (
    "You read the marginal coordinate figures printed at the corners of French "
    "colonial survey sheets. Return exactly the characters printed. Never round, "
    "never normalise, never supply a figure that is not there."
)

_CORNER_PROMPT = (
    "This is one corner of a French 1:25,000 sheet of Tonkin. Printed just "
    "outside the corner of the mapped area are two figures in GRADES: a longitude "
    "written horizontally, around 115 to 117, and a latitude written vertically "
    "(rotated a quarter turn), around 21 to 23.\n\n"
    "Each is written as a whole number, a superscript g, a comma, then the "
    "decimals -- for example `115g,20` or `22g,875`. The comma is the decimal "
    "point.\n\n"
    "Return `longitude` and `latitude` as plain decimal numbers with a full stop, "
    "e.g. `115.20` and `22.875`. Read every decimal digit that is printed: 22.75 "
    "and 22.875 are different corners 14 km apart. If a figure is not legible or "
    "not present, return an empty string for it -- do not guess it from the other."
)


def read_corner(img, model=None, log_path=None, cache_dir=None):
    """The two printed figures at one corner, in grades."""
    import gemini_client as G
    got = G.extract_labels(
        img,
        system_prompt=_CORNER_SYSTEM,
        user_prompt=_CORNER_PROMPT,
        schema=_CORNER_SCHEMA,
        model=model or G.DEFAULT_MODEL,
        log_path=log_path,
        cache_dir=cache_dir,
    )
    return grades(got.get("longitude")), grades(got.get("latitude"))


def grades(text):
    """`115g,20` / `115.20` / `22^g,875'` -> 115.20 / 22.875, or None."""
    if not text:
        return None
    m = re.search(r"(\d{2,3})\s*\D{0,4}?\s*[,.]\s*(\d{1,3})", str(text))
    if not m:
        m = re.fullmatch(r"\s*(\d{2,3})\s*", str(text))
        return float(m.group(1)) if m else None
    return float(f"{m.group(1)}.{m.group(2)}")


# Which way the printed figures lie from each corner: outward, on both axes.
OUTWARD = {"NW": (-1, -1), "NE": (1, -1), "SE": (1, 1), "SW": (-1, 1)}


def corner_crop(base, corner, side, W, H):
    """The patch of paper carrying one corner's printed figures."""
    sx, sy = OUTWARD[side]
    cx, cy = corner
    x = cx - PAD + INSET if sx < 0 else cx - INSET
    y = cy - PAD + INSET if sy < 0 else cy - INSET
    x, y = max(0, min(W - PAD, int(x))), max(0, min(H - PAD, int(y)))
    return T.fetch_crop_level0(base, x, y, PAD, PAD, PAD * 2)


def ground(lon0, lat0, lon1, lat1):
    """Metres across and down the quadrangle, on the WGS 84 ellipsoid.

    Through pyproj rather than a spherical shortcut: the check this feeds asks
    whether the two axes agree to a few parts in a thousand, and the cos-latitude
    formula for a degree of meridian is wrong by six of them at this latitude --
    enough on its own to reverse which of the rim's two lines looks right.
    """
    from pyproj import Geod
    g = Geod(ellps="WGS84")
    north = g.inv(lon0, lat0, lon1, lat0)[2]
    south = g.inv(lon0, lat1, lon1, lat1)[2]
    return (north + south) / 2, g.inv(lon0, lat0, lon0, lat1)[2]


def resolve(read, aspect_px):
    """Four corners, eight figures, and the two the detector says are wrong.

    Each side of the sheet is printed twice -- the west longitude at NW and again
    at SW -- so a misreading announces itself. What it does not do is say which of
    the two is wrong, and the model's error here is systematically the same shape:
    a vertical `22g,25'` read as 22.625, because a superscript g over a comma looks
    like a 6. Both readings are perfectly plausible in isolation.

    So the choice is made on evidence the model had no part in. A sheet has to be a
    rectangle -- east of west, north of south -- which usually kills one candidate
    outright, and of whatever survives, the right combination is the one whose
    ground shape matches the pixel quad that was measured off the paper. The
    detector arbitrates the OCR; neither could have caught this alone.
    """
    sides = {"west": (read["NW"][0], read["SW"][0]),
             "east": (read["NE"][0], read["SE"][0]),
             "north": (read["NW"][1], read["NE"][1]),
             "south": (read["SW"][1], read["SE"][1])}
    disagree = [f"{k} {a} vs {b}" for k, (a, b) in sides.items() if a != b]
    opts = {k: sorted(set(v)) for k, v in sides.items()}
    best = None
    for w in opts["west"]:
        for e in opts["east"]:
            for n in opts["north"]:
                for s_ in opts["south"]:
                    if not (e > w and n > s_):
                        continue
                    gx, gy = ground(w * GRADE + PARIS, n * GRADE,
                                    e * GRADE + PARIS, s_ * GRADE)
                    err = abs(gx / gy - aspect_px) / aspect_px
                    if best is None or err < best[0]:
                        best = (err, {"west": w, "east": e, "north": n, "south": s_})
    if best is None:
        return None, "; ".join(disagree) or "no rectangle", None
    return best[1], disagree, best[0]


# A half-sheet is half a cell wide, and a cell is 0.20 grades. The lattice check
# measures that constant over the whole series and finds it exact to 0.000, which
# is what makes it safe to supply the edge the paper does not print.
CELL_LON, CELL_LAT = 0.20, 0.125


def resolve_cut(read, aspect_px, cut):
    """Two printed corners, and the third edge taken from the lattice.

    A cut sheet prints its figures only at the two corners on its framed vertical
    side, so `resolve`'s cross-check -- each side's coordinate printed twice, at
    both its corners -- is available for the longitude and gone for the two
    latitudes. The lattice puts it back: every sheet in this survey is 0.125
    grades tall, measured over 66 of them and exact to 0.000, so the latitude read
    at one corner predicts the other. Both readings and both predictions go in as
    candidates and the pixel quad arbitrates, exactly as it does for a whole
    sheet. The missing longitude is not a candidate but a derivation -- framed
    edge plus or minus half a cell -- which the aspect gate then tests: get the
    width wrong by a factor of two and the shape is wrong by a factor of two.
    """
    if cut == "L":                       # framed on the east
        lons, (nc, sc) = [read["NE"][0], read["SE"][0]], ("NE", "SE")
    else:                                # framed on the west
        lons, (nc, sc) = [read["NW"][0], read["SW"][0]], ("NW", "SW")
    n_read, s_read = read[nc][1], read[sc][1]
    disagree = ([f"{'east' if cut == 'L' else 'west'} {lons[0]} vs {lons[1]}"]
                if lons[0] != lons[1] else [])
    norths = sorted({n_read, round(s_read + CELL_LAT, 4)})
    souths = sorted({s_read, round(n_read - CELL_LAT, 4)})
    best = None
    for lon in sorted(set(lons)):
        w, e = ((lon - CELL_LON / 2, lon) if cut == "L"
                else (lon, lon + CELL_LON / 2))
        for n in norths:
            for s_ in souths:
                if not (e > w and n > s_):
                    continue
                gx, gy = ground(w * GRADE + PARIS, n * GRADE,
                                e * GRADE + PARIS, s_ * GRADE)
                err = abs(gx / gy - aspect_px) / aspect_px
                if best is None or err < best[0]:
                    best = (err, {"west": w, "east": e, "north": n, "south": s_})
    if best is None:
        return None, "; ".join(disagree) or "no rectangle", None
    return best[1], disagree, best[0]


def read_sheet(base, W, H, which="inner", verbose=False, cut=None):
    """Corners in pixels, corners in degrees, and whether the two agree.

    A sheet is tried as a whole sheet first and only re-read as a cut one when
    exactly one vertical side failed -- which is what a missing frame looks like
    and is also, honestly, what a badly scanned frame looks like. The two are
    told apart downstream rather than here: a sheet wrongly called cut is handed
    a width half of its real one, and `aspect` and `scale_gap` both fail on it.
    """
    got, err = detect(base, W, H, which, verbose, cut)
    if err and cut is None and err[0] in "LR" and err[1] == ":":
        if verbose:
            print(f"  {err}\n  -- retrying with {err[0]} as a cut edge")
        return read_sheet(base, W, H, which, verbose, cut=err[0])
    if err:
        return None, err
    return finish(base, W, H, got)


def finish(base, W, H, got):
    """Everything after the corners: read them, reconcile them, judge the result."""
    C = got["corners"]
    # All four corners print both figures, not just the diagonal pair. Reading all
    # four is four Gemini calls instead of two and buys the only check that
    # localises a misreading: the two corners on a side must agree about that
    # side's coordinate. A sheet 14 km out of place is otherwise invisible -- it
    # still lies flat on the basemap and still looks like a map.
    cut = got.get("cut")
    # A cut edge prints no figures at all -- what sits outside it is the Bonne
    # kilometre chiffraison, not grades -- so its two corners are not read. Two
    # Gemini calls instead of four, and the check that survives is the longitude,
    # printed at both ends of the framed side.
    wanted = CORNERS if not cut else (("NE", "SE") if cut == "L" else ("NW", "SW"))
    read = {k: read_corner(corner_crop(base, C[k], k, W, H)) for k in wanted}
    if any(v is None for pair in read.values() for v in pair):
        return None, "corner figures unread: " + ", ".join(
            f"{k} {a},{b}" for k, (a, b) in read.items())
    q = quad(got)
    edges, disagree, err = (resolve_cut(read, q["aspect"], cut) if cut
                            else resolve(read, q["aspect"]))
    if edges is None:
        return None, f"corner figures irreconcilable: {disagree}"
    nw_lon, se_lon = edges["west"], edges["east"]
    nw_lat, se_lat = edges["north"], edges["south"]
    west, east = nw_lon * GRADE + PARIS, se_lon * GRADE + PARIS
    north, south = nw_lat * GRADE, se_lat * GRADE
    gx, gy = ground(west, north, east, south)
    mx, my = gx / q["w"], gy / q["h"]
    # The cut side's offset is 0 by construction -- the line found there IS the
    # rim, with no thick line to measure in from -- so including it would make
    # every half-sheet fail the spread gate that exists to catch a side which
    # locked onto the graticule band instead.
    offs = [v["offset"] for k, v in got["lines"].items() if k != cut]
    mean_off = sum(offs) / len(offs)
    got.update({
        "rim_spread": (max(offs) - min(offs)) / mean_off if mean_off else 0.0,
        "read": {k: list(v) for k, v in read.items()},
        "disagree": disagree,
        "aspect_err": err,
        "grades": {"NW": [nw_lon, nw_lat], "SE": [se_lon, se_lat]},
        "wgs84": {"NW": [west, north], "NE": [east, north],
                  "SE": [east, south], "SW": [west, south]},
        "quad": q, "m_per_px": [mx, my],
        "scale_gap": abs(mx - my) / max(mx, my),
    })
    got["verdict"] = verdict(got)
    return got, None


# What a sheet has to clear to be proposed at all. Each number is a different
# thing going wrong, and none of them is visible in the result: a sheet that fails
# any of these still produces a map that sits flat on the basemap and looks right.
GATE = {
    "residual": 3.0,    # a side's thick line did not fit a straight line
    "rim_spread": 0.12,  # the four sides disagree about how far in the rim is,
                         # which means at least one of them locked onto the band
    "aspect": 0.03,     # the printed corners and the measured quad describe
                        # differently shaped sheets
    "scale_gap": 0.015,  # the two axes disagree about the ground scale, which
                         # means the printed figures and the pixels are telling
                         # different stories -- a misread decimal does this
}


def verdict(got):
    bad = []
    if got.get("aspect_err", 0) > GATE["aspect"]:
        bad.append(f"shape off by {got['aspect_err']*100:.1f}%")
    worst = max(v["res"] for v in got["lines"].values())
    if worst > GATE["residual"]:
        bad.append(f"edge fit {worst:.1f}px")
    if got["rim_spread"] > GATE["rim_spread"]:
        bad.append(f"rim offsets spread {got['rim_spread']*100:.0f}%")
    if got["scale_gap"] > GATE["scale_gap"]:
        bad.append(f"axes disagree {got['scale_gap']*100:.1f}%")
    g = got["grades"]
    dlon, dlat = g["SE"][0] - g["NW"][0], g["NW"][1] - g["SE"][1]
    if not (0.05 <= dlon <= 0.5 and 0.05 <= dlat <= 0.5):
        bad.append(f"corner figures span {dlon}g x {dlat}g")
    return bad


def sheets():
    """The series, out of the database: every sheet still not georeferenced."""
    import requests
    from dotenv import load_dotenv
    import os
    load_dotenv(Path(".env"))
    url, key = os.environ["PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
    r = requests.get(f"{url}/rest/v1/maps", timeout=30,
                     headers={"apikey": key, "Authorization": f"Bearer {key}"},
                     params={"select": "id,name,year_label,extra_metadata",
                             "georef_done": "eq.false", "collection": f"eq.{COLLECTION}",
                             "order": "name"})
    r.raise_for_status()
    return r.json()


COLLECTION = "Indochine 1:25,000 \u2014 Tonkin & Thanh H\u00f3a"


def run_all(which="inner", shard=None):
    WORK.mkdir(parents=True, exist_ok=True)
    rows = sheets()
    if shard:
        i, n = (int(x) for x in shard.split("/"))
        rows = rows[i::n]
    print(f"{len(rows)} sheets\n")
    ok = 0
    for i, row in enumerate(rows, 1):
        mid, name = row["id"], row["name"]
        out = WORK / f"{mid}.json"
        if out.exists():
            got = json.loads(out.read_text())
            note = "cached"
        else:
            try:
                base = f"https://iiif.maparchive.vn/iiif/{mid}"
                info = T.get_image_info(base)
                got, err = read_sheet(base, info["width"], info["height"], which)
            except Exception as exc:                      # noqa: BLE001
                got, err = None, f"{type(exc).__name__}: {exc}"
            if err:
                print(f"{i:3d}/{len(rows)} {name:22.22s} FAILED  {err}")
                continue
            got["id"], got["name"] = mid, name
            # Which of the rim's two lines this sheet was read on. Normally
            # `inner`; a sheet that had to fall back to `outer` sits about 7 px
            # -- some 30 m -- further out, and that is worth being able to see
            # later without re-running anything.
            got["which"] = which
            out.write_text(json.dumps(got, indent=1))
            note = ""
        v = got["verdict"]
        mx, my = got["m_per_px"]
        flag = "ok  " if not v else "CHECK"
        ok += not v
        note = (note + " fixed:" + ",".join(got["disagree"])) if got.get("disagree") else note
        print(f"{i:3d}/{len(rows)} {name:22.22s} {flag} "
              f"{got['grades']['NW'][0]:.2f}/{got['grades']['NW'][1]:.3f}g "
              f"{mx:.3f}m/px  axes {got['scale_gap']*100:4.2f}%  "
              f"{'; '.join(v)} {note}")
    print(f"\n{ok}/{len(rows)} clear the gate")


CORNERS = ("NW", "NE", "SE", "SW")
BUCKET = "annotations"


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


def annotate(write=False):
    """Write an annotation per sheet that cleared the gate; optionally publish it.

    `georef_done` goes true and `status` is left alone. Every one of these rows is
    a draft, so turning the flag on puts the sheet on /explore for a signed-in
    reviewer and nowhere else -- which is the point: the last step of this pipeline
    is a person looking at all of them, and they cannot look at what the viewer
    will not list.
    """
    import os
    import requests
    from dotenv import load_dotenv
    load_dotenv(Path(".env"))
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    H = {"apikey": key, "Authorization": f"Bearer {key}"}
    outdir = WORK / "annotations"
    outdir.mkdir(parents=True, exist_ok=True)
    files = sorted(WORK.glob("*.json"))
    done = skipped = 0
    for f in files:
        got = json.loads(f.read_text())
        if got.get("verdict"):
            print(f"  {got['name']:22.22s} skipped -- {'; '.join(got['verdict'])}")
            skipped += 1
            continue
        mid, iiif = got["id"], f"https://iiif.maparchive.vn/iiif/{got['id']}"
        info = T.get_image_info(iiif)
        ann = annotation(iiif, info["width"], info["height"], got)
        (outdir / f"{mid}.json").write_text(json.dumps(ann, indent=1))
        w = got["wgs84"]
        bbox = [w["SW"][0], w["SW"][1], w["NE"][0], w["NE"][1]]
        if not write:
            print(f"  {got['name']:22.22s} ready   bbox {bbox}")
            done += 1
            continue
        body = (outdir / f"{mid}.json").read_bytes()
        obj = f"{url}/storage/v1/object/{BUCKET}/{mid}.json"
        r = requests.post(obj, headers={**H, "Content-Type": "application/json",
                                        "x-upsert": "true"}, data=body, timeout=60)
        if r.status_code == 400:
            r = requests.put(obj, headers={**H, "Content-Type": "application/json",
                                           "x-upsert": "true"}, data=body, timeout=60)
        r.raise_for_status()
        public = f"{url}/storage/v1/object/public/{BUCKET}/{mid}.json"
        r = requests.patch(f"{url}/rest/v1/maps?id=eq.{mid}", headers=H, timeout=30,
                           json={"annotation_url": public, "georef_done": True,
                                 "bbox": bbox})
        r.raise_for_status()
        print(f"  {got['name']:22.22s} written")
        done += 1
    print(f"\n{done} {'written' if write else 'ready'}, {skipped} held back")


def check():
    """Lay the whole series out as the grid it is, and see whether it is one.

    The strongest check available costs nothing, because the series checks itself.
    These sheets are a quadrangle grid numbered row by row, and each carries its
    own printed corner -- so if the reading is right then every sheet's west edge
    lands on a common 0.20-grade lattice, every north edge on a common 0.125-grade
    one, and along any row the sheet numbers run up as the longitude does.

    A single misread decimal cannot satisfy all three. It puts a sheet in a cell
    that is either already taken, off the lattice, or out of order with its own
    neighbours -- and it is otherwise invisible: a sheet 14 km from where it belongs
    still lies flat on the basemap and still looks like a map.
    """
    rows = {r["id"]: r for r in sheets()}
    cells, bad, rims = {}, [], []
    whole_lons, half_lons = set(), set()
    for f in sorted(WORK.glob("*.json")):
        got = json.loads(f.read_text())
        if got.get("verdict"):
            continue
        g, row = got["grades"], rows.get(got["id"], {})
        n = (row.get("extra_metadata") or {}).get("sheet_number", "??")
        cells.setdefault(g["NW"][1], {}).setdefault(g["NW"][0], []).append(
            (n, got["name"], f))
        (half_lons if got.get("cut") else whole_lons).add(g["NW"][0])
        if not got.get("by_hand"):
            real = [v["offset"] for k, v in got["lines"].items()
                    if k != got.get("cut")]
            off = sum(real) / len(real)
            # Against the sheet's HEIGHT, not its width. The margin is a printed
            # constant and the division is only there to be independent of scan
            # resolution -- but this survey has two formats, the full sheet
            # (~4500 px wide) and the demi-format (~2700), and they share their
            # other dimension. Normalised by width, four correctly-read
            # demi-format sheets reported "+100% off the series" while their
            # absolute offsets -- 84.3, 84.2, 84.2, 81.7 px -- were the closest
            # in the corpus to the 84.2 px median. A gate that fires on every
            # sheet of a whole format teaches the reader to ignore it.
            rims.append((off / got["quad"]["h"], off, got["name"]))

    # The frame is printed, so the distance from the thick neatline in to the rim
    # is a constant of the edition -- about 84 px on a 4400 px sheet, everywhere.
    # A sheet far off that did not find the same two lines as the rest, which is
    # the one way a sheet can pass every other check and still be 150 m out: all
    # four sides shifted together change the size but barely the shape.
    if rims:
        med = float(np.median([r[0] for r in rims]))
        print(f"  rim offset: median {med*1e4:.1f} parts per 10k of sheet height "
              f"({np.median([r[1] for r in rims]):.1f} px)")
        out = [r for r in rims if abs(r[0] - med) / med > 0.15]
        for frac, off, name in sorted(out, key=lambda r: -abs(r[0] - med)):
            print(f"  !! {name}: rim {off:.1f}px, {(frac-med)/med*100:+.0f}% off the series")
        print(f"  {len(rims) - len(out)}/{len(rims)} sheets on the series rim, "
              f"{len(out)} to look at\n")
    lons = sorted({lon for r in cells.values() for lon in r})
    lats = sorted(cells, reverse=True)
    if lons:
        # Two lattices, because the survey has two formats. A whole sheet spans a
        # full cell and its west edge is a multiple of 0.20g; a half-sheet spans
        # half a cell, so the east one starts at a half-step. Checked against a
        # single 0.20g lattice the sixteen half-sheets all read "off by 0.500",
        # which is the check misdescribing the paper rather than a misplaced
        # sheet -- and a gate that reports a whole correct format as broken is
        # worse than no gate. Each format is held to its own.
        base = min(whole_lons) if whole_lons else lons[0]
        step_lon = min((b - a) for a, b in zip(lons, lons[1:])) if len(lons) > 1 else 0.2
        ow = [round((x - base) / 0.20, 3) % 1 for x in sorted(whole_lons)]
        oh = [round((x - base) / 0.10, 3) % 1 for x in sorted(half_lons)]
        print(f"  west edges: {len(lons)} distinct, smallest step {step_lon:.3f}g")
        print(f"    {len(whole_lons)} whole-sheet, off the 0.20g lattice by "
              f"{max(ow + [0]):.3f}")
        if half_lons:
            print(f"    {len(half_lons)} half-sheet, off the 0.10g lattice by "
                  f"{max(oh + [0]):.3f}")
    if len(lats) > 1:
        off = [round((lats[0] - y) / 0.125, 3) % 1 for y in lats]
        print(f"  north edges: {len(lats)} distinct, off the 0.125g lattice by "
              f"{max(off + [0]):.3f}\n")
    hdr = "      " + "".join(f"{x:>8.2f}" for x in lons)
    print(hdr)
    for y in lats:
        line = f"{y:6.3f}" + "".join(
            f"{cells[y][x][0][0] if x in cells[y] else '':>8}" for x in lons)
        print(line)
        nums = [(x, cells[y][x][0][0]) for x in lons if x in cells[y]]
        # Four numbers in this series are used twice -- second editions, filed as
        # 00b, 05b, 10b -- so the digits are what orders a row, not the string.
        seq = [int(re.match(r"\d+", str(n)).group())
               for _, n in nums if re.match(r"\d+", str(n))]
        if seq != sorted(seq):
            bad.append(f"row {y}g: sheet numbers out of order {seq}")
    # Two sheets in one cell is either a second edition -- same place, same name,
    # reprinted -- or one of them is in the wrong place. The second is the failure
    # this whole pipeline exists to catch and the only one that gets this far: a
    # sheet whose four corners agree with each other and with its own pixels, and
    # are still wrong. Ha Noi prints 22g,50' where the map it draws is at 23g,25',
    # a clean 0.75g out, and nothing inside that sheet can tell.
    clashes = 0
    for y, row in cells.items():
        for x, here in row.items():
            names = {n for _, n, _ in here}
            if len(names) < 2:
                continue
            clashes += 1
            print(f"  !! {x}g {y}g claimed by {', '.join(sorted(names))}"
                  f" -- holding all of them")
            for _, _, f in here:
                got = json.loads(f.read_text())
                note = f"shares its quadrangle with {', '.join(sorted(names - {got['name']}))}"
                if note not in got["verdict"]:
                    got["verdict"].append(note)
                f.write_text(json.dumps(got, indent=1))
    for b in bad:
        print("  !! " + b)
    placed = sum(len(v) for r in cells.values() for v in r.values())
    print(f"\n  {placed} sheets placed, {len(bad)} rows out of order, "
          f"{clashes} cells claimed twice")


def place(map_id):
    """Take the four corners from a person and run the rest of the pipeline on them.

    Two sheets in this series -- Gia Binh 1911 and Phuc Nhac 1906 -- are a later
    edition with a thin ruled frame instead of the heavy neatline the detector
    anchors on, so on those the argmax finds map content and the fit falls apart.
    Their corners are measured by hand instead. Everything downstream is unchanged:
    the same four-corner reading, the same arbitration against the measured quad,
    the same gate. What a person supplies here is only what the detector could not.

    Reads work/tonkin/hand/<map-id>.json: {"corners": {"NW": [x, y], ...}}.
    """
    hand = json.loads((WORK / "hand" / f"{map_id}.json").read_text())
    base = f"https://iiif.maparchive.vn/iiif/{map_id}"
    info = T.get_image_info(base)
    W, H = info["width"], info["height"]
    got = {"corners": {k: [float(v[0]), float(v[1])] for k, v in hand["corners"].items()},
           "lines": {k: {"res": 0.0, "kept": 0, "found": 0, "offset": hand.get("offset", 0.0)}
                     for k in "LRTB"},
           "by_hand": True}
    got, err = finish(base, W, H, got)
    if err:
        sys.exit(f"place failed: {err}")
    rows = {r["id"]: r for r in sheets()}
    got["id"] = map_id
    got["name"] = rows.get(map_id, {}).get("name", map_id)
    (WORK / f"{map_id}.json").write_text(json.dumps(got, indent=1))
    q = got["quad"]
    print(f"{got['name']}  {W}x{H}  placed by hand")
    for k, v in got["wgs84"].items():
        print(f"  {k} {v[0]:10.5f} E {v[1]:9.5f} N")
    mx, my = got["m_per_px"]
    print(f"  box {q['w']:.1f} x {q['h']:.1f} px   ground scale {mx:.4f} / {my:.4f} m/px"
          f"  ({got['scale_gap']*100:.2f}% apart)")
    print("  verdict: " + ("clear" if not got["verdict"] else
                           "HOLD -- " + "; ".join(got["verdict"])))


def selfcheck():
    """The two pieces whose failure is silent, on numbers small enough to read.

    `rim_in` picking the graticule band instead of the rim, or `grades` dropping a
    decimal, both produce a sheet that lies flat on the basemap and looks right --
    170 m out in the first case, 14 km in the second.
    """
    assert grades("115g,20") == 115.20
    assert grades("115\u1d4d,20'") == 115.20
    assert grades("22\u1d4d,875") == 22.875
    assert grades("22.75") == 22.75
    assert grades("115") == 115.0
    assert grades("") is None and grades(None) is None

    # One side's cross-profile, outside -> inside, with the shape every sheet has:
    # paper, a thin line, the thick neatline, paper, the graticule band, a wide run
    # of paper, the rim pair, then content that never returns to paper.
    p = np.full(340, 26.0)
    p[170:174] = 80                       # thin companion line
    p[185:196] = 165                      # thick neatline   <- `thick`
    p[229:239] = 70                       # graticule band
    p[267:270] = 90                       # rim, outer line
    p[273:277] = 110                      # rim, inner line
    p[278:] = 50                          # map content
    k = np.array([0.25, 0.5, 0.25])       # the scan's own blur; square edges are
    p = np.convolve(p, k, mode="same")    # not a shape any printed line has
    inner, outer = rim_in(p, 190, "inner"), rim_in(p, 190, "outer")
    assert 273 <= inner <= 277, f"inner rim at {inner}, not the pair's inner line"
    assert 266 <= outer <= 270, f"outer rim at {outer}, not the pair's outer line"
    assert rim_in(p, 190, "inner") > 250, "locked onto the band, 40px short"

    # A patch of content that dips towards paper must not be read as the gap.
    q = p.copy()
    q[300:312] = 30
    assert abs(rim_in(q, 190, "inner") - inner) < 1.5, "a pale patch stole the rim"
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["detect", "read", "all", "annotate", "check", "selfcheck", "place"])
    ap.add_argument("map_id", nargs="?")
    ap.add_argument("--which", default="inner", choices=["inner", "outer"])
    ap.add_argument("--shard", help="all: run every n-th sheet, as i/n")
    ap.add_argument("--write", action="store_true",
                    help="annotate: upload and point the rows at it")
    args = ap.parse_args()

    if args.phase == "all":
        run_all(args.which, args.shard)
        return
    if args.phase == "annotate":
        annotate(args.write)
        return
    if args.phase == "check":
        check()
        return
    if args.phase == "selfcheck":
        selfcheck()
        return
    if args.phase == "place":
        place(args.map_id)
        return

    base = T.get_iiif_base_from_supabase(args.map_id)
    info = T.get_image_info(base)
    W, H = info["width"], info["height"]
    print(f"{args.map_id}  {W}x{H}")
    if args.phase == "read":
        got, err = read_sheet(base, W, H, args.which, verbose=True)
    else:
        got, err = detect(base, W, H, args.which, verbose=True)
    if err:
        sys.exit(f"{args.phase} failed: {err}")
    q = got.get("quad") or quad(got)
    for k, v in got["corners"].items():
        print(f"  {k} {v[0]:9.2f} {v[1]:9.2f}")
    print(f"  box {q['w']:.1f} x {q['h']:.1f} px   aspect {q['aspect']:.4f}")
    print(f"  opposite sides {q['opp_x']*100:.2f}% / {q['opp_y']*100:.2f}%   "
          f"diagonals {q['diag']*100:.2f}%")
    if "wgs84" in got:
        g = got["grades"]
        print(f"  printed  NW {g['NW'][0]}g {g['NW'][1]}g   SE {g['SE'][0]}g {g['SE'][1]}g")
        for k, v in got["wgs84"].items():
            print(f"  {k} {v[0]:10.5f} E {v[1]:9.5f} N")
        mx, my = got["m_per_px"]
        print(f"  ground scale {mx:.4f} m/px across, {my:.4f} down "
              f"-- they differ by {got['scale_gap']*100:.2f}%")
        v = got["verdict"]
        print("  verdict: " + ("clear" if not v else "HOLD -- " + "; ".join(v)))


if __name__ == "__main__":
    main()
