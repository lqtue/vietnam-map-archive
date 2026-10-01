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
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None   # 1898 is 242 Mpx, past PIL's 179 Mpx bomb limit
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


def verify(sheet: str) -> None:
    """Cut every window of `sheet` from its native.png and compare the RGB hash with crops.json. Hashes only."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    pin = json.loads((HERE / "native.json").read_text())[sheet]
    crops = json.loads((HERE / "crops.json").read_text())
    im = Image.open(HERE.parents[2] / pin["path"]).convert("RGB")
    bad = 0
    for w in json.loads((HERE / "windows.json").read_text())["windows"]:
        if w["sheet"] != sheet or f"{sheet}-{w['id']}" not in crops:   # windows added after the last export have no pin
            continue
        x, y, bw, bh = w["box"]
        ok = hashlib.sha256(im.crop((x, y, x + bw, y + bh)).tobytes()).hexdigest() == crops[f"{sheet}-{w['id']}"]["rgb_sha256"]
        bad += not ok
    print(sheet, "windows identical" if not bad else f"{bad} windows DIFFER")


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
    if sys.argv[1:2] == ["--full"]:
        full(sys.argv[2])
    elif sys.argv[1:2] == ["--verify"]:
        verify(sys.argv[2])
    else:
        main()
