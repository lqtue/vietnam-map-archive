"""Name-vote: place a Cochinchina plate from printed village names. Rule: README.md (fixed before any fit).

    python name_vote.py --config ../river-match/plates/sa-dec/config.json \
        --ocr ocr/sa-dec.all_extractions.json --osm osm-places-261021.csv [--out DIR]
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "river-match"))
import river_match as rm  # noqa: E402

BIN = 1000.0                  # vote bin, m
EXCL = 2000.0                 # held-out radius round each check, m
PREFIX = ("ap ", "xa ", "thon ", "phuong ", "thi tran ", "khom ", "lang ")
LINE_WORDS = {"rach", "kinh", "song", "route", "arrond", "fleuve", "canal", "riviere", "chemin", "enclave"}


def norm(s):
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z ]", " ", s)
    s = " ".join(s.split())
    for p in PREFIX:
        if s.startswith(p):
            s = s[len(p):]
    return s


def labels(path, ps0, check_px):
    out = []
    for e in json.load(open(path))["extractions"]:
        t = e["text"].strip()
        if e["category"] != "place" or e["confidence"] < 0.5 or t.endswith("...") or re.search(r"ARR", t.upper()):
            continue
        n = norm(t)
        if len(n.replace(" ", "")) < 2 or set(n.split()) & LINE_WORDS:
            continue
        x, y, w, h = e["global_bbox"]
        cx, cy = x + w / 2, y + h / 2
        if any(np.hypot(cx - px, cy - py) * ps0 < EXCL for px, py in check_px):
            continue
        out.append((t, n, cx, cy))
    return out


def nodes(path, check_m):
    S, W, N, E = rm.BBOX
    by = defaultdict(list)
    for r in csv.DictReader(open(path)):
        lon, lat = float(r["lon"]), float(r["lat"])
        if not (S <= lat <= N and W <= lon <= E):
            continue
        x, y = rm.to_m(lon, lat)
        if any(np.hypot(x - cx, y - cy) < EXCL for cx, cy in check_m):
            continue
        for nm in {norm(r["name"]), norm(r["name_vi"])} - {""}:
            by[nm].append((float(x), float(y), r["name"]))
    return by


def votes(L, by, theta, scale):
    """{(bx, by): {label index: weight}} and the shifts behind each."""
    t, ps = np.radians(theta), rm.M_PER_PX * scale
    acc = defaultdict(dict)
    for i, (_, n, X, Y) in enumerate(L):
        c = by.get(n)
        if not c:
            continue
        lx, ly = ps * (np.cos(t) * X + np.sin(t) * Y), ps * (np.sin(t) * X - np.cos(t) * Y)
        for nx, ny, _ in c:
            sx, sy = nx - lx, ny - ly
            acc[(int(np.floor(sx / BIN)), int(np.floor(sy / BIN)))][i] = 1.0 / len(c)
    return acc


def peaks(acc):
    """Smoothed score (3 x 3 neighbours) per bin."""
    out = {}
    for (bx, by_) in acc:
        got = {}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i, w in acc.get((bx + dx, by_ + dy), {}).items():
                    got[i] = max(got.get(i, 0), w)
        out[(bx, by_)] = sum(got.values())
    return out


def search(L, by, thetas, scales, ref, prior_km=30):
    res = []
    for th in thetas:
        t = np.radians(th)
        for sc in scales:
            ps = rm.M_PER_PX * sc
            rx, ry = ps * (np.cos(t) * ref[0] + np.sin(t) * ref[1]), ps * (np.sin(t) * ref[0] - np.cos(t) * ref[1])
            for b, s in peaks(votes(L, by, th, sc)).items():
                cx, cy = (b[0] + .5) * BIN + rx, (b[1] + .5) * BIN + ry     # plate reference point, metric
                if np.hypot(cx, cy) <= prior_km * 1000:
                    res.append(dict(theta=th, scale=sc, ps=ps, score=s, bin=b, cx=cx, cy=cy))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ocr", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    cfgp = Path(a.config).resolve()
    cfg = json.load(open(cfgp))
    rm.configure(cfg)
    out = Path(a.out) if a.out else HERE / "plates" / cfgp.parent.name
    out.mkdir(parents=True, exist_ok=True)

    checks = list(csv.DictReader(open((cfgp.parent / cfg["checks"]).resolve())))
    check_px = [(float(r["px"]), float(r["py"])) for r in checks]
    check_m = [tuple(map(float, rm.to_m(float(r["lon"]), float(r["lat"])))) for r in checks]
    L = labels(a.ocr, rm.M_PER_PX, check_px)
    by = nodes(a.osm, check_m)
    n_match = sum(1 for l in L if l[1] in by)
    print(f"labels used {len(L)}, with a same-name node {n_match}; node names {len(by)}")

    d = json.load(open(HERE.parent / "allmaps-drafts" / f"{rm.MAP_ID}.json"))["items"][0]["target"]["selector"]["value"]
    pts = [tuple(map(float, p.split(","))) for p in re.search(r'points="([^"]*)"', d).group(1).split()]
    cen = Polygon(pts).centroid
    ref = (cen.x, cen.y) if rm.REF == "mask" else (rm.FULL[0] / 2, rm.FULL[1] / 2)

    coarse = search(L, by, rm.NORTH + np.arange(-10, 10.01, 1.0), np.arange(0.90, 1.101, 0.02), ref)
    if not coarse:
        print("no votes inside the prior")
        return
    best = max(coarse, key=lambda r: r["score"])
    far = [r for r in coarse if np.hypot(r["cx"] - best["cx"], r["cy"] - best["cy"]) > 5000]
    second = max((r["score"] for r in far), default=0.0)
    ratio = second / best["score"]
    print(f"coarse best theta {best['theta']:.1f} scale {best['scale']:.2f} score {best['score']:.1f}; second {second:.1f}; ratio {ratio:.3f}")

    fine = search(L, by, np.arange(best["theta"] - 1.5, best["theta"] + 1.51, 0.25),
                  np.arange(best["scale"] - 0.02, best["scale"] + 0.0201, 0.005), ref)
    fb = max(fine, key=lambda r: r["score"])
    # shift: median of the contributing label-node shifts inside the best bin's neighbourhood
    t, ps = np.radians(fb["theta"]), fb["ps"]
    sh, who = [], set()
    for i, (_, n, X, Y) in enumerate(L):
        lx, ly = ps * (np.cos(t) * X + np.sin(t) * Y), ps * (np.sin(t) * X - np.cos(t) * Y)
        for nx, ny, _ in by.get(n, []):
            sx, sy = nx - lx, ny - ly
            if abs(sx - (fb["bin"][0] + .5) * BIN) < 1.5 * BIN and abs(sy - (fb["bin"][1] + .5) * BIN) < 1.5 * BIN:
                sh.append((sx, sy)); who.add(i)
    ox, oy = np.median(np.array(sh), axis=0)
    agree = []
    for i in sorted(who):
        _, n, X, Y = L[i]
        lx, ly = ps * (np.cos(t) * X + np.sin(t) * Y) + ox, ps * (np.sin(t) * X - np.cos(t) * Y) + oy
        k = min(by[n], key=lambda c: np.hypot(c[0] - lx, c[1] - ly))
        if np.hypot(k[0] - lx, k[1] - ly) <= 1000:
            agree.append(i)
    print(f"fine theta {fb['theta']:.2f} scale {fb['scale']:.3f} score {fb['score']:.1f}; distinct labels agreeing within 1 km: {len(agree)}")

    errs = []
    for r in checks:
        X, Y = float(r["px"]), float(r["py"])
        x, y = ox + ps * (np.cos(t) * X + np.sin(t) * Y), oy + ps * (np.sin(t) * X - np.cos(t) * Y)
        tx, ty = rm.to_m(float(r["lon"]), float(r["lat"]))
        e = float(np.hypot(x - tx, y - ty)); errs.append(e)
        print(f"check {r['id']}: error {e:.0f} m (E {x - tx:+.0f}, N {y - ty:+.0f})")
    med = float(np.median(errs))
    ok = ratio < 0.70 and med <= 1000 and len(errs) >= 3 and len(agree) >= 8
    print(f"held-out median {med:.0f} m, n {len(errs)}; ratio {ratio:.3f}; names {len(agree)} -> {'PASS' if ok else 'FAIL'}")
    json.dump(dict(labels_used=len(L), labels_with_node=n_match, coarse=dict(theta=best["theta"], scale=round(best["scale"], 3), score=round(best["score"], 1),
                   second_peak=round(second, 1), ratio=round(ratio, 3)),
                   fine=dict(theta=fb["theta"], scale=round(fb["scale"], 4), m_per_px_full=round(fb["ps"], 4), score=round(fb["score"], 1), shift_m=[round(ox), round(oy)]),
                   names_agreeing=len(agree), agreeing=[L[i][0] for i in agree], check_errors_m=[round(e) for e in errs],
                   check_median_m=round(med), verdict="pass" if ok else "fail"), open(out / "summary.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
