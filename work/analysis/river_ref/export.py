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


def full(sheet: str) -> None:
    """Whole sheet at native, raw tile bytes, to work/ocr/outputs/<map_id>/native.png; sha pinned in native.json."""
    s = json.loads((HERE / "windows.json").read_text())["sheets"][sheet]
    base = f"https://iiif.maparchive.vn/iiif/{s['map_id']}"
    img, tiles = fixed_tile_crop(base, s["width"], s["height"], [0, 0, s["width"], s["height"]])
    out = HERE.parents[2] / "work" / "ocr" / "outputs" / s["map_id"] / "native.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, compress_level=1)
    pins = json.loads((HERE / "native.json").read_text()) if (HERE / "native.json").exists() else {}
    pins[sheet] = {"path": str(out.relative_to(HERE.parents[2])), "size": list(img.size), "tiles": tiles,
                   "rgb_sha256": hashlib.sha256(img.tobytes()).hexdigest()}
    (HERE / "native.json").write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n")
    print(sheet, pins[sheet])


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
    full(sys.argv[2]) if sys.argv[1:2] == ["--full"] else main()
