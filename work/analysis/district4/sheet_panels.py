#!/usr/bin/env python3
"""Is a scan one printed plan, or several butted together?

A scan that carries two sheets of a series is not a thing one transform can
place, and the resulting residual looks like bad control points rather than
like a bad scan. This measures the two things that separate the good case from
the bad one, in source pixels off the native IIIF tiles:

  1. each panel's printed neat-line, and the angle between panels;
  2. whether a linear water feature runs across the seam without a step.

Run after `river_full_map.py` has written that sheet's tiles and mask:

    python work/analysis/district4/sheet_panels.py --self-check
    python work/analysis/district4/sheet_panels.py --year 1942

Measured on 1942, 2026-09-21: two panels, parallel to 0.02 deg, and the canal
crosses the seam with no step. The mosaic is sound, so it does **not** explain
that sheet's 72.3 m residual (`georef_error.md`). Recording the negative is
the point -- it was the obvious suspect and it is not the cause.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from river_full_map import MAPS, region  # noqa: E402

# Panels found by eye on the overview, then snapped to the printed neat-line by
# `frames()` below. Only sheets actually inspected appear here.
PANELS = {
    # Rescaled to the 2026 rescan (x1.9943, y1.9959) when MAPS["1942"] moved to it;
    # `frames()` re-snaps these to the printed neat-line anyway.
    "1942": {
        "Cholon": (253, 7427, 2297, 12233),
        "Saigon": (7363, 14540, 327, 10253),
    },
}
# Seam traces: (name, guessed centreline y, x from, x to, step).
SEAMS = {"1942": ("Tau Hu canal", 7403, 6581, 8376, 100)}


def window(tiles: Path, width: int, height: int,
           x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
    """Greyscale source pixels for a box, with region()'s halo trimmed off."""
    image = region(tiles, width, height, x0, y0, x1 - x0, y1 - y0)
    a = np.asarray(image.convert("L"), dtype=np.float32)
    oy, ox = y0 - max(0, y0 - 32), x0 - max(0, x0 - 32)
    return a[oy:oy + (y1 - y0), ox:ox + (x1 - x0)]


def line_angle(a: np.ndarray) -> tuple[float, float, int]:
    """Fit one near-horizontal printed line in a strip. Returns deg, rms, n.

    Per column, the darkness-weighted centroid gives the line to well under a
    pixel; the trimming passes drop columns where lettering or a stamp is
    darker than the rule.
    """
    weight = np.clip(160.0 - a, 0, None)
    total = weight.sum(axis=0)
    ok = total > 400
    if ok.sum() < 20:
        return float("nan"), float("nan"), int(ok.sum())
    rows = np.arange(a.shape[0])[:, None]
    centre = (weight * rows).sum(axis=0)[ok] / total[ok]
    cols = np.arange(a.shape[1])[ok].astype(float)
    for _ in range(4):
        m, c = np.polyfit(cols, centre, 1)
        resid = np.abs(centre - (m * cols + c))
        keep = resid <= max(1.0, 3.0 * np.median(resid))
        if keep.sum() < 20:
            break
        cols, centre = cols[keep], centre[keep]
    m, c = np.polyfit(cols, centre, 1)
    rms = float(np.sqrt(((centre - (m * cols + c)) ** 2).mean()))
    return math.degrees(math.atan(m)), rms, len(cols)


def trace(mask: np.memmap, x: int, guess: int, half: int = 140) -> float | None:
    """Centre of the water run nearest `guess` in column `x`, or None."""
    top = max(0, guess - half)
    col = np.asarray(mask[top:guess + half, x]).astype(bool)
    if not col.any():
        return None
    d = np.diff(np.r_[0, col.astype(np.int8), 0])
    runs = [(a, b) for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0])
            if b - a > 8]
    if not runs:
        return None
    local = guess - top          # not `half`: the window is clipped at the top
    a, b = min(runs, key=lambda r: abs((r[0] + r[1]) / 2 - local))
    return top + (a + b) / 2


def report(year: str, root: Path, mpp: float) -> None:
    _, width, height = MAPS[year]
    tiles = root / year / "tiles"
    if not tiles.is_dir():
        raise SystemExit(f"no tiles for {year}: run river_full_map.py --year {year}")
    panels = PANELS.get(year)
    if not panels:
        raise SystemExit(f"{year} has no panel boxes in PANELS; add them from the overview")

    print(f"{year}: scan {width}x{height}, {mpp} m/px\n")
    means = {}
    for name, (x0, x1, y0, y1) in panels.items():
        inset = int((x1 - x0) * 0.05)
        angles = []
        for edge, y in (("top", y0), ("bottom", y1)):
            a = window(tiles, width, height, x0 + inset, y - 25, x1 - inset, y + 25)
            deg, rms, n = line_angle(a)
            angles.append(deg)
            print(f"  {name:8s} {edge:6s} neat-line  {deg:+.4f} deg   "
                  f"fit rms {rms:.2f} px over {n} columns")
        means[name] = float(np.nanmean(angles))
        print(f"  {name:8s} panel {x1 - x0} x {y1 - y0} px, mean {means[name]:+.4f} deg\n")

    if len(means) > 1:
        (an, av), (bn, bv) = list(means.items())[:2]
        spread = abs(av - bv)
        (ax0, ax1, ay0, ay1) = panels[an]
        diag = math.hypot(ax1 - ax0, ay1 - ay0)
        print(f"  {an} to {bn} rotation {spread:.4f} deg "
              f"= {math.radians(spread) * diag * mpp:.0f} m corner to corner")
        sizes = [(x1 - x0, y1 - y0) for x0, x1, y0, y1 in panels.values()]
        print(f"  panel sizes {sizes} -- equal sizes mean sheets of one series\n")

    if year in SEAMS:
        name, guess, xa, xb, step = SEAMS[year]
        path = root / year / "candidate.uint8"
        if not path.exists():
            print(f"  (no river mask yet, skipping the {name} seam trace)")
            return
        mask = np.memmap(path, dtype=np.uint8, mode="r", shape=(height, width))
        print(f"  {name} across the seam -- a step here is a misassembled mosaic")
        ys, xs, g = [], [], guess
        for x in range(xa, xb, step):
            y = trace(mask, x, int(g))
            if y is None:
                continue
            ys.append(y)
            xs.append(x)
            g = y
        if len(ys) < 6:
            print("  too little water traced to judge the seam")
            return
        ys, xs = np.asarray(ys), np.asarray(xs, float)
        # A mosaic step shows up as one outlier in the second difference of the
        # centreline; real curvature spreads across every sample.
        second = np.abs(np.diff(ys, 2))
        worst = int(second.argmax())
        print(f"  traced {len(ys)} samples, x {xs[0]:.0f}-{xs[-1]:.0f}")
        print(f"  largest bend {second[worst]:.1f} px at x={xs[worst + 1]:.0f} "
              f"({second[worst] * mpp:.0f} m); median {np.median(second):.1f} px")
        print("  a seam step would sit at the neat-line and dwarf the median")


def self_check() -> None:
    """Offline: the line fit and the trace on synthetic data."""
    # A ruled line at a known angle, with lettering above it to be trimmed.
    h, w = 50, 2000
    a = np.full((h, w), 240.0)
    for x in range(w):
        centre = int(round(25 + 0.01 * x))
        a[centre - 2:centre + 2, x] = 20.0     # a 4px rule, as printed
    a[5:12, 400:520] = 0.0                     # lettering, must be trimmed off
    deg, rms, n = line_angle(a)
    assert abs(deg - math.degrees(math.atan(0.01))) < 0.01, deg
    assert rms < 0.6 and n > 1500, (rms, n)

    # A flat line is 0 deg, and a sparse strip returns nan rather than lying.
    flat = np.full((50, 2000), 240.0)
    flat[24:28] = 20.0
    assert abs(line_angle(flat)[0]) < 1e-9
    assert math.isnan(line_angle(np.full((50, 2000), 240.0))[0])

    # trace() finds the run nearest the guess, not the biggest one.
    mask = np.zeros((400, 10), np.uint8)
    mask[100:140] = 1          # wide run, far
    mask[250:270] = 1          # narrow run, near the guess
    assert trace(mask, 5, 260) == 260.0, trace(mask, 5, 260)
    assert trace(mask, 5, 120) == 120.0, trace(mask, 5, 120)
    # ... including when the window is clipped at the top of the image.
    assert trace(mask, 5, 110) == 120.0, trace(mask, 5, 110)
    assert trace(np.zeros((400, 10), np.uint8), 5, 200) is None
    print("self-check ok")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--year", choices=tuple(MAPS))
    p.add_argument("--out", type=Path, default=Path("/private/tmp/vma-river-full"))
    p.add_argument("--mpp", type=float, default=1.69,
                   help="metres per source pixel, for the metre columns")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.year:
        p.error("--year is required unless --self-check is given")
    report(args.year, args.out, args.mpp)


if __name__ == "__main__":
    main()
