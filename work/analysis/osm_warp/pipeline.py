"""fit_all: DE global affine candidates (on cached cell surfaces) -> per-cell residual search -> thin-plate field;
the candidate with the best TRAINING-cell score after the residual stage is kept."""
from gfit import *
from fit import Warp
SMOOTH = (0.03, 0.3, 3.0)
def sim_de(g, cells, cl, seed):
    cen = np.array([cells[c]['cen'] for c in cl]) - C0
    S = np.array([cells[c]['S'] for c in cl]); n = np.array([cells[c]['n'] for c in cl], float)
    kk = np.arange(len(cl), dtype=float); N = len(g)
    def f(par):
        t = par[:2]; M = np.array([[par[2], -par[3]], [par[3], par[2]]]); p = t + cen @ M.T
        ix = (p[:, 0] - g[0]) / 8; iy = (p[:, 1] - g[0]) / 8
        ok = (ix >= 0) & (ix <= N - 1) & (iy >= 0) & (iy <= N - 1)
        val = mc(S, [kk, np.clip(iy, 0, N - 1), np.clip(ix, 0, N - 1)], order=1)
        return -float((n * val * ok).sum() / n.sum())
    r = differential_evolution(f, [(-200, 200)] * 2 + [(-0.03, 0.03)] * 2, seed=seed, popsize=60, maxiter=500, tol=1e-10, polish=False)
    p = r.x; return np.array([p[0], p[1], p[2], -p[3], p[3], p[2]]), -r.fun
def candidates(g, cells, cl, nseed=6, kinds=('sim', 'aff')):
    out = []
    for sd in range(nseed):
        if 'sim' in kinds: out.append(('sim', sim_de(g, cells, cl, sd)))
        if 'aff' in kinds: out.append(('aff', affine_de(g, cells, cl, seed=sd)))
    uniq = []
    for kind, (v, s) in out:
        if not any(np.abs(v[:2] - u[1][:2]).max() < 6 and np.abs(v[2:] - u[1][2:]).max() < 1.5e-3 for u in uniq): uniq.append((kind, v, s))
    return uniq
def residual_stage(d, P1, P0, v, cell_ids_train, rng=56, step=4, supmin=8):
    aff = Warp(v[:2], v[2:].reshape(2, 2)); base = aff.disp(d['x'], d['y'])
    res = {}
    for c in cell_ids_train:
        idx = np.where((d['cy'] == c[0]) & (d['cx'] == c[1]))[0]
        dx, dy, pk, md, _ = search(P1, idx, rng=rng, step=step, base=base)
        dx, dy, pk, _m = refine(P1, idx, (dx, dy), base=base, rng=4, step=2)
        sub0 = Pre(d['x'][idx], d['y'][idx], d['ang'][idx], 0)
        sup = int((sub0.eval(base[idx, 0] + dx, base[idx, 1] + dy) > 0.3).sum())
        if sup >= supmin and pk > 2 * md: res[c] = (np.array([d['x'][idx].mean(), d['y'][idx].mean()]), np.array([dx, dy]), pk, sup)
    return aff, res
def make_models(aff, res, smooth=SMOOTH):
    models = {'affine': aff}
    if len(res) >= 6:
        rc = np.array([v[0] for v in res.values()]); rr = np.array([v[1] for v in res.values()])
        for s in smooth:
            tps = RBFInterpolator(rc / 1000, rr, kernel='thin_plate_spline', smoothing=s)
            models[f'grid_s{s:g}'] = Warp(aff.t, aff.M, lambda xy, tps=tps: np.clip(tps(xy / 1000), -64, 64))
    return models
def train_score(d, models, tr_idx, key):
    x2, y2 = models[key].apply(d['x'][tr_idx], d['y'][tr_idx])
    P = Pre(x2, y2, d['ang'][tr_idx], 0); return float(P.eval(np.zeros(len(tr_idx)), np.zeros(len(tr_idx))).mean())
def fit_all(d, P1, P0, g, cells, train_cells, verbose=True, nseed=6, kinds=('sim', 'aff')):
    cl = [c for c in train_cells if c in cells]
    cands = candidates(g, cells, cl, nseed, kinds)
    tri = np.where(np.isin(d['cy'] * 1000 + d['cx'], [c[0] * 1000 + c[1] for c in cl]))[0]
    best = None
    for kind, v, s in cands:
        aff, res = residual_stage(d, P1, P0, v, cl)
        models = make_models(aff, res)
        key = 'grid_s0.3' if 'grid_s0.3' in models else 'affine'
        sc = train_score(d, models, tri, key)
        if verbose: print(f'  cand {kind} t=({v[0]:.0f},{v[1]:.0f}) M={np.round(v[2:],4)} DEscore {s:.4f} -> res cells {len(res)} train meanQ(grid) {sc:.4f}', flush=True)
        if best is None or sc > best[0]: best = (sc, kind, v, aff, res, models)
    return best
