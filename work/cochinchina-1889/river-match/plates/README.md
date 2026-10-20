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
