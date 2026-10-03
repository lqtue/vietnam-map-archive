# 1898 Plan Cadastral (Bertaux) — segmentation run

**Date:** 2026-09-19 · **Map:** `20ec4f9a-16bd-4895-a593-40c6ed9c9555` · 16267 × 14859 px
Gallica `btv1b530297676` · shelfmark **Ge C 2682**
**Tool:** `work/image-processing/scripts/colour_blocks.py` + `review_figs.py` (CPU)
**Status:** runs clean · georeference blocks geographic use · segmentation importable

## The sheet

> COCHINCHINE FRANÇAISE · PLAN CADASTRAL · **DE LA VILLE DE SAIGON** · publié sous
> la direction de M. **BERTAUX**, Géomètre en Chef, Chef du Service du Cadastre et
> de la Topographie · **1898** · Echelle de 1/4000 · Réduit et dessiné par
> A. CHAUVET, Dessinateur du Cadastre

The catalogue year is **correct**. This is a distinct map from the 1882
`0e02b9d9` (Myre de Vilers / Boilloux, shelfmark Ge B 9) and covers considerably
more ground — Phú Nhuận, Hòa Hưng, Tân Hòa, Khánh Hội, out toward Chợ Lớn —
where the 1882 sheet stops at the city proper. Raw scans of both are in
`raw-scan/` for comparison.

## Two real bugs in `review_figs.py` — both now fixed

**1. The default image was the 1882 sheet.** `review_figs.py` hardcoded

```python
MAP = "0e02b9d9-…"   # 1882 Plan Cadastral
IMG = ".tile_cache/ocr/full_c03b7f44a1d8d455c2b476d248651265.jpg"
```

and took **pixels from `--image`** while taking scale, water points, furniture
mask and OCR labels from `--map-id`. So `--map-id <anything>` without `--image`
rendered **1882 pixels** labelled as the other map, silently. That is the exact
failure class `docs/digitalize-guide.md` warns about — output that looks right
while the data underneath is wrong.

*Fixed* by deleting the default: the sheet is now fetched by map id through
IIIF, the same call `colour_blocks` makes, so pixels and annotation can no
longer come from different maps. `--image` survives as an explicit override and
must be the sheet at full resolution.

**2. The crop boxes were the 1882 sheet's pixel coordinates**, including the one
named `whole_sheet`: `(0, 0, 12102, 8982)`. The 1898 sheet is **16267 × 14859**,
so `00_whole_sheet.png` showed its **top-left 74% × 60%** and called it the whole
sheet — the cartouche, the legend, Khánh Hội and the whole southern reach were
outside the picture. The fourteen named crops were 1882 place coordinates
landing on unrelated ground.

*Fixed* by deriving the whole-sheet box from the sheet's real size, and by
serving any map other than 1882 a **3 × 3 grid** (`grid_r1c1` …) that tiles it
edge to edge, instead of borrowed place names. `work/ocr/scripts/test_review_figs.py`
pins both. The 1882 named windows are unchanged on the 1882 sheet.

**What the bugs cost this report.** An earlier version of this file claimed
`20ec4f9a` was a duplicate scan of the 1882 sheet catalogued under the wrong
year — that came from bug 1 and is fully withdrawn; the raw IIIF settles it. A
later version corrected the image but still fetched it at the wrong scale, so
its "correct image" counts (1,165 → 2,365 kept, 2 → 439 water) were themselves
wrong. The figures now agree with the run they are supposed to mirror:

| | wrong image | wrong scale | **correct** |
|---|---:|---:|---:|
| kept | 1,165 | 2,365 | **3,275** |
| water | 2 | 439 | **676** |
| m per source px | — | — | **0.3377** |

0.3377 is the value `colour_blocks` reports for this sheet, which is the
agreement the renderer's docstring claims and had silently lost.

**Still open (not fixed):** the pass keeps polygons **outside the neatline** —
the corrected whole-sheet figure shows orange fragments in the printed margin,
and across the cartouche and legend panel. The furniture mask is not catching
this sheet's border. Worth a look before these 3,275 are treated as parcels.

## The georeference blocks geographic use

This is the finding that matters, and it is independent of the image — it comes
from the annotation JSON.

The annotation uses a **1st-order polynomial** (affine, 6 parameters) fitted from
exactly **3 control points**. Six equations, six unknowns: the fit passes exactly
through all three, so its residual is **zero by construction**. `geom_rmse` here
is not merely unreliable — it is structurally incapable of being non-zero, and
any gate reading it will pass this map. For contrast `0e02b9d9` uses **helmert
with 10 points**, overdetermined, which is why it can report a real 11.3 m RMSE
with a 23.0 m worst point.

The three points are also clustered:

| | |
|---|---|
| GCP hull, horizontal | 34% of sheet width |
| GCP hull, **vertical** | **13% of sheet height** |
| extrapolation to reach the corners | **3.9× the GCP spread** |

`/explore?map=20ec4f9a…#@10.77294,106.69949,14.27z` opens inside that cluster,
which is why the overlay looks correct there. At the sheet edges it will drift
and nothing downstream will say so. The fitted affine also implies **0.3266 m per
source px** against the run's reported **0.3377** — a 3.3% scale disagreement on
a sheet printed at 1/4000.

This is ROADMAP **I3**'s failure mode on a second sheet, and a concrete argument
for **I1**: "3 GCPs on a 1st-order polynomial" is exactly what a next-action view
should block a sheet on, because no downstream number will.

## The segmentation runs are valid

`colour_blocks.py` fetches from IIIF via `--map-id` and does **not** share
`review_figs.py`'s defect — its logs report `sheet 16267 x 14859`, the correct
dimensions. The GeoJSON below is good.

| run | too small (blocks) | too small (cream) | features |
|---|---:|---:|---:|
| @ `--render 4096` | 13,847 | 73,539 | 2,920 |
| @ `--render 6144` | 16,831 | 185,757 | 3,239 |
| 1882 @ 6051 — accepted baseline | 27,923 | 131,391 | 2,200 |

**The drop ratio is normal.** The baseline sheet drops twice as many. "Too small"
counts connected components under `MIN_AREA_M2 = 200` — on a dense cadastral
sheet that is ink texture, stipple and type. It *rises* with resolution because
finer rendering resolves more small components. No defect signal. This number
had never been recorded for 1882 anywhere; it is worth adding to
`EVAL-BASELINE.md` so nobody re-runs this investigation.

Class mix at 6144: building 1763, cream 559, admin 355, salmon 284, blue 153,
green 125. These differ from 1882's mix because **the maps genuinely differ** —
different surveyor, sixteen years apart, wider extent, different legend
(this sheet's key is military/local-service/unassigned/communal/private).

### The class mix is not reproducible — found 2026-09-19, after the figures

Re-running the identical command (`--map-id 20ec4f9a --render 6144`) gave the
same *shapes* and different *labels*. Counted inside the same `main_map` frame,
so the border clip below is not what moved them:

| | first run | re-run | |
|---|---:|---:|---|
| polygons | 3,185 | 3,177 | stable |
| salmon | 284 | **671** | |
| green | 106 | **11** | |
| cream | 533 | 342 | |
| blue | 153 | 221 | |
| admin | 348 | 289 | |
| building | 1,761 | 1,643 | |

The cause is upstream of the pass. `split_by_vote` is deterministic — run twice
on fixed pixels it returns `+0.0575 / +0.0075` both times — but the two runs
recorded green splits of **+0.0125** and **+0.0075**, so they did not see the
same pixels. `fetch_crop` can answer one request from the IIIF region URL, from
a composed tile pyramid (`fetch_crop_level0`) or from a full download cropped
locally, and each resamples differently. Every threshold in this pass is derived
from those bytes, and 5 thousandths on the green axis moved 90% of one class.

So **the class mix printed above is one draw, not a measurement**, and the same
is true of the 1882 mix it was compared against. Geometry is the durable output
here; classification is not, until the input is pinned.

`blocks.run.json` now records `image_sha256` of the working image, which is what
lets the next run tell a real change from a different JPEG. The manifest already
carried the derived thresholds — nothing was reading them.

### Polygons outside the printed border — fixed

The corrected whole-sheet figure showed orange in the paper margin, on the
mount, and running diagonally across the cartouche: the margin is tinted and
components like anything else, and a stringy margin strip's concave hull cuts
across the sheet. The sheet's `main_map` triage region — `[439, 401, 15388,
14012]`, already in the database, already used by
`to_sam2_seeds.load_seeds_from_prior` — bounds it. `colour_blocks.py` was the
only consumer that never read it; it now clips by default (`--no-clip-main-map`
restores the old behaviour) and drops 101 polygons on this sheet.

**Sheet size is now RAM-bounded.** `colour_blocks.py` has no tiling, by design.
The baseline's 2× downscale needs `--render 8134`, a 60 Mpx working image; the
pass holds several float32 RGB copies (~725 MB each) and was SIGKILLed on an 8 GB
machine (`run-8134-OOM.log`, exit 137). 6144 is the practical ceiling. This is
the first sheet to hit the limit and will not be the last.

## Import

Safe to import — the pixel-space polygons do not depend on the georeference.

```bash
node --env-file=.env scripts/import-seg-geojson.mjs \
  --map-id 20ec4f9a-16bd-4895-a593-40c6ed9c9555 \
  --run-id colour-1898-20260919 \
  --input ~/Desktop/vma-1898-seg-260919/run-6144-clipped/blocks.geojson --dry
```

`run-6144-clipped` is the run to import: same pass with the printed border
clipped, so the margin and mount polygons are gone. The earlier `run-6144` dry
run verified 2,919 proposals, 1 exact duplicate dropped, run id free; re-check
the count against the clipped input before dropping `--dry`.

Two properties of this manifest, both fixable by re-running:

- **no `image_sha256`** — the run predates the field, so it cannot be compared
  against a later one. See *The class mix is not reproducible* above for why
  that matters more than it sounds.
- **`ocr_run_id: null`** — the OCR rows that seeded water, the furniture mask
  and the legend key were pooled rather than pinned. Harmless while the sheet
  has one run (`2026-09-13T1036-20ec4f9a`, 472 rows) and not after the next.
  `--ocr-run-id` on the re-run settles both.

But **re-georeference the sheet before trusting anything geographic from it.**

Caveat on choosing 6144 over 4096: it is closer to the baseline's effective
resolution, but there is no ground truth on this sheet, so the preference is
reasoned, not measured. That is ROADMAP **I4**'s missing denominator in practice.

## Files

- `raw-scan/` — unprocessed IIIF images of both sheets, and the 1898 title cartouche
- `figures/` — 10 review figures: the whole sheet at 16267 × 14859, then a 3 × 3
  grid over it. Orange = kept, blue outline = dropped, blue tint = water, green
  tint = land mask.
- `../_superseded/1898-figures-wrong-image/` — the superseded set, kept only as evidence of the two bugs
- `run-6144-clipped/` — **the run to use**: border-clipped, 3,178 polygons
- `run-4096/`, `run-6144/` — the two unclipped runs, kept for the resolution comparison
- `baseline-1882-6051/` — the 1882 reference run
- `run-8134-OOM.log` — evidence for the RAM finding
