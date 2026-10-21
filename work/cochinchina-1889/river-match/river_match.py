#!/usr/bin/env python3
"""Place a Cochinchina plate (1881-89) by matching its rivers to OpenStreetMap, with no graticule.

    work/ocr/.venv/bin/python work/cochinchina-1889/river-match/river_match.py \
        --config <plate config.json> --med <quarter-res plate JPEG> --osm <osm_water.json> [--out DIR]

The config holds what is read off the plate before any fit: map id, full size, the printed 20 km bar
in quarter-res pixels, the arrondissement's centre (a gazetteer prior), the OSM box, and the path of
the held-out checks. Every plate runs the same search; nothing is tuned per plate.

Reads only. One cached Overpass response (water=river polygons, ways and relations).

Model: a similarity (scale, rotation, shift) from plate pixels to a local metric frame.
  * scale is read off the printed bar (20 km = 2329 px at full resolution, 8.59 m/px) and
    searched +-10 %; rotation +-10 deg; the plate centre within 30 km of Mỹ Tho town;
  * the plate's water is blue water-lining (big rivers, river mouths), kept inside the
    arrondissement outline dilated by ~2 km so the boundary rivers count;
  * score = correlation of the zero-mean plate water with rasterised OSM river polygons,
    over every shift at once (FFT); land under OSM water costs, water on water pays;
  * coarse grid (150 m cells), then a finer one (75 m) around the best.
Checks are four town centres placed by eye BEFORE any fit (points/check.csv); they are
not used by the fit at all.
"""
import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy.signal import fftconvolve
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

HERE = Path(__file__).resolve().parent
# Set by configure(): the plate's map id, size, scale and the metric frame (origin = the prior centre).
MAP_ID = IIIF = FULL = M_PER_PX = LON0 = LAT0 = KX = KY = BBOX = NORTH = None
REF = None                           # "image" or "mask": which plate point the 30 km prior binds


def configure(cfg):
    global MAP_ID, IIIF, FULL, M_PER_PX, LON0, LAT0, KX, KY, BBOX, NORTH, REF
    MAP_ID = cfg["map_id"]
    IIIF = f"https://iiif.maparchive.vn/iiif/{MAP_ID}"
    FULL = tuple(cfg["full"])                       # info.json
    M_PER_PX = 20000 / (cfg["bar_med_px"] * 4)      # printed scale bar: 20 km, full-res pixels
    LAT0, LON0 = cfg["prior"]                       # the metric frame's origin
    KX, KY = 111320 * np.cos(np.radians(LAT0)), 110574.0
    BBOX = tuple(cfg["bbox"])                       # S W N E of the OSM query
    REF = cfg.get("prior_on", "image")
    NORTH = cfg.get("north_deg", 0.0)               # sheet turned clockwise this far, read off the north arrow / side labels


def to_m(lon, lat):
    return (np.asarray(lon) - LON0) * KX, (np.asarray(lat) - LAT0) * KY


def to_ll(x, y):
    return LON0 + np.asarray(x) / KX, LAT0 + np.asarray(y) / KY


# ---------------------------------------------------------------- OSM water raster
def osm_lines(path):
    """waterway=river centrelines (lon, lat arrays)."""
    if str(path).endswith(".geojsonseq"):
        out = []
        for ln in open(path):
            f = json.loads(ln)
            if f["geometry"]["type"] == "LineString" and f["properties"].get("waterway") == "river":
                out.append(np.array(f["geometry"]["coordinates"]))
        return out
    return [np.array([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in json.load(open(path))["elements"]
            if e["type"] == "way" and e.get("tags", {}).get("waterway") == "river"]


def osm_polygons(path):
    if str(path).endswith(".geojsonseq"):       # `osmium export` of a Geofabrik extract: areas already assembled
        from shapely.geometry import shape
        polys = []
        for ln in open(path):
            f = json.loads(ln)
            t = f["properties"]
            if t.get("natural") == "water" and f["geometry"]["type"] in ("Polygon", "MultiPolygon"):
                polys.append(shape(f["geometry"]).buffer(0))
        return unary_union(polys)
    els = json.load(open(path))["elements"]
    polys = []
    for e in els:
        tags = e.get("tags", {})
        if tags.get("natural") != "water":
            continue
        if e["type"] == "way":
            g = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if len(g) >= 4 and g[0] == g[-1]:
                polys.append(Polygon(g).buffer(0))
        else:   # relation: assemble rings from member ways
            lines = {"outer": [], "inner": []}
            for m in e.get("members", []):
                if m.get("type") == "way" and "geometry" in m and m.get("role") in lines:
                    lines[m["role"]].append(LineString([(p["lon"], p["lat"]) for p in m["geometry"]]))
            outer = unary_union(list(polygonize(unary_union(lines["outer"])))) if lines["outer"] else None
            if outer is None or outer.is_empty:
                continue
            if lines["inner"]:
                outer = outer.difference(unary_union(list(polygonize(unary_union(lines["inner"])))))
            polys.append(outer)
    return unary_union(polys)


def rasterise(geom, G, lines=()):
    x0, y0 = to_m(BBOX[1], BBOX[0])
    x1, y1 = to_m(BBOX[3], BBOX[2])
    W, H = int((x1 - x0) / G), int((y1 - y0) / G)
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    def px(coords):
        lon, lat = np.asarray(coords).T
        x, y = to_m(lon, lat)
        return list(zip((x - x0) / G, (y1 - y) / G))
    for p in getattr(geom, "geoms", [geom]):
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        for ring in [p.exterior, *p.interiors]:      # banks, not areas: the plate shows bank lines
            d.line(px(ring.coords), fill=1, width=1)
    for ln in lines:
        d.line(px(ln), fill=1, width=1)
    r = ndi.gaussian_filter(np.asarray(im, np.float32), 1.0)
    return r / r.max(), (x0, y1)      # origin = metric (x, y) of pixel (0, 0)


# ---------------------------------------------------------------- plate water
def outline(path):
    svg = json.load(open(path))["items"][0]["target"]["selector"]["value"]
    pts = re.search(r'points="([^"]+)"', svg).group(1).split()
    return [tuple(map(float, p.split(","))) for p in pts]


def plate_water(med_path, mask_full, f):
    """Zero-mean water signal at 1/f of full resolution, inside the dilated outline."""
    a = np.asarray(Image.open(med_path).convert("RGB")).astype(np.int16)
    k = f // 4
    blue = (a[..., 2] - a[..., 0]) > -15          # bank lines and small rivers are blue-grey ink
    h, w = blue.shape[0] // k, blue.shape[1] // k
    water = blue[:h * k, :w * k].reshape(h, k, w, k).any(axis=(1, 3))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([(x / f, y / f) for x, y in mask_full], fill=1)
    m = ndi.binary_dilation(np.asarray(m, bool), iterations=max(1, int(2000 / (M_PER_PX * f))))
    sig = ndi.gaussian_filter(water.astype(np.float32), 1.0)
    p = np.where(m, sig - sig[m].mean(), 0).astype(np.float32)
    return p, water, m


# ---------------------------------------------------------------- search
def warp(P, ps, theta, G):
    """Plate (rows v, cols u; ps metres per plate px) rotated by theta into a north-up grid of G m.
    Returns the grid and the grid position of plate pixel (0, 0)."""
    h, w = P.shape
    c, s = np.cos(theta), np.sin(theta)
    # plate (u, v) -> metric (x, y) = ps * R(theta) @ (u, -v)
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], float)
    xy = ps * np.c_[c * corners[:, 0] + s * corners[:, 1], s * corners[:, 0] - c * corners[:, 1]]
    xmin, ymax = xy[:, 0].min(), xy[:, 1].max()
    W, H = int(np.ceil((xy[:, 0].max() - xmin) / G)) + 1, int(np.ceil((ymax - xy[:, 1].min()) / G)) + 1
    jj, ii = np.meshgrid(np.arange(W), np.arange(H))
    x, y = xmin + jj * G, ymax - ii * G
    u = (c * x + s * y) / ps
    v = (s * x - c * y) / ps
    out = ndi.map_coordinates(P, [v, u], order=1, cval=0.0)
    return out.astype(np.float32), (-xmin / G, ymax / G)   # (col, row) of plate px (0,0)


def search(P, Wr, worg, G, f, thetas, scales, ref, centre_km=30):
    ps0 = M_PER_PX * f
    h, w = P.shape
    res = []
    for th in thetas:
        for sc in scales:
            ps = ps0 * sc
            Q, (qc, qr) = warp(P, ps, np.radians(th), G)
            C = fftconvolve(Wr, Q[::-1, ::-1], mode="full")
            Qh, Qw = Q.shape
            # C[a, b]: Q's (0,0) at Wr row a-(Qh-1), col b-(Qw-1); plate px (0,0) there + (qr, qc)
            a, b = np.mgrid[0:C.shape[0], 0:C.shape[1]]
            ox = worg[0] + (b - (Qw - 1) + qc) * G          # metric x of plate px (0,0)
            oy = worg[1] - (a - (Qh - 1) + qr) * G
            t = np.radians(th)
            cu, cv = ref
            cx = ox + ps * (np.cos(t) * cu + np.sin(t) * cv)
            cy = oy + ps * (np.sin(t) * cu - np.cos(t) * cv)
            ok = np.hypot(cx, cy) < centre_km * 1000
            C = np.where(ok, C, -np.inf)
            i = np.unravel_index(np.argmax(C), C.shape)
            # local maxima (one per ~5 km) kept for the second-peak test; the surfaces are not
            pk = (C == ndi.maximum_filter(C, size=int(5000 / G))) & np.isfinite(C) & (C > 0)
            top = np.argsort(C[pk])[-20:]
            peaks = np.c_[C[pk][top], cx[pk][top], cy[pk][top]]
            res.append(dict(theta=th, scale=sc, ps=ps, score=float(C[i]), ox=float(ox[i]), oy=float(oy[i]),
                            cx=float(cx[i]), cy=float(cy[i]), peaks=peaks))
    return res


def refpt(P, m):
    """The plate point the 30 km prior binds, in P pixels: the image centre, or the mask centroid."""
    if REF == "mask":
        ys, xs = np.nonzero(m)
        return float(xs.mean()), float(ys.mean())
    return P.shape[1] / 2, P.shape[0] / 2


def model(r, f):
    """plate full-res px (X, Y) -> metric (x, y)."""
    t, ps = np.radians(r["theta"]), r["ps"] / f
    def fwd(X, Y):
        X, Y = np.asarray(X, float), np.asarray(Y, float)
        return r["ox"] + ps * (np.cos(t) * X + np.sin(t) * Y), r["oy"] + ps * (np.sin(t) * X - np.cos(t) * Y)
    return fwd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--med", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", help="output folder; default the config's folder")
    args = ap.parse_args()
    cfgp = Path(args.config).resolve()
    cfg = json.load(open(cfgp))
    configure(cfg)
    OUT = Path(args.out) if args.out else cfgp.parent
    (OUT / "points").mkdir(parents=True, exist_ok=True)
    mask_full = outline(HERE.parent / "allmaps-drafts" / f"{MAP_ID}.json")
    geom = osm_polygons(args.osm)
    rivers = osm_lines(args.osm)

    # coarse: 150 m cells, plate at 1/16
    G, f = 150.0, 16
    Wr, worg = rasterise(geom, G, rivers)
    P, _, m = plate_water(args.med, mask_full, f)
    coarse = search(P, Wr, worg, G, f, NORTH + np.arange(-10, 10.01, 1.0), np.arange(0.90, 1.101, 0.02), refpt(P, m))
    best = max(coarse, key=lambda r: r["score"])
    # second peak: best placement whose plate centre is > 5 km from the best's, any theta/scale
    second = -np.inf
    for r in coarse:
        p = r["peaks"]
        far = np.hypot(p[:, 1] - best["cx"], p[:, 2] - best["cy"]) > 5000
        if far.any():
            second = max(second, float(p[far, 0].max()))
    print(f"coarse best theta {best['theta']:.1f} scale {best['scale']:.3f} score {best['score']:.1f}; "
          f"second peak (>5 km away) {second:.1f}; ratio {second / best['score']:.3f}")

    # fine: 75 m cells, plate at 1/8, around the best
    G2, f2 = 75.0, 8
    Wr2, worg2 = rasterise(geom, G2, rivers)
    P2, water2, m2 = plate_water(args.med, mask_full, f2)
    fine = search(P2, Wr2, worg2, G2, f2, np.arange(best["theta"] - 1.5, best["theta"] + 1.51, 0.25),
                  np.arange(best["scale"] - 0.03, best["scale"] + 0.0301, 0.005), refpt(P2, m2))
    fb = max(fine, key=lambda r: r["score"])
    print(f"fine best theta {fb['theta']:.2f} scale {fb['scale']:.3f} ({fb['ps'] / f2:.3f} m/px full) score {fb['score']:.1f}")
    fwd = model(fb, f2)

    # held-out checks
    rows = list(csv.DictReader(open((cfgp.parent / cfg["checks"]).resolve())))
    errs = []
    for r in rows:
        x, y = fwd(float(r["px"]), float(r["py"]))
        tx, ty = to_m(float(r["lon"]), float(r["lat"]))
        e = float(np.hypot(x - tx, y - ty))
        errs.append(e)
        lon, lat = to_ll(x, y)
        print(f"check {r['id']}: predicted {lon:.5f} {lat:.5f}  error {e:.0f} m  (E {x - tx:+.0f}, N {y - ty:+.0f})")
    print(f"held-out median {np.median(errs):.0f} m, max {max(errs):.0f} m, n {len(errs)}")

    # GCPs: 12 plate water pixels nearest the centres of a 4 x 3 grid, inside the outline
    ys, xs = np.nonzero(water2 & m2)
    gcps = []
    H2, W2 = water2.shape
    for gy in range(3):
        for gx in range(4):
            cxp, cyp = (gx + 0.5) * W2 / 4, (gy + 0.5) * H2 / 3
            d = np.hypot(xs - cxp, ys - cyp)
            if d.min() > 0.2 * W2:
                continue
            i = int(np.argmin(d))
            X, Y = xs[i] * f2 + f2 / 2, ys[i] * f2 + f2 / 2
            lon, lat = to_ll(*fwd(X, Y))
            gcps.append(((round(X), round(Y)), (round(float(lon), 6), round(float(lat), 6))))
    with open(OUT / "points" / "fit.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["role", "id", "px", "py", "lon", "lat", "note"])
        for k, ((X, Y), (lon, lat)) in enumerate(gcps):
            w.writerow(["fit", f"gcp{k:02d}", X, Y, lon, lat,
                        "plate water pixel; ground from the fitted similarity (not an independent point)"])

    import sys
    sys.path.insert(0, str(HERE.parents[2] / "scripts" / "lib"))
    from georef_annotation import annotation
    ann = annotation(IIIF, FULL[0], FULL[1], gcps, mask_full)
    (OUT / f"{MAP_ID}.json").write_text(json.dumps(ann, indent=1))

    summary = dict(water_frac_in_mask=round(float(water2[m2].mean()), 4), coarse=dict(theta=best["theta"], scale=round(best["scale"], 3), score=round(best["score"], 1),
                               second_peak=round(second, 1), ratio=round(second / best["score"], 3)),
                   fine=dict(theta=round(fb["theta"], 2), scale=round(fb["scale"], 4),
                             m_per_px_full=round(fb["ps"] / f2, 4), score=round(fb["score"], 1)),
                   checks={r["id"]: round(e) for r, e in zip(rows, errs)},
                   check_median_m=round(float(np.median(errs))), check_max_m=round(max(errs)))
    (OUT / "points" / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))

    # overlay for a look: OSM river outlines drawn on the plate
    im = Image.open(args.med).convert("RGB")
    d = ImageDraw.Draw(im)
    t, ps = np.radians(fb["theta"]), fb["ps"] / f2
    def inv(x, y):     # metric -> full px -> med px
        dx, dy = (x - fb["ox"]) / ps, (y - fb["oy"]) / ps
        return (np.cos(t) * dx + np.sin(t) * dy) / 4, (np.sin(t) * dx - np.cos(t) * dy) / 4
    for p in getattr(geom, "geoms", [geom]):
        if p.geom_type != "Polygon":
            continue
        for ring in [p.exterior, *p.interiors]:
            lon, lat = np.asarray(ring.coords).T
            u, v = inv(*to_m(lon, lat))
            if ((u > 0) & (u < im.size[0]) & (v > 0) & (v < im.size[1])).any():
                d.line(list(zip(u, v)), fill=(220, 0, 0), width=2)
    for r in rows:
        u, v = inv(*to_m(float(r["lon"]), float(r["lat"])))
        d.ellipse((u - 8, v - 8, u + 8, v + 8), outline=(0, 160, 0), width=3)
        X, Y = float(r["px"]) / 4, float(r["py"]) / 4
        d.line((X - 10, Y, X + 10, Y), fill=(0, 0, 0), width=3)
        d.line((X, Y - 10, X, Y + 10), fill=(0, 0, 0), width=3)
    im.save(OUT / "overlay.jpg", quality=85)


if __name__ == "__main__":
    main()
