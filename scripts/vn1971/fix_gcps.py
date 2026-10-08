"""fix_gcps.py: recompute every stored GCP's lon/lat from its round 10 km grid value through
the explicit Helmert (common.to_lonlat). Pixels are untouched. Originals go to
work/vn1971/grid_before_datum/ once, so a second run changes nothing."""
import glob, json, os, shutil
from common import WORK, snap, to_lonlat

os.makedirs(WORK + 'grid_before_datum', exist_ok=True)
moved = n = unshifted = 0
for f in sorted(glob.glob(WORK + 'grid/gcp*.json')):
    pts = json.load(open(f))
    bak = WORK + 'grid_before_datum/' + os.path.basename(f)
    if not os.path.exists(bak):
        shutil.copy(f, bak)
    for p in pts:
        z, e, nn, shifted = snap(*p['lonlat'])
        new = list(to_lonlat(z, e, nn))
        n += 1
        unshifted += not shifted
        moved += abs(new[0] - p['lonlat'][0]) > 1e-9 or abs(new[1] - p['lonlat'][1]) > 1e-9
        p['lonlat'] = new
    json.dump(pts, open(f, 'w'))
print(f'{n} GCPs ({unshifted} were unshifted), {moved} changed')
