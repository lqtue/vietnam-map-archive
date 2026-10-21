"""Test A: affine instead of similarity on one plate. Rule: README.md (fixed before any run).

    python affine_test.py --config ../river-match/plates/bentre/config.json --med bentre.jpg \
        --osm bentre_all.geojsonseq --ocr ocr/bentre.all_extractions.json \
        --places ../name-vote/osm-places-261021.csv [--checks-only]
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "river-match"))
sys.path.insert(0, str(HERE.parent / "name-vote"))
import river_match as rm  # noqa: E402
import name_vote as nv  # noqa: E402


def name_checks(ocr, places):
    """Mechanical: place labels whose name is unique on the plate and matches exactly one OSM place node."""
    by = nv.nodes(places, [])
    L = nv.labels(ocr, rm.M_PER_PX, [])
    cnt = Counter(l[1] for l in L)
    out = []
    for t, n, X, Y in L:
        if cnt[n] == 1 and len(by.get(n, [])) == 1:
            x, y, nm = by[n][0]
            out.append(dict(id=f"name:{t}", px=X, py=Y, x=x, y=y))
    return out


def main():
    ap = argparse.ArgumentParser()
    for k in ("config", "med", "osm", "ocr", "places"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--out")
    ap.add_argument("--checks-only", action="store_true", help="list the checks and stop (before any fit)")
    a = ap.parse_args()
    cfgp = Path(a.config).resolve()
    cfg = json.load(open(cfgp))
    rm.configure(cfg)
    out = Path(a.out) if a.out else HERE / "plates" / cfgp.parent.name
    out.mkdir(parents=True, exist_ok=True)

    eye = [dict(id=r["id"], px=float(r["px"]), py=float(r["py"]), **dict(zip("xy", map(float, rm.to_m(float(r["lon"]), float(r["lat"]))))))
           for r in csv.DictReader(open((cfgp.parent / cfg["checks"]).resolve()))]
    named = name_checks(a.ocr, a.places)
    checks = eye + named
    print(f"checks: {len(eye)} by eye + {len(named)} by name = {len(checks)}")
    for c in named:
        print("  ", c["id"])
    json.dump(checks, open(out / "checks.json", "w"), indent=1, ensure_ascii=False)
    if a.checks_only:
        return

    # ---- baseline, exactly as river_match.main
    mask_full = rm.outline(HERE.parent / "allmaps-drafts" / f"{rm.MAP_ID}.json")
    geom, rivers = rm.osm_polygons(a.osm), rm.osm_lines(a.osm)
    G, f = 150.0, 16
    Wr, worg = rm.rasterise(geom, G, rivers)
    P, _, m = rm.plate_water(a.med, mask_full, f)
    coarse = rm.search(P, Wr, worg, G, f, rm.NORTH + np.arange(-10, 10.01, 1.0), np.arange(0.90, 1.101, 0.02), rm.refpt(P, m))
    best = max(coarse, key=lambda r: r["score"])
    second = max((float(r["peaks"][np.hypot(r["peaks"][:, 1] - best["cx"], r["peaks"][:, 2] - best["cy"]) > 5000, 0].max())
                  for r in coarse if (np.hypot(r["peaks"][:, 1] - best["cx"], r["peaks"][:, 2] - best["cy"]) > 5000).any()), default=-np.inf)
    G2, f2 = 75.0, 8
    Wr2, worg2 = rm.rasterise(geom, G2, rivers)
    P2, water2, m2 = rm.plate_water(a.med, mask_full, f2)
    fine = rm.search(P2, Wr2, worg2, G2, f2, np.arange(best["theta"] - 1.5, best["theta"] + 1.51, 0.25),
                     np.arange(best["scale"] - 0.03, best["scale"] + 0.0301, 0.005), rm.refpt(P2, m2))
    fb = max(fine, key=lambda r: r["score"])
    summ = json.load(open(cfgp.parent / "points" / "summary.json"))
    print(f"baseline reproduced: ratio {second / best['score']:.3f} (pushed {summ['coarse']['ratio']}), "
          f"theta {fb['theta']:.2f} (pushed {summ['fine']['theta']}), scale {fb['scale']:.3f} (pushed {summ['fine']['scale']})")
    sim = rm.model(fb, f2)

    def errs(fwd):
        return np.array([float(np.hypot(*(np.array(fwd(c["px"], c["py"])) - [c["x"], c["y"]]))) for c in checks])

    e_sim = errs(sim)
    print(f"similarity: eye median {np.median(e_sim[:len(eye)]):.0f} m (pushed {summ['check_median_m']}), all median {np.median(e_sim):.0f} m")

    # ---- affine: free the 2 x 2 matrix and the shift, Powell, entries within +-5 % of the similarity's
    vv, uu = np.nonzero(P2 != 0)
    w = P2[vv, uu]
    t = np.radians(fb["theta"])
    ps = fb["ps"]                                               # metres per P2 pixel
    A0 = ps * np.array([[np.cos(t), np.sin(t)], [np.sin(t), -np.cos(t)]])

    def score(p):
        A = A0 + ps * np.array([[p[2], p[3]], [p[4], p[5]]])
        x = fb["ox"] + p[0] + A[0, 0] * uu + A[0, 1] * vv
        y = fb["oy"] + p[1] + A[1, 0] * uu + A[1, 1] * vv
        s = ndi.map_coordinates(Wr2, [(worg2[1] - y) / G2, (x - worg2[0]) / G2], order=1, cval=0.0)
        return -float((w * s).sum())

    p0 = np.zeros(6)
    print(f"score at the similarity {-score(p0):.1f} (fft peak {fb['score']:.1f})")
    bounds = [(-1500, 1500)] * 2 + [(-0.05, 0.05)] * 4
    r = minimize(score, p0, method="Powell", bounds=bounds, options=dict(xtol=1e-4, ftol=1e-6, maxiter=20000))
    p = r.x
    A = A0 + ps * np.array([[p[2], p[3]], [p[4], p[5]]])
    at_bound = [i for i in range(2, 6) if abs(abs(p[i]) - 0.05) < 1e-3]
    print(f"affine score {-r.fun:.1f}; shift {p[0]:+.0f} {p[1]:+.0f} m; matrix change {np.round(p[2:], 4)}; at bound: {at_bound}")

    def aff(X, Y):
        u, v = X / f2, Y / f2
        return fb["ox"] + p[0] + A[0, 0] * u + A[0, 1] * v, fb["oy"] + p[1] + A[1, 0] * u + A[1, 1] * v

    e_aff = errs(aff)
    for c, es, ea in zip(checks, e_sim, e_aff):
        print(f"{c['id']:34s} similarity {es:6.0f} m   affine {ea:6.0f} m")
    better = float((e_aff < e_sim).mean())
    ok = len(checks) >= 8 and np.median(e_aff) <= 700 and better >= 0.70 and not at_bound
    print(f"n {len(checks)}; median similarity {np.median(e_sim):.0f}, affine {np.median(e_aff):.0f}; "
          f"affine better on {better:.0%}; at bound {at_bound} -> {'PASS' if ok else 'FAIL'}")
    json.dump(dict(n=len(checks), median_similarity=round(float(np.median(e_sim))), median_affine=round(float(np.median(e_aff))),
                   share_better=round(better, 3), at_bound=at_bound, matrix_change=[round(float(v), 4) for v in p[2:]],
                   shift_m=[round(float(v)) for v in p[:2]], errors=[dict(id=c["id"], similarity=round(float(s)), affine=round(float(e)))
                                                                    for c, s, e in zip(checks, e_sim, e_aff)],
                   verdict="pass" if ok else "fail"), open(out / "summary.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
