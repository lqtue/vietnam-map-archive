"""Shared by every vn1971 script: the work dir, and the one grid -> lon/lat conversion.

The atlas prints a UTM grid on Indian 1960. `go.py` used to call
`Transformer.from_crs("EPSG:3148", "EPSG:4326")` with no area hint; PROJ then picks a
different transformation per point, and 3,033 of 4,985 GCPs (61%) came out unshifted
(~490 m off) while the rest matched the Helmert to 12 m, often in the same sheet.
So the shift is spelled out (`INDIAN_1960_PROJ4`, from the L7014 pipeline, never looked up).
`python3 scripts/vn1971/common.py` is the self-check; `fix_gcps.py` repairs stored GCPs.
"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
from pyproj import Transformer
from l7014_mosaic import INDIAN_1960_PROJ4

WORK = os.path.normpath(os.path.join(HERE, '..', '..', 'work', 'vn1971')) + '/'
DATUM = 'Indian1960 towgs84=198,881,317'  # the --datum string georef_write.mjs records
ZONES = (48, 49)
_utm = lambda z, shift=INDIAN_1960_PROJ4: f'+proj=utm +zone={z} ' + shift
_fwd = {z: Transformer.from_crs(_utm(z), 'EPSG:4326', always_xy=True) for z in ZONES}
_inv = {z: Transformer.from_crs('EPSG:4326', _utm(z), always_xy=True) for z in ZONES}
# the same ellipsoid with no shift: what the old PROJ pick amounted to for the bad points
_inv0 = {z: Transformer.from_crs('EPSG:4326', _utm(z, '+a=6377276.345 +rf=300.8017 +no_defs'), always_xy=True) for z in ZONES}


def to_lonlat(zone, e_km, n_km):
    """Printed grid (km, zone 48/49) -> WGS84 lon/lat through the explicit Helmert."""
    return _fwd[zone].transform(e_km * 1000, n_km * 1000)


def snap(lon, lat, tol_m=20.0):
    """A stored GCP's lon/lat -> (zone, E km, N km, shifted) on the round 10 km grid, or None.
    `shifted` False means it was one of the unshifted points. The default 20 m takes in the
    old points that were shifted by another PROJ pipeline (up to 12 m off the Helmert) but
    nothing unshifted (~490 m); the self-check re-runs it at 1 m on repaired files."""
    for inv, shifted in ((_inv, True), (_inv0, False)):
        for z in ZONES:
            e, n = inv[z].transform(lon, lat)
            re, rn = round(e / 1e4) * 10, round(n / 1e4) * 10
            if abs(e - re * 1000) < tol_m and abs(n - rn * 1000) < tol_m:
                return z, re, rn, shifted
    return None


if __name__ == '__main__':
    # known point (the L7014 pipeline's own conversion of 500000,1100000, zone 48)
    lo, la = to_lonlat(48, 500, 1100)
    assert abs(lo - 104.99618) < 1e-5 and abs(la - 9.95397) < 1e-5, (lo, la)
    # round trip is exact to well under a metre, both zones
    for z, e, n in ((48, 740, 1790), (49, 230, 1620)):
        assert snap(*to_lonlat(z, e, n)) == (z, e, n, True)
    # an unshifted point resolves too, and is told apart (the shift is ~490 m, far over tol)
    t0 = Transformer.from_crs(_utm(48, '+a=6377276.345 +rf=300.8017 +no_defs'), 'EPSG:4326', always_xy=True)
    assert snap(*t0.transform(500000, 1100000)) == (48, 500, 1100, False)
    # nothing in the grid directory may sit more than 1 m from the Helmert of a round value
    pts = [p for f in glob.glob(WORK + 'grid/gcp*.json') for p in json.load(open(f))]
    off = [p for p in pts if (s := snap(*p['lonlat'], tol_m=1.0)) is None or not s[3]]
    print(f'{len(pts)} GCPs; {len(off)} not on the Helmert of a round 10 km value')
    assert not off, 'run scripts/vn1971/fix_gcps.py'
