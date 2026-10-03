"""Build the raw-evidence 'street gap' score maps Q_k, one per street direction bin.

Signal (raw sheet evidence only; road.png is never read):
  ink   = wash.npz['ink'] (ink OD x255) > INK_THR, max-pooled to quarter res (4 src px).
          Ink inside every seen:false window (+8 px) is overwritten with a constant (the source pixels are never read), and Q within KERNEL_PAD of one is NaN.
  For a street running along direction phi, rotate so it is horizontal, then per pixel:
    kerb  = ink smoothed along the street over LK=48 px > KERB_FRAC=0.30   (a continuous line PARALLEL to the street;
            perpendicular parcel lines and lettering do not survive the smoothing)
    dL,dR = distance along the normal to the nearest kerb on each side
    free  = ink density in a (2*CORR+1) x LF box (49 x 120 src px) < FREE_MAX=0.012: no crossing parcel line, no lettering         (an empty paper corridor on the line itself)
    Q     = free * [CORR_MIN <= dL,dR <= WMAX] * exp(-((dL-dR)/(2*SIG))^2)   (kerbs both sides, centred between them)
  Water.png is used only to zero Q on water.
Q is stored in each direction's rotated frame (float16); osm samples are mapped into it by rot().
"""
import sys
from common import *
from scipy.ndimage import label, find_objects, uniform_filter1d, uniform_filter, affine_transform, maximum_filter, gaussian_filter
INK_THR = 40
LK = 48 // Q               # along-street smoothing for kerbs (quarter px)
LF = 120 // Q
KERB_FRAC = 0.30
CORR = 12 // Q             # half corridor, quarter px (12 src px = 4 m)
FREE_MAX = 0.0       # no ink pixel in the 2*CORR+1 px of normal; lines are 1-3 q px so any crossing breaks it
GLYPH = 100          # src px
RUN0, RUN1 = 250, 700  # src px: free-corridor run shorter than RUN0 scores 0 (parcel strips), longer than RUN1 scores 1 (streets)
CORR_MIN = 12 // Q
WMAX = 110 // Q            # largest half-gap (~37 m); wider gaps (river, squares) are not 'streets'
SIG = 20 / Q
NK = 36
def rot_params(phi_deg):
    """frame for direction phi: out(r,c) <- in = R (out - oc) + ic ; returns (R, ic, oc, out_shape)."""
    a = math.radians(phi_deg)
    # rotate image coords (x,y) so that direction (cos a, sin a) becomes +x
    ca, sa = math.cos(a), math.sin(a)
    R_fwd = np.array([[ca, sa], [-sa, ca]])         # (x,y)_rot = R_fwd (x,y)_in
    ic = np.array([WQ / 2, HQ / 2])
    corners = np.array([[0, 0], [WQ, 0], [0, HQ], [WQ, HQ]]) - ic
    rc = corners @ R_fwd.T
    wr = int(np.ceil(rc[:, 0].max() - rc[:, 0].min())) + 2
    hr = int(np.ceil(rc[:, 1].max() - rc[:, 1].min())) + 2
    oc = np.array([wr / 2, hr / 2])
    return R_fwd, ic, oc, (hr, wr)
def to_rot(x, y, phi_deg):
    """source px -> (row, col) in direction-phi frame (quarter-res pixel centres)."""
    R_fwd, ic, oc, shp = rot_params(phi_deg)
    p = np.column_stack([x / Q, y / Q]) - ic
    r = p @ R_fwd.T + oc
    return r[:, 1], r[:, 0]
def rotate_img(a, phi_deg, order=1):
    R_fwd, ic, oc, shp = rot_params(phi_deg)
    Rinv = R_fwd.T                                   # in = Rinv (out-oc) + ic, in (x,y)
    # affine_transform works in (row, col): in_rc = M out_rc + off
    M = np.array([[Rinv[1, 1], Rinv[1, 0]], [Rinv[0, 1], Rinv[0, 0]]])
    off = ic[::-1] - M @ oc[::-1]
    return affine_transform(a, M, offset=off, output_shape=shp, order=order, mode='constant', cval=0.0)
def nearest_dist(mask, axis, reverse):
    """distance (px) along axis to the next True at/after (reverse False) or at/before (reverse True)."""
    m = np.moveaxis(mask, axis, 1)
    n = m.shape[1]
    idx = np.arange(n)[None, :]
    if reverse:
        pos = np.where(m, idx, -10**6); pos = np.maximum.accumulate(pos, axis=1); d = idx - pos
    else:
        pos = np.where(m, idx, 10**6); pos = np.minimum.accumulate(pos[:, ::-1], axis=1)[:, ::-1]; d = pos - idx
    d = np.clip(d, 0, 10**4).astype(np.float32)
    return np.moveaxis(d, 1, axis)
def main():
    wz = np.load(OUT / 'features/wash.npz')
    ink = wz['ink'] > INK_THR                                  # half res
    h2, w2 = ink.shape
    pad = np.zeros((HQ * 2, WQ * 2), bool); pad[:h2, :w2] = ink[:HQ * 2, :WQ * 2]
    for bx, by, bw, bh in BLIND:                                # blank before any further computing
        pad[max(0, (by - BLIND_PAD_INK) // 2):(by + bh + BLIND_PAD_INK) // 2 + 1, max(0, (bx - BLIND_PAD_INK) // 2):(bx + bw + BLIND_PAD_INK) // 2 + 1] = True     # constant ink: never read, and it ends corridor runs at the box
    B = pad.reshape(HQ, 2, WQ, 2).max((1, 3))
    del pad, ink, wz
    # lettering, hatch specks and building glyphs are not geometry: drop connected ink components whose extent is < GLYPH src px
    lab, nl = label(B, structure=np.ones((3, 3), int))
    keep = np.zeros(nl + 1, bool)
    for i, sl in enumerate(find_objects(lab), 1):
        keep[i] = max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) * Q >= GLYPH
    B = keep[lab].astype(np.float32); del lab
    water = np.asarray(Image.open(OUT / 'river/water.png').convert('L'))[::Q, ::Q][:HQ, :WQ] > 0
    nanm = boxes_mask_q(KERNEL_PAD)
    np.save(SP / 'ink_q.npy', B)
    for k in range(NK):
        phi = k * 180.0 / NK
        Br = rotate_img(B, phi)
        K = uniform_filter1d(Br, LK, axis=1) > KERB_FRAC
        # drop kerb pixels' own thickness: a kerb is a run in the normal direction; keep as is
        dR = nearest_dist(K, 0, False); dL = nearest_dist(K, 0, True)
        # free paper corridor of half-width CORR across the street, then how far it runs along the street
        fr = uniform_filter1d(Br, 2 * CORR + 1, axis=0) <= FREE_MAX
        runl = nearest_dist(~fr, 1, False) + nearest_dist(~fr, 1, True)    # run length (q px) of the free corridor through each pixel
        runs = np.clip((runl * Q - RUN0) / (RUN1 - RUN0), 0, 1)
        gap = (dL >= CORR_MIN) & (dR >= CORR_MIN) & (dL <= WMAX) & (dR <= WMAX)
        Qr = fr * gap * runs * np.exp(-((dL - dR) / (2 * SIG)) ** 2)
        Qr = Qr.astype(np.float16)
        np.save(SP / f'Q_{k:02d}.npy', Qr)
        print(k, phi, Qr.shape, float(Qr.astype(np.float32).mean()), flush=True)
    np.save(SP / 'nanmask_q.npy', nanm); np.save(SP / 'water_q.npy', water)
if __name__ == '__main__':
    main()
