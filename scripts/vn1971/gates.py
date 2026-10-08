"""gates.py [NN ...]: the automatic gates on each 1971 sheet; exits 1 when any sheet is flagged.

1. per-zone affine residual of the GCPs (px -> printed grid, metres): max <= 15 m (~2 px at 1:200k)
2. grid step within 2% of the scale-predicted step (the 24 east strip failed this one)
3. the neatline mask covers > 0.25 of the image and holds >= 90% of the GCPs
4. the province's centre falls inside the GCP extent plus the 0.45-cell margin the mask adds
Centres are approximate (a town in the province, to 0.1 deg): a miss flags the sheet for a
person to look at, it does not say the sheet is wrong."""
import json, sys, re, collections, numpy as np
from matplotlib.path import Path as Poly
from common import WORK, snap, ZONES, _inv

CENTRES = {  # lon, lat
 '01': (105.4, 10.4), '02': (105.1, 9.0), '03': (105.95, 9.6), '04': (105.7, 9.3), '05': (107.0, 10.95),
 '06': (106.65, 11.0), '07': (108.9, 14.0), '08': (106.6, 11.7), '09': (107.7, 10.9), '10': (108.1, 11.1),
 '11': (105.1, 10.7), '12': (105.5, 9.8), '13': (108.0, 12.7), '14': (106.25, 10.4), '15': (106.65, 10.35),
 '16': (106.7, 10.8), '17': (106.4, 11.0), '18': (105.0, 10.0), '19': (106.4, 10.1), '20': (105.7, 10.5),
 '21': (105.95, 10.75), '22': (108.0, 14.4), '23': (109.0, 12.3), '24': (107.8, 11.6), '25': (106.4, 10.55),
 '26': (107.3, 10.9), '27': (108.95, 11.6), '28': (108.0, 13.9), '29': (105.7, 10.0), '30': (108.3, 13.0),
 '31': (109.1, 13.1), '32': (107.0, 11.9), '33': (107.2, 10.55), '34': (107.7, 12.0), '35': (108.0, 15.6),
 '36': (108.8, 15.0), '37': (108.4, 15.5), '38': (107.0, 16.8), '39': (105.75, 10.3), '40': (106.2, 11.4),
 '41': (108.4, 11.8), '42': (107.6, 16.4), '43': (106.3, 9.8), '44': (105.95, 10.2)}
RES_MAX, STEP_TOL, MASK_MIN, GCP_IN = 15.0, 0.02, 0.25, 0.90

ids = {r['sheet_number']: r['id'] for r in json.load(open(WORK + 'maps.json'))}
scale = {}
for line in open(WORK + 'list.tsv'):
    j = json.loads(line.split('\t')[3])
    scale[j['sheet_number']] = int(re.sub(r'\D', '', j['scale'].split(':')[1]))  # '1:150.000' -> 150000


def check(n):
    ann = json.load(open(WORK + f'annotations/{ids[n]}.json'))['items'][0]
    feats = ann['body']['features']
    px = np.array([f['properties']['resourceCoords'] for f in feats])
    ll = np.array([f['geometry']['coordinates'] for f in feats])
    sn = [snap(*p, tol_m=1.0) for p in ll]
    assert all(sn), f'{n}: a GCP is off the round grid, run fix_gcps.py'
    per_zone, steps = [], []
    for z in sorted({s[0] for s in sn}):
        i = [k for k, s in enumerate(sn) if s[0] == z]
        if len(i) < 4:
            continue
        en = np.array([_inv[z].transform(*ll[k]) for k in i])  # metres, Helmert UTM
        A = np.c_[px[i], np.ones(len(i))]
        coef, *_ = np.linalg.lstsq(A, en, rcond=None)
        per_zone.append(np.hypot(*(A @ coef - en).T).max())
        steps.append(np.linalg.svd(coef[:2], compute_uv=False))  # metres per px, both axes
    res = max(per_zone)
    want = 10000 / (2354 * 100 / (scale[n] / 1000))  # metres per px at the scale's nominal 598 dpi
    got = np.concatenate(steps)
    step_err = max(abs(got / want - 1))
    w, h = (int(v) for v in re.search(r'width="(\d+)" height="(\d+)"', ann['target']['selector']['value']).groups())
    mask = np.array([[float(v) for v in p.split(',')] for p in
                     re.search(r'points="([^"]+)"', ann['target']['selector']['value']).group(1).split()])
    area = 0.5 * abs(np.dot(mask[:, 0], np.roll(mask[:, 1], -1)) - np.dot(mask[:, 1], np.roll(mask[:, 0], -1))) / (w * h)
    inside = Poly(mask).contains_points(px).mean()
    # ~0.45 cell is ~0.045 deg at the finest scale; use the larger 0.1 deg
    lo, hi = ll.min(0) - 0.1, ll.max(0) + 0.1
    cx = CENTRES[n]
    centre = lo[0] <= cx[0] <= hi[0] and lo[1] <= cx[1] <= hi[1]
    why = [m for ok, m in ((res <= RES_MAX, f'residual {res:.0f} m'), (step_err <= STEP_TOL, f'step {step_err:+.1%}'),
                           (area > MASK_MIN, f'mask {area:.2f}'), (inside >= GCP_IN, f'{inside:.0%} GCPs in mask'),
                           (centre, 'centre outside')) if not ok]
    return n, len(feats), res, step_err, area, inside, centre, why


if __name__ == '__main__':
    sheets = sys.argv[1:] or sorted(ids)
    bad = 0
    print('sheet gcps  res_m  step    mask  in   centre  flags')
    for n in sheets:
        n, k, res, se, area, inside, centre, why = check(n)
        bad += bool(why)
        print(f'{n}    {k:4d} {res:6.1f} {se:+6.1%} {area:5.2f} {inside:4.0%} {str(centre):6}  {"; ".join(why) or "pass"}')
    print(f'{bad} of {len(sheets)} flagged')
    sys.exit(1 if bad else 0)
