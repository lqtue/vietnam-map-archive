"""Fast batched evaluation of Q for many per-sample displacements at once."""
from lib import *
from q_maps import rot_params
class Pre:
    """Per-sample, per-bin geometry for a set of samples (x,y,ang)."""
    def __init__(self, x, y, ang, sigma=0):
        self.x, self.y, self.ang, self.sigma = x, y, ang, sigma
        k0 = bins(ang); self.groups = []
        for dk in (-1, 0, 1):
            k = (k0 + dk) % NK
            for kk in np.unique(k):
                idx = np.where(k == kk)[0]
                r, c = to_rot(x[idx], y[idx], kk * 180.0 / NK)
                self.groups.append((kk, idx, r, c, rot_params(kk * 180.0 / NK)[0]))
    def eval(self, DX, DY):
        """DX, DY: (n,) or (n,S) displacement in source px. Returns (n,) or (n,S) Q at p+d."""
        DX = np.asarray(DX, float); DY = np.asarray(DY, float)
        scalar = DX.ndim == 1
        if scalar: DX, DY = DX[:, None], DY[:, None]
        n = len(self.x); S = max(DX.shape[1], DY.shape[1])
        out = np.zeros((n, S), np.float32)
        for kk, idx, r, c, R in self.groups:
            dX = np.broadcast_to(DX, (n, S))[idx]; dY = np.broadcast_to(DY, (n, S))[idx]
            rr = r[:, None] + (R[1, 0] * dX + R[1, 1] * dY) / Q
            cc = c[:, None] + (R[0, 0] * dX + R[0, 1] * dY) / Q
            v = map_coordinates(qmap(kk, self.sigma), [rr, cc], order=1, mode='constant', cval=0.0)
            out[idx] = np.maximum(out[idx], v)
        return out[:, 0] if scalar else out
