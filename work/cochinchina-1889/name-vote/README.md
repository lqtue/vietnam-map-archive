# Name-vote on the Cochinchina plates — rule set before any fit

Question: can printed village names place a plate where river ink could not? Sa Đéc first (river-match
failed it, ratio 0.947). One plate, one number. A fail is a result.

Serves bet 3, feeds 1c (`docs/NOW.md`). **Kill:** Sa Đéc fails the rule below → name-vote is parked and
the seven failed plates go to hand points in the Allmaps editor. **If it passes:** the same code and
parameters run on the other six, no per-plate tuning.

**Written and committed before the OCR was read and before any fit.**

## Method

* **Names off the plate:** `ocr.py batch --map-id <id>` (Gemini, local files only, no `--db`), once.
  Keep labels with confidence ≥ 0.5 and 2+ letters. Drop words that name a line, not a place
  (Rạch, Kinh, Sông, Route, Arrond, Fleuve, Canal, Rivière, Chemin, Enclave).
* **Names on the ground:** OpenStreetMap `place` nodes (city, town, suburb, village, hamlet, locality)
  from the Geofabrik Vietnam extract of 2026-10-21, inside the plate's `config.json` `bbox`. Both
  `name` and `name:vi`.
* **Match:** lower case, tone marks and `đ` stripped, prefixes ấp / xã / thôn / phường / thị trấn /
  khóm / làng removed, then exact equality. No fuzzy match in this first run.
* **Model:** the river-match similarity (`river_match.model`): scale from the printed 20 km bar,
  turn from `north_deg`. Search turn ±10° (step 1°) and scale ±10 % (step 0.02), then the fine pass
  (turn ±1.5°, step 0.25). The plate's mask centre must lie within 30 km of `prior`, as before.
* **Vote:** for each (turn, scale) every label–node pair of the same name votes for one shift. Votes go
  into 1 km bins. A label counts once per bin. A name that has k nodes in the bbox weighs 1/k, so
  "Tân Hưng" (dozens of nodes) cannot outvote a rare name. Score = best bin, summed over its
  3 × 3 neighbours.
* **Held-out checks:** `river-match/plates/<slug>/check.csv`, unchanged. Held out by place, not by
  name (some checks sit on a different label than the town's name, e.g. Cao Lãnh on the Mỹ Trà
  market): every OCR label whose centre lies within 2 km of a check's plate pixel (2000 m /
  m-per-px, about 230 full-res px), and every OSM node within 2 km of a check's ground point, is
  removed before voting. Amended before the OCR was read; it was first written as exclusion by name.

## Pass rule (fixed now)

A plate **passes** only if all hold:

1. coarse ratio `second peak (> 5 km away) / best` **< 0.70**, as in river-match;
2. held-out **median error ≤ 1000 m**;
3. **at least 3** checks, and **at least 8** distinct labels inside the best bin (fewer: "too few names",
   no verdict).

Only a pass goes to Allmaps. Fit GCPs take their ground from the fitted similarity; they carry the
placement and are not independent evidence. Only the held-out checks are.

## Known limits (said now, not after)

* Many of these villages were renamed or merged after 1889; some plate names will have no node.
  The test counts what matches, and does not repair the rest.
* OCR on Vietnamese tone marks is imperfect; tones are stripped, but a wrong base letter loses the name.
* Rule 1 reuses the river-match ratio; with name votes it measures how much better one shift is than
  the best far-away shift.

## Amendments made after reading the OCR counts, before any fit

The Sa Đéc OCR (`ocr/sa-dec.all_extractions.json`, one run, `name-vote-sadec-1`, 200 labels after dedup:
115 `place`, 45 `hydrology`, 21 `legend`, 9 `title`, 6 `institution`, 4 `other`) was read for category
counts and a few lines only. Added to the rule:

* Only labels with `category == "place"` vote. Drop any whose text ends in `...`, or contains
  ARRONDISSEMENT or ARR (the OCR gave fragments of the arc titles as `place`).
* OSM places: `osm-places-261021.csv`, from `ogr2ogr -f GeoJSONSeq … vietnam-261021.osm.pbf points
  -spat 104.5 8.5 107.6 11.7 -where "place IN ('city','town','suburb','village','hamlet','locality')"`
  (Geofabrik Vietnam extract downloaded 2026-10-21); `name_vi` is `name:vi` where tagged.

## Result: Sa Đéc, run once — **fail**, name-vote parked

101 labels voted (115 `place` less fragments and the check zones); 38 of them have a same-name OSM node.

| Number | Value | Rule |
|---|---|---|
| Coarse ratio (second / best) | 0.614 (3.5 / 5.7) | < 0.70: met, but on a best score of 5.7 |
| Distinct labels agreeing within 1 km | **2** | ≥ 8: **failed** |
| Held-out median (4 checks) | **1822 m** (280, 1492, 2153, 2373) | ≤ 1000 m: **failed** |

So the kill result applies: **name-vote is parked**; the seven failed plates go to hand points in the
Allmaps editor (or the chaining test with a person picking the tie points).

What the number says: the old village names on this plate mostly have no same-name node in OSM
(63 of 101 labels have none), and the common names (Tân Hòa, Phú Thạnh…) have many nodes that spread
the vote. Fuzzy matching, or a 1880s name list instead of OSM, were not tried: the rule said exact
match, and changing it after this result would be tuning to pass. If name-vote is reopened, that is a
new test with its own rule, not a rerun of this one.
