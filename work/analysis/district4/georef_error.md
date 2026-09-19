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
