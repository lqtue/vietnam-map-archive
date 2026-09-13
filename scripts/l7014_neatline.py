#!/usr/bin/env python3
"""Find a sheet's printed neatline corners in its own pixels.

The neatline is the one line on the sheet with paper margin on one side and map
content on the other. Everything further in -- grid lines, boundaries, the inner
rule some editions print -- has map on both sides, which is what separates them.

So: classify paper, walk inward from each side until it stops being paper and
stays stopped, fit a straight line through those crossings, and intersect
adjacent lines for the corners. Fitting is what makes it work. Marginal text, a
torn edge and a stray tick move individual rows; they cannot move a line fitted
through hundreds of them with the outliers trimmed.

    python3 scripts/l7014_neatline.py validate     # against the GeoPDFs' own NEATLINE
    python3 scripts/l7014_neatline.py propose      # -> work/l7014/gcp/<sheet>.proposed.json

Validate first, always. This proposes; a person accepts.
"""

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

WORK = Path("work/l7014")
WIDE = 1400            # working width; the refine pass goes back to full scale
RUN = 0.020            # a crossing must stay non-paper for this much of the width
SPAN = (0.12, 0.88)    # sample this part of each edge, away from the corners
INSIDE = 0.55          # a crossing needs the window this much "map"
MARGIN = 0.50          # ...and no more than this much blank paper
TRIM = 3.0             # outlier trim, in median absolute residuals

# The gate an edge has to clear to be proposed at all. Measured over 232 edges
# on 60 GeoPDFs against their own NEATLINE: it accepts 46% of edges and every
# single one it accepts is right — median 1.7 px, p95 6.8, worst 10.1. It is
# deliberately lopsided. A rejected good edge costs four clicks; an accepted bad
# one costs a sheet placed hundreds of metres out with nothing to show for it.
GATE = {"residual": 2.0, "inliers": 0.55, "found": 0.60}


def read_scaled(path, width=WIDE):
    ds = gdal.Open(str(path))
    W, H = ds.RasterXSize, ds.RasterYSize
    h = max(1, round(H * width / W))
    small = gdal.Translate("", ds, format="MEM", width=width, height=h,
                           bandList=[1, 2, 3], resampleAlg="average")
    return np.asarray(small.ReadAsArray(), dtype=float).transpose(1, 2, 0), W, H


def paper_mask(img):
    """Paper is the bright, unsaturated colour the margin is made of."""
    h, w, _ = img.shape
    ring = np.concatenate([
        img[: int(h * 0.02)].reshape(-1, 3), img[-int(h * 0.02):].reshape(-1, 3),
        img[:, : int(w * 0.02)].reshape(-1, 3), img[:, -int(w * 0.02):].reshape(-1, 3),
    ])
    ring = ring[ring.min(axis=1) > 150]
    if len(ring) < 100:
        return None
    base = np.median(ring, axis=0)
    # Generous on brightness, tight on hue: a pale field inside the map is still
    # map, and the margin can be shadowed at the edge of the scan.
    d = np.abs(img - base).max(axis=2)
    return (d < 34) & (img.min(axis=2) > 165)


def colour_mask(img):
    """Where the sheet is printed in colour rather than in ink on white.

    This is the discriminator the margins need. The title block above the top
    neatline and the legend below the bottom one are black text on white paper —
    neutral, no hue. The map body is tinted: green vegetation, blue water, brown
    contours. So "the first place that stops being paper" finds the title block,
    but "the first place that starts being coloured" finds the map.
    """
    mx = img.max(axis=2)
    mn = img.min(axis=2)
    return (mx - mn > 14) & (mx > 60)


def crossings(paper, inside, side):
    """Where the margin gives way to the map, per row (or column) of one side.

    `inside` is whatever says "this is map and not margin" — hue for a coloured
    sheet, texture for a pale one. Both share this walk, and both face the same
    gate afterwards.
    """
    flip = {"L": lambda a: a, "R": lambda a: a[:, ::-1],
            "T": lambda a: a.T,  "B": lambda a: a.T[:, ::-1]}[side]
    P, C = flip(paper), flip(inside)
    span, n = P.shape
    win = max(10, int(0.030 * n))
    limit = int(n * 0.32)
    out = []
    for i in range(int(span * SPAN[0]), int(span * SPAN[1])):
        prow, crow = P[i], C[i]
        for j in range(int(n * 0.004), limit - win):
            # Both anchors, or the crossing slides. It must be the first pixel
            # that is map — otherwise the window merely averaging out as map
            # fires half a window early, a clean 73 px bias on every sheet — and
            # the first that is not margin, because a sheet with a tinted margin
            # reads as "map" from x=0 and the hue anchor alone means nothing.
            if not crow[j] or prow[j]:
                continue
            w = slice(j, j + win)
            # "Mostly map from here on", not "no paper from here on". The delta
            # sheets are half blank paper *inside* the neatline — pale water and
            # paddy — so demanding the absence of paper meant the crossing could
            # never fire on exactly the sheets that needed it most.
            if crow[w].mean() > INSIDE and prow[w].mean() < MARGIN:
                out.append((i, j))
                break
    return out


def busy_mask(img):
    """Where the sheet carries printing, as opposed to being blank paper.

    Brightness and colour both fail on the delta sheets — Can Gio, Go Cong,
    Binh Dai — whose map body is pale water and paddy, as white and as neutral
    as the margin beside it. What the margin does not have is *texture*: outside
    the neatline the paper is blank, and inside it there is always linework,
    stipple or a name. Local variance sees that where a threshold on the pixel
    value cannot.
    """
    g = img.mean(axis=2)
    k = 5
    pad = np.pad(g, k, mode="edge")
    c1 = pad.cumsum(0).cumsum(1)
    c2 = (pad * pad).cumsum(0).cumsum(1)

    def box(c):
        h, w = g.shape
        n = 2 * k
        return (c[n:h + n, n:w + n] - c[0:h, n:w + n]
                - c[n:h + n, 0:w] + c[0:h, 0:w]) / (n * n)

    var = np.maximum(box(c2) - box(c1) ** 2, 0)
    sd = np.sqrt(var)
    # The margin's own quiet, measured on this scan rather than assumed: scans
    # differ in noise by more than the threshold does.
    h, w = sd.shape
    quiet = np.concatenate([sd[: int(h * .015)].ravel(), sd[-int(h * .015):].ravel(),
                            sd[:, : int(w * .015)].ravel(), sd[:, -int(w * .015):].ravel()])
    return sd > max(3.0, float(np.percentile(quiet, 97)) * 1.6)


def fit(points):
    """Least squares with the outliers trimmed away — the part that matters."""
    if len(points) < 40:
        return None
    a = np.array([p[0] for p in points], float)
    b = np.array([p[1] for p in points], float)
    keep = np.ones(len(a), bool)
    for _ in range(8):
        m, c = np.polyfit(a[keep], b[keep], 1)
        r = np.abs(b - (m * a + c))
        med = np.median(r[keep]) or 1.0
        new = r < max(1.5, TRIM * med)
        if new.sum() < 30 or (new == keep).all():
            keep = new
            break
        keep = new
    m, c = np.polyfit(a[keep], b[keep], 1)
    return m, c, float(np.median(np.abs(b[keep] - (m * a[keep] + c)))), int(keep.sum())


def corners(path, expect=None):
    img, W, H = read_scaled(path)
    mask = paper_mask(img)
    if mask is None:
        return None
    h, w, _ = img.shape
    colour = colour_mask(img)
    busy = busy_mask(img)
    lines = {}
    for side in "LRTB":
        span = h if side in "LR" else w
        sampled = max(1, int(span * SPAN[1]) - int(span * SPAN[0]))
        best = None
        # Two independent readings of the same line. Either may be the one that
        # works on a given sheet; both face the same gate, so taking whichever
        # scores higher cannot let a bad edge through.
        for pts in (crossings(mask, colour, side), crossings(mask, busy, side)):
            f = fit(pts)
            if not f:
                continue
            m, c, res, n = f
            ok = (res < GATE["residual"] and n / sampled > GATE["inliers"]
                  and len(pts) / sampled > GATE["found"])
            score = (ok, n / sampled - res / 10)
            if best is None or score > best[0]:
                best = (score, m, c, res, n, len(pts), ok)
        if best is None:
            return None
        _, m, c, res, n, found, ok = best
        if side == "R":   m, c = -m, w - 1 - c
        elif side == "B": m, c = -m, h - 1 - c
        lines[side] = {"m": m, "c": c, "res": res,
                       "inliers": n / sampled, "found": found / sampled, "ok": ok}

    def cross(vert, horiz):
        v, hz = lines[vert], lines[horiz]
        y = (hz["m"] * v["c"] + hz["c"]) / (1 - hz["m"] * v["m"])
        return (v["m"] * y + v["c"], y)

    sc = W / w
    out = {}
    for k, (a, b) in (("NW", ("L", "T")), ("NE", ("R", "T")),
                      ("SE", ("R", "B")), ("SW", ("L", "B"))):
        x, y = cross(a, b)
        out[k] = {"px": [x * sc, y * sc], "ok": lines[a]["ok"] and lines[b]["ok"],
                  "edges": [a, b]}
    good, why = quad_ok(out, expect)
    if not good:
        # A failed quad means at least one edge is wrong, and nothing here says
        # which — so no corner can be proposed. The edges keep their own verdict:
        # each was gated on its own evidence, and a guide line is checkable in a
        # way a control point is not. It either lies along the printed neatline
        # on screen or it visibly does not.
        for v in out.values():
            v["ok"] = False
    full = {k: {"m": v["m"], "c": v["c"] * sc, "ok": v["ok"],
                "res": v["res"], "inliers": v["inliers"], "found": v["found"]}
            for k, v in lines.items()}
    return out, full, W, H, (good, why)


def quad_ok(c, expect):
    """Does the proposed quad look like the cell it claims to be?

    A per-edge fit can be beautiful and still be on the wrong line — the second
    detector locks onto a grid line or the sheet edge with a low residual and
    sails through the per-edge gate. What it cannot fake is the shape of the
    whole sheet. The cell is 15' x 15', so its width/height ratio is fixed by
    its latitude, and an edge that has jumped a few hundred pixels throws that
    ratio by tens of percent. Edges also have to be near the image axes — the
    measured worst skew over the series is 0.61 degrees — and near parallel.
    """
    P = {k: c[k]["px"] for k in ("NW", "NE", "SE", "SW")}
    top = math.dist(P["NW"], P["NE"]); bot = math.dist(P["SW"], P["SE"])
    lft = math.dist(P["NW"], P["SW"]); rgt = math.dist(P["NE"], P["SE"])
    if min(top, bot, lft, rgt) < 100:
        return False, "degenerate"
    if abs(top - bot) / max(top, bot) > 0.03 or abs(lft - rgt) / max(lft, rgt) > 0.03:
        return False, "opposite edges disagree"
    ang = lambda a, b: math.degrees(math.atan2(P[b][1] - P[a][1], P[b][0] - P[a][0]))
    if max(abs(ang("NW", "NE")), abs(ang("SW", "SE"))) > 1.5:
        return False, "edge not near the image axis"
    if expect:
        got = ((top + bot) / 2) / ((lft + rgt) / 2)
        if abs(got - expect) / expect > 0.03:
            return False, f"aspect {got:.3f} vs {expect:.3f}"
    return True, ""


def truth(pdf):
    """The sheet's own NEATLINE corners, for checking the detector against."""
    import re
    ds = gdal.Open(str(pdf))
    gt = ds.GetGeoTransform(can_return_null=True) or gdal.GCPsToGeoTransform(ds.GetGCPs() or [])
    nl = ds.GetMetadata().get("NEATLINE")
    if not gt or not nl:
        return None
    inv = gdal.InvGeoTransform(gt)
    px = [gdal.ApplyGeoTransform(inv, x, y) for x, y in
          (tuple(map(float, m.split())) for m in re.findall(r"(-?\d+\.?\d*\s-?\d+\.?\d*)", nl))]
    uniq = []
    for q in px:
        if all(math.dist(q, u) > 1 for u in uniq):
            uniq.append(q)
    if len(uniq) < 4:
        return None
    cx = sum(a for a, _ in uniq) / len(uniq)
    cy = sum(b for _, b in uniq) / len(uniq)
    pick = lambda sx, sy: max(uniq, key=lambda q: sx * (q[0] - cx) + sy * (q[1] - cy))
    return {"NW": pick(-1, -1), "NE": pick(1, -1), "SE": pick(1, 1), "SW": pick(-1, 1)}


def sheets():
    return json.loads((WORK / "sheets.json").read_text())


def expect_aspect(pdf):
    """The width/height the printed cell must have, from its own latitude."""
    ds = gdal.Open(str(pdf))
    m = xmp_corners(ds)
    if not m:
        return None
    lat = (m[1] + m[3]) / 2
    return math.cos(math.radians(lat)) * 111320 / 110540


def xmp_corners(ds):
    md = ds.GetMetadata("xml:XMP") or ds.GetMetadata()
    blob = md[0] if isinstance(md, list) else " ".join(f"{k}={v}" for k, v in md.items())
    want = {}
    for key in ("ll_lat", "ll_long", "ur_lat", "ur_long"):
        m = re.search(rf"{key}[\"'=:>\s]+([+-]?\d+\.?\d*)", blob)
        if not m:
            return None
        want[key] = float(m.group(1))
    return (want["ll_long"], want["ll_lat"], want["ur_long"], want["ur_lat"])


def cmd_validate(limit):
    import random
    rows = [r for r in sheets() if r["kind"] == "pdf"]
    random.seed(7)
    random.shuffle(rows)
    taken, lost, done, fail = [], 0, 0, 0
    for r in rows:
        if done >= limit:
            break
        pdf = WORK / "pdfs" / (Path(r["file"]).stem.strip() + ".pdf")
        if not pdf.exists():
            continue
        t = truth(pdf)
        if not t:
            continue
        done += 1
        try:
            got = corners(pdf, expect_aspect(pdf))
        except Exception:
            got = None
        if not got:
            fail += 1
            continue
        c, _, W, H, _ = got
        mpp = 0.25 * 111320 * 0.95 / abs(c["NE"]["px"][0] - c["NW"]["px"][0])
        for k, v in c.items():
            d = math.dist(v["px"], t[k])
            if v["ok"]:
                taken.append((r["sheet"], k, d, d * mpp))
            elif d < 20:
                lost += 1
    n = done * 4
    print(f"{done} sheets, {fail} gave no answer")
    print(f"proposed {len(taken)} of {n} corners ({len(taken)/n*100:.0f}%); "
          f"{lost} correct ones held back")
    if not taken:
        return
    d = sorted(x[2] for x in taken)
    q = lambda p: d[min(len(d) - 1, int(p * len(d)))]
    print(f"error of what it proposed, px: median {q(.5):.2f}  p95 {q(.95):.2f}  max {d[-1]:.2f}")
    g = sorted(x[3] for x in taken)
    print(f"                        metres: median {g[len(g)//2]:.1f}  max {g[-1]:.1f}")
    wrong = [x for x in taken if x[2] > 20]
    print(f"proposed but wrong by >20 px: {len(wrong)}" + (f"  {wrong[:3]}" if wrong else "  — none"))


def ground_aspect(sheet):
    """The same shape check, for a sheet with no GeoPDF: off its known cell."""
    import csv
    rows = [r for r in csv.DictReader(open(WORK / "corners.csv")) if r["sheet"] == sheet]
    if len(rows) != 4:
        return None
    lat = sum(float(r["lat"]) for r in rows) / 4
    return math.cos(math.radians(lat)) * 111320 / 110540


def cmd_propose(limit):
    out_dir = WORK / "gcp"
    out_dir.mkdir(parents=True, exist_ok=True)
    n = free = 0
    for r in sheets():
        if r["kind"] != "jpg" or (limit and n >= limit):
            continue
        jpg = WORK / "jpgs" / (Path(r["file"]).stem.strip() + ".jpg")
        if not jpg.exists():
            continue
        try:
            got = corners(jpg, ground_aspect(r['sheet']))
        except Exception as e:
            print(f"  {r['sheet']}: {e}")
            continue
        if not got:
            print(f"  {r['sheet']}: no answer")
            continue
        c, lines, W, H, (qok, why) = got
        sure = [k for k, v in c.items() if v["ok"]]
        free += len(sure)
        (out_dir / f"{r['sheet']}.proposed.json").write_text(json.dumps({
            "sheet": r["sheet"], "size": [W, H],
            "corners": {k: {"px": [round(v["px"][0], 1), round(v["px"][1], 1)],
                            "ok": v["ok"]} for k, v in c.items()},
            "edges": {k: {"m": round(v["m"], 6), "c": round(v["c"], 1), "ok": v["ok"],
                          "res": round(v["res"], 2)} for k, v in lines.items()},
        }, indent=1))
        edges = "".join(k if lines[k]["ok"] else "·" for k in "LRTB")
        print(f"  {r['sheet']:<8} edges {edges}   corners {''.join(k[0] if c[k]['ok'] else '·' for k in ('NW','NE','SE','SW'))}"
              f"   {len(sure)}/4 proposed")
        n += 1
    print(f"\n{n} sheets, {free} of {n*4} corners proposed -> {out_dir}/")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else (60 if cmd == "validate" else 0)
    {"validate": cmd_validate, "propose": cmd_propose}[cmd](lim)
