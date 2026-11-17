# Tonkin 1950 administrative atlas: georeference from the printed graticule

*Bản đồ hành chính các tỉnh Trung Châu Bắc Việt* (Sở Địa-Chính Bắc-Việt, 1950, 1:100 000; David Rumsey
Historical Map Collection via Wikimedia Commons, public domain). 15 rows: 11 map sheets in a 4×3 grid
(Phủ Nho Quan, the twelfth, is not in the scan set), plus cover, legend, sheet index and composite.

**Question.** Can the 11 sheets be placed without a person clicking points?
**Answer.** Yes. The faint grey grid on every sheet is a 0.2-grade graticule counted from the Paris
meridian. Its crossings are found automatically, 5–9 per sheet, with affine residuals of 1–5 px at
quarter resolution (25–125 m).
**So what.** Bet 3 (corpus to link against) gains a placed 1950 commune-level map of the delta. It is the
name key parked behind bet 1c (admin units for all of Vietnam).

## Method

1. `frame.py`: neatline of each sheet (long thin dark lines on paper, tilt-tolerant), on quarter-res images.
2. `tk_fit.py`: a draft series grid (one sheet = one cell) fitted on 9 hand-placed points on three sheets
   (Long Biên bridge, Bắc Ninh citadel, Đáp Cầu; Phủ Lý, Hưng Yên, Nam Định; Hải Dương, Hải Phòng, Thái
   Bình). Draft error about 1 km.
3. `snap.py`: predict every 0.2-grade crossing from the draft, then find the actual lines locally
   (thin-dark-line response, sheared projections, ±70 px then ±25 px around the sheet's median offset).
   This is local per crossing, so it survives the fold-out halves. Output: `crossings.json`.
4. `extents.py`: per sheet, an affine from the strong crossings (score ≥ 1.5, worst residual dropped
   until ≤ 8 px); the sheet edges in grades. Neighbours agree to 0.004–0.013 gr. Each sheet measures
   0.54 × 0.63 gr.
5. `offset.py`: graticule placement versus the 9 points: the truth sits 438 m east (±80) and 51 m north
   (±140) of it. That shift is applied series-wide. It holds the survey datum and the Paris/Greenwich
   ambiguity together. Paris- and Greenwich-based 0.2-grade lines here are only 290 m apart, so this
   data does not decide which meridian was used.
6. `build_tk.py`: GCPs = the crossings; mask = one shared series frame (columns at 114.36 / 114.90 /
   115.44 / 115.978 / 116.524 gr, rows at 23.941 / 23.307 / 22.677 / 22.046 gr) projected through each
   sheet's own fit, so neighbouring masks meet exactly. Transformation: first-order polynomial.
   **The mask itself was wrong** (30-320 px off the printed edge: the affine extrapolates, and each
   fold-out's halves lie at different angles). The masks of record are Tue's hand edits of all 11
   sheets in Allmaps (2026-10-21), saved in `annotations-live/`.
7. `neatline.py`: the printed edge found by machine, for sheets nobody has edited. Thin dark line with
   paper on both sides (a ridge), tilted, innermost strong line (a black bar or an outer frame can sit
   outside the neatline), each fold-out half on its own: a 6-point mask in `masks.json`; an edge
   below `MIN_COVER` goes to a person. The red, blue and brown plates print their own corner marks
   10-26 px outside the black neatline (misregistered plates); the black line is the edge.
   `score.py` scores it against the hand edits. Against Tue's 10 edits of those sheets, 9 are within 15 px
   at all four corners; Hưng Yên bottom-right is 19 px off (the detector is the worse by eye). It
   sits about 6 px above Tue's bottom edge on average. Vĩnh Bắc Việt: no mask (blank sea).
   The edge of 4 of the 10 was tuned on (`INNER_MIN` after An Châu); 6 were unseen.

Run: `SERIES_WORK=<dir with thumbs/, med/, rows.json> work/ocr/.venv/bin/python work/tonkin-1950/build_tk.py`.
`snap.py` and `extents.py` regenerate `crossings.json` and `extents.json` the same way.

## Checks (not in any fit)

| Town | Error |
|---|---|
| Ninh Bình | ~50 m |
| Hòa Bình | ~350 m |
| Việt Trì | ~1.3 km: placed by its label, not the town symbol, so a weak check |

The town coordinates are from memory, not a gazetteer. Read these as a sanity check, not as accuracy.

## Seams (2026-10-21, `seams.py`)

**Question.** With every mask on its printed edge, do neighbouring sheets meet on the ground?
**Answer.** No. Placed through each sheet's own order-1 fit, neighbouring edges miss by 0-560 m (gap or overlap) and
slide 0-300 m along the seam. A single atlas-wide scale (one x and y scale, per-sheet rotation and shift) did
not help: control-point residuals rose to 337 m (own fit: 129 m), leave-one-out error rose (median 137 m against
96 m), seam rms 354 m against 322 m. Printed frames differ in size by up to 2 per cent (49.2-50.7 km wide), so
no uniform scale tiles them; paper distortion or unequal frames, not told apart.
**So what.** Each sheet is right on its own to about 0.1-0.3 km; the mosaic is not seamless. More grid points are not
available (two vertical grid lines per sheet). Only ties between neighbours (hand-placed points at the same
road or river on both sides of a seam) add information.

## Modern railway as a witness (2026-10-21, `railoff.py`)

**Question.** Is the seam gap a placement error or an error in the 1950 map?
**Answer (one sheet, not yet a seam).** The Hà Nội - Hải Phòng railway (OpenStreetMap, via the public Overpass servers) lies
wholly inside the Hải Phòng sheet. Placed through that sheet's own control points, the printed line sits south of the
modern one by about 440 m at the west end, about 0 in the middle, and 150-280 m in the east, with 100-250 m of jitter over
a few km that this test cannot split into map error and detector error. The railway is a thick grainy black band; a
thin-line detector latches onto the "+" boundary lines, a black-density detector does not.
**So what.** One sheet cannot separate placement error from map error; both show as an offset from modern ground. A line
that crosses a seam can. Fit on part of a modern witness and score on points held back.

## The frame in grade (2026-10-21, `grid2.py`, `frame2.py`, `overlap.py`)

**Question.** Do neighbouring sheets share a frame in grade, measured from the printed grid?
**Grid tracking, fixed.** The grid is cyan, so it shows on the red channel (strength 40-70 against 6 for the next peak),
not on blue minus red. `grid2.py` finds the lines over the whole sheet with a tilt search, traces each fold-out half on its
own, and gates each sheet (lines straight to 60 m, equal spacing). 9 of 10 sheets pass; Ninh Bình's left half is marginal
(74 m). An earlier tracker used seeds up to 35 px off and a +-25 px window, and its numbers, including a "top row 0.3-1.0
km off its neighbours" claim, were wrong.
**Measured frames.** From the nearest line, the top-row sheets end 0.3-1.9 km north of the sheets below them, and rows 1-2
overlap by about 0.7 km (Hưng Yên over Ninh Bình, Hưng Yên beside Hải Phòng).
**The check that could fail, failed.** An overlap of 0.7 km means the same ground is printed on both sheets. Matching
Hưng Yên's last 32 rows inside Ninh Bình's top, over +-3 km, found nothing (best 0.40, scattered offsets, 0 of 9 strips). So
the frames as measured are not right to better than about 0.7 km.
**So what.** Do not use frame gaps or overlaps from the grid. The distance from a grid line out to the frame edge (10-14 km,
extrapolated with the inner spacing) carries an error of at least 0.7 km; the cause is open (local stretch near the margin,
or the grid origin differs from sheet to sheet). The grid places a sheet's middle well. Seams and edges need a witness that
is not the grid: hand-placed ties across a seam, or a modern line that crosses it.

## Allmaps

`push.mjs` pushes annotations to live.allmaps.org only (no VMA write), skipping an image Allmaps
already holds; `--update` PATCHes pushed maps and overwrites any editor edits, so compare first with
`allmaps.mjs`'s `differences()`. Map ids: `allmaps-ids.json`. `serve.py` is the CORS static server
that put the series manifest behind a Cloudflare quick tunnel for the editor.
