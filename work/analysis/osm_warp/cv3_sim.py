from pipeline import *
from cv import d, n, P1, P0, metrics, evaluate
g, cells = load_surfaces()
cy, cx = d['cy'], d['cx']
allc = sorted(cells)
schemes = {'checker': (lambda c: (c[0] + c[1]) % 2 == 0), 'halves_x': (lambda c: c[1] < 12)}
if __name__ == '__main__':
    out = {}
    for name, fn in schemes.items():
        A = [c for c in allc if fn(c)]; B = [c for c in allc if not fn(c)]
        for tr, te, lab in ((A, B, 'A->B'), (B, A, 'B->A')):
            print(name, lab, 'train cells', len(tr), flush=True)
            sc, kind, v, aff, res, models = fit_all(d, P1, P0, g, cells, tr, nseed=5, kinds=('sim',))
            tem = np.isin(cy * 1000 + cx, [c[0] * 1000 + c[1] for c in te])
            r = evaluate(models, tem); out[(name, lab)] = (r, kind, v)
            print(f' chosen {kind} t=({v[0]:.0f},{v[1]:.0f}) M={np.round(v[2:],4)}; test n={tem.sum()}')
            for k, vv in r.items(): print(f"   {k:11s} meanQ {vv['meanQ']:.4f} hit {vv['hit']*100:5.1f}% inkhit {vv['ink']*100:5.1f}%", flush=True)
    pickle.dump(out, open(SP / 'cv3_sim.pkl', 'wb'))
