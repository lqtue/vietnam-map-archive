"""Summarise scout-eval runs: sheet facts, layout, and agreement with human truth (read-only).

For every work/ocr/outputs/*/runs/scout-eval-*/scout.json:
  - metadata the scout read (title, scale, series, language)
  - region counts, body (main_map) share of the sheet, legend / name_list present
  - IoU of main_map against a human-set neatline (maps.triage.neatline_src = 'human'), where one exists
  - IoU per category against regions already saved for the sheet (stability of the model, not truth)
"""
import glob, json, os, urllib.request

U, K = os.environ["PUBLIC_SUPABASE_URL"], os.environ["PUBLIC_SUPABASE_ANON_KEY"]
maps = {m["id"]: m for m in json.load(urllib.request.urlopen(urllib.request.Request(
    U + "/rest/v1/maps?select=id,year,name,collection,triage&limit=2000", headers={"apikey": K})))}


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    i = max(0, x1 - x0) * max(0, y1 - y0)
    u = a[2] * a[3] + b[2] * b[3] - i
    return i / u if u else 0.0


for f in sorted(glob.glob("work/ocr/outputs/*/runs/scout-eval-*/scout.json")):
    d = json.load(open(f)); mid = d["map_id"]; m = maps.get(mid, {}); tri = m.get("triage") or {}
    regs = d.get("regions") or []; by = {}
    for r in regs: by.setdefault(r["category"], []).append(r["bbox"])
    sheet = (by.get("sheet") or [[0, 0, 1, 1]])[0]; main = (by.get("main_map") or [None])[0]
    md = d.get("metadata") or {}
    line = f"{mid[:8]} {m.get('year')} {(md.get('title') or m.get('name') or '')[:26]!r:30} scale {md.get('scale')} | regions {len(regs)}"
    if main: line += f" | body {main[2]*main[3]/(sheet[2]*sheet[3]):.0%}"
    line += f" | legend {'y' if 'legend' in by else 'n'} list {'y' if 'name_list' in by else 'n'}"
    if tri.get("neatline_src") == "human" and main and tri.get("neatline"):
        line += f" | main_map vs human neatline IoU {iou(main, tri['neatline']):.2f}"
    saved = {}
    for r in tri.get("regions") or []: saved.setdefault(r["category"], []).append(r["bbox"])
    st = [f"{c}:{max(iou(b, s) for s in saved[c] for b in bs):.2f}" for c, bs in by.items() if c in saved and c != "sheet"]
    if st: line += " | vs saved " + " ".join(st)
    print(line)
