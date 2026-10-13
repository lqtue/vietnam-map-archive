#!/usr/bin/env python3
"""Georeference the L909 city maps from USGS/NGA's GeoPDFs; the geometry half of
`ingest_l909_usgs.mjs`, which calls it. Reads PDFs, writes local files, never the
database.

    python3 scripts/oneoff/l909_usgs_georef.py analyse  <pdf-dir> <out.json>
    python3 scripts/oneoff/l909_usgs_georef.py render   <pdf> <out.jpg>
    python3 scripts/oneoff/l909_usgs_georef.py datum    <pdf> <annotation.json> <image.jpg> <out.json>

Each GeoPDF carries eight NGA control points in its own UTM grid and its printed
neatline -- the same structure as the L7014 sheets, so the reading follows
`l7014_annotate_pdf.read_pdf`, with the same trap: GDAL reads the datum as
`Indian_1960` (an EPSG:4131 lookup that is a no-op over most of the country) or
as `unknown` on the WGS84 ellipsoid (`IND-I`). Neither is used. The CRS is built
here, UTM zone from the sheet centre, on `INDIAN_1960_PROJ4` -- Everest 1830
(1937 Adj.) with the Helmert spelled out.

`analyse` gates each sheet on things the PDF cannot agree with itself about:
control points against an affine (scan registration), square ground pixels at
the scale the sheet prints, the neatline against the graticule the XMP states
(catches a wrong zone, NOT a wrong datum), and the city's own centre inside the
warped sheet (a km-scale sanity check, NOT a datum check). The datum is proved
separately by `datum`, against an outside opinion: a sheet of the same city a
person georeferenced by hand against a modern basemap.

`datum` needs OpenCV (`pip install opencv-python-headless` into a venv made with
`--system-site-packages`, so GDAL stays importable): the hand-placed sheet is a
different edition, so the two images are registered by SIFT + RANSAC rather
than by anything the sheets print alike.
"""

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import l7014_mosaic as M  # noqa: E402
from l7014_annotate_pdf import annotation  # noqa: E402

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")  # "Unhandled (yet) value for Datum : IND-I" x8 per open

DPI = 300  # every embedded image in all 18 PDFs is 300 ppi; GDAL's default DPI halves two of them
ORDER = 2  # same transformation the L7014 PDF sheets use
# Gates. A pixel at 1:12,500 and 300 dpi is 1.06 m on the ground.
# Control points vs an affine. 14 of 18 sheets max out at 1.5-8.4 m; Hai Phong (26 m) and
# Quang Ngai (37 m) have a control point sitting exactly on its printed graticule cross
# where the affine puts that cross 20-35 px away -- the paper is not affine there, and an
# affine annotation would carry that error. Held, not patched.
GCP_TOL_M = 10.0
SQUARE_TOL = 0.01  # ground pixel aspect, x vs y
SCALE_TOL = 0.03  # ground pixel vs the printed scale at 300 dpi
# Neatline vs the XMP's stated corners, in the sheet's own datum: a zone/axis check, blind
# to datum. NGA neatlines step out around map content that runs into the collar (Da Nang
# reads 4" wide of its XMP), so this is seconds, not metres.
GRATICULE_TOL_M = 150.0
ASPECT_TOL = 0.03  # neatline aspect in pixels vs the XMP's graticule rectangle on the ground
FRAME_TOL_PX = 6  # printed frame line found within this of the PDF's neatline...
FRAME_MIN = 0.6  # ...on at least this share of the samples along it
CITY_TOL_M = 500.0  # city centre to the warped sheet
# XMP fields that disagree with what the sheet prints, each read off the sheet by eye.
XMP_ERRATA = {
    # XMP says N 12 11' 10"; both bottom corners print 12 11' 40" (40.003" / 39.907"),
    # and the PDF's own neatline reads 12 11' 40.13".
    "NHATRANG": {"ll_lat": str(12 + 11 / 60 + 40 / 3600)},
}

# Outside the PDFs: each code's city cell (series_cells.sheet_number) and a
# WGS84 point in that city's centre, from general knowledge. Km-scale on purpose:
# it catches a sheet put on the wrong city or in the wrong zone, nothing finer.
CITIES = {
    "BIENHOA": ("Biên Hòa", 106.824, 10.945),
    "CANTHO": ("Cần Thơ", 105.785, 10.034),
    "CHULAIVI": ("Chu Lai", 108.69, 15.42),
    "DALAT": ("Đà Lạt", 108.442, 11.942),
    "DANANG": ("Đà Nẵng", 108.221, 16.068),
    "DONGHOI": ("Đồng Hới", 106.616, 17.475),
    "HAIPHONG": ("Hải Phòng", 106.682, 20.856),
    "HANOI": ("Hà Nội", 105.852, 21.028),
    "HUE": ("Huế", 107.580, 16.467),
    "LACGIAO": ("Lạc Giao", 108.045, 12.680),
    "MYTHO": ("Mỹ Tho", 106.360, 10.356),
    "NHATRANG": ("Nha Trang", 109.194, 12.245),
    "PHULANGT": ("Phủ Lạng Thương", 106.195, 21.273),
    "QUANGNGA": ("Quảng Ngãi", 108.800, 15.121),
    "QUINHON": ("Quy Nhơn", 109.224, 13.770),
    "TUYHOA": ("Tuy Hòa", 109.317, 13.088),
    "VINHBENT": ("Vinh và Bến Thủy", 105.681, 18.672),
    "VINHLONG": ("Vĩnh Long", 105.970, 10.254),
}


def open_pdf(pdf):
    return gdal.OpenEx(str(pdf), open_options=[f"DPI={DPI}"])


def utm(zone, datum):
    s = osr.SpatialReference()
    s.ImportFromProj4(f"+proj=utm +zone={zone} +units=m " + (M.INDIAN_1960_PROJ4 if datum == "indian1960" else "+datum=WGS84 +no_defs"))
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


def to_wgs(srs):
    s = srs.Clone()
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return osr.CoordinateTransformation(s, M.wgs84())


def to_own_geog(srs):
    s = srs.Clone()
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    g = srs.CloneGeogCS()
    g.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return osr.CoordinateTransformation(s, g)


def metres(a, b):
    a, b = np.atleast_2d(a), np.atleast_2d(b)
    lat = np.radians((a[:, 1] + b[:, 1]) / 2)
    return np.hypot((a[:, 0] - b[:, 0]) * 111320 * np.cos(lat), (a[:, 1] - b[:, 1]) * 110574)


def basis(p, order):
    x, y = p[:, 0] / 1000, p[:, 1] / 1000
    cols = [np.ones_like(x), x, y] + ([x * x, x * y, y * y] if order == 2 else [])
    return np.stack(cols, 1)


def neatline_ring(ds):
    geom = ogr.CreateGeometryFromWkt(ds.GetMetadata().get("NEATLINE", "POLYGON EMPTY"))
    if geom.IsEmpty():
        raise ValueError("no neatline")
    if not geom.IsValid():  # NGA neatlines double back on themselves (Nha Trang's is a bowtie)
        geom = geom.MakeValid()
    polys = [geom.GetGeometryRef(i) for i in range(geom.GetGeometryCount())] if geom.GetGeometryName() in ("MULTIPOLYGON", "GEOMETRYCOLLECTION") else [geom]
    polys = [p for p in polys if p.GetGeometryName() == "POLYGON"]
    poly = max(polys, key=lambda g: g.GetArea()).SimplifyPreserveTopology(0.5)  # drops collinear vertices only (<0.5 m)
    ring = poly.GetGeometryRef(0)
    pts = [ring.GetPoint_2D(i) for i in range(ring.GetPointCount())]
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 4:
        raise ValueError("no usable neatline")
    return np.array(pts), poly


def frame_check(ds, mask):
    """Is there a dark printed line where the PDF says the neatline is?

    The PDF's NEATLINE and its control points are both NGA metadata; this looks
    at the pixels instead. Along every edge longer than 800 px, 15 profiles
    across the edge (+-30 px, each averaged over 7 px along it): the darkest
    point must be a real line (40 levels under the profile's median) and sit
    within FRAME_TOL_PX of the mask. Edges that cut through map content where
    the sheet bleeds past its frame fail some samples; a misregistered neatline
    fails nearly all of them. Returns (share found, median |offset| px).
    """
    bands = [ds.GetRasterBand(b) for b in (1, 2, 3)]
    W, H = ds.RasterXSize, ds.RasterYSize
    found, offsets, n = 0, [], 0
    for a, b in zip(mask, np.roll(mask, -1, 0)):
        L = np.hypot(*(b - a))
        if L < 800:
            continue
        u = (b - a) / L
        nrm = np.array([-u[1], u[0]])
        for t in np.linspace(0.1, 0.9, 15):
            p = a + t * (b - a)
            x0, y0 = int(p[0] - 40), int(p[1] - 40)
            if x0 < 0 or y0 < 0 or x0 + 81 > W or y0 + 81 > H:
                continue
            n += 1
            win = np.mean([bd.ReadAsArray(x0, y0, 81, 81).astype(float) for bd in bands], 0)
            prof = []
            for s_ in range(-30, 31):
                vals = [win[int(round(40 + s_ * nrm[1] + k * u[1])), int(round(40 + s_ * nrm[0] + k * u[0]))] for k in range(-3, 4)]
                prof.append(np.mean(vals))
            prof = np.array(prof)
            k = int(prof.argmin())
            if np.median(prof) - prof[k] >= 40 and abs(k - 30) <= FRAME_TOL_PX:
                found += 1
                offsets.append(abs(k - 30))
    return (round(found / n, 2) if n else 0.0), (float(np.median(offsets)) if offsets else None)


def analyse_one(pdf, code):
    city, clon, clat = CITIES[code]
    ds = open_pdf(pdf)
    md, meta = ds.GetMetadata(), {**M.xmp_fields(ds), **XMP_ERRATA.get(code, {})}
    w, h = ds.RasterXSize, ds.RasterYSize
    out = {"code": code, "city": city, "width": w, "height": h, "held": []}
    hold = out["held"].append
    out["edition"] = (md.get("KEYWORDS") or "").strip()
    if out["edition"] != meta.get("edition", "").strip():
        hold(f"edition: PDF keywords {out['edition']!r} vs XMP {meta.get('edition')!r}")
    out["title"] = meta.get("title", "").strip() or None
    out["pri_date"] = meta.get("pri_date")
    out["year"] = int(meta["pri_date"][:4]) if re.match(r"^\d{4}-", meta.get("pri_date", "")) else None
    out["scale"] = int(meta["scale"]) if meta.get("scale", "").isdigit() else None
    out["xmp_datum"] = meta.get("horizontal_datum")
    declared = osr.SpatialReference()
    declared.ImportFromWkt(ds.GetGCPProjection() or ds.GetProjection())
    out["gdal_datum"] = declared.GetAttrValue("DATUM")

    # Zone from the sheet centre (never an edge), cross-checked against GDAL's central meridian.
    ll = (float(meta["ll_long"].lstrip("+")), float(meta["ll_lat"].lstrip("+")))
    ur = (float(meta["ur_long"].lstrip("+")), float(meta["ur_lat"].lstrip("+")))
    zone = int(((ll[0] + ur[0]) / 2 + 180) // 6) + 1
    cm = declared.GetProjParm("central_meridian")
    out["zone"] = zone
    if int(round((cm + 183) / 6)) != zone:
        hold(f"zone: centre says {zone}, PDF central meridian {cm}")
    srs = utm(zone, "indian1960")

    # Control points against an affine in the sheet's own grid.
    gcps = ds.GetGCPs()
    if len(gcps) < 4:
        raise ValueError(f"{len(gcps)} control points")
    px = np.array([[g.GCPPixel, g.GCPLine] for g in gcps])
    proj = np.array([[g.GCPX, g.GCPY] for g in gcps])
    inv = np.linalg.lstsq(np.c_[px, np.ones(len(px))], proj, rcond=None)[0]  # pixel -> proj
    fwd = np.linalg.lstsq(np.c_[proj, np.ones(len(proj))], px, rcond=None)[0]  # proj -> pixel
    res = np.hypot(*(np.c_[px, np.ones(len(px))] @ inv - proj).T)
    out["gcps"] = len(gcps)
    out["gcp_rms_m"] = round(float(np.sqrt((res**2).mean())), 2)
    out["gcp_max_m"] = round(float(res.max()), 2)
    if res.max() > GCP_TOL_M:
        hold(f"control points: max {res.max():.1f} m off an affine")
    sx, sy = np.hypot(*inv[0]), np.hypot(*inv[1])
    out["m_per_px"] = [round(float(sx), 4), round(float(sy), 4)]
    out["squareness"] = round(float(abs(sx - sy) / ((sx + sy) / 2)), 4)
    if out["squareness"] > SQUARE_TOL:
        hold(f"pixels not square: {sx:.3f} x {sy:.3f} m")
    if out["scale"]:
        want = out["scale"] * 0.0254 / DPI
        out["scale_ratio"] = round(float((sx + sy) / 2 / want), 4)
        if abs(out["scale_ratio"] - 1) > SCALE_TOL:
            hold(f"ground pixel {(sx + sy) / 2:.3f} m, printed 1:{out['scale']} at {DPI} dpi says {want:.3f}")

    # Neatline: printed graticule (own datum -- a zone check, blind to datum) and pixel mask.
    ring, poly = neatline_ring(ds)
    geo = np.array([to_own_geog(srs).TransformPoint(x, y)[:2] for x, y in ring])
    got = (*geo.min(0), *geo.max(0))
    want = (*ll, *ur)
    gerr = max(abs(a - b) for a, b in zip(got, want))
    out["graticule_err_m"] = round(gerr * 111000, 1)
    if out["graticule_err_m"] > GRATICULE_TOL_M:
        hold(f"neatline {out['graticule_err_m']} m off the XMP graticule")
    mask = np.c_[ring, np.ones(len(ring))] @ fwd
    if (mask.min(0) < -1).any() or (mask[:, 0].max() > w + 1) or (mask[:, 1].max() > h + 1):
        hold("neatline falls outside the raster")
    mask = np.clip(mask, 0, [w, h])
    nw, nh = (mask.max(0) - mask.min(0))
    mid = math.radians((ll[1] + ur[1]) / 2)
    printed = (ur[0] - ll[0]) * 111320 * math.cos(mid) / ((ur[1] - ll[1]) * 110574)
    out["neatline_px"] = [round(float(nw)), round(float(nh))]
    out["neatline_aspect"] = round(float(nw * sx / (nh * sy)), 4)
    out["graticule_aspect"] = round(float(printed), 4)
    if abs(out["neatline_aspect"] / printed - 1) > ASPECT_TOL:
        hold(f"neatline aspect {out['neatline_aspect']} vs the printed graticule's {printed:.4f}")
    if nw < 0.5 * w or nh < 0.5 * h:
        hold(f"neatline only {nw:.0f}x{nh:.0f} of a {w}x{h} page")
    out["frame_found"], out["frame_offset_px"] = frame_check(ds, mask)
    if out["frame_found"] < FRAME_MIN:
        hold(f"printed frame line found on only {out['frame_found']:.0%} of the neatline")

    # Ground: the affine sampled 5x5 across the neatline, through the explicit Indian 1960.
    (x0, y0), (x1, y1) = mask.min(0), mask.max(0)
    gpx = np.array([[x, y] for y in np.linspace(y0, y1, 5) for x in np.linspace(x0, x1, 5)])
    gproj = np.c_[gpx, np.ones(len(gpx))] @ inv
    t = to_wgs(srs)
    ground = np.array([t.TransformPoint(x, y)[:2] for x, y in gproj])
    coef, *_ = np.linalg.lstsq(basis(gpx, ORDER), ground, rcond=None)
    fit = metres(basis(gpx, ORDER) @ coef, ground)
    out["fit_rms_m"] = round(float(np.sqrt((fit**2).mean())), 3)
    if out["fit_rms_m"] > 1.0:
        hold(f"order-{ORDER} fit misses its own grid by {out['fit_rms_m']} m")
    mask_ground = basis(mask, ORDER) @ coef
    out["bbox"] = [round(float(v), 6) for v in (*mask_ground.min(0), *mask_ground.max(0))]

    # The city: its centre inside the warped sheet.
    ring_g = ogr.Geometry(ogr.wkbLinearRing)
    for lon, lat in [*mask_ground, mask_ground[0]]:
        ring_g.AddPoint_2D(float(lon), float(lat))
    sheet = ogr.Geometry(ogr.wkbPolygon)
    sheet.AddGeometry(ring_g)
    pt = ogr.Geometry(ogr.wkbPoint)
    pt.AddPoint_2D(clon, clat)
    out["city_miss_m"] = 0.0 if sheet.Contains(pt) else round(pt.Distance(sheet) * 111320 * math.cos(math.radians(clat)), 0)
    if out["city_miss_m"] > CITY_TOL_M:
        hold(f"{city} centre is {out['city_miss_m']:.0f} m outside the sheet")

    # What the two wrong readings would have done to the sheet centre (diagnostic, not a gate).
    c = gproj[12]
    here = np.array(t.TransformPoint(*c)[:2])
    for name, s in (("wgs84", utm(zone, "wgs84")), ("gdal_declared", declared)):
        other = np.array(to_wgs(s).TransformPoint(*c)[:2])
        out[f"shift_vs_{name}_m"] = round(float(metres(here, other)[0]), 1)

    out["annotation_input"] = {"w": w, "h": h, "px": gpx.tolist(), "ground": ground.tolist(), "mask": mask.tolist()}
    out["pass"] = not out["held"]
    return out


def cmd_analyse(pdf_dir, out_path):
    report = {}
    for code in CITIES:
        pdf = Path(pdf_dir) / f"{code}.pdf"
        if not pdf.exists():
            report[code] = {"code": code, "city": CITIES[code][0], "pass": False, "held": ["pdf not downloaded"]}
            continue
        try:
            report[code] = analyse_one(pdf, code)
        except (ValueError, RuntimeError, KeyError) as e:
            report[code] = {"code": code, "city": CITIES[code][0], "pass": False, "held": [f"unreadable: {e}"]}
    Path(out_path).write_text(json.dumps(report, indent=1, ensure_ascii=False))


def cmd_annotation(analysis_json, code, iiif, out_path):
    a = json.load(open(analysis_json))[code]["annotation_input"]
    doc = annotation(iiif, a["w"], a["h"], np.array(a["px"]), np.array(a["ground"]), np.array(a["mask"]), ORDER)
    Path(out_path).write_text(json.dumps(doc, indent=1))


def cmd_render(pdf, out_jpg):
    tif = str(out_jpg) + ".tif"
    gdal.Translate(tif, open_pdf(pdf), format="GTiff", creationOptions=["COMPRESS=LZW", "BIGTIFF=IF_SAFER"])
    gdal.Translate(str(out_jpg), tif, format="JPEG", creationOptions=["QUALITY=92"])
    Path(tif).unlink()
    aux = Path(str(out_jpg) + ".aux.xml")
    if aux.exists():
        aux.unlink()


# ── the datum check ──────────────────────────────────────────────────────────


def merc(lonlat):
    lonlat = np.atleast_2d(lonlat)
    r = 6378137.0
    return np.c_[np.radians(lonlat[:, 0]) * r, r * np.log(np.tan(np.pi / 4 + np.radians(lonlat[:, 1]) / 2))]


def unmerc(xy):
    r = 6378137.0
    return np.c_[np.degrees(xy[:, 0] / r), np.degrees(2 * np.arctan(np.exp(xy[:, 1] / r)) - np.pi / 2)]


def helmert(src, dst):
    """Similarity src -> dst (least squares), as Allmaps' helmert: in Web Mercator metres."""
    A = []
    b = []
    src = np.c_[src[:, 0], -src[:, 1]]  # pixel rows run down, northings up: a similarity cannot reflect
    for (x, y), (u, v) in zip(src, dst):
        A += [[x, -y, 1, 0], [y, x, 0, 1]]
        b += [u, v]
    p = np.linalg.lstsq(np.array(A, float), np.array(b, float), rcond=None)[0]
    return lambda q: np.c_[p[0] * q[:, 0] + p[1] * q[:, 1] + p[2], p[1] * q[:, 0] - p[0] * q[:, 1] + p[3]]


def cmd_datum(pdf, ann_path, img_path, out_path):
    import cv2

    code = Path(pdf).stem
    ann = json.load(open(ann_path))
    item = ann["items"][0] if "items" in ann else ann
    src = item["target"]["source"]
    feats = item["body"]["features"]
    ref_px = np.array([f["properties"]["resourceCoords"] for f in feats], float)
    ref_geo = np.array([f["geometry"]["coordinates"] for f in feats], float)
    kind = item["body"].get("transformation", {}).get("type")
    hand = helmert(ref_px, merc(ref_geo))  # the hand opinion, applied the way Allmaps applies it
    hand_self = metres(unmerc(hand(ref_px)), ref_geo)

    ref = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    rs = src["width"] / ref.shape[1]  # served image may be a downscale of the annotated size
    ds = open_pdf(pdf)
    W, H = ds.RasterXSize, ds.RasterYSize
    k = max(1, round(W / (ref.shape[1] * 1.2)))
    usgs = np.dstack([ds.GetRasterBand(b).ReadAsArray(buf_xsize=W // k, buf_ysize=H // k) for b in (1, 2, 3)])
    usgs = cv2.cvtColor(usgs, cv2.COLOR_RGB2GRAY)
    sift = cv2.SIFT_create(nfeatures=20000)
    ka, da = sift.detectAndCompute(usgs, None)
    kb, db = sift.detectAndCompute(ref, None)
    pairs = [m for m, n in cv2.BFMatcher().knnMatch(da, db, k=2) if m.distance < 0.75 * n.distance]
    pa = np.float32([ka[m.queryIdx].pt for m in pairs]) * k
    pb = np.float32([kb[m.trainIdx].pt for m in pairs]) * rs
    Hm, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 6.0 * rs)
    inl = inl.ravel().astype(bool)
    reproj = np.hypot(*(cv2.perspectiveTransform(pa[inl][None], Hm)[0] - pb[inl]).T)

    a = analyse_one(pdf, code)
    zone = a["zone"]
    gcps = ds.GetGCPs()
    px = np.array([[g.GCPPixel, g.GCPLine] for g in gcps])
    proj = np.array([[g.GCPX, g.GCPY] for g in gcps])
    inv = np.linalg.lstsq(np.c_[px, np.ones(len(px))], proj, rcond=None)[0]
    declared = osr.SpatialReference()
    declared.ImportFromWkt(ds.GetGCPProjection() or ds.GetProjection())
    readings = {"indian1960_explicit": utm(zone, "indian1960"), "wgs84_unshifted": utm(zone, "wgs84"), "gdal_declared": declared}

    def usgs_lonlat(upx, s):
        t = to_wgs(s)
        return np.array([t.TransformPoint(*p)[:2] for p in np.c_[upx, np.ones(len(upx))] @ inv])

    # (1) At the hand-placed points themselves: where they fall on the USGS sheet, read three ways.
    gcp_usgs = cv2.perspectiveTransform(ref_px[None].astype(np.float32), np.linalg.inv(Hm))[0]
    # (2) Across the USGS neatline: a 5x5 grid pushed into the hand-placed sheet and through its fit.
    m = np.array(a["annotation_input"]["mask"])
    (x0, y0), (x1, y1) = m.min(0), m.max(0)
    grid = np.array([[x, y] for y in np.linspace(y0, y1, 5) for x in np.linspace(x0, x1, 5)], np.float32)
    grid_ref = cv2.perspectiveTransform(grid[None], Hm)[0]
    inside = (grid_ref >= 0).all(1) & (grid_ref[:, 0] <= src["width"]) & (grid_ref[:, 1] <= src["height"])
    hand_grid = unmerc(hand(grid_ref[inside]))

    out = {
        "code": code,
        "hand": {"gcps": len(feats), "transformation": kind, "self_rms_m": round(float(np.sqrt((hand_self**2).mean())), 1), "self_max_m": round(float(hand_self.max()), 1)},
        "registration": {"matches": len(pairs), "inliers": int(inl.sum()), "reproj_median_px": round(float(np.median(reproj)), 2), "ref_px_per_usgs_px": round(float(np.sqrt(abs(np.linalg.det(Hm[:2, :2])))), 4)},
        "at_hand_gcps": {},
        "across_sheet": {"points": int(inside.sum())},
    }
    for name, s in readings.items():
        got = usgs_lonlat(gcp_usgs, s)
        d1 = metres(got, ref_geo)
        lat = np.radians(ref_geo[:, 1].mean())
        mean_en = ((got - ref_geo) * [111320 * np.cos(lat), 110574]).mean(0)  # USGS minus hand, metres east/north
        d2 = metres(usgs_lonlat(grid[inside], s), hand_grid)
        out["at_hand_gcps"][name] = {"median_m": round(float(np.median(d1)), 1), "max_m": round(float(d1.max()), 1), "each_m": [round(float(v), 1) for v in d1], "mean_offset_en_m": [round(float(v), 1) for v in mean_en]}
        out["across_sheet"][name] = {"median_m": round(float(np.median(d2)), 1), "max_m": round(float(d2.max()), 1)}
    best = min(out["at_hand_gcps"], key=lambda n: out["at_hand_gcps"][n]["median_m"])
    out["closest_reading"] = best
    i60 = out["at_hand_gcps"]["indian1960_explicit"]["median_m"]
    w84 = out["at_hand_gcps"]["wgs84_unshifted"]["median_m"]
    out["verdict"] = "indian1960" if best == "indian1960_explicit" and i60 < 100 and w84 > 3 * i60 else "inconclusive"
    Path(out_path).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("code", "hand", "registration", "closest_reading", "verdict")}))
    for n in readings:
        print(f"  {n:22s} at hand GCPs median {out['at_hand_gcps'][n]['median_m']:7.1f} m (max {out['at_hand_gcps'][n]['max_m']:7.1f})   across sheet median {out['across_sheet'][n]['median_m']:7.1f} m")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    {"analyse": cmd_analyse, "render": cmd_render, "annotation": cmd_annotation, "datum": cmd_datum}.get(cmd, lambda *_: sys.exit(__doc__))(*args)
