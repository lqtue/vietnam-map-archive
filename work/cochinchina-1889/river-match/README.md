# Mỹ Tho plate (1885): placed by its rivers, no graticule

**Question.** Can a Cochinchina arrondissement plate that prints no graticule be placed
automatically, by sliding its rivers over OpenStreetMap's?

**Answer.** Yes, on this plate. The best placement is clearly ahead of any other more than 5 km
away: the runner-up scores 0.61 of it. Four towns placed by eye before the fit, and not used by it,
land 183, 467, 499 and 968 m from their OpenStreetMap positions. The median is **483 m**, under the
1 km kill line.

**So what.** This moves bet 3 (a corpus to link against). The 11 plates with no graticule have a
way in that needs no person at the map, and Mỹ Tho is the first of them. The next step is to run
the same script on a second plate, before treating it as a pipeline.

## Method

`river_match.py`, reads only:

* **Scale** comes from the printed bar: 20 km = 2329 px at full resolution, so 8.59 m/px. It is
  searched ±10 % and lands at 1.000.
* **Plate signal.** The blue-grey ink (b − r > −15 at quarter resolution) is the river banks and
  small rivers. It is kept inside the arrondissement outline (`../allmaps-drafts/`), widened by 2 km
  so the boundary rivers count, then made zero-mean.
* **OSM signal.** These are `natural=water` + `water=river` outlines (ways and multipolygon
  relations) and `waterway=river` centrelines, for 9.9–11.0 N, 105.5–107.0 E. That is one cached
  Overpass response (22 MB, not in the repo).
* **Search.** The model is a similarity. Rotation runs ±10° and scale ±10 %; the plate centre must
  sit within 30 km of Mỹ Tho; every shift is scored at once by FFT correlation. The coarse pass uses
  150 m cells and steps of 1° and 2 %. The fine pass uses 75 m cells and steps of 0.25° and 0.5 %
  around the best.
* **Result:** rotation −4.0°, 8.587 m/px.

## Numbers

| | |
|---|---|
| best score (coarse) | 1471.7 |
| best score more than 5 km away, any rotation/scale | 893.4 (ratio 0.607) |
| Mỹ Tho town | 499 m (E +381, N −322) |
| Chợ Gạo market | 968 m (E +910, N −328) |
| Cai Lậy market | 183 m |
| Cái Bè market | 467 m |
| held-out median / max | **483 m / 968 m** |

## Why not to over-read it

* The checks are town centres. A town is not a point: the plate's market and the OSM `place` node
  can differ by a few hundred metres for that reason alone. The four were placed before any fit was
  run (`points/check.csv`).
* Three of the four errors point east (+380 to +910 m). That looks like a small scale or rotation
  bias that a similarity cannot absorb; an affine or a spline from more points might.
* Rivers move. The Tiền's banks and islands have shifted since 1885, and the match is a best
  average over them.
* This is one plate, with a big distinctive river. Plates whose rivers are small or straight
  (Long Xuyên, Sa Đéc's plain) may not give a clear peak.
* `points/fit.csv` holds 11 GCPs at plate river pixels whose ground comes *from the fitted
  transform*. They carry the placement into Allmaps and are not independent evidence.

## Files

* `river_match.py`: the search, the checks, the GCPs, the annotation and `overlay.jpg`.
* `points/check.csv` (role `check`), `points/fit.csv` (role `fit`), `points/summary.json`.
* `ff6489cd-b5fe-4dea-9513-5468f5972eb3.json`: an Allmaps annotation with 11 GCPs, a first-order
  polynomial, and the outline mask from `../allmaps-drafts/`. It is **not** pushed to Allmaps or
  written to VMA.
* `overlay.jpg`: OSM river outlines in red, drawn through the fit onto the plate. Black crosses are
  the plate check points; green circles are where OSM puts those towns.

```bash
work/ocr/.venv/bin/python work/cochinchina-1889/river-match/river_match.py \
  --med <quarter-res plate JPEG, 3799x2292> --osm <osm_water.json>
```
