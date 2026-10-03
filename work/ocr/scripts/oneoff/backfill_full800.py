#!/usr/bin/env python3
"""Store the `full/800,` derivative in R2 for every published map.

Why this exists: the R2 host renders nothing — it maps a IIIF path onto an R2
key and proxies anything it does not hold (see worker/src/index.ts). The only
`full/` size `tile_map.sh` writes is a ~200px thumbnail, so `full/800,` — the
size the share page's OG image asks for — has always fallen through to the
originating library. That is invisible until the library errors, which is
exactly what broke three sheets.

Fetching is `fetch_crop`, unchanged: it tries the region endpoint (a real 800px
render when the upstream is healthy) and falls back to assembling the pyramid we
already hold. Either way the bytes end up in R2 and the proxy is out of the loop.

One map at a time, on purpose. Parallel runs hammer the upstream we are trying
to stop depending on.

    python work/ocr/scripts/oneoff/backfill_full800.py --dry-run
    python work/ocr/scripts/oneoff/backfill_full800.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402
from iiif_tiles import fetch_crop, get_image_info  # noqa: E402

BUCKET = "r2:vma-tiles"
WIDTH = 800
REPO = Path(__file__).resolve().parents[4]


def r2_key(map_id: str) -> str:
    """The exact key the worker looks up for a `full/800,` request."""
    return f"tiles/{map_id}/full/{WIDTH},/0/default.jpg"


def env_from_dotenv() -> tuple[str, str]:
    url = key = ""
    for line in (REPO / ".env").read_text().splitlines():
        name, _, value = line.partition("=")
        value = value.strip().strip('"')
        if name.strip() == "PUBLIC_SUPABASE_URL":
            url = value
        elif name.strip() == "SUPABASE_SERVICE_KEY":
            key = value
    if not url or not key:
        sys.exit("Missing PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_KEY in .env")
    return url, key


def published_maps() -> list[dict]:
    url, key = env_from_dotenv()
    resp = requests.get(
        f"{url}/rest/v1/maps",
        params={"select": "id,name,year", "status": "in.(public,featured)"},
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def already_stored(map_id: str) -> bool:
    done = subprocess.run(
        ["rclone", "lsf", f"{BUCKET}/{r2_key(map_id)}"],
        capture_output=True, text=True,
    )
    return bool(done.stdout.strip())


def upload(local: Path, map_id: str) -> None:
    subprocess.run(
        ["rclone", "copyto", "--s3-no-check-bucket", str(local), f"{BUCKET}/{r2_key(map_id)}"],
        check=True, capture_output=True, text=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report what is missing, change nothing")
    ap.add_argument("--force", action="store_true", help="regenerate even if the key exists")
    ap.add_argument("--only", help="a single map id, for testing")
    args = ap.parse_args()

    maps = published_maps()
    if args.only:
        maps = [m for m in maps if m["id"] == args.only]
    print(f"{len(maps)} published map(s)")

    made = skipped = failed = 0
    for i, m in enumerate(maps, 1):
        mid, label = m["id"], f"{m.get('year') or '?'} {(m.get('name') or '')[:44]}"
        if not args.force and already_stored(mid):
            skipped += 1
            print(f"[{i:2}/{len(maps)}] skip (already stored)  {label}")
            continue
        if args.dry_run:
            made += 1
            print(f"[{i:2}/{len(maps)}] WOULD build           {label}")
            continue

        base = f"https://iiif.maparchive.vn/iiif/{mid}"
        try:
            info = get_image_info(base)
            img = fetch_crop(base, 0, 0, info["width"], info["height"],
                             size=WIDTH, quality=info.get("quality", "default"))
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "default.jpg"
                img.convert("RGB").save(out, format="JPEG", quality=88)
                upload(out, mid)
                kb = out.stat().st_size // 1024
            made += 1
            print(f"[{i:2}/{len(maps)}] built {img.width}x{img.height} {kb}KB  {label}")
        except Exception as e:  # noqa: BLE001 — one bad sheet must not stop the run
            failed += 1
            print(f"[{i:2}/{len(maps)}] FAILED {type(e).__name__}: {e}  {label}")

    print(f"\nbuilt={made} skipped={skipped} failed={failed}")
    return 1 if failed else 0


def self_check() -> None:
    assert r2_key("abc") == "tiles/abc/full/800,/0/default.jpg", r2_key("abc")
    print("self-check ok")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        self_check()
    else:
        sys.exit(main())
