#!/usr/bin/env python3
"""Checks for the control-point readers in l7014_mosaic.py.

    python3 scripts/test_l7014_gcp.py

Three of these fail silently in production rather than raising, which is why
they are pinned here: a QGIS .points read without the y-flip warps the sheet
upside down and still succeeds, a transformation the annotation declares and
gdalwarp is never told about fits perfectly in the Allmaps Editor and lands
wrong in the archive, and a source-precedence slip quietly warps yesterday's
corners over today's approved ones.
"""

import importlib.util
import json
import math
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "l7014", Path(__file__).with_name("l7014_mosaic.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# One sheet corner, spelled the two ways the Allmaps GCP box accepts.
QGIS = ("#CRS: EPSG:4326\n"
        "mapX,mapY,sourceX,sourceY,enable,dX,dY,residual\n"
        "105.7458739,20.7512331,152.4,-194.2,1,0,0,0\n"
        "105.9958406,20.7512391,4407.2,-194.2,1,0,0,0\n"
        "105.9958474,20.5012619,4407.2,-4638.5,1,0,0,0\n")
GDAL = ("152.4 194.2 105.7458739 20.7512331\n"
        "4407.2 194.2 105.9958406 20.7512391\n"
        "4407.2 4638.5 105.9958474 20.5012619\n")


def test_text_formats_agree():
    q, g = m.parse_gcp_text(QGIS), m.parse_gcp_text(GDAL)
    assert q == g, f"{q} != {g}"
    assert q[0] == (152.4, 194.2, 105.7458739, 20.7512331), q[0]
    # The y-flip is the whole point: QGIS writes it negative, and a reader that
    # takes it at face value mirrors the sheet about its own top edge.
    assert all(p[1] > 0 for p in q), q


def test_header_decides_not_the_numbers():
    # Both columns are plausible pixels on a sheet this size, so a reader that
    # guesses by magnitude rather than by the header gets this backwards.
    rows = m.parse_gcp_text("4407.2 194.2 105.99 20.75\n")
    assert rows[0][:2] == (4407.2, 194.2), rows


def test_warp_flags():
    assert m.warp_flags({"type": "thinPlateSpline"})[0] == ["-tps"]
    assert m.warp_flags({"type": "polynomial", "options": {"order": 2}})[0] == ["-order", "2"]
    assert m.warp_flags(None)[0] == ["-order", "1"]
    for bad in ({"type": "helmert"}, {"type": "projective"},
                {"type": "polynomial", "options": {"order": 7}}):
        try:
            m.warp_flags(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} was approximated instead of refused")


def _anno(pts, transformation=None, mask=None):
    return {"type": "AnnotationPage", "items": [{
        "type": "Annotation",
        "target": {"selector": {"value": '<svg><polygon points="%s" /></svg>' %
                                " ".join(f"{x},{y}" for x, y in mask)}} if mask else {},
        "body": {"type": "FeatureCollection",
                 "transformation": transformation,
                 "features": [{"properties": {"resourceCoords": [px, py]},
                               "geometry": {"coordinates": [lon, lat]}}
                              for px, py, lon, lat in pts]}}]}


SQUARE = [(0, 0, 106.0, 10.1), (1000, 0, 106.1, 10.1),
          (1000, 1000, 106.1, 10.0), (0, 1000, 106.0, 10.0)]


def test_annotation_reader():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.json"
        p.write_text(json.dumps(_anno(SQUARE, {"type": "thinPlateSpline"},
                                      [(0, 0), (1000, 0), (1000, 1000)])))
        g = m.gcps_from_annotation(p)
        assert g["pts"] == [tuple(float(v) for v in q) for q in SQUARE], g["pts"]
        assert g["flags"] == ["-tps"], g["flags"]
        assert g["mask"] == [(0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0)], g["mask"]


def test_precedence():
    """Annotation over pins over .points — most recently human-approved wins."""
    pins = {"9999-1": {"pixels": {c: [1, 2] for c in m.CORNERS},
                       "ground": {c: [106.0, 10.0] for c in m.CORNERS}}}
    with tempfile.TemporaryDirectory() as d:
        m.GCP_DIR = Path(d)
        (m.GCP_DIR / "9999-1.points").write_text(GDAL)
        assert m.load_gcps("9999-1", {})["src"].endswith(".points")
        assert m.load_gcps("9999-1", pins)["src"] == "pins.json"
        (m.GCP_DIR / "9999-1.json").write_text(json.dumps(_anno(SQUARE)))
        g = m.load_gcps("9999-1", pins)
        assert g["src"] == "9999-1.json" and len(g["pts"]) == 4, g


def test_residuals_find_the_bad_point():
    # A 3x3 grid, exact affine: 9 points against 6 parameters, which is the
    # spread a misplaced click needs in order to stand out rather than be
    # absorbed into the fit. Four corners cannot do it -- with 8 observations
    # and 6 parameters every residual comes out equal, which is why the phase
    # only names a worst point when there are more than four.
    grid = [(px, py, 106.0 + px / 10000, 10.1 - py / 10000)
            for px in (0, 500, 1000) for py in (0, 500, 1000)]
    r, mpp = m.fit_residuals(grid, 1)
    assert r.max() < 0.5, r
    assert 10 < mpp < 15, mpp          # ~11 m/px for 1000 px over ~11 km

    # Drag one point 0.001 deg (~110 m) east and it becomes the worst by far.
    bad = list(grid)
    bad[4] = (500, 500, bad[4][2] + 0.001, bad[4][3])
    r, _ = m.fit_residuals(bad, 1)
    assert int(r.argmax()) == 4, r
    assert r.max() > 3 * r.mean(), r   # the threshold phase_residuals reports on


def test_order_2_does_not_rescue_a_misclick():
    # The diagnostic that tells the two faults apart: paper distortion is a
    # shape order 2 can follow, a misplaced click is not.
    grid = [(px, py, 106.0 + px / 10000, 10.1 - py / 10000)
            for px in (0, 500, 1000) for py in (0, 500, 1000)]
    grid[4] = (500, 500, grid[4][2] + 0.001, grid[4][3])
    r1, _ = m.fit_residuals(grid, 1)
    r2, _ = m.fit_residuals(grid, 2)
    assert r2.mean() > 0.5 * r1.mean(), (r1.mean(), r2.mean())
    assert int(r2.argmax()) == 4, r2


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
