"""Render the block/water layers of a `colour_blocks` run as review pictures.

Three of the last four findings on this track were made by looking at a crop,
not at a number: the missing administrative class, the river the blue test
could not find, the Arsenal's dockyard apron. `seg_eval` cannot see any of
them — every score it prints is recall-flavoured and indifferent to a false
positive — so these pictures are the only check the water work has ever had.
That makes the renderer part of the harness, not a throwaway, which is why it
now lives here instead of beside its own output.

    python work/ocr/scripts/review_figs.py --map-id <uuid> [--out DIR]

It mirrors `main()`'s order and must reproduce its counts exactly (798/203/43
default, 888/352/56 under --recut) — that agreement is the only reason to
trust the tints. It prints both, so a drift shows up as a wrong number rather
than as a wrong picture nobody checks.

Two runs, and every figure says which one it came from:

    A. default    --cream --drop-furniture --drop-water --drop-slivers
    B. + --recut  the same, plus --recut. Opt-in; 25 s -> 80 s.

Colours: orange = kept, blue outline = dropped, blue tint = the water region,
green tint = the land mask that bounds it.

The PNGs are ~3 MB each and stay out of git — the record is this script plus
the journal, not 164 MB of history.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import shapely
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import colour_blocks as cb  # noqa: E402

MAP = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"          # 1882 Plan Cadastral
IMG = ".tile_cache/ocr/full_c03b7f44a1d8d455c2b476d248651265.jpg"
RENDER = 6051

# Source-px windows, named for what each one is evidence of. 00-08 in the
# 2026-09-18 folder were cropped by hand from an earlier build and are not
# reproduced here; these four are the pair the Arsenal finding turns on.
WINDOWS = {
    "arsenal": (6450, 5830, 8250, 7630),
    "arroyo": (500, 2400, 2400, 4300),
}


def load(image: str, render: int):
    """(rgb, pil, scale) at `render` px wide, scale = source px per render px."""
    Image.MAX_IMAGE_PIXELS = None
    pil = Image.open(image).convert("RGB")
    source_w = pil.width
    pil = pil.resize((render, round(pil.height * render / pil.width)))
    rgb = np.asarray(pil, dtype=np.uint8)[..., :3]
    return rgb, pil, source_w / rgb.shape[1]


def splits(rgb: np.ndarray):
    """The three voted troughs, derived rather than read from a side-car.

    The Desktop copy of this script read them from a `splits.json` that was
    never written, so the folder could not rebuild itself. They cost ~8 s.
    """
    split, _, _ = cb.split_by_vote(rgb)
    green, _, _ = cb.split_by_vote(rgb, axis="green", ink_v=cb.INK_V)
    cool, _, _ = cb.split_by_vote(rgb, axis="cool", ink_v=cb.INK_V, rg_split=split)
    return split, cool, green


def pipeline(rgb, scale, *, split, cool, green, mpp, wet, furn, recut: bool):
    """main()'s order, with the full flag set. Returns (kept, drowned, slivers, all)."""
    px_area_m2 = (mpp * scale) ** 2
    feats, _ = cb.blocks_from_colour(rgb, split, scale, mpp=mpp, cool=cool, green=green,
                                     water=wet, recut=recut)
    ink_v, _ = cb.cream_ink(rgb, split, cool=cool, green=green, px_area_m2=px_area_m2,
                            min_area_m2=cb.MIN_AREA_M2, max_area_m2=cb.MAX_AREA_M2)
    cfeats, _ = cb.blocks_from_colour(rgb, split, scale, mpp=mpp, close=0, ink_v=ink_v,
                                      cool=cool, green=green, classes=("cream",))
    feats, _, _ = cb.subtract_blocks(feats + cfeats)
    if furn is not None and not furn.is_empty:
        feats = [f for f in feats if not shapely.centroid(f["geom"]).within(furn)]
    wm = cb.water_mask(feats, rgb, scale, wet)
    kept = [f for f, w in zip(feats, wm) if not w]
    drowned = [f for f, w in zip(feats, wm) if w]
    thin = cb.sliver_mask(kept)
    slivers = [f for f, t in zip(kept, thin) if t]
    kept = [f for f, t in zip(kept, thin) if not t]
    kept, *_ = cb.relabel_by_swatch(kept, rgb, scale, green=green, hatch=cb.HATCH_COHERENCE)
    return kept, drowned, slivers, feats


def region_masks(feats, rgb, scale, wet):
    """The water region and the land mask — the pass's own, not a copy."""
    full, land, _named = cb.water_region(feats, rgb, scale, wet)
    return full, land


def tint(base: Image.Image, mask, box, scale, colour, alpha):
    """Paint a render-px boolean mask over a source-px crop."""
    x0, y0, x1, y1 = box
    sub = mask[int(y0 / scale):int(y1 / scale), int(x0 / scale):int(x1 / scale)]
    layer = Image.fromarray((sub * 255).astype("uint8")).resize(base.size, Image.NEAREST)
    base.paste(Image.new("RGB", base.size, colour), (0, 0), layer.point(lambda p: alpha if p else 0))


def draw(pil, scale, box, out, *, water=None, land=None, kept=(), dropped=(),
         size=1500, width=2):
    x0, y0, x1, y1 = box
    im = pil.crop((int(x0 / scale), int(y0 / scale), int(x1 / scale), int(y1 / scale))).convert("RGB")
    im = im.resize((size, round(size * im.height / im.width)))
    if land is not None:
        tint(im, land, box, scale, (60, 190, 90), 70)
    if water is not None:
        tint(im, water, box, scale, (40, 90, 235), 90)
    dr = ImageDraw.Draw(im, "RGBA")
    k = size / (x1 - x0)
    for feats, colour in ((dropped, (30, 90, 255, 255)), (kept, (240, 110, 20, 255))):
        for f in feats:
            g = f["geom"]
            if g.bounds[2] < x0 or g.bounds[0] > x1 or g.bounds[3] < y0 or g.bounds[1] > y1:
                continue
            for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
                dr.line([((px - x0) * k, (py - y0) * k) for px, py in p.exterior.coords],
                        fill=colour, width=width)
    im.save(out)
    print(f"  {out.name}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map-id", default=MAP, help=f"maps.id UUID (default {MAP[:8]}, the 1882 sheet)")
    p.add_argument("--image", default=IMG, help="local sheet to render from (default the tile cache)")
    p.add_argument("--render", type=int, default=RENDER)
    p.add_argument("--out", type=Path, default=Path.home() / "Desktop" / "vma-colour-pass",
                   help="folder for the PNGs (default ~/Desktop/vma-colour-pass)")
    p.add_argument("--size", type=int, default=1200, help="output width in px")
    p.add_argument("--dropped", action="store_true",
                   help="also outline the polygons the run threw away. Off by default: on a "
                        "river window they are hundreds of ripple ribbons and they bury the "
                        "thing being checked. Turn them on to audit a drop, not to read a run")
    args = p.parse_args()

    if not Path(args.image).exists():
        print(f"no such image: {args.image} — run colour_blocks once to fill the tile cache",
              file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)

    rgb, pil, scale = load(args.image, args.render)
    split, cool, green = splits(rgb)
    print(f"splits: r-g {split:+.3f}  r-b {cool:+.3f}  green {green:+.3f}")

    import scale as scale_mod
    fit = scale_mod.metres_per_pixel(scale_mod.annotation_for_map(args.map_id))
    mpp = (fit.mx + fit.my) / 2.0
    wet = cb.water_points(args.map_id)
    furn = cb.furniture_mask(args.map_id)
    print(f"{mpp:.4f} m per source px, {len(wet)} hydrology labels")

    runs = {}
    for name, recut in (("default", False), ("recut", True)):
        kept, drowned, slivers, allf = pipeline(
            rgb, scale, split=split, cool=cool, green=green, mpp=mpp,
            wet=wet, furn=furn, recut=recut)
        print(f"{name:8s}: {len(kept)} kept, {len(drowned)} water, {len(slivers)} slivers")
        runs[name] = (kept, drowned, slivers, region_masks(allf, rgb, scale, wet))

    b_kept, b_drowned, b_slivers, (b_water, b_land) = runs["default"]
    r_kept, r_drowned, r_slivers, (r_water, r_land) = runs["recut"]
    if not args.dropped:
        b_drowned = b_slivers = r_drowned = r_slivers = []
    print(f"writing to {args.out}")
    draw(pil, scale, WINDOWS["arsenal"], args.out / "09_arsenal_yard_STILL_WRONG.png",
         water=b_water, land=b_land, kept=b_kept, dropped=b_drowned + b_slivers, size=args.size)
    draw(pil, scale, WINDOWS["arsenal"], args.out / "10_arsenal_yard_FIXED_recut.png",
         water=r_water, land=r_land, kept=r_kept, dropped=r_drowned + r_slivers, size=args.size)
    draw(pil, scale, WINDOWS["arsenal"], args.out / "11_arsenal_yard_the_block.png",
         kept=r_kept, size=args.size, width=5)
    draw(pil, scale, WINDOWS["arroyo"], args.out / "12_arroyo_chinois_named_is_water.png",
         water=r_water, land=r_land, kept=r_kept, dropped=r_drowned + r_slivers, size=args.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
