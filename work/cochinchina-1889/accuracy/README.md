# Cochinchina placed plates: a tighter placement and a tighter mask — rules before any run

Question: can the four plates that passed river-match (Mỹ Tho, Vĩnh Long, Bến Tre, Gò Công) be placed
and cut more accurately than one similarity and a wash-edge mask? Serves bet 2 (measured gates),
`docs/NOW.md`. Two independent tests. A fail is a result.

**Written and committed before any run of either test.**

## Test A — affine instead of similarity (Bến Tre first)

Why Bến Tre: weakest pass (median 988 m, limit 1000), and its four errors all point the same way
(1.0–1.5 km): a scale error, which a similarity cannot absorb.

* **Baseline:** `river_match.py` on Bến Tre, rerun first. It must reproduce the pushed result
  (ratio 0.552, median 988 m, 4 checks); if it does not, stop and say so.
* **Candidate:** from the baseline's fine similarity, free the 2 × 2 matrix (4 entries) and the shift
  (6 numbers). Maximise the same water-correlation score at the fine grid (75 m cells, plate at 1/8),
  Powell, entries bounded to ±5 % of the similarity's. Nothing else changes: same mask, same OSM
  rivers, same grid.
* **Checks (held out):** the 4 read by eye, unchanged, plus the **name checks**: every OCR label
  (`category == "place"`, confidence ≥ 0.5, not ending `...`) whose normalised name (the `name-vote`
  rule: no tones, no `đ`, prefixes removed) equals **exactly one** OSM place node's name inside the
  plate's bbox; the node is the ground truth. Chosen mechanically **before** any affine fit, from
  `ocr/bentre.all_extractions.json` (one Gemini run, committed). A name check can be a wrong village
  (names moved); that noise is the same for both models, so the comparison is **paired**: the same
  checks under the similarity and under the affine.
* **Pass:** at least **8** checks in all, and (1) the affine's median error ≤ **700 m**, and (2) the
  affine's error is lower than the similarity's on at least **70 %** of the checks.
* **Kill:** either fails, or any matrix entry sits on its ±5 % bound (the fit wants more than the
  rule allows). Then the placement stays a similarity, and the next step is hand points.
* **If it passes:** the same on the other three, same rule, no tuning. Nothing goes to Allmaps without
  Tue's yes; an affine placement is pushed as GCPs and read back, as before.

## Test B — mask along the printed line, half resolution

The masks come from `cc_mask.py`: the inside of the pink wash at quarter scale, eroded, simplified
with a tolerance of about 200 m. The wash lies outside the printed boundary line, so the mask rides
on the wash and shows a pink fringe.

* **Candidate:** the same method at half scale: finer morphology, simplify tolerance 2 px at half
  scale (about 35 m), so the edge follows the inner side of the wash, where the line is. No new
  inputs. Run on the four placed plates; masks land in files, not in Allmaps.
* **Score, computed the same way before and after, on the four plates:**
  1. **Neighbour overlap:** the sum, over the placed pairs, of the ground overlap of the two masks
     (each projected with its pushed GCPs). Today: Mỹ Tho/Vĩnh Long 113, Mỹ Tho/Bến Tre 259,
     Mỹ Tho/Gò Công 201, Vĩnh Long/Bến Tre 111 km² (from the wash-edge masks).
  2. **Line support:** the share of mask-edge vertices with a dark ink pixel (darker than the paper
     median by 60 grey levels) within 6 full-resolution pixels. Higher is better.
* **Pass:** the summed overlap falls by at least **one third**, and line support does not fall on any plate.
* **Kill:** either fails. Then the masks stay as pushed.
* Pushing a new mask to Allmaps (the mask changes the drawn edge only; the GCPs stay) needs Tue's yes
  and a read-back, as before.

## Limits (said now)

* Overlap between neighbours is not zero even for a perfect mask: both plates draw the shared river,
  and the placements carry 200–1000 m of error. The test asks only whether it falls.
* 8 checks give a wide interval; the paired comparison, not the median alone, is the evidence.

## Clarification written before the Bến Tre OCR was read or any fit

A name check also needs its name to be **unique on the plate** (one `place` label with that normalised
name). Two labels of one name would map to one node, and one of them is a wrong village by
construction. Labels filter as in `name-vote/README.md` (category `place`, confidence ≥ 0.5, no `...`,
no ARR, no line words). The Bến Tre run is `accuracy-bentre-1`, one pass, default settings. Scratch
(quarter-res JPEG, OSM rivers) is rebuilt as in `river-match/plates/README.md`; the OSM rivers for
this test come from the Geofabrik extract of 2026-10-21, not the 2026-10-19 one used for the pushed
placement, so the baseline must reproduce within a few metres or the test stops.
