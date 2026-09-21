# District 4 — georeference error per sheet

**Measured 2026-09-19** by `work/analysis/district4/georef_error.py`, against production, from each
sheet's own Allmaps annotation. All six sheets, one code path, so the figures are comparable to each
other — which is why 1882 was redone rather than carried over.

```bash
python3 work/analysis/district4/georef_error.py --self-check   # no network
python3 work/analysis/district4/georef_error.py                # the table below
```

## The table

| year | sheet | GCPs | declared | scan (px) | m/px | rot | similarity+yflip RMSE | worst | affine RMSE | worst |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1882 | Plan Cadastral de la ville de Saigon | 10 | `helmert` | 12102×8982 | 0.3411 | 89.66° | **12.7 m** | 27.7 m | 10.6 m | 17.4 m |
| 1895 | Plan des environs de Saïgon | 11 | `thinPlateSpline` | 13654×8964 | 1.7073 | 359.49° | 34.6 m | 59.1 m | 26.4 m | 49.7 m |
| 1923 | Saigon – Cholon | **3** | `polynomial` order 1 | 16064×14027 | 0.8452 | 359.57° | 8.8 m | 11.6 m | 0.0 m | 0.0 m |
| 1942 | Plan de Saigon – Cho Lon | 12 | `helmert` | 14915×12602 | 0.8458 | 0.21° | **72.3 m** | **193.7 m** | 67.1 m | 174.5 m |
| 1959 | Đô thành Sài Gòn | 10 | `polynomial` order 1 | 14000×10773 | 0.9974 | 359.69° | 14.0 m | 22.9 m | **12.8 m** | 18.1 m |
| 1968 | Sài Gòn – Việt Nam City Maps 1:12,500 | 15 | `helmert` | 10816×13523 | 1.2729 | 359.53° | **9.0 m** | 20.1 m | 8.8 m | 18.9 m |

Every scan dimension above came from the annotation's own `target.source` — the same document the
control points live in. Never from a README.

## Read the column the sheet's own transform makes authoritative

**Do not read the bold similarity column across all six rows.** Allmaps applies the transform the
annotation declares, and three different transforms appear here:

| declared | what Allmaps renders | the column that states its error |
|---|---|---|
| `helmert` (1882, 1942, 1968) | similarity + y-flip | **similarity+yflip** |
| `polynomial` order 1 (1923, 1959) | an affine — order 1 *is* affine | **affine** |
| `thinPlateSpline` (1895) | TPS, which interpolates **exactly** through every GCP | **neither** |

So the archive's actual position on these six sheets:

| year | stated georeference error | |
|---|---|---|
| **1968** | **9.0 m** RMSE, worst 20.1 m | measurable, healthy |
| **1882** | **12.7 m** RMSE, worst 27.7 m | measurable, healthy |
| **1959** | **12.8 m** RMSE, worst 18.1 m | measurable, healthy |
| **1942** | **72.3 m** RMSE, worst 193.7 m | measurable, **and bad** |
| 1895 | **not measurable from its own GCPs** | TPS is exact at them by construction |
| 1923 | **not measurable from its own GCPs** | 3 GCPs exactly determine its declared affine |

**Four of six sheets now have a stated georeference limit where one had it this morning.** Two
cannot have one, and both for the same reason in different clothes: the model has enough freedom to
pass through its own control points, so the residual is zero or near-zero however the sheet is
placed. That is the fourth instance this week of a check that cannot fail — see
`docs/paper/outline.md`. For these two the error has to come from somewhere outside the annotation:
independent check points, or the lattice.

## 1942 is the finding, and it is not good news

**72.3 m RMSE and a worst point at 193.7 m, on 12 GCPs, declared `helmert`, condition 0.410.** This
is a well-determined fit on adequate, well-spread control points — it is not an artefact of thin
data. The sheet really is placed that badly.

It matters more than the number suggests, because **1942 is the most-extracted sheet in the
archive**: 4,287 `ocr_extractions` rows, 31.7% of all 13,525 (`docs/paper/figures.md` §0.1). Every
ground claim made from those labels is bounded at ~72 m, not at the ~11 m the 1882 worked example
established and that it is tempting to generalise. A Saigon block is 20–40 m across, so a 1942 label
can land **five plots away**.

Nothing downstream currently says so. `ocr_extractions.geom_rmse` is a per-*map* constant (16.50 on
1882's 499 rows, per `worked-example-1882.md`) and cannot carry this.

**Also: 1942 has two scans, exactly like 1959 did.** The annotation's GCPs sit on **14915×12602**.
`work/analysis/district4/README.md` records **7479×6314** as *"confirmed — its own layout job, run
2026-09-05, reports this `source_size`"*. Both are right about their own scan: 14915/7479 = 1.994
and 12602/6314 = 1.996, so one is a 2× resampling of the other. The README's figure is confirmed
against a scan the control points do not live on. Fix the README row; do not fix the annotation.

## The 1882 figure has moved, and why

`docs/worked-example-1882.md:40` records **RMSE 11.3 m, worst 23.0 m, 0.3426 m/px**. This script
measures **12.7 m, 27.7 m, 0.3411 m/px** on the same annotation and the same ten points.

**Neither is a bug, and the difference is the degrees→metres conversion.** The recorded pair was
computed over a *spherical* earth (R = 6,371,008 m); feeding that conversion into this script
reproduces 11.28 / 23.00 exactly. This script uses the WGS84 **radii of curvature at the sheet's own
latitude** — 110,613 m per degree of latitude and 109,368 per degree of longitude at 10.78° N —
cross-checked against `pyproj` UTM 48N, which agrees to **0.01 m**. The geodetic figures are the
ones to quote.

A third convention was tried and rejected: `scale.py`'s fixed constants (111,132.95 / 111,320.0),
which are global means rather than local values and give 11.6 m. `scale.py` is right to use them —
it sizes tiles, needs ~1%, and a metre is invisible after snapping to a grid. A residual is a
different job.

### The part worth keeping

**The affine residual is 10.58 m / 17.41 m under every one of the four conventions tried. The
similarity residual moves from 11.3 to 12.7.**

Six degrees of freedom absorb a wrong latitude/longitude ratio into the fitted coefficients; four
cannot. So the more flexible model is *blind to an error in the frame it is being measured in*, and
the stricter one is the only one that can see it. This is the archive's own thesis appearing inside
its own measurement code, and it is a cleaner miniature of it than anything in the L7014 series:
same data, same points, one model reports the fault and the other reports nothing.

It also means the old sentence in `worked-example-1882.md` — *"Affine barely beats helmert (10.6
against 11.3). There is no shear and no differential scale, so the scan is undistorted"* — needs
softening. Under the geodetic conversion it is 10.6 against 12.7, and the affine's two axis scales
are 0.3396 and 0.3445, **1.4% apart**. That is not "no differential scale".

## Per-sheet notes

- **1895** — `thinPlateSpline`, 11 GCPs. The 34.6 m similarity figure is a measure of how far the
  sheet departs from rigidity, not of georeference error. Given 1.71 m/px it is ~20 px, which is
  consistent with a hand-placed set on a coarse scan.
- **1923** — **3 GCPs, condition 0.160.** The minimum that determines anything, and the affine 0.0 m
  is arithmetic, not accuracy: 3 points × 2 coordinates = 6 equations for a 6-parameter affine. The
  similarity's 8.8 m has just two degrees of redundancy behind it. **This sheet needs more control
  points before any number from it is quoted**, and it covers 56% of the peninsula.
- **1959** — healthy at 12.8 m affine, and the 14000×10773 scan confirms the 2026-09-10 correction
  in the README rather than the stale 5000×3790 row.
- **1968** — the best of the six at 9.0 m, 15 GCPs, condition 0.958 (the most evenly spread control
  in the set).
- Rotations: 1882 sits at 89.66°, the other five within 0.5° of 0°. The 1882 sheet being turned
  ~90° is already documented and is why a naive pixel-to-ground check on it looks wrong.

## What this does not establish

- **It is the fit's residual at the control points, not accuracy against independent ground.** A
  sheet whose GCPs were all placed consistently wrong reads as excellent here. That is the same
  limitation Luft & Schiewe's corner metric has (`docs/paper/related-work.md` §2), and the honest
  name for it is precision, not accuracy.
- **No check point was used.** Every figure above is in-sample.
- 1895 and 1923 remain unmeasured, per above.
- The conversion is a local tangent plane, good to ~0.01 m against UTM here; do not carry it to a
  sheet spanning degrees.

## Archive-wide

This six-sheet result is extended to all 274 sheets in `maps`, same code path, in
`work/analysis/georef_coverage.md` (2026-09-19). Headline: 65.0% of the archive's `ocr_extractions`
rows sit on a sheet with no stated georeference limit or a bad one, and 1942 is not even the worst
case — eight sheets score worse, one of them (1922, 456.9 m RMSE) the archive's third
most-extracted sheet.

## The 1942 two-panel suspicion, tested and rejected (2026-09-21)

The 1942 scan carries **two separate printed sheets** — `PLAN DE CHOLON` (itself
marked *"Extrait du Plan de Saigon-Cholon en 4 feuilles"*) and `PLAN DE SAIGON`,
both *Edition de Novembre 1942*, both 1:10.000 — laid side by side with their
neat-lines butted together. That is visible on any overview and is not recorded
anywhere else in this repo.

It is the obvious explanation for 72.3 m: two plans cannot share one rigid
transform. **Measured, it is not the explanation.** `sheet_panels.py --year 1942`
fits each panel's printed neat-line to sub-pixel precision off the native tiles
and traces the Tàu Hủ canal across the seam in the full-sheet river mask:

| | |
|---|---|
| Cholon panel | 3597 × 4978 px, neat-lines −0.0219° |
| Saigon panel | 3599 × 4973 px, neat-lines −0.0467° |
| panel-to-panel rotation | **0.0248°** — 4 m corner to corner at 1.69 m/px |
| panel size agreement | 0.06% in x, 0.10% in y — two sheets of one series |
| canal across the seam | largest bend 5.5 px (9 m), **at x=3800, past the neat-line**; median 1.5 px |

No step at the seam, no relative rotation, no scale difference. Whoever
assembled this scan aligned the ground rather than the paper — the panels' own
frames are 987 px apart vertically precisely because the ground was matched
instead. **The mosaic is sound to a few pixels, so it contributes nothing like
72 m and the sheet's residual has another cause.**

Reproduce (needs that sheet's tiles and mask from `river_full_map.py --year 1942`):

```bash
python work/analysis/district4/sheet_panels.py --self-check
python work/analysis/district4/sheet_panels.py --year 1942
```

### What this leaves

The affine residual is 67.1 m against the similarity's 72.3 m. **Six degrees of
freedom buy almost nothing**, so whatever is wrong is not a systematic linear
distortion — not rotation, not scale, not shear, and now not a mosaic seam
either. An error that a more flexible model cannot absorb, with a worst point at
193.7 m against a 72.3 m RMSE, is the signature of **a few blunder points**, not
of a distorted sheet.

That is cheap to test and has not been tested: refit dropping the worst
residual, one point at a time, and watch the RMSE. If three exclusions take it
from 72 m to the ~13 m the other healthy sheets sit at, the sheet is fine and
its annotation has bad control points — which is a fixable data problem on the
archive's most-extracted sheet, not a limit on it.

**Blocked on credentials, not on method.** `annotation_for_map` needs
`PUBLIC_SUPABASE_URL` + `SUPABASE_SERVICE_KEY`, and there is no `.env` in the
working tree; the Allmaps public annotation server 404s on these IIIF images, so
the GCPs cannot be reached another way. Everything above was measured off the
public IIIF tiles instead, which is why it is about the scan and not about the
control points.

### Also checked

**1923 is a single sheet, not a mosaic** — but it is a *folded* one, and both
fold creases are strong enough that the river detector traces them across the
full sheet (`docs/journals/260920-colour-transfer.md`, 2026-09-21). With 3 GCPs
and an unmeasurable residual already, that sheet's geometry should not be
assumed rigid either.

## The 1942 blunder points, found — and the river as the stopping rule (2026-09-21)

**The credential blocker was wrong.** The annotations are mirrored to a *public* Supabase
Storage bucket (`maps.annotation_url`), so plain `curl` reaches every sheet's GCPs with no
service key. The `maps` row that names the URL needs only the anon key, which ships in the
deployed bundle. Nothing here required `SUPABASE_SERVICE_KEY`.

**And the "1942 scan mismatch" was never a data error.** Its GCPs sit on
`eca788e5-…-20260911`, a 2026 rescan at 14915×12602 that is live and serving tiles. The
7479×6314 image every river run used is the *older* scan. The ratio is 1.9943 × 1.9959, so
the two are reconcilable exactly, and `river_align.py` carries that factor. The rescan is
twice the linear resolution and the river work should move onto it.

### All four sheets, measured

| year | GCPs | declared | similarity RMSE | worst | affine RMSE |
|---|---:|---|---:|---:|---:|
| 1923 | 3 | polynomial | 8.8 m | 11.6 m | 0.0 m — degenerate, 3 points exactly determine an affine |
| **1942** | 12 | helmert | **72.3 m** | 193.7 m | 67.1 m |
| 1959 | 10 | polynomial | 14.0 m | 22.9 m | 12.8 m |
| 1968 | 15 | helmert | 9.0 m | 20.1 m | 8.8 m |

1968 is the control this file previously lacked. Its leave-one-out curve falls **10–15% per
exclusion**; 1942 falls **40% on the first**. That contrast is the blunder signature, and it
is visible only because a healthy sheet was measured alongside.

### The stopping rule, which is the actual finding

Dropping the worst point always lowers RMSE, so **RMSE cannot say when to stop dropping.**
The warped river can, because it is not used in the fit:

| dropped | n | GCP RMSE | river ↔ 1959 | river ↔ 1968 |
|---|---:|---:|---:|---:|
| none | 12 | 72.3 m | 31.6 m | 58.3 m |
| #1 | 11 | 43.2 m | 30.0 m | 58.3 m |
| #1, #7 | 10 | 34.2 m | 28.3 m | 58.3 m |
| **#1, #7, #11** | 9 | **19.3 m** | **22.4 m** | 58.3 m |
| #1, #7, #11, #4 | 8 | 15.9 m | 22.4 m | 56.6 m |
| #1, #7, #11, #4, #9 | 7 | 12.6 m | **50.0 m** | 60.0 m |

The fifth exclusion takes RMSE to 12.6 m — the healthiest number in the table — while the
independent river check **more than doubles**. That is overfitting, and nothing in the GCP
residual reveals it.

**Recommendation: drop GCPs #1, #7 and #11 from the 1942 annotation** (#1 is the 193.7 m
point at 106.70371, 10.76800). RMSE 72.3 → 19.3 m *and* independent river agreement
31.6 → 22.4 m, moving together. This is the archive's most-extracted sheet at 31.7% of all
extractions. **Not yet applied** — it is a write to a published annotation and wants a human
look at those three points on the sheet first.

### What this does not establish

- 1942 ↔ 1968 sits at ~58 m throughout and barely responds. Different era, real bank change
  and 1968's own error are all mixed into it; the pairwise number cannot separate them.
- The river masks have **no hand-drawn reference** (`river-comparison.md` §Gate), so these
  distances are agreement between two unvalidated masks, not accuracy.
- Mask thickness enters the distance. A median of 22.4 m is a few cells at 10 m grid.
- 1923's river is the least trustworthy of the four (8.55% of sheet, folds and boulevards
  still in) and its 3-GCP fit is degenerate, so its rows are context, not evidence.

Reproduce:

```bash
python work/analysis/district4/river_align.py --self-check
python work/analysis/district4/river_align.py --step 4
python work/analysis/district4/river_align.py --step 4 --drop-1942 1 7 11
```
