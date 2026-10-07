#!/usr/bin/env python3
"""Georeference an L909 city plan from the UTM grid it prints.

L909 sheets are 1:12,500 photomaps with a 1,000 m UTM grid drawn over the image,
the grid zone, the datum and the corner coordinates all stated in the margin.
The datum is Indian 1960. PROJ's own EPSG:4131 -> 4326 pipeline gives *no* shift
for Vietnam, so the Helmert is spelled out exactly as `l7014_mosaic.py` does it.

    python scripts/l909_georef.py detect <image> <sheet>      # grid fit, no writes
    python scripts/l909_georef.py check  <image> <sheet>      # + printed-tick check
    python scripts/l909_georef.py annotate <image> <sheet>    # + local Allmaps JSON, no DB write
    python scripts/l909_georef.py compare  <image> <sheet>    # grid fit vs the stored georef; read-only

Per-sheet facts (zone, which km line is which, printed corner ticks) are READ OFF
THE SCAN BY EYE and recorded in READINGS with where they were read. The detector
finds the gridlines; it never invents a coordinate.

Accuracy ceiling, printed on the sheets themselves (Can Tho): these are photomaps
controlled by the best average 1:50,000 map, "features may be displaced in areas
of varying terrain heights". A small residual here measures the grid, not the
ground.
"""
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

Image.MAX_IMAGE_PIXELS = None

# Same string as scripts/l7014_mosaic.py INDIAN_1960_PROJ4 -- do not re-derive.
INDIAN_1960 = "+a=6377276.345 +rf=300.8017 +towgs84=198,881,317 +no_defs"

# e_km / n_km: the grid value of the gridline that sits at `anchor`; ticks are the
# printed geographic corner labels (Indian 1960, so compare WITHOUT the shift).
READINGS = {
    "bien-hoa": {
        "zone": 48,
        # margin: "697000m.E." under the first full vertical line, "1205000m" at the
        # bottom-most horizontal line (SW crop, read 2026-10-07).
        "e0_km": 697, "n0_km": 1205,
        # SW neatline corner ticks as printed: 10 53 40 N, 106 47 50 E.
        "sw_tick": (10 + 53 / 60 + 40 / 3600, 106 + 47 / 60 + 50 / 3600),
        "datum_note": "Horizontal datum: Indian Datum 1960; UTM zone 48 (margin, read 2026-10-07)",
    },
    "hai-phong-1968": {
        "zone": 48,
        # margin: "667000m.E." under the first full vertical line, "2300000m.N." at the
        # bottom-most horizontal line (SW crop, read 2026-10-07).
        "e0_km": 667, "n0_km": 2300,
        # SW neatline corner ticks as printed: 20 47 30 N, 106 36 00 E.
        "sw_tick": (20 + 47 / 60 + 30 / 3600, 106 + 36 / 60),
        "datum_note": "Horizontal datum: Indian 1960; 1,000 meter UTM zone 48 (margin, read 2026-10-07)",
    },
    "hon-gay": {
        "zone": 48,
        # margin: "713000m.E." under the first full vertical line, "2316000m.N." at the
        # bottom-most printed horizontal line (SW crop, read 2026-10-07). The datum line of the
        # box was cut off in the crop; Indian 1960 assumed from the series.
        "e0_km": 713, "n0_km": 2317,
        "sw_tick": (20 + 56 / 60, 107 + 2.5 / 60),
        "datum_note": "UTM zone 48 read; horizontal datum assumed Indian 1960",
        # the 2316000 line sits 3 px inside the detected face edge, so it is not traced
        "face": (0.032, 0.048, 0.979, 0.6505),
        # the bay is too faint for the detector: y of the 2316000 line, fraction of height.
        # That line hugs the neatline and is not traced, so n0_km is the 2317000 line above it.
        "hline": 0.642,
    },
    "quang-ngai-1966": {
        "zone": 49,
        # margin: "261" under the first full vertical line (neatline is 260000m.E.),
        # "1671000m.N." at the bottom-most horizontal line (read 2026-10-07).
        "e0_km": 261, "n0_km": 1671,
        "sw_tick": (15 + 6 / 60, 108 + 46 / 60),
        # tinted paper: the colour test takes the whole page, so the face is read by eye
        # (fractions x0, y0, x1, y1 of the image, from the overview)
        "face": (0.047, 0.032, 0.822, 0.728),
        "datum_note": "Horizontal datum: Indian Datum 1960; 1,000 meter UTM zone 49 (margin, read 2026-10-07)",
    },
}


def map_face(rgb):
    """Bounding box of the coloured photomap: the margin and legend are white/grey."""
    a = rgb.astype(np.int16)
    h, w = a.shape[:2]
    chroma = a.max(2) - a.min(2)
    # Biên Hòa's vivid print first; pale prints (Hải Phòng) need the looser pass.
    for thr, cf, rf in ((28, 0.35, 0.25), (10, 0.2, 0.2)):
        sat = chroma > thr
        xs, ys = np.where(sat.mean(0) > cf)[0], np.where(sat.mean(1) > rf)[0]
        if len(xs) and len(ys) and (xs[-1] - xs[0]) > 0.5 * w and (ys[-1] - ys[0]) > 0.3 * h:
            return xs[0], ys[0], xs[-1], ys[-1]
    raise SystemExit("map_face: no coloured photomap region found -- check the scan")


def darkness(gray, axis, win=15):
    """Thin dark lines: local mean minus pixel, along `axis` only."""
    mean = uniform_filter1d(gray.astype(np.float32), win, axis=axis)
    return np.maximum(mean - gray, 0)


def spacing_from_profile(prof, extent):
    """Grid spacing = strongest autocorrelation lag between 6% and 40% of the face."""
    p = prof - prof.mean()
    ac = np.correlate(p, p, "full")[len(p) - 1:]
    lo, hi = int(0.06 * extent), int(0.40 * extent)
    return lo + int(np.argmax(ac[lo:hi]))


def line_family(gray, box, axis):
    """Positions of a family of equally spaced gridlines along `axis`.

    axis=1 finds vertical lines (x positions); axis=0 finds horizontal ones.
    Returns (positions, spacing) in pixels of `gray`.
    """
    x0, y0, x1, y1 = box
    d = darkness(gray[y0:y1, x0:x1], axis)
    prof = d.sum(axis=0 if axis == 1 else 1)
    prof = uniform_filter1d(prof, 3)
    prof = prof - uniform_filter1d(prof, 101)  # drop slow imagery trend
    hint = spacing_from_profile(prof, len(prof))
    pk, _ = find_peaks(prof, distance=int(hint * 0.6), prominence=prof.std() * 0.8)
    off = x0 if axis == 1 else y0
    return pk + off, hint


def equal_spacing(pos, s0):
    """Equal-spacing fit anchored on the autocorrelation spacing `s0`.

    The phase is voted, not taken from the first peak: any peak may be a road.
    Returns (inlier positions, their integer line index, spacing, phase).
    """
    best = None
    for p0 in pos:
        k = np.round((pos - p0) / s0)
        keep = np.abs(pos - (p0 + k * s0)) < 0.12 * s0
        if best is None or keep.sum() > best.sum():
            best = keep
    keep = best
    p0 = pos[keep][0]
    k = np.round((pos[keep] - p0) / s0).astype(int)
    A = np.c_[k, np.ones(len(k))]
    s, p = np.linalg.lstsq(A, pos[keep], rcond=None)[0]
    return pos[keep], k, s, p


def trace(D, axis, pred, extent, win=30, strips=16):
    """Follow one gridline along its length: the best local peak in each strip.

    D is the darkness map; axis=1 traces a vertical line (x as a function of y).
    Returns (c0, c1, n_inliers) for pos = c0 + c1 * along, or None.
    """
    lo, hi = extent
    edges = np.linspace(lo, hi, strips + 1).astype(int)
    pts = []
    for a, b in zip(edges[:-1], edges[1:]):
        c = int(round(pred))
        w0, w1 = max(c - win, 0), c + win
        if axis == 1:
            prof = D[a:b, w0:w1].sum(0)
        else:
            prof = D[w0:w1, a:b].sum(1)
        prof = uniform_filter1d(prof, 3)
        if prof.max() < 2.5 * (np.median(prof) + 1e-6):
            continue
        pts.append(((a + b) / 2, w0 + int(np.argmax(prof))))
    if len(pts) < strips // 2:
        return None
    t, v = np.array(pts, float).T
    keep = np.ones(len(t), bool)
    for _ in range(3):
        c1, c0 = np.polyfit(t[keep], v[keep], 1)
        keep = np.abs(v - (c0 + c1 * t)) < 3.0
        if keep.sum() < strips // 2:
            return None
    return c0, c1, int(keep.sum())


def lattice(gray, box, hline=None):
    """Traced gridlines and their intersections: ({i: line}, {j: line}, [(i, j, x, y)], spacing).

    i counts vertical lines rightward and j horizontal lines downward, from the first
    traced line. Which km each one is comes later, from the margin or a stored fit.
    """
    x0, y0, x1, y1 = box
    inset = 40
    vx, vh = line_family(gray, box, 1)
    hy, hh = line_family(gray, box, 0)
    _, vk, vs, vp = equal_spacing(vx, vh)
    # the grid is square: a horizontal hint far from the vertical spacing is a harmonic
    if abs(hh / vh - 1) > 0.08:
        hh = vh
    _, hk, hs, hp = equal_spacing(hy, hh)
    if hline is not None:  # faint horizontals: one hand-read line pins the phase
        hs, hp = vs, hline
    Dv, Dh = darkness(gray, 1), darkness(gray, 0)
    ik = [k for k in range(-3, 40) if x0 + inset < vp + k * vs < x1 - inset]
    jk = [k for k in range(-3, 60) if y0 + inset < hp + k * hs < y1 - inset]
    V = {k: trace(Dv, 1, vp + k * vs, (y0 + inset, y1 - inset)) for k in ik}
    H = {k: trace(Dh, 0, hp + k * hs, (x0 + inset, x1 - inset)) for k in jk}
    V = {k: v for k, v in V.items() if v}
    H = {k: v for k, v in H.items() if v}
    # a line that locked onto the neatline or a label runs at another slope than its family
    for L in (V, H):
        med = np.median([b for _, b, _ in L.values()]) if L else 0
        for k in [k for k, (_, b, _) in L.items() if abs(b - med) > 0.004]:
            del L[k]
    pts = []
    for i, (a, b, _) in V.items():
        for j, (c, d, _) in H.items():
            x = (a + b * c) / (1 - b * d)
            pts.append((i, j, x, c + d * x))
    return V, H, pts, (vs, hs)


def fit_grid(gray, box, rd):
    """GCPs from the grid intersections: [(x_px, y_px, E_m, N_m), ...], labels from READINGS.

    Vertical k counts rightward from the first traced line, which the margin reads as
    e0_km; horizontal k counts downward and the LAST traced line is n0_km (the
    bottom-most gridline whose label was read).
    """
    hl = rd.get("hline")
    V, H, pts, sp = lattice(gray, box, None if hl is None else hl * gray.shape[0])
    kv0, kh_bottom = min(V), max(H)
    gcps = [(x, y, (rd["e0_km"] + i - kv0) * 1000.0, (rd["n0_km"] + kh_bottom - j) * 1000.0)
            for i, j, x, y in pts]
    return gcps, V, H, sp


def affine(gcps):
    g = np.array(gcps)
    A = np.c_[g[:, 0], g[:, 1], np.ones(len(g))]
    M = np.linalg.lstsq(A, g[:, 2:4], rcond=None)[0]  # pixel -> (E, N)
    res = np.hypot(*(A @ M - g[:, 2:4]).T)
    return M, res


def to_wgs84(rd, E, N):
    from pyproj import Transformer
    ell = "+a=6377276.345 +rf=300.8017"
    shifted = f"+proj=utm +zone={rd['zone']} {INDIAN_1960} +units=m"
    flat = f"+proj=utm +zone={rd['zone']} {ell} +units=m +no_defs"
    t84 = Transformer.from_crs(shifted, "EPSG:4326", always_xy=True)
    tind = Transformer.from_crs(flat, f"+proj=longlat {ell} +no_defs", always_xy=True)
    return t84.transform(E, N), tind.transform(E, N)


def neatline(gray, box):
    """The four neatline sides, each traced like a gridline, as a pixel quad (TL,TR,BR,BL).

    A side that cannot be traced falls back to the face box edge and is reported:
    the quad is only as good as the sides found, and a person edits the mask in
    Allmaps either way.
    """
    x0, y0, x1, y1 = box
    Dv, Dh = darkness(gray, 1), darkness(gray, 0)
    L = trace(Dv, 1, x0 + 4, (y0 + 60, y1 - 60), win=30)
    R = trace(Dv, 1, x1 - 4, (y0 + 60, y1 - 60), win=30)
    T = trace(Dh, 0, y0 + 4, (x0 + 60, x1 - 60), win=30)
    B = trace(Dh, 0, y1 - 4, (x0 + 60, x1 - 60), win=30)
    miss = [n for n, v in zip("LRTB", (L, R, T, B)) if v is None]
    L = L or (x0, 0.0, 0); R = R or (x1, 0.0, 0); T = T or (y0, 0.0, 0); B = B or (y1, 0.0, 0)

    def cross(v, h):  # vertical x = a + b y, horizontal y = c + d x
        a, b, _ = v
        c, d, _ = h
        x = (a + b * c) / (1 - b * d)
        return [x, c + d * x]
    return [cross(L, T), cross(R, T), cross(R, B), cross(L, B)], miss


def scan_row(slug):
    import json
    return next(s for s in json.load(open("work/l909/ingested-scans.json"))["scans"]
                if s["slug"] == slug and s["side"] == "recto")


def annotation(iiif, w, h, pts, mask):
    """Allmaps georeference annotation: polynomial order 1, mask = neatline quad.

    Same shape as `annotation()` in indochine100k_georef.py. Not imported: that one
    is fixed to four named corners, and this takes any control-point list.
    """
    poly = " ".join(f"{round(x)},{round(y)}" for x, y in mask)
    return {
        "type": "AnnotationPage",
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "items": [{
            "id": f"{iiif}/annotation", "type": "Annotation",
            "@context": ["http://iiif.io/api/extension/georef/1/context.json",
                         "http://iiif.io/api/presentation/3/context.json"],
            "motivation": "georeferencing",
            "target": {"type": "SpecificResource",
                       "source": {"id": iiif, "type": "ImageService3", "width": w, "height": h},
                       "selector": {"type": "SvgSelector",
                                    "value": f'<svg width="{w}" height="{h}"><polygon points="{poly}" /></svg>'}},
            "body": {"type": "FeatureCollection",
                     "transformation": {"type": "polynomial", "options": {"order": 1}},
                     "features": [{"type": "Feature",
                                   "properties": {"resourceCoords": [round(x), round(y)]},
                                   "geometry": {"type": "Point", "coordinates": [round(lo, 7), round(la, 7)]}}
                                  for (x, y), (lo, la) in pts]},
        }],
    }


def stored_annotation(mid):
    """The stored (draft or public) annotation, read with the service key. Read-only."""
    import os
    import requests
    from dotenv import load_dotenv
    load_dotenv(".env")
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    r = requests.get(f"{url}/storage/v1/object/annotations/{mid}.json",
                     headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=60)
    r.raise_for_status()
    return r.json()["items"][0]


def poly_terms(p, order):
    x, y = p[:, 0], p[:, 1]
    cols = [np.ones(len(x))]
    for n in range(1, order + 1):
        cols += [x ** (n - k) * y ** k for k in range(n + 1)]
    return np.c_[tuple(cols)]


def compare(path, slug):
    """Grid fit vs the stored georeference, in the stored annotation's own pixel frame.

    Km labels come from the stored fit rounded to the nearest 1,000 m, so this proves
    nothing about the labels themselves -- only the stored fit's offset from the
    printed grid. Zone is whichever of 48/49 leaves the smallest rounding margin; a
    margin over ~250 m means the labels or the zone are not trustworthy and the row
    says so. Datum is assumed Indian 1960 (the Helmert above), which the sheets'
    margins state for Bien Hoa; a sheet on another datum would show as a ~500 m offset.
    """
    from pyproj import Transformer
    row = scan_row(slug)
    ann = stored_annotation(row["id"])
    src = ann["target"]["source"]
    feats = ann["body"]["features"]
    order = ann["body"]["transformation"]["options"]["order"]
    spx = np.array([f["properties"]["resourceCoords"] for f in feats], float)
    sll = np.array([f["geometry"]["coordinates"] for f in feats], float)
    C = np.linalg.lstsq(poly_terms(spx, order), sll, rcond=None)[0]
    img = Image.open(path).convert("RGB")
    f = src["width"] / img.size[0]  # working image -> stored frame (same file, so uniform)
    gray = np.asarray(img.convert("L"))
    box = map_face(np.asarray(img))
    V, H, pts, (vs, hs) = lattice(gray, box)
    P = np.array([[x * f, y * f] for _, _, x, y in pts])
    st = poly_terms(P, order) @ C                      # stored fit's lon/lat at each grid crossing
    best = None
    for zone in (48, 49):
        t = Transformer.from_crs("EPSG:4326", f"+proj=utm +zone={zone} {INDIAN_1960} +units=m", always_xy=True)
        E, N = t.transform(st[:, 0], st[:, 1])
        ii = np.array([p[0] for p in pts]); jj = np.array([p[1] for p in pts])
        eL = {i: np.median(E[ii == i]) for i in set(ii)}
        nL = {j: np.median(N[jj == j]) for j in set(jj)}
        margin = max(max(abs(v - round(v, -3)) for v in eL.values()),
                     max(abs(v - round(v, -3)) for v in nL.values()))
        if best is None or margin < best[0]:
            best = (margin, zone, eL, nL)
    margin, zone, eL, nL = best
    G = np.array([[round(eL[p[0]], -3), round(nL[p[1]], -3)] for p in pts])
    M, res = affine([(x, y, e, n) for (_, _, x, y), (e, n) in zip(pts, G)])
    t = Transformer.from_crs(f"+proj=utm +zone={zone} {INDIAN_1960} +units=m", "EPSG:4326", always_xy=True)
    mine = np.array(t.transform(G[:, 0], G[:, 1])).T   # grid-defined lon/lat of each crossing
    lat = np.radians(sll[:, 1].mean())
    d = np.c_[(st[:, 0] - mine[:, 0]) * 111320 * np.cos(lat), (st[:, 1] - mine[:, 1]) * 110574]
    mag = np.hypot(*d.T)
    flag = "LABELS?" if margin > 250 else ("" if res.max() < 15 else "GRID-FIT?")
    print(f"{slug:24} zone {zone} lines {len(V)}x{len(H)} grid-fit rms {np.sqrt((res**2).mean()):4.1f} m  "
          f"label margin {margin:4.0f} m | stored-minus-grid: mean E {d[:,0].mean():+6.1f} N {d[:,1].mean():+6.1f}  "
          f"rms {np.sqrt((mag**2).mean()):5.1f}  max {mag.max():5.1f} m  (order {order}, {len(feats)} pts) {flag}")


def main(argv):
    import json
    from pathlib import Path
    cmd, path, sheet = argv[1], argv[2], argv[3]
    if cmd == "compare":
        return compare(path, sheet)
    rd = READINGS[sheet]
    img = Image.open(path).convert("RGB")
    rgb = np.asarray(img)
    gray = np.asarray(img.convert("L"))
    box = map_face(rgb) if "face" not in rd else tuple(int(v * d) for v, d in zip(rd["face"], (img.size[0], img.size[1]) * 2))
    print(f"{sheet}: image {img.size}, map face x {box[0]}..{box[2]}  y {box[1]}..{box[3]}")
    gcps, V, H, (vs, hs) = fit_grid(gray, box, rd)
    print(f"traced lines: {len(V)} vertical, {len(H)} horizontal, {len(gcps)} intersections")
    print(f"spacing {vs:.2f} x {hs:.2f} px  (aspect {vs / hs:.4f})")
    for name, Ls in (("vertical", V), ("horizontal", H)):
        print(f"  {name} slope (px/px): " + " ".join(f"{b:+.4f}" for _, b, _ in Ls.values()))
    M, res = affine(gcps)
    print(f"affine pixel->grid: RMS {np.sqrt((res**2).mean()):.1f} m, max {res.max():.1f} m, "
          f"scale {np.hypot(M[0,0],M[0,1]):.3f} / {np.hypot(M[1,0],M[1,1]):.3f} m/px")
    quad, miss = neatline(gray, box)
    if miss:
        print(f"  neatline sides NOT traced (fell back to the face box): {''.join(miss)}")
    if cmd in ("check", "annotate"):
        x, y = quad[3]  # SW corner of the traced neatline
        E, N = np.array([x, y, 1.0]) @ M
        (lon84, lat84), (lonI, latI) = to_wgs84(rd, E, N)
        tl, tn = rd["sw_tick"]
        print(f"SW corner  grid E {E:.0f} N {N:.0f}")
        print(f"  Indian 1960 geographic : {latI:.5f} N {lonI:.5f} E   printed {tl:.5f} N {tn:.5f} E")
        print(f"  off printed tick       : {(latI - tl) * 110574:.0f} m N, "
              f"{(lonI - tn) * 111320 * np.cos(np.radians(latI)):.0f} m E")
        off = max(abs((latI - tl) * 110574), abs((lonI - tn) * 111320 * np.cos(np.radians(latI))))
        if off > 40:  # a wrong km label is off by kilometres; 40 m clears whole-second ticks
            raise SystemExit(f"printed corner tick disagrees by {off:.0f} m -- km labels or zone wrong; nothing written")
        print(f"  WGS 84 (shifted)       : {lat84:.5f} N {lon84:.5f} E "
              f"({np.hypot((lat84 - latI) * 110574, (lon84 - lonI) * 111320 * np.cos(np.radians(latI))):.0f} m from the unshifted reading)")
    if cmd == "annotate":
        row = scan_row(sheet)
        f = row["width"] / img.size[0]  # working image -> full-resolution pixels
        ik, jk = sorted(V), sorted(H)
        pick_i = [ik[0], ik[len(ik) // 2], ik[-1]]
        pick_j = [jk[0], jk[len(jk) // 2], jk[-1]]
        # 3 x 3 lattice: few enough to edit by hand in Allmaps, spread enough to pin the fit
        nine = [g for g in gcps
                if any(abs(g[2] - (rd["e0_km"] + i - ik[0]) * 1000) < 1 for i in pick_i)
                and any(abs(g[3] - (rd["n0_km"] + jk[-1] - j) * 1000) < 1 for j in pick_j)]
        M9, _ = affine(nine)
        full = np.array(gcps)
        pred = np.c_[full[:, 0], full[:, 1], np.ones(len(full))] @ M9
        r9 = np.hypot(*(pred - full[:, 2:4]).T)
        print(f"{len(nine)} editable control points vs all {len(gcps)} intersections: "
              f"RMS {np.sqrt((r9**2).mean()):.1f} m, max {r9.max():.1f} m")
        pts = []
        for x, y, E, N in nine:
            (lon, lat), _ = to_wgs84(rd, E, N)
            pts.append(((x * f, y * f), (lon, lat)))
        mask = [(x * f, y * f) for x, y in quad]
        ann = annotation(row["iiif_image"], row["width"], row["height"], pts, mask)
        out = Path("work/l909/annotations")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{row['id']}.json").write_text(json.dumps(ann, indent=1))
        lonlat = [to_wgs84(rd, *(np.array([x, y, 1.0]) @ M))[0] for x, y in quad]
        bbox = [min(l[0] for l in lonlat), min(l[1] for l in lonlat),
                max(l[0] for l in lonlat), max(l[1] for l in lonlat)]
        print(f"wrote work/l909/annotations/{row['id']}.json   bbox "
              f"{bbox[0]:.5f},{bbox[1]:.5f},{bbox[2]:.5f},{bbox[3]:.5f}")
        if "--apply" in argv:
            apply(row["id"], out / f"{row['id']}.json", [round(b, 7) for b in bbox])
        else:
            print("dry run: no database or storage write (add --apply)")


def apply(mid, file, bbox):
    """Draft rows only, like `annotate` in indochine100k_georef.py.

    Upload the JSON, point `annotation_url` at the app's own route (the raw storage
    URL 400s -- see that script), set the bbox and the flag. status stays draft, so
    nothing becomes public; the PATCH filter refuses anything already georeferenced.
    """
    import os
    import requests
    from dotenv import load_dotenv
    load_dotenv(".env")
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    row = requests.get(f"{url}/rest/v1/maps", headers=h, timeout=30, params={
        "id": f"eq.{mid}", "select": "name,status,is_georeferenced,annotation_url"}).json()
    if not row or row[0]["status"] != "draft" or row[0]["is_georeferenced"] or row[0]["annotation_url"]:
        raise SystemExit(f"refusing: row is not an un-georeferenced draft: {row}")
    body = file.read_bytes()
    obj = f"{url}/storage/v1/object/annotations/{mid}.json"
    hdr = {**h, "Content-Type": "application/json", "x-upsert": "true"}
    r = requests.post(obj, headers=hdr, data=body, timeout=60)
    if r.status_code == 400:
        r = requests.put(obj, headers=hdr, data=body, timeout=60)
    r.raise_for_status()
    r = requests.patch(f"{url}/rest/v1/maps?id=eq.{mid}&status=eq.draft&is_georeferenced=is.false",
                       headers={**h, "Prefer": "return=representation"}, timeout=30,
                       json={"annotation_url": f"https://maparchive.vn/api/maps/{mid}/annotation",
                             "is_georeferenced": True, "bbox": bbox})
    r.raise_for_status()
    back = requests.get(f"{url}/storage/v1/object/annotations/{mid}.json", headers=h, timeout=60)
    print(f"written: {row[0]['name']} -> draft row patched ({len(r.json())} row); "
          f"storage read-back {'identical' if back.content == body else 'DIFFERS'}")


if __name__ == "__main__":
    main(sys.argv)
