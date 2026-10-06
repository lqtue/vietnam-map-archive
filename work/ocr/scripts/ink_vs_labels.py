"""Colour/ink text-amount estimate vs OCR labels, per grid cell (read-only; usage: ink_vs_labels.py <map-id>...). Truth is unvalidated until the sheets are edited — see .claude/handoff-ocr-ingest.md."""
import os, sys, json, urllib.request, collections
import numpy as np
from scipy import ndimage as ndi
from scipy.stats import spearmanr
sys.path.insert(0, "work/ocr/scripts")
from iiif_tiles import fetch_crop, get_image_info

U, K = os.environ["PUBLIC_SUPABASE_URL"], os.environ["PUBLIC_SUPABASE_ANON_KEY"]
SCR = os.path.join("work", "ocr", "outputs", "_ink-cache"); os.makedirs(SCR, exist_ok=True)  # overview PNGs; slow to refetch
OUT_W = 5000          # overview width of the neatline crop
CELL = 250            # overview px per grid cell (~ a 1/20 slice of the sheet)


def get(p):
    return json.load(urllib.request.urlopen(urllib.request.Request(U + "/rest/v1/" + p, headers={"apikey": K})))


def labels(mid, status):
    out, off = [], 0
    while True:
        r = get(f"ocr_labels?select=global_x,global_y,global_w,global_h,text,text_corrected&map_id=eq.{mid}"
                f"&review_status=in.({status})&limit=1000&offset={off}&order=id")
        out += r
        if len(r) < 1000:
            return out
        off += 1000


def ink_maps(img):
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    gray = rgb.mean(2)
    mx, mn = rgb.max(2), rgb.min(2)
    sat = (mx - mn) / np.maximum(mx, 1e-3)
    # black-hat: local paper level minus pixel, so aged/yellow paper and tint washes cancel
    bg = ndi.grey_closing(gray, size=(9, 9))
    bh = bg - gray
    ink = (bh > 0.18) & (sat < 0.45)         # dark, neutral → ink, not wash
    # shape filter: glyph-sized components only (drops neatline, hachure runs, contour lines)
    lab, n = ndi.label(ink)
    sl = ndi.find_objects(lab)
    keep = np.zeros(n + 1, bool)
    h = np.array([s[0].stop - s[0].start for s in sl]); w = np.array([s[1].stop - s[1].start for s in sl])
    keep[1:] = (h >= 3) & (h <= 30) & (w <= 30)
    glyph = keep[lab]
    cx = np.array([(s[1].start + s[1].stop) // 2 for s in sl]); cy = np.array([(s[0].start + s[0].stop) // 2 for s in sl])
    return gray, ink, glyph, cx[keep[1:]], cy[keep[1:]]


def cells(shape, f):
    H, W = shape
    return H // CELL, W // CELL


def run(mid):
    m = get(f"maps?select=name,year,iiif_image,triage&id=eq.{mid}")[0]
    nx, ny, nw, nh = m["triage"]["neatline"]
    cache = f"{SCR}/{mid[:8]}.png"
    from PIL import Image
    if os.path.exists(cache):
        img = Image.open(cache)
    else:
        img = fetch_crop(m["iiif_image"], nx, ny, nw, nh, size=OUT_W); img.save(cache)
    s = img.width / nw
    gray, ink, glyph, gx, gy = ink_maps(img)
    gh, gw = cells(gray.shape, CELL)
    def agg(a): return a[:gh * CELL, :gw * CELL].reshape(gh, CELL, gw, CELL).mean((1, 3))
    local_std = np.sqrt(np.maximum(ndi.uniform_filter(gray ** 2, 8) - ndi.uniform_filter(gray, 8) ** 2, 0))
    feats = {"std_density(existing)": agg(local_std > 25 / 255), "ink_frac": agg(ink), "glyph_ink_frac": agg(glyph)}
    cnt = np.zeros((gh, gw))
    for x, y in zip(gx, gy):
        if y // CELL < gh and x // CELL < gw: cnt[y // CELL, x // CELL] += 1
    feats["glyph_count"] = cnt
    res = {}
    for status in ("validated", "validated,pending"):
        L = labels(mid, status)
        lc = np.zeros((gh, gw)); ch = np.zeros((gh, gw))
        for r in L:
            cxl = ((r["global_x"] + r["global_w"] / 2) - nx) * s; cyl = ((r["global_y"] + r["global_h"] / 2) - ny) * s
            i, j = int(cyl // CELL), int(cxl // CELL)
            if 0 <= i < gh and 0 <= j < gw:
                lc[i, j] += 1; ch[i, j] += len(r["text_corrected"] or r["text"] or "")
        res[status] = (len(L), lc, ch)
    print(f"\n{mid[:8]} {m['year']} {m['name'][:30]} grid {gh}x{gw}={gh*gw} cells")
    for status, (n, lc, ch) in res.items():
        print(f"  truth={status}: {n} labels, {int(ch.sum())} chars, {int((lc>0).sum())} cells with a label")
        for k, f in feats.items():
            rs_c = spearmanr(f.ravel(), ch.ravel())[0]
            print(f"    {k:24s} spearman vs chars {rs_c:+.2f}")
    return feats, res


if __name__ == "__main__":
    for mid in sys.argv[1:]:
        run(mid)
