#!/usr/bin/env python3
"""Georeference annotations for the PCL L7014 rows, from the control points inside each GeoPDF.

The 436 sheets that `l7014_mosaic.py warp` accepts carry their own control
points and printed neatline, so there is nothing to pin by hand: read them,
write them as an Allmaps annotation against the sheet's IIIF image, done. The
CRS is `pick_crs`, the same measurement the mosaic warp uses -- so the Indian
1960 datum shift is applied here too, and a sheet the warp refuses (NOGEO,
OFFCELL, OFFGRID) is refused here for the same reason.

    python3 scripts/l7014_annotate_pdf.py --sheet 6150-1     # dry run, one sheet
    python3 scripts/l7014_annotate_pdf.py                    # dry run, every PCL row
    python3 scripts/l7014_annotate_pdf.py --write            # upload what passes, point the rows at it
    python3 scripts/l7014_annotate_pdf.py --auto --write     # the autoplace passes (no PDF georef) instead

Second-order polynomial, not first: the control points are in UTM and Allmaps
wants lon/lat, which a first-order fit cannot follow over 28 km -- measured
11-13 m RMS on two sheets, against 3 m at order 2.

The gate, per sheet, is not the fit's own residual (a fit always agrees with
itself). It is the annotation's mask pushed through its own transform and
compared with the outline the mosaic draws for that sheet
(`work/l7014/build/<key>.geojson`): two independent routes from the same PDF
to the same ground.
"""

import argparse
import json
import sys
import urllib.error
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

sys.path.insert(0, str(Path(__file__).parent))
import l7014_mosaic as M  # noqa: E402
from l7014_annotate import BUCKET, env, plain, req  # noqa: E402

gdal.UseExceptions()
OUT = Path("work/l7014/annotations")
MANIFEST = Path("work/l7014/build/l7014-20260921.geojson")
ORDER = 2
AFFINE_TOL_M = 40.0
OFFCELL = {"5650-1", "5729-1", "5926-2", "6130-1", "6146-2", "6147-1", "6433-3", "6530-3", "6534-3", "6538-4", "6636-4", "6731-1"}
FIT_TOL_M = 80.0  # four hand/detected corners, an affine: a good sheet misses by <25 m (the 7 autoplace passes: 5-22); above that the misfit is recorded in the row
OUTLINE_TOL_M = 25.0  # ~6 px at 150 dpi; the fit itself is ~3 m


def _basis(p):
    x, y = p[:, 0] / 1000, p[:, 1] / 1000
    return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], 1)


def _lonlat(srs):
    s = srs.Clone()
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    w = osr.SpatialReference()
    w.ImportFromEPSG(4326)
    w.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return osr.CoordinateTransformation(s, w)


def read_pdf(sheet, pdf, offcell_ok=False):
    """(pixels, ground lon/lat, mask pixels, size, crs reading, affine residual m) or raises ValueError(reason)."""
    ds = gdal.Open(str(pdf))
    gcps, gt = ds.GetGCPs(), ds.GetGeoTransform(can_return_null=True)
    if not gcps and gt is None:
        raise ValueError("nogeo")
    meta = M.xmp_fields(ds)
    try:
        srs, crs, _ = M.pick_crs(ds, meta, sheet)
    except ValueError as e:
        if not offcell_ok:
            raise ValueError(f"offcell: {e}")
        # The 15' lattice is what these miss, and it is the lattice that is in doubt (a larger or
        # re-framed print, not a faulty georeference: 6146-2's neatline corner lands within 25 m of
        # the 105 45' / 18 48'30" it prints). So take the datum reading the other 285 sheets chose.
        declared, _ = M.sheet_crs(ds, meta)
        srs, crs = M.indian_1960_utm(declared), "indian1960*"
    # Where the sheet carries no printed corners the check snaps to the 15' lattice, which is the very
    # thing an offcell sheet disagrees with -- so for them it is skipped, and the check is the
    # neatline's corners landing on round minutes (printed in the note) with the printed labels read by eye.
    err = None if offcell_ok else M.graticule_error(ds, srs, meta)
    if err is not None and err > M.GRATICULE_TOL:
        raise ValueError(f"offgrid: {err:.5f} deg")
    w, h = ds.RasterXSize, ds.RasterYSize
    if gcps:
        px = np.array([[g.GCPPixel, g.GCPLine] for g in gcps])
        proj = np.array([[g.GCPX, g.GCPY] for g in gcps])
    else:  # a geotransform and no points: a 3x3 grid off the transform
        px = np.array([[x * w, y * h] for y in (0, .5, 1) for x in (0, .5, 1)])
        proj = np.array([[gt[0] + a * gt[1] + b * gt[2], gt[3] + a * gt[4] + b * gt[5]] for a, b in px])
    # The PDF's georeference is an affine in its own projected coordinates.
    inv = np.linalg.lstsq(np.c_[px, np.ones(len(px))], proj, rcond=None)[0]   # pixel -> proj
    fwd = np.linalg.lstsq(np.c_[proj, np.ones(len(proj))], px, rcond=None)[0]  # proj -> pixel
    off = np.hypot(*(np.c_[px, np.ones(len(px))] @ inv - proj).T).max()
    if off > AFFINE_TOL_M:  # 10-20 m is the scan's own registration noise (2 px), not a bad sheet
        raise ValueError(f"georef not affine: {off:.0f} m")

    neat = ds.GetMetadata().get("NEATLINE")
    if not neat:
        raise ValueError("no neatline")
    geom = ogr.CreateGeometryFromWkt(neat)
    if not geom.IsValid():
        geom = geom.MakeValid() or geom.Buffer(0)
    if geom.GetGeometryName() == "MULTIPOLYGON":  # MakeValid can split a bowtie in two
        geom = max((geom.GetGeometryRef(i) for i in range(geom.GetGeometryCount())), key=lambda g: g.Area())
    ring = geom.GetGeometryRef(0)
    ring = [ring.GetPoint_2D(i) for i in range(ring.GetPointCount())] if ring else []
    if len(ring) < 4:
        raise ValueError("no usable neatline")
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    mask = np.c_[np.array(ring), np.ones(len(ring))] @ fwd
    if offcell_ok and (mask.max(0) - mask.min(0) > 0.98 * np.array([w, h])).all():
        # Six of these carry the whole page as their NEATLINE; the printed frame is what the detector found.
        frame = frame_corners().get(sheet)
        if frame is None:
            raise ValueError("neatline is the page and no detected frame")
        mask = np.array([frame[k] for k in ("NW", "NE", "SE", "SW")])

    # Not the PDF's own 8 points: they sit on a symmetric lattice (4 corners + a
    # 2x2 interior block) that lies on one conic, so a second-order fit through
    # them is singular and swings ~2 km between points. The same affine, sampled
    # on a 5x5 grid across the neatline, is exact and well-posed.
    (x0, y0), (x1, y1) = mask.min(0), mask.max(0)
    px = np.array([[x, y] for y in np.linspace(y0, y1, 5) for x in np.linspace(x0, x1, 5)])
    t = _lonlat(srs)
    ground = np.array([t.TransformPoint(x, y)[:2] for x, y in np.c_[px, np.ones(len(px))] @ inv])
    return px, ground, mask, (w, h), crs, off


def frame_corners():
    """Pixel corners of the printed frame for sheets whose NEATLINE is the whole page."""
    regen = Path("work/l7014/regen")
    out = {s: r["corners"] for s, r in json.load(open(regen / "autoplace-detect.json")).items() if r.get("quad_ok")}
    out.update({s: r["corners"] for s, r in json.load(open(regen / "hand-corners.json")).items()})
    return out


def corner_sources():
    """sheet -> (pixel corners NW NE SE SW, ground corners, pixel size, how it was placed).

    Two sources, neither with a georeference of its own to read: the corners a person read off the
    sheet and snapped to its printed frame (`l7014_hand_corners.py`), and `l7014_autoplace.py`'s
    detected neatline against the lattice cell, for the sheets whose seams missed its 25 m gate
    (all measured under 100 m; the two above that are left out)."""
    regen = Path("work/l7014/regen")
    out = {}
    summary = json.load(open(regen / "autoplace-summary.json"))
    detect = json.load(open(regen / "autoplace-detect.json"))
    cells = json.load(open("work/l7014/lattice.json"))["cells"]
    worst = {}
    for line in open(regen / "autoplace-seams.csv").read().splitlines()[1:]:
        f = line.split(",")
        if f[3]:
            worst[f[0]] = max(worst.get(f[0], 0), float(f[3]))
    for sh in summary["fail"] + summary["unverified"]:
        if worst.get(sh, 0) >= 100:
            continue
        note = f"neatline to lattice cell; worst seam {worst[sh]:.0f} m" if sh in worst else "neatline to lattice cell; no neighbour to check against"
        out[sh] = (detect[sh]["corners"], cells[sh], detect[sh]["size"], note)
    for sh, r in json.load(open(regen / "hand-corners.json")).items():
        if r["ok"]:
            out[sh] = (r["corners"], r["ground"], r["size"],
                       f"hand-read neatline to {r['ground_from']} corners; aspect {r['aspect_err_pct']}% off")
    for sh in summary["pass"] + sorted(OFFCELL):  # done already / placed on their own PDF georeference
        out.pop(sh, None)
    return out


def read_corners(sheet, src):
    if sheet not in src:
        raise ValueError("no hand or autoplace corners")
    c, ground, size, note = src[sheet]
    px = np.array([c[k] for k in ("NW", "NE", "SE", "SW")])
    return px, np.array(ground), px, tuple(size), "lattice" if "lattice" in note else "printed", 0.0


def read_auto(sheet):
    """The 7 sheets with no usable PDF georeference that `l7014_autoplace.py seams` passed:
    the printed neatline's four detected corners against the sheet's lattice cell. Four
    points, so order 1 -- an affine, exactly what the autoplace warp itself uses."""
    summary = json.load(open("work/l7014/regen/autoplace-summary.json"))
    if sheet not in summary["pass"]:
        raise ValueError("not an autoplace pass")
    rec = json.load(open("work/l7014/regen/autoplace-detect.json"))[sheet]
    px = np.array([rec["corners"][k] for k in ("NW", "NE", "SE", "SW")])
    ground = np.array(json.load(open("work/l7014/lattice.json"))["cells"][sheet])
    return px, ground, px, tuple(rec["size"]), "lattice", 0.0


def apply(px, ground, pts, order=ORDER):
    b = _basis if order == 2 else lambda p: _basis(p)[:, :3]
    c, *_ = np.linalg.lstsq(b(px), ground, rcond=None)
    return b(pts) @ c, b(px) @ c - ground


def metres(a, b):
    lat = np.radians((a[:, 1] + b[:, 1]) / 2)
    return np.hypot((a[:, 0] - b[:, 0]) * 111320 * np.cos(lat), (a[:, 1] - b[:, 1]) * 110574)


def outline_gap(mask_ground, sheet, manifest):
    """Max metres from the annotation's outline to the mosaic's outline for the same sheet."""
    feat = manifest.get(sheet)
    if feat is None:
        return None
    ref = ogr.CreateGeometryFromJson(json.dumps(feat))
    boundary = ref.GetBoundary()
    gap = 0.0
    for lon, lat in mask_ground:
        p = ogr.Geometry(ogr.wkbPoint)
        p.AddPoint_2D(lon, lat)
        gap = max(gap, p.Distance(boundary) * 111320 * np.cos(np.radians(lat)))
    return gap


def annotation(iiif, w, h, px, ground, mask, order=ORDER):
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in mask)
    return {
        "type": "AnnotationPage",
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "items": [{
            "id": f"{iiif}/annotation",
            "type": "Annotation",
            "@context": ["http://iiif.io/api/extension/georef/1/context.json",
                         "http://iiif.io/api/presentation/3/context.json"],
            "motivation": "georeferencing",
            "target": {
                "type": "SpecificResource",
                "source": {"id": iiif, "type": "ImageService3", "width": w, "height": h},
                "selector": {"type": "SvgSelector",
                             "value": f'<svg width="{w}" height="{h}"><polygon points="{poly}" /></svg>'},
            },
            "body": {
                "type": "FeatureCollection",
                "transformation": {"type": "polynomial", "options": {"order": order}},
                "features": [
                    {"type": "Feature",
                     "properties": {"resourceCoords": [round(float(p[0]), 1), round(float(p[1]), 1)]},
                     "geometry": {"type": "Point", "coordinates": [round(float(g[0]), 7), round(float(g[1]), 7)]}}
                    for p, g in zip(px, ground)
                ],
            },
        }],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", nargs="*", help="only these sheet numbers")
    ap.add_argument("--write", action="store_true", help="upload and update the rows")
    ap.add_argument("--hand", action="store_true", help="hand-read / autoplace-failed corners (four points, order 1)")
    ap.add_argument("--offcell", action="store_true", help="the 11 OFFCELL PDFs, on their own georeference")
    ap.add_argument("--auto", action="store_true", help="the autoplace passes, from detected corners")
    ap.add_argument("--bbox-only", action="store_true", help="set maps.bbox on rows already annotated; upload nothing")
    ap.add_argument("--force", action="store_true", help="redo rows that already have an annotation")
    args = ap.parse_args()

    base, key = env()
    rows = req(f"{base}/rest/v1/maps?select=id,slug,iiif_image,annotation_url,bbox,extra_metadata"
               f"&collection=ilike.*L7014*&limit=1000", key)
    manifest = {f["properties"]["sheet"]: f["geometry"] for f in json.load(open(MANIFEST))["features"]}
    files = {r["sheet"]: r for r in M.load_sheets() if r["kind"] == "pdf"}
    OUT.mkdir(parents=True, exist_ok=True)

    src = corner_sources() if args.hand else None
    ok, skipped = [], []
    for m in sorted(rows, key=lambda r: r["extra_metadata"]["sheet_number"]):
        sheet = m["extra_metadata"]["sheet_number"]
        if args.sheet and sheet not in args.sheet:
            continue
        if args.bbox_only:
            if not m["annotation_url"] or m["bbox"]:
                continue
        elif m["annotation_url"] and not args.force:
            skipped.append((sheet, "already annotated"))
            continue
        try:
            order = 1 if (args.auto or args.hand) else ORDER
            note_how = None
            if args.hand:
                px, ground, mask, (w, h), crs, off = read_corners(sheet, src)
                note_how = src[sheet][3]
            elif args.auto:
                px, ground, mask, (w, h), crs, off = read_auto(sheet)
            else:
                if args.offcell and not sheet in OFFCELL:
                    raise ValueError("not offcell")
                px, ground, mask, (w, h), crs, off = read_pdf(sheet, M.local_pdf(files[sheet]), args.offcell)
            info = plain(f"{m['iiif_image']}/info.json")
            if args.hand and max(abs(info["width"] - w), abs(info["height"] - h)) <= 2:
                w, h = info["width"], info["height"]  # the detector's size is rounded from a 2000-px render
            if (info["width"], info["height"]) != (w, h):
                raise ValueError(f"size {w}x{h} but IIIF says {info['width']}x{info['height']}")
            mask_ground, resid = apply(px, ground, mask, order)
            rms = float(np.sqrt((metres(ground + resid, ground) ** 2).mean()))
            if (args.hand or args.auto) and rms > FIT_TOL_M:
                raise ValueError(f"corners are not a parallelogram: affine misses by {rms:.0f} m (a side snapped to the wrong line)")
            gap = None if (args.auto or args.hand or args.offcell) else outline_gap(mask_ground, sheet, manifest)
            if gap is not None and gap > OUTLINE_TOL_M:
                raise ValueError(f"outline {gap:.0f} m off the mosaic's")
        except (ValueError, RuntimeError, urllib.error.URLError, KeyError) as e:
            skipped.append((sheet, str(e)))
            continue
        if note_how and rms > 25:
            note_how += f"; corners are {rms:.0f} m off a parallelogram (bent scan or a corner off by a few px)"
        # The warped extent of the mask, as `oneoff/backfill_map_bbox.mjs` defines it. Without it a
        # sheet has no known place: zoom-to-overlay and `?map=` fall back to fetching the annotation,
        # which a draft only serves to a staff session.
        bbox = [round(float(v), 6) for v in (*mask_ground.min(0), *mask_ground.max(0))]
        out = OUT / f"{m['id']}.json"
        out.write_text(json.dumps(annotation(m["iiif_image"], w, h, px, ground, mask, order), indent=1))
        if args.offcell:
            dm = lambda v: f"{int(v)}d{(v % 1) * 60:05.2f}"
            crs = f"{crs} NW {dm(mask_ground[0][0])} {dm(mask_ground[0][1])} SE {dm(mask_ground[2][0])} {dm(mask_ground[2][1])}"
        note = f"{sheet}  {crs:<10} src {off:4.1f} m  fit {rms:4.1f} m  outline {'n/a' if gap is None else f'{gap:4.1f} m'}"
        if args.write and args.bbox_only:
            req(f"{base}/rest/v1/maps?id=eq.{m['id']}", key, "PATCH", {"bbox": bbox})
            note += f"  bbox {bbox}"
        elif args.write:
            url = f"{base}/storage/v1/object/{BUCKET}/{m['id']}.json"
            try:
                req(url, key, "POST", out.read_bytes(), extra={"x-upsert": "true"})
            except urllib.error.HTTPError as e:
                if e.code != 400:
                    raise
                req(url, key, "PUT", out.read_bytes(), extra={"x-upsert": "true"})
            req(f"{base}/rest/v1/maps?id=eq.{m['id']}", key, "PATCH",
                {"annotation_url": f"https://maparchive.vn/api/maps/{m['id']}/annotation",
                 "is_georeferenced": True, "bbox": bbox,
                 **({"extra_metadata": {**m["extra_metadata"], "georef_method": note_how}} if note_how else {})})
            note += "  uploaded"
        ok.append(note)
        print(note)

    print(f"\n{len(ok)} {'written' if args.write else 'ready'}, {len(skipped)} skipped")
    reasons = {}
    for s, why in skipped:
        reasons.setdefault(why.split(":")[0].split(" ")[0], []).append(s)
    for why, ss in sorted(reasons.items()):
        print(f"  {why}: {len(ss)}  {' '.join(ss[:12])}{' ...' if len(ss) > 12 else ''}")


if __name__ == "__main__":
    main()
