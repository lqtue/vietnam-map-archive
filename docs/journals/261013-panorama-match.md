# 261013 — can the 1881 Favre engraving be pinned to the map?

**Question.** Can one geometric transform carry a point on Favre's 1881 engraving *Saïgon d'après
nature* (Gallica `btv1b53062212t`, sourced in [260921](260921-panorama-sourcing.md)) to the ground
within a block width? Kill rule, set before scoring: median leave-one-out error above ~60 m under
both a projective and a local fit means stop. The 60 m is a rough block width, not a derived figure.

**Answer.** No. The projective median is **131 m** and the thin-plate-spline median is 146 m, both more
than twice the limit. The error is not even: about **71 m** where a point sits inside the other
points' hull, **164 m** outside it. The artist compressed the edges. A single camera does not fit
either. The engraving is not one perspective.

**So what.** No bet moved. The pin-a-point tool is killed by its own rule. The engraving can still
show *an area* with its error drawn honestly, but that use was found after the kill, so it is an
idea for the gate, not a pass. The two follow-up tests below are parked, not started.

## What was done

- **Ground points.** `points.py` writes 17 street corners that existed in 1881 and still exist, read
  off the modern street layer already aligned to the 1882 sheet (`points.csv`). Check: the
  cathedral footprint lands on the cathedral.
- **Image points.** Gallica blocks scripted access and the Allmaps editor won't open plain-http
  images, so the owner placed **16 points by hand** in the Allmaps editor on Gallica's IIIF feed
  (`favre1881-tue.gcps`). They are the owner's own choice, not the 17 above. Only about 6 fall within
  30 m of a `points.csv` corner. A first set of six machine guesses gave a misplaced quay in an
  overlay (four sat on one street) and was dropped.
- **Pixel space.** The overlay page uses the Wikimedia Commons copy (10717 × 7527), a bot upload of
  the same Gallica item. It is assumed to share Gallica's pixel space from size and source, with no
  pixel-level check. The owner's local scan (10601 × 7443) is a different pixel space.
- **No prediction.** The plan asked for a predicted error before scoring. None was written.

## Numbers

Leave-one-out over all 16 points: each dropped in turn, the transform fitted to the other 15. No
outliers dropped. Only the projective row comes from `score.py`; the rest were one-off runs.

| Fit | Median held-out (m) | Note |
|---|---|---|
| Projective | **131** | max 357 m, in-fit RMS 109 m (`score.py`) |
| Thin-plate spline | 146 | scipy `RBFInterpolator` |
| 2nd-order polynomial | 163 | |
| Affine | 171 | |

Inside / outside, one-off and chosen after the fact: a point is "inside" when it lies within the
convex hull of the other 15 on the ground. Inside (lines 1–5, 7, 10, 13, 14) median 71 m; outside
(6, 8, 9, 11, 12, 15, 16) median 164 m. Worst: line 8 (971, 3763), far left on the Arroyo Chinois
side, 338 m projective. Line numbers follow the `.gcps` file, 1-based.

**Camera fit**, one-off and not saved: a homography with the principal point at the image centre
gives two focal estimates that disagree, 2,216 and 3,737 px (the nine inside points alone give 4,861
and 0). Drop-one ranges: viewpoint over Thủ Thiêm, looking 292–296°, height 915–1,079 m, tilt 57–62°
down, horizontal FOV 115–125°. The fitted camera puts the horizon off the top of the sheet; the
painted horizon (y ≈ 1260) was read by eye. Heights therefore cannot come from one camera. If ever
wanted, they must come from local ratios on buildings with known storeys, given as storey ranges,
never metres.

## The two-pane page

`index.html` (served by `serve.py` on port 8794) shows the engraving and the map side by side.
Clicking either side draws a red patch on the other whose size is the local error. The patch uses the
thin-plate-spline leave-one-out errors, computed in the page, not the projective ones.

## Parked tests

Neither has a bet. Reopen only by putting one through the gate in `NOW.md`.

1. **Footprint linking.** Add corner points around the cathedral blocks, link ~30 footprints by
   order along each street front, and time each. Kill if under 50% can be confirmed.
2. **Storeys.** Measure ~30 drawn buildings, 10 with known storeys. Kill if drawn heights predict
   storeys no better than calling every building one storey.

## Files

Uncommitted, in `work/image-processing/experiments/panorama-match/`: `points.py`, `points.csv`,
`favre1881-tue.gcps`, `score.py` (pass/kill against 60 m; self-check passes), `index.html`,
`serve.py`. Tiles (Commons copy, 29 MB) are in the gitignored
`work/image-processing/results/panorama-match/favre1881/`.
