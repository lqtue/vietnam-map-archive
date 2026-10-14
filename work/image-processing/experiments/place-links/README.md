# Place links, 1882 Plan Cadastral (offline prototype)

Part of the **entities** layer — see [ATLAS](../../../../docs/ATLAS.md).

Machines suggest "what stands here today" for each place-naming label; a person confirms; every verdict
records its time and the exact candidate list it judged. Map `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`.

    python3 work/image-processing/experiments/place-links/build.py            # items.json, candidates.csv, score.json
    python3 work/image-processing/experiments/place-links/confirm.py          # review page, http://127.0.0.1:8792
    python3 work/image-processing/experiments/place-links/confirm.py --self-check
    python3 work/image-processing/experiments/place-links/review_items.py     # items for the web review page (docs/plans/review-page-plan.md); then work/review-kit/review_sync.py push
    python3 work/image-processing/scripts/name_today.py --self-check

Everything written goes to `work/image-processing/results/prior/0e02…/place-links/` (gitignored):
`items.json` `candidates.csv` `score.json` `session.json` `verdicts.jsonl` `spot/`.

## Predictions, written 2026-10-12 BEFORE the first scoring run

Independent reference: `landmarks.csv`, rows that have a 1882 label (`name_1882` non-empty): 14. Controls
within 30 m of a GCP are `in_fit` and leave the accuracy numbers.

| quantity | predicted |
|---|---|
| landmark rows with a matched in-scope label | 13 of 14 (the "Place de la Cathédrale" label may sit in another category) |
| of those, `in_fit` | 2 |
| scored n | 11 |
| hit@1 | 5/11 (45%) |
| hit@3 | 7/11 (64%) |
| labels with no candidate in 150 m | 2 (`old-marche-central`, which moved; `ba-son`, 168 m from its outline) |

Reasons: the 1968 dev set gave 18/27 (67%) in-sample, an independent set on a sheet with an 11.5 m
fit and French-only labels should do worse; the owner's "moved" and "same site, new building" rows are
exactly where a radius search cannot or should not hit.

## Arms and order

- Order: random permutation of the item ids, seed recorded in `session.json`. Not sorted by score.
- Blind arm: a fixed random 20% of the items **that have at least one candidate**, seed recorded. Items with
  no candidate are a third arm (`nocand`), shown the same way (nothing to show). Sampling among items with
  candidates is deliberate: a blind item with nothing to hide says nothing about agreement with the machine.
- `session.json` is written once and refuses to change if the items change (hash), so the arm of an item
  cannot drift between sittings. `--new-session` moves it aside.

## Verdict line

`verdicts.jsonl`, the `review_record` contract, task `place-link`, `item_id` = `ocr_labels.id`:

    bound           hash of {label id, label px, the machine's top-3 list, radius} + method version
                    (name_today git blob hash + place-link-v1)
    proposal_shown  true only when candidates were on screen
    verdicts        {arm, pick (1-3 | null), pick_via (candidate|search|null), relation, target{source,id,name,lng,lat,...}}
    relation        same_building | same_site_new_building | moved | gone | none | unsure
    undo            appends a line with verdicts {"undone": true}; consumers drop those items' undone lines
                    (the last line for an item wins, so an undone item is simply not decided any more)

Idle gaps: `review_record.sittings` drops items longer than 300 s and counts them.

## Known limits

- Candidate pool = HCMC topo `label_congtrinhs` (TASCO, 2023; the owner treats it as public, 2026-10-12) +
  cached Overpass named features. Cached OSM relations have only a bounding box, except 3 with full outlines;
  those distances are to the box (`approx` in candidates.csv).
- A radius search cannot find a place that moved (Marché Central -> Chợ Bến Thành); those are reviewed as
  `moved` / `gone` by hand.

## First run, 2026-10-12 (predictions above were fixed before it)

| quantity | predicted | got |
|---|---|---|
| landmark rows with a matched in-scope label | 13 | 14 |
| `in_fit` | 2 | 0 (no label, and no matched modern outline, within 30 m of a GCP) |
| scored n | 11 | 14 |
| hit@1 | 5/11 | 13/14, 92.9% [69-99] |
| hit@3 | 7/11 | 13/14, 92.9% [69-99] |
| no candidate in 150 m | 2 | 0 (`old-marche-central` has 9 candidates and none is the successor market: a miss, as `moved` should be) |

Far above the prediction, and not to be read as accuracy: the 14 rows are the landmarks that have a
polygon in the OSM cache and an OCR label sitting on it, so label-to-outline distance is ~0 by
construction. Nearest-outline alone scores 12/14 (85.7% [60-96]). Name and kind add one (Gia Long). A
harder reference needs labels that were not chosen because they sit on a known footprint: the blind arm.

Dev set (not accuracy): `name_today.py --eval` on the 27 legend_finds, topo only, was 18/27 hit@1, 20/27
hit@3 before the kind fix and is 18/27, 21/27 after (Chi Lăng Park left the Park Hyatt, hit@1 unchanged).
