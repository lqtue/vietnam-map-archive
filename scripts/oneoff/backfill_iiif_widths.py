#!/usr/bin/env python3
"""Write the missing `full/<w>,/` derivatives for sheets that have none.

    source work/ocr/.venv/bin/activate
    python scripts/oneoff/backfill_iiif_widths.py --collection 'Indochine 1:25,000 — Tonkin & Thanh Hóa' --dry
    python scripts/oneoff/backfill_iiif_widths.py --collection 'Indochine 1:25,000 — Tonkin & Thanh Hóa'

The R2 worker renders nothing: it is a key lookup over what `vips dzsave` wrote,
then a proxy to the originating library read from `sources/<mapId>`. A sheet
mirrored before `tile_map.sh` grew its `full/800,` step, and uploaded from a
local file so it has no `sources/` entry either, therefore 404s **every**
width-addressed derivative, forever, with nothing behind the miss.

Measured on the Indochine 1:25,000 series, 2026-09-13: 62 of 62 sheets serve
`full/163,121/` (the ~160px thumbnail dzsave writes, and what `maps.thumbnail`
points at) and 404 `full/200,/`, `full/400,/`, `full/800,/`, every other size in
their own `info.json`, and `?force_proxy=1`. Their `info.json` still carries the
`sizes` array that the current `tile_map.sh` deletes, which is what dates them.

`atWidth()` rewrites the stored URL's size segment to a width-only form, so the
one derivative that exists is exactly the one nothing asks for. /catalog's list,
the /explore rail and FeaturedSheet each recover through their own error
handler, at the cost of two dead round trips per thumbnail; /catalog's grid did
not, and 56 published sheets were invisible there until MapCard learned the same
fallback.

The pixels come from the **tile pyramid**, not from a source image: these were
uploaded from local files that are not in the repo, and there is no upstream to
re-fetch. `fetch_crop_level0` already composes an arbitrary region out of level0
tiles — the same function OCR reads sheets through — so this script is a loop
around it, not a second assembler.

ponytail: writes 200/400/800 and nothing else. Those are the three `atWidth()`
callers ask for (48px rail, 96px table cell, 400px card, 800px OG image); the
1200 `FeaturedSheet` wants for its plate is deliberately absent, because no
sheet in this state is featured and `stepDown` covers it if one ever is.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work" / "ocr" / "scripts"))

from iiif_tiles import fetch_crop_level0, get_image_info  # noqa: E402

WIDTHS = (800, 400, 200)
BUCKET = "vma-tiles"


def maps_in_collection(collection: str) -> list[dict]:
    """Rows with an iiif_image, via the REST API — no supabase-py dependency."""
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    url = os.environ["PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    q = urllib.parse.urlencode(
        {
            "collection": f"eq.{collection}",
            "select": "id,name,status,iiif_image,thumbnail",
            "iiif_image": "not.is.null",
        }
    )
    req = urllib.request.Request(
        f"{url}/rest/v1/maps?{q}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    import json

    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


# The edge refuses `Python-urllib/3.x` with a 403, and `head_status` reads
# anything that is not a 200 as "this width is missing" — so with the default
# User-Agent this script reports every width of every sheet as absent, would
# rewrite them all, and would then fail its own verification the same way.
# Measured 2026-09-13: 31 of 31 L7014 and 62 of 62 Indochine sheets "missing"
# all three widths under urllib, 6 and 0 under curl.
UA = {"User-Agent": "vma-backfill/1.0 (+https://maparchive.vn)"}


def head_status(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:  # noqa: PERF203 - the 404 is the answer
        return e.code
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True)
    ap.add_argument("--dry", action="store_true", help="report, upload nothing")
    ap.add_argument(
        "--force",
        action="store_true",
        help="regenerate even where the width already serves",
    )
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = maps_in_collection(args.collection)
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} sheets in {args.collection!r}")

    todo, already, failed = [], 0, []
    for m in rows:
        base = (m["iiif_image"] or "").rstrip("/")
        missing = [
            w
            for w in WIDTHS
            if args.force or head_status(f"{base}/full/{w},/0/default.jpg") != 200
        ]
        if missing:
            todo.append((m, missing))
        else:
            already += 1
    print(f"need derivatives: {len(todo)} | already complete: {already}")
    for m, missing in todo[:5]:
        print(f"  {m['status']:<7} {m['name'][:30]:<31} missing {missing}")
    if len(todo) > 5:
        print(f"  … and {len(todo) - 5} more")

    if args.dry:
        print("\n--dry: nothing written")
        return 0

    written = 0
    for i, (m, missing) in enumerate(todo, 1):
        base = m["iiif_image"].rstrip("/")
        mid = m["id"]
        try:
            info = get_image_info(base)
            w, h = info["width"], info["height"]
            # One assembly at the widest size wanted; the rest are resizes of it,
            # so a 62-sheet run is 62 pyramid reads, not 186.
            img = fetch_crop_level0(base, 0, 0, w, h, max(missing))
        except Exception as e:  # a sheet whose pyramid is itself broken
            failed.append((m["name"], str(e)[:120]))
            print(f"[{i}/{len(todo)}] {m['name'][:40]}: FAILED {e}")
            continue

        with tempfile.TemporaryDirectory() as td:
            paths = []
            for width in missing:
                # Height-unbounded: `vips thumbnail`-style box fitting would cap
                # the other axis too, silently yielding a narrower image that is
                # still a valid JPEG. These sheets are landscape, so the box
                # would bite the width; a portrait sheet loses the height.
                scaled = img.resize(
                    (width, max(1, round(img.height * width / img.width)))
                )
                p = Path(td) / f"{width}.jpg"
                scaled.save(p, "JPEG", quality=88)
                paths.append((width, p))

            for width, p in paths:
                dest = f"r2:{BUCKET}/tiles/{mid}/full/{width},/0/default.jpg"
                r = subprocess.run(
                    ["rclone", "copyto", str(p), dest, "--s3-no-check-bucket"],
                    capture_output=True,
                    text=True,
                )
                if r.returncode != 0:
                    failed.append((m["name"], r.stderr.strip()[:120]))
                    print(f"[{i}/{len(todo)}] {m['name'][:40]}: rclone failed")
                    break
                written += 1
            else:
                print(
                    f"[{i}/{len(todo)}] {m['name'][:40]}: wrote {[w for w, _ in paths]}"
                )

    print(f"\nwrote {written} objects across {len(todo)} sheets")
    if failed:
        print(f"{len(failed)} failures:")
        for name, err in failed:
            print(f"  {name}: {err}")

    # Verify pixels, not the gate: re-ask the service for what we just claimed
    # to write. A publish that reports success and serves nothing is the failure
    # mode this whole script exists to clean up after.
    # A freshly written object is not instantly readable through the worker —
    # measured 2026-09-13, a key that rclone had already confirmed served 404 on
    # the next request and 200 a few seconds later. Verifying once, immediately,
    # reports a false failure on a run that worked; retrying is what makes the
    # check mean "this sheet is serving" rather than "this sheet was fast".
    print("\nverifying…")
    import time

    bad = 0
    for m, missing in todo:
        base = m["iiif_image"].rstrip("/")
        for w in missing:
            url = f"{base}/full/{w},/0/default.jpg"
            for attempt in range(5):
                if head_status(url) == 200:
                    break
                time.sleep(2 * (attempt + 1))
            else:
                print(f"  STILL 404 after retries: {m['name'][:40]} at {w}")
                bad += 1
    print("all requested widths serve" if not bad else f"{bad} widths still 404")
    return 1 if (failed or bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
