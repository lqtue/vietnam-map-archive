"""Read-only, no-spend ingest plan: layout -> body area -> density tiles -> est. calls/USD.

  ingest_plan.py --map-id 3a446d85 --map-id 0e02b9d9 [--tile-metres 1400]
No Gemini calls, no DB writes. Reads Supabase (anon ok) and public IIIF.
"""
import argparse, math, os
import requests
from iiif_tiles import auto_tile_overrides, compute_tile_densities, fetch_crop, get_iiif_base_from_supabase, get_image_info, tile_grid
from scale import DEFAULT_OVERLAP_RATIO, annotation_for_map, metres_per_pixel, tile_size_for

OVERVIEW_WIDTH = 2048  # same as ocr.py cmd_batch; do not lower (docs/pipelines.md)
TILES_PER_CALL = 4
USD_PER_CALL = (0.011, 0.018)  # measured 2026-10-05: $0.134/12 calls @700m, $0.089/5 calls @1400m
INDEX_USD = 0.25               # per ~384-name index pass


def rest(**params):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))
    k = os.environ["PUBLIC_SUPABASE_ANON_KEY"]
    r = requests.get(os.environ["PUBLIC_SUPABASE_URL"] + "/rest/v1/maps", params=params,
                     headers={"apikey": k, "Authorization": f"Bearer {k}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def resolve(prefix):
    rows = rest(select="id", limit=5000)
    hit = [r["id"] for r in rows if r["id"].startswith(prefix)]
    if len(hit) != 1:
        raise SystemExit(f"{prefix}: {len(hit)} matches")
    return hit[0]


def inside(t, r):  # tile centre in region [x,y,w,h]
    cx, cy = t[0] + t[2] / 2, t[1] + t[3] / 2
    return r[0] <= cx <= r[0] + r[2] and r[1] <= cy <= r[1] + r[3]


def plan(mid, tile_metres):
    m = rest(select="id,year,name,triage", id=f"eq.{mid}")[0]
    tri = m.get("triage") or {}
    regs = tri.get("regions") or []
    scouted = None
    sj = f"work/ocr/outputs/{mid}/runs/scout-eval-{mid[:8]}/scout.json"
    if not regs and os.path.exists(sj):  # a scout run made but not saved to triage
        import json
        regs, scouted = json.load(open(sj)).get("regions") or [], True
    base = get_iiif_base_from_supabase(mid)
    info = get_image_info(base)
    W, H = info["width"], info["height"]
    out = {"id": mid[:8], "year": m["year"], "name": (m["name"] or "")[:34], "size": f"{W}x{H}", "notes": []}
    main = next((r["bbox"] for r in regs if r["category"] == "main_map"), None)
    if regs:
        srcs = {r.get("source") for r in regs}
        out["notes"].append(f"layout {'from scout run (unsaved)' if scouted else 'saved'} ({len(regs)} regions, {'/'.join(sorted(map(str, srcs)))})")
    else:
        out["notes"].append("NO layout: +1 scout call (~$0.009, measured 2026-10-05)")
    if main:
        crop, cs = tuple(main), "main_map"
    elif tri.get("neatline"):
        crop, cs = tuple(int(v) for v in tri["neatline"]), "neatline"
    else:
        crop, cs = (0, 0, W, H), "whole sheet"
    excl = [r["bbox"] for r in regs if r["category"] in ("legend", "name_list")]
    ann = annotation_for_map(mid)
    fit = metres_per_pixel(ann) if ann else None
    if fit:
        tp = tile_size_for(fit.mean, crop[2], crop[3], target_metres=tile_metres)
        tile = tp.tile
        out["notes"].append(f"{fit.mean:.2f} m/px, tile {tile}px={tp.metres_per_tile:.0f}m")
    else:
        tile = 2400  # ground-agnostic fallback (comment in ocr.py: 2400/300 gate setting)
        out["notes"].append("NO georef: ground-agnostic tile 2400px")
    tiles = list(tile_grid(W, H, tile=tile, overlap=int(tile * DEFAULT_OVERLAP_RATIO), region=crop))
    keep = [t for t in tiles if not any(inside(t, e) for e in excl)]
    ov = fetch_crop(base, 0, 0, W, H, size=OVERVIEW_WIDTH)
    ov_ok = ov.size[0] >= OVERVIEW_WIDTH
    d = compute_tile_densities(ov, keep, W, H)
    pr = auto_tile_overrides(d)
    skip = sum(v == "skip" for v in pr.values())
    low = sum(v == "low_res" for v in pr.values())
    full = len(keep) - skip - low
    n = full + low
    calls_lo = math.ceil((full + low / 2) / TILES_PER_CALL)
    calls_hi = math.ceil(n / TILES_PER_CALL)
    idx = INDEX_USD if any(r["category"] in ("legend", "name_list") for r in regs) else 0
    out.update(body=f"{cs} {crop[2]}x{crop[3]}", legend_tiles=len(tiles) - len(keep), grid=len(tiles),
               skip=skip, low=low, full=full, empty_pct=round(100 * skip / max(len(keep), 1)),
               calls=f"{calls_lo}-{calls_hi}",
               usd=(round(calls_lo * USD_PER_CALL[0], 2), round(calls_hi * USD_PER_CALL[1] + idx, 2)))
    if not ov_ok:
        out["notes"].append(f"overview only {ov.size[0]}px (<2048): density unreliable")
    if idx:
        out["notes"].append(f"+${idx} index pass assumed (legend/name_list present)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--map-id", action="append", required=True, help="uuid or unique prefix")
    ap.add_argument("--tile-metres", type=float, default=1400)
    a = ap.parse_args()
    tot = [0.0, 0.0]
    for p in a.map_id:
        try:
            o = plan(resolve(p) if len(p) < 36 else p, a.tile_metres)
        except (Exception, SystemExit) as e:  # keep going on a bad sheet
            print(f"{p}: FAILED {type(e).__name__}: {e}")
            continue
        print(f"{o['id']} {o['year']} {o['name']} [{o['size']}]\n  body {o['body']}; grid {o['grid']} tiles, {o['legend_tiles']} in legend/name_list (excluded)"
              f"\n  tiles skip/low/full = {o['skip']}/{o['low']}/{o['full']} ({o['empty_pct']}% empty)"
              f"\n  ESTIMATE {o['calls']} calls, ${o['usd'][0]}-${o['usd'][1]}  | " + "; ".join(o["notes"]))
        tot[0] += o["usd"][0]; tot[1] += o["usd"][1]
    print(f"TOTAL ESTIMATE ${tot[0]:.2f}-${tot[1]:.2f} (assumes {TILES_PER_CALL} tiles/call, ${USD_PER_CALL[0]}-{USD_PER_CALL[1]}/call from 2 measured runs; low_res counted half in low case; estimates only)")
