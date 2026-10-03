# L7014 automatic placement of the 74 unplaced sheets — record

**Run 2026-09-20**, from the `docs/paper-phase-0-1` working tree, on top of the `l7014_mosaic.py`
corrected build recorded in `REGEN.md` (`work/l7014/build/l7014-fixed-hand.geojson`, 460 sheets: 436
pdf + 24 jpg). GDAL 3.13.3 · Python 3.14.7 · macOS arm64.

New code: `scripts/l7014_autoplace.py` (self-checked, `--self-check`). One extension to
`scripts/l7014_neatline.py`: `corners()` gained an optional `gate=` parameter (default unchanged) so
an experiment can classify against a different threshold without touching what `validate`/`propose`
do by default. `l7014_mosaic.py`, `l7014_hand.py`, `l7014_seams.py` are unmodified — read and
imported (and, for one neighbour-warp step, monkeypatching `l7014_mosaic.COG_DIR` at runtime to
redirect *output location only*), never edited.

## Inputs

| input | where it came from |
|---|---|
| 74 unplaced sheets | `work/l7014/regen/warp-fixed.log`, the `NOGEO`/`OFFCELL`/`OFFGRID` lines from `l7014_mosaic.py warp` |
| `work/l7014/lattice.json` | 627 cells' WGS 84 corners, from `l7014_mosaic.py corners` (already on disk) |
| 460 already-placed sheets | `work/l7014/build/l7014-fixed-hand.geojson` (436 pdf + 24 jpg, the *corrected* build) |
| the 74 PDFs | `work/l7014/pdfs/`, already fetched |

`work/l7014/cogs/` was **not read as ground truth and not written to**: it currently holds the
*faulty*-datum pass (`--no-datum-shift`), the last thing `l7014_mosaic.py warp` wrote to it per
`REGEN.md`'s own command order — confirmed by comparing its file mtimes against
`build/l7014-faulty.geojson` (both ~11:29) versus `build/l7014-fixed.geojson` (11:13, before the
`rm -rf cogs` that preceded the faulty pass). Verified untouched throughout this run: 437 `.tif`
before and after. Wherever this record needed a *corrected* neighbour's pixels, it re-warped that
one sheet with `l7014_mosaic.warp_one`/`warp_pinned_one` unmodified, output redirected to
`work/l7014/cogs-ref/` (48 sheets, only the neighbours actually needed).

## Commands

```bash
python3 scripts/l7014_autoplace.py sweep --jobs 1      # see "the --jobs 4 deadlock" below
python3 scripts/l7014_autoplace.py place --gate loose
python3 scripts/l7014_autoplace.py seams
python3 scripts/l7014_autoplace.py --self-check
```

Outputs: `regen/autoplace-detect.json` (raw per-sheet detection), `regen/autoplace-sweep.csv`
(per-sheet classification under both gates), `regen/autoplace-placed.json` (the 26 candidates),
`cogs-auto/` (26 production-style COGs, cropped to their cell), `cogs-check/` (the same 26,
unclipped + 600 m buffer, diagnostic only), `regen/autoplace-seams.csv` + `autoplace-summary.json`
(the pixel check).

## 1. Full-quad yield over the 74

`quad_ok` is `l7014_neatline.py`'s geometric check on the detected quad: opposite edges agree to 3%,
corners are near the image axes, and (when an expected aspect is supplied) the width/height ratio
matches the cell's own latitude to 3%.

| reject | n | quad_ok |
|---|---|---|
| NOGEO | 62 | 29 |
| OFFCELL | 11 | 4 |
| OFFGRID | 1 | 1 |
| **total** | **74** | **34** |

**This supersedes an earlier number, and the reason is itself a finding.** The first pass at this
sweep (`work/l7014/regen/neatline-unplaced.csv`, produced before this record, per the task's own
instruction not to redo it) reported **37** quad_ok. Both runs call the same `corners()`; the
difference is `expect`, the expected width/height ratio the aspect check compares against.
`l7014_neatline.cmd_propose` — and the standalone sweep that first produced `neatline-unplaced.csv`
— get it from `ground_aspect(sheet)`, which reads `work/l7014/corners.csv`. That CSV is written by
`l7014_mosaic.py corners` for **`kind: jpg` sheets only** (`phase_corners`: `rows = [... r["kind"] ==
"jpg" ...]`) — and all 74 sheets here are `kind: pdf`. Confirmed directly:
`ground_aspect('6440-2')` and `ground_aspect('5650-1')` both return `None`. `quad_ok`'s own code
skips the aspect leg entirely when `expect` is falsy (`if expect: ...`). So the first sweep ran
`quad_ok` on 3 of its 4 checks for every one of the 74 sheets, silently.

This run fixes it: `expect_aspect(sheet, cells)` reads the width/height ratio straight off
`lattice.json`, which has all 627 cells (not just the 24 jpg ones), the same "the sheet's own claim
is exactly what's missing or wrong here, so use the lattice instead" reasoning `pick_crs` and
`lattice_error` already apply to the CRS choice. With the aspect check actually running, **three
sheets that passed the broken check now fail it** — direct evidence the gap was not cosmetic: it was
specifically the leg of `quad_ok` built to catch a uniformly-scaled bad quad (§"the design point" in
the task brief — a detector that locks onto an interior grid line on all four sides can still produce
a geometrically tidy, parallel, near-axis-aligned rectangle; only the aspect ratio catches that it is
the *wrong size* of rectangle).

## 2. Choosing GATE_LOOSE

`GATE_DEFAULT` (`l7014_neatline.GATE`, unchanged: `residual<2.0px, inliers>0.55, found>0.60`) gives
**18** of 74 sheets all four corners `ok`. The task's premise — residuals stay tight on rejected
edges, so the fix is in `inliers`/`found`, not fit quality — was checked against the full 74, not
just the 13-sheet sample it was first observed on. One detection pass ran with an accept-everything
gate (so which of the two candidate line-fits wins a side is decided purely by fit quality, never by
a threshold — see the note in `l7014_autoplace.corners`'s docstring reuse), and both gates were then
applied after the fact to the same (residual, inliers, found) numbers.

Restricting to the **196 of 288 edges with residual < 2.0 px** (i.e. leaving the residual leg exactly
where the default gate already sets it — nothing here argues for loosening it, and the brief's own
premise was about the other two legs):

| population | n | inliers | found |
|---|---|---|---|
| passes default (inliers>0.55 **and** found>0.60) | 149 | — | — |
| fails on `found` alone | **0** | — | — |
| fails on `inliers` alone | 43 | **0.230 – 0.550** (median 0.486) | 0.632 – 1.000 (median 0.883) |
| fails on both | 4 | 0.041 – 0.193 (median 0.114) | 0.059 – 0.427 (median 0.271) |

Two things settle the gate. First, **`found` is never the sole reason an otherwise-clean edge is
rejected** — 0 of 196 tight-residual edges fail on `found` alone, so loosening it barely matters and
can be generous. Second, there is a **clean, unoccupied gap** between the two failing populations:
the 43-edge "rescue" population's lowest `inliers` is 0.230, the 4-edge "still bad" population's
highest is 0.193 — nothing falls between 0.193 and 0.230, and correspondingly nothing falls between
`found` 0.427 and 0.632. That is not a threshold chosen to hit a target count; it is where the data
itself splits into two populations. `GATE_LOOSE = {residual: 2.0, inliers: 0.20, found: 0.45}` sits
in the middle of both gaps.

The two edges just above the residual cut (2.0–2.9 px, `inliers` 0.48–0.73, `found` 0.59–0.95:
`6433-4 T`, `5554-4 T`) were left alone on purpose — loosening `inliers`/`found` is supported by a
clean split in the data; loosening `residual` past its already-validated value (the module `GATE`
comment: "median 1.7 px, p95 6.8, worst 10.1" against real NEATLINE ground truth) is not, since these
74 sheets have no NEATLINE to validate a new residual threshold against. Recorded here rather than
acted on.

With `GATE_LOOSE`, full 4/4 goes **18 → 26**:

| reject | n | default4 | loose4 |
|---|---|---|---|
| NOGEO | 62 | 14 | 21 |
| OFFCELL | 11 | 4 | 4 |
| OFFGRID | 1 | 0 | 1 |
| **total** | **74** | **18** | **26** |

(OFFCELL's 4 are unchanged — those four sheets' edges were already clean enough to clear the default
gate; loosening only reaches into the population that was failing on thin evidence, not fit quality.)

## 3. `place`: 26 candidates warped

All 26 sheets that clear `quad_ok` + 4/4 corners under `GATE_LOOSE` warped cleanly: 4 detected-corner
GCPs → order-1 affine (the same recipe `l7014_mosaic.warp_pinned_one` uses for the hand-pinned JPGs,
just sourced from the PDF), cropped to the lattice cell → `work/l7014/cogs-auto/`. A second,
unclipped, 600 m-buffered warp of the same GCPs went to `work/l7014/cogs-check/` for the seam check
only (see below) — its outline is not the cell, on purpose.

## The design point: why an outline check is void here, and what replaced it

Every GCP this script builds has the lattice cell as its ground half — identical in kind to
`l7014_hand.py`'s `ground_quad`. A placed sheet's *outline* is therefore the cell by construction,
regardless of whether the detected neatline was right. Running `l7014_seams.py` against
`cogs-auto/`'s outlines would reproduce exactly the trap `REGEN.md` documents for the 36 hand-to-mosaic
seams ("a hand sheet is on the lattice by construction... not a free seam"). So `seams` never touches
an outline. It has to look at pixels.

**First design, and why it was replaced.** The first implementation cross-correlated a raw-grayscale
window straddling each shared edge, candidate against neighbour, searching a wide pixel range for the
shift maximising correlation. Run over all 26 candidates it returned **FAIL on every single edge** —
58 of 58 — at offsets clustering suspiciously close to the search radius rather than anywhere
data-dependent. Diagnosed on the cleanest candidate available (`6144-3`, quad_ok, all four edges
sub-pixel residual under the default gate): at zero shift, with full valid pixel overlap, the
correlation was **negative** (-0.28) — there was never a real peak to find. The reason is physical:
a correctly warped candidate's unclipped buffer is blank *page margin* (confirmed directly —
`l7014_neatline.py`'s own `INSET` measurement puts the printed neatline at 3–4% in from three edges
of the page), not real map content, so there is no texture there to correlate against the neighbour's
real content at *any* shift. Normalized cross-correlation over a shrinking, noise-dominated sample
count then did what it always does absent a true signal: reported whichever trial shift's tiny,
unluckily-correlated sample scored highest, which is systematically near the edge of the search
window. Raising the required overlap fraction to 70% did not fix it — the flat, near-zero correlation
surface persisted even then (checked directly on `6144-3`/`6144-2`; the "corrected" run still could
not find a shift with `corr` meaningfully above 0).

**What replaced it.** Not "does this pixel value match that one" but "where does each sheet's own
real content stop" — reusing, unmodified, the same `paper_mask`/`colour_mask`/`busy_mask`
classification `l7014_neatline.py` already uses on the source page, aimed instead at a strip
straddling the shared cell edge on the *warped* output:

- The **candidate**'s content/margin transition is found by re-running that classification on
  `cogs-check/`'s unclipped raster, walking outward from the candidate's own interior. A correctly
  placed sheet's real content should stop within noise of the lattice edge (normal-distance ≈ 0); a
  sheet whose neatline was detected on the wrong line — "right frame, shifted content", the failure
  mode this whole exercise exists to catch — stops measurably short of or past it.
- The **neighbour**'s transition needs no reclassification: its `cogs-ref/` raster is already
  production-cropped to its own NEATLINE (`write_cutline`), so the alpha channel's edge *is* its
  measured border.
- Both are found by binning pixels into 3 m normal-distance bins (averaged across a 200 m strip along
  the edge) and locating the sub-pixel crossing where the profile drops below 0.5 and stays there for
  3 consecutive bins (the same "a transition has to hold, not just touch" reasoning behind
  `l7014_neatline.RUN`) — implemented as `find_crossing`/`binned_profile`, both self-checked.

The offset is the ground-metre gap between the two independently-measured stopping points. Sanity
check on `6144-3`/`6144-2` (E): candidate content stops ≈ +20 m past the lattice edge, the
neighbour's own crop already extends ≈ -23.5 m short of it on its side (consistent with `REGEN.md`'s
"median miss (on-cell) 10 m" for even validated sheets — no sheet, including correctly placed ones,
sits exactly on the idealised lattice cell) — combined gap 43.5 raw-map-units × the Mercator scale
correction (below) = 40.0 m, exactly what the full run reports for that edge.

**EPSG finding.** The task brief describes the mosaic's CRS as EPSG:4326. It is not: every COG here
(both the archive's own and this script's) is **EPSG:3857** (Web Mercator) —
`gdalwarp -t_srs EPSG:3857` in both `l7014_mosaic.warp_one`/`warp_pinned_one` and this script's
`warp_affine`, confirmed by reading a production COG's geotransform (`11910716..., 4.42, 0,
1862878..., 0, -4.42` — metres in the millions, not degrees). This matters for a metre offset: Web
Mercator inflates ground distance by `1/cos(latitude)`, so every raw map-unit offset here is
multiplied by `cos(latitude)` (`merc_scale`, self-checked: 1° of longitude at 10° N reads back as
109.63 km, matching `111.32 × cos(10°)`) before being reported. Skipping that correction would have
overstated every offset in this series (5–16° N) by 2–5%.

## 3 (continued). Per-sheet cross-seam offsets

58 candidate/already-placed shared edges found via lattice adjacency (`shared_edges`, geometry only —
this is not the void outline check; it only asks which cells are neighbours, never whether either
sheet's outline is correct). One neighbour (`6541-3`, a hand-georeferenced jpg) could not be
re-warped at all — its `.points` file is neither a 4-corner quad nor carries a mask, so
`warp_pinned_one` correctly refuses it ("give it a mask in the Allmaps Editor") — leaving **58**
measurable pairs.

| candidate | neighbour | edge | offset (m) | verdict |
|---|---|---|---|---|
| 5650-1 | 5651-2 | N | 14.2 | PASS |
| 5650-1 | 5750-4 | E | 60.5 | FAIL |
| 5750-1 | 5750-4 | W | — | no signal |
| 5750-1 | 5751-2 | N | — | no signal |
| 5847-2 | 5847-1 | N | 19.3 | PASS |
| 5847-2 | 5947-3 | E | 27.1 | FAIL |
| 5851-3 | 5751-2 | W | — | no signal |
| 5851-3 | 5851-2 | E | — | no signal |
| 5851-3 | 5851-4 | N | — | no signal |
| 5946-1 | 5947-2 | N | 14.8 | PASS |
| 5946-1 | 6046-4 | E | 15.5 | PASS |
| 5948-4 | 5948-1 | E | — | no signal |
| 5948-4 | 5948-3 | S | — | no signal |
| 5949-1 | 5950-2 | N | 17.0 | PASS |
| 5949-1 | 6049-4 | E | 16.4 | PASS |
| 5950-3 | 5950-2 | E | 23.7 | PASS |
| 5950-3 | 5950-4 | N | 28.8 | FAIL |
| 6144-3 | 6144-2 | E | 40.0 | FAIL |
| 6332-4 | 6332-1 | E | 29.4 | FAIL |
| 6332-4 | 6332-3 | S | 34.4 | FAIL |
| 6433-3 | 6432-4 | S | 23.4 | PASS |
| 6433-3 | 6433-2 | E | 32.6 | FAIL |
| 6437-1 | 6437-2 | S | — | no signal |
| 6440-2 | 6440-1 | N | 3.6 | PASS |
| 6440-2 | 6540-3 | E | 23.0 | PASS |
| 6440-4 | 6440-1 | E | — | no signal |
| 6441-1 | 6441-4 | W | 8.8 | PASS |
| 6441-1 | 6442-2 | N | 20.0 | PASS |
| 6441-1 | 6541-4 | E | 13.2 | PASS |
| 6441-2 | 6440-1 | S | 28.6 | FAIL |
| 6530-3 | 6430-2 | W | 231.5 | FAIL |
| 6530-3 | 6530-2 | E | 21.3 | PASS |
| 6530-3 | 6530-4 | N | 6.1 | PASS |
| 6534-3 | 6533-4 | S | 67.9 | FAIL |
| 6534-3 | 6534-2 | E | 8.5 | PASS |
| 6535-4 | 6535-1 | E | 23.4 | PASS |
| 6535-4 | 6536-3 | N | 9.2 | PASS |
| 6537-4 | 6537-1 | E | 33.8 | FAIL |
| 6537-4 | 6537-3 | S | 26.7 | FAIL |
| 6537-4 | 6538-3 | N | 5.1 | PASS |
| 6538-2 | 6537-1 | S | 35.9 | FAIL |
| 6538-2 | 6538-1 | N | 28.1 | FAIL |
| 6538-2 | 6538-3 | W | 10.6 | PASS |
| 6538-2 | 6638-3 | E | 22.6 | PASS |
| 6538-4 | 6538-1 | E | 23.0 | PASS |
| 6538-4 | 6538-3 | S | 20.5 | PASS |
| 6539-3 | 6439-2 | W | 16.3 | PASS |
| 6539-3 | 6539-2 | E | 29.2 | FAIL |
| 6539-4 | 6539-1 | E | 23.4 | PASS |
| 6539-4 | 6540-3 | N | 2.4 | PASS |
| 6736-1 | 6736-2 | S | 37.9 | FAIL |
| 6736-1 | 6736-4 | W | 10.7 | PASS |
| 6736-1 | 6737-2 | N | 7.7 | PASS |
| 6736-1 | 6836-4 | E | 37.9 | FAIL |
| 6835-4 | 6735-1 | W | 14.3 | PASS |
| 6835-4 | 6835-1 | E | 20.4 | PASS |
| 6835-4 | 6835-3 | S | 69.2 | FAIL |
| 6835-4 | 6836-3 | N | 118.6 | FAIL |

Edge tally: **58** measurable, **49** produced a usable offset, **30 pass** at <25 m (the series'
drafting accuracy), **19 fail**. 9 edges gave no signal at all — both sides' content/margin
classification found no sustained transition within the ±250 m window, which reads as genuinely
sparse map content near that particular border (these sheets sit in remote hill country — Laos
border, Nghệ An highlands — where a 500 m strip can be short of any road, river or contour dense
enough for `busy_mask`/`colour_mask` to fire) rather than a detector fault, but this is not proven
either way — see "what is not established".

**Per-candidate**, requiring every measured edge on a sheet to pass (one bad seam withholds the whole
sheet, the same rule `classify` already applies to a corner needing both its edges):

| bucket | n | sheets |
|---|---|---|
| **pass** (every measured edge <25 m) | **7** | 5946-1, 5949-1, 6440-2, 6441-1, 6535-4, 6538-4, 6539-4 |
| **fail** (≥1 measured edge ≥25 m) | **14** | 5650-1, 5847-2, 5950-3, 6144-3, 6332-4, 6433-3, 6441-2, 6530-3, 6534-3, 6537-4, 6538-2, 6539-3, 6736-1, 6835-4 |
| **unverified** (a neighbour exists but gave no usable content at any shared edge) | **5** | 5750-1, 5851-3, 5948-4, 6437-1, 6440-4 |

Every one of the 26 candidates had at least one lattice-adjacent already-placed neighbour — the
`unverified` 5 are not "no neighbour to test against", they are "the neighbour(s) they had produced
no measurable signal". **Unverified sheets are not counted as passing** and are excluded from the net
answer below; they are placed (in `cogs-auto/`) but not proven.

`6530-3`/`6430-2` (231.5 m) is worth a specific note: the 7 per-sample offsets on that one edge were
bimodal — two near-zero (0.0, 8.0 m), the rest clustered 231–240 m — not a uniform shift, which reads
like a rotation/shear error concentrated toward one end of the edge rather than a simple translation.
`6530-3` is the series' one `OFFGRID` sheet (its own control points sit 0.00417° off its printed
graticule, the anomaly that put it in that bucket to begin with); this is independent, converging
evidence that this specific sheet carries a real geometric problem the corner detector's quad/gate
checks did not catch.

## 4. The net answer

Of the 74 unplaced sheets:

- **34** produce a geometrically valid quad (`quad_ok`), with the aspect-check gap in §1 corrected.
- **26** additionally clear 4/4 corners at `GATE_LOOSE` and were warped (`cogs-auto/`).
- Of those 26, **7 are verified** by the pixel content check at <25 m on every shared edge it could
  measure.

**7 of 74 can be placed automatically with proof**, by the standard this task set: a check that
looks at content, not outline. A further 14 are placed but pixel-verified as failing (they belong
back with a person or a better detector, not in the archive), and 5 are placed but unverified — real
sheets sitting in real cells, with no independent confirmation either way.

If "placed with a plausible geometric detection" is the bar instead (no pixel check, matching what
`l7014_mosaic.py warp` already trusts for the other 437), the number is 26; this run's whole point is
that 19 of those 26 would have gone into the archive **wrong** — 14 failing outright, 5 with no way
to tell — on a check that cannot see it.

## 5. What is not established

- **Whether the 9 no-signal edges are truly featureless or the detector's blind spot.** Nothing here
  distinguishes "this stretch of border genuinely has no road, river or contour dense enough to
  classify" from "the classification/window parameters (±250 m span, 200 m along-edge strip, 3-bin
  run) are too narrow for this terrain." A wider `PROFILE_SPAN_M` or a lower `RUN_BINS` was not tried
  against a labelled case, because there is no ground truth for these 74 sheets to try it against.
- **The check only measures the normal-direction gap at sampled points, not a fitted transform.**
  Seven points per edge, median-combined; it does not attempt to recover *what* affine error produced
  a given offset (scale, shear, rotation) the way `6530-3`'s bimodal result hints one sheet has. A
  per-sheet fit over all its measured points would say more and was not built.
- **`cmd_sweep` has no guard against two concurrent runs.** Both the parallel (`--jobs 4`, which
  deadlocked — see below) and serial paths write `autoplace-detect.json`/`autoplace-sweep.csv` only
  once, at the very end, keyed by nothing but their own fixed path. Two runs racing — which is
  exactly what happened partway through this task (a stray `--jobs 1` run this record's `sweep`
  output actually came from, started outside this script's own invocation, plus a redundant `--jobs
  4` attempt) — means whichever finishes last wins, silently, with no check that the other's result
  was even for the same input. Worth a lock file or a distinct output path per run; not fixed here.
- **The `--jobs 4` (`ProcessPoolExecutor`) path deadlocks under GDAL's PDF driver.** Confirmed
  directly by the coordinator on two separate runs (pid 36874, then pid 39880): the pool's worker
  processes sit at 0% CPU with no visible progress, indefinitely. `cmd_sweep` was patched to take a
  plain serial path (`map()`, no pool) under `--jobs 1`, with a comment recording the cause as the PDF
  driver rather than the executor (a bare `ProcessPoolExecutor` and importing this module both work
  fine in this environment). The parallel path is left in the script, unfixed, for anything that does
  not render PDFs concurrently.
- **`lattice_err`'s own baseline (~10 m median, up to ~95 m for a few sheets) is folded into every
  offset here**, because the neighbour's measured stopping point is *its own* true border, not the
  idealised lattice cell. A "perfect" candidate would therefore not read as exactly 0 m even in
  principle — the 25 m pass line already has to absorb that baseline, which is presumably why the
  series' own drafting accuracy (25 m) is wider than the lattice's (~15 m, per
  `l7014_mosaic.LATTICE_TOL`'s comment).
- **The EPSG:3857 finding (§3) and the `ground_aspect`/`corners.csv` gap (§1)** are both corrections
  to the task's own premises, not to this script's results — carried here rather than worked around,
  per the brief's own instruction.
- **The first (abandoned) cross-correlation design is not merely "less accurate"** — it is
  demonstrated wrong (negative correlation at the true zero-shift case), and its FAIL-everything
  output should not be read as "these sheets are all badly placed"; it is read as "raw grayscale
  correlation across a real/blank-margin boundary has no signal to find," full stop.

## Artifacts

`scripts/l7014_autoplace.py` (self-checked) · one added parameter on `scripts/l7014_neatline.py`
(`corners(..., gate=None)`, default behaviour unchanged) · `regen/autoplace-detect.json` ·
`regen/autoplace-sweep.csv` · `regen/autoplace-placed.json` · `regen/autoplace-seams.csv` ·
`regen/autoplace-summary.json` · `cogs-auto/` (26 `.tif`, the placement) · `cogs-check/` (26 `.tif`,
unclipped, diagnostic only) · `cogs-ref/` (48 `.tif`, corrected-warp neighbours, scratch — never
`cogs/`).
