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
* **Held-out checks:** `river-match/plates/<slug>/check.csv`, unchanged. Any label or node whose
  normalised name equals a check town's name is removed before voting, so the checks stay held out.

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
