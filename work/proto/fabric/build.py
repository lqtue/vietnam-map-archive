#!/usr/bin/env python3
"""Flatten per-year blocks + OCR labels into layers.json for index.html.

Every sheet is warped to GROUND METRES by its own Allmaps GCPs -- the same
document `scale.py` and `georef_error.py` read -- so the layers are stacked on
the world, not on each other. Adding a sheet is one entry in SHEETS; nothing
has to be registered to anything.

    curl .../storage/v1/object/public/annotations/<mapId>.json \\
         -o work/ocr/outputs/annotations/<mapId>.json
    python3 work/proto/fabric/build.py

An affine is fitted to the GCPs rather than the transformation the annotation
declares. Reason: the declared type varies across the corpus (helmert,
polynomial 1, thinPlateSpline) and an affine is the one form every sheet's
points support, so the stack is built the same way for all of them. It also
reproduces `georef_error.md` exactly on 1882 (RMSE 10.6 m, worst 17.4 m), which
is the check that this file reads the annotation the way the rest of the repo
does.

Watch the reported axis scales. An affine has one scale per axis and no more;
where the two differ by a couple of percent the paper or the scan is distorted
in a way NO affine can absorb, and that difference -- not the georeference --
is the floor on how well two sheets can overlap.

ponytail: equirectangular metres about LAT0, not a projection library. At this
latitude over a 6 km sheet the error is centimetres; swap for pyproj when the
corpus leaves Saigon.
"""
import argparse, json, math, pathlib, re, unicodedata
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
ANN = ROOT / "work/ocr/outputs/annotations"
OUT_DIR = "work/ocr/outputs"
LAT0 = 10.775
K = np.array([111320.0 * math.cos(math.radians(LAT0)), 110540.0])
SPAN, PREC, KEEP = 1000.0, 1, 500
SKIP_CAT = {"title", "legend", "other"}      # sheet furniture, not places

SHEETS = [
    dict(year=1882, label="Plan Cadastral", map_id="0e02b9d9-9d40-4cca-8e41-8c8373d54d3b",
         blocks=f"{OUT_DIR}/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/colour-20260919-normalized/blocks.clean.geojson",
         ocr=f"{OUT_DIR}/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/runs/post0910/all_extractions.json"),
    dict(year=1898, label="Bertaux", map_id="20ec4f9a-16bd-4895-a593-40c6ed9c9555",
         blocks=f"{OUT_DIR}/20ec4f9a-16bd-4895-a593-40c6ed9c9555/colour-1898-20260919-normalized/blocks.clean.geojson",
         ocr=f"{OUT_DIR}/20ec4f9a-16bd-4895-a593-40c6ed9c9555/runs/2026-09-13T1036-20ec4f9a/all_extractions.json"),
]


def affine(map_id):
    """px -> local metres, least squares over the annotation's GCPs."""
    doc = json.loads((ANN / f"{map_id}.json").read_text())
    m = doc.get("items", [doc])[0]
    feats = m["body"]["features"]
    px = np.array([f["properties"]["resourceCoords"] for f in feats], float)
    gr = np.array([f["geometry"]["coordinates"][:2] for f in feats], float) * K
    A = np.hstack([px, np.ones((len(px), 1))])
    M, *_ = np.linalg.lstsq(A, gr, rcond=None)
    res = np.linalg.norm(A @ M - gr, axis=1)
    sv = np.linalg.svd(M[:2])[1]
    return M, dict(
        gcps=len(px), declared=m["body"]["transformation"]["type"],
        rmse_m=round(float(np.sqrt((res ** 2).mean())), 1),
        worst_m=round(float(res.max()), 1),
        # 3 GCPs give 6 equations for a 6-parameter affine: RMSE 0 is arithmetic,
        # not accuracy. georef_error.md makes the same point about the 1923 sheet.
        exact=len(px) <= 3,
        m_per_px=[round(float(sv[0]), 4), round(float(sv[1]), 4)],
        scale_spread_pct=round(float(100 * abs(sv[0] - sv[1]) / sv.mean()), 2),
        rot_deg=round(math.degrees(math.atan2(M[0, 1], M[0, 0])), 2))


def warp(M, pts):
    p = np.asarray(pts, float)
    return np.hstack([p, np.ones((len(p), 1))]) @ M


def rings(g):
    if g["type"] == "Polygon":
        return [g["coordinates"][0]]
    if g["type"] == "MultiPolygon":
        return [p[0] for p in g["coordinates"]]
    return []


def name_key(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.casefold()).split())


def read(sheet):
    M, info = affine(sheet["map_id"])
    feats = json.loads((ROOT / sheet["blocks"]).read_text())["features"]
    feats.sort(key=lambda f: -(f["properties"].get("area_px") or 0))
    polys = [warp(M, r) for f in feats[:KEEP] for r in rings(f["geometry"])]

    labels, seen = [], {}
    for e in json.loads((ROOT / sheet["ocr"]).read_text())["extractions"]:
        if e.get("category") in SKIP_CAT:
            continue
        k = name_key(e["text"])
        if len(k) < 5:
            continue
        x, y, w, h = e["global_bbox"]
        seen.setdefault(k, []).append((e["text"], warp(M, [[x + w / 2, y + h / 2]])[0]))
    # a name printed twice on one sheet is a correspondence to nothing
    labels = [dict(t=v[0][0], k=k, c=v[0][1]) for k, v in seen.items() if len(v) == 1]
    return dict(sheet=sheet, M=M, info=info, polys=polys, labels=labels,
                n_blocks=len(feats))


def main(out, link_max_m):
    read_sheets = [read(s) for s in SHEETS]
    allpts = np.vstack([p for s in read_sheets for p in s["polys"]])
    # percentiles, not min/max: a surviving neatline arm reaches far past the
    # mapped city and would otherwise set the frame and squash everything else
    lo, hi = np.percentile(allpts, 0.5, axis=0), np.percentile(allpts, 99.5, axis=0)
    sc = SPAN / (hi - lo).max()

    def put(p):
        q = (np.asarray(p, float) - lo) * sc
        q[..., 1] = SPAN - q[..., 1]          # metres go north-up, screen y goes down
        return np.round(q, PREC)

    def in_frame(q):
        return (q[:, 0].max() > 0 and q[:, 0].min() < SPAN
                and q[:, 1].max() > 0 and q[:, 1].min() < SPAN)

    layers, links = [], []
    for s in read_sheets:
        kept = [q for q in (put(p) for p in s["polys"]) if in_frame(q)]
        layers.append(dict(year=s["sheet"]["year"], label=s["sheet"]["label"],
                           polys=[q.tolist() for q in kept],
                           n_blocks=s["n_blocks"], n_labels=len(s["labels"]),
                           georef=s["info"]))
    for i in range(len(read_sheets) - 1):
        later = {l["k"]: l for l in read_sheets[i + 1]["labels"]}
        for l in read_sheets[i]["labels"]:
            o = later.get(l["k"])
            if o is None:
                continue
            d = float(np.linalg.norm(l["c"] - o["c"]))
            # both ends are now on the ground, so a link that lands hundreds of
            # metres away is a coincidence of spelling, not a place
            if d <= link_max_m:
                links.append(dict(a=i, b=i + 1, t=l["t"], m=round(d, 1),
                                  p=put(l["c"]).tolist(), q=put(o["c"]).tolist()))
    links.sort(key=lambda L: L["m"])

    pathlib.Path(out).write_text(json.dumps(dict(layers=layers, links=links),
                                            separators=(",", ":")))
    for l in layers:
        g = l["georef"]
        flag = " EXACT-FIT, unverifiable" if g["exact"] else ""
        print(f"{l['year']}: {len(l['polys'])} polys, {l['n_labels']} names · "
              f"{g['gcps']} GCPs ({g['declared']}) RMSE {g['rmse_m']} m{flag} · "
              f"rot {g['rot_deg']:+.2f}° · axis scales {g['m_per_px']} "
              f"({g['scale_spread_pct']}% apart)")
    if links:
        d = [L["m"] for L in links]
        print(f"name links within {link_max_m:.0f} m: {len(links)} · "
              f"median {np.median(d):.0f} m · best: "
              + " · ".join(f"{L['t']} ({L['m']:.0f} m)" for L in links[:5]))
    assert layers and all(l["polys"] for l in layers)
    for l in layers:
        pts = [c for p in l["polys"] for c in p]
        frac = sum(0 <= c[0] <= SPAN and 0 <= c[1] <= SPAN for c in pts) / len(pts)
        assert frac > 0.9, f"{l['year']} outside the union frame ({frac:.0%})"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pathlib.Path(__file__).with_name("layers.json")))
    ap.add_argument("--link-max-m", type=float, default=150)
    a = ap.parse_args()
    main(a.out, a.link_max_m)
