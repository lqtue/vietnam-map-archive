"""Corner measurement for the thin-frame edition, for scripts/tonkin_georef.py `place`.

Same strips, same rim reader, same downstream gate. The one substitution: the
thick outer line is picked per patch as the strongest peak NEAR the rough frame
rather than the strongest peak in the whole strip, because on this edition the
graticule band and the rim are as dark as the frame and argmax flips between the
three along a side (measured: Quat Lam's left side scatters over 191/203/239/274).
Nothing else differs, and every check downstream is unchanged.
"""
import importlib.util, json, sys
import numpy as np
from pathlib import Path

spec = importlib.util.spec_from_file_location("tg", "scripts/tonkin_georef.py")
tg = importlib.util.module_from_spec(spec); spec.loader.exec_module(tg)

NEAR = 35   # the rough frame is this close; the band sits +49 and the rim +84


def rim_relaxed(p, thick):
    """`tg.rim_in` with the prominence floor lowered, for a faint rim only.

    Nothing else changes -- same blank-run landmark, same innermost peak, same
    centroid. On two sheets of this edition the inner rim line is 10 counts above
    its neighbours where the floor asks for 12, because the map content just
    inside is dark and that both raises the floor and eats the prominence. A
    measurement made this way is only accepted if it lands within 5 px of what the
    sheet's other sides measured unaided -- the rim offset is a printed constant.
    """
    hi = min(len(p), thick + tg.MAXIN)
    paper = float(np.percentile(p[thick:hi], 25))
    thr = paper + max(6.0, 0.06 * (float(p.max()) - paper))
    gap, run, start = None, 0, None
    for i in range(thick, hi):
        if p[i] < thr:
            start = i if run == 0 else start
            run += 1
        else:
            if run >= tg.MINGAP:
                gap = start + run
            run = 0
    if gap is None:
        return None
    lo, hi2 = gap, min(len(p), gap + tg.LIM)
    if hi2 - lo < 4:
        return None
    floor = max(5.0, 0.12 * (float(p[lo:hi2].max()) - paper))
    picked = []
    for j in range(max(1, lo), min(len(p) - 1, hi2)):
        if not (p[j] >= p[j - 1] and p[j] > p[j + 1]):
            continue
        u, v = max(0, j - 10), min(len(p), j + 11)
        if p[j] - max(p[u:j + 1].min(), p[j:v].min()) >= floor:
            picked.append(j)
    if not picked:
        return None
    j = picked[-1]
    u = v = j
    while u > 0 and p[u - 1] > thr and p[u - 1] <= p[u]:
        u -= 1
    while v < len(p) - 1 and p[v + 1] > thr and p[v + 1] <= p[v]:
        v += 1
    w = p[u:v + 1] - thr
    if w.sum() <= 0:
        return None
    return u + float((np.arange(len(w)) * w).sum() / w.sum())


def patches(d):
    n = d.shape[0]
    edges = np.linspace(0, n, tg.PATCHES + 1).round().astype(int)
    out = []
    for k in range(tg.PATCHES):
        lo, hi = edges[k], edges[k + 1]
        if hi - lo >= 8:
            out.append(((lo + hi) / 2.0, d[lo:hi].mean(axis=0)))
    return out


def side_line(d, ref, verbose=False):
    ps = patches(d)
    lo, hi = int(ref) - NEAR, int(ref) + NEAR
    consensus = lo + int(np.argmax(np.mean([p for _, p in ps], axis=0)[lo:hi]))
    pick = lambda prof, c, w: max(0, int(c - w)) + int(np.argmax(prof[max(0, int(c - w)):int(c + w) + 1]))
    pts = [(mid, float(pick(prof, consensus, 12))) for mid, prof in ps]
    f = tg.fit(pts)
    if f is None:
        return None, "would not fit"
    m, c, *_ = f
    pts = [(mid, float(pick(prof, m * mid + c, 8))) for mid, prof in ps]
    f = tg.fit(pts)
    m, c, res, keep, tot = f
    if verbose:
        print(f"      consensus {consensus}  peaks {[int(p[1]) for p in pts]}")
    if res > 3.0:
        return None, f"thick line residual {res:.1f}px"
    anchor = float(np.mean([mid for mid, _ in ps]))
    ref2 = m * anchor + c
    grid = np.arange(d.shape[1], dtype=float)
    avg = np.mean([np.interp(grid, grid + (ref2 - (m * mid + c)), prof) for mid, prof in ps], axis=0)
    r, how = tg.rim_in(avg, int(round(ref2)), "inner"), ""
    if r is None:
        r, how = rim_relaxed(avg, int(round(ref2))), " (relaxed floor)"
    if r is None:
        return None, "no rim found inside the thick line"
    return {"m": m, "c": c + (r - ref2), "res": res, "kept": keep, "found": tot,
            "offset": r - ref2, "how": how}, None


def measure(mid, verbose=True):
    base = f"https://iiif.maparchive.vn/iiif/{mid}"
    info = tg.T.get_image_info(base)
    W, H = info["width"], info["height"]
    frame = tg.rough_frame(base, W, H)
    lines, how = {}, {}
    for side in "LRTB":
        d, origin, step, a0 = tg.strip(base, side, frame, W, H)
        ref = (frame[side] - origin) * step
        got, err = side_line(d, ref, verbose)
        if err:
            return None, f"{side}: {err}", (W, H)
        how[side] = got.pop("how", "")
        m = got["m"] * step
        c = origin + step * (got["c"] - got["m"] * a0)
        midpt = (H if side in "LR" else W) * (tg.SPAN[0] + tg.SPAN[1]) / 2
        lines[side] = {"m": m, "c": c, "anchor": [midpt, m * midpt + c], "res": got["res"],
                       "kept": got["kept"], "found": got["found"], "offset": got["offset"]}
    tan = float(np.mean([lines["T"]["m"], lines["B"]["m"], -lines["L"]["m"], -lines["R"]["m"]]))
    for side in "LRTB":
        m = -tan if side in "LR" else tan
        ax, ay = lines[side]["anchor"]
        lines[side]["m"], lines[side]["c"] = m, ay - m * ax
        if verbose:
            print(f"    {side}: rim {lines[side]['offset']:5.1f}px inside the thick line  "
                  f"fit residual {lines[side]['res']:.2f}px  {lines[side]['kept']}/{lines[side]['found']} patches{how[side]}")
    solo = [lines[s2]["offset"] for s2 in "LRTB" if not how[s2]]
    for side in "LRTB":
        if how[side] and solo and abs(lines[side]["offset"] - float(np.median(solo))) > 5.0:
            return None, (f"{side}: relaxed rim {lines[side]['offset']:.1f}px is "
                          f"{lines[side]['offset'] - float(np.median(solo)):+.1f}px off "
                          f"the sides that measured unaided"), (W, H)

    def cross(v, hz):
        V, Hz = lines[v], lines[hz]
        y = (Hz["m"] * V["c"] + Hz["c"]) / (1.0 - Hz["m"] * V["m"])
        return [V["m"] * y + V["c"], y]

    corners = {k: cross(*ab) for k, ab in (("NW", ("L", "T")), ("NE", ("R", "T")),
                                           ("SE", ("R", "B")), ("SW", ("L", "B")))}
    return {"corners": corners, "lines": lines, "rotation": tan}, None, (W, H)


if __name__ == "__main__":
    mid = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else mid
    got, err, (W, H) = measure(mid)
    print(f"{name} {W}x{H}")
    if err:
        sys.exit(f"  measure failed: {err}")
    base = f"https://iiif.maparchive.vn/iiif/{mid}"
    got, err = tg.finish(base, W, H, got)
    if err:
        sys.exit(f"  finish failed: {err}")
    got["id"], got["name"] = mid, name
    q = got["quad"]
    for k, v in got["wgs84"].items():
        print(f"  {k} {v[0]:10.5f} E {v[1]:9.5f} N")
    g = got["grades"]
    print(f"  printed NW {g['NW'][0]}g {g['NW'][1]}g  SE {g['SE'][0]}g {g['SE'][1]}g   read {got['read']}")
    mx, my = got["m_per_px"]
    print(f"  box {q['w']:.1f} x {q['h']:.1f} px  aspect {q['aspect']:.4f} (printed off by {got['aspect_err']*100:.2f}%)")
    print(f"  ground {mx:.4f} / {my:.4f} m/px  axes {got['scale_gap']*100:.2f}% apart  "
          f"rim spread {got['rim_spread']*100:.1f}%")
    print("  verdict: " + ("clear" if not got["verdict"] else "HOLD -- " + "; ".join(got["verdict"])))
    out = Path(f"/private/tmp/claude-501/-Users-airm1-Desktop-svelte-beta/3c595b1e-b94b-45a4-911f-08a21e2377d1/scratchpad/{mid}.json")
    out.write_text(json.dumps(got, indent=1))
    print(f"  -> {out}")
