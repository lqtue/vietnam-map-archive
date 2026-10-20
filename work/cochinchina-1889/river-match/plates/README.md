# River-match on the other ten Cochinchina plates — rule set before any fit

Question: does the Mỹ Tho result hold on plates that print no graticule? Same search, same
parameters, no per-plate tuning. A fail is a result.

**Written and committed before any plate was run.**

## What was read off each plate (before the fit)

* `bar_med_px`: the printed 20 km bar, in quarter-resolution pixels (±3 px, about ±0.5 %).
* `north_deg`: how far the sheet is turned clockwise, from the north arrow or the side labels
  (NORD/OUEST/…). Sa Đéc and Long Xuyên 90°, Trà Vinh −39°, Sài Gòn −22°, the rest 0°. The search
  covers ±10° around it.
* `prior` + `prior_on: mask`: a gazetteer-level centre of the arrondissement (province centre).
  The centre of the plate's mask must lie within 30 km of it. (Mỹ Tho bound the image centre.)
* `check.csv`: 2–4 towns placed by eye on the plate, with the OSM `place` node of the same name.
  Candidates came from OSM town names whose position, predicted from the chef-lieu, the bar and
  the north arrow, fell on a legible label. No fit was run to choose them.
* `mask`: the Allmaps draft mask. Saigon, Biên Hòa, Chợ Lớn and Long Xuyên have a neatline box
  (outline not separable), so title, legend and bar ink can enter the signal. They run anyway.

## Pass rule (fixed now)

A plate **passes** only if all hold:

1. coarse ratio `second peak (>5 km away) / best` **< 0.70** (Mỹ Tho: 0.607);
2. held-out **median error ≤ 1000 m**;
3. **at least 3** checks. A plate with fewer cannot pass; it is reported as "no verdict".

Only passes are pushed to Allmaps, one at a time, and read back. Water fraction inside the mask
is reported as a sanity number, not tuned on. OSM data: Geofabrik Vietnam extract of
2026-10-19 (Overpass was unreachable), `natural=water` + `water=river` polygons and
`waterway=river` lines; the Mỹ Tho run through this path gives the same ratio and errors as the
Overpass run.

## Results (run once, same parameters on every plate)

| Plate | Mask | m/px | Turn° | Ratio | Median m | Max m | Checks | Water in mask | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Mỹ Tho (earlier run) | outline | 8.59 | −4.0 | 0.607 | 483 | 968 | 4 | n/a | **pass** |
| Vĩnh Long | outline | 8.46 | −2.0 | 0.442 | 215 | 329 | 3 | 0.041 | **pass** |
| Bến Tre | outline | 8.70 | 1.25 | 0.552 | 988 | 1488 | 4 | 0.053 | **pass**, barely: the median is 12 m under the line |
| Gò Công | outline | 8.33 | −1.0 | 0.619 | 440 | 557 | 3 | 0.203 | **pass** |
| Sa Đéc | outline | 8.56 | 85.0 | 0.947 | 924 | 2351 | 4 | 0.042 | fail (ratio) |
| Trà Vinh | outline | 8.59 | −44.25 | 0.918 | 1325 | 2795 | 4 | 0.014 | fail (ratio, median) |
| Long Xuyên | box | 8.50 | 87.0 | 0.812 | 863 | 1027 | 3 | 0.018 | fail (ratio) |
| Sài Gòn | box | 8.39 | −26.25 | 0.812 | 379 | 628 | 3 | 0.010 | fail (ratio) |
| Bà Rịa | outline | 9.61 | 9.75 | 0.972 | 28217 | 29673 | 4 | 0.123 | fail: scale and turn at the search edge, 28 km off |
| Chợ Lớn | box | 9.27 | 3.25 | 0.977 | 23000 | 25327 | 4 | 0.012 | fail: scale at the search edge, 23 km off |
| Biên Hòa | box | 8.50 | −4.0 | 0.702 | 1350 | 2305 | 2 | 0.022 | fail (ratio 0.702, 2 checks: no verdict) |

**4 of 11 pass** (Mỹ Tho, Vĩnh Long, Bến Tre, Gò Công). All four have an outline mask, a large
river or coast, and a plate that is mostly land with long river banks.

* The failing plates are not near misses on distance only. Sài Gòn and Long Xuyên put their
  towns 0.4–0.9 km from where they were read, yet the best peak is not clearly ahead of the
  runner-up (0.81). The rule asks for both, and a placement with no clear winner cannot be told
  from a lucky one.
* Long Xuyên, Sa Đéc and Trà Vinh are wetland or flat plates: the plate's blue ink is hatching
  (Plaine des Joncs, U Minh), not river banks, so the signal is mostly not rivers.
* Bà Rịa and Chợ Lớn are rejected twice: no clear peak, and an answer 20 km+ off. The search
  ran to the edge of the scale range there, a sign the peak is false.
* The four neatline-box plates (Sài Gòn, Biên Hòa, Chợ Lớn, Long Xuyên) all fail; title and
  legend ink in the box may hurt. This run cannot separate that from the plate itself.
* Check quality varies: some are labels, not points (see each `note`), and Bến Tre's four
  errors all point the same way (1.0–1.5 km), which looks like a scale error of the plate, not
  noise. It passed on the rule as written, and the rule was not moved.

Pushed to Allmaps (PATCH, read back equal): Vĩnh Long, Bến Tre, Gò Công, and Mỹ Tho earlier.
Nothing was pushed for the failing plates. `points/fit.csv` GCPs take their ground from the
fitted similarity; they carry the placement, they are not independent evidence.

OSM data came from the Geofabrik extract, not committed. To rebuild: download
`vietnam-261019.osm.pbf`, then `ogr2ogr -f GeoJSONSeq` for `multipolygons` where
`natural='water'` and `other_tags` has `"water"=>"river"`, and `lines` where `waterway='river'`,
clipped to each `config.json` `bbox`.
