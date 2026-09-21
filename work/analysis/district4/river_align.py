#!/usr/bin/env python3
"""Warp each sheet's river mask to the ground and compare the four against each other.

The GCPs are a handful of points; the river is a line across the whole sheet. Warping
each sheet's river with its own accepted georeference and overlaying the results gives a
spatially distributed picture of where a georeference is wrong, which a GCP residual
cannot show.

This measures *agreement between sheets*, not correctness: the river itself moved
(reclamation, bank works), so disagreement localises a problem without saying which
sheet owns it.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scipy import ndimage  # noqa: E402

from georef_error import _local_metres, _score  # noqa: E402
from river_full_map import MAPS  # noqa: E402

ANN = Path("/private/tmp/vma-river-full")
# The scan the GCPs were placed on is not always the scan we fetched tiles from:
# 1942's annotation is on a 2026 rescan at twice the linear resolution.
GRID_M = 10.0
# Beyond this a cell is taken to be somewhere the other sheet simply does not
# draw water, rather than the same water in the wrong place.
CAP_M = 400.0


def annotation(year: str) -> dict:
    return json.loads((ANN / f"ann-{year}.json").read_text())["items"][0]


def control(year: str) -> tuple[np.ndarray, np.ndarray, str, tuple[int, int]]:
    item = annotation(year)
    px = np.array([f["properties"]["resourceCoords"] for f in item["body"]["features"]], float)
    ll = np.array([f["geometry"]["coordinates"] for f in item["body"]["features"]], float)
    src = item["target"]["source"]
    return px, ll, item["body"]["transformation"]["type"], (src["width"], src["height"])


def solve(year: str, drop: list[int] | None = None):
    """Pixel -> local metres, in the transform family the annotation declares."""
    px, ll, kind, (aw, ah) = control(year)
    if drop:
        keep = [i for i in range(len(px)) if i not in drop]
        px, ll = px[keep], ll[keep]
    met = _local_metres(ll)
    _, live_w, live_h = MAPS[year]
    scale = np.array([aw / live_w, ah / live_h])      # live tile px -> annotation px

    if kind == "helmert":
        u, v, n = px[:, 0], -px[:, 1], len(px)
        design = np.zeros((2 * n, 4))
        design[0::2] = np.column_stack([u, -v, np.ones(n), np.zeros(n)])
        design[1::2] = np.column_stack([v, u, np.zeros(n), np.ones(n)])
        (a, b, tx, ty), *_ = np.linalg.lstsq(design, met.reshape(-1), rcond=None)
        pred = np.column_stack([a * u - b * v + tx, b * u + a * v + ty])

        def fwd(p: np.ndarray) -> np.ndarray:
            q = p * scale
            uu, vv = q[:, 0], -q[:, 1]
            return np.column_stack([a * uu - b * vv + tx, b * uu + a * vv + ty])
    else:                                              # polynomial order 1 == affine
        design = np.column_stack([px, np.ones(len(px))])
        coef, *_ = np.linalg.lstsq(design, met, rcond=None)
        pred = design @ coef

        def fwd(p: np.ndarray) -> np.ndarray:
            q = p * scale
            return np.column_stack([q[:, 0], q[:, 1], np.ones(len(q))]) @ coef

    rmse, worst = _score(pred, met)
    return fwd, {"n": len(px), "kind": kind, "rmse_m": rmse, "worst_m": worst,
                 "ann_size": [aw, ah], "px_scale": scale.tolist()}


def river_points(year: str, step: int) -> np.ndarray:
    """Set pixels of the tightened mask, subsampled on a regular lattice."""
    _, w, h = MAPS[year]
    mask = np.memmap(ANN / year / "river.uint8", np.uint8, "r", shape=(h, w))
    ys = np.arange(0, h, step)
    rows = np.asarray(mask[ys][:, ::step], bool)
    yy, xx = np.nonzero(rows)
    return np.column_stack([xx * step, ys[yy]]).astype(float)


def rasterise(points: np.ndarray, origin: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    idx = np.floor((points - origin) / GRID_M).astype(int)
    ok = (idx[:, 0] >= 0) & (idx[:, 1] >= 0) & (idx[:, 0] < shape[1]) & (idx[:, 1] < shape[0])
    grid = np.zeros(shape, bool)
    grid[idx[ok, 1], idx[ok, 0]] = True
    return grid


def distance_to(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Ground distance from every set cell of `a` to the nearest set cell of `b`."""
    return ndimage.distance_transform_edt(~b, sampling=GRID_M)[a]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", type=int, default=4, help="mask subsample stride, source px")
    ap.add_argument("--drop-1942", type=int, nargs="*", default=None,
                    help="GCP indices to exclude from the 1942 fit")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--out", type=Path, default=ANN / "align")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return

    warped, info = {}, {}
    for year in ("1923", "1942", "1959", "1968"):
        fwd, meta = solve(year, args.drop_1942 if year == "1942" else None)
        pts = fwd(river_points(year, args.step))
        warped[year], info[year] = pts, meta
        print(f"{year}: {len(pts):7d} river points, fit {meta['kind']:10s} "
              f"n={meta['n']:2d} RMSE {meta['rmse_m']:6.1f} m")

    allpts = np.vstack(list(warped.values()))
    origin = allpts.min(axis=0)
    shape = (int(np.ceil((allpts[:, 1].max() - origin[1]) / GRID_M)) + 1,
             int(np.ceil((allpts[:, 0].max() - origin[0]) / GRID_M)) + 1)
    grids = {y: rasterise(p, origin, shape) for y, p in warped.items()}

    print(f"\ncommon grid {shape[1]}x{shape[0]} at {GRID_M:.0f} m")
    print("\nnearest-water distance between warped sheets, where both drew water")
    print("(cells further than the cap are treated as non-overlapping coverage, not error)")
    print(f"  {'pair':<16} {'median':>8} {'p90':>8} {'overlap':>9}")
    years = list(grids)
    pairs = {}
    for i, a in enumerate(years):
        for b in years:
            if a == b:
                continue
            d = distance_to(grids[a], grids[b])
            near = d[d <= CAP_M]
            pairs[f"{a}->{b}"] = {
                "median_m": float(np.median(near)) if near.size else None,
                "p90_m": float(np.percentile(near, 90)) if near.size else None,
                "overlap_frac": float(near.size / max(grids[a].sum(), 1)),
            }
            if i < years.index(b):
                print(f"  {a} vs {b:<9} {np.median(near):7.1f}m {np.percentile(near, 90):7.1f}m "
                      f"{near.size / max(grids[a].sum(), 1):8.1%}")
    info["_pairs"] = pairs

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "fits.json").write_text(json.dumps(info, indent=2) + "\n")
    np.savez_compressed(args.out / "grids.npz", origin=origin, grid_m=GRID_M,
                        **{y: g for y, g in grids.items()})
    print(f"\nwrote {args.out}/fits.json and grids.npz")


def self_check() -> None:
    # rasterise() must place a point in the cell its coordinates fall in.
    origin = np.array([100.0, 200.0])
    g = rasterise(np.array([[100.0, 200.0], [125.0, 234.0]]), origin, (5, 5))
    assert g[0, 0] and g[3, 2], np.argwhere(g)
    assert g.sum() == 2, g.sum()

    # A helmert fit on points generated by a known similarity must recover it.
    rng = np.random.default_rng(0)
    px = rng.uniform(0, 5000, (8, 2))
    th, s = math.radians(3.0), 1.7
    m = s * np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    truth = (np.column_stack([px[:, 0], -px[:, 1]]) @ m.T) + np.array([500.0, -300.0])
    u, v, n = px[:, 0], -px[:, 1], len(px)
    d = np.zeros((2 * n, 4))
    d[0::2] = np.column_stack([u, -v, np.ones(n), np.zeros(n)])
    d[1::2] = np.column_stack([v, u, np.zeros(n), np.ones(n)])
    coef, *_ = np.linalg.lstsq(d, truth.reshape(-1), rcond=None)
    pred = np.column_stack([coef[0]*u - coef[1]*v + coef[2], coef[1]*u + coef[0]*v + coef[3]])
    assert np.allclose(pred, truth, atol=1e-6), np.abs(pred - truth).max()

    # river_points must respect the stride and stay inside the scan.
    _, w, h = MAPS["1942"]
    pts = river_points("1942", 64)
    assert pts[:, 0].max() < w and pts[:, 1].max() < h, pts.max(axis=0)
    assert set(np.unique(pts[:, 0] % 64)) == {0.0}, "stride broken"
    print("self-check ok")


if __name__ == "__main__":
    main()
