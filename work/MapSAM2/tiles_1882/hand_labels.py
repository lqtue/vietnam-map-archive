#!/usr/bin/env python
"""Which 1882 rows are hand-labelled, and where. Read-only (GETs).

  python hand_labels.py            # counts, per-window and per-tile overlap, out/review/hand_labels.png

Hand-labelled = every row with source != 'import' (volunteer, sam-corrected), plus any approved row.
An import row counts as edited only if it is no longer `needs_review`, has a `reviewed_at`, or its
source changed; `updated_at` cannot tell (a bulk update stamped every row, imported or not).
Rows inside a held-out window that is still unseen are counted but not drawn.
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, box as sbox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_tiles as E  # noqa: E402

COL = {"building": (0, 170, 0), "land_plot": (0, 80, 255), "road": (255, 140, 0), "waterway": (0, 200, 220)}


def main() -> None:
    from vma_core import iiif

    sys.path.insert(0, str(E.REF))
    import view

    cfg = json.loads(E.TILES_JSON.read_text())
    rows = E._get_all(
        f"footprints?map_id=eq.{cfg['map_id']}&select=id,pixel_polygon,feature_type,review_status,source,reviewed_at&order=id"
    )
    print(collections.Counter((r["source"], r["feature_type"], r["review_status"]) for r in rows))
    edited_imports = [r for r in rows if r["source"] == "import" and (r["review_status"] != "needs_review" or r["reviewed_at"])]
    print("import rows no longer needs_review / reviewed:", len(edited_imports))
    hand = [r for r in rows if r["source"] != "import" or r["review_status"] == "approved"]
    for r in hand:
        r["poly"] = Polygon(r["pixel_polygon"]).buffer(0)
    print("hand-labelled:", len(hand), dict(collections.Counter(r["feature_type"] for r in hand)))
    wins = [w for w in json.loads((E.REF / "windows.json").read_text())["windows"] if w["sheet"] == "1882"]

    def touching(b):
        s = sbox(b[0], b[1], b[0] + b[2], b[1] + b[3])
        return [r for r in hand if r["poly"].intersects(s)]

    for name, sel in (
        ("heldout unseen", lambda w: w["split"] == "heldout" and not w["seen"]),
        ("heldout seen", lambda w: w["split"] == "heldout" and w["seen"]),
        ("calibrate", lambda w: w["split"] != "heldout"),
    ):
        ids = {r["id"] for w in wins if sel(w) for r in touching(w["box"])}
        print(f"touch {name}: {len(ids)}")
    for t in cfg["reserved_test"] + cfg["tiles"]:
        print(t["id"], dict(collections.Counter(r["feature_type"] for r in touching(t["box"]))))

    scale = 8
    base = iiif.get_iiif_base_from_supabase(cfg["map_id"])
    w, h = cfg["image"]
    im = iiif.fetch_crop(base, 0, 0, w, h, size=w // scale, fit=True)
    pil = Image.fromarray(view.blank(np.array(im), "1882", scale))
    d = ImageDraw.Draw(pil)
    blind = view.blind_boxes("1882")
    for r in hand:
        b = r["poly"].bounds
        if any(b[0] < x + bw and x < b[2] and b[1] < y + bh and y < b[3] for x, y, bw, bh in blind):
            continue
        d.polygon([(x / scale, y / scale) for x, y in r["pixel_polygon"]], outline=COL[r["feature_type"]], width=2)
    for t in cfg["reserved_test"] + cfg["tiles"]:
        x, y, bw, bh = t["box"]
        d.rectangle([x / scale, y / scale, (x + bw) / scale, (y + bh) / scale], outline=(255, 0, 255), width=1)
        d.text((x / scale + 3, y / scale + 3), t["id"], fill=(255, 0, 255))
    out = E.DEFAULT_OUT / "review"
    out.mkdir(parents=True, exist_ok=True)
    pil.save(out / "hand_labels.png")


if __name__ == "__main__":
    main()
