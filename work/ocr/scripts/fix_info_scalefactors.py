#!/usr/bin/env python3
"""Drop scale factors from a stored info.json that the tile pyramid does not hold.

`vips dzsave --layout iiif3` advertises one more scale factor than it writes: the
top level is listed in `tiles[0].scaleFactors` but its single tile is never
emitted. A client that trusts the list requests that level, misses in R2, and the
worker proxies the request to the originating library — the silent dependency
this whole exercise is removing. `iiif_tiles.py` already works around it
("the top factor is often advertised and absent"); this fixes the cause.

A level's origin tile is the only one that must exist for the level to exist:
    0,0,{min(256*sf, W)},{min(256*sf, H)}/
so presence is one directory lookup per advertised factor, and the listing is
fetched once per map.

**Except for the level whose origin tile is the whole image**, which dzsave
files under `full/{ceil(W/sf)},{ceil(H/sf)}` and never under a `0,0,W,H` region.
Checking only the region spelling declares that level absent when it is present
and serving, and trims it — so 21 of the Indochine sheets advertised [1,2,4,8]
while `full/166,235` sat in the bucket answering 200. The renderer then clamps
to the level below and fetches a 2x2 grid where one tile would have done.

That mistake was pinned as correct in `self_check`, which asserted a
`0,0,10816,13523` directory dzsave does not write, and it is spelled a second
time in `scripts/tile_map.sh`. Two implementations of one check, with one blind
spot: change either and change both. Corrected 2026-09-14.

    python work/ocr/scripts/fix_info_scalefactors.py --dry-run
    python work/ocr/scripts/fix_info_scalefactors.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backfill_full800 import BUCKET, published_maps  # noqa: E402


def stored_info(map_id: str) -> dict | None:
    done = subprocess.run(
        ["rclone", "cat", f"{BUCKET}/tiles/{map_id}/info.json"],
        capture_output=True, text=True,
    )
    if done.returncode != 0 or not done.stdout.strip():
        return None
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return None


def stored_dirs(map_id: str) -> set[str]:
    done = subprocess.run(
        ["rclone", "lsf", "--dirs-only", f"{BUCKET}/tiles/{map_id}"],
        capture_output=True, text=True,
    )
    return {line.rstrip("/") for line in done.stdout.splitlines() if line.strip()}


def stored_full_sizes(map_id: str) -> set[str]:
    """The `w,h` names under `full/`, where dzsave files the whole-image level.

    Listed rather than inferred from `full/` merely existing: `tile_map.sh`
    writes `full/200,`, `full/400,` and `full/800,` thumbnails afterwards, so
    the directory is there on every map whether or not dzsave's overview is.
    """
    done = subprocess.run(
        ["rclone", "lsf", "--dirs-only", f"{BUCKET}/tiles/{map_id}/full"],
        capture_output=True, text=True,
    )
    return {line.rstrip("/") for line in done.stdout.splitlines() if line.strip()}


def present_factors(info: dict, dirs: set[str], full_sizes: set[str]) -> list[int]:
    """Those advertised factors whose origin tile actually exists.

    Two spellings, because dzsave uses two: a region for any level that still
    takes more than one tile, and `full/{w},{h}` for the level that does not.
    """
    w, h = info["width"], info["height"]
    factors = info.get("tiles", [{}])[0].get("scaleFactors", [])
    kept = []
    for sf in factors:
        span = 256 * sf
        if f"0,0,{min(span, w)},{min(span, h)}" in dirs:
            kept.append(sf)
        elif span >= w and span >= h and f"{-(-w // sf)},{-(-h // sf)}" in full_sizes:
            # The whole image fits one tile at this factor, so dzsave wrote it
            # as the `full/` overview. Sizes round up, per axis, independently.
            kept.append(sf)
    return kept


def write_info(map_id: str, info: dict) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "info.json"
        path.write_text(json.dumps(info, separators=(",", ":")))
        subprocess.run(
            ["rclone", "copyto", "--s3-no-check-bucket", str(path),
             f"{BUCKET}/tiles/{map_id}/info.json"],
            check=True, capture_output=True, text=True,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()

    maps = published_maps()
    if args.only:
        maps = [m for m in maps if m["id"] == args.only]

    fixed = ok = broken = 0
    for i, m in enumerate(maps, 1):
        mid, label = m["id"], f"{m.get('year') or '?'} {(m.get('name') or '')[:40]}"
        info = stored_info(mid)
        if not info:
            broken += 1
            print(f"[{i:2}/{len(maps)}] NO info.json           {label}")
            continue
        advertised = info.get("tiles", [{}])[0].get("scaleFactors", [])
        kept = present_factors(info, stored_dirs(mid), stored_full_sizes(mid))
        if kept == advertised:
            ok += 1
            print(f"[{i:2}/{len(maps)}] ok {advertised}  {label}")
            continue
        missing = [f for f in advertised if f not in kept]
        if not kept:
            broken += 1
            print(f"[{i:2}/{len(maps)}] REFUSING — no level found, leaving alone  {label}")
            continue
        print(f"[{i:2}/{len(maps)}] {'would fix' if args.dry_run else 'fixing'} "
              f"{advertised} -> {kept} (dropping {missing})  {label}")
        if not args.dry_run:
            info["tiles"][0]["scaleFactors"] = kept
            info.pop("sizes", None)  # worker recomputes these from the factors
            write_info(mid, info)
        fixed += 1

    print(f"\nfixed={fixed} already-correct={ok} skipped={broken}")
    return 0


def self_check() -> None:
    info = {"width": 10816, "height": 13523,
            "tiles": [{"scaleFactors": [1, 2, 4, 8, 16, 32, 64], "width": 256}]}
    dirs = {"0,0,256,256", "0,0,512,512", "0,0,1024,1024", "0,0,2048,2048",
            "0,0,4096,4096", "0,0,8192,8192"}
    assert present_factors(info, dirs, set()) == [1, 2, 4, 8, 16, 32]

    # sf 64 spans past the image (16384 > 13523), so its one tile is the whole
    # image and dzsave files it under `full/`, NOT as `0,0,10816,13523`. This
    # asserted the region spelling until 2026-09-14, which is what made the
    # trim look correct: 13523 / 64 = 211.3 -> 212, 10816 / 64 = 169 exactly.
    assert present_factors(info, dirs, {"169,212"}) == [1, 2, 4, 8, 16, 32, 64]
    assert present_factors(info, dirs, {"0,0,10816,13523"}) == [1, 2, 4, 8, 16, 32]

    # `full/` is there on every map — tile_map.sh writes 200,/400,/800,
    # thumbnails into it — so its mere presence must not keep a level.
    assert present_factors(info, dirs, {"200,", "400,", "800,"}) == [1, 2, 4, 8, 16, 32]

    # Real case: the Indochine portrait sheet that lost its top level. 2652x3753
    # at factor 16 is 166x235 (both round up), one tile, written as full/166,235.
    port = {"width": 2652, "height": 3753,
            "tiles": [{"scaleFactors": [1, 2, 4, 8, 16], "width": 256}]}
    pdirs = {"0,0,256,256", "0,0,512,512", "0,0,1024,1024", "0,0,2048,2048"}
    assert present_factors(port, pdirs, set()) == [1, 2, 4, 8]
    assert present_factors(port, pdirs, {"166,235"}) == [1, 2, 4, 8, 16]

    # A landscape sheet, same shape one level deeper: 4998x3780 at factor 32.
    land = {"width": 4998, "height": 3780,
            "tiles": [{"scaleFactors": [1, 2, 4, 8, 16, 32], "width": 256}]}
    ldirs = {"0,0,256,256", "0,0,512,512", "0,0,1024,1024", "0,0,2048,2048",
             "0,0,4096,3780"}
    assert present_factors(land, ldirs, {"157,119"}) == [1, 2, 4, 8, 16, 32]
    print("self-check ok")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        self_check()
    else:
        sys.exit(main())
