#!/usr/bin/env python3
"""Build an independently georeferenced six-sheet District 4 stack.

Each scan is positioned by its own Allmaps control points, never registered to
another sheet. Raster images are always present; block outlines only render
for a sheet whose SHEETS entry carries a `blocks` path (none currently do —
the 1882/1898 traces were pulled pending a redo).
"""
import argparse, csv, json, math, pathlib, re, sys, unicodedata, urllib.request

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "ocr/scripts"))
from labels import fold  # Đ -> d and tone marks off; key() below drops Đ outright

ROOT = pathlib.Path(__file__).resolve().parents[3]
ANN = ROOT / "work/ocr/outputs/annotations"
OUT = "work/ocr/outputs"
DOLING_CSV = ROOT / "work/research/doling/street-name-pairs.csv"
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
        # The app's route: the annotations bucket is private (mig 097), and the
        # route serves published maps' copies without a session.
        url = f"https://maparchive.vn/api/maps/{map_id}/annotation"
        print(f"fetching annotation: {map_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Cloudflare 403s urllib's default User-Agent.
        req = urllib.request.Request(url, headers={"User-Agent": "vma-fabric-build"})
        path.write_bytes(urllib.request.urlopen(req, timeout=30).read())
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
    words = re.sub(r"[^a-z0-9 ]", " ", text.casefold()).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


# Twin of src/lib/core/utils/placeKey.ts (placeCoreKey). labels.name_key is not
# equivalent: a different prefix list, one prefix only, no four-character floor.
GENERIC = ("rue|r|ruelle|boulevard|boul|bould|bd|blvd|avenue|av|ave|quai|quay|impasse|imp|"
           "place|pl|chemin|ch|route|rte|passage|village|vge|vlge|hameau|marche|pont|canal|"
           "arroyo|riviere|riv|fleuve|faubourg|duong|dg|pho|hem|rach|song|kenh|cho|ap|xom|"
           "cau|ben|khu|phuong|quan|xa|thon|lang|de|du|des|d|le|la|les|l|au|aux")


def core_key(text):
    full = " ".join(re.sub(r"[^a-z0-9]+", " ", fold(text)).split())
    core = re.sub(r" (de|du|des|d|le|la|les|l)$", "", re.sub(rf"^(({GENERIC}) )+", "", full))
    return core if len(core) >= 4 else full


def load_doling():
    """key(colonial or modern name) -> {modern, kind, sightings, post_title, post_date,
    post_url}, from Tim Doling's Historic Vietnam (work/research/doling/street-name-pairs.csv,
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
    seen, labels = {}, []
    ocr_path = ROOT / sheet.get("ocr", "")
    if ocr_path.is_file():
        for extraction in json.loads(ocr_path.read_text())["extractions"]:
            if extraction.get("category") in SKIP: continue
            name = key(extraction["text"])
            if len(name) < 5: continue
            x, y, w, h = extraction["global_bbox"]
            point = warp(M, [[x + w / 2, y + h / 2]])[0]
            seen.setdefault(name, []).append((extraction["text"], point))
            labels.append(dict(text=extraction["text"], category=extraction["category"], point=point))
    return dict(sheet=sheet, M=M, georef=georef, polys=polys, n_blocks=n_blocks, labels=seen, all_labels=labels, width=source["width"], height=source["height"], iiif=source["id"])


# --- Legend entries: ocr_labels rows (category legend_entry) read from Supabase ---
# Parser twin of src/lib/server/legendEntry.ts; reads follow legendRead.ts.

def note(notes, name):
    for part in (notes or "").split(";"):
        if part.strip().startswith(f"{name}="): return part.strip()[len(name) + 1:].strip() or None


def pair(raw):
    try: v = [float(x) for x in (raw or "").split(",")]
    except ValueError: return None
    return v if len(v) == 2 and all(map(math.isfinite, v)) else None


def legend_points(notes):
    """[(src, x, y)]: px / more are image pixels, point is legacy lng,lat."""
    px, ll = pair(note(notes, "px")), pair(note(notes, "point"))
    pts = [("px", *px)] if px and px[0] >= 0 and px[1] >= 0 else [("point", *ll)] if ll and abs(ll[0]) <= 180 and abs(ll[1]) <= 90 else []
    more = [pair(p) for p in (note(notes, "more") or "").split("|")]
    return pts + [("more", *p) for p in more[:20] if p and p[0] >= 0 and p[1] >= 0]


def read_legend(sheets):
    """One record per placed point. An entry with no placed point takes its
    body numeral (src "numeral") only when exactly one sits outside the legend box."""
    from eval import _rest_get  # service key from the repo-root .env
    ids = [s["sheet"].get("annotation_id", s["sheet"]["map_id"]) for s in sheets]
    rows = _rest_get("ocr_labels", {"select": "id,map_id,run_id,text,text_corrected,category,category_corrected,review_status,notes,global_x,global_y,global_w,global_h",
                                    "map_id": f"in.({','.join(ids)})", "or": "(category.eq.legend_entry,category_corrected.eq.legend_entry)", "order": "id"})
    rows = [r for r in rows if (r["category_corrected"] or r["category"]) == "legend_entry" and r["review_status"] != "rejected"]
    records, stats = [], []
    for i, (s, mid) in enumerate(zip(sheets, ids)):
        entries, rects, M = {}, {}, s["M"]
        for r in (r for r in rows if r["map_id"] == mid):
            text = r["text_corrected"] or r["text"] or ""
            m = re.match(r"(\d+)\.\s*(.*)$", text)
            n = int(m[1]) if m else int(note(r["notes"], "n") or 0)
            if n <= 0: print(f"legend: no number, skipped: {text!r} {r['notes']!r}"); continue
            if n in entries and entries[n]["ok"] and r["review_status"] != "validated": continue
            entries[n] = dict(name=m[2] if m else text, vn=note(r["notes"], "vn"), pts=legend_points(r["notes"]), ok=r["review_status"] == "validated")
            if r["global_x"] is not None:
                b = rects.setdefault(r["run_id"], [math.inf, math.inf, -math.inf, -math.inf])
                b[:] = [min(b[0], r["global_x"]), min(b[1], r["global_y"]), max(b[2], r["global_x"] + (r["global_w"] or 0)), max(b[3], r["global_y"] + (r["global_h"] or 0))]
        unplaced = [n for n, e in entries.items() if not e["pts"]]
        if unplaced:
            refs = _rest_get("ocr_labels", {"select": "text,text_corrected,global_x,global_y,global_w,global_h", "map_id": f"eq.{mid}",
                                            "category": "in.(legend_ref,other)", "review_status": "neq.rejected", "order": "id"})
            cand = {}
            for r in refs:
                t = (r["text_corrected"] or r["text"] or "").strip()
                if not t.isdigit() or not 1 <= int(t) <= max(entries) or r["global_x"] is None: continue
                x, y = r["global_x"] + (r["global_w"] or 0) / 2, r["global_y"] + (r["global_h"] or 0) / 2
                if not any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in rects.values()): cand.setdefault(int(t), []).append(("numeral", x, y))
            for n in unplaced:
                if len(cand.get(n, [])) == 1: entries[n]["pts"] = cand[n]
        outside = 0
        for n, e in sorted(entries.items()):
            keys = {k for k in (core_key(e["name"]), core_key(e["vn"] or "")) if k}
            for src, x, y in e["pts"]:
                if src == "point": g = np.array([x, y]) * K
                elif 0 <= x <= s["width"] and 0 <= y <= s["height"]: g = warp(M, [[x, y]])[0]
                else: outside += 1; continue
                records.append(dict(sheet=i, year=s["sheet"]["year"], n=n, name=e["name"], vn=e["vn"], g=g, src=src, keys=keys))
        stats.append(f"{s['sheet']['year']}: {len(entries)} entries, {sum(r['sheet'] == i for r in records)} points" + (f", {outside} outside the image" if outside else ""))
    print("legend " + "; ".join(stats))
    return records


def main(out, link_max_m, legend_link_max_m):
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
        labels = [dict(t=l["text"], k=l["category"], p=put(l["point"]).tolist()) for l in s["all_labels"]]
        layers.append(dict(year=s["sheet"]["year"], label=s["sheet"]["label"], map_id=s["sheet"].get("annotation_id", s["sheet"]["map_id"]), polys=[put(p).tolist() for p in s["polys"]], labels=labels, n_blocks=s["n_blocks"], n_labels=len(s["labels"]), georef=s["georef"], image=dict(iiif=s["iiif"], width=s["width"], height=s["height"], matrix=[round(float(v),5) for v in matrix])))
    # Union-find over (sheet, name, occurrence) nodes: a link unions the exact
    # occurrence pair it matched, so a name that resolves to different physical
    # spots on different sheet-pairs (a long street, matched at its west end for
    # one gap and its east end for the next) ends up as separate chains rather
    # than one name-keyed blob spanning two places.
    parent = {}
    def find(n):
        while parent[n] != n: n = parent[n]
        return n
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra
    links, link_node = [], []
    for i, left in enumerate(sheets[:-1]):
        right = sheets[i + 1]["labels"]
        for name, occ_left in left["labels"].items():
            occ_right = right.get(name)
            if not occ_right: continue
            (ia, (t_a, c_a)), (ib, (t_b, c_b)) = min(
                ((a, b) for a in enumerate(occ_left) for b in enumerate(occ_right)),
                key=lambda ab: np.linalg.norm(ab[0][1][1] - ab[1][1][1]))
            distance = float(np.linalg.norm(c_a - c_b))
            if distance > link_max_m: continue
            node_a, node_b = (i, name, ia), (i + 1, name, ib)
            parent.setdefault(node_a, node_a); parent.setdefault(node_b, node_b)
            union(node_a, node_b)
            links.append(dict(a=i, b=i+1, t=t_a, m=round(distance,1), p=put(c_a).tolist(), q=put(c_b).tolist(), d=DOLING.get(name)))
            link_node.append(node_a)
    # Legend pass. Legend points mark buildings, not text, so the radius is looser.
    # Legend<->legend links to the nearest LATER sheet with a match (not only the
    # adjacent one: the placed sheets are not neighbours); legend<->body links to
    # every other sheet. Both union into the same chains as the body links.
    legend = read_legend(sheets)
    body = {}
    for j, s in enumerate(sheets):
        for name, occ in s["labels"].items():
            for idx, (text, pt) in enumerate(occ): body.setdefault((j, core_key(text)), []).append(((j, name, idx), pt))
    legend_links, legend_node = [], []
    def link_to(a, ai, b_sheet, cands, kind):
        """cands: [(node, point)] already key-matched."""
        if not cands: return False
        node, pt = min(cands, key=lambda c: np.linalg.norm(c[1] - a["g"]))
        d = float(np.linalg.norm(pt - a["g"]))
        if d > legend_link_max_m: return False
        parent.setdefault(("L", ai), ("L", ai)); parent.setdefault(node, node); union(("L", ai), node)
        legend_links.append(dict(a=a["sheet"], b=b_sheet, t=a["name"], m=round(d, 1), p=put(a["g"]).tolist(), q=put(pt).tolist(), k=kind))
        legend_node.append(("L", ai))
        return True
    for ai, a in enumerate(legend):
        for j in range(a["sheet"] + 1, len(sheets)):
            if link_to(a, ai, j, [(("L", bi), b["g"]) for bi, b in enumerate(legend) if b["sheet"] == j and a["keys"] & b["keys"]], "ll"): break
        for j in range(len(sheets)):
            if j != a["sheet"]: link_to(a, ai, j, [(n, pt) for k in a["keys"] for n, pt in body.get((j, k), [])], "lb")
    roots = {r: idx for idx, r in enumerate(sorted({find(n) for n in parent}, key=str))}
    for link, node in zip(links, link_node): link["c"] = roots[find(node)]
    for link, node in zip(legend_links, legend_node): link["c"] = roots[find(node)]
    legend_links.sort(key=lambda link: link["m"])
    legend_out = [dict(sheet=r["sheet"], year=r["year"], n=r["n"], name=r["name"], vn=r["vn"], x=round(float(r["g"][0]), 1), y=round(float(r["g"][1]), 1), p=put(r["g"]).tolist(), src=r["src"],
                       **({"c": roots[find(("L", ai))]} if ("L", ai) in parent else {})) for ai, r in enumerate(legend)]
    links.sort(key=lambda link: link["m"])
    pathlib.Path(out).write_text(json.dumps(dict(layers=layers, links=links, legend=legend_out, legend_links=legend_links, meters_per_unit=1 / scale, ground_origin_m=lo.tolist(), meters_per_degree=K.tolist(), span=SPAN), separators=(",", ":")))
    print(f"wrote {len(layers)} independently georeferenced scans and {len(links)} adjacent-sheet name links, {len(legend_out)} legend points, {len(legend_links)} legend links")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(pathlib.Path(__file__).with_name("layers.json")))
    parser.add_argument("--link-max-m", type=float, default=150)
    parser.add_argument("--legend-link-max-m", type=float, default=300)
    args = parser.parse_args()
    main(args.out, args.link_max_m, args.legend_link_max_m)
