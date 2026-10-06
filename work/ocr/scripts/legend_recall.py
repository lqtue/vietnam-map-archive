"""Score a body-OCR run against a sheet's staff-placed legend pins (read-only).

Each placed legend entry (px=x,y, plus more=x,y|x,y) is a human-fixed position
of a printed numeral. Recall = share of pins with an extraction near them
(`any`) and with the same bare number near them (`number`). Radius is in source
px; three are shown because the right one is a judgement.

  legend_recall.py --map-id <uuid> --run-dir <dir with all_extractions.json>
"""
import argparse, json, math, os, re, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--map-id", required=True)
ap.add_argument("--run-dir")
ap.add_argument("--db", action="store_true", help="score digit-only ocr_labels rows already in the database")
ap.add_argument("--run-id", help="with --db: only rows from this run_id")
ap.add_argument("--radii", default="40,80,160")
a = ap.parse_args()
U, K = os.environ["PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
req = urllib.request.Request(
    f"{U}/rest/v1/ocr_labels?select=notes&category=eq.legend_entry&review_status=neq.rejected"
    f"&map_id=eq.{a.map_id}&limit=2000", headers={"apikey": K, "Authorization": "Bearer " + K})
pins = []
for r in json.load(urllib.request.urlopen(req)):
    n = r["notes"] or ""
    num = re.search(r"\bn=(\d+)", n)
    px = re.search(r"\bpx=(-?[\d.]+),(-?[\d.]+)", n)
    if not (num and px):
        continue
    pts = [(float(px[1]), float(px[2]))]
    more = re.search(r"\bmore=([^;]+)", n)
    if more:
        pts += [tuple(map(float, p.split(","))) for p in more[1].split("|") if p.count(",") == 1]
    pins += [(int(num[1]), x, y) for x, y in pts]
if a.db:
    ex, o = [], 0
    while True:
        q = (f"{U}/rest/v1/ocr_labels?select=text,text_corrected,run_id,global_x,global_y,global_w,global_h"
             f"&map_id=eq.{a.map_id}&global_x=not.is.null&order=id&offset={o}&limit=1000"
             + (f"&run_id=eq.{a.run_id}" if a.run_id else ""))
        page = json.load(urllib.request.urlopen(urllib.request.Request(q, headers={"apikey": K, "Authorization": "Bearer " + K})))
        ex += [{"text": r["text_corrected"] or r["text"] or "", "global_bbox": [r["global_x"], r["global_y"], r["global_w"] or 0, r["global_h"] or 0]} for r in page]
        o += 1000
        if len(page) < 1000: break
else:
    d = json.load(open(os.path.join(a.run_dir, "all_extractions.json")))
    ex = d if isinstance(d, list) else d.get("extractions") or d.get("items") or []
cen = [(re.sub(r"\D", "", e["text"]) if re.fullmatch(r"\s*\d+\.?\s*", e["text"]) else "",
        e["global_bbox"][0] + e["global_bbox"][2] / 2, e["global_bbox"][1] + e["global_bbox"][3] / 2)
       for e in ex if e.get("global_bbox")]
print(f"{a.map_id[:8]}: {len(pins)} placed pins, {len(cen)} extractions")
for R in map(float, a.radii.split(",")):
    anyhit = sum(any(math.hypot(x - cx, y - cy) <= R for _, cx, cy in cen) for _, x, y in pins)
    numhit = sum(any(t == str(n) and math.hypot(x - cx, y - cy) <= R for t, cx, cy in cen) for n, x, y in pins)
    print(f"  radius {R:>4.0f}px  any {anyhit}/{len(pins)} = {anyhit/max(1,len(pins)):.3f}   "
          f"same number {numhit}/{len(pins)} = {numhit/max(1,len(pins)):.3f}")
