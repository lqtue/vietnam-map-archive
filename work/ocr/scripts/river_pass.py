"""River pass v1, 1882: water from line texture, built on sheet_features.py's layers. No traces used.

    work/ocr/.venv/bin/python work/ocr/scripts/river_pass.py --sheet 1882
    work/ocr/.venv/bin/python work/ocr/scripts/river_pass.py --self-check

Writes work/ocr/outputs/<map_id>/river/: water.png (native, 255 = water joined to the river network,
128 = an isolated water-like body awaiting review, 0 = not water), cells.npz, preview.jpg, run.json.

How 1882 draws water: blue ripple lines parallel to the bank, 6-28 px apart, hand engraved, no wash.
The south bank has no ink line; the ripples stop. Colour cannot separate them from the blue military
ruling (same ink, measured), so the pass reads geometry:
  1. per 32 px cell, a 64 px FFT: dominant spacing, and `rule`, the share of power at the sheet's
     machine ruling (4.0-5.6 px, lines at 144 deg; military and salmon hatch both sit there).
  2. candidate cell: textured, its marks mostly blue (wash.npz), coherent, not ruled (stricter next
     to ruled cells, where a block edge dilutes the ruling). Seed cell: ripple spacing, very coherent.
  3. components with enough seeds; those within LINK cells of the largest are the network. Others
     (the citadel's rampart hachures look exactly like ripples; garden ponds) are review only:
     enclosed water needs its own confirmed seed (docs/river-reconstruction.md). The owner's answers
     live in river_ref/confirmed.json: a point inside a body settles it; a point that no longer
     lands in a body is reported as stale in run.json, never guessed.
  4. pixels: inside the cell zone, bluish line pixels not under a Gabor ruling response, closed by
     CLOSE_R; the eroded cell core is water outright. So the edge is the outermost ripple line.
     Machine ruling comes in two pitches (4.48 land, 3.55 buildings), and a large ruled area's
     edge, where a wall outline spoils the response, still counts as ruled (v3). Solid dark
     structures and enclosed ruled patches are never filled in.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image
from scipy import ndimage as nd
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "work" / "analysis" / "river_ref"

CELL, FFT_N, FFT_P = 32, 64, 128
BAND = (2.5, 30)                 # px spacing considered at all
RULE_SPACING = (4.0, 5.6)        # measured: military ruling 4.48 px, salmon hatch 5.09 px
RULE_PERIODS = (4.48, 3.55)      # Gabor periods: land ruling 4.48 (salmon falls inside its bandwidth), and the
                                 # denser 3.55 that fills buildings, same 144 deg (arsenal_quay, 2026-10-01)
RULE_ANGLE, RULE_TOL = 144, 8    # line direction, image axes, deg; every ruled cell on 1882 sits here
# The four constants above that describe the machine ruling (RULE_SPACING, RULE_PERIODS, RULE_ANGLE,
# RULE_TOL) are properties of the sheet, not of the method. The values here are 1882's and are the
# defaults; `sheets.<id>.ruling` in river_ref/windows.json overrides any of them (see sheet_ruling).
TEX_LOG_E = 4.0                  # log10 band power below which a cell is blank paper
BLUE_SHARE, MARKED = 0.5, 0.03   # of a cell's marked (non-paper) half-res pixels; marked share
COH = 0.4                        # structure-tensor coherence (texture.npz); gardens sit near 0.2
RULE_MAX, RULE_NEAR = 0.35, 0.08 # ruled cells measure ~0.9, ripples < 0.06, ripples under lettering 0.1-0.3
SEED_SPACING, SEED_COH, SEED_RULE = 6.5, 0.8, 0.05
COMP_SEEDS, COMP_AREA, COMP_SEED_SHARE = 4, 12, 0.15
LINK = 2                         # cells; bridges and lettering gaps up to ~2 cells join the network
GABOR_SIGMA, GABOR_FLOOR, RULE_PX = 4, 0.7, 45     # ruling share per pixel: calibrate dry_blue_parcels median 29 / ruled ~88,
                                 # open_bank 90th pct 0.4, river_label 90th 19 (lettering, before smoothing)
LINE_PX, BLUE_ODR = 0.9, 1.0     # red / paper red below this is a line; OD blue/red below this is blue ink
CLOSE_R, HOLE_MAX, MIN_PX = 6, 40_000, 2_000
RULE_SOFT, RULE_REACH, RULE_BLOB = 15, 10, 4000    # pixels: a half-ruled pixel within this reach of a fully ruled one is ruled too (arsenal_quay: hatch beside a wall reads 33, ripples <0.5)
HOLE_RULED = 0.5                 # share of an enclosed patch under the Gabor ruling above which it is not refilled
CORE_ERODE = 1                   # cells; 2 was tried: it cut real river at the frame and moved no held-out edge
SOLID_INK, SOLID_CLOSE, SOLID_OPEN, SOLID_PAD = 0.45, 2, 4, 3
                                 # grey / paper below SOLID_INK, closed then opened: a solid dark block
                                 # (landing stage, pier, bridge, bold lettering) is not water. Piers measure
                                 # grey 0.37-0.41, ripples 0.52-0.57 (calibrate quay_primauguet, open_bank)
TILE, MARGIN = 1024, 48


def sheet_ruling(sheet):
    """The sheet's machine-ruling constants: this module's (1882's) unless windows.json overrides them."""
    r = sheet.get("ruling", {})
    return {"spacing": tuple(r.get("spacing", RULE_SPACING)), "periods": tuple(r.get("periods", RULE_PERIODS)),
            "angle": r.get("angle", RULE_ANGLE), "tol": r.get("tol", RULE_TOL), "structure": r.get("structure")}


def cell_fft(red, paper_red, rows, cols, ruling=None):
    """Per cell: dominant spacing and the ruling share of band power, from a centred 64 px window."""
    ruling = ruling or sheet_ruling({})
    ky = np.fft.fftfreq(FFT_P)[:, None]
    kx = np.fft.rfftfreq(FFT_P)[None, :]
    kr = np.hypot(ky, kx)
    band = (kr > 1 / BAND[1]) & (kr < 1 / BAND[0])
    grad = np.abs((np.degrees(np.arctan2(ky, kx)) - (ruling["angle"] - 90) + 90) % 180 - 90)
    ruleband = band & (kr > 1 / ruling["spacing"][1]) & (kr < 1 / ruling["spacing"][0]) & (grad < ruling["tol"])
    han = np.outer(np.hanning(FFT_N), np.hanning(FFT_N))
    h = (FFT_N - CELL) // 2
    pad = np.pad(red, ((h, FFT_N), (h, FFT_N)), mode="edge")
    spacing, rule, energy = (np.zeros((rows, cols), np.float32) for _ in range(3))
    for r in range(rows):
        win = sliding_window_view(pad[r * CELL:r * CELL + FFT_N].astype(np.float32), (FFT_N, FFT_N))[0, :cols * CELL:CELL]
        win = win / paper_red[r][:, None, None]
        win = (win - win.mean((1, 2), keepdims=True)) * han
        ps = (np.abs(np.fft.rfft2(win, (FFT_P, FFT_P))) ** 2 * band).reshape(cols, -1)
        tot = ps.sum(1) + 1e-9
        spacing[r] = 1 / np.maximum(kr.ravel()[ps.argmax(1)], 1e-6)
        rule[r] = (ps * ruleband.ravel()).sum(1) / tot
        energy[r] = tot
    return spacing, rule, np.log10(energy + 1e-9)


def gabor_rule(rel, ruling=None):
    """Per-pixel share of local line energy at the ruling frequency and angle."""
    ruling = ruling or sheet_ruling({})
    k = int(3 * GABOR_SIGMA)
    y, x = np.mgrid[-k:k + 1, -k:k + 1]
    env = np.exp(-(x ** 2 + y ** 2) / (2 * GABOR_SIGMA ** 2))
    a = np.radians(ruling["angle"] - 90)
    rel = np.maximum(rel, GABOR_FLOOR)   # a dark outline must not swamp the normaliser and blank the hatch beside it
    bp = rel - nd.gaussian_filter(rel, 6)
    local = nd.gaussian_filter(bp ** 2, GABOR_SIGMA)
    best = 0
    for period in ruling["periods"]:
        kern = env * np.exp(2j * np.pi / period * (np.cos(a) * x + np.sin(a) * y))
        kern -= env * kern.sum() / env.sum()
        g = np.abs(fftconvolve(bp, kern, mode="same")) ** 2
        best = np.maximum(best, g / (local * (np.abs(kern) ** 2).sum() + 1e-6))
    return nd.gaussian_filter(best, GABOR_SIGMA)


def cells_to_water(spacing, rule, loge, coh, blue, marked, inside):
    tex = loge > TEX_LOG_E
    ruled = tex & (rule > RULE_MAX)
    near = nd.binary_dilation(ruled, np.ones((3, 3)))
    cand = tex & (blue > BLUE_SHARE) & (marked > MARKED) & (coh > COH) & inside & (rule < np.where(near, RULE_NEAR, RULE_MAX))
    seed = cand & (spacing >= SEED_SPACING) & (coh > SEED_COH) & (rule < SEED_RULE)
    lab, n = nd.label(cand, np.ones((3, 3)))
    idx = np.arange(1, n + 1)
    area, ns = nd.sum(cand, lab, idx), nd.sum(seed, lab, idx)
    keep = np.isin(lab, idx[(ns >= COMP_SEEDS) & (area >= COMP_AREA) & (ns >= COMP_SEED_SHARE * area)])
    glab, gn = nd.label(nd.binary_dilation(keep, np.ones((2 * LINK + 1,) * 2)))
    big = 1 + np.argmax(nd.sum(keep, glab, range(1, gn + 1))) if gn else 0
    network = keep & (glab == big)
    return cand, seed, network, keep & ~network


def refine(rgb, paper_at, zone_cells, core_cells, ruling=None):
    """Native mask from cell masks: line pixels in the zone, closed; eroded core is water outright;
    solid dark structures are cut out and never refilled as holes."""
    h, w, _ = rgb.shape
    ruling = ruling or sheet_ruling({})
    out, solid_px, ruled_px = (np.zeros((h, w), bool) for _ in range(3))
    dk = lambda r: np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r
    disk = np.hypot(*np.mgrid[-CLOSE_R:CLOSE_R + 1, -CLOSE_R:CLOSE_R + 1]) <= CLOSE_R
    full = lambda m: np.pad(np.repeat(np.repeat(m, CELL, 0), CELL, 1), ((0, h - m.shape[0] * CELL), (0, w - m.shape[1] * CELL)))
    zone_px, core_px = full(zone_cells), full(core_cells)
    for y0 in range(0, h, TILE):
        for x0 in range(0, w, TILE):
            y1, x1 = min(h, y0 + TILE), min(w, x0 + TILE)
            cy, cx = slice(y0 // CELL, -(-y1 // CELL)), slice(x0 // CELL, -(-x1 // CELL))
            if not zone_cells[cy, cx].any():
                continue
            a, b, c, d = max(0, y0 - MARGIN), min(h, y1 + MARGIN), max(0, x0 - MARGIN), min(w, x1 + MARGIN)
            s = rgb[a:b, c:d].astype(np.float32)
            p = paper_at(np.arange(a, b) + 0.5, np.arange(c, d) + 0.5)
            od = np.clip(-np.log10(np.maximum(s, 1) / p), 0, None)
            rel = s[..., 0] / p[..., 0]
            g = gabor_rule(rel, ruling)
            strong = g >= RULE_PX
            sl_, sn_ = nd.label(strong)
            land = np.isin(sl_, 1 + np.where(nd.sum(strong, sl_, range(1, sn_ + 1)) >= RULE_BLOB)[0])   # not a bridge deck or a ladder
            ruled = strong | ((g >= RULE_SOFT) & nd.binary_dilation(land, dk(RULE_REACH)))   # a ruled area's edge reads ~0.3-0.8 of the full share
            line = (rel < LINE_PX) & (od[..., 2] < BLUE_ODR * od[..., 0]) & ~ruled
            zone = zone_px[a:b, c:d]
            solid = s.mean(2) / p.mean(2) < SOLID_INK
            solid = nd.binary_dilation(nd.binary_opening(nd.binary_closing(solid, dk(SOLID_CLOSE)), dk(SOLID_OPEN)), dk(SOLID_PAD))
            if ruling.get("structure"):
                # a sheet that hatches structures (piers, buildings) in neutral black while water is blue ink:
                # dark neutral hatch, closed into a body, is a structure. Off by default (1882 hatches both in blue).
                st = ruling["structure"]
                black = (rel < st["rel"]) & (od[..., 2] >= st["odr"] * od[..., 0])
                black = nd.binary_dilation(nd.binary_opening(nd.binary_closing(black, dk(st["close"])), dk(st["open"])), dk(SOLID_PAD))
                solid = solid | black
            m = (nd.binary_closing(line & zone, disk) | core_px[a:b, c:d]) & zone & ~solid
            out[y0:y1, x0:x1] = m[y0 - a:y1 - a, x0 - c:x1 - c]
            solid_px[y0:y1, x0:x1] = solid[y0 - a:y1 - a, x0 - c:x1 - c]
            ruled_px[y0:y1, x0:x1] = strong[y0 - a:y1 - a, x0 - c:x1 - c]
    holes = nd.binary_fill_holes(out) & ~out & ~solid_px
    hl, hn = nd.label(holes)
    idx = np.arange(1, hn + 1)
    # an enclosed patch is refilled only if small and not itself machine-ruled (a ruled building ringed by ripple-like outline is not a gap)
    small = np.isin(hl, idx[(nd.sum(holes, hl, idx) <= HOLE_MAX) & (nd.mean(ruled_px, hl, idx) < HOLE_RULED)])
    out |= small
    ol, on = nd.label(out)
    return np.isin(ol, 1 + np.where(nd.sum(out, ol, range(1, on + 1)) >= MIN_PX)[0])


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from sheet_features import paper_at

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    t0 = time.time()
    spec = json.loads((REF / "windows.json").read_text())
    sheet = spec["sheets"][a.sheet]
    pin = json.loads((REF / "native.json").read_text())[a.sheet]
    Image.MAX_IMAGE_PIXELS = None
    rgb = np.asarray(Image.open(ROOT / pin["path"]).convert("RGB"))
    assert hashlib.sha256(rgb.tobytes()).hexdigest() == pin["rgb_sha256"], "native raster differs from native.json"
    base = ROOT / "work" / "ocr" / "outputs" / sheet["map_id"]
    feat, out = base / "features", base / "river"
    out.mkdir(parents=True, exist_ok=True)
    paper = np.load(feat / "paper.npy")
    tex = np.load(feat / "texture.npz")
    lab = np.load(feat / "wash.npz")["label"]
    h, w, _ = rgb.shape
    rows, cols = h // CELL, w // CELL
    half = lambda m: m[:rows * 16, :cols * 16].reshape(rows, 16, cols, 16).mean((1, 3))
    marked = half(lab > 0)
    blue = half(lab == 1) / np.maximum(marked, 1e-6)
    paper_red = np.kron(paper[..., 0], np.ones((2, 2)))[:rows, :cols]     # PAPER_CELL 64 = 2 cells
    ruling = sheet_ruling(sheet)
    spacing, rule, loge = cell_fft(rgb[..., 0], paper_red, rows, cols, ruling)
    inside = np.zeros((rows, cols), bool)
    x, y, bw, bh = sheet["neatline"]
    inside[-(-y // CELL):(y + bh) // CELL, -(-x // CELL):(x + bw) // CELL] = True
    for fx, fy, fw, fh in sheet["furniture"].values():
        inside[fy // CELL:-(-(fy + fh) // CELL), fx // CELL:-(-(fx + fw) // CELL)] = False
    cand, seed, network, review = cells_to_water(spacing, rule, loge, tex["coherence"][:rows, :cols], blue, marked, inside)
    # owner decisions on review bodies (river_ref/confirmed.json): water joins the network, dry is settled
    rl, _ = nd.label(review, np.ones((3, 3)))
    stale, settled = [], {True: 0, False: 0}
    for p in json.loads((REF / "confirmed.json").read_text()).get(a.sheet, []):
        i = rl[p["y"] // CELL, p["x"] // CELL]
        if not i:
            stale.append(p)    # the body moved or vanished under new settings: ask again, never guess
            continue
        body = rl == i
        if p["water"]:
            network |= body
        review &= ~body
        settled[p["water"]] += 1
    t1 = time.time()
    pa = lambda yc, xc: paper_at(paper, yc, xc)
    sq = np.ones((3, 3))
    mask = np.zeros((h, w), np.uint8)
    for val, cells in ((128, review), (255, network)):
        m = refine(rgb, pa, nd.binary_dilation(cells, sq), nd.binary_erosion(cells, sq, iterations=CORE_ERODE), ruling)
        mask[m] = val
    Image.fromarray(mask).save(out / "water.png", compress_level=6)
    np.savez_compressed(out / "cells.npz", spacing=spacing, rule=rule, loge=loge, blue=blue, marked=marked,
                        cand=cand, seed=seed, network=network, review=review)
    rl, rn = nd.label(review, np.ones((3, 3)))
    bodies = [{"box": [int(sl[1].start * CELL), int(sl[0].start * CELL), int((sl[1].stop - sl[1].start) * CELL),
                       int((sl[0].stop - sl[0].start) * CELL)], "cells": int((rl[sl] == i + 1).sum())}
              for i, sl in enumerate(nd.find_objects(rl))]
    pv = rgb[::8, ::8].astype(np.float32)
    mv = mask[::8, ::8]
    pv[mv == 255] = pv[mv == 255] * 0.4 + np.array([0, 170, 255]) * 0.6
    pv[mv == 128] = pv[mv == 128] * 0.4 + np.array([255, 120, 0]) * 0.6
    sys.path.insert(0, str(REF))
    from view import blank     # heldout windows with seen:false are black in every preview
    Image.fromarray(blank(pv.astype(np.uint8), a.sheet, 8)).save(out / "preview.jpg", quality=85)
    run = {"sheet": a.sheet, "native_sha256": pin["rgb_sha256"],
           "ruling": ruling,
           "settings": {k: globals()[k] for k in ("CELL", "FFT_N", "BAND",
                                                  "TEX_LOG_E", "BLUE_SHARE", "MARKED", "COH", "RULE_MAX", "RULE_NEAR",
                                                  "SEED_SPACING", "SEED_COH", "SEED_RULE", "COMP_SEEDS", "COMP_AREA",
                                                  "COMP_SEED_SHARE", "LINK", "GABOR_SIGMA", "GABOR_FLOOR", "RULE_PX", "LINE_PX",
                                                  "BLUE_ODR", "CLOSE_R", "HOLE_MAX", "RULE_SOFT", "RULE_REACH", "RULE_BLOB", "HOLE_RULED", "MIN_PX", "CORE_ERODE",
                                                  "SOLID_INK", "SOLID_CLOSE", "SOLID_OPEN", "SOLID_PAD")},
           "cells": {"candidate": int(cand.sum()), "seed": int(seed.sum()), "network": int(network.sum()), "review": int(review.sum())},
           "water_px": int((mask == 255).sum()), "review_px": int((mask == 128).sum()),
           "confirmed": {"water": settled[True], "dry": settled[False], "stale": stale},
           "review_bodies": bodies,
           "seconds": {"cells": round(t1 - t0, 1), "total": round(time.time() - t0, 1)}}
    (out / "run.json").write_text(json.dumps(run, indent=1) + "\n")
    print(json.dumps({k: v for k, v in run.items() if k != "settings"}, indent=1))


def self_check():
    """Synthetic: ripples (11 px, 20 deg) beside machine ruling (4.48 px, 144 deg) and blank paper."""
    n = 256
    y, x = np.mgrid[0:n, 0:2 * n].astype(float)
    a_r, a_m = np.radians(20 + 90), np.radians(RULE_ANGLE + 90)
    red = np.full((n, 2 * n), 220.0)
    rip = np.cos(2 * np.pi * (np.cos(a_r) * x + np.sin(a_r) * y) / 11) > 0.8
    mil = np.cos(2 * np.pi * (np.cos(a_m) * x + np.sin(a_m) * y) / 4.48) > 0.6
    red[:, :n][rip[:, :n]] = 150
    red[:, n:][mil[:, n:]] = 150
    rows, cols = n // CELL, 2 * n // CELL
    sp, rule, loge = cell_fft(red.astype(np.uint8), np.full((rows, cols), 220.0), rows, cols)
    assert np.median(rule[2:6, 1:6]) < 0.05 and np.median(rule[2:6, 10:15]) > 0.5, (rule[2:6, 1:6], rule[2:6, 10:15])
    assert 9 < np.median(sp[2:6, 1:6]) < 13 and 4 < np.median(sp[2:6, 10:15]) < 5.2, np.median(sp[2:6, 10:15])
    g = gabor_rule(red / 220)
    assert np.median(g[64:192, 300:450]) > RULE_PX > np.median(g[64:192, 40:200]), (np.median(g[64:192, 300:450]), np.median(g[64:192, 40:200]))
    # component logic: a big seeded body, a small seeded body far away (review), a seedless one (dropped)
    c = np.zeros((40, 40), bool)
    c[2:20, 2:20] = c[30:36, 30:36] = c[2:6, 30:36] = True
    one = np.ones_like(c, float)
    sp2 = np.where(c, 10, 0).astype(float)
    sp2[2:6, 30:36] = 5
    _, _, net, rev = cells_to_water(sp2, np.zeros_like(one), c * 5.0, one * 0.9, one, one, np.ones_like(c))
    assert net[10, 10] and not net[33, 33] and rev[33, 33] and not rev[3, 31] and not net[3, 31]
    # refine: blue ripples are water, a solid dark pier inside them is cut out and not refilled as a hole
    img = np.full((224, 224, 3), 220, np.uint8)
    img[::9] = (120, 140, 170)                                   # blue lines 9 px apart
    img[80:130, 90:120] = (60, 60, 60)                           # pier
    on = np.ones((224 // CELL, 224 // CELL), bool)
    m = refine(img, lambda yc, xc: np.full((len(yc), len(xc), 3), 220, np.float32), on, on)
    assert m[40, 40] and m[150, 60] and not m[105, 105], (m[40, 40], m[150, 60], m[105, 105])
    # a building filled with the finer 3.55 px machine ruling (same 144 deg) is ink, not ripples
    yy, xx = np.mgrid[0:224, 0:224].astype(float)
    a_m = np.radians(RULE_ANGLE + 90)
    img2 = img.copy()
    bld = np.cos(2 * np.pi * (np.cos(a_m) * xx + np.sin(a_m) * yy) / 3.55) > 0.2
    img2[130:190, 160:224][bld[130:190, 160:224]] = (120, 140, 170)
    img2[130:190, 160:224][~bld[130:190, 160:224]] = (220, 220, 220)
    m2 = refine(img2, lambda yc, xc: np.full((len(yc), len(xc), 3), 220, np.float32), on, ~on)   # zone only, no core
    assert not m2[140:180, 170:224].any() and m2[:100].any(), m2[140:180, 170:224].mean()
    # ... and one ringed by ripple lines is not a hole to refill (it was, before HOLE_RULED)
    img3 = img.copy()
    img3[70:150, 70:150][bld[70:150, 70:150]] = (120, 140, 170)
    img3[70:150, 70:150][~bld[70:150, 70:150]] = (220, 220, 220)
    m3 = refine(img3, lambda yc, xc: np.full((len(yc), len(xc), 3), 220, np.float32), on, ~on)
    assert not m3[90:130, 90:130].any() and m3[:60].any(), m3[90:130, 90:130].mean()
    # 1898 ruling (per-sheet): 6 px lines at 45 deg are ruled, 11 px ripples are not; and black hatch is a structure
    r98 = sheet_ruling({"ruling": {"spacing": [5.2, 6.8], "periods": [5.95, 2.95], "angle": 45, "tol": 8,
                                   "structure": {"rel": 0.6, "odr": 0.8, "close": 4, "open": 6}}})
    a_m = np.radians(45 + 90)
    red2 = np.full((n, 2 * n), 220.0)
    red2[:, :n][rip[:, :n]] = 150
    mil2 = np.cos(2 * np.pi * (np.cos(a_m) * x + np.sin(a_m) * y) / 6.0) > 0.6
    red2[:, n:][mil2[:, n:]] = 150
    sp2_, rule2, _ = cell_fft(red2.astype(np.uint8), np.full((rows, cols), 220.0), rows, cols, r98)
    assert np.median(rule2[2:6, 1:6]) < 0.05 and np.median(rule2[2:6, 10:15]) > 0.5, (rule2[2:6, 1:6], rule2[2:6, 10:15])
    g98 = gabor_rule(red2 / 220, r98)
    assert np.median(g98[64:192, 300:450]) > RULE_PX > np.median(g98[64:192, 40:200]), (np.median(g98[64:192, 300:450]), np.median(g98[64:192, 40:200]))
    img4 = img.copy()                                                         # blue ripples with a black-hatched pier
    pier = np.zeros((224, 224), bool)
    pier[80:130, 90:120] = True
    hatch = np.cos(2 * np.pi * (xx + yy) / (6 * np.sqrt(2))) > 0.6           # thin lines 6 px apart at 135 deg, off the 45 deg ruling and too sparse for the solid test
    img4[pier & hatch] = (60, 62, 66)                                         # near-neutral: OD blue/red 0.93, passes the 1882 blue test
    img4[pier & ~hatch] = (200, 200, 200)
    flat = lambda yc, xc: np.full((len(yc), len(xc), 3), 220, np.float32)
    off, on_ = refine(img4, flat, on, on), refine(img4, flat, on, on, r98)
    assert off[85:125, 95:115].mean() > 0.2 and on_[85:125, 95:115].mean() < 0.02 and on_[40, 40], (off[85:125, 95:115].mean(), on_[85:125, 95:115].mean())
    print("self-check ok")


if __name__ == "__main__":
    main()
