#!/usr/bin/env python3
"""Attach outside history to legend chains: OSM features with a wikidata tag at the chain's
site, then Wikidata (dates, description) and Wikipedia (extract). Writes places.json, keyed by
chain id, for viewer.js's popup. Tentative by construction: a site match, not an identity.
"""
import json, math, pathlib, re, unicodedata
import requests

HERE = pathlib.Path(__file__).parent
UA = {"User-Agent": "vma-fabric-proto/0.1 (+https://maparchive.vn)"}
BBOX = "10.69,106.60,10.83,106.74"
NEAR_M, NEAR_SAME_KIND_M = 40.0, 25.0  # a different or unknown kind must be this close

# Coarse kinds, French + Vietnamese + OSM tags, so a church is not matched to the bank next door.
KINDS = {
    "church": r"eglise|cathedrale|basilique|chapelle|nha tho|church|cathedral",
    "market": r"marche|cho |market",
    "school": r"ecole|lycee|college|universite|truong|school|university",
    "hospital": r"hopital|clinique|maternite|polyclinique|benh|bao sanh|hospital|clinic",
    "cemetery": r"cimetiere|nghia|cemetery",
    "police": r"commissariat|police|canh sat",
    "bank": r"banque|ngan hang|bank",
    "palace": r"palais|phu |dinh |palace",
    "museum": r"musee|vien bac|bao tang|museum",
    "post": r"poste|buu dien|post_office",
    "pagoda": r"pagode|chua |temple|dinh|pagoda",
    "station": r"gare|ga |station",
}
def fold(s):
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", s)


def kind(text):
    t = " " + fold(text) + " "
    return next((k for k, rx in KINDS.items() if re.search(rx, t)), None)


def osm_features():
    cache = HERE / ".osm-cache.json"
    if not cache.exists():
        q = f'[out:json][timeout:90];nwr["wikidata"]["name"]({BBOX});out center tags;'
        r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, headers=UA, timeout=120)
        r.raise_for_status()
        cache.write_text(r.text)
    out = []
    for e in json.loads(cache.read_text())["elements"]:
        c = e.get("center") or e
        if "lat" in c and not {"railway", "public_transport"} & e["tags"].keys(): out.append(dict(id=f'{e["type"]}/{e["id"]}', lat=c["lat"], lng=c["lon"], tags=e["tags"]))
    return out


def metres(lat, lng, f):
    return math.hypot((lng - f["lng"]) * 111320 * math.cos(math.radians(lat)), (lat - f["lat"]) * 110540)


def wikidata(qids):
    out = {}
    for i in range(0, len(qids), 40):
        r = requests.get("https://www.wikidata.org/w/api.php", headers=UA, timeout=60, params=dict(
            action="wbgetentities", format="json", ids="|".join(qids[i:i + 40]), props="labels|descriptions|claims|sitelinks", languages="en|fr|vi"))
        out.update(r.json().get("entities", {}))
    return out


def year(entity, prop):
    for c in entity.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if v and v.get("time"): return int(v["time"][1:5])


def wikipedia(entity):
    for lang in ("en", "vi", "fr"):
        link = entity.get("sitelinks", {}).get(f"{lang}wiki")
        if not link: continue
        r = requests.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{link['title'].replace(' ', '_')}", headers=UA, timeout=30)
        if r.ok and r.json().get("extract"):
            j = r.json(); return dict(lang=lang, title=j["title"], url=j["content_urls"]["desktop"]["page"], extract=j["extract"])


def main():
    d = json.load(open(HERE / "layers.json")); K = d["meters_per_degree"]
    chains = {}
    for r in d["legend"]:
        if "c" in r: chains.setdefault(r["c"], []).append(r)
    chains = {c: m for c, m in chains.items() if len({r["year"] for r in m}) >= 2}
    feats = osm_features(); print(len(feats), "OSM features with wikidata;", len(chains), "multi-year legend chains")
    hits = {}
    for c, members in chains.items():
        best = None
        for r in members:
            lat, lng = r["y"] / K[1], r["x"] / K[0]
            for f in feats:
                m = metres(lat, lng, f)
                if m > NEAR_M or (best and m >= best[0]): continue
                a, b = kind(r["name"]) or kind(r.get("vn") or ""), kind(f["tags"]["name"] + " " + f["tags"].get("amenity", "") + " " + f["tags"].get("building", ""))
                if (a and b and a != b) or (not (a and b and a == b) and m > NEAR_SAME_KIND_M): continue
                best = (m, r, f)
        if best: hits[c] = best
    ent = wikidata(sorted({f["tags"]["wikidata"] for _, _, f in hits.values()}))
    places = {}
    for c, (m, r, f) in hits.items():
        e = ent.get(f["tags"]["wikidata"], {})
        label = lambda k, src: (e.get(k, {}).get("en") or e.get(k, {}).get("fr") or e.get(k, {}).get("vi") or {}).get("value")
        places[c] = dict(m=round(m), osm=dict(id=f["id"], name=f["tags"]["name"], url=f"https://www.openstreetmap.org/{f['id']}"), wikidata=f["tags"]["wikidata"],
                         label=label("labels", e), description=label("descriptions", e), inception=year(e, "P571"), dissolved=year(e, "P576"), wikipedia=wikipedia(e))
    (HERE / "places.json").write_text(json.dumps(places, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(places)} chains matched to a wikidata place;", sum(bool(p["wikipedia"]) for p in places.values()), "with a Wikipedia extract")
    for c, (m, r, f) in list(hits.items())[:40]: print(f"  {m:4.0f}m  {r['year']}#{r['n']} {r['name'][:34]:34} -> {f['tags']['name'][:36]} ({f['tags']['wikidata']})")


if __name__ == "__main__": main()
