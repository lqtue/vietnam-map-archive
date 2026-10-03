"""Lookup of the raw-evidence score Q at source-pixel positions, per street direction."""
from common import *
from q_maps import to_rot, NK
from scipy.ndimage import map_coordinates, gaussian_filter
_maps = {}
_nan = None
def qmap(k, sigma=0):
    key = (k, sigma)
    if key not in _maps:
        a = np.load(SP / f'Q_{k:02d}.npy', mmap_mode='r')
        _maps[key] = np.asarray(a, np.float32) if not sigma else gaussian_filter(np.asarray(a, np.float32), sigma)
    return _maps[key]
def nanmask():
    global _nan
    if _nan is None: _nan = np.load(SP / 'nanmask_q.npy')
    return _nan
def bins(ang):
    return (np.round(ang / (180.0 / NK)).astype(int)) % NK
def qlook(x, y, ang, sigma=0, drop=()):
    """Q at (x,y) (source px) for street direction ang (deg, image axes). sigma smooths Q (quarter px)."""
    k0 = bins(ang); out = np.zeros(len(x), np.float32)
    # bin-k maps are in each bin's own frame; direction tolerance = max over the +-1 neighbouring bins
    for dk in (-1, 0, 1):
        k = (k0 + dk) % NK
        for kk in np.unique(k):
            m = k == kk
            r, c = to_rot(x[m], y[m], kk * 180.0 / NK)
            out[m] = np.maximum(out[m], map_coordinates(qmap(kk, sigma), [r, c], order=1, mode='constant', cval=0.0))
    nm = nanmask()
    bad = nm[np.clip((y / Q).astype(int), 0, HQ - 1), np.clip((x / Q).astype(int), 0, WQ - 1)]
    out[bad] = np.nan
    return out
def load_samples():
    d = np.load(SP / 'samples.npz', allow_pickle=True)
    return {k: d[k] for k in d.files}
