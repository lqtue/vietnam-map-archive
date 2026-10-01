"""Export native-pixel crops for every river reference window and pin their RGB hashes.

Run with work/ocr/.venv/bin/python. Writes crops/<sheet>-<id>.png (gitignored,
regenerable), crops.json (committed: box, tile count, RGB sha256), and creates
an empty traces/<sheet>-<id>.geojson where none exists.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "river_pair"))
from eda import fixed_tile_crop  # noqa: E402  raw-byte cache, see river_pair/README.md

EMPTY = {"type": "FeatureCollection", "reviewed": False, "features": []}


def main() -> None:
    spec = json.loads((HERE / "windows.json").read_text())
    (HERE / "crops").mkdir(exist_ok=True)
    (HERE / "traces").mkdir(exist_ok=True)
    out = {}
    for w in spec["windows"]:
        s = spec["sheets"][w["sheet"]]
        base = f"https://iiif.maparchive.vn/iiif/{s['map_id']}"
        crop, tiles = fixed_tile_crop(base, s["width"], s["height"], w["box"])
        name = f"{w['sheet']}-{w['id']}"
        assert crop.size == tuple(w["box"][2:]), (name, crop.size)
        crop.save(HERE / "crops" / f"{name}.png")
        out[name] = {"box": w["box"], "tiles": tiles, "rgb_sha256": hashlib.sha256(crop.tobytes()).hexdigest()}
        trace = HERE / "traces" / f"{name}.geojson"
        if not trace.exists():
            trace.write_text(json.dumps(EMPTY))
        print(name, crop.size, tiles)
    (HERE / "crops.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
