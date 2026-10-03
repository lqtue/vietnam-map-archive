"""Apply the fitted field to every OSM way, write the warped GeoJSON, summary numbers and figures."""
from pipeline import *
from cv import d, P1, P0, ink
from scipy.ndimage import distance_transform_edt, binary_dilation
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
F = pickle.load(open(SP / 'field.pkl', 'rb')); v = F['v']; res = F['res']
aff = Warp(v[:2], v[2:].reshape(2, 2)); models = make_models(aff, res); grid = models['grid_s0.3']
# ---- trusted cells: evidence-accepted cells and their 8 neighbours
acc = set(res); trust = set()
for (cy, cx) in acc:
    for a in (-1, 0, 1):
        for b in (-1, 0, 1): trust.add((cy + a, cx + b))
acc_xy = np.array([r[0] for r in res.values()])
def field(x, y):
    """grid field inside trusted cells, similarity-only elsewhere"""
    dd = grid.disp(x, y); da = aff.disp(x, y)
    cy, cx = (y // CELL).astype(int), (x // CELL).astype(int)
    tr = np.array([(a, b) in trust for a, b in zip(cy, cx)])
    return np.where(tr[:, None], dd, da), tr
# ---- warp every way
g = json.load(open(STREETS)); feats = []
for f in g['features']:
    gm = f['geometry']; lines = [gm['coordinates']] if gm['type'] == 'LineString' else gm['coordinates']
    out = []
    for c in lines:
        c = np.array(c, float); dd, tr = field(c[:, 0], c[:, 1]); out.append((c + dd).round(1).tolist())
        trusted = float(tr.mean())
    feats.append(dict(type='Feature', properties=dict(f['properties'], trusted=round(trusted, 2)), geometry=dict(type='LineString' if len(out) == 1 else 'MultiLineString', coordinates=out[0] if len(out) == 1 else out)))
json.dump(dict(type='FeatureCollection', crs=g.get('crs'), note='OSM centrelines warped onto the 1882 plan, source pixels. Fitted on ink/paper evidence only (work/analysis/osm_warp). properties.trusted = share of vertices in evidence-supported cells; below ~0.5 the line is only similarity-corrected.', features=feats), open(HERE / 'streets_warped_1882.geojson', 'w'))
# ---- scores
ns = np.arange(len(d['x']))
dd, tr = field(d['x'], d['y']); xw = d['x'] + dd[:, 0]; yw = d['y'] + dd[:, 1]
def sc(x, y, m):
    i = np.where(m)[0]; P = Pre(x[i], y[i], d['ang'][i], 0); q = P.eval(np.zeros(len(i)), np.zeros(len(i)))
    xi = np.clip((x[i] / Q).astype(int), 0, WQ - 1); yi = np.clip((y[i] / Q).astype(int), 0, HQ - 1)
    return dict(n=int(len(i)), meanQ=float(q.mean()), hit=float((q > .3).mean()), ink=float(ink[yi, xi].mean()))
da = aff.disp(d['x'], d['y']); xa = d['x'] + da[:, 0]; ya = d['y'] + da[:, 1]
summ = {}
for name, m in (('all', np.ones(len(ns), bool)), ('trusted', tr)):
    summ[name] = dict(unwarped=sc(d['x'], d['y'], m), similarity=sc(xa, ya, m), grid=sc(xw, yw, m))
    print(name, json.dumps(summ[name]))
# ---- secondary: road.png agreement (circular risk; never used in the fit)
road = np.asarray(Image.open(OUT / 'river/road.png').convert('L')) > 0
for bx, by, bw, bh in BLIND: road[by:by + bh, bx:bx + bw] = False
def road_dist(x, y):
    xi = np.clip(np.round(x).astype(int), 0, WD - 1); yi = np.clip(np.round(y).astype(int), 0, H - 1)
    dist = np.full(len(x), 250., np.float32); T = 1200; M = 250
    for ty in range(0, H, T):
        for tx in range(0, WD, T):
            s = np.where((xi >= tx) & (xi < tx + T) & (yi >= ty) & (yi < ty + T))[0]
            if not len(s): continue
            y0, y1, x0, x1 = max(0, ty - M), min(H, ty + T + M), max(0, tx - M), min(WD, tx + T + M)
            sub = road[y0:y1, x0:x1]
            if not sub.any(): continue
            e = distance_transform_edt(~sub); dist[s] = np.minimum(e[yi[s] - y0, xi[s] - x0], M)
    return dist
roadres = {}
for name, m in (('all', np.ones(len(ns), bool)), ('trusted', tr)):
    for lab, (x, y) in (('unwarped', (d['x'], d['y'])), ('similarity', (xa, ya)), ('grid', (xw, yw))):
        ds = road_dist(x[m], y[m]); roadres[f'{name}/{lab}'] = dict(inside=float((ds == 0).mean()), median_px=float(np.median(ds)), le12=float((ds <= 12).mean()), n=int(m.sum()))
        print('road', name, lab, roadres[f'{name}/{lab}'])
# ---- drift field summary, over trusted cell centres
cc = np.array([[(b + .5) * CELL, (a + .5) * CELL] for a, b in sorted(trust)])
okc = np.array([(0 <= x < WD and 0 <= y < H) for x, y in cc]); cc = cc[okc]
D = grid.disp(cc[:, 0], cc[:, 1]); mag = np.hypot(*D.T)
vsim = aff.disp(cc[:, 0], cc[:, 1]); resid = D - vsim
# best similarity / affine to D itself
A = np.column_stack([np.ones(len(cc)), cc[:, 0] - C0[0], cc[:, 1] - C0[1]])
cf, *_ = np.linalg.lstsq(A, D, rcond=None); fitaff = A @ cf
ss = ((D - D.mean(0)) ** 2).sum()
drift = dict(n_cells=int(len(cc)), max_px=float(mag.max()), median_px=float(np.median(mag)), mean_dir_deg_img=float(np.degrees(np.arctan2(*D.mean(0)[::-1]))),
             max_m=float(mag.max() * MPP), median_m=float(np.median(mag) * MPP),
             sim_rotation_deg=float(np.degrees(np.arctan2(v[4], v[5] + 1))), sim_scale_pct=float(v[5] * 100),
             tps_residual_median_px=float(np.median(np.hypot(*resid.T))), tps_residual_max_px=float(np.hypot(*resid.T).max()),
             share_var_by_similarity=float(1 - ((D - vsim) ** 2).sum() / ss), share_var_by_affine_fit=float(1 - ((D - fitaff) ** 2).sum() / ss),
             dy_per_1000px_x=float(cf[1, 1] * 1000), affine_M=cf[1:].T.round(4).tolist())
print('drift', json.dumps(drift))
# ---- trusted share of the neatline (area), and of way length
nx, ny, nw, nh = neatline()
cells_in = [(a, b) for a in range(-(-H // CELL)) for b in range(-(-WD // CELL))]
area = 0; atr = 0
for a, b in cells_in:
    x0, y0 = max(b * CELL, nx), max(a * CELL, ny); x1, y1 = min((b + 1) * CELL, nx + nw), min((a + 1) * CELL, ny + nh)
    if x1 <= x0 or y1 <= y0: continue
    ar = (x1 - x0) * (y1 - y0); area += ar; atr += ar * ((a, b) in trust)
sv = np.load(SP / 'samples.npz', allow_pickle=True)
dd2, tr2 = field(sv['x'], sv['y']); nsv = sv['cls'] != 'service'
share = dict(neatline_area_trusted=atr / area, samples_trusted=float(tr2[nsv].mean()), accepted_cells=len(acc), trusted_cells=len(trust), km_samples_trusted_nonservice=float(tr2[nsv].sum() * STEP * MPP / 1000) if False else float(tr2[nsv].sum() * 8 * MPP / 1000))
# per-piece retention (way pieces whose warped Q hits)
Pq = Pre(sv['x'] + dd2[:, 0], sv['y'] + dd2[:, 1], sv['ang'], 0); qv = Pq.eval(np.zeros(len(sv['x'])), np.zeros(len(sv['x'])))
import collections
pc = sv['piece']; sm = collections.defaultdict(list)
for p_, q_ in zip(pc, qv): sm[p_].append(q_)
good = {p_ for p_, l in sm.items() if np.mean(l) >= 0.15 and len(l) >= 6}
share['pieces_with_signal'] = len(good) / len(sm); share['samples_in_signal_pieces_nonservice'] = float(np.mean([p_ in good for p_ in pc[nsv]]))
print('share', share)
json.dump(dict(scores=summ, road=roadres, drift=drift, share=share, affine=v.tolist()), open(HERE / 'summary.json', 'w'), indent=1)
pickle.dump(dict(trust=trust, acc=acc), open(SP / 'trust.pkl', 'wb'))
# ---- figures
fig, ax = plt.subplots(1, 2, figsize=(20, 8))
for a_, (title, vec) in zip(ax, (('total displacement (px, x5)', D), ('residual after similarity (px, x5)', resid))):
    a_.imshow(ink[::2, ::2], cmap='gray_r', alpha=.25, extent=(0, WQ * Q, HQ * Q, 0))
    for (cy_, cx_) in acc: a_.add_patch(plt.Rectangle((cx_ * CELL, cy_ * CELL), CELL, CELL, fc='none', ec='tab:green', lw=.6))
    a_.quiver(cc[:, 0], cc[:, 1], vec[:, 0], -vec[:, 1] * -1, np.hypot(*vec.T), angles='xy', scale_units='xy', scale=0.2, cmap='viridis', width=.002)
    for bx, by, bw, bh in BLIND: a_.add_patch(plt.Rectangle((bx, by), bw, bh, fc='k', alpha=.5))
    a_.set_xlim(0, WD); a_.set_ylim(H, 0); a_.set_aspect('equal'); a_.set_title(title + '; green = evidence-accepted cells, black = excluded windows')
plt.tight_layout(); plt.savefig(HERE / 'fig_drift_field.png', dpi=200); plt.close()
# overlay: unwarped vs warped on a seen window
from viz import crop
for name, box in (('west_dense', [2700, 3600, 1000, 1000]), ('dry_city_blocks', [4300, 3700, 900, 900])):
    try: im = crop(box)
    except SystemExit as e: print(e); continue
    fig, ax = plt.subplots(1, 2, figsize=(18, 9))
    for a_, (lab, X, Y) in zip(ax, (('unwarped OSM', d['x'], d['y']), ('warped OSM', xw, yw))):
        a_.imshow(im, extent=(box[0], box[0] + box[2], box[1] + box[3], box[1]))
        m = (X > box[0]) & (X < box[0] + box[2]) & (Y > box[1]) & (Y < box[1] + box[3]); a_.plot(X[m], Y[m], 'r.', ms=2); a_.set_title(f'{name}: {lab}')
    plt.tight_layout(); plt.savefig(HERE / f'fig_overlay_{name}.png', dpi=200); plt.close()
