from cv import *
import pickle
if __name__ == '__main__':
    allm = np.ones(n, bool)
    models, info = fit_model(d, P1, P0, allm, (0.3, 3.0, 30.0, 300.0), verbose=True)
    print('affine t', info['aff'].t, 'M', info['aff'].M)
    pickle.dump(dict(info={k: v for k, v in info.items() if k != 'cells'}, cells={c: {kk: vv for kk, vv in v.items() if kk != 'idx'} for c, v in info['cells'].items()}), open(SP / 'full_info.pkl', 'wb'))
    r = evaluate(models, allm)
    for k, v in r.items(): print(f"   {k:14s} meanQ {v['meanQ']:.4f} hit {v['hit']*100:5.1f}% inkhit {v['ink']*100:5.1f}%")
    # tps shifts at cell centres
    rc = np.array([v[0] for v in info['res'].values()]); rr = np.array([v[1] for v in info['res'].values()])
    print('residual cells', len(rc), 'residual |r| median', np.median(np.hypot(*rr.T)), 'max', np.hypot(*rr.T).max())
    for k in models:
        if k.startswith('grid'):
            t = models[k].tps(rc); print(k, 'tps at centres rms diff vs data', np.sqrt(((t - rr) ** 2).sum(1).mean()))
