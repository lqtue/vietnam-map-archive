#!/usr/bin/env python3
"""Place-link items for the web review page: items.json -> review_items rows + the review_tasks row.

  review_items.py                 read build.py's items.json, write review-task.json and review-items.json beside it
  review_items.py --items F --out D --key place-link --seed 20261012 --blind-frac 0.2 --status open
  review_items.py --crops         also write the plain crops to D/crops/<item id>/{close,context}.png
  review_items.py --self-check    no network, no data files

The web page shows each view as an image at payload.views.<name>.url and draws the label box, markers, north
arrow and scale bar over it (src/lib/features/review). So the crops are plain: nothing the machine made is on
them, one image serves both arms. They have to be where the URLs point (--img-base, default IMG_BASE below):

  python3 review_items.py --crops
  rclone copy D/crops r2:vma-tiles/review/place-link --s3-no-check-bucket      # a production write: Tue runs it

Then send the items:  python3 work/review-kit/review_sync.py push review-task.json review-items.json
and read the web verdicts back:  python3 work/review-kit/review_sync.py pull place-link out/verdicts.jsonl

One row per label (docs/plans/review-page-plan.md section 3):
  item_id   ocr_labels.id, as in confirm.py's verdicts.jsonl
  bound     confirm.py's `item_bound` (what was judged: label, radius, the candidate list, plus the method), so a
            web verdict and an offline verdict on the same item are comparable and neither can approve new candidates
  payload   what BOTH arms see: the label as printed (text, px, box, lon/lat, names), the 300 m pool the
            reviewer searches, the sheet's scale and north (to draw the scale bar and arrow), and `views`: where
            each plain crop is (url) and where it sits on the sheet (x0, y0, side in source px, out in image px)
  proposal  the machine's up-to-3 candidates, in rank order (only the shown arm gets them); null when there are
            none, which is also what keeps such an item out of the blind arm
  gold      null (no practice answers yet)
The plain crops are made by --crops (write_crops); the page draws the label box, markers and outlines over them
from payload and proposal.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "work" / "review-kit"))
from confirm import MAP, OUT, VIEWS, Session, crop_box, item_bound, open_native, plain_crop  # noqa: E402

TASK_KEY = "place-link"
QUESTION = "What is this 1882 place today?"
QUESTION_VI = "Địa điểm năm 1882 này ngày nay là gì?"
PAYLOAD_KEYS = ("text", "category", "names", "px", "box", "pos_from", "lon", "lat")
# The plain crops are uploaded to the vma-tiles R2 bucket, which tiles.maparchive.vn serves (docs/guides/architecture.md).
IMG_BASE = "https://tiles.maparchive.vn/review/place-link"


def task_row(meta: dict, key: str = TASK_KEY, seed: int = 20261012, blind_frac: float = 0.2, status: str = "draft") -> dict:
    return {"key": key, "title": "Place links · 1882 Plan Cadastral", "question": QUESTION, "question_vi": QUESTION_VI,
            "method": meta["method"], "seed": seed, "blind_frac": blind_frac, "audience": "staff", "status": status}


def views_of(it: dict, img_base: str) -> dict:
    """Where each plain crop is and where it sits on the sheet (see confirm.crop_box); the page draws over it."""
    out = {}
    for name, (half, px, bar_m) in VIEWS.items():
        x0, y0, side = crop_box(it, name)
        out[name] = {"url": f"{img_base}/{it['id']}/{name}.png", "x0": x0, "y0": y0, "side": side, "out": px, "bar_m": bar_m}
    return out


def item_row(it: dict, meta: dict, img_base: str = IMG_BASE) -> dict:
    payload = {k: it.get(k) for k in PAYLOAD_KEYS}
    payload["pool"] = it["pool300"]
    payload["sheet"] = {"map_id": meta.get("map_id", MAP), "m_per_px": meta["m_per_px"], "north_px": meta["north_px"],
                        "size": meta.get("size"), "radius_m": meta["radius_m"]}
    payload["views"] = views_of(it, img_base)
    return {"item_id": it["id"], "bound": item_bound(it, meta), "payload": payload,
            "proposal": it["cands"] or None, "gold": None, "active": True}


def convert(doc: dict, img_base: str = IMG_BASE, **task_kw) -> tuple[dict, list[dict]]:
    return task_row(doc["meta"], **task_kw), [item_row(it, doc["meta"], img_base) for it in doc["items"]]


def write_crops(doc: dict, im, out: Path) -> int:
    """One plain PNG per item and view: out/<item id>/close.png, context.png. Nothing machine-made is on them."""
    n = 0
    for it in doc["items"]:
        d = out / it["id"]
        d.mkdir(parents=True, exist_ok=True)
        for name in VIEWS:
            plain_crop(im, it, name).save(d / f"{name}.png", optimize=True)
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", default=str(OUT / "items.json"))
    ap.add_argument("--out", default=None, help="default: beside --items")
    ap.add_argument("--key", default=TASK_KEY)
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--blind-frac", type=float, default=0.2)
    ap.add_argument("--status", default="draft", choices=["draft", "open", "closed"])
    ap.add_argument("--img-base", default=IMG_BASE, help="where the crops will be served from")
    ap.add_argument("--crops", action="store_true", help="also render the plain crops (reads native.png)")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    src = Path(a.items)
    if not src.exists():
        sys.exit(f"{src} missing: run build.py first")
    out = Path(a.out) if a.out else src.parent
    doc = json.loads(src.read_text())
    task, items = convert(doc, img_base=a.img_base, key=a.key, seed=a.seed, blind_frac=a.blind_frac, status=a.status)
    out.mkdir(parents=True, exist_ok=True)
    if a.crops:
        print(f"{write_crops(doc, open_native(), out / 'crops')} crops -> {out / 'crops'}")
    (out / "review-task.json").write_text(json.dumps(task, ensure_ascii=False, indent=1))
    (out / "review-items.json").write_text(json.dumps(items, ensure_ascii=False))
    print(f"{len(items)} items ({sum(1 for i in items if i['proposal']) } with a proposal) -> {out}\n"
          f"next: python3 work/review-kit/review_sync.py push {out / 'review-task.json'} {out / 'review-items.json'}")
    return 0


def self_check() -> int:
    from review_sync import read_push_files

    def cand(k):
        return {"id": f"osm:way/{k}", "name": f"Place {k}", "names": [f"Place {k}"], "source": "osm", "osm": f"way/{k}",
                "osm_alts": [], "wikidata": None, "tasco_ids": [], "lon": 106.7, "lat": 10.78, "dist_m": 10.0 * k, "score": 0.9,
                "shared": 2, "same_kind": True, "px": [300 + 50 * k, 300], "outline_px": [[280, 280], [400, 280], [400, 340]]}

    def item(i, n):
        return {"id": f"id{i}", "category": "institution", "text": f"LABEL {i}", "names": [f"LABEL {i}"], "px": [400.0, 300.0],
                "lon": 106.7, "lat": 10.78, "box": [330, 280, 150, 40], "pos_from": "box", "in_fit": False, "gcp_dist_m": 99,
                "cands": [cand(k) for k in range(1, n + 1)],
                "pool300": [{k: v for k, v in cand(k).items() if k not in ("score", "shared", "same_kind", "px", "outline_px")}
                            for k in range(1, 6)]}

    doc = {"meta": {"map_id": MAP, "radius_m": 150, "method": "name_today@test+place-link-v1", "m_per_px": 0.341,
                    "north_px": [1.0, 0.0], "size": [9000, 7000]},
           "items": [item(0, 3), item(1, 0), item(2, 2)]}
    task, rows = convert(doc)
    assert task["key"] == "place-link" and task["method"] == doc["meta"]["method"] and task["blind_frac"] == 0.2
    assert [r["item_id"] for r in rows] == ["id0", "id1", "id2"]

    # the bound is exactly what the offline page signs with, for every item
    with tempfile.TemporaryDirectory() as td:
        s = Session(doc, Path(td), "tester")
        for r, it in zip(rows, doc["items"]):
            assert r["bound"] == s.bound(it), "web and offline verdicts must share the bound"
        # and it moves with the candidates, so an old verdict cannot approve a new list
        moved = {**doc["items"][0], "cands": doc["items"][0]["cands"][:2]}
        assert item_bound(moved, doc["meta"]) != rows[0]["bound"]
        # the push files pass the same check review_sync applies before sending
        tp, ip = Path(td) / "t.json", Path(td) / "i.json"
        tp.write_text(json.dumps(task))
        ip.write_text(json.dumps(rows))
        assert read_push_files(tp, ip)[1] == rows

    # what both arms see carries nothing machine-made but the pool the reviewer may search
    seen = json.dumps(rows[0]["payload"], ensure_ascii=False)
    for machine in ('"score"', '"shared"', '"same_kind"', '"outline_px"', '"cands"', '"in_fit"', '"gcp_dist_m"'):
        assert machine not in seen, f"payload leaks {machine}"
    assert rows[0]["payload"]["pool"] == doc["items"][0]["pool300"] and rows[0]["payload"]["sheet"]["m_per_px"] == 0.341
    assert [c["id"] for c in rows[0]["proposal"]] == ["osm:way/1", "osm:way/2", "osm:way/3"], "candidates keep their rank"
    assert rows[1]["proposal"] is None, "an item without candidates has no proposal, so it is never blind"
    assert all(r["gold"] is None and r["active"] is True for r in rows)
    json.dumps(rows, ensure_ascii=False)

    # the views tell the page where each plain crop sits, in the numbers render() uses
    v = rows[0]["payload"]["views"]
    assert v["close"] == {"url": f"{IMG_BASE}/id0/close.png", "x0": 400 - 520, "y0": 300 - 520, "side": 1040, "out": 800, "bar_m": 50}
    assert v["context"]["side"] == 3600 and v["context"]["out"] == 900 and v["context"]["bar_m"] == 200
    assert convert(doc, img_base="https://x.test/c")[1][0]["payload"]["views"]["close"]["url"] == "https://x.test/c/id0/close.png"
    assert rows[0]["bound"] == item_bound(doc["items"][0], doc["meta"]), "views are not part of what was judged"

    # a plain crop is the sheet's own pixels at that box: nothing drawn, so the page's overlay is the only overlay
    from PIL import Image

    im = Image.new("RGB", (4000, 4000))
    im.putdata([((i % 4000) // 16 % 256, 0, 0) for i in range(4000 * 4000)])
    with tempfile.TemporaryDirectory() as td:
        small = {"items": [{**doc["items"][0], "px": [2000.0, 2000.0]}]}
        assert write_crops(small, im, Path(td)) == 2
        close = Image.open(Path(td) / "id0" / "close.png")
        assert close.size == (800, 800)
        x0 = 2000 - 520
        assert abs(close.getpixel((400, 400))[0] - (2000 // 16 % 256)) <= 2, "the crop is centred on the label"
        assert abs(close.getpixel((0, 400))[0] - ((x0 + 1) // 16 % 256)) <= 3, "and starts at x0"
    print("review_items self-check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
