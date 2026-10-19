#!/usr/bin/env python3
"""Series 325 (1st éd. SGI, 1900-47): place a sheet from the grade lines it prints.

Every 325 sheet prints thin graticule lines across the map (Paris grades every 0.2 g, or Greenwich
degrees every 5') and the map border. Both systems are tried per sheet; the one that passes the gates is kept. The catalogue box only says which lines to expect; their pixel positions fix the
placement. The map border is then compared with the catalogue box as an outside check.

Read-only: fetches images, writes local JSON and an overlay PNG under work/indochine-100k/325-graticule/.
No database writes.

    work/ocr/.venv/bin/python scripts/indochine100k/indochine325_graticule.py probe <map-id> [<map-id> ...]
    work/ocr/.venv/bin/python scripts/indochine100k/indochine325_graticule.py sample 10
    work/ocr/.venv/bin/python scripts/indochine100k/indochine325_graticule.py --self-test
"""
import argparse
import itertools
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw
from scipy.ndimage import median_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indochine100k_georef as geo  # noqa: E402

T = geo.T
OUT = geo.WORK / "325-graticule"
COLLECTION = "Indochine 1:100,000 — 1st édition SGI (1900–1947)"
# unit = what the printed lines count in; k = degrees per unit; f = grades-to-unit factor for the grade-sized constants below
PARIS = dict(name="paris", step=0.2, k=0.9, off=geo.PARIS, f=1.0)
GREENWICH = dict(name="greenwich", step=1 / 12, k=1.0, off=0.0, f=0.9)
SYSTEMS = (PARIS, GREENWICH)
TARGET_W = 2600                    # work width in px; line fits are sub-pixel
SLOPES = np.arange(-0.012, 0.01201, 0.0006)
LINE_THR = 14                      # tophat darkness for a line candidate
# Faint mode, tried only when the normal pass fails (lowering the threshold for every sheet broke 7 of the 9 passing ones):
LINE_FLOOR = 5                     # faint sea-sheet lines are 5-13 deep
LINE_NOISE_K = 6                   # a faint candidate must also beat this many times the profile's median |tophat|
TRACE_MIN_PEAK = 18                # per-window peak a traced line needs; faint lines get 0.7 x their candidate strength
# Printed border minus catalogue edge, in grades, median of the first 6 solved sheets (about -175/-130/-90/-105 m):
# the catalogue boxes sit a little north-east of the print. Used only to centre the border search window.
CATALOGUE_BIAS_G = dict(w=-0.0017, e=-0.0012, n=-0.0009, s=-0.0011)
AHEAD_PX = 7                       # inward window of the texture step (30 px pulled the edge outward on 4 sheets)
BORDER_WINDOW_G = 0.004            # half-width of that window, about 440 m
MIN_CONTRAST = 3.0                 # texture (grey change per 4 px): a border has map inside and paper outside
RES_MAX_M = 30.0                   # crossings must agree with one affine to this many metres
FIT_RMS_MAX = 1.5                  # px at work scale
M_LAT, M_LON0 = 110900.0, 111320.0


# ---- catalogue ------------------------------------------------------------------------------

def catalogue_boxes():
    by_fkey = {}
    for records in json.loads((geo.WORK / "sources/serie-325.json").read_text())["cells"].values():
        for rec in records:
            by_fkey[str(rec["fkey"])] = rec
    return by_fkey


def box_of(row, records):
    """Catalogue box of a sheet in degrees (Greenwich). Every fkey of the row must agree."""
    keys = (row.get("extra_metadata") or {}).get("cartomundi_fkeys") or []
    boxes = set()
    for k in keys:
        u = (records.get(str(k)) or {}).get("unimarc") or {}
        v = {s: geo.unimarc(u.get(s)) for s in "wens"}
        if None in v.values():
            continue
        boxes.add(tuple(v[s] for s in "wens"))
    if len(boxes) != 1:
        return None
    w, e, n, s = boxes.pop()
    return dict(west=w, east=e, north=n, south=s)


def to_grades(lon, lat, sy=PARIS):
    """Degrees to the system's own units (grades for Paris, degrees for Greenwich)."""
    return (lon - sy["off"]) / sy["k"], lat / sy["k"]


def from_grades(lon_g, lat_g, sy=PARIS):
    return lon_g * sy["k"] + sy["off"], lat_g * sy["k"]


def expected_lines(lo_g, hi_g, margin, sy):
    """Multiples of the system's line step strictly inside (lo_g, hi_g)."""
    step = sy["step"]
    k0 = int(np.ceil((lo_g + margin) / step - 1e-9))
    k1 = int(np.floor((hi_g - margin) / step + 1e-9))
    return [round(k * step, 6) for k in range(k0, k1 + 1)]


# ---- line detection -------------------------------------------------------------------------

def tophat(p, k=9):
    return median_filter(p, size=2 * k + 1, mode="nearest") - p


def groups(idx, gap=3):
    out = []
    for x in idx:
        if out and x - out[-1][-1] <= gap:
            out[-1].append(x)
        else:
            out.append([x])
    return out


def sheared_profile(img, slope, lo, hi, step=3):
    """Mean over rows lo..hi of img sampled along lines x = x0 + slope*(y-ymid)."""
    ys = np.arange(lo, hi, step)
    sh = np.rint(slope * (ys - (lo + hi) / 2)).astype(int)
    idx = (np.arange(img.shape[1])[None, :] + sh[:, None]).clip(0, img.shape[1] - 1)
    return img[ys[:, None], idx].astype(np.float32).mean(axis=0)


def candidate_lines(img, lo, hi, faint=False):
    """Long dark lines running along the rows lo..hi: [{pos at ymid, slope, strength}], strongest first."""
    found = []
    for s in SLOPES:
        t = tophat(sheared_profile(img, s, lo, hi))
        thr = max(LINE_FLOOR, LINE_NOISE_K * float(np.median(np.abs(t)))) if faint else LINE_THR
        for g in groups(np.where(t > thr)[0]):
            w = np.clip(t[g], 0, None)
            found.append(dict(pos=float(np.average(g, weights=w)), slope=float(s), strength=float(t[g].max())))
    found.sort(key=lambda c: -c["strength"])
    kept = []
    for c in found:
        if all(abs(c["pos"] - k["pos"]) > 4 for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c["pos"])


def trace(img, mid, slope, lo, hi, halfw=10, win=96, minpeak=TRACE_MIN_PEAK):
    """Fit the line x = c + m*(y-ymid) near (mid, slope) along rows lo..hi; None if it does not hold."""
    ymid = (lo + hi) / 2
    pts = []
    d = np.arange(-halfw, halfw + 1)
    for y0 in range(lo, hi - win, win // 2):
        ys = np.arange(y0, y0 + win)
        yc = ys.mean()
        xp = mid + slope * (ys - ymid)
        idx = np.rint(xp[:, None] + d[None, :]).astype(int).clip(0, img.shape[1] - 1)
        t = np.median(prof := img[ys[:, None], idx].astype(np.float32).mean(axis=0)) - prof
        i = int(np.argmax(t))
        if t[i] < minpeak or i in (0, len(d) - 1):
            continue
        a, b = max(0, i - 2), i + 3
        w = np.clip(t[a:b] - t[i] * .5, 0, None)
        sub = (w * d[a:b]).sum() / w.sum() if w.sum() > 0 else d[i]
        pts.append((yc, mid + slope * (yc - ymid) + sub))
    pts = np.array(pts)
    if len(pts) < 8:
        return None
    keep = np.ones(len(pts), bool)
    for _ in range(5):
        A = np.c_[np.ones(keep.sum()), pts[keep, 0] - ymid]
        c, m = np.linalg.lstsq(A, pts[keep, 1], rcond=None)[0]
        res = pts[:, 1] - (c + m * (pts[:, 0] - ymid))
        keep = np.abs(res) < max(1.5, 2.5 * np.std(res[keep]))
    return dict(c=float(c), m=float(m), ymid=float(ymid), rms=float(np.sqrt(np.mean(res[keep] ** 2))),
                n=int(keep.sum()), of=len(pts))


def at(L, t):
    return L["c"] + L["m"] * (t - L["ymid"])


def cross(V, Hh):
    """Intersection of x=V(y) and y=H(x)."""
    y = Hh["c"]
    for _ in range(20):
        x = at(V, y)
        y = at(Hh, x)
    return x, y


def edge_contrast(img, pos, slope, lo, hi, inward, deep=32, shallow=9):
    """Ink texture over a deep strip just inside the line minus a shallow strip just outside it.

    The deep strip tells the map border from the narrow ticked band and the frame rules further out: the map
    runs far inward of the border, but only a band's width inward of those. Texture is the change of grey along
    the line, so lines parallel to the border add nothing and blank paper reads ~0 however stained."""
    ys = np.arange(lo, hi - 4, 3)
    xc = pos + slope * (ys - (lo + hi) / 2)

    def texture(a, b):
        d = np.arange(a, b + 1)
        idx = np.rint(xc[:, None] + inward * d[None, :]).astype(int).clip(0, img.shape[1] - 1)
        return np.abs(img[ys[:, None] + 4, idx] - img[ys[:, None], idx]).mean()

    return float(texture(2, deep) - texture(-shallow, -2))


def find_edge(img, lo, hi, want, tol, inward):
    """Where the map starts: the offset (and shear) in want+-tol at which ink texture steps up going `inward`.

    Texture is the change of grey along the line, so lines parallel to the border add nothing and blank
    paper reads ~0 however dark or stained it is. img has the line running along its rows (+1 inward =
    map toward larger x). Positions are at the middle of rows lo..hi. Returns dict(pos, slope, score)."""
    ys = np.arange(lo, hi - 4, 3)
    ymid = (lo + hi) / 2
    pad, k_in, k_out = 40, AHEAD_PX, 8
    ds = np.arange(-int(tol) - pad, int(tol) + pad + 1)
    best = None
    for s in SLOPES:
        idx = np.rint(want + s * (ys - ymid)[:, None] + ds[None, :]).astype(int).clip(0, img.shape[1] - 5)
        tex = np.abs(img[ys[:, None] + 4, idx] - img[ys[:, None], idx]).mean(axis=0)
        for j in range(pad, len(ds) - pad):
            if not -tol <= ds[j] <= tol:
                continue
            if inward > 0:
                score = tex[j + 2:j + 2 + k_in].mean() - tex[j - 2 - k_out:j - 2].mean()
            else:
                score = tex[j - 2 - k_in:j - 2].mean() - tex[j + 2:j + 2 + k_out].mean()
            if best is None or score > best["score"]:
                best = dict(pos=float(want + ds[j]), slope=float(s), score=float(score))
    return best


def pick_border(cands, extent, fracs, strengths_floor=25):
    """Choose the (low, high) border pair of lines that explains the expected grade lines.

    cands: candidate lines along one axis. fracs: expected grade-line positions as fractions of the way
    from the low to the high border. Score = border strength + the strength found at each predicted line."""
    best = None
    for lo, hi in itertools.combinations([c for c in cands if c["strength"] >= strengths_floor], 2):
        span = hi["pos"] - lo["pos"]
        if span < 0.45 * extent or span > 0.97 * extent:
            continue
        score = lo["strength"] + hi["strength"]
        hits = []
        for f in fracs:
            want = lo["pos"] + f * span
            near = [c for c in cands if abs(c["pos"] - want) < max(20, 0.02 * span) and c is not lo and c is not hi]
            if not near:
                score -= 80
                hits.append(None)
                continue
            c = min(near, key=lambda c: abs(c["pos"] - want))
            score += c["strength"]
            hits.append(c)
        if best is None or score > best[0]:
            best = (score, lo, hi, hits)
    return best


def refine_hits(cands, hits, grades, window=80, max_rms=3.0):
    """With 3+ lines on an axis, positions must be linear in grade (equal spacing). Search every combination
    of candidates near the first guesses and keep the most evenly spaced, strongest one; None if none fits."""
    if len(hits) < 3 or any(h is None for h in hits):
        return hits
    pools = [[c for c in cands if abs(c["pos"] - h["pos"]) <= window] for h in hits]
    g_ = np.array(grades)
    best = None
    for combo in itertools.product(*pools):
        pos = np.array([c["pos"] for c in combo])
        if len(set(round(p) for p in pos)) < len(pos):
            continue
        A = np.c_[np.ones(len(g_)), g_]
        coef = np.linalg.lstsq(A, pos, rcond=None)[0]
        rms = float(np.sqrt(np.mean((A @ coef - pos) ** 2)))
        if rms > max_rms:
            continue
        score = sum(c["strength"] for c in combo) - 40 * rms
        if best is None or score > best[0]:
            best = (score, list(combo))
    return best[1] if best else [None] * len(hits)


# ---- one sheet ------------------------------------------------------------------------------

def fetch_gray(row):
    base = row["iiif_image"]
    info = requests.get(base.rstrip("/") + "/info.json", timeout=30).json()
    W, H = info["width"], info["height"]
    scale = max(1, round(W / TARGET_W))
    im = T.fetch_crop_level0(base, 0, 0, W, H, W // scale, max_workers=8).convert("L")
    return np.asarray(im, np.float32), scale, (W, H)


EDGE_TOL = 0.004                   # a catalogue edge this close to a grade multiple IS that grade line
SCALE_TOL = 0.04                   # lon/lat px-per-grade may differ this much (paper shrink + projection)


def solve(img, box, sy=PARIS, faint=False):
    """Locate the graticule lines and the map border in img; returns a result dict (no network).

    Half the sheets are cut on a grade line (catalogue edge within EDGE_TOL g of a multiple of 0.2), so
    the printed border is itself a grade line and counts as one."""
    H, W = img.shape
    step, f = sy["step"], sy["f"]
    edge_tol, border_win = EDGE_TOL * f, BORDER_WINDOW_G * f
    bias = {k: v * f for k, v in CATALOGUE_BIAS_G.items()}
    g = dict(w=to_grades(box["west"], 0, sy)[0], e=to_grades(box["east"], 0, sy)[0],
             n=to_grades(0, box["north"], sy)[1], s=to_grades(0, box["south"], sy)[1])
    aligned = {k: round(round(v / step) * step, 6) for k, v in g.items()
               if abs(v - round(v / step) * step) <= edge_tol}
    lon_lines = expected_lines(g["w"], g["e"], edge_tol, sy)
    lat_lines = expected_lines(g["s"], g["n"], edge_tol, sy)
    out = dict(system=sy["name"] + ("+faint" if faint else ""), expected_lon=lon_lines, expected_lat=lat_lines, aligned_edges=aligned)
    if not lon_lines or len(lat_lines) < 2:
        out["status"] = "fewer interior grade lines than the method needs (1 lon, 2 lat)"
        return out
    vc = candidate_lines(img, int(.12 * H), int(.88 * H), faint)
    hc = candidate_lines(img.T.copy(), int(.12 * W), int(.88 * W), faint)
    fv = [(l - g["w"]) / (g["e"] - g["w"]) for l in lon_lines]
    fh = [(g["n"] - l) / (g["n"] - g["s"]) for l in lat_lines]
    bv, bh = pick_border(vc, W, fv), pick_border(hc, H, fh)
    if bv is None or bh is None:
        out["status"] = "no border pair"
        return out
    _, L, R, vhits = bv
    _, Tp, B, hhits = bh
    vhits = refine_hits(vc, vhits, lon_lines)
    hhits = refine_hits(hc, hhits, lat_lines)
    out["border_candidates"] = dict(L=L["pos"], R=R["pos"], T=Tp["pos"], B=B["pos"])
    out["expected_hits"] = dict(lon=[None if h is None else h["pos"] for h in vhits],
                                lat=[None if h is None else h["pos"] for h in hhits])
    if None in vhits or None in hhits:
        out["status"] = "graticule line not found near its predicted position"
        return out
    vy = (int(Tp["pos"] + .04 * (B["pos"] - Tp["pos"])), int(B["pos"] - .04 * (B["pos"] - Tp["pos"])))
    hx = (int(L["pos"] + .04 * (R["pos"] - L["pos"])), int(R["pos"] - .04 * (R["pos"] - L["pos"])))
    imgT = img.T.copy()
    ov = (int(.12 * H), int(.88 * H))
    oh = (int(.12 * W), int(.88 * W))

    V = {f"lon{l}": trace(img, anchor(c, *vy, ov), c["slope"], *vy, minpeak=min_peak(c, faint)) for l, c in zip(lon_lines, vhits)}
    Hl = {f"lat{l}": trace(imgT, anchor(c, *hx, oh), c["slope"], *hx, minpeak=min_peak(c, faint)) for l, c in zip(lat_lines, hhits)}
    if any(v is None for v in {**V, **Hl}.values()):
        out["status"] = "graticule line did not trace"
        out["lines"] = {**V, **Hl}
        return out
    vm, hm = (vy[0] + vy[1]) / 2, (hx[0] + hx[1]) / 2
    xs = [at(V[f"lon{l}"], vm) for l in lon_lines]
    ys = [at(Hl[f"lat{l}"], hm) for l in lat_lines]
    dy = (ys[0] - ys[-1]) / (lat_lines[-1] - lat_lines[0])      # px per grade, vertical
    lat_mid = np.mean([g["n"], g["s"]]) * sy["k"]
    if len(lon_lines) >= 2:
        dx, dx_known = (xs[-1] - xs[0]) / (lon_lines[-1] - lon_lines[0]), True
    else:                                                       # one lon line: scale from the lat axis
        dx, dx_known = dy * np.cos(np.radians(lat_mid)) * M_LON0 / M_LAT, False
    gb = {k: g[k] + bias[k] for k in g}
    want = dict(L=xs[0] - (lon_lines[0] - gb["w"]) * dx, R=xs[0] + (gb["e"] - lon_lines[0]) * dx,
                T=ys[0] - (gb["n"] - lat_lines[0]) * dy, B=ys[0] + (lat_lines[0] - gb["s"]) * dy)
    slack = (lambda dist: 0) if dx_known else (lambda dist: SCALE_TOL * dist)
    tol = dict(L=border_win * dx + slack(abs(xs[0] - want["L"])), R=border_win * dx + slack(abs(want["R"] - xs[0])),
               T=border_win * dy, B=border_win * dy)
    mid_x, mid_y = (want["L"] + want["R"]) / 2, (want["T"] + want["B"]) / 2

    def border_line(side, img_, lo, hi, inward):
        e = find_edge(img_, lo, hi, want[side], tol[side], inward)
        out.setdefault("border_scores", {})[side] = None if e is None else {k: round(v, 2) for k, v in e.items()}
        return e if e is not None and e["score"] >= MIN_CONTRAST else None

    bl = {"L": border_line("L", img, *vy, 1), "R": border_line("R", img, *vy, -1),
          "T": border_line("T", imgT, *hx, 1), "B": border_line("B", imgT, *hx, -1)}
    out["lines"] = {**V, **Hl}
    if None in bl.values():
        out["status"] = f"no border line near the predicted edge: {[k for k, v in bl.items() if v is None]}"
        return out
    for name in "LR":
        V[name] = trace(img, bl[name]["pos"], bl[name]["slope"], *vy, halfw=8)
    for name in "TB":
        Hl[name] = trace(imgT, bl[name]["pos"], bl[name]["slope"], *hx, halfw=8)
    out["lines"] = {**V, **Hl}
    if any(V[k] is None or Hl[j] is None for k in "LR" for j in "TB"):
        out["status"] = "border line did not trace"
        return out
    return fit_and_report(out, V, Hl, lon_lines, lat_lines, aligned, box, sy)


def anchor(c, lo, hi, old):
    """Candidate pos is at the midpoint of the span it was found over; move it to the midpoint of rows lo..hi."""
    return c["pos"] + c["slope"] * ((lo + hi) / 2 - (old[0] + old[1]) / 2)


def min_peak(c, faint):
    return min(TRACE_MIN_PEAK, max(LINE_FLOOR, 0.7 * c["strength"])) if faint else TRACE_MIN_PEAK


def fit_and_report(out, V, Hl, lon_lines, lat_lines, aligned, box, sy):
    """Shared tail: V/Hl hold traced grade lines (lonX / latX) and borders (L R T B). Gates, affine, corners."""
    # A border cut on a grade line is that line. Which edges really are is decided by the fit: try every
    # subset of the aligned edges and keep the most lines whose crossings agree to RES_MAX_M.
    interior_v = {l: V[f"lon{l}"] for l in lon_lines}
    interior_h = {l: Hl[f"lat{l}"] for l in lat_lines}
    edge_lines = [(e, n) for e, n in (("w", "L"), ("e", "R"), ("n", "T"), ("s", "B")) if e in aligned]
    bad = [k for k, v in {**V, **Hl}.items() if k.startswith(("lon", "lat")) and v["rms"] > FIT_RMS_MAX]
    if bad:
        out["status"] = f"line fit failed: {sorted(bad)}"
        return out
    best = None
    for r in range(len(edge_lines), -1, -1):
        for subset in itertools.combinations(edge_lines, r):
            grat_v, grat_h = dict(interior_v), dict(interior_h)
            for e, n in subset:
                (grat_v if n in "LR" else grat_h)[aligned[e]] = (V if n in "LR" else Hl)[n]
            if len(grat_v) < 2 or len(grat_h) < 2:
                continue
            fit_ = affine(grat_v, grat_h, sy)
            if fit_["max_res"] <= RES_MAX_M and abs(fit_["ratio"] - 1) <= SCALE_TOL and (best is None or (r, -fit_["max_res"]) > (best[0], -best[2]["max_res"])):
                best = (r, subset, fit_, grat_v, grat_h)
    if best is None:
        out["status"] = f"grade lines disagree: no subset fits within {RES_MAX_M:.0f} m and the lon/lat scale ratio"
        out["aligned_trials"] = {str(s_): None for s_ in edge_lines}
        return out
    _, subset, fit_, grat_v, grat_h = best
    cl, cb = fit_["cl"], fit_["cb"]
    out["affine_residual_m"] = fit_["res_m"]
    out["xy_scale_ratio"] = round(fit_["ratio"], 4)
    out["grade_lines"] = dict(lon=sorted(grat_v), lat=sorted(grat_h))
    out["borders_used_as_grade_lines"] = [e for e, _ in subset]
    corners = {}
    for k, (vn, hn) in {"NW": ("L", "T"), "NE": ("R", "T"), "SE": ("R", "B"), "SW": ("L", "B")}.items():
        x, y = cross(V[vn], Hl[hn])
        lon, lat = from_grades(cl[0] + cl[1] * x + cl[2] * y, cb[0] + cb[1] * x + cb[2] * y, sy)
        corners[k] = dict(px=[round(float(x), 1), round(float(y), 1)], lon=float(lon), lat=float(lat))
    out["corners"] = corners
    lons = [c["lon"] for c in corners.values()]
    lats = [c["lat"] for c in corners.values()]
    mlon2 = M_LON0 * np.cos(np.radians(np.mean(lats)))
    out["catalogue_gap_m"] = dict(
        W=round((min(lons) - box["west"]) * mlon2), E=round((max(lons) - box["east"]) * mlon2),
        N=round((max(lats) - box["north"]) * M_LAT), S=round((min(lats) - box["south"]) * M_LAT))
    # every solved sheet so far has all four gaps in [-350, +150] m; outside that the border pick is suspect
    gap = out["catalogue_gap_m"]
    out["border_suspect"] = any(not -350 <= v <= 150 for v in gap.values())
    out["status"] = "ok"
    return out


# ---- lines first (ponytail: replaces solve if it wins on the fresh sample; delete the loser) -------

FRAME_ZONE = 0.18                  # the frame band lies in this outer fraction of the image
FRAME_GAP = 0.0135                 # rules closer than this fraction of the axis belong to one band (~35 px at 2600)
COMB_PRINT = 0.9                   # prior: the printed area fills ~90 % of the scan, centred
COMB_WINDOW = 0.10                 # a line may sit this fraction of the axis from where that prior puts it
COMB_SPACING = (0.85, 1.12)        # allowed px-per-unit against the prior
COMB_RMS = 3.0                     # px, equal spacing over 3+ lines


def frame_rules(cands, extent):
    """Frame band at each end of one axis: (inner rule at the low end, inner rule at the high end, both bands).

    The band is the cluster of strong rules (outer rules, ticked band, neat line) in the outer FRAME_ZONE;
    the map border is its innermost rule. No catalogue involved."""
    strong = [c for c in cands if c["strength"] >= 25]

    def band(zone):
        groups_ = []
        for c in sorted(zone, key=lambda c: c["pos"]):
            if groups_ and c["pos"] - groups_[-1][-1]["pos"] <= FRAME_GAP * extent:
                groups_[-1].append(c)
            else:
                groups_.append([c])
        return max(groups_, key=lambda g: sum(c["strength"] for c in g), default=None)

    lo = band([c for c in strong if c["pos"] < FRAME_ZONE * extent])
    hi = band([c for c in strong if c["pos"] > (1 - FRAME_ZONE) * extent])
    return (lo[-1] if lo else None), (hi[0] if hi else None), (lo or []), (hi or [])


def comb(cands, extent, lines, lo, hi, flip, exclude, faint):
    """One candidate per expected line, equally spaced, anywhere in a wide window: the catalogue only NAMES the lines.

    lo..hi is the catalogue span in the system's units (flip: positions fall as values rise, the lat axis).
    Returns a list of candidates in line order, or None."""
    b0 = COMB_PRINT * extent / (hi - lo)
    sgn = -1 if flip else 1
    pred = [extent / 2 + sgn * (l - (lo + hi) / 2) * b0 for l in lines]
    floor = LINE_FLOOR if faint else LINE_THR
    pools = [sorted([c for c in cands if id(c) not in exclude and c["strength"] >= floor
                     and abs(c["pos"] - p) <= COMB_WINDOW * extent], key=lambda c: -c["strength"])[:8] for p in pred]
    best = [None, None]

    def rec(i, chosen):
        if i == len(lines):
            pos = np.array([c["pos"] for c in chosen])
            rms = 0.0
            if len(lines) >= 3:
                A = np.c_[np.ones(len(lines)), lines]
                rms = float(np.sqrt(np.mean((A @ np.linalg.lstsq(A, pos, rcond=None)[0] - pos) ** 2)))
                if rms > COMB_RMS:
                    return
            score = sum(c["strength"] for c in chosen) - 40 * rms - 0.1 * float(np.abs(pos - pred).sum())
            if best[0] is None or score > best[0]:
                best[:] = [score, list(chosen)]
            return
        for c in pools[i]:
            if chosen:
                d, want_d = (c["pos"] - chosen[-1]["pos"]) * sgn, b0 * (lines[i] - lines[i - 1])
                if not COMB_SPACING[0] * want_d <= d <= COMB_SPACING[1] * want_d:
                    continue
            rec(i + 1, chosen + [c])

    rec(0, [])
    return best[1]


def solve2(img, box, sy=PARIS, faint=False):
    """Lines first, border last. Same gates as solve; the border is the innermost frame rule, not a catalogue window."""
    H, W = img.shape
    step, f = sy["step"], sy["f"]
    edge_tol = EDGE_TOL * f
    g = dict(w=to_grades(box["west"], 0, sy)[0], e=to_grades(box["east"], 0, sy)[0],
             n=to_grades(0, box["north"], sy)[1], s=to_grades(0, box["south"], sy)[1])
    aligned = {k: round(round(v / step) * step, 6) for k, v in g.items()
               if abs(v - round(v / step) * step) <= edge_tol}
    lon_lines = expected_lines(g["w"], g["e"], edge_tol, sy)
    lat_lines = expected_lines(g["s"], g["n"], edge_tol, sy)
    out = dict(system=sy["name"] + ("+faint" if faint else "") + "/lines", expected_lon=lon_lines,
               expected_lat=lat_lines, aligned_edges=aligned)
    if not lon_lines or len(lat_lines) < 2:
        out["status"] = "fewer interior grade lines than the method needs (1 lon, 2 lat)"
        return out
    imgT = img.T.copy()
    ov, oh = (int(.12 * H), int(.88 * H)), (int(.12 * W), int(.88 * W))
    vc = candidate_lines(img, *ov, faint)
    hc = candidate_lines(imgT, *oh, faint)
    L, R, lcl, rcl = frame_rules(vc, W)
    Tp, B, tcl, bcl = frame_rules(hc, H)
    if None in (L, R, Tp, B):
        out["status"] = "no frame band found"
        return out
    # the inner rule stays available: a sheet cut on a grade line has the neat line AS that line
    frame = {id(c) for cl, inner in ((lcl, L), (rcl, R), (tcl, Tp), (bcl, B)) for c in cl if c is not inner}
    vhits = comb(vc, W, lon_lines, g["w"], g["e"], False, frame, faint)
    hhits = comb(hc, H, lat_lines, g["s"], g["n"], True, frame, faint)
    out["border_candidates"] = dict(L=L["pos"], R=R["pos"], T=Tp["pos"], B=B["pos"])
    if vhits is None or hhits is None:
        out["status"] = "graticule lines not found as an equally spaced set"
        return out
    vy = (int(Tp["pos"] + .04 * (B["pos"] - Tp["pos"])), int(B["pos"] - .04 * (B["pos"] - Tp["pos"])))
    hx = (int(L["pos"] + .04 * (R["pos"] - L["pos"])), int(R["pos"] - .04 * (R["pos"] - L["pos"])))
    V = {f"lon{l}": trace(img, anchor(c, *vy, ov), c["slope"], *vy, minpeak=min_peak(c, faint)) for l, c in zip(lon_lines, vhits)}
    Hl = {f"lat{l}": trace(imgT, anchor(c, *hx, oh), c["slope"], *hx, minpeak=min_peak(c, faint)) for l, c in zip(lat_lines, hhits)}
    if any(v is None for v in {**V, **Hl}.values()):
        out["status"] = "graticule line did not trace"
        out["lines"] = {**V, **Hl}
        return out
    for name, c in (("L", L), ("R", R)):
        V[name] = trace(img, anchor(c, *vy, ov), c["slope"], *vy, halfw=8)
    for name, c in (("T", Tp), ("B", B)):
        Hl[name] = trace(imgT, anchor(c, *hx, oh), c["slope"], *hx, halfw=8)
    out["lines"] = {**V, **Hl}
    if any(V[k] is None or Hl[j] is None for k in "LR" for j in "TB"):
        out["status"] = "border line did not trace"
        return out
    return fit_and_report(out, V, Hl, lon_lines, lat_lines, aligned, box, sy)


def affine(grat_v, grat_h, sy=PARIS):
    """pixel (x, y) -> (lon, lat) in the system's units from every crossing of a vertical and a horizontal grade line."""
    pts = []
    for l_lon, lv in grat_v.items():
        for l_lat, lh in grat_h.items():
            x, y = cross(lv, lh)
            pts.append((x, y, l_lon, l_lat))
    P = np.array(pts)
    A = np.c_[np.ones(len(P)), P[:, 0], P[:, 1]]
    cl = np.linalg.lstsq(A, P[:, 2], rcond=None)[0]
    cb = np.linalg.lstsq(A, P[:, 3], rcond=None)[0]
    k = sy["k"]
    mlon = M_LON0 * np.cos(np.radians(np.mean(P[:, 3]) * k))
    res = np.hypot((A @ cl - P[:, 2]) * k * mlon, (A @ cb - P[:, 3]) * k * M_LAT)
    # x-scale over y-scale against what the ground predicts at this latitude (paper shrinks a little)
    ratio = abs(cb[2] / cl[1]) / (np.cos(np.radians(np.mean(P[:, 3]) * k)) * M_LON0 / M_LAT)
    return dict(cl=cl, cb=cb, res_m=[round(float(r), 1) for r in res], max_res=float(res.max()), ratio=float(ratio))


def overlay(img, res, path):
    im = Image.fromarray(img.astype("uint8")).convert("RGB")
    d = ImageDraw.Draw(im)
    for k, v in (res.get("lines") or {}).items():
        if v is None:
            continue
        col = (220, 0, 0) if k.startswith(("lon", "lat")) else (0, 90, 220)
        if k.startswith("lon") or k in "LR":
            d.line([(at(v, y), y) for y in (0, img.shape[0])], fill=col, width=2)
        else:
            d.line([(x, at(v, x)) for x in (0, img.shape[1])], fill=col, width=2)
    r = 900 / im.width
    im.resize((900, round(im.height * r))).save(path)


SOLVE = solve


def probe(row, records):
    box = box_of(row, records)
    if box is None:
        return dict(id=row["id"], name=row["name"], status="no single catalogue box")
    t0 = time.time()
    img, scale, size = fetch_gray(row)
    # try both printed systems; keep the one that passes the gates (clean border first, then the tighter fit)
    tries = [SOLVE(img, box, sy) for sy in SYSTEMS]
    if not any(t["status"] == "ok" for t in tries):
        tries += [SOLVE(img, box, sy, faint=True) for sy in SYSTEMS]
    passed = [t for t in tries if t["status"] == "ok"]
    res = (min(passed, key=lambda t: (t["border_suspect"], max(t["affine_residual_m"]))) if passed
           else tries[0])
    res["system_status"] = {t["system"]: t["status"] for t in tries}
    res.update(id=row["id"], name=row["name"], box=box, scale=scale, size=size, seconds=round(time.time() - t0))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{row['id']}.json").write_text(json.dumps(res, indent=1))
    overlay(img, res, OUT / f"{row['id']}.png")
    return res


# ---- driver ---------------------------------------------------------------------------------

def rows():
    load_dotenv(Path(".env"))
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    r = requests.get(f"{url}/rest/v1/maps", timeout=30, headers={"apikey": key, "Authorization": f"Bearer {key}"},
                     params={"select": "id,name,sheet_number,sheet_half,extra_metadata,iiif_image",
                             "collection": f"eq.{COLLECTION}", "order": "id", "limit": 500})
    r.raise_for_status()
    return r.json()


def sample(all_rows, records, count, fresh=False):
    """Evenly spaced by latitude among rows with a single clean catalogue box; fresh skips sheets already probed."""
    done = {p.stem for p in OUT.glob("*-*-*-*-*.json")} if fresh else set()
    ok = [(box_of(r, records), r) for r in all_rows if r["id"] not in done]
    ok = sorted([(b["south"], r) for b, r in ok if b], key=lambda t: t[0])
    step = len(ok) / count
    return [ok[int(i * step + step / 2)][1] for i in range(count)]


def self_test():
    # synthetic sheets with a physical lon/lat scale (455 px vs 480 px per 0.2 g at ~19 N)
    H, W = 1600, 1100
    rng = np.random.default_rng(0)
    dxg, dyg = 455 / .2, 480 / .2

    def sheet(vx, hy):
        img = np.full((H, W), 230, np.float32)
        img[104:1500, 104:1000] = 170 + rng.normal(0, 25, (1396, 896))   # inked map inside, blank paper outside
        img[:, 100:104] = 60; img[:, 1000:1004] = 60; img[100:104, :] = 60; img[1500:1504, :] = 60
        for x in vx:
            img[:, x:x + 2] = 80
        for y in hy:
            img[y:y + 2, :] = 80
        return img + rng.normal(0, 6, img.shape)

    def box_of_grades(gw, ge, gs, gn):
        return dict(west=from_grades(gw, 0)[0], east=from_grades(ge, 0)[0],
                    north=from_grades(0, gn)[1], south=from_grades(0, gs)[1])

    # lon lines 114.4 / 114.6 at x=421 / 876, lat lines 19.4 / 19.2 at y=561 / 1041; border 102..1002 x 102..1502
    gn, gs = 19.4 + (561 - 102) / dyg, 19.2 - (1502 - 1041) / dyg
    box = box_of_grades(114.4 - (421 - 102) / dxg, 114.6 + (1002 - 876) / dxg, gs, gn)
    sh = sheet((420, 875), (560, 1040))
    res = solve(sh, box)
    assert res["status"] == "ok", res
    res2 = solve2(sh, box)
    assert res2["status"] == "ok" and max(res2["affine_residual_m"]) < 5, res2.get("status")
    assert max(res["affine_residual_m"]) < 5, res["affine_residual_m"]
    assert abs(res["lines"]["lon114.4"]["c"] - 421) < 1.5, res["lines"]["lon114.4"]
    # a half sheet whose west border IS the 115.0 g line: one interior lon line (115.2) + the border
    box = box_of_grades(115.0018, 115.2 + (1002 - 558) / dxg, gs, gn)
    res = solve(sheet((557,), (560, 1040)), box)
    assert res["status"] == "ok", res
    assert res["grade_lines"]["lon"] == [115.0, 115.2], res["grade_lines"]
    # Greenwich 5' sheet: lon lines 114.5 / 114.5833 (one step apart, 455 px), lat lines 19.5 / 19.4167 (480 px)
    st = 1 / 12
    dxd, dyd = 455 / st, 480 / st
    gn, gs = 19.5 + (561 - 102) / dyd, 19.5 - st - (1502 - 1041) / dyd
    box = dict(west=114.5 - (421 - 102) / dxd, east=114.5 + st + (1002 - 876) / dxd, north=gn, south=gs)
    res = solve(sheet((420, 875), (560, 1040)), box, GREENWICH)
    assert res["status"] == "ok", res
    assert max(res["affine_residual_m"]) < 5, res["affine_residual_m"]
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["probe", "sample"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--method", choices=["old", "lines"], default="old", help="old: border pair first; lines: grade lines first, border last")
    ap.add_argument("--fresh", action="store_true", help="sample: skip sheets already probed")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    global SOLVE
    SOLVE = solve2 if a.method == "lines" else solve
    records = catalogue_boxes()
    all_rows = rows()
    chosen = ([r for r in all_rows if r["id"] in a.args] if a.cmd == "probe"
              else sample(all_rows, records, int(a.args[0]), a.fresh))
    summary = []
    for r in chosen:
        try:
            res = probe(r, records)
        except Exception as e:  # keep going: one bad sheet must not stop the run
            res = dict(id=r["id"], name=r["name"], status=f"error: {e!r}")
        summary.append(res)
        print(r["name"], r["id"][:8], res["status"] + (" (BORDER SUSPECT)" if res.get("border_suspect") else ""),
              res.get("catalogue_gap_m", ""), res.get("affine_residual_m", ""), flush=True)
    (OUT / "summary.json").write_text(json.dumps([{k: s.get(k) for k in ("id", "name", "status", "border_suspect", "catalogue_gap_m", "affine_residual_m", "seconds")} for s in summary], indent=1))


if __name__ == "__main__":
    main()
