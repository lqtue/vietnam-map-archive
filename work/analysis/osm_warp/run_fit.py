"""Fit on a set of cells, evaluate anywhere. python3 run_fit.py  -> cv results + final field (see cv.py)."""
from fit import *
import pickle, time
NMIN = 60          # samples in a cell to attempt a fit
SUP_MIN = 8        # samples (64 px of line) scoring Q>0.3 at the best shift to trust a cell
def load():
    s = load_samples(); ns = s['cls'] != 'service'
    d = {k: v[ns] for k, v in s.items()}
    d['cy'], d['cx'] = cell_ids(d['x'], d['y'])
    return d, s
def fit_model(d, P1, P0, train_mask, smooth=(1.0,), verbose=False):
    cells = sorted(set(zip(d['cy'][train_mask], d['cx'][train_mask])))
    cells = [c for c in cells if ((d['cy'] == c[0]) & (d['cx'] == c[1]) & train_mask).sum() >= NMIN]
    tr = np.where(train_mask)[0]
    tx, ty, th, gs, gm = rigid_search(P1.x[tr], P1.y[tr], P1.ang[tr], nsub=4000)
    thr = math.radians(th); Rm = np.array([[math.cos(thr) - 1, -math.sin(thr)], [math.sin(thr), math.cos(thr) - 1]])
    v0 = np.array([tx, ty, Rm[0, 0], Rm[0, 1], Rm[1, 0], Rm[1, 1]])
    if verbose: print('rigid init t', tx, ty, 'theta', th, 'score', round(gs, 4), 'median', round(gm, 4))
    rigid = Warp((tx, ty), Rm)
    rs = np.random.default_rng(2); sub = tr if len(tr) <= 9000 else np.sort(rs.choice(tr, 9000, replace=False))
    Ptr = Pre(P1.x[sub], P1.y[sub], P1.ang[sub], 2)
    aff2, sc2 = fit_affine(Ptr, np.arange(len(sub)), v0, 2)
    aff, sc = fit_affine(Ptr, np.arange(len(sub)), np.r_[aff2.t, aff2.M.ravel()], 1)
    models = {'rigid': rigid, 'affine': aff}
    info = dict(cells={}, reliable=[], rigid=(tx, ty, th, gs, gm), aff_score=sc)
    # residual per cell around the affine
    base = aff.disp(P1.x, P1.y)
    res = {}
    idxs = {c: np.where((d['cy'] == c[0]) & (d['cx'] == c[1]) & train_mask)[0] for c in cells}
    cens = {c: np.array([d['x'][idxs[c]].mean(), d['y'][idxs[c]].mean()]) for c in cells}
    for c in cells:
        idx = idxs[c]
        dx, dy, pk, md, _ = search(P1, idx, rng=64, step=4, base=base)
        dx, dy, pk, _m = refine(P1, idx, (dx, dy), base=base, rng=4, step=2)
        sub0 = Pre(P0.x[idx], P0.y[idx], P0.ang[idx], 0)
        sup = int((sub0.eval(base[idx, 0] + dx, base[idx, 1] + dy) > 0.3).sum())
        if sup >= SUP_MIN and pk > 2 * md:
            res[c] = (cens[c], np.array([dx, dy]), pk)
    rc = np.array([v[0] for v in res.values()]); rr = np.array([v[1] for v in res.values()])
    info['res'] = res; info['aff'] = aff
    for s in smooth:
        if len(rc) >= 6:
            tps = RBFInterpolator(rc / 1000, rr, kernel='thin_plate_spline', smoothing=s)
            f = lambda xy, tps=tps: np.clip(tps(xy / 1000), -64, 64)
        else: f = None
        models[f'grid_s{s:g}'] = Warp(aff.t, aff.M, f)
    info['res'] = res; info['aff'] = aff
    return models, info
