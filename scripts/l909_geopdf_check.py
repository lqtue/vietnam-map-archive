#!/usr/bin/env python3
"""Check that stored L909 georefs are the USGS GeoPDF's own georeference.

    python3 scripts/l909_geopdf_check.py <pdf-cache-dir> [slug ...]    # read-only; exit 1 if any > 1 m

Fourteen L909 sheets were placed from their GeoPDF's geotransform by code that no longer
exists (an old session scratchpad). This reproduces the claim: for each stored GCP, take its
pixel, scale it from the served image to the GeoPDF raster (some /v2 images are 2x), push it
through the GeoPDF's geotransform and the same Indian 1960 Helmert as `l909_georef.py`, and
report the worst distance to the stored lon/lat. 0.05-0.08 m on all 14 on 2026-10-07 -- the
GCPs ARE the GeoPDF's, so `method=geopdf` and `derived_from=<pdf url>` are true.
PDF URLs come from work/usgs/vietnam-products.json; PDFs are cached in the directory given.
"""
import json, os, re, subprocess, sys, urllib.request

from pyproj import Transformer

CODES = {
    "bien-hoa": "L909XBIENHOA", "can-tho": "L909XCANTHO", "chu-lai-and-vicinity": "L909XCHULAIVI",
    "da-lat-dalat": "L909XDALAT", "da-nang-tourane": "L909XDANANG", "dong-hoi": "L909XDONGHOI",
    "lac-giao-ban-me-thuot": "L909XLACGIAO", "my-tho": "L909XMYTHO", "nha-trang": "L909XNHATRANG",
    "phu-lang-thuong-1968": "L909XPHULANGT", "qui-nhon-2": "L909XQUINHON", "tuy-hoa-1968": "L909XTUYHOA",
    "vinh-long": "L909XVINHLONG", "vinh-and-ben-thuy": "L909XVINHBENT",
}
# Same string as scripts/l7014_mosaic.py INDIAN_1960_PROJ4 -- do not re-derive.
HELMERT = "+x=198 +y=881 +z=317"
ELL = "+a=6377276.345 +rf=300.8017"


def check(cache, slug, scans, prods):
    code = CODES[slug]
    pdf = f"{cache}/{code}.pdf"
    if not os.path.exists(pdf):
        subprocess.run(["curl", "-sL", "-o", pdf, prods[code]["pdf"]], check=True)
    info = json.loads(subprocess.run(["gdalinfo", "-json", pdf], capture_output=True, text=True).stdout)
    gt, size = info["geoTransform"], info["size"]
    zone = int(re.search(r"UTM zone (\d+)N", info["coordinateSystem"]["wkt"]).group(1))
    t = Transformer.from_pipeline(
        f"+proj=pipeline +step +inv +proj=utm +zone={zone} {ELL} +step +proj=push +v_3 "
        f"+step +proj=cart {ELL} +step +proj=helmert {HELMERT} +step +inv +proj=cart +ellps=WGS84 "
        "+step +proj=pop +v_3 +step +proj=unitconvert +xy_in=rad +xy_out=deg"
    )
    req = urllib.request.Request(  # the site 403s Python's default user agent
        f"https://maparchive.vn/api/maps/{scans[slug]['id']}/annotation", headers={"User-Agent": "curl/8"}
    )
    ann = json.load(urllib.request.urlopen(req))["items"][0]
    w, h = map(int, re.search(r'width="(\d+)" height="(\d+)"', ann["target"]["selector"]["value"]).groups())
    worst = 0.0
    for f in ann["body"]["features"]:
        px, py = f["properties"]["resourceCoords"]
        px, py = px * size[0] / w, py * size[1] / h
        lon, lat = t.transform(gt[0] + gt[1] * px + gt[2] * py, gt[3] + gt[4] * px + gt[5] * py)
        worst = max(worst, (((lon - f["geometry"]["coordinates"][0]) * 111320 * 0.985) ** 2
                            + ((lat - f["geometry"]["coordinates"][1]) * 110574) ** 2) ** 0.5)
    return zone, len(ann["body"]["features"]), size[0] / w, worst


if __name__ == "__main__":
    cache, slugs = sys.argv[1], sys.argv[2:] or list(CODES)
    scans = {s["slug"]: s for s in json.load(open("work/l909/ingested-scans.json"))["scans"] if s["side"] == "recto"}
    prods = {p["code"]: p for p in json.load(open("work/usgs/vietnam-products.json"))["products"]}
    bad = 0
    for slug in slugs:
        zone, n, k, worst = check(cache, slug, scans, prods)
        bad += worst > 1
        print(f"{slug:24s} zone {zone} gcps {n} scale {k:.2f} worst {worst:.2f} m {'FAIL' if worst > 1 else 'ok'}", flush=True)
    sys.exit(1 if bad else 0)
