#!/usr/bin/env python3
"""Build an independently georeferenced six-sheet District 4 stack.

Each scan is positioned by its own Allmaps control points, never registered to
another sheet. Raster images are always present; block outlines only render
for a sheet whose SHEETS entry carries a `blocks` path (none currently do —
the 1882/1898 traces were pulled pending a redo).
"""
import argparse, csv, json, math, pathlib, re, unicodedata, urllib.request

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
ANN = ROOT / "work/ocr/outputs/annotations"
OUT = "work/ocr/outputs"
DOLING_CSV = ROOT / "work/doling/street-name-pairs.csv"
K = np.array([111320.0 * math.cos(math.radians(10.775)), 110540.0])
SPAN, PREC, KEEP = 1000.0, 1, 500
SKIP = {"title", "legend", "other"}

SHEETS = [
    dict(year=1882, label="Plan Cadastral", map_id="0e02b9d9-9d40-4cca-8e41-8c8373d54d3b", ocr=f"{OUT}/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/runs/post0910/all_extractions.json"),
    dict(year=1898, label="Bertaux", map_id="20ec4f9a-16bd-4895-a593-40c6ed9c9555", ocr=f"{OUT}/20ec4f9a-16bd-4895-a593-40c6ed9c9555/runs/2026-09-13T1036-20ec4f9a/all_extractions.json"),
    dict(year=1923, label="Saigon – Cholon", map_id="1bce28f0-aa82-48eb-8e33-8f0b07182c2f", ocr=f"{OUT}/1bce28f0-aa82-48eb-8e33-8f0b07182c2f/runs/2026-09-12T1324-1bce28f0/all_extractions.json"),
    dict(year=1942, label="Plan de Saigon – Cho Lon", map_id="eca788e5-6780-4dca-bf23-7651a1c48aba-20260911", annotation_id="eca788e5-6780-4dca-bf23-7651a1c48aba", ocr=f"{OUT}/eca788e5-6780-4dca-bf23-7651a1c48aba/runs/2026-09-11T1628-eca788e5/all_extractions.json"),
    dict(year=1959, label="Đô thành Sài Gòn", map_id="34d4edb2-f7df-4c47-a65a-f6b471400396", ocr=f"{OUT}/34d4edb2-f7df-4c47-a65a-f6b471400396/runs/2026-09-10T0930-34d4edb2/all_extractions.json"),
    dict(year=1968, label="Sài Gòn – Việt Nam City Maps", map_id="3a446d85-25a8-4e81-9cfc-8de357c3a5df", ocr=f"{OUT}/3a446d85-25a8-4e81-9cfc-8de357c3a5df/runs/body-1968-20260910g-t800/all_extractions.json"),
]


def annotation(map_id):
    path = ANN / f"{map_id}.json"
    if not path.exists():
        # Public production mirror. These inputs are archive data, not secrets.
        base = "https://trioykjhhwrruwjsklfo.supabase.co"
        url = f"{base.rstrip('/')}/storage/v1/object/public/annotations/{map_id}.json"
        print(f"fetching annotation: {map_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(url, timeout=30).read())
    return json.loads(path.read_text())["items"][0]


def warp(M, pts):
    pts = np.asarray(pts, float)
    return np.hstack([pts, np.ones((len(pts), 1))]) @ M


def affine(item):
    features = item["body"]["features"]
    px = np.array([f["properties"]["resourceCoords"] for f in features], float)
    ground = np.array([f["geometry"]["coordinates"][:2] for f in features], float) * K
    A = np.hstack([px, np.ones((len(px), 1))])
    M, *_ = np.linalg.lstsq(A, ground, rcond=None)
    residual = np.linalg.norm(A @ M - ground, axis=1)
    singular = np.linalg.svd(M[:2])[1]
    return M, dict(gcps=len(px), declared=item["body"]["transformation"]["type"], rmse_m=round(float(np.sqrt((residual**2).mean())), 1), exact=len(px) <= 3, scale_spread_pct=round(float(100 * abs(singular[0] - singular[1]) / singular.mean()), 2))


def rings(geometry):
    if geometry["type"] == "Polygon": return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon": return [p[0] for p in geometry["coordinates"]]
    return []


def key(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.casefold()).split())


def load_doling():
    """key(colonial or modern name) -> {modern, kind, sightings, post_title, post_date,
    post_url}, from Tim Doling's Historic Vietnam (work/doling/street-name-pairs.csv,
    given by the author, cited with permission -- see the file's own header for terms).
    Unreviewed by a human yet (docs/search-plan.md's `doling-review`), so this is shown
    in the viewer as an attributed citation, never merged into a printed label as fact.
    Colonial keys checked first, since five of the six sheets print colonial names; a
    modern key is only added where no colonial one already claims it."""
    if not DOLING_CSV.is_file(): return {}
    by_colonial, by_modern = {}, {}
    with open(DOLING_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = dict(modern=row["modern"], kind=row["kind"], sightings=int(row["sightings"]),
                      post_title=row["post_title"], post_date=row["post_date"], post_url=row["post_url"])
            ck = key(row["colonial"])
            if ck and ck not in by_colonial: by_colonial[ck] = dict(d, colonial=row["colonial"])
            mk = key(re.sub(r"^\d+[-\d]*\s+", "", row["modern"]))
            if mk and mk not in by_modern: by_modern[mk] = dict(d, colonial=row["colonial"])
    return {**by_modern, **by_colonial}


DOLING = load_doling()


def read(sheet):
    item = annotation(sheet.get("annotation_id", sheet["map_id"]))
    source = item["target"]["source"]
    M, georef = affine(item)
    polys, n_blocks = [], 0
    block_path = ROOT / sheet.get("blocks", "")
    if block_path.is_file():
        features = json.loads(block_path.read_text())["features"]
        n_blocks = len(features)
        features.sort(key=lambda f: -(f["properties"].get("area_px") or 0))
        polys = [warp(M, ring) for f in features[:KEEP] for ring in rings(f["geometry"])]
    seen = {}
    ocr_path = ROOT / sheet.get("ocr", "")
    if ocr_path.is_file():
        for extraction in json.loads(ocr_path.read_text())["extractions"]:
            if extraction.get("category") in SKIP: continue
            name = key(extraction["text"])
            if len(name) < 5: continue
            x, y, w, h = extraction["global_bbox"]
            seen.setdefault(name, []).append((extraction["text"], warp(M, [[x + w / 2, y + h / 2]])[0]))
    return dict(sheet=sheet, M=M, georef=georef, polys=polys, n_blocks=n_blocks, labels=seen, width=source["width"], height=source["height"], iiif=source["id"])


def main(out, link_max_m):
    sheets = [read(s) for s in SHEETS]
    corners = np.vstack([warp(s["M"], [[0, 0], [s["width"], 0], [s["width"], s["height"]], [0, s["height"]]]) for s in sheets])
    lo, hi = corners.min(axis=0), corners.max(axis=0)
    scale = SPAN / (hi - lo).max()
    def put(p):
        q = (np.asarray(p, float) - lo) * scale
        q[..., 1] = SPAN - q[..., 1]
        return np.round(q, PREC)
    layers = []
    for s in sheets:
        M = s["M"]
        matrix = [M[0,0]*scale, -M[0,1]*scale, M[1,0]*scale, -M[1,1]*scale, (M[2,0]-lo[0])*scale, SPAN-(M[2,1]-lo[1])*scale]
        layers.append(dict(year=s["sheet"]["year"], label=s["sheet"]["label"], polys=[put(p).tolist() for p in s["polys"]], n_blocks=s["n_blocks"], n_labels=len(s["labels"]), georef=s["georef"], image=dict(iiif=s["iiif"], width=s["width"], height=s["height"], matrix=[round(float(v),5) for v in matrix])))
    links = []
    for i, left in enumerate(sheets[:-1]):
        right = sheets[i + 1]["labels"]
        for name, occ_left in left["labels"].items():
            occ_right = right.get(name)
            if not occ_right: continue
            (t_a, c_a), (t_b, c_b) = min(((a, b) for a in occ_left for b in occ_right), key=lambda ab: np.linalg.norm(ab[0][1] - ab[1][1]))
            distance = float(np.linalg.norm(c_a - c_b))
            if distance <= link_max_m: links.append(dict(a=i, b=i+1, t=t_a, m=round(distance,1), p=put(c_a).tolist(), q=put(c_b).tolist(), d=DOLING.get(name)))
    links.sort(key=lambda link: link["m"])
    pathlib.Path(out).write_text(json.dumps(dict(layers=layers, links=links), separators=(",", ":")))
    print(f"wrote {len(layers)} independently georeferenced scans and {len(links)} adjacent-sheet name links")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(pathlib.Path(__file__).with_name("layers.json")))
    parser.add_argument("--link-max-m", type=float, default=150)
    args = parser.parse_args()
    main(args.out, args.link_max_m)
