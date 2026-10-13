#!/usr/bin/env python3
"""What stands today where a sheet names a place — candidates from position, name and type.

    python3 work/image-processing/scripts/name_today.py --map-id <uuid>          # write the CSV
    python3 work/image-processing/scripts/name_today.py --map-id <uuid> --eval   # score vs legend_finds
    python3 work/image-processing/scripts/name_today.py --self-check             # no network, no data

An editor placing a legend point finds today's equivalent by hand: they search
OpenStreetMap for the old name, and migration 119 keeps what they typed and what
they picked (`legend_finds`). This does the same lookup without the person: the
label's position (its legend point `px=` if placed, else its box centre) goes
through the sheet's own control points to lng/lat, and every named structure in
the 2023 HCMC topo layer (`label_congtrinhs`, local; the owner treats this data as
public, 2026-10-12 — keep `source` on every row so it can be traced or pulled) within --radius metres is scored on

    shared distinctive name tokens  (accents and type words stripped)
    same kind of place               (hôpital / bệnh viện / hospital → one kind)
    distance                         (nearer is better; the fit is ±10-15 m)

Candidates also come from OpenStreetMap when `results/prior/<map-id>/landmarks_overpass.json`
exists (named features only; the distance is to the feature's outline, not its centre; each carries
`osm_type/osm_id` and `wikidata`). A topo and an OSM feature within 40 m of each other that share a
name token are one candidate holding both ids. `source` is `tasco`, `osm` or `osm+tasco` on every row.

Kind words inside a brand do not make a civic kind: "Khách sạn Park Hyatt" is a hotel, not a park
(`kinds(..., brand=True)`). That was the "PARC DU GÉNIE -> Park Hyatt" leak.

It proposes; a person decides. `--eval` scores the proposals against the
editors' own picks: a hit is a candidate lying within --hit-m of the OSM point
the editor chose. Those 27 picks are a DEV set (the scorer was tuned on them,
results/prior/eval-freeze.json): the number printed is in-sample, never accuracy.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

KINDS = {  # accent-stripped, upper-case; multi-word keys match as phrases
    "hospital": ["HOPITAL", "HOSPITAL", "BENH VIEN", "BAO SANH VIEN", "DUONG DUONG", "CLINIC", "AMBULANCE", "MATERNITY"],
    "church": ["EGLISE", "CATHEDRALE", "CHAPELLE", "CHURCH", "CATHEDRAL", "CHAPEL", "NHA THO", "THANH DUONG"],
    "school": ["ECOLE", "COLLEGE", "LYCEE", "SCHOOL", "TRUONG", "INSTITUTION", "SEMINAIRE", "CHUNG VIEN"],
    "market": ["MARCHE", "MARKET", "CHO"],
    "temple": ["PAGODE", "TEMPLE", "PAGODA", "CHUA", "MIEU", "DEN", "DINH THAN", "TINH XA", "THANH THAT"],
    "park": ["JARDIN", "PARC", "PARK", "CONG VIEN", "SQUARE", "VUON"],
    "government": ["DIRECTION", "MINISTRY", "MINISTERE", "BO TAI", "BO CONG", "TOA HANH CHANH", "TOA AN", "PREFECTURE",
                   "MAIRIE", "HOTEL DE VILLE", "UBND", "UY BAN", "OFFICE", "PALAIS", "DINH", "TRESOR", "KHO BAC"],
    "military": ["CASERNE", "ARSENAL", "CITADELLE", "BARRACKS", "QUAN KHU", "BO CHI HUY"],
    "prison": ["PRISON", "KHAM", "TRAI GIAM"],
    "post": ["POSTE", "POST", "BUU DIEN"],
    "convent": ["COUVENT", "CARMEL", "TU VIEN", "SAINTE ENFANCE"],
}
# Words that name a kind or a filler, not a place: never count as a shared name.
STOP = {w for ks in KINDS.values() for k in ks for w in k.split()} | {
    "DE", "DU", "DES", "LA", "LE", "LES", "ET", "THE", "OF", "AND", "SAINT", "ST", "NATIONAL", "QUOC", "GIA",
    "THANH", "PHO", "HO", "CHI", "MINH", "TP", "HCM", "SAI", "GON", "SAIGON", "NO", "SO", "CO", "SE", "VIEN",
    "VGE", "VILLAGE",
}
# A name saying one of these is a business or a lodging, whatever kind word sits inside the brand.
COMMERCIAL = ["KHACH SAN", "HOTEL", "MOTEL", "HOSTEL", "NHA NGHI", "RESTAURANT", "NHA HANG", "SHOP", "STORE", "BANK",
              "NGAN HANG", "CAFE", "COFFEE", "CA PHE", "SPA", "KARAOKE", "MALL", "SUPERMARKET", "SIEU THI",
              "CUA HANG", "THUONG MAI", "CONG TY", "COMPANY", "APARTMENT", "CAN HO"]
NON_PLACE = {"street", "legend_ref", "title", "hydrology"}
PLACE_CATS = {"institution", "place", "building", "legend"}  # the categories that can name a place
PLACED_ONLY = {"legend", "legend_entry"}  # their box is the legend; only a `px=` note says where the place is
MERGE_M = 40.0
OSM_NAMES = ("name", "name:vi", "name:en", "name:fr", "old_name", "alt_name")


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").upper()
    return " " + re.sub(r"[^A-Z0-9]+", " ", s).strip() + " "


def kinds(s: str, brand: bool = False, extra: set[str] | None = None) -> set[str]:
    """Kinds a name says. brand=True is for a candidate: a business or lodging word makes it commercial and
    nothing else (a kind word inside a brand is not the kind of place). "Hôtel de Ville" is the town hall."""
    f = fold(s)
    got = {k for k, keys in KINDS.items() if any(f" {key.strip()} " in f for key in keys)} | set(extra or ())
    if brand:
        plain = f.replace(" HOTEL DE VILLE ", " ")
        if "commercial" in got or any(f" {c} " in plain for c in COMMERCIAL):
            return {"commercial"}
    return got


def tokens(s: str) -> set[str]:
    return {t for t in fold(s).split() if len(t) > 1 and t not in STOP and not t.isdigit()}


def score(label_names: list[str], cand: str, d_m: float, radius: float,
          cand_kinds: set[str] | None = None) -> tuple[float, int, bool]:
    lt = set().union(*(tokens(n) for n in label_names))
    shared = len(lt & tokens(cand))
    same_kind = bool(set().union(*(kinds(n) for n in label_names)) & kinds(cand, brand=True, extra=cand_kinds))
    return 2.0 * shared + 1.0 * same_kind + (1.0 - d_m / radius), shared, same_kind


def metres(lon0: float, lat0: float, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    # ponytail: equirectangular, fine to <0.1% over a few hundred metres
    k = math.cos(math.radians(lat0))
    return np.hypot((lon - lon0) * 111_320 * k, (lat - lat0) * 110_574)


def label_names(lab: dict) -> list[str]:
    names = [lab.get("text_corrected") or lab.get("text") or ""]
    vn = re.search(r"(?:^|;\s*)vn=([^;]+)", lab.get("notes") or "")
    if vn:
        names.append(vn.group(1))
    return [re.sub(r"^\s*\d+\.\s*", "", n) for n in names if n]


def cat(lab: dict) -> str:
    """The label's category as the editors left it: corrected wins."""
    return lab.get("category_corrected") or lab.get("category") or ""


def label_px(lab: dict) -> tuple[float, float] | None:
    m = re.search(r"px=(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)", lab.get("notes") or "")
    if m:
        return float(m.group(1)), float(m.group(2))
    if cat(lab) in PLACED_ONLY:
        return None  # an unplaced legend entry's box is the legend, not the place
    if lab.get("global_x") is None:
        return None
    return lab["global_x"] + (lab.get("global_w") or 0) / 2, lab["global_y"] + (lab.get("global_h") or 0) / 2


def blob_hash(path: Path) -> str:
    """git's blob id of a file (what `git hash-object` prints), so a method version needs no git."""
    import hashlib

    b = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


# --------------------------------------------------------------------------- the candidate pool

def _tf():
    from pyproj import Transformer

    return Transformer.from_crs(4326, 32648, always_xy=True)  # UTM 48N: metres


def tag_kinds(tags: dict) -> set[str]:
    """Kinds an OSM feature's tags state, so a church needs no 'Nhà thờ' in its name."""
    a, rel = tags.get("amenity"), tags.get("religion")
    ks: set[str] = set()
    if a in ("school", "university", "college", "kindergarten"):
        ks.add("school")
    if a in ("hospital", "clinic", "doctors"):
        ks.add("hospital")
    if a == "marketplace":
        ks.add("market")
    if a in ("townhall", "courthouse", "police", "public_building") or tags.get("office") == "government" \
            or tags.get("building") in ("civic", "government", "public"):
        ks.add("government")
    if a == "post_office":
        ks.add("post")
    if a == "prison":
        ks.add("prison")
    if a == "place_of_worship":
        ks.add("church" if rel == "christian" else "temple")
    if a == "monastery" or tags.get("building") in ("monastery", "convent"):
        ks.add("convent")
    if tags.get("leisure") in ("park", "garden"):
        ks.add("park")
    if tags.get("military") or tags.get("landuse") == "military" or tags.get("building") == "barracks":
        ks.add("military")
    if tags.get("tourism") in ("hotel", "hostel", "motel", "guest_house", "apartment") or tags.get("shop") \
            or a in ("restaurant", "cafe", "bar", "fast_food", "bank", "pub", "nightclub"):
        ks.add("commercial")
    return ks


def _osm_geom(e: dict, rels: dict):
    import shapely
    from shapely.ops import polygonize, unary_union

    t = e["type"]
    if t == "node":
        return shapely.Point(e["lon"], e["lat"]), False
    if t == "way" and e.get("geometry"):
        pts = [(p["lon"], p["lat"]) for p in e["geometry"]]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            g = shapely.Polygon(pts)
            return (g if g.is_valid else g.buffer(0)), False
        return (shapely.LineString(pts) if len(pts) >= 2 else shapely.Point(pts[0])), False
    if t == "relation":
        full = rels.get(e["id"])
        if full:
            lines = [shapely.LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                     for m in full.get("members", []) if m.get("role") == "outer" and len(m.get("geometry") or []) >= 2]
            polys = list(polygonize(unary_union(lines))) if lines else []
            if polys:
                return unary_union(polys), False
        b = e.get("bounds")
        if b:  # ponytail: only 3 cached relations carry outlines; the rest are measured to their bounding box
            return shapely.box(b["minlon"], b["minlat"], b["maxlon"], b["maxlat"]), True
    return None, False


def load_osm(cache: Path, rel_cache: Path | None = None) -> list[dict]:
    """Named features of a cached Overpass reply, geometry in lng/lat."""
    import json

    els = json.loads(Path(cache).read_text())["elements"]
    rels = {}
    if rel_cache and Path(rel_cache).exists():
        rels = {e["id"]: e for e in json.loads(Path(rel_cache).read_text())["elements"]}
    out = []
    for e in els:
        tags = e.get("tags") or {}
        names = list(dict.fromkeys(tags[k] for k in OSM_NAMES if tags.get(k)))
        if not names or tags.get("highway") or tags.get("railway") not in (None, "station", "halt"):
            continue  # a street or a rail line is not a place
        g, approx = _osm_geom(e, rels)
        if g is None:
            continue
        out.append({"source": "osm", "osm": f"{e['type']}/{e['id']}", "osm_alts": [], "wikidata": tags.get("wikidata"),
                    "tasco_ids": [], "name": names[0], "names": names, "geom_ll": g, "approx": approx,
                    "kind_extra": tag_kinds(tags)})
    return out


def load_tasco(bbox) -> list[dict]:
    import pyarrow.parquet as pq
    import shapely

    from landmarks_1882 import VECTOR_PARQUET

    t = pq.read_table(VECTOR_PARQUET, columns=["name", "geometry"], filters=[("layer", "==", "label_congtrinhs")])
    g = shapely.from_wkb(t.column("geometry").to_pylist())
    xy = shapely.get_coordinates(shapely.centroid(g))
    out = []
    for i, n in enumerate(t.column("name").to_pylist()):
        if n and n.strip() and bbox[0] <= xy[i, 0] <= bbox[2] and bbox[1] <= xy[i, 1] <= bbox[3]:
            out.append({"source": "tasco", "osm": None, "osm_alts": [], "wikidata": None, "tasco_ids": [i],
                        "name": n.strip(), "names": [n.strip()], "geom_ll": shapely.Point(*xy[i]), "approx": False,
                        "kind_extra": set()})
    return out


def merge_records(osm: list[dict], tasco: list[dict], merge_m: float = MERGE_M) -> list[dict]:
    """One record per place. Records carry `geom_m` (metres). An OSM feature and a topo point, or two OSM
    features, within merge_m of each other (outline to outline) that share a distinctive name token are one
    candidate holding every id. The larger OSM outline leads."""
    import shapely
    from shapely.strtree import STRtree

    osm = sorted(osm, key=lambda r: (r["approx"], -r["geom_m"].area))
    parent = list(range(len(osm)))
    toks = [set().union(*(tokens(n) for n in r["names"])) for r in osm]

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    tree = STRtree([r["geom_m"] for r in osm]) if osm else None
    for i in range(len(osm)):
        near = sorted(j for j in tree.query(osm[i]["geom_m"], predicate="dwithin", distance=merge_m) if j < i)
        for j in near:
            if toks[i] & toks[root(j)]:
                parent[i] = root(j)
                toks[root(j)] |= toks[i]
                break
    groups: dict[int, dict] = {}
    for i, r in enumerate(osm):
        k = root(i)
        if k == i:
            groups[i] = {**r, "osm_alts": [], "names": list(r["names"]), "kind_extra": set(r["kind_extra"])}
        else:
            g = groups[k]
            g["osm_alts"].append(r["osm"])
            g["names"] += [n for n in r["names"] if n not in g["names"]]
            g["kind_extra"] |= r["kind_extra"]
            g["wikidata"] = g["wikidata"] or r["wikidata"]
    out = list(groups.values())
    gl = list(groups)
    gtree = STRtree([groups[k]["geom_m"] for k in gl]) if gl else None
    for r in tasco:
        best, bd = None, merge_m + 1
        rt = set().union(*(tokens(n) for n in r["names"]))
        for ix in (gtree.query(r["geom_m"], predicate="dwithin", distance=merge_m) if gtree else []):
            k = gl[ix]
            d = float(shapely.distance(groups[k]["geom_m"], r["geom_m"]))
            if d < bd and rt & toks[k]:
                best, bd = k, d
        if best is None:
            out.append(r)
        else:
            g = groups[best]
            g["source"] = "osm+tasco"
            g["tasco_ids"] += r["tasco_ids"]
            g["names"] += [n for n in r["names"] if n not in g["names"]]
    for r in out:
        r["id"] = ("osm:" + r["osm"]) if r["osm"] else "tasco:%d" % r["tasco_ids"][0]
        r["lon"], r["lat"] = (float(v) for v in shapely.get_coordinates(shapely.centroid(r["geom_ll"]))[0])
    return out


class Pool:
    """Merged candidates, queryable by distance to their outline."""

    def __init__(self, recs: list[dict]):
        from shapely.strtree import STRtree

        self.recs = recs
        self.tree = STRtree([r["geom_m"] for r in recs]) if recs else None
        self.tf = _tf()

    def near(self, lon: float, lat: float, radius: float) -> list[tuple[dict, float]]:
        import shapely

        if not self.recs:
            return []
        p = shapely.Point(*self.tf.transform(lon, lat))
        idx = self.tree.query(p, predicate="dwithin", distance=radius)
        d = shapely.distance(np.array([self.recs[i]["geom_m"] for i in idx], dtype=object), p)
        return sorted(((self.recs[i], float(x)) for i, x in zip(idx, d)), key=lambda t: t[1])


def build_pool(bbox, osm_files: tuple[Path, Path | None] | None = None) -> Pool:
    import shapely

    tf = _tf()

    def proj(rs):
        for r in rs:
            r["geom_m"] = shapely.transform(r["geom_ll"], lambda xy: np.column_stack(tf.transform(xy[:, 0], xy[:, 1])))
        return rs

    osm = proj(load_osm(*osm_files)) if osm_files and Path(osm_files[0]).exists() else []
    return Pool(merge_records(osm, proj(load_tasco(bbox))))


def rank(names: list[str], hits, radius: float, top: int) -> list[dict]:
    rows = []
    for r, d in hits:
        s, sh, sk = score(names, " / ".join(r["names"]), d, radius, r["kind_extra"])
        rows.append({"c": r, "d": d, "score": s, "shared": sh, "same_kind": sk})
    rows.sort(key=lambda x: (-x["score"], x["d"]))
    return rows[:top]


def public(c: dict) -> dict:
    """The JSON-able face of a pool record."""
    return {"id": c["id"], "name": c["name"], "names": c["names"], "source": c["source"], "osm": c["osm"],
            "osm_alts": c["osm_alts"], "wikidata": c["wikidata"], "tasco_ids": c["tasco_ids"],
            "lon": round(c["lon"], 7), "lat": round(c["lat"], 7), "approx": c["approx"]}


def rest(table: str, params: dict) -> list[dict]:
    import requests

    from supabase_client import _headers, _load_config

    url, key = _load_config()
    rows, start = [], 0
    while True:
        r = requests.get(f"{url}/rest/v1/{table}", params=params,
                         headers={**_headers(key), "Range": f"{start}-{start + 999}"}, timeout=30)
        r.raise_for_status()
        rows += r.json()
        if len(r.json()) < 1000:
            return rows
        start += 1000


def propose(labels, fit, pool: Pool, radius, top, cats: set[str] | None = None):
    """cats: only these categories (the place-links scope); default: everything but NON_PLACE."""
    out = []
    for lab in labels:
        px = label_px(lab)
        c = cat(lab)
        if px is None or lab.get("review_status") == "rejected" or (c not in cats if cats else c in NON_PLACE):
            continue
        lon, lat = fit.lonlat(np.array([px]))[0]
        ln = label_names(lab)
        out.append({"lab": lab, "px": px, "lon": float(lon), "lat": float(lat), "names": ln,
                    "cands": rank(ln, pool.near(lon, lat, radius), radius, top)})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map-id")
    p.add_argument("--radius", type=float, default=150.0, help="metres around the label (default 150)")
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--no-osm", action="store_true", help="topo candidates only")
    p.add_argument("--eval", action="store_true", help="score against the editors' legend_finds picks (DEV set, in-sample)")
    p.add_argument("--hit-m", type=float, default=60.0, help="--eval: a candidate this close to the pick is a hit")
    p.add_argument("--out", help="CSV path (default results/prior/<map-id>/name_today.csv)")
    p.add_argument("--self-check", action="store_true")
    a = p.parse_args()
    if a.self_check:
        return self_check()
    if not a.map_id:
        p.error("--map-id is required")

    import shapely

    import modern_prior as mp
    from iiif_tiles import get_iiif_base_from_supabase, get_image_info
    from scale import annotation_for_map

    fit = mp.fit_sheet(annotation_for_map(a.map_id) or {})
    if not fit:
        print("no usable georeference", file=sys.stderr)
        return 1
    info = get_image_info(get_iiif_base_from_supabase(a.map_id))
    bbox = fit.bbox_lonlat(int(info["width"]), int(info["height"]))
    prior = Path(__file__).resolve().parents[1] / "results" / "prior" / a.map_id
    osm = None if a.no_osm else (prior / "landmarks_overpass.json", prior / "landmarks_overpass_relations.json")
    pool = build_pool(bbox, osm)
    labels = rest("ocr_labels", {"map_id": f"eq.{a.map_id}",
                                 "select": "id,text,text_corrected,category,category_corrected,review_status,notes,global_x,global_y,global_w,global_h"})
    srcs = {s: sum(r["source"] == s for r in pool.recs) for s in ("osm", "osm+tasco", "tasco")}
    print(f"georef {fit}\ncandidates {len(pool.recs)} {srcs} · labels {len(labels)}")
    rows = propose(labels, fit, pool, a.radius, a.top)
    print(f"proposed for {len(rows)} labels, {sum(1 for r in rows if r['cands'])} with a candidate within {a.radius:.0f} m")

    out = Path(a.out) if a.out else prior / "name_today.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label_id", "category", "name_on_sheet", "lon", "lat", "rank", "today", "source", "osm_id", "wikidata",
                    "dist_m", "shared_tokens", "same_kind", "score"])
        for r in rows:
            for k, c in enumerate(r["cands"] or [None], 1):
                base = [r["lab"]["id"], cat(r["lab"]), " | ".join(r["names"]), f"{r['lon']:.6f}", f"{r['lat']:.6f}"]
                if c is None:
                    w.writerow(base + [""] * 9)
                else:
                    w.writerow(base + [k, c["c"]["name"], c["c"]["source"], c["c"]["osm"] or "", c["c"]["wikidata"] or "",
                                       f"{c['d']:.0f}", c["shared"], int(c["same_kind"]), f"{c['score']:.2f}"])
    print(f"→ {out}")

    if a.eval:
        tf = _tf()
        finds = rest("legend_finds", {"map_id": f"eq.{a.map_id}", "select": "label_id,query,osm_name,osm_lng,osm_lat,created_at",
                                      "order": "created_at"})
        pick = {f["label_id"]: f for f in finds}  # newest per label wins
        by_id = {r["lab"]["id"]: r for r in rows}
        h1 = h3 = n = 0
        for lid, f in pick.items():
            r = by_id.get(lid)
            n += 1
            pt = shapely.Point(*tf.transform(f["osm_lng"], f["osm_lat"]))
            ds = [] if not r else [float(shapely.distance(c["c"]["geom_m"], pt)) for c in r["cands"]]
            hit1, hit3 = bool(ds) and ds[0] <= a.hit_m, any(x <= a.hit_m for x in ds)
            h1 += hit1
            h3 += hit3
            top1 = r["cands"][0]["c"]["name"] if r and r["cands"] else "—"
            print(f"  {'✓' if hit1 else ('·' if hit3 else '✗')} {' | '.join(r['names']) if r else lid:55.55} "
                  f"→ {top1[:40]:40} (editor: {f['osm_name'].split(',')[0][:35]})")
        print(f"\nDEV, in-sample (the scorer was tuned on these 27; not accuracy)\n"
              f"hit@1 {h1}/{n}   hit@{a.top} {h3}/{n}   (hit = within {a.hit_m:.0f} m of the editor's pick)")
    return 0


def self_check() -> int:
    import shapely

    assert fold("Bệnh Viện Đồn Đất") == " BENH VIEN DON DAT "
    assert kinds("Hôpital Maritime") == {"hospital"} and "hospital" in kinds("Bệnh viện Nhi đồng 2")
    assert kinds("Chợ Bến Thành") == {"market"} and "hospital" not in kinds("Bệnh viện Nhi Đồng") - {"hospital"}
    assert tokens("Bệnh Viện Chợ Rẫy") == {"RAY"}  # CHO is a kind word, RAY is the name
    s_same, sh, sk = score(["Chợ Rẫy Hospital"], "Bệnh viện Chợ Rẫy", 40, 150)
    s_other, *_ = score(["Chợ Rẫy Hospital"], "Trạm biến áp", 10, 150)
    assert sh == 1 and sk and s_same > s_other, "a shared name beats a nearer stranger"
    assert label_px({"notes": "n=6; vn=X; px=7924,5905", "category": "legend_entry"}) == (7924.0, 5905.0)
    assert label_px({"notes": "n=6", "category": "legend_entry", "global_x": 1, "global_y": 1}) is None
    assert label_px({"notes": "", "category": "legend", "global_x": 1, "global_y": 1}) is None, "sheet furniture has no place"
    assert label_px({"notes": "", "category": "other", "category_corrected": "legend", "global_x": 1, "global_y": 1}) is None
    assert label_px({"category": "institution", "global_x": 10, "global_y": 20, "global_w": 4, "global_h": 6}) == (12, 23)
    assert label_names({"text": "6. Grall's Hospital", "notes": "vn=Bệnh Viện Grall (Đồn Đất); px=1,2"}) == \
        ["Grall's Hospital", "Bệnh Viện Grall (Đồn Đất)"]
    assert abs(metres(106.7, 10.78, np.array([106.7]), np.array([10.781]))[0] - 110.6) < 1
    assert tokens("Vge de Tân Hòa") == {"TAN", "HOA"}, "Vge is a type word, not a name"
    # the kind leak: a kind word inside a brand is not that kind of place
    assert "park" in kinds("Công viên Chi Lăng") and kinds("Khách sạn Park Hyatt SaiGon", brand=True) == {"commercial"}
    assert kinds("Nhà hàng Café Jardin", brand=True) == {"commercial"} and kinds("Hotel Majestic", brand=True) == {"commercial"}
    assert "government" in kinds("Hôtel de Ville", brand=True) and "commercial" not in kinds("Hôtel de Ville", brand=True)
    assert kinds("Trường Kỹ thuật Cao Thắng", brand=True) == {"school"}
    park_label = ["PARC DU GÉNIE"]
    _, _, leak = score(park_label, "Khách sạn Park Hyatt SaiGon", 20, 150)
    _, _, ok = score(park_label, "Công viên Tao Đàn", 20, 150)
    assert not leak and ok, "PARC DU GÉNIE must not be the same kind as a Park Hyatt"
    assert tag_kinds({"amenity": "place_of_worship", "religion": "christian"}) == {"church"}
    assert "commercial" in tag_kinds({"tourism": "hotel"})
    # merging: same place from two sources within 40 m sharing a name token is one candidate with both ids
    sq = lambda x, y, n: shapely.box(x, y, x + n, y + n)
    osm = [{"source": "osm", "osm": "way/1", "osm_alts": [], "wikidata": "Q1", "tasco_ids": [], "name": "Bệnh viện Chợ Rẫy",
            "names": ["Bệnh viện Chợ Rẫy"], "geom_ll": shapely.Point(106.0, 10.0), "geom_m": sq(0, 0, 30), "approx": False,
            "kind_extra": {"hospital"}},
           {"source": "osm", "osm": "way/2", "osm_alts": [], "wikidata": None, "tasco_ids": [], "name": "Chợ Rẫy Hospital",
            "names": ["Chợ Rẫy Hospital"], "geom_ll": shapely.Point(106.0, 10.0), "geom_m": sq(35, 0, 5), "approx": False,
            "kind_extra": set()}]
    tas = [{"source": "tasco", "osm": None, "osm_alts": [], "wikidata": None, "tasco_ids": [7], "name": "Bệnh viện Chợ Rẫy",
            "names": ["Bệnh viện Chợ Rẫy"], "geom_ll": shapely.Point(106.0, 10.0), "geom_m": shapely.Point(60, 15), "approx": False,
            "kind_extra": set()},
           {"source": "tasco", "osm": None, "osm_alts": [], "wikidata": None, "tasco_ids": [8], "name": "Trạm biến áp",
            "names": ["Trạm biến áp"], "geom_ll": shapely.Point(106.0, 10.0), "geom_m": shapely.Point(10, 10), "approx": False,
            "kind_extra": set()},
           {"source": "tasco", "osm": None, "osm_alts": [], "wikidata": None, "tasco_ids": [9], "name": "Bệnh viện Chợ Rẫy",
            "names": ["Bệnh viện Chợ Rẫy"], "geom_ll": shapely.Point(106.0, 10.0), "geom_m": shapely.Point(500, 500), "approx": False,
            "kind_extra": set()}]
    m = merge_records(osm, tas)
    by = {r["id"]: r for r in m}
    big = by["osm:way/1"]
    assert len(m) == 3 and big["source"] == "osm+tasco" and big["osm_alts"] == ["way/2"] and big["tasco_ids"] == [7], m
    assert "tasco:8" in by and "tasco:9" in by, "a stranger, and the same name 700 m away, stay separate"
    import tempfile

    with tempfile.NamedTemporaryFile() as t:
        assert blob_hash(Path(t.name)) == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"  # git's empty blob
    print("name_today self-check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
