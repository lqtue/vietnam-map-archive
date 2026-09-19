"""Render the block/water layers of a `colour_blocks` run as review pictures.

Three of the last four findings on this track were made by looking at a crop,
not at a number: the missing administrative class, the river the blue test
could not find, the Arsenal's dockyard apron. `seg_eval` cannot see any of
them — every score it prints is recall-flavoured and indifferent to a false
positive — so these pictures are the only check the water work has ever had.
That makes the renderer part of the harness, not a throwaway, which is why it
now lives here instead of beside its own output.

    python work/ocr/scripts/review_figs.py --map-id <uuid> [--out DIR]

It mirrors `main()`'s order and must reproduce its counts exactly — that
agreement is the only reason to trust the tints. It prints both runs' counts,
so a drift shows up as a wrong number rather than as a wrong picture nobody
checks.

Two runs, and every figure says which one it came from:

    AFTER   the current default: --cream --drop-furniture --drop-water
            --drop-slivers --swatch-labels, and --recut. 888/352/56.
    BEFORE  the run as it shipped at 9a2fe561: --no-recut, and the wash cut
            with no minimum component size. 798/203/43.

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

# Source-px windows on the 12102 x 8982 sheet, each named for what it is
# evidence of. A window ending _BEFORE/_AFTER is rendered from both runs.
WINDOWS = [
    # (figure name, box, which runs, note)
    ("whole_sheet",        (0, 0, 12102, 8982),          ("after",),  "the run at a glance"),
    ("creek_khanh_hoi",    (630, 4050, 1830, 5100),      ("before", "after"),
     "Rach Cau Chong: the packed ripple the wash cut used to eat"),
    ("inlet_hoi_an",       (9300, 2650, 11100, 3750),    ("before", "after"),
     "the same defect on a tidal inlet"),
    ("arsenal_edge",       (6600, 6000, 8400, 7400),     ("before", "after"),
     "the water/land edge --recut fixes: quay, sheds, dockyard apron"),
    ("arroyo_chinois",     (1800, 4200, 3600, 5600),     ("after",),
     "the named-label rule: the arroyo is water for its whole length"),
    ("tam_hoi_shoreline",  (400, 6100, 1800, 7100),      ("after",),  "shoreline detail"),
    ("vinh_hoi",           (200, 2900, 1600, 3900),      ("after",),  "shoreline detail"),
    ("jardin_botanique",   (8100, 5850, 9300, 6750),     ("before", "after"),
     "the lake and stream are real; the BEFORE floods the stipple beds around them"),
    ("city_untouched",     (5700, 3300, 6900, 4200),     ("before", "after"),
     "TRAP: Place de la Cathedrale. The pair must be identical"),
    ("river_saigon",       (4200, 6100, 5400, 7000),     ("after",),  "the river the pass always had"),
]


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
    p.add_argument("--size", type=int, default=1400, help="output width in px")
    p.add_argument("--only", help="render only figures whose name contains this")
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

    # "before" is the run as it shipped at 9a2fe561: no re-cut, and the wash cut
    # with no minimum component size. Reproduced here rather than described, so
    # every pair in the folder is the same build arguing with itself.
    runs, counts = {}, {}
    wash_min = cb.WATER_WASH_MIN_PX
    try:
        for tag, recut, wash in (("after", True, wash_min), ("before", False, 0)):
            cb.WATER_WASH_MIN_PX = wash
            kept, drowned, slivers, allf = pipeline(
                rgb, scale, split=split, cool=cool, green=green, mpp=mpp,
                wet=wet, furn=furn, recut=recut)
            counts[tag] = (len(kept), len(drowned), len(slivers))
            runs[tag] = (kept, drowned, slivers, region_masks(allf, rgb, scale, wet))
            print(f"{tag:6s}: {len(kept)} kept, {len(drowned)} water, {len(slivers)} slivers")
    finally:
        cb.WATER_WASH_MIN_PX = wash_min

    print(f"writing to {args.out}")
    n, manifest = 0, []
    for name, box, tags, note in WINDOWS:
        for tag in tags:
            suffix = f"_{tag.upper()}" if len(tags) > 1 else ""
            out = args.out / f"{n:02d}_{name}{suffix}.png"
            n += 1                          # numbering never depends on --only
            manifest.append((out.name, note))
            if args.only and args.only not in name:
                continue
            kept, drowned, slivers, (water, land) = runs[tag]
            draw(pil, scale, box, out, water=water, land=land, kept=kept,
                 dropped=(drowned + slivers) if args.dropped else (), size=args.size)

    (args.out / "README.txt").write_text(
        "THE COLOUR PASS — 1882 Plan Cadastral, map {m}\n"
        "Regenerated by work/ocr/scripts/review_figs.py. Findings: "
        "docs/journals/260918-colour-blocks.md\n\n"
        "TWO RUNS\n"
        "  AFTER   the current default (--recut on): {a[0]} kept, {a[1]} water, {a[2]} slivers\n"
        "  BEFORE  as shipped at 9a2fe561 (--no-recut, no wash minimum): "
        "{b[0]} kept, {b[1]} water, {b[2]} slivers\n\n"
        "COLOURS  orange = kept - blue tint = the water region - green tint = the land\n"
        "         mask that bounds it. Dropped polygons are off; --dropped draws them.\n\n"
        "FIGURES\n".format(m=args.map_id[:8], a=counts["after"], b=counts["before"])
        + "".join(f"  {fn:<38s} {note}\n" for fn, note in manifest))
    print(f"  README.txt\n{n} figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
