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

## Allmaps

`push.mjs` pushes annotations to live.allmaps.org only (no VMA write), skipping an image Allmaps
already holds; `--update` PATCHes pushed maps and overwrites any editor edits, so compare first with
`allmaps.mjs`'s `differences()`. Map ids: `allmaps-ids.json`. `serve.py` is the CORS static server
that put the series manifest behind a Cloudflare quick tunnel for the editor.
