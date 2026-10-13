#!/usr/bin/env python3
"""How well does one projective transform (a flat ground seen in perspective) fit the 1881 view?

    python3 work/image-processing/experiments/panorama-match/score.py ANNOTATION.json
    python3 work/image-processing/experiments/panorama-match/score.py --self-check

ANNOTATION.json is the Georeference Annotation the Allmaps editor exports, or plain `x y lng lat` lines. Each point is left out in
turn, the transform is fitted to the rest, and the left-out point's miss on the ground is reported in
metres. Points are named from points.csv when the map click lands within 30 m of one.
Kill result (docs: idea gate): median left-out miss > 60 m.
"""
import csv, json, sys
from pathlib import Path
import numpy as np

M_PER_DEG = np.array([111_320 * np.cos(np.radians(10.78)), 111_133])


def homography(src, dst):
    """DLT with Hartley normalisation; src, dst (N,2), N >= 4."""
    def norm(p):
        c = p.mean(0); s = np.sqrt(2) / np.mean(np.linalg.norm(p - c, axis=1))
        return np.array([[s, 0, -s * c[0]], [0, s, -s * c[1]], [0, 0, 1]])
    Ts, Td = norm(src), norm(dst)
    a = (Ts @ np.c_[src, np.ones(len(src))].T).T; b = (Td @ np.c_[dst, np.ones(len(dst))].T).T
    rows = []
    for (x, y, _), (u, v, _) in zip(a, b):
        rows += [[-x, -y, -1, 0, 0, 0, u * x, u * y, u], [0, 0, 0, -x, -y, -1, v * x, v * y, v]]
    H = np.linalg.svd(np.array(rows))[2][-1].reshape(3, 3)
    return np.linalg.inv(Td) @ H @ Ts


def apply(H, p):
    q = (H @ np.c_[p, np.ones(len(p))].T).T
    return q[:, :2] / q[:, 2:]


def loo(px, m):
    """Left-out miss in metres for each point."""
    out = []
    for i in range(len(px)):
        k = np.arange(len(px)) != i
        out.append(np.linalg.norm(apply(homography(px[k], m[k]), px[i:i + 1])[0] - m[i]))
    return np.array(out)


def gcps(ann):
    items = ann.get("items", [ann]) if ann.get("type") == "AnnotationPage" else [ann]
    feats = [f for it in items for f in it["body"]["features"]]
    return (np.array([f["properties"]["resourceCoords"] for f in feats], float),
            np.array([f["geometry"]["coordinates"] for f in feats], float))


def read(path):
    """An exported annotation (JSON), or plain `x y lng lat` lines as the editor's GCP box shows them."""
    text = open(path).read()
    if text.lstrip().startswith("{"):
        return gcps(json.loads(text))
    a = np.array([l.replace("-gcp", "").split()[:4] for l in text.splitlines() if l.strip()], float)
    return a[:, :2], a[:, 2:]


def main(path):
    px, ll = read(path)
    if len(px) < 6:
        sys.exit(f"{len(px)} points: need at least 6 (4 fit the transform exactly, nothing is left to check)")
    o = ll.mean(0); m = (ll - o) * M_PER_DEG
    named = list(csv.DictReader(open(Path(__file__).with_name("points.csv"))))
    ref = (np.array([[float(r["lng"]), float(r["lat"])] for r in named]) - o) * M_PER_DEG
    fit = np.linalg.norm(apply(homography(px, m), px) - m, axis=1)
    miss = loo(px, m)
    print(f"{'point':<18}{'map click vs points.csv m':>27}{'in-fit m':>10}{'left-out m':>12}")
    for i in np.argsort(-miss):
        d = np.linalg.norm(ref - m[i], axis=1); j = int(d.argmin())
        name = named[j]["id"] if d[j] < 30 else f"#{i}"
        print(f"{name:<18}{d[j]:>27.1f}{fit[i]:>10.1f}{miss[i]:>12.1f}")
    print(f"\nn={len(px)}  in-fit RMS {np.sqrt((fit**2).mean()):.1f} m  "
          f"left-out median {np.median(miss):.1f} m  max {miss.max():.1f} m")
    print("KILL (median > 60 m)" if np.median(miss) > 60 else "passes the 60 m gate")


def self_check():
    rng = np.random.default_rng(0)
    H = np.array([[0.8, 0.3, 10], [-0.1, 1.2, 5], [1e-4, 3e-4, 1]])
    px = rng.uniform(0, 10_000, (12, 2))
    m = apply(H, px)
    assert np.allclose(apply(homography(px, m), px), m, atol=1e-6)
    assert loo(px, m).max() < 1e-6
    noisy = m + rng.normal(0, 5, m.shape)
    assert 0 < np.median(loo(px, noisy)) < 50
    print("self-check ok")


if __name__ == "__main__":
    self_check() if sys.argv[1:] == ["--self-check"] else main(sys.argv[1])
