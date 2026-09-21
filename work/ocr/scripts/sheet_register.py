#!/usr/bin/env python3
"""sheet_register.py — register one historical sheet onto another using the
names printed on both, then refine on block geometry.

    python work/ocr/scripts/sheet_register.py --pair 1882:1898
    python work/ocr/scripts/sheet_register.py --pair 1882:1898 --no-icp
    python work/ocr/scripts/sheet_register.py --self-check

Why this exists: `modern_prior.py` warps 2023 geodata into a sheet's pixel grid
through that sheet's ground control points. A sheet whose georeference is bad
(1898: three points, documented unreliable) therefore gets no prior at all, and
cannot be compared to anything. But place names persist across editions, so the
words printed on two sheets are correspondences that need no ground frame:

    1882 px --(similarity from shared names)--> 1898 px

Compose that with 1882's own georeference -- the one sheet a human has checked,
12.7 m RMSE -- and 1898 inherits a usable one. 1882 is the root; every sheet
registers to the root directly, never only to its neighbour, so error does not
accumulate along a chain.

Two stages:

  names  RANSAC over a 4-dof similarity (scale, rotation, translation). Only
         names unique on BOTH sheets are used -- "Rue Projetée" appears many
         times and is a correspondence to nothing.
  icp    trimmed iterative closest point on block centroids, seeded by the name
         fit. Text is printed NEAR a feature, not on it, so the name stage is a
         seed (tens of metres); block geometry is what carries the refinement.

ponytail: similarity only -- 4 dof. No affine, no TPS. `georef_error.md` measures
1.4% differential scale on the 1882 scan, so a similarity leaves ~1% on the
table; add affine when a measured residual says that 1% is what is hurting.
"""
from __future__ import annotations

import argparse, json, math, pathlib, re, sys, unicodedata
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]

# m/px and the checked georeference come from work/analysis/district4/georef_error.md
SHEETS = {
    "1882": dict(
        map_id="0e02b9d9-9d40-4cca-8e41-8c8373d54d3b", m_per_px=0.3411, georef_rmse_m=12.7,
        ocr="work/ocr/outputs/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/runs/post0910/all_extractions.json",
        blocks="work/ocr/outputs/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/colour-20260919-normalized/blocks.clean.geojson"),
    "1898": dict(
        map_id="20ec4f9a-16bd-4895-a593-40c6ed9c9555", m_per_px=None, georef_rmse_m=None,
        ocr="work/ocr/outputs/20ec4f9a-16bd-4895-a593-40c6ed9c9555/runs/2026-09-13T1036-20ec4f9a/all_extractions.json",
        blocks="work/ocr/outputs/20ec4f9a-16bd-4895-a593-40c6ed9c9555/colour-1898-20260919-normalized/blocks.clean.geojson"),
}
SKIP_CAT = {"title", "legend", "other"}   # sheet furniture: same words on every sheet
MIN_KEY = 5                               # "OUEST" and shorter match by accident


# ---------------------------------------------------------------- similarity

def fit_similarity(a, b):
    """Umeyama: the 4-dof (s, R, t) least-squares fit taking a -> b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ca, cb = a.mean(0), b.mean(0)
    da, db = a - ca, b - cb
    cov = db.T @ da
    var = (da ** 2).sum()
    if var == 0:
        raise ValueError("degenerate: all source points coincide")
    num_c = cov[0, 0] + cov[1, 1]
    num_s = cov[1, 0] - cov[0, 1]
    s = math.hypot(num_c, num_s) / var
    th = math.atan2(num_s, num_c)
    R = s * np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    return dict(R=R, t=cb - R @ ca, scale=s, rot_deg=math.degrees(th))


def apply(T, pts):
    return np.asarray(pts, float) @ T["R"].T + T["t"]


def residuals(T, a, b):
    return np.linalg.norm(apply(T, a) - np.asarray(b, float), axis=1)


def ransac(a, b, tol_px, iters=4000, seed=0):
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(iters):
        idx = rng.choice(len(a), 3, replace=False)
        try:
            T = fit_similarity(a[idx], b[idx])
        except ValueError:
            continue
        keep = residuals(T, a, b) < tol_px
        if best is None or keep.sum() > best.sum():
            best = keep
    if best is None or best.sum() < 3:
        raise ValueError("no consensus set")
    return fit_similarity(a[best], b[best]), best


# ---------------------------------------------------------------------- ICP

def icp(T, src, dst, iters=30, trim=0.6):
    """Trimmed ICP. Blocks are built and demolished between editions, so only
    the closest `trim` share of correspondences vote on each round."""
    from scipy.spatial import cKDTree
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    tree = cKDTree(dst)
    k = max(3, int(trim * len(src)))
    for _ in range(iters):
        moved = apply(T, src)
        d, j = tree.query(moved, workers=-1)
        take = np.argsort(d)[:k]
        new = fit_similarity(src[take], dst[j[take]])
        if np.allclose(new["R"], T["R"], atol=1e-9) and np.allclose(new["t"], T["t"], atol=1e-6):
            T = new
            break
        T = new
    d, _ = cKDTree(dst).query(apply(T, src), workers=-1)
    return T, np.sort(d)[:k]


# ------------------------------------------------------------------- inputs

def name_key(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.casefold()).split())


def unique_names(path):
    """name key -> centre px, keeping only names that appear ONCE on the sheet."""
    seen = {}
    for e in json.loads((ROOT / path).read_text())["extractions"]:
        if e.get("category") in SKIP_CAT:
            continue
        k = name_key(e["text"])
        if len(k) < MIN_KEY:
            continue
        x, y, w, h = e["global_bbox"]
        seen.setdefault(k, []).append((x + w / 2, y + h / 2, e["text"]))
    return {k: v[0] for k, v in seen.items() if len(v) == 1}


def block_centroids(path, limit=2000):
    feats = json.loads((ROOT / path).read_text())["features"]
    feats.sort(key=lambda f: -(f["properties"].get("area_px") or 0))
    out = []
    for f in feats[:limit]:
        g = f["geometry"]
        rings = [g["coordinates"][0]] if g["type"] == "Polygon" else [p[0] for p in g["coordinates"]]
        pts = np.array([c for r in rings for c in r], float)
        out.append(pts.mean(0))
    return np.array(out)


# -------------------------------------------------------------------- driver

def register(src_tag, dst_tag, tol_px, use_icp, out_path):
    src, dst = SHEETS[src_tag], SHEETS[dst_tag]
    A, B = unique_names(src["ocr"]), unique_names(dst["ocr"])
    shared = sorted(set(A) & set(B))
    if len(shared) < 3:
        sys.exit(f"only {len(shared)} shared unique names — not enough to register")
    pa = [A[k][:2] for k in shared]
    pb = [B[k][:2] for k in shared]

    T, keep = ransac(pa, pb, tol_px)
    r = residuals(T, pa, pb)[keep]
    # the target sheet's m/px is unknown until now: the fit itself supplies it
    m_per_px_dst = src["m_per_px"] / T["scale"]
    report = dict(
        source=src_tag, target=dst_tag, source_map_id=src["map_id"], target_map_id=dst["map_id"],
        shared_unique_names=len(shared), inliers=int(keep.sum()),
        rot_deg=round(T["rot_deg"], 3), scale=round(T["scale"], 5),
        target_m_per_px=round(m_per_px_dst, 4),
        names_residual_px=dict(median=round(float(np.median(r)), 1),
                               mean=round(float(r.mean()), 1), max=round(float(r.max()), 1)),
        names_residual_m=round(float(np.median(r)) * m_per_px_dst, 1),
        inlier_names=[A[k][2] for k, ok in zip(shared, keep) if ok],
        stage="names")

    if use_icp:
        ca, cb = block_centroids(src["blocks"]), block_centroids(dst["blocks"])
        T, d = icp(T, ca, cb)
        m_per_px_dst = src["m_per_px"] / T["scale"]
        report.update(stage="names+icp", scale=round(T["scale"], 5),
                      rot_deg=round(T["rot_deg"], 3), target_m_per_px=round(m_per_px_dst, 4),
                      icp_blocks=[len(ca), len(cb)],
                      icp_residual_px=dict(median=round(float(np.median(d)), 1),
                                           mean=round(float(d.mean()), 1)),
                      icp_residual_m=round(float(np.median(d)) * m_per_px_dst, 1),
                      names_after_icp_m=round(float(np.median(residuals(T, pa, pb)[keep]))
                                              * m_per_px_dst, 1))

    report["matrix"] = dict(a=T["R"][0, 0], b=T["R"][0, 1], c=T["R"][1, 0],
                            d=T["R"][1, 1], tx=T["t"][0], ty=T["t"][1])
    # 1882 is the root: its georeference is the only checked one, so it bounds
    # everything composed through it. The target can never be better than this.
    report["inherited_georef_floor_m"] = src["georef_rmse_m"]
    pathlib.Path(out_path).write_text(json.dumps(report, indent=2))
    return report


def self_check():
    rng = np.random.default_rng(1)
    src = rng.uniform(0, 1000, (60, 2))
    th, s, t = math.radians(30), 1.2, np.array([400.0, -250.0])
    R = s * np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    dst = src @ R.T + t
    T = fit_similarity(src, dst)
    assert abs(T["scale"] - s) < 1e-9 and abs(T["rot_deg"] - 30) < 1e-9
    assert residuals(T, src, dst).max() < 1e-6

    dirty = dst.copy()
    dirty[:15] = rng.uniform(0, 2000, (15, 2))           # 25% outliers
    T2, keep = ransac(src, dirty, tol_px=5, seed=3)
    assert keep.sum() >= 40 and not keep[:15].any(), (keep.sum(), keep[:15].sum())
    assert abs(T2["scale"] - s) < 1e-6

    off = fit_similarity(src[:3], (src[:3] @ R.T + t) + 30)  # seed 30 px out
    T3, d = icp(off, src, dst)
    assert np.median(d) < 1e-6, np.median(d)
    assert len(unique_names.__doc__) > 0
    print("self-check ok — similarity exact, RANSAC rejects 25% outliers, ICP converges")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="1882:1898", help="source:target, e.g. 1882:1898")
    ap.add_argument("--tol-px", type=float, default=400,
                    help="RANSAC inlier tolerance; label centres are slack by nature")
    ap.add_argument("--no-icp", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check(); sys.exit()
    s, d = a.pair.split(":")
    out = a.out or ROOT / f"work/ocr/outputs/register-{s}-{d}.json"
    rep = register(s, d, a.tol_px, not a.no_icp, out)
    print(json.dumps({k: v for k, v in rep.items() if k != "inlier_names"}, indent=2))
    print(f"\n{len(rep['inlier_names'])} anchor names: " + " · ".join(rep["inlier_names"][:10]))
    print(f"-> {out}")
