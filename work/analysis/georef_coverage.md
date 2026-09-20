# Archive-wide georeference-error coverage

**Measured 2026-09-19** by `work/analysis/district4/georef_error.py --maps <all 274 ids> --csv`,
run in batches of 25 against every row in `maps`. Extends the six-sheet result in
`work/analysis/district4/georef_error.md` to the whole archive. Same code path, same rules — see
that file for what the columns mean and why TPS and thin GCP sets can't be scored.

```bash
source work/ocr/.venv/bin/activate
python3 work/analysis/district4/georef_error.py --self-check        # no network
python3 work/analysis/district4/georef_error.py                     # the D4 six, reproduces exactly
python3 work/analysis/district4/georef_error.py --maps <id>... --csv out.csv   # this run, batched
```

## Step 1 — District 4 reproduction

All six D4 figures reproduced exactly against production, including the 1882 anchor
(`12.74 m` / `27.72 m` / `0.3411 m/px` / `89.66°`, affine `10.58 m` / `17.41 m`). **No drift.**

## The denominator

`maps` holds **274 rows**, confirmed two ways: full pagination (limit/offset, asserting the page
count each time) and PostgREST's `Content-Range` header on an exact count, which read `0-0/274`.
Every row carries an `allmaps_id`, an `annotation_url`, or both — zero rows have neither.

**The "58" figure elsewhere in the docs is not this population.** It comes from
`docs/allmaps-series-note.md` (~L191) and `docs/paper/figures.md:138,141` / `outline.md:31`: a
rim-offset / lattice-residual check run over the Indochine 1:25,000 series, "58 sheets read
independently." That series' own row in the same note gives "56 of 62 georeferenced" — close to
58 but not identical, and neither number is the archive's map count. Conflating either with 274
would understate the archive by 4-5x.

## The coverage table

274 sheets, one code path, the authoritative column read per the sheet's own declared transform
(similarity+yflip for `helmert`, affine for `polynomial` order 1 — **every one of the 230
polynomial-declared sheets was individually checked and is order 1**, not assumed; one fetch hit a
transient `ConnectionError` and was retried by hand, also order 1).

| bucket | sheets | % of 274 | extraction rows | % of 13,525 |
|---|---:|---:|---:|---:|
| measurable, healthy (RMSE < 20 m) | 225 | 82.1% | 3,875 | 28.6% |
| measurable, marginal (20 m ≤ RMSE < 40 m) | 4 | 1.5% | 854 | 6.3% |
| **measurable, bad (RMSE ≥ 40 m)** | **10** | 3.6% | **6,111** | **45.2%** |
| not measurable — model too free (TPS, or GCPs ≤ model DOF/2) | 14 | 5.1% | 2,685 | 19.9% |
| not measurable — no annotation (fetch failed) | 21 | 7.7% | 0 | 0.0% |
| **total** | **274** | 100% | **13,525** | 100% |

**Bad, defined:** RMSE ≥ 40 m — the upper edge of a Saigon block (20-40 m across, the yardstick
`georef_error.md` already uses for 1942). Below that a mis-registered label still lands inside a
recognisable block; at or above it, it doesn't. The distribution supports the cut: nothing sits
between 35.1 m and 62.9 m — nine of the ten "bad" sheets are already past 62 m, only one (1864,
35.1 m) sits in the gap below, correctly landing in "marginal" not "bad."

**Measurable = 239/274 (87.2%). Not measurable = 35/274 (12.8%).**

### By declared transform

| declared | sheets | measurable | not measurable | reason |
|---|---:|---:|---:|---|
| `polynomial` (order 1, verified per-sheet) | 230 | 222 | 8 | n_gcps = 3 ≤ affine DOF/2 = 3 |
| `helmert` | 17 | 17 | 0 | — |
| `thinPlateSpline` | 6 | 0 | 6 | TPS is exact at its own GCPs by construction |
| (no annotation — fetch 404) | 21 | — | 21 | see below |
| **total** | **274** | **239** | **35** | |

## The headline number

**65.0% of the archive's 13,525 `ocr_extractions` rows (8,796 of them) sit on a sheet with no
stated georeference limit or a bad one** — the "bad" (6,111), "model too free" (2,685) and
"no-annotation" (0) buckets combined. Two-thirds of everything ever extracted from this archive
carries either an unstated or a bad ground-truth bound. 1942 alone (31.7% of all extractions) was
already known to be bad; this run finds it keeps company.

### Sheets worse than 1942 (RMSE > 72.3 m)

Eight of them — 1942 is not the worst case, it is the median of this list:

| year | sheet | RMSE | worst | extractions |
|---|---|---:|---:|---:|
| 1909 | Province de Thua-thien | **1,415.9 m** | 2,441.7 m | 0 |
| 1922 | Carte routière des environs de Saïgon | **456.9 m** | 695.8 m | **1,420** |
| 1880 | Plan annamite d'Hanoï | 262.9 m | 503.5 m | 0 |
| 1951 | Hanoi economique | 179.4 m | 378.0 m | 0 |
| 1819 | Plan de la rivière de Huê | 127.4 m | 164.8 m | 0 |
| 1862 | Bâtiments civils: Le plan du Colonel... | 101.8 m | 255.0 m | 57 |
| 1863 | Administrados al. S. Coronel Don Carlos... | 76.4 m | 119.6 m | 0 |
| 1900 | Environs de Saïgon | 75.6 m | 138.5 m | 320 |
| — | **1942 Plan de Saigon - Cho Lon** | 72.3 m | 193.7 m | 4,287 |

**1922 is the finding that matters most here.** 456.9 m RMSE, 6 GCPs, `helmert`, and it is the
**third most-extracted sheet in the entire archive** — 1,420 `ocr_extractions` rows, more than
every sheet except 1942 and 1959. Every label pulled from it is bounded at ~460 m, over six times
1942's already-bad figure, and nothing downstream marks it as different from a healthy sheet.

### Not measurable, but heavily extracted

The five most-extracted "too free" sheets are all `polynomial` order 1 on exactly 3 GCPs — the
minimum that exactly determines a 6-DOF affine, so the affine residual is 0.0 m by arithmetic, not
accuracy (the same fact `georef_error.md` already documents for 1923):

| year | sheet | GCPs | extractions |
|---|---|---:|---:|
| 1923 | Saigon - Cholon | 3 | **1,029** |
| 1881 | Cochinchine Francaise | 3 | 548 |
| 1898 | Saigon Plan | 3 | 472 |
| 1882 (2) | Plan topographique du 20e Arrondissement | 3 | 293 |
| 1920 | Cochinchine Administrative | 3 | 225 |

Among the archive's top 15 most-extracted sheets, only six are cleanly measurable-and-healthy
(1959, 1912, 1882 cadastral, 1968, plus two below); four are structurally unmeasurable and four are
bad or marginal. A ranking by extraction volume and a ranking by "has a trustworthy stated limit"
disagree for most of the sheets that matter.

### A second, quieter version of the same fault: degenerate 4-GCP fits

216 of the 230 `polynomial`-declared sheets carry exactly 4 GCPs. Checking a sample (`1905 Nam
Dinh`) shows why: the four points are the sheet's own printed graticule corners — `lonlat` an exact
axis-aligned rectangle, `px` a rectangle to within a few pixels. An affine transform preserves
parallelograms, so it fits a near-rectangle in **either** direction essentially exactly: the fourth
point supplies almost no independent constraint beyond the first three. **93 of the 216 score
under 1.0 m RMSE** — not because the georeference is unusually good, but because the same
corner-to-corner computation that likely produced the annotation is what is being asked to check
it. This clears rule 2's literal bar (n_gcps = 4 > DOF/2 = 3) and so is counted as "measurable,
healthy" above, but it is the same failure mode as rule 2 in different clothes: **GCP count alone
does not guarantee independence: three of four corners of a rectangle determine the fourth under
any affine map.** It costs the headline number little — these 216 sheets carry only 272
extraction rows between them — but it means "measurable, healthy" at 82.1% overstates how many
sheets have a check that could actually have failed. One outlier breaks the pattern outright:
**1909 Province de Thua-thien**, also 4 GCPs, scores **1,415.9 m** — proof the corners aren't
always even self-consistent.

### No annotation (21 sheets, all L7014)

All 21 fetch failures are **L7014** sheets (US Army 1:50,000, 452-of-535 published per
`docs/allmaps-series-note.md`). Each carries an `allmaps_id` in `maps`, but
`https://annotations.allmaps.org/maps/<id>` returns `404 Map not found` for every one — consistent
with that series "arriving georeferenced" from its own GeoPDF rather than through an Allmaps
Editor annotation the hosted API would know about. None of the 21 carry any `ocr_extractions`
rows, so this bucket costs the headline number nothing, but it is a real gap: 21/274 (7.7%) of the
archive has literally no reachable georeference document to score, by a mechanism distinct from
"too few GCPs." (9 other L7014-named sheets *do* resolve, via a mirrored `annotation_url` rather
than the hosted API — `scale.py`'s "mirrored copy first, Allmaps second" order is why those
succeed where the other 21 don't.)

## What this does not establish

- Same limitation as the six-sheet result: this is in-sample residual at the control points, not
  accuracy against independent ground truth. A sheet whose GCPs were all placed consistently wrong
  reads as excellent here — see the corner-graticule note above for a documented instance of this.
- The `marginal` (20-40 m) sheets are a judgment call, not a bright line; the underlying numbers are
  in `archive_wide.csv` (not checked in — this run's own output) if a different cut is wanted.
- Not established: whether the 221 non-L7014, 4-corner `polynomial` sheets are all one series
  (candidates for the Indochine 1:25,000 series in `allmaps-series-note.md`, but that note's own
  count for that series — 56-62 — is well short of 221, so at least some of these are a different
  batch built the same way). Confirming that split needs the series field, not measured here.
- Not established: why the 21 L7014 `allmaps_id`s 404 while 9 others resolve — plausibly a mirroring
  gap rather than a georeferencing one, but not traced further than the HTTP response.

## Cross-reference

Full per-sheet CSV from this run (id, year, name, GCPs, declared transform, condition number, scan
size, both fits' RMSE/worst/scale/rotation) is not checked into the repo — see the run command
above to regenerate it; it takes about 10-15 minutes across ~550 HTTP calls.
