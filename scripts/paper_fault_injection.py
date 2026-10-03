#!/usr/bin/env python3
"""Fault-injection evaluation of the paper's Table 1.

    python3 scripts/paper_fault_injection.py            # writes docs/paper/fault-injection.json
    python3 scripts/paper_fault_injection.py --self-check

Table 1 says which checks can see which faults. That is argued from mechanism
plus one incident per cell. Here the faults are injected into the corrected
build, where the truth is known by construction, and the repo's own checks are
run unchanged: `graticule_error`, `lattice_error`, `pick_crs`
(scripts/l7014_mosaic.py) and the seam census (scripts/l7014_seams.py).

Caveat that bounds every result: "truth" is the adopted Helmert and the
lattice built from it. This measures what each check can DETECT relative to
that frame, not absolute accuracy. Thresholds are the code's own (5e-4 deg,
150 m) and the paper's 100 m seam cutoff, so a cell at the boundary is a fact
about the threshold, not the check.

PREDICTIONS -- written before the first run, graded by `grade()` below.
Only the ends of each range are predicted; the middle is reported, not scored.

  datum translation d (towgs84 scaled, same direction as the real fault)
    graticule_error      invariant (empty set) for every d
    lattice_error        silent d<=100, fires d>=300
    seam census f=1.0    silent for every d      (the stated limit, section 7.3)
    seam census f=.1/.5  silent d<=25, fires d>=300
  ellipsoid fallback (WGS 84 ellipsoid on the declared projection)
    graticule_error      fires      (phase_check already asserts this)
    lattice_error        fires
  misregistration e (the sheet's control displaced, frame correct)
    graticule_error      silent e<=25, fires e>=100
    lattice_error        silent e<=100, fires e>=300
    pick_crs             accepts e<=100, refuses e>=300
    seam census (1 sheet) silent e<=25, fires e>=300
  index entry wrong (sheet filed under a neighbouring cell)
    graticule_error      invariant (it never reads the index)
    lattice_error        fires
"""

import argparse
import json
import math
import random
import re
from pathlib import Path

import l7014_mosaic as m
import l7014_seams as s
from osgeo import gdal, osr

gdal.UseExceptions()
SEED = 20261001
SHEETS = 30
DATUM_D = (25, 50, 100, 150, 300, 455, 800)
FRACTIONS = (0.0, 0.1, 0.5, 1.0)
REPS = 5
SEAM_CUTOFF = 100.0
# the real fault's direction, from the 438.0 E/W and 133.7 N/S seam components
DIR = (0.9565, 0.2920)
OUT = Path("docs/paper/fault-injection.json")
ROWS = {r["sheet"]: r for r in m.load_sheets()}


class Shifted:
    """A dataset whose control points have moved; everything else is delegated."""

    def __init__(self, ds, dx, dy):
        self._ds = ds
        self._gcps = [gdal.GCP(g.GCPX + dx, g.GCPY + dy, g.GCPZ, g.GCPPixel, g.GCPLine)
                      for g in ds.GetGCPs()]

    def GetGCPs(self):
        return self._gcps

    def __getattr__(self, name):
        return getattr(self._ds, name)


def with_towgs84(srs, k, truth_proj4):
    out = osr.SpatialReference()
    out.ImportFromProj4(re.sub(r"\+towgs84=\S+", "+towgs84=" + ",".join(
        str(k * v) for v in (198, 881, 317)), truth_proj4))
    return out


def displacement(ds, truth, fault):
    g = ds.GetGCPs()[0]
    a = osr.CoordinateTransformation(truth, m.wgs84()).TransformPoint(g.GCPX, g.GCPY)[:2]
    b = osr.CoordinateTransformation(fault, m.wgs84()).TransformPoint(g.GCPX, g.GCPY)[:2]
    return m.ground_metres(a, b)


def pick(ds, meta, sheet):
    try:
        m.pick_crs(ds, meta, sheet)
        return 0.0
    except ValueError:
        return 1.0


def sheet_trials(sheet, cells):
    ds = gdal.Open(str(m.local_pdf(ROWS[sheet])))
    meta = m.xmp_fields(ds)
    if not ds.GetGCPs():
        return None
    declared, _ = m.sheet_crs(ds, meta)
    truth = m.indian_1960_utm(declared)
    if truth is None:
        return None
    base = {"grat": m.graticule_error(ds, truth, meta), "lat": m.lattice_error(ds, truth, sheet, cells)}
    if base["grat"] is None or base["lat"] is None or base["grat"] > m.GRATICULE_TOL or base["lat"] > 30:
        return None  # not a known-good baseline; do not inject into it
    truth_p4 = truth.ExportToProj4()
    rows = []
    d0 = displacement(ds, truth, with_towgs84(truth, 0.0, truth_p4))
    for d in DATUM_D:
        fault = with_towgs84(truth, 1 - d / d0, truth_p4)
        rows.append({"fault": "datum", "mag": d, "measured_m": displacement(ds, truth, fault),
                     "grat": m.graticule_error(ds, fault, meta),
                     "lat": m.lattice_error(ds, fault, sheet, cells)})
    wrong, _ = m.sheet_crs(ds, meta, force_epsg=4326)
    rows.append({"fault": "ellipsoid", "mag": None, "measured_m": displacement(ds, truth, wrong),
                 "grat": m.graticule_error(ds, wrong, meta),
                 "lat": m.lattice_error(ds, wrong, sheet, cells)})
    for e in DATUM_D:
        moved = Shifted(ds, e * DIR[0], e * DIR[1])
        rows.append({"fault": "misreg", "mag": e, "grat": m.graticule_error(moved, truth, meta),
                     "lat": m.lattice_error(moved, truth, sheet, cells),
                     "pick": pick(moved, meta, sheet)})
    # filed under the next cell along: same sheet, wrong index entry
    other = next((k for k in sorted(cells) if m.cell_of(k, cells) is not m.cell_of(sheet, cells)
                  and m.cell_corners(k, cells)
                  and m.ground_metres(m.cell_corners(k, cells)[0], m.cell_corners(sheet, cells)[0]) < 40000), None)
    rows.append({"fault": "index", "mag": None, "other": other, "grat": m.graticule_error(ds, truth, meta),
                 "lat": m.lattice_error(ds, truth, other, cells) if other else None})
    return {"sheet": sheet, "base": base, "trials": rows}


def shift_ring(ring, d):
    lat = sum(p[1] for p in ring) / len(ring)
    dx = d * DIR[0] / (111320.0 * math.cos(math.radians(lat)))
    dy = d * DIR[1] / 110540.0
    return [[x + dx, y + dy] for x, y in ring]


def moved(feature, d):
    """Every ring: a sheet's outline is a MultiPolygon with slivers, not one ring."""
    return dict(feature, geometry={"type": "MultiPolygon",
                                   "coordinates": [[shift_ring(r, d)] for r in s.rings(feature["geometry"])]})


def seam_trials(features, cells):
    pdfs = [f for f in features if f["properties"].get("kind") == "pdf"]
    rng = random.Random(SEED)
    out = []
    for f in FRACTIONS:
        for d in DATUM_D:
            reps = 1 if f in (0.0, 1.0) else REPS
            hits, counts, worst = 0, [], 0.0
            for _ in range(reps):
                chosen = {p["properties"]["sheet"] for p in rng.sample(pdfs, round(f * len(pdfs)))}
                feats = [moved(p, d) if p["properties"]["sheet"] in chosen else p for p in pdfs]
                rows = s.census(cells, feats)
                over = sum(r["median_m"] > SEAM_CUTOFF for r in rows)
                hits += over > 0
                counts.append(over)
                worst = max(worst, max(r["median_m"] for r in rows))
            out.append({"fraction": f, "mag": d, "reps": reps, "detected": hits / reps,
                        "seams_over_100": counts, "max_edge_median_m": worst})
    # one displaced sheet
    for e in DATUM_D:
        hits = 0
        for sheet in rng.sample(pdfs, REPS):
            name = sheet["properties"]["sheet"]
            feats = [moved(p, e) if p["properties"]["sheet"] == name else p for p in pdfs]
            hits += any(r["median_m"] > SEAM_CUTOFF for r in s.census(cells, feats))
        out.append({"fraction": "one sheet", "mag": e, "reps": REPS, "detected": hits / REPS})
    return out


def rate(trials, fault, key, pred):
    xs = [t for t in trials if t["fault"] == fault]
    return {t_mag: sum(pred(t[key]) for t in xs if t["mag"] == t_mag) / max(1, sum(t["mag"] == t_mag for t in xs))
            for t_mag in sorted({t["mag"] for t in xs if t["mag"] is not None})}


def grade(sheets, seam):
    """Compare observed cells with the predictions in the module docstring."""
    allt = [t for sh in sheets for t in sh["trials"]]
    fire_g = lambda v: v is not None and v > m.GRATICULE_TOL
    fire_l = lambda v: v is not None and v > m.LATTICE_TOL
    res = {"datum_graticule_invariant": max(abs(t["grat"] - sh["base"]["grat"])
                                            for sh in sheets for t in sh["trials"] if t["fault"] == "datum") < 1e-9,
           "datum_lattice_by_d": rate(allt, "datum", "lat", fire_l),
           "ellipsoid_graticule": sum(fire_g(t["grat"]) for t in allt if t["fault"] == "ellipsoid"),
           "ellipsoid_lattice": sum(fire_l(t["lat"]) for t in allt if t["fault"] == "ellipsoid"),
           "ellipsoid_trials": sum(t["fault"] == "ellipsoid" for t in allt),
           "misreg_graticule_by_e": rate(allt, "misreg", "grat", fire_g),
           "misreg_lattice_by_e": rate(allt, "misreg", "lat", fire_l),
           "misreg_pick_refuses_by_e": rate(allt, "misreg", "pick", lambda v: v == 1.0),
           "index_graticule_invariant": max(abs(t["grat"] - sh["base"]["grat"])
                                            for sh in sheets for t in sh["trials"] if t["fault"] == "index") < 1e-9,
           "index_lattice_fires": sum(fire_l(t["lat"]) for t in allt if t["fault"] == "index"),
           "seam_by_fraction": {str(r["fraction"]) + "/" + str(r["mag"]): r["detected"] for r in seam}}
    return res


def self_check():
    ring = [[106.0, 10.0], [106.1, 10.0], [106.1, 10.1], [106.0, 10.0]]
    assert abs(m.ground_metres(ring[0], shift_ring(ring, 470.0)[0]) - 470.0) < 1.0
    assert abs(DIR[0] ** 2 + DIR[1] ** 2 - 1) < 1e-3
    feature = {"type": "Feature", "properties": {"sheet": "x"}, "geometry": {
        "type": "MultiPolygon", "coordinates": [[ring], [ring]]}}
    assert len(s.rings(moved(feature, 25)["geometry"])) == 2
    print("self-check: ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--sheets", type=int, default=SHEETS)
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    cells = m.lattice_cells()
    manifest = json.loads((m.WORK / "build" / "l7014-fixed.geojson").read_text())["features"]
    names = sorted(f["properties"]["sheet"] for f in manifest if f["properties"].get("kind") == "pdf")
    rng = random.Random(SEED)
    sheets, skipped = [], 0
    for sheet in rng.sample(names, len(names)):
        if len(sheets) == args.sheets:
            break
        got = sheet_trials(sheet, cells)
        if got is None:
            skipped += 1
            continue
        sheets.append(got)
    seam = seam_trials(manifest, s.load_cells())
    out = {"seed": SEED, "sheets": [x["sheet"] for x in sheets], "skipped_baselines": skipped,
           "thresholds": {"graticule_deg": m.GRATICULE_TOL, "lattice_m": m.LATTICE_TOL,
                          "seam_m": SEAM_CUTOFF},
           "graded": grade(sheets, seam), "seam": seam}
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out["graded"], indent=1))


if __name__ == "__main__":
    main()
