# OCR eval baseline

Gate for step-3 (neighbor-window batching) and any future core-loop change.
Regenerate: `eval.py ocr --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b --run-id <run>`.

**Ground truth:** 43 human-validated extractions, map `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`, source run `v1b`. This is a *partial* subset of the true labels, not exhaustive.

> **The baseline below predates the prompt-plumbing fix of 2026-09-08.** Every run in this
> file was measured while `extract_labels_sequence()` was sending its own hardcoded "1882
> Saigon cadastral map" prompt instead of `PROMPTS["v8"]` (see `docs/pipelines.md`). The
> numbers stand as the gate — the harness is unchanged — but they are *not* a measurement
> of v8. The first post-fix run has to be eval'd against them before anything else in the
> call is touched, and `char_acc` is the column to watch: the fix targets diacritics, which
> is exactly what character accuracy sees.
>
> **Measured 2026-09-08 — and the prompt the fix delivers fails the gate. See below.**

> **The 118-row trace set was never a ground truth. Corrected 2026-09-18.**
> `load_gt` selected on `map_id` alone, and `footprint_submissions` holds predictions as
> well as traces: run `seg-20260916T1632` wrote 72 `sam-auto` rows typed `building` back
> into it. So every segmentation row measured between 2026-09-16 and this correction was
> scored against 46 hand traces **plus 72 pieces of model output**. The sheet has 46
> traces — building 17 · land_plot 24 · road 3 · waterway 2 — and it always did; the jump
> to 118 was not new tracing.
>
> The 72 are worse than model output: median IoU **0.83** to their own prompt box in
> `ocr_extractions`, 60 of 72 above 0.5, each carrying the label text as `name`. SAM2
> segmented the lettering's background from OCR seeds — the failure C4 predicted for line
> features. They are label boxes typed as buildings. Control: the 17 volunteer buildings
> score 0.054 on the same measure.
>
> **What this does and does not touch.** `land_plot` is 24/24 volunteer, so every
> `land_plot` figure in this file stands exactly as printed. Every `building` figure at
> **n=89** is 81% scored against label boxes and is void; the ones that have been
> re-measured against the 17 real traces are marked below. `road` and `waterway` are
> volunteer-only and unaffected.
>
> `load_gt` now filters `source=eq.volunteer` (`seg_eval.py`), so n=89 cannot recur.
> `docs/worked-example-1882.md` counts 118 in a third sense — polygons produced, not
> traces scored against — so check the sentence, not the number.

## Baseline — run `baseline` (current default row-sequence batch), IoU ≥ 0.5

| metric | value | trust |
|--------|-------|-------|
| recall | 0.7674 | ✓ trustworthy (33/43 known-good found) |
| char_acc | 0.9808 | ✓ trustworthy (text quality on matches) |
| mean_iou | 0.7234 | ✓ trustworthy (box quality on matches) |
| precision | 0.2276 | ✗ **not** trustworthy — GT is partial, so correct preds absent from GT count as false positives |
| raw → deduped | 174 → 145 | 29 cross-tile dupes collapsed |

## Prompt plumbing fix: v8 on the row-sequence path — REJECTED as the default (2026-09-08)

`ed92e484` made the row-sequence call send the prompt the run selected instead of a
hardcoded fallback (see `docs/pipelines.md`). Correct as plumbing. But the prompt it now
delivers — `PROMPTS["v8"] + sequence_frame_rules(n)` — scores worse than the fallback it
replaced, on the same sheet, same model (`gemini-3-flash-preview`), same tiling
(2400/300/1024, 30 tiles, 10 row calls), one variable.

Both runs scored from their run directories via `--pred-run-dir`, so this is like-for-like.

| metric | baseline (fallback prompt) | postfix-v8 | Δ |
|--------|---------------------------|------------|---|
| recall @ IoU≥0.5 | 0.7674 | 0.6279 | **−0.14** |
| char_acc | 0.9793 | 0.9519 | **−0.027** |
| mean_iou | 0.7234 | 0.7355 | +0.012 |
| predictions | 145 | 204 | +59 |
| diacritic_rate | 0.331 | 0.3039 | −0.027 |

**The recall loss is box geometry, not missed labels.** Sweeping the threshold separates them:

| IoU≥ | baseline recall | postfix recall |
|------|-----------------|----------------|
| 0.3 | 0.8140 | 0.8140 |
| 0.4 | 0.7907 | 0.7442 |
| 0.5 | 0.7674 | 0.6279 |
| 0.6 | 0.6512 | 0.4651 |

Equal at 0.3 and diverging as the threshold tightens: the labels are found, their boxes
agree with ground truth less well. v8 asks for more and tighter extractions — mean box area
drops 72,575 → 50,877 px², single-word labels rise 12% → 19%, mean words per label 3.09 →
2.79 — and the ground truth was drawn around whole assembled names, so a tighter or split
box slides under the threshold. Four of the eight labels lost at 0.5 have a correct-text
prediction sitting at IoU 0.34-0.50 (`MAGASINS A PÉTROLE`, `CASERNES` are character-exact).
`mean_iou` rising while recall falls is the same fact seen from the other side.

**`char_acc` is the loss that is not an artefact.** It is down ~2.7 points at every
threshold, and the fix was supposed to move it the other way. Two of the regressions are
exactly what the new system prompt argues against: `MARCHÉ CENTRAL` → `Marche Central` (mark
dropped *and* case flattened) and `COLLÈGE CHASSELOUP LAUBAT` → `CHASSELOUD`.

**Why v8 is wrong for this path.** v8's transcription rule forbids completing a label from
prior knowledge and asks for fragments to be marked as such — written for the per-tile path,
where `clean` rejoins fragments afterwards. The fallback it replaced said the opposite:
assemble the complete label across frames. `sequence_frame_rules()` names cross-frame joining
as an exception, which is evidently too narrow to counter the rule it is appended to.

**Rejected as the default.** Same call as the neighbour-window experiment above: the gate
says worse, so it does not ship as the default. Unlike that one, the *plumbing* stays — the
bug it fixed was real and `_meta.prompt` no longer lies. What has to change is which prompt
the sequence path composes. A sequence-specific version that keeps v8's category vocabulary,
normalization and diacritic demand but restores "assemble the complete label" is the next
thing to measure; do not re-derive v8 as the answer.

**Also corrected here:** the claim that diacritic retention "varies by run, not by sheet"
does not survive being measured per run directory. It tracks the sheet's language, hard —
1895 fr 0.08-0.14, 1882 fr 0.31-0.42, 1923 fr 0.23-0.41, 1942 fr 0.30-0.38, 1959 vi
0.80-1.00, 1968 vi 0.76-1.00 — while within one sheet it moves ±0.1. The 9%/100% pair was
computed over live-table `run_id`s that span several sheets, so it was reading corpus
composition. Diacritics are still worth a metric, and the Vietnamese sheets were already at
0.9+ under a French-priming prompt. The open anomaly is 1895 at 0.08 against three other
French sheets above 0.23 — same prompt, same model, same language. That is the better lead.

## Step-3 target
recall ≥ 0.77, char_acc ≥ 0.98, mean_iou ≥ 0.72; raw dupes should shrink (neighbor windows prevent cross-tile splits, so less for dedup to collapse).

## Step-3 attempt: neighbor-window batching — REJECTED (2026-08)

Built a flag-guarded `--neighbor-window` path (each tile read with its 4 grid neighbours in one call; labels kept by centroid ownership). Eval'd run `step3` vs the baseline above:

| metric | baseline | neighbor-window | Δ |
|--------|----------|-----------------|---|
| recall | 0.7674 | 0.6047 | **−0.16** |
| char_acc | 0.9808 | 0.9692 | −0.01 |
| mean_iou | 0.7234 | 0.7266 | ≈ |

**Rejected — regresses recall 16pts.** Two causes: (1) wrong `frame_idx` from the model globalizes a label outside every center tile → owned by nobody → lost; (2) centroid ownership leaked in the 300px tile-overlap band (adjacent tiles both "own" a band centroid), so dedup couldn't even be retired. The doc's premise (neighbor windows beat row-sequence) is false on this map. Code reverted; **row-sequence stays the default.** Don't re-attempt without fixing frame attribution AND owning by non-overlapping core regions (or nearest-center Voronoi), and only if a bigger GT set justifies it.

## The fragment join is not a lever (2026-09-08)

Hypothesis after the v8 result: the lost labels were word fragments (`MARCHÉ` + `CENTRAL`)
that `_spatial_join_fragments` could not merge, because `_is_fragment_candidate` only fires
on words ≤ 4 chars. Tested offline — `all_extractions.json` → dedup → join → `eval.py
--pred-run-dir`, no API calls — with the predicate widened to any lone word plus a same-
category / same-height / edge-gap ≤ 1.5× text-height rule:

| preds | baseline raw | baseline join-old | baseline join-new | v8 raw | v8 join-old | v8 join-new |
|---|---|---|---|---|---|---|
| matched / 43 | 33 | 33 | 33 | 27 | 27 | **26** |
| predictions | 145 | 139 | 139 | 204 | 197 | 194 |

Widening never gains a match and costs one on v8 (it fused `GENDARMERIE` + `TRÉSOR`,
`Hamelin` + `Batavia` — neighbouring labels on one axis). Reverted; the predicate stands.

**Every miss is one of two things, neither of them fragmentation.** Listing the unmatched GT
with its best-IoU prediction: *right text, wrong box* — `POUDRIÈRE` at IoU 0.31, `ABATTOIR`
0.29–0.36, `MESSAGERIES MARITIMES` 0.44, `MAGASINS A PÉTROLE` 0.46, `MARCHÉ CENTRAL` 0.49
(already a single prediction, `Marche Central`), `CASERNES` 0.50 — or *not detected at all*
(`FOURRIERE`, `GENDARMERIE`, `POSTE DE POLICE` ×2, `OUEST` read as `QUEST`). So the gate at
IoU ≥ 0.5 is measuring box convention against hand-drawn GT boxes, and the recall left on the
table is detection, not assembly. A text-exact match column at IoU ≥ 0.3 would separate the two.

## Prompt-first call order (2026-09-08)

`extract_labels` and `extract_labels_sequence` sent the image parts before the prompt. Implicit
context caching keys on a stable prefix, so the ~1.5k-token prompt was the *varying* part and
billed in full every call. Both now send `[prompt, images…]`; `calls.jsonl` gains
`cached_tokens` (`usage.cached_content_token_count`). Live check, run `ordercheck` (no `--db`),
`gemini-3-flash-preview`: 3 calls, 4847 / 5941 / 4838 input, all parsed, **`cached_tokens`
null on every call** including the third, whose prefix was identical to the first. The order
is now cache-eligible; a hit was not observed on this model in this sample. If the saving
matters, explicit caching (`client.caches.create` on system+prompt) is deterministic where
implicit is not.

## seq-v1 passes the gate — new default (2026-09-08)

Two sequence prompts, each one full run (30 tiles → 10 row calls, 2400/300/1024, no
`--db`), scored from the run dir. **Two variables, not one:** these ran on
`gemini-3.8-flash` (`DEFAULT_MODEL` since 2026-09-04) while `baseline` and `postfix-v8`
in this file ran on `gemini-3-flash-preview` — read `model` in each run's `calls.jsonl`, not
the prose. A `seq-v1` run on the old model (`seq-v1-m3`, below) separates the prompt's share. `seq-v1` is v8 with the
per-tile fragment rule replaced by whole-label assembly and abbreviations transcribed as
printed; `seq-v1-style` adds the `style` / `ink` reading guidance and nothing else.

| metric | baseline (fallback) | postfix-v8 | **seq-v1** | seq-v1-style |
|---|---|---|---|---|
| matched / 43 @ IoU ≥ 0.5 | 33 | 27 | **39** | 38 |
| recall | 0.7674 | 0.6279 | **0.9070** | 0.8837 |
| char_acc | 0.9793 | 0.9519 | **0.9895** | 0.9840 |
| mean_iou | 0.7234 | 0.7355 | **0.7739** | 0.7625 |
| text_recall@0.3 | 33/43 | 26/43 | **40/43** | 39/43 |
| diacritic_recall | 0.9048 | 0.9375 | **1.0** | **1.0** |
| predictions | 145 | 204 | 210 | 222 |
| input / cached / output tokens | 43.2k / – / 14.1k | 53.9k / – / 18.3k | 54.3k / 16.1k / 31.3k | 55.4k / 17.1k / 36.4k |
| wall clock | — | ~35 min | 7 min | 6 min |

`DEFAULT_PROMPT` is now `seq-v1`. The one-label gap to `seq-v1-style` is inside single-run
noise on a 43-label GT and is not a finding; the gate picks the winner so nobody argues
from taste. What *is* a finding: the optional `style`/`ink` schema fields get filled ~15% of
the time under `seq-v1` and 100% under `seq-v1-style` — the schema alone does not make the
model read typography; the prompt has to ask. Under `seq-v1-style`, hydrology came back
3 italic / 3 caps, streets 92 roman / 10 italic, institutions 56 caps. The ten italic
"streets" are the review queue that field was meant to produce. Both prompts put
`Rach Cầu Kho` and `Rạch Cầu Chống` under hydrology without any `R.` rule — the as-printed
normalization was enough on this sheet. Run `seq-v1-style` with `--prompt seq-v1-style`
(or `prompt` in the job payload) when the typography fields are wanted.

Output tokens roughly doubled against baseline: more predictions, longer notes
(`spans frames 0-1`, `expanded from …`, the style tags). Cached input covers the system +
task prompt on every call; the images are the floor.

## Two passes, then agree — 41/43 (2026-09-08)

The remaining `seq-v1` misses were not fragments and not box convention: `MESSAGERIES
MARITIMES` and `POSTE DE POLICE` were absent from the raw tile output. A second look at
the sheet finds them, provided the merge does not throw them away again.

**The merge was the leak.** `dedup_items` keeps the higher self-reported confidence. Across
prompts that number is not comparable — postfix-v8 reports 1.00 on a `POUDRIÈRE` box at
IoU 0.06 and on every "Village de …" expansion — so the union of four runs scored *below*
the best single run:

| union of runs | raw union | `dedup_items` | `ensemble_items` (vote) |
|---|---|---|---|
| seq-v1 + seq-v1-style | 40 | 40 | 40 |
| + baseline | 41 | 39 | 40 |
| + postfix-v8 | 41 | **38** | 40 |

`ensemble_items` (`ocr.py merge`) clusters same-label detections, keeps the spelling most
passes wrote and the box that overlaps the other members most. Agreement between passes is
the signal that survives a prompt change; confidence is not.

**Second pass = same prompt, grid shifted half a tile** (`--crop 1200,1200,10902,7782`, so
every seam falls where the first pass had tile interior). Alone it scores 28/43 — it does
not cover the outer 1200 px strip and cuts labels in new places — and that is fine, it is
not meant to stand alone. No coordinate drift in crop mode: median centroid offset against
GT is < 3 px on both runs, same as the unshifted one.

| | seq-v1 | seq-v1-shift | **merge(seq-v1, seq-v1-shift)** | merge(+ seq-v1-style) |
|---|---|---|---|---|
| matched / 43 | 39 | 28 | **41** | 41 |
| char_acc | 0.9895 | 0.9846 | **0.990** | 0.990 |
| text_recall@0.3 | 40/43 | 30/43 | **42/43** | 42/43 |
| predictions | 210 | 264 | 337 | 360 |

A third pass adds nothing. The recipe is two passes of `seq-v1` — one on the grid, one on
the grid shifted half a tile — merged by vote. Cost: 2× the single-pass tokens (~110k in,
a third of it cached, ~60k out), ~14 minutes per sheet at concurrency 3. The one label still
missing at 0.5 is box convention; the one still missing at 0.3 is `POSTE DE POLICE`, which
neither pass read.

## Prompt × model, separated (2026-09-08)

The `seq-v1` gain above was measured against runs made on a different model. Two more runs
fill the square — same sheet, tiling and pass count, one variable per cell:

| prompt \ model | gemini-3-flash-preview | gemini-3.8-flash |
|---|---|---|
| fallback (hardcoded, retired) | 33/43 · char 0.979 · text@0.3 33 | — |
| v8 | 27/43 · char 0.952 · text@0.3 26 | 38/43 · char 0.962 · text@0.3 **31** |
| seq-v1 | **25/43** · char 0.968 · text@0.3 23 | **39/43** · char **0.990** · text@0.3 **40** |

Read across: the model moves the **boxes**. On 3-flash-preview `seq-v1` transcribes the text
(318 raw extractions, `MARCHÉ CENTRAL` / `OUEST` / `DIRECTION DU Pt DE GUERRE` all present,
character-exact) and puts the box in the wrong place — IoU 0.01–0.06, offsets under a tile,
so not a frame-index slip, just poor localisation under a prompt that asks for whole labels.
The retired fallback was tuned around that model's habits, which is why it led there.

Read down: the prompt moves the **reading**. On 3.8-flash, v8 and seq-v1 box nearly the same
labels (38 vs 39) but v8 reads 31 of them correctly to seq-v1's 40 — the expansion rule
("Vge de" → "Village de", `R.` → `Rue`) and the fragment rule cost it nine labels against an
as-printed GT, and 2.8 points of char_acc.

So: the model bought most of the recall at IoU 0.5; the prompt bought the text. `seq-v1`
stays the default on char_acc and text_recall@0.3, the two columns that say whether the
label that reaches a reader is spelled the way the sheet spells it. The two-pass result
(41/43) is unaffected — both passes ran on 3.8-flash.

**Rule from this:** compare runs by the `model` field in their `calls.jsonl`, never by the
prose around them. `DEFAULT_MODEL` changed on 09-04 and every run after it silently moved.

## Resolution was the wall for small type — and it fragments the rest (2026-09-08)

`seq-v1` at `--tile-size 1200 --overlap 150` (108 tiles → 36 calls, render 1024, so ~1.2×
downsample instead of 2.3×): **it read `POSTE DE POLICE` (×4) and `MESSAGERIES MARITIMES`**,
the two labels no 2400 px pass ever returned. Resolution, not prompt or pass count, was what
stood between the model and that lettering.

| | seq-v1 (2400) | seq-v1-hires (1200) | 2-pass 2400 merge | 2400 + hires merge | **3-pass merge** |
|---|---|---|---|---|---|
| matched / 43 | 39 | 41 | 41 | 41 | 41 |
| char_acc | 0.9895 | 0.9737 | **0.990** | 0.9835 | 0.988 |
| text_recall@0.3 | 40 | 38 | **42** | 41 | **42** |
| category_acc | 0.872 | 0.854 | 0.878 | 0.878 | 0.878 |
| diacritic_recall | 1.0 | — | 1.0 | 0.864 | 0.955 |
| tokens in / cached / out | 54k/16k/31k | 206k/58k/46k | 110k/32k/60k | — | ~316k/90k/106k |
| wall clock | 7 min | 30 min | 14 min | — | ~45 min |

The gate cannot tell the 3-pass merge from the 2-pass one — 43 labels is at its ceiling — so
the decision rests on what the gate cannot see. Against the 2-pass output, the hi-res pass
holds 20 labels the 2400 passes lack (15 confident), and the 2400 passes hold **95** it lacks
(86 confident). Its extras are the small type — and fragments: `Rue de Thuận`, `Charner`,
`e de Thái Bình`, `S A I G O`. Small tiles chop the long labels the 2400 passes read whole.
So the 1200 px pass is a supplement for dense small lettering, never a replacement.

**Default stays two passes.** `passes: 3` in the job payload adds the 1200 px pass as `<run>-c`
before the merge, for sheets where the 2400 passes visibly miss small type. The two-run
merge with hi-res dropped diacritic_recall to 0.864: with two voters every disagreement is a
tie and the tie-break is "longest", which favours the fragmentary spelling. Three voters fix
it; if a two-run merge is ever the norm, tie-break on confidence instead.

## Rotation: already good, never drawn, and no help to matching (2026-09-08)

Asked whether adding bbox rotation would improve *matching* and *orientation*. Measured
both. The answers pull apart.

**The ground truth doubled today.** `status='validated'` on the gate sheet is now **85
scorable rows** (78 rows carry a full `global_*` box; 77 of them from run `v1b`, one from
`2026-09-04T0527`), against the 43 every number above was scored on — 35 were validated on
09-08. So the 41/43 result in the sections above is stale as a *fraction*; rescored against
the bigger GT the same two-pass merge reads:

| | seq-v1 | seq-v1-shift | 2-pass merge |
|---|---|---|---|
| matched / 85 @ IoU 0.5 | 71 | 42 | **75** |
| char_acc | 0.981 | 0.983 | 0.979 |
| text_recall@0.3 | 75/85 (0.882) | 44/85 | **77/85 (0.906)** |
| category_acc | 0.873 | 0.810 | 0.880 |
| diacritic_recall | 1.0 | 1.0 | 1.0 |
| **rotation_mae** | 3.65° | 3.81° | **3.49°** |

The merge still wins on every column that matters, on a gate twice the size. Note the GT is
still 77/78 `v1b` rows — a reviewer approved *more of v1b's existing output*, so "recall
against what v1b found" is unchanged as a caveat; only the sample grew.

**Matching: no.** Every path that compares two boxes gates on text first —
`dedup_extractions` (`ocr.py`, "Text similarity check first") and `ensemble_items` (the
`_text_similar` guard before `_iou`). A fat axis-aligned box cannot merge two different
labels, so a rotated-rect IoU has nothing to fix there. The one path that is *not*
text-gated is the eval's own `greedy_match`, and the labels it matches below IoU 0.5 are
horizontal: of the five, one is diagonal. The 0.3–0.5 gap this file records for POUDRIERE /
ABATTOIR / MARCHE CENTRAL is box tightness on long horizontal institution names, not
rotation. `shapely` is already in the venv, so the cost was never the obstacle — the
measurement was.

**Orientation: the data is there and it is right.** `rotation_mae` (new, `eval_metrics.py`)
folds two baseline angles modulo 180 — a baseline is a line, so −90 and 90 agree — and over
the merge's 75 matched pairs it is **3.49°, with 5 pairs disagreeing by 15° or more**. The
model's angle is not the weak link. Caveat in the metric's name: GT's angle is *also* model
output, from `v1b`, which no reviewer ever saw (the review UI has no rotation control), so
this is agreement between two runs, not accuracy against the sheet.

**What was actually missing was that nothing drew it.** Before today, `rotation_deg` was
read by `_group_sequential` and the fragment pass and by nothing else: no file under `src/`
touched it but the generated types. So a reviewer looking at a diagonal label saw an
axis-aligned rectangle — and **58% of the merge's 337 labels claim |angle| ≥ 20°, 157 of
them ≥ 40°** (the 1882 sheet's street grid runs on the diagonal). Their boxes have a median
aspect ratio of 1.15: near-square, roughly twice the text's real area, telling a reviewer
nothing about which way the lettering runs.

`baselineChord()` (`src/lib/core/geo/rectUtils.ts`) draws it, and needs no new data. The
chord of a *tight* AABB through its centre at the baseline angle **is** the text's extent —
half-length is whichever side the chord reaches first — so `OcrBboxTool` renders it as a
second style on the existing feature (no new layer, no new interaction), skipped below 5°
where the box already reads right. `tests/baseline-chord.spec.ts` pins the sign convention.

**Not done, and why:** asking the model for a quad (four corners instead of a box plus an
angle) would give a tight oriented box for free downstream. It costs a schema field on a
prompt that currently passes, and the last two fields added to `seq-v1` were measured and
cut (`c6b983af`). With `rotation_mae` at 3.5° there is nothing visibly broken for it to fix,
so it waits until something needs the tight box — SAM2 is the candidate, and SAM2's box
prompt is axis-aligned anyway.

**Also worth knowing:** the oriented box *can* be recovered offline from a tight AABB plus an
angle — `W = w·c + h·s`, `H = w·s + h·c`, so `w = (W·c − H·s)/cos2θ` — but `cos 2θ` vanishes
at 45°, which is where 137 of this sheet's labels sit. Recovery solves the cases that did not
need solving. The chord does not have this problem: it needs no inversion.

## The automated path, audited and then automated (2026-09-08)

Two passes over the same code, in the same day: an audit of everything that runs
unattended, then removing the manual steps that were left.

**Twelve faults, every one of them producing plausible output.** The full list is
in the commit (`fix(pipeline): the twelve faults the automated path was hiding`).
The four that cost data:

| | Measured |
|---|---|
| The OCR upsert key ignored position | 18 of 337 merged rows (5.3%) overwrote each other; 1 of 210 for a single pass |
| A layout re-run replaced `regions` wholesale | every `source: 'human'` correction discarded, silently |
| Pass 2 could not match the triage's tile keys | stride 1800, offset 1200 — `1800m − 1800n = 1200` has no integer solution, so *no* key matched and every skipped tile was read at full cost |
| Merged rows lost their provenance | `model = NULL`, `prompt = 'merge'` on the default path |

The upsert key was the interesting one, because the honest fix was not the first
idea. Re-keying each row to its own grid cell instead of the winning pass's tile
origin sounded better and measured **worse** — 47 rows lost against 18, because a
coarse cell concentrates more, not less. Position had to go in the key
(migration 077, `global_xi`/`global_yi`, generated `round()` columns because
PostgREST cannot name an expression index in `on_conflict`). With it: 0 lost.

**Then the triage.** It was five manual steps per sheet; it is now a proposal a
person checks. What made that cheap is that two of the three signals were
already built and simply never wired:

- The `layout` job's own `main_map` region becomes the crop. Two independent runs
  on the 1882 sheet put it **0.2% apart at conf 0.98**, covering 80.4% of the
  scan — against the 81% `suggestTriage.ts`'s ink-profile walk finds by a wholly
  different method. `tilingCrop()` already preferred main_map to a neatline.
- `--auto-priority` had existed in `ocr.py` all along and **no enqueue path or
  worker ever passed it**, so automated runs paid full price for blank margins.

**The blocker nobody could see was a gate.** `enqueue_ocr_all.mjs` required
`triage.neatline`, and across 101 georeferenced maps **not one had one** — while
37 already carried the `main_map` region the crop resolver prefers. The script's
default mode therefore queued nothing across the entire corpus and exited
reporting success. `/admin?tab=status` had even printed the symptom ("this is the
blocker") without anyone finding the cause. `triageState()` is now the one
predicate and a `--dry` run names every state, so "queued nothing" cannot pass
for success again.

**The one measurement that had to be made before wiring any of it.** The
tile-density signal exists twice — the measured TS the browser proposes with, and
the Python the automated path now uses — and `suggestTriage.ts`'s header exists
*because the Python one was silently wrong on this corpus*: fed a 1024px overview
it rated the dense city centre lower than the margins and would have skipped
exactly the tiles worth reading. That was a resolution bug, since fixed, but
nothing stopped the two drifting again, and a drift does not look like a bug — it
looks like a sheet that came back thin.

`tests/density-parity.spec.ts` compares them on **identical bytes** (a 512px
window of the 1882 overview across the left sheet edge: dark scan margin, blank
paper, the printed rule, map content — all three decision bands) and asserts they
agree on every tile's `skip`/`low_res`/`normal` **verdict**, not just its number.
They do. Comparing two fetches of an image would have confounded a decoder
difference with an algorithm difference, hence the stored raw L bytes.

The colour/wash demotion inside that pass was made opt-in rather than shipped:
its hue bands are 60–260° and every saturated pixel on this sheet sits in 0–60°
(warm paper, pink parcel tints), so it scored 0.000 on every tile at every
saturation gate. Wiring `--auto-priority` into the queue would otherwise have
shipped an unmeasured signal by the back door.

**Rule from this pass:** the corpus-wide count is the check nobody runs. Three of
these faults — the dead gate, the never-passed flag, the missing neatlines — were
invisible in the code and obvious the moment someone counted rows. Two of the
twelve were caught only by re-measuring a thing that already appeared to work.

## The dedupe was deleting distinct streets — recall-neutral on this gate (2026-09-10)

`_text_similar` decided two labels were one label read twice. Four false
positives, each measured on the 1959 Saigon sheet (`34d4edb2`):

| what matched | why |
|---|---|
| `Đại Lộ Lê Lợi` = `Đại Lộ Hàm Nghi` | shared prefix is 2 of 4 words, clearing the `≥ 0.5` word-overlap test |
| `Đại Lộ Lê Lợi` = `Đại Lộ Lê Lai` | 0.92 as strings, 0.83 on the names — the prefix pads every ratio |
| `Đường Tự Do` = `Đường Tự Đức` | `do` vs `duc` scores 0.80 as characters |
| `Đường` = *every street on the sheet* | a bare generic is a whole-word substring of all of them, and both `dedup_items` and `ensemble_items` cluster by union-find, so **one such row chained 43 streets into a single cluster** whose winning text replaced all 43 |

Fixed by comparing the prefix-stripped **name**, syllable by syllable, with fuzz
only above four characters, two shared syllables required rather than a ratio,
and the substring rule gated on both sides being name-like with a non-empty
core. `work/ocr/scripts/test_dedup_labels.py` is the check: 16 pairs that must
stay apart, 7 that must join. `_CLOSE_FACTOR` replaces `max_dim * 1.5` — the
proximity budget now scales with the label's **height**, not its length, because
a 600px street label was buying 900px and sweeping up the next street over.

**On the 1959 sheet:** distinct name cores 456 → 607 (+33%), street rows 452 →
795. Lê Lợi, Hàm Nghi, Công Lý, Phan Chu Trinh, Lý Thái Tổ, Tổng Đốc Phương and
Lê Đại Hành were all absent and are all back.

**On this gate sheet, re-deduped from cached tiles — no API calls:**

| metric | `baseline` | `baseline` re-deduped | `seq-v1` | `seq-v1` re-deduped |
|---|---|---|---|---|
| recall | 0.5529 | **0.5529** | 0.8353 | **0.8353** |
| char_acc | 0.9797 | **0.9797** | 0.9814 | **0.9814** |
| mean_iou | 0.7194 | **0.7194** | 0.7503 | **0.7503** |
| category_acc | 0.8936 | **0.8936** | 0.8732 | **0.8732** |
| text_recall@0.3 | 0.5647 | **0.5647** | 0.8824 | **0.8824** |
| predictions | 145 | 167 | 210 | 235 |
| precision | 0.3241 | 0.2814 | 0.3381 | 0.3021 |

Every trustworthy metric is **identical**; only the row count moves. `seq-v1`
re-deduped still clears the step-3 target (recall ≥ 0.77, char_acc ≥ 0.98,
mean_iou ≥ 0.72). The precision drop is the partial-GT artefact this file warns
about at the top: the ground truth is 85 of the sheet's labels, so 25 extra
correct rows are counted as 25 false positives. Do not read it as a regression,
and do not tune against it.

**The important result is the null one: this gate cannot see the bug it was
asked about.** It is a French sheet, and `Rue Catinat` / `Rue Charner` survive
character comparison where `Đại Lộ Lê Lợi` / `Đại Lộ Lê Lai` do not — Vietnamese
street names are two or three short syllables that differ in one, and the generic
is most of the string. 85 GT labels on one French sheet is the wrong instrument
for a corpus that is mostly Vietnamese. See *Getting more out of OCR* in
`docs/pipelines.md` for the cheap fix: a sheet's own printed street index is 384
name→cell-range pairs of free ground truth, and needs no human labelling.

**And that instrument now exists**: `eval.py index-agreement`. Scored against the
1959 sheet's own printed directory, the same dedupe change reads
**`name_recall` 0.7493 → 0.7947** (281 → 298 of 375 printed names). The metric
this file is built on moved by zero; the one built out of the sheet moved by 4.5
points. Baselines for both indexed sheets are in `work/ocr/index-baselines.json`,
and the command prints the delta against them.

## The 1968 sheet reads a third of its own directory — and the scan is why (2026-09-10)

First body pass ever run on the 1968 Sài Gòn sheet (`3a446d85`), which the
index metric had just measured at `name_recall` **0.0245** (9 of 367 printed
street names). Candidate run `body-1968-20260910a`, scored from its run
directory, **not upserted** — no `--db`, no `--save`.

```
ocr.py batch --map-id 3a446d85-25a8-4e81-9cfc-8de357c3a5df \
  --crop 281,311,10015,9533 --tile-size 1120 --overlap 280 --render-size 1120 \
  --prompt seq-v1 --min-confidence 0.5 --concurrency 3 --auto-priority
```

The tiling mirrors the 1959 recipe **in ground, not in pixels**. This sheet is
**1.274 m/px** (least-squares affine over its 15 georeference GCPs, isotropic,
north-up) against 1959's **0.997 m/px**, so 1120 px = 1427 m per tile against
1959's 1404 px = 1400 m. 12 cols × 12 rows = 144 tiles → 48 calls of 4 frames.
`--auto-priority` found 0 skip / 1 low-res: the `main_map` crop is inky
throughout, so there is no margin to save on.

| | 1959 single pass (`…1555-34d4edb2-a`) | **1968 single pass** | 1959 3-run merge |
|---|---|---|---|
| `name_recall` (±1 cell) | 0.7120 (267/375) | **0.3270 (120/367)** | 0.8000 (300/375) |
| `agreement` ±1 cell | 0.9666 | **0.9603** (145/151) | 0.9439 |
| `agreement` ±0 cells | — | **0.8212** (124/151) | 0.8679 |
| street+hydrology labels | 464 | 279 | 883 |
| distinct name cores (street+hydro) | — | **210** | — |
| `diacritic_rate` (all preds) | — | **0.7869** (0.9462 over street+hydro) | — |
| calls / in / cached / out | 36 / 205k / 58k / 87k | 48 / 274k / 77k / 82k | — |
| wall clock | 31 min | 26 min | — |

**+0.30 on the metric, and still half the 1959 rate at the same metres per
call.** Both are one `seq-v1` pass at 1:1 render on a Vietnamese sheet, ~1400 m
per tile, same model. The distinguishing variable is the scan: 1.274 vs
0.997 m/px, and the sheet is itself a **photo-reduction** of 1:10,000 originals
to 1:12,500 (`dc_description`), so the type is smaller on the paper *and*
sampled more coarsely. The pass is already rendering 1:1 — there is nothing
left to stop downsampling. `archive.org/details/1968-sg` holds exactly one
image, and it is this one (10816×13523), so **a rescan, not a flag, is what
buys the missing resolution.**

**Recall is flat across the sheet**, which rules out the cheap explanations.
By the directory's own FROM-row: F 0.19, G 0.22, H 0.46, I 0.42, J 0.21,
K 0.38, L 0.29; by FROM-column 0.22–0.62 with no dead band. Not a bad crop, not
a mis-set tile priority, not one unreadable quarter — a uniform ~⅓ read rate.
So a second shifted pass buys what it bought on 1959 (+0.09 there, three passes)
and not the missing 0.38.

**The grid was suspected and is exonerated — the crop is what is short.**
`triage.grid` puts 15 rows over `bbox [281, 338, 10123, 11819]`, reaching
y = 12157, which is **2313 px below the bottom of `main_map` [281, 311, 10015,
9533]**, and 13 directory boxes land past it. That looked like a mis-fitted
grid. Re-deriving every directory box from its printed `grid=` citation under
four hypotheses and rescoring the same 150 matched labels says otherwise:

| grid hypothesis | cell | `agreement` ±1 | ±0 |
|---|---|---|---|
| **committed (15 rows A–O over 281,338,10123,11819)** | 779×788 | **0.9600** | **0.8267** |
| 15 rows A–O over `main_map` | 770×636 | 0.2333 | 0.0667 |
| 15 rows A–O over `main_map`, 12 cols | 835×636 | 0.2333 | 0.0733 |
| 10 rows F–O over `main_map`, 12 cols | 835×953 | 0.0267 | 0.0067 |

The committed grid wins by 0.73. So the sheet's reference grid genuinely
continues into the lower margin band and **`main_map` is the region that stops
early** — it covers 80.7% of the grid's y-extent. The cost this pass is small
(4 directory names entirely below the crop, 9 straddling it), because rows L–O
carry only 35 of 734 citations and sit at columns 2–6, but the layout job's
`main_map` is understating this sheet's south-west corner and a later pass
should crop to the grid's extent minus the two `name_list` blocks, not to
`main_map`.

**The denominator is partial, in the direction that flatters the score.** This
sheet has **two** `name_list` regions — `[7571, 9871, 2745, 3262]` and
`[4218, 9871, 3271, 3506]` — and `ocr street-index` (run `streetindex-1968`,
regions at x 7571/8257/8943/9629) read only the first. 367 names is one block's
worth; reading the second would raise the denominator and lower `name_recall`.

**Not to be read as a regression:** `agreement` 1.0000 → 0.9603 in
`index-baselines.json` is the partial-sample artefact this file warns about —
the old figure was 9 matched labels, this one is 151.

**What the next pass should try, in order.** (1) Fewer metres per call:
`--tile-size 800` is 1019 m and ~2× the calls (~USD 2.5 at the corrected cost
below; originally written as ~$0.5, doubled off the uncorrected actual). doc
step 3 is measured on 1959 and untried here. (2) An **upsampled** render
(`--tile-size 1120 --render-size 1680`) — this is *not* the resolution bump
this file rejects, which was smaller tiles fragmenting long labels; it is the
same tile with bigger glyphs, and nothing in the corpus has measured it. (3)
Read the second `name_list` block so the denominator is the whole directory.

**Cost:** estimated USD 0.37 before running (48 calls × 5984 in / 1607 cached /
~2500 out at 0.30/0.075/2.50 per Mtok), actual **USD 0.271** — output came in
at 82k rather than the 120k budgeted.

**Both of those numbers are wrong, on two counts, corrected 2026-09-10** (see
*Prices used* below): they price at $0.30/$2.50, a rate this file uses nowhere
else, and they cost `output_tokens` (82,397 — visible text only) rather than
what Gemini actually bills, `total_tokens − input_tokens`, which includes
thinking. That figure is 288,613 for this run — **3.5× the visible one**.
Recomputed straight from this run's own `calls.jsonl`, at the $0.75/$3.75
input/output and $0.075 cached-read rate the rest of this file settles on:
**actual USD 1.236** — 4.6× the number originally recorded. (At the original,
non-standard $0.30/$2.50 rate but with the billed-output correction only, it
is USD 0.786 — the rate and the token definition are two separate bugs, and
this shows their sizes apart.)

## The recipe of record, re-run: free from cache, and two inert knobs (2026-09-10)

Re-ran the two-pass merge on the gate sheet at exactly the settings recorded
above — `seq-v1`, `gemini-3.8-flash`, 2400/300/**1024**, `--min-confidence 0.4`,
grid + `--grid-offset 1200`, vote-merged — with today's code, no `--db`, no
`--save`. Runs `rr0910-a` / `rr0910-b` / `rr0910`.

**18 of 18 calls came out of `outputs/.cache`.** The response cache keys on
image bytes + composed prompt + model + schema version, and none of the four has
moved since 2026-09-07, so re-running the recipe of record on this sheet costs
**USD 0.00 and 40 seconds**. Worth knowing before anyone budgets a re-run: the
expensive thing is changing the grid, not repeating the pass.

| | baseline of record | re-run, same settings | fleet payload today |
|---|---|---|---|
| calls (fresh / cache-served) | 18 / 0 | **0 / 18** | 16 / 0 |
| tiles | 54 | 54 | 44 |
| wall clock | 12.5 min | 0.7 min | 13.2 min |
| USD | 0.945 | **0.000** | 0.868 |
| matched / 85 @ IoU 0.5 | 75 | **75** | 68 |
| `text_recall@0.3` | 0.9059 | **0.9059** | 0.8588 |
| `char_acc` | 0.9786 | **0.9786** | 0.9699 |
| `mean_iou` | 0.7495 | **0.7495** | 0.7380 |
| `category_acc` | 0.880 | **0.880** | 0.8676 |
| rows | 337 | 348 | 281 |
| **distinct name cores** | 233 | **247** | 243 |

Every trustworthy metric is bit-identical; the 2026-09-10 dedupe fix shows up
only as **+14 distinct name cores at the merge level (233 → 247, +6.0%)**, which
is the same null-then-positive result the section above records for the single
passes. `_label_core` + `_fold` is the count; rows are not.

**`--render-size` above 1024 is inert, twice over.** One controlled pass, same
grid, render 2400 instead of 1024 (`r2400-a`): input tokens **54,243 against
54,339** — the API tokenises a 2400×2400 frame and a 1024×1024 frame to the same
~1032 tokens, so the extra pixels never reach the model. Scores are a wash
(matched 73 vs 71, `text_recall@0.3` 73 vs 75, `char_acc` 0.9758 vs 0.9814,
distinct cores 217 vs 212) for 13% more wall clock. And separately: the tile PNG
cache at `outputs/<map>/<x>_<y>_<w>_<h>_tile.png` **carries no render size in its
key**, so on any sheet already tiled once, `--render-size` is silently ignored
and the stored resolution is reused. `vma_worker.RENDER_FLOOR`'s "a stock 2400
tile renders 1:1" therefore does nothing on this sheet, and nothing at all on any
previously-tiled grid. Fix the cache key before claiming a render change shipped.

**The fleet's own payload scores 7 labels below the recipe of record at the same
money.** `enqueue_ocr_all.mjs` + `vma_worker.py` on this triaged sheet send
`--crop 459,413,11073,7913` (the `main_map` region), `--auto-priority`,
`--min-confidence 0.5` and render 2400 — 16 calls over 44 tiles for USD 0.868
against 18 over 54 for USD 0.945. It reads **68/85**. Two of the four differences
are measurably not the cause: `--min-confidence` 0.5 vs 0.4 changes nothing on
this sheet (277 → 243 either way, re-deduped offline for free), and render is
inert per above. What is left is **coverage**: only one GT label sits outside the
`main_map` crop, but `--grid-offset` applied to a crop leaves pass 2 with 20
tiles instead of 24, and the merge votes over 453 labels instead of 513. Ten GT
labels drop and four appear — grid-seam churn, net −7. Cropping to `main_map`
saves 8% of the money and 19% of the coverage on a sheet that is 80% main map.

**Prices used:** Gemini 3.8 Flash introductory rates, in force through
2026-12-31 — USD 0.75/Mtok input, 3.75/Mtok output, 0.075/Mtok context-cache
read (apidog.com/blog/gemini-3-8-flash-pricing, requesty.ai; both double on
2027-01-01). Output is billed as `total_tokens − input_tokens`, i.e. **candidates
plus thinking**: on this sheet thinking is ~4× the visible output (pass 1 emits
31k visible and is billed for 124k), so a cost read off `output_tokens` alone
understates a run by about four. The 1968 note above priced at 0.30/2.50 and
counted visible output only, so it was not comparable to this section —
corrected in place above (2026-09-10) to this same basis, and it moves from
$0.271 to $1.236 once it is.

**Not accepted.** `index-baselines.json` and every number above this section are
untouched; nothing was written to `ocr_extractions`. Run dirs for the paid probes
are at `outputs/0e02b9d9…/runs/_fleet-probe-0910/`.

## 2026-09-10 — the 1882 grids behind 68/85 and 75/85 no longer exist

Both scores above were measured before `b532d3b9`, which changed what
`--grid-offset` does. They are still the record of what was run, and they are
still comparable to each other, but neither can be reproduced now and neither
should be quoted as the current state of the pipeline.

The offset pass used to inset its region rather than phase-shift its lattice, so
it never read the leading `offset`-wide strip of the sheet. That is what the
68/85 measured: cropped to `main_map` the inset also crossed a step boundary and
cost pass 2 four of its 24 tiles, and the vote saw 453 labels instead of 513.
The 75/85 recipe ran uncropped, where the inset happened not to cross a
boundary — so it kept its tile count and looked correct while still never
reading its own leading strip.

Both passes now cover their whole region: the crop goes 20 -> 30 tiles and the
full sheet 24 -> 35. **The expectation is that a re-run beats 75/85, not that it
reproduces it**, because the recipe of record was also losing area. Re-running
the gate sheet is the next measurement, and the ~11 new tiles per pass are new
geometry, so they are cache misses and it will not be free.

## 2026-09-10 — the 1882 re-gate: the fix is right, and this gate cannot see it

Ran the recipe of record against the fixed `--grid-offset` (`b532d3b9`).
Projected USD 0.71 on the billed basis, actual **USD 0.6686** (pass 1 0.1799,
pass 2 0.4887, merge free), 16.7 min. Tiles per run 54 -> 65, calls 18 -> 25.

| | matched / 85 |
|---|---|
| record `rr0910` | 75 |
| fixed `regate0910` | **76** |
| control `regate0910-ctrl` — same pass 1, *old* inset pass 2 off disk | **76** |
| the offset pass alone, before -> after | **42 -> 73** |

**The offset pass now genuinely reads the sheet** — 42/85 to 73/85 standalone,
`text_recall@0.3` 0.5176 -> 0.8824. That is the fix working exactly as
`b532d3b9` describes.

**And it is worth zero labels on this gate.** The control run — the same pass 1
merged with the *old* broken pass-2 output — also reaches 76/85, gains the same
single label (`COLLÈGE D'ADRAN`) and loses none. Two reasons, both measured:

- The strip that was never read is the leading 1200 px in x and y, which on this
  sheet is the top and left margin. Only **7 of the 85 ground-truth labels** sit
  in it, and pass 1 always covered it, so all seven were already found. 78 of 85
  are inside what the broken pass 2 had already tiled.
- The gate's ceiling is **box convention, not coverage**. All 9 remaining misses
  have a prediction sitting on them (best IoU 0.09-0.50), six of those are
  character-identical or differ only by a diacritic the ground truth itself
  drops, and `text_recall@0.3` is unchanged at 0.9059.

What the fix did recover is real and this gate is blind to it: the strip is the
margin, so the fixed merge picks up `REGISTRE DU CADASTRE`, the Boilloux
imprint, five whole-string legend rows and **20 cadastral street numbers** —
none of which a ground truth of 85 French street and institution names can
score. The -4 distinct cores and -68 rows are mostly the vote collapsing
duplicates it can now see twice (189 of 471 multi-pass, against 160 of 513)
plus fragments a one-voter region used to leave behind.

**So `b532d3b9`'s commit message set the wrong expectation.** It said a re-run
should beat 75/85 because the recipe of record was losing area too. The premise
was right and the prediction did not follow: the recipe was losing *margin*
area, and margin content is not what these 85 labels are. Scoring a coverage
change needs a ground truth that includes margin content, or a coverage measure
reported separately from `name_recall`.

### Two faults found in the process, neither of them `b532d3b9`

1. **The +1 label is a confound, and no two runs on a sheet are byte-comparable
   until it is fixed.** `_cached_tile` reads `{key}@{requested_render}` while the
   save path writes `{key}@{max(img.size)}`, and `fetch_crop` defaults to
   width-only (`{size},`), so any tile taller than it is wide — the whole
   right-edge column of a grid — is written under one name and looked for under
   another. It is re-fetched every run, and the re-fetched bytes differ from the
   legacy file at the same size after the `2cf6dd02` pyramid change. Four of
   pass 1's ten calls were re-paid and returned slightly different output, and
   that is where `COLLÈGE D'ADRAN` came from. Treat 75 -> 76 as noise.
2. **A row group discards 22% of what it pays for.** Row grouping is
   `range(0, len(row), 3)` in slices of 4, so a 7-tile row is `[0:4] [3:7]
   [6:7]`; each group rewrites the per-tile JSON for its own frames, so a later
   group overwrites a shared tile, and the trailing single-frame group — here the
   402 px right-edge sliver rendered 1024x6113 — returns 0 every time and wipes
   what `[3:7]` found for that tile. Replayed from `outputs/.cache`: pass 2's
   calls returned 362 extractions and 284 reached disk, 78 lost; pass 1 315 ->
   263. About 1 label and 5 wasted calls per run.

Both are being fixed separately. Until the first one is, **do not compare two
runs on one sheet and attribute a one- or two-label difference to anything.**

## 2026-09-10, later — the 1968 passes: the denominator was never partial

Three steps, USD 2.2544 billed, nothing written to the database. The harness
had to be rebuilt offline first, because `eval.py index-agreement` takes its
ground truth from `ocr_extractions` and this run was forbidden to write:
composing GT rows exactly as `cmd_street_index --db` does and calling the same
`score_index_agreement` against the same `maps.triage.grid` reproduces the
recorded figures bit for bit (369 entries, 367 names, 151 matched, 0.3270,
0.9603, and every per-row value F 0.19 / G 0.22 / H 0.46 / I 0.42 / J 0.20 /
K 0.38 / L 0.29). Everything below is therefore comparable to what is above.

### The claim above about two `name_list` blocks is wrong — retracted

The unread block `[4218, 9871, 3271, 3506]` **is not a second street
directory.** Rendered, it is headed *GUIDE TO NUMBERED FEATURES · BẢNG CHỈ DẪN
CÁC KIẾN-TRÚC*: 244 numbered institutions — hospitals, ministries, markets,
schools, embassies — indexed by `Chỉ Số` and `Ô Vuông`. The street directory is
the other block and it was read **whole**: its four printed column groups span
x ≈ 7639–10246 against windows covering 7571–10449, its last row sits at
y ≈ 12939 inside the read band, and the one empty band (region 3, y 12390) is
correct rather than a failure, because group 4 is a short column ending at
y ≈ 11919 (`Yersin`, `Yết Kiêu`, `Hẻm Cây Điệp`, `Tống Duy Tân`). An ink
projection counts ≈356 printed rows against 369 entries read.

**So `name_recall` 0.3270 stands, and 0.327 does not flatter anything.** The
denominator was already complete. Folding block 2 in would make the figure
*worse* founded, not more honest: predictions are filtered to
`category in (street, hydrology)`, so 244 institution names would enter the
denominator unmatchable and print ≈0.196 while nothing about the read had
changed. Block 2 needs its own institution gate, not a place in this one.

### What ground per call is worth, measured

`--tile-size 800` against the 1120 baseline, scored over the same rectangle
`281,311,10015,7400` and the same 189-name restricted denominator:

| | tile 1120 (1427 m/call) | tile 800 (1019 m/call) |
|---|---|---|
| `name_recall` | 0.3651 (69/189) | **0.4180 (79/189)** |
| `agreement` ±1 | 0.9500 | 0.9333 |
| distinct name cores | 127 | **171** |

+10 printed names and +44 name cores (+35%) for USD 1.8364, about **USD 0.09
per additional name**. Ground per call is confirmed as the lever on this sheet.
The per-call rate is not flat — USD 0.0166 over the sparse north against USD
0.0382 marginal in the city core — which is why the pass was stopped on a clean
row boundary at 12 of 16 rows rather than breaching the ceiling; its 204 tile
JSONs were assembled through the pipeline's own `_apply_conf_floors` +
`dedup_extractions` tail.

### The south band: the geometry claim holds, the value claim does not

Run as an increment (`--crop 281,9844,3759,2416`) so nothing already paid for
was re-read. `main_map` does stop early, exactly as measured above. It bought
**+2 printed names** — 0.3270 to 0.3324 — for USD 0.4180, or **USD 0.21 a
name, the worst value on this sheet**, because only 24 directory names have
their FROM cell in rows L–O. It did add 20 hamlet and canal names the directory
never lists: real content this gate cannot see, which is the same blind spot
the 1882 re-gate ran into.

**Best current read of the sheet**: the union of all three runs scores
`name_recall` **0.3978 (146/367)**, `agreement` ±1 0.9377, distinct name cores
210 → 292. Recall stayed flat across rows, so the finer tiles lifted the whole
sheet rather than filling a hole.

**Next, in order:** finish the 800 pass (24 calls, ~USD 0.9 — its 204 paid
tiles are detected as done), then consider `--grid-offset 400` and a vote
merge. Do **not** re-run the south band, do **not** fold block 2 into this
gate, and do not upsample the render.

## 2026-09-10 — run `post0910`: the first 1882 rows written after the fixes

Run id **`post0910`** on sheet `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`, executed
by a peer session under its own approval, recipe of record **uncropped**
(`seq-v1`, `gemini-3.8-flash`, 2400/300/1024, `--min-confidence 0.4`), two
passes vote-merged, **287 rows upserted to `ocr_extractions`** and pipeline
status set to `ocr_done`. Run dirs `runs/post0910{,-a,-b}`. This is the run the
MapSAM2 side should seed from; the April/May v1b rows should not be used.

| | tiles | calls | fresh | raw → unique |
|---|---|---|---|---|
| `post0910-a` (grid) | 30 | 10 | 0 | 315 → 233 |
| `post0910-b` (`--grid-offset 1200`) | 35 | 10 | 4 | 387 → 261 |
| merge | | | | 494 → **287** (196 seen by both passes) |

**Billed cost USD 0.1967**, computed from `post0910-b/calls.jsonl`: 4 fresh
calls, input 23,953 of which 6,428 cached, total 72,776, so billed output
48,823 against the 19,725 the `output_tokens` field reports — 2.48x. The peer's
estimate of "about USD 0.10" is USD 0.0919 on the old output-tokens basis, which
is the arithmetic this file corrected earlier today; the two figures differ by
the thinking tokens. `post0910-a` wrote no `calls.jsonl` at all because all ten
of its calls were served from the model-response cache, which is the same
mechanism that made `street-index` report 15 calls when 14 were billed.

**Two caveats on using this as a measurement, as opposed to as seed rows.**

1. **It is largely a replay.** 16 of the 20 calls came from the model-response
   cache, inherited from `regate0910` earlier today. Only 4 calls are a fresh
   read of the sheet. The rows are sound and that is what the seg side needs,
   but `post0910` is not an independent sample of the model's behaviour and
   should not be treated as one.
2. **It is a new baseline, not a reproduction of 0.945 / 75-of-85.** Three
   things moved underneath the recipe today: `b532d3b9` (the offset pass
   phase-shifts the lattice, so pass b covers the full extent — 35 tiles where
   the record had 24), `094c92fa` (row grouping stopped emitting a trailing
   subset group whose empty result overwrote its neighbour, and the tile cache
   started hitting at all), and `9357f30b` before them (the dedupe deleting
   distinct streets). A polygon count diffed against the April/May set measures
   those three fixes as much as anything else.

`b532d3b9` is visible on disk here: `post0910-b`'s first tile is
`0_0_1500_1500`, the lattice index -1 tile clipped to the region, which the old
inset implementation dropped entirely.

## 2026-09-10 — the 1863 Palanca Gutierrez sheet re-mirrored at full size

Not an OCR run; a source fix, recorded here because it moves a number this file
tracks. Map `876dc3c6-2709-4b80-bece-32ada0dfff76`.

| | before | after |
|---|---|---|
| pyramid | 4876×8396 | **6501×11195** |
| `ocr.py scale` | 1.804 m/px | **1.353 m/px** |
| R2 objects | 901 / 9.3 MiB | 1542 / 17.1 MiB |
| tile grid at `--tile-metres 1400` | — | 1042 px, 8×14 = 112 tiles, 1410 m/call |

R2 had been mirroring a clean 75% downscale of a copy Humazur serves in full,
and `source_url` had pointed at the full one all along. Humazur's
`iiif-img/2984` answers `full/full/0/default.jpg` (10.2 MB) but **400s on
`full/max/…`**, which is worth knowing before the next re-mirror: the usual
fetch shape fails on this server.

The order matters and is the reusable part. The rescaled annotation is prepared
**first** — GCP `resourceCoords` and the `SvgSelector` mask multiplied by
6501/4876 and 11195/8396, 1.333265 and 1.333373, which differ in the sixth
decimal because the downscale was rounded rather than an exact three-quarters —
then the pyramid is uploaded, then the annotation is upserted. Between those
last two the sheet is live with a georeference 25% out of scale, so that window
is one upload long and nothing else goes in it. `sources/<id>` was repointed to
Humazur in the same pass, so a worker cache miss now proxies the large copy
rather than IA's small one, and `rclone delete --min-age 30m` cleared the old
pyramid's unreachable tiles afterwards.

Safe here because the sheet carried no `ocr_extractions` and no
`footprint_submissions`. On a sheet that carried either, both are in
source-pixel space and would need the same two multipliers.

Still above the 1.1 m/px line, so it stays on the coarse list — 25% less
severe, at no cost, and the last row of that audit that could be closed without
buying anything.

## 2026-09-10 — the 1968 800-tile pass finished, and G's extrapolation was low

`body-1968-20260910g-t800` was stopped at 72 of 96 calls to hold a USD 3
ceiling. Resumed on its own run dir (the 204 tiles on disk are detected as
done), it took the remaining **24 calls for USD 0.7293** — the 72-call prefix
of `calls.jsonl` still reprices to 1.8364, so the two halves are directly
comparable. 1054 raw → **773 unique** at the 0.5 floor.

| over the whole sheet, 367 printed names | `name_recall` | body labels |
|---|---|---|
| `…910a`, tile 1120, `main_map` | 0.3270 (120) | 289 |
| G's union of three passes | 0.3978 (146) | — |
| **the 800 pass alone, complete** | **0.4632 (170)** | 439 |
| **union of all three, `_union-0910-t800full`** | **0.4959 (182)** | 524 |

`agreement` 0.9402 at ±1 cell on 234 matched, 290 labels not in the directory.

**The extrapolation was wrong in the direction that matters.** G projected
0.375–0.385 for a complete 800 pass, reasoning that the four unrun rows were
"the sheet's southern edge where the directory is thinnest". They were not: the
last 24 calls added **+36 printed names** for USD 0.7293, which is **USD 0.020
per name** against the USD 0.09 measured over the first twelve rows — the best
value anything has returned on this sheet, four times over. The thin part of
that projection was the assumption, not the paper.

Total for the sheet: G's 2.2544 plus this 0.7293 is **USD 2.98**, and 0.3270 →
0.4959, +62 printed names.

The merge is a plain union (`ocr.py merge`, three runs, 1439 labels → 990, 427
seen by more than one pass), not a vote — the shifted second 800 pass that
would make a vote meaningful is the next step, not this one.

## 2026-09-10 — the coverage blind spot, made visible in both gates

The one open methodological item from the round-two work, and it was the same
finding twice in one day. Neither gate can score a coverage change:

- the **1882** gate is 85 street and institution names, so the margin content
  the `--grid-offset` fix recovered — `REGISTRE DU CADASTRE`, the Boilloux
  imprint, five legend rows, 20 cadastral street numbers — is unscorable;
- the **1968** gate is the printed street directory, so the 20 hamlet and canal
  names the south band found are unscorable.

Both times a real improvement measured as worth nothing. On the `ocr` gate it is
worse than nothing: unmatched predictions are false positives, so **coverage
scores as harm**. Run `post0910` reads 287 labels against that 85-name GT and
prints `precision 0.2509`, which a reader takes for a run that is three-quarters
wrong. It is a run that read three times as much sheet as the GT describes.

The fix is reporting, not a new instrument, because the signal was already being
computed and printed as an aside:

- `index-agreement` prints `n_unlisted` as its own **`coverage`** line — labels
  read that the directory does not list — and it now joins `agreement` and
  `name_recall` in the `vs baseline` comparison. On the 1968 union that reads
  `n_unlisted 5 → 290  +285`, which is the whole story the two recall numbers
  could not tell.
- `ocr` prints, whenever any prediction went unmatched, that a partial GT prices
  new coverage as false positives — so precision there is agreement with the
  GT's **scope**, not accuracy.

A GT that includes non-directory content is still the real answer, and is still
unwritten. Until then the numbers at least say which of them is blind.

### `post0910` scored, with its caveats intact

For the record, since the run existed for a week as seed rows with no score:

    predictions 287   ground truth 85   matched 72
    precision 0.2509  recall 0.8471  f1 0.3871  mean_iou 0.7441
    char_acc 0.9799   text_recall@0.3 0.9059 (77/85)
    category_acc 0.875   diacritic_recall 1.0 (34 marked GT labels)
    rotation_mae 3.91°

Read `precision` as scope, per above. The caveats already recorded against this
run still stand: 16 of its 20 calls were served from the model-response cache,
and three fixes moved underneath the recipe before it ran, so it is a new
baseline rather than a reproduction of 0.945 / 75-of-85.

## 2026-09-10 — 1968 `--grid-offset 400`, the four-way merge, and the sliver it exposed

Run `body-1968-20260910h-t800off`, same crop and tiling as the aligned 800 pass,
lattice phase-shifted 400 px. **86 calls, USD 2.7096**, 1184 raw → 770 unique.

| over the whole sheet, 367 printed names | `name_recall` | `agreement` | coverage |
|---|---|---|---|
| `…910a`, tile 1120 | 0.3270 (120) | 0.9603 | — |
| the aligned 800 pass | 0.4632 (170) | 0.9366 | 234 |
| the offset 800 pass alone | 0.4278 (157) | 0.9450 | 256 |
| three-way union | 0.4959 (182) | 0.9402 | 290 |
| **four-way union, `_union-0910-4way`** | **0.5450 (200)** | 0.9326 | **380** |

2209 labels → 1187 merged, 573 seen by more than one pass. The 1959 pattern held:
a shifted pass plus a merge lifts the number, here 0.4959 → 0.5450, **+18 printed
names for USD 2.71 — USD 0.15 a name**, the worst rate of the three steps and
still worth having. Sheet total **USD 5.69**, 0.3270 → 0.5450.

### The run lost 32 of its 306 tiles, and the reason is a one-line grid bug

Every failure was an edge tile, in two groups: **16 slivers** 15 px wide, and
**13 perfectly good 615 px columns taken down with them**, plus 3 short bottom
strips.

`_axis_tiles` kept any tile with `w > 0`. On an offset grid the far edge makes a
sliver whenever the region's extent is not a whole number of steps past the
shift: this crop is 10015 wide, so a 600-step lattice shifted by 400 puts its
last origin 15 px from the end and yields a 15x800 column — **entirely inside the
615x800 column before it**, so it could not contribute a pixel even in principle.

It was not merely wasteful. Gemini answers a 15 px strip with `400
INVALID_ARGUMENT: Unable to process input image`, and row-sequence packs four
tiles into one call, so **each sliver failed its three real neighbours too**.
That is the 13. A run can therefore lose good tiles at a rate set by how badly
the region divides, and say nothing but a few 400s in a log nobody re-reads.

Fixed by dropping a tile contained in its predecessor — containment rather than
a pixel floor, because containment is the exact statement of "this tile is
worthless" and needs no threshold to argue about. A narrow far-edge tile that
still reaches past its predecessor is kept. On this crop: **306 → 272 tiles, no
degenerates, and the covered span is unchanged** (281–10296 by 311–9844), the
same tile count as the aligned pass. `test_grid_offset.py` pins the 1968 case
and asserts the property over every region/offset pair it already exercised.

**So 0.5450 is a floor, not a ceiling.** The offset pass scored it with 274 of
its 306 tiles, and 13 of the missing ones were real. A re-run on the fixed grid
would read them; it is not queued, because the tiles it would add are the
sheet's right-hand edge and the marginal apparatus rather than the street body.

## 2026-09-11 — the first segmentation numbers, and the pooling that hid them

Working record, nine run JSONs and the scoring script:
`work/ocr/outputs/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/seg-review/blockprior-20260910/`
(gitignored). **Unreproduced, and nothing was written to Supabase.** The map is the
1882 Plan Cadastral, 12102x8982, 154 tiles of 1024, `epoch_010.pth`
(SAM2.1 hiera_small + LoRA r=4) on MPS unless a row says otherwise.

Ground truth is the only segmentation ground truth that exists — the 46
`footprint_submissions` rows on that sheet, the user's own traces. **They are also
what the LoRA was fine-tuned on, so every LoRA figure here is a train-set score,
flattered by an unknown amount.** A held-out trace set is the fix.

    land_plot 24 · building 17 · road 3 · waterway 2

**The 5 linear rows do not belong in any mean.** A block box cannot score against a
road centreline — measured, 0.042 — so pooling all 46 is what made the first reading
say 0.194 where the areal figure is 0.212 and land_plot alone is **0.249**. Split by
kind, best IoU per GT polygon:

| prompts | land_plot (24) | building (17) | areal (41) |
|---|---|---|---|
| SAM2 LoRA-s on 4 m blocks | **0.249** | 0.160 | 0.212 |
| SAM2 stock-l on same | 0.198 | 0.132 | 0.170 |
| those block boxes used raw | 0.161 | 0.093 | 0.133 |
| raw blocks on disk at 8 m | 0.197 | 0.100 | 0.157 |

Label prompting, which this replaces, was only ever measured pooled over 46:
OCR run `post0910` **0.089**, `v1b` 0.097, `--text-mask` 0.062, label *point* 0.116 —
median 0.000 in every one of them.

1. **The prompt was the fault, not the model.** A label bbox asks what is inside a
   rectangle drawn around lettering, and SAM2 answers by redrawing it: median IoU
   between a mask and its own prompt box 0.64–0.68, 46% above 0.7, half the masks
   4–5 vertices. `--text-mask` is *worse* (0.062) because filling each label box with
   flat paper tone creates a new rectangular object exactly where the prompt is.
2. **Coverage was the ceiling.** Only 22 of the 46 GT polygons contain an OCR label
   centroid, so label prompting could not exceed 48% recall whatever the model.
   Block prompts remove it: median best IoU 0.000 → 0.165 on land_plot, and the union
   of predictions covers 90% of a typical plot.
3. **SAM2 earns its place** — 0.249 against 0.161 for the same boxes used raw, +55%.
   It is snapping drifted modern geometry onto 1882 ink, which is the job.
4. **A bigger stock backbone does not help.** LoRA-small 0.249 vs stock SAM2.1 large
   0.198 at 3.7x the runtime (120.6 s vs 41.6 s). Keep the LoRA.
5. **`building` is capped by granularity, not by the segmenter** (0.160, `cover`
   0.98): a dissolved modern block legitimately holds several 1882 buildings. The ink
   is found, the subdivision is not. Next piece of work is a **within-block split**,
   and the signal for it is the OCR centroids *inside* a found block — useless as a
   detector at 22/46, usable as a splitter.

Do not pin anything to these yet, for three reasons the record states itself: the
0.249 is against the **4 m** dissolve (1,228 blocks) while the file on disk is now
8 m (666), and at 8 m the raw blocks score a higher median per plot (0.173) on far
less of it (`cover` 0.60 vs 0.92); everything is scored on the LoRA's training set;
and `partition_seeds` landed after these runs, so every `n` moves on the next one.

## 2026-09-11 — Gemini as the segmenter, against SAM2 on the same plots

`work/ocr/scripts/seg_gemini.py` asks Gemini for polygons instead of asking SAM2
for masks, and `work/ocr/scripts/seg_eval.py` scores any run of either kind. The
reason to try: SAM2 needs a box prompt per object, a GPU, a LoRA checkpoint and a
mask-to-polygon step, and returns a nameless shape. Gemini returns `box_2d`, a
`label` and a **polygon**, in the 0-1000 space `ocr.py` already parses.

40 calls, one per city block, blocks chosen because they overlap a hand trace
(`--near-gt`) — otherwise the biggest blocks on the sheet are scored against
ground truth that is somewhere else. 37 returned something, 100 polygons. The
whole experiment, including the false starts, was **79 calls / ~USD 2**, median
10.0 s a call, on `gemini-3.8-flash` at `thinking_level=low`.

Scored `--in-frame`, so the comparison is over the **12 land_plots and 2 buildings
that were at least half inside a crop somebody actually called**. Scoring the
whole sheet's 24 plots against a 40-block window measures the window, not the
model — it halves every mean, which is how the first reading of this run came
back at 0.098.

| run | prompts | @.3 | mean | median | cover |
|---|---|---|---|---|---|
| **Gemini, one call per block** | 100 polys / 40 calls | **4** | **0.254** | **0.278** | 0.78 |
| SAM2 LoRA on 4 m block boxes | 950 prompts, whole sheet | 3 | 0.184 | 0.144 | **0.97** |
| SAM2 LoRA on OCR label boxes | 99 prompts, whole sheet | 4 | 0.237 | 0.222 | 0.30 |

**Nobody clears IoU 0.5 on a single one of the 12.** That is the result. Gemini
leads on mean and median IoU at its first attempt, with no GPU, no checkpoint and
no prompt engineering, and it is the only one of the three that returns a name
with the shape. SAM2 keeps coverage — 0.97 of a typical plot's area lands under
*some* prediction — which says the block prior finds the ink and the models
disagree about how to cut it.

Read it as a reason to keep testing, not as a winner. n=12; the blocks were
selected for overlapping traces; and the ground truth is still the 46 traces the
LoRA trained on, which flatters the two SAM2 rows and not the Gemini one.

### Two things the docs say that this model does not do

Both were found by the scores being wrong, and both are silent failures — a
polygon in the wrong place is still a valid polygon.

- **`box_2d` is `[xmin, ymin, xmax, ymax]`**, not the documented
  `[ymin, xmin, ymax, xmax]`. Over 240 real objects, mean IoU between a polygon's
  own bounding box and its `box_2d` is **0.909** read x-first and **0.284**
  read y-first.
- **`mask` is normalized to the image**, not "inside the bounding box". Read as
  box-relative, the same 100 polygons score 0.141 instead of 0.254 and cover 0.14
  instead of 0.78.

`seg_gemini.py` briefly had an `auto` that guessed between the two per object. It
chose "box" for 107 of 139 objects — correctly, given it was comparing against a
transposed box — and the wrong guess reads as a weak model rather than as a bug.
Deleted. A heuristic that can hide a coordinate fault is worse than a flag.

### The reliability problem

Two calls on the same crop, same prompt, same model, minutes apart: **18 objects,
then 1**. Across ten crops the two passes disagreed by a factor of two or more.
SAM2 given the same box returns the same mask. Before any of this is worth
wiring into the pipeline, a run needs to be repeatable or explicitly voted over
several passes — which is what the OCR side already does, and at the same cost
multiplier.

### Then the polygons were drawn on the sheet, and the reading above changes

`render_seg.py` beside the run writes four blocks with all three sources
overlaid (`seg_*.png`, gitignored). Two facts that no metric in this section
reported, and they are decisive:

- **Gemini did not subdivide.** 22 of the 37 answering calls returned exactly
  **one** object — the block it was handed. Three returned 11-13. The hypothesis
  this experiment was built to test, that a VLM does the within-block split a
  box-prompted SAM2 cannot, is **not supported**.
- **It is returning a quadrilateral, not a boundary.** Median **5 vertices** per
  polygon against SAM2's 8, and on the page it is a rotated rectangle laid over
  the block rather than anything following the printed line. SAM2's output, in
  the same crops, visibly traces individual hatched buildings.

So the IoU win is explained rather than impressive: the 12 `land_plot` traces
are block-sized, and a good quadrilateral around a block scores well against
them. Against `building` — the granularity that actually needs the split — it is
0.056.

**What Gemini did do, that nothing else in the pipeline does: it named the
shapes.** 28 of the 100 polygons came back with the sheet's own text attached —
`GRAND SEMINAIRE DES MISSIONS`, `COLLEGE D'ADRAN`, `HÔPITAL MARITIME`,
`CASERNES`, `POUDRIÈRE` — read off the paper and bound to a polygon in one call,
with no OCR pass, no seeding and no `join_labels` step to guess which extraction
belongs to which mask.

That is the result worth carrying. Not "Gemini replaces SAM2" — it draws a
worse boundary and does not subdivide — but that **the naming half of Track C
may not need a join at all**. The pipeline shape it suggests is Gemini for the
name and the coarse extent, SAM2 for the boundary inside it.

### Not tested

`--mode tiles`, the whole-sheet grid. The interesting question there is the
density ceiling — how many parcels in one frame before the answer thins out —
and it is the same question `--tile-metres` answers on the OCR side.

### The resolution confound, tested: it was not the explanation

`--render 0` sends each block at its own width (capped 2048) instead of
resampling every one to 1024. Same 40 blocks, same prompt, +40 calls / ~USD 1.

| | 1024 px | native |
|---|---|---|
| land_plot mean / median | 0.254 / 0.278 | **0.282** / 0.274 |
| land_plot @ IoU≥0.5 | 0 of 12 | **1** of 12 |
| areal mean | 0.226 | **0.251** |
| polygons | 100 | 123 |
| calls returning exactly one object | 20 of 37 | 17 of 36 |
| median vertices | 5 | **5** |

**Retracted, an hour later: the IoU half of that table is noise.** A reviewer in
another session pointed out that this page already documents the model
returning 18 objects and then 1 on identical repeat calls, so one pass a side
at n=12 cannot separate a setting from a re-roll. Running the **1024 arm a
second time** (`--no-cache`, so it asks again rather than replaying) settles it:

| 1024, pass A | 1024, pass B | native |
|---|---|---|
| mean 0.254 · med 0.278 · @.5 **0** · cover 0.78 | mean **0.289** · med 0.280 · @.5 **1** · cover 0.91 | mean 0.282 · med 0.274 · @.5 **1** · cover 0.86 |

One setting against itself moves **0.035** — more than the 0.028 the resolution
change was credited with — and the second 1024 pass scores *above* native on
mean and cover. "The first IoU≥0.5 any segmenter has scored on this sheet"
turns out to be one polygon that the repeat 1024 pass also finds. **Resolution
is unmeasured here, not established.** Anything that wants to claim it needs
several passes a side, which on this sheet is about USD 1 each.

What survives all three passes is the qualitative half, and it is the half the
experiment was for: **median 5 vertices every time**, and 16-20 of ~36
answering calls returning a single object. Gemini declines to subdivide a
block, and it declines at every resolution tried. That is not a noise-scale
effect and it is the answer to the question this run existed to ask.

Also recorded because it will happen again: the repeat pass died mid-run on
`httpx.ConnectError: [Errno 54] Connection reset by peer`. `gemini_client`
retries 429s, 500s and 503s but not a transport error, so an unattended pass
ends at whatever tile the network blipped on — the same fault `vma_worker.py`
had and fixed in `5c`.

### Naming the other model's masks — the part that works

`work/ocr/scripts/name_masks.py` gives each mask the name of the **smallest
named polygon containing it** — `join_labels.py`'s rule, with Gemini's named
quadrilaterals as the source instead of OCR extractions. Of the **213** SAM2
masks inside the 40 called blocks, **61 (28.6%)** come out named:

    13  CASERNE ET ATELIERS DE L'ARTILLERIE     5  ANCIEN CAMP DES INDIGÈNES
    13  PYROTECHNIE                             4  SAINTE ENFANCE
     9  CASERNES                                2  HÔPITAL MARITIME
     7  POUDRIÈRE                               1  COLLÈGE CHASSELOUP LAUBAT

This is a different question from the OCR route, not a better answer to the
same one — and the two fail in opposite directions. The OCR-prompted run names
**99 of 99** of its polygons, because each one *is* a label's box; what it
cannot do is produce a polygon where no label centroid falls, which is 24 of
the 46 traces on this sheet. Gemini reads the block's name off the ink and then
that name propagates to every mask inside it, so `PYROTECHNIE` lands on 13
separate buildings. For an arsenal that is arguably correct and for a mixed
block it is arguably wrong; `MIN_INSIDE` is the knob and nothing has measured
where it should sit.

Neither is a georeference-grade fact yet. Both are cheap.

### Still not tested

`--mode tiles`, the whole-sheet grid, and its density ceiling — the same
question `--tile-metres` answers on the OCR side.

## 2026-09-11 — the block prior built from road surface instead of a buffer

`modern_prior.py --blocks-from-roads`. The block prior up to now is buildings
grown by `BLOCK_BUFFER_M` until they touch, and that constant is the reason
nothing here could be pinned: at 4 m it gives 1,228 blocks and land_plot
0.249, at 8 m it gives 666 and a higher median per plot on far less of it
(cover 0.92 → 0.60). The buffer moves every block edge, so each setting is a
different set of shapes and the two numbers are not two readings of one thing.

`/Users/airm1/Desktop/tasco/hcmc/vector_out/hcmc_vector.gpkg` carries the road
*surface* as 74,566 polygons, plus river and lake. A block is then the
complement of the street network — edges are the kerb lines the survey drew,
and there is no distance to choose. Two numbers remain, a floor and a ceiling
on block area, but they only **select** among parts whose edges are already
fixed: below 500 m² are noding slivers where two carriageway polygons fail to
quite meet, above 200,000 m² is open country, one polygon the size of a
district. On the 1882 sheet that is 1,457 slivers and 1 open-ground dropped,
**1,184 blocks** kept.

Both sets scored raw, no segmenter, against the same 46 traces:

| | n | land_plot mean | median | cover | building mean | areal mean | areal @.3 |
|---|---|---|---|---|---|---|---|
| 8 m buffer-dissolve | 666 | 0.197 | **0.173** | 0.60 | 0.100 | 0.157 | 7 |
| road-surface complement | 1,184 | **0.262** | 0.157 | **0.87** | **0.123** | **0.204** | **11** |

**Read the median against the mean before calling this a win everywhere.**
Mean, cover, @.3 and @.5 all rise, and the median land_plot IoU *falls*
(0.173 → 0.157). Finer blocks fix the cases the buffer lost outright and make
the typical large plot slightly worse, because a plot that one dissolved block
covered is now cut by an alley the 1882 surveyor did not draw. If a within-block
merge ever lands, this is the number it should move.

That is worth stating plainly, because it inverts where this thread started. The
open item after the buffer prior was a within-block **split** — a dissolved
modern block legitimately holds several 1882 buildings, `building` scored 0.160
at cover 0.98, and the ink was found while the subdivision was not. On the road
complement the failure has changed ends: the blocks are already finer than the
plots, and the missing operation is a **merge** across alleys that postdate the
sheet. Both may be needed at different scales, but nothing should be built on
"split" as the standing answer without re-reading these two rows.

**This particular comparison is the one clean row on this page.** Every other
result here is measured against the 46 traces the LoRA trained on, which
flatters any SAM2 row and makes "a better prior" unfalsifiable. Neither run
above involves a model at all — they are raw geometry against hand traces — so
the training-set objection does not reach them. It is still one sheet and 24
plots, and the corpus-level gate is still ~20 held-out traces on a second sheet.

Counts are not comparable enough to worry about: 1,184 against 666 is 1.8x,
under the 3x at which `seg_eval` warns about `cover`.

**Both rows are scored against all 24 plots on the whole sheet, and must not be
compared against a windowed run.** `--in-frame` only bites when a run records a
crop per polygon; raw prior geometry records none, so it silently scores against
everything. That is the right denominator for a whole-sheet prior and the wrong
one for anything that looked at a window — the Gemini runs read 0.098 against
all 24 and 0.254 against the 12 they covered. Re-score before putting a windowed
run in this table.

`--blocks` and `--blocks-from-roads` both write `blocks.geojson` so consumers
(`to_sam2_seeds.py`, `--prior`) read one name; passing both is refused rather
than letting the later branch win silently. Pass `--out` to keep two.

### Not done

SAM2 has not been re-run on these blocks. The 0.249 land_plot figure for
LoRA-on-blocks is against the 4 m set, so the whole prompted arm wants
re-measuring on this prior before any of it is compared to the Gemini runs.

---

## Thinking, and one call for names + numbers (2026-09-12)

Three findings, all measured on two sheets with a **printed numbered legend as
the ground truth** — the 1923 Saigon-Cholon sheet (`1bce28f0`, index 1..182) and
the 1942 Plan de Saigon - Cho Lon (`eca788e5`, index 1..236, 235 entries read).
No hand labelling: the sheet states every number that exists, so numeral recall
is measurable for the price of reading the legend box.

The scripts are scratchpad one-offs, not pipeline code. Nothing here is wired in.

### 1. `thinking=False` is cheaper AND better on numerals

1923 sheet, 42 tiles of the `main_map` crop, one call per tile:

| metric | thinking on | **thinking off** |
|---|---|---|
| found | 116/182 | **126/182** |
| orphans (number not in the index) | 0 | 0 |
| cost | $0.435 | **$0.129** |
| wall clock | 8.5 min | **3.8 min** |

Thinking was **93% of billed output** on the thinking-on run: 7,009 logged output
tokens against 104,904 billed. (Billed output is `total_tokens - input_tokens`;
see the DEFAULT_MODEL comment in `gemini_client.py`.)

Confirmed on the 1942 sheet: 218/235, 0 orphans, $0.123.

This contradicts the comment at `gemini_client.py:284` — "every text path measured
so far is better with it." Numerals were never one of those paths; they were
Tesseract-local until this date.

Two traps for anyone re-running it:

- `extract_labels_sequence` **does not take the flag**. Only `extract_labels`
  does, so the production row-sequence body path cannot be A/B'd without a code
  change. That test is still open and is where the money is — the 1923 body
  passes spent 44% and 56% of billed output on thinking.
- The tile cache key does not include the flag (the module says so). An A/B in
  one `cache_dir` silently returns the first run's answers.

### 2. Gemini beats Tesseract at numerals, which inverts the local/Gemini split

1923 sheet, same crop. `local_vision.spot_numerals` is psm 11 + a digit whitelist:

| | local (tesseract) | gemini |
|---|---|---|
| rows returned | 259 | 139 |
| found | 96/182 | **116/182** |
| orphans | 30 (`700`..`787`, `1477`, `2005`) | **0** |
| numbers claimed >1x | 34, worst `4x36`, `2x17`, `7x16` | 21, worst `x3` |

Local returned 87% more rows for 21% fewer real hits. The rationale in
`local_vision.py` — "geometry and digits are the parts classical tools do as
well as a frontier VLM" — does not hold for small, faded, half-rotated numerals
printed on ink.

They are complementary, not ordered: union was 153/182, with 57 gemini-only and
37 local-only. Local costs nothing, so a vote of the two is the obvious shape.

### 3. Asking for names and numbers in ONE call reads MORE names

> **Correction, same day.** This is not a new finding. `seq-v1-idx` (commit
> e8a5c2d8, 2026-09-10) already does exactly this, and does it better — the
> September 1942 run scored **226/235 numerals and 819 distinct names** against
> the 187/326 below. The lever it has and the experiment below does not is
> **ground per call**: `--tile-metres 1400` sizes the grid from the sheet's own
> m/px (97 tiles, 65 demoted to low-res and 13 skipped by `--auto-priority`)
> instead of a flat 2400px. That is §3 of *Getting more out of OCR*, and it is
> ranked there for a reason. The rows below are one bad recipe measured against
> another; they are kept because the direction of both effects is real, and
> because the 2400px arm is what a sheet gets if nobody passes `--tile-metres`.

The production row-sequence path (`seq-v1` + `sequence_frame_rules`), with
`legend_ref` appended to the category enum and a rule overriding the prompt's
"do NOT extract bare integers". One pass against one pass, same tiles, same
prompt but for the numeral rule, legend boxes excluded from both counts:

| sheet | names only | **combined** | delta |
|---|---|---|---|
| 1923 | 252 distinct | **299** | +47 |
| 1942 | 241 distinct | **326** | +85 |

Reproduced, and larger on the second sheet. No explanation offered — asking for
small isolated marks may make the model sweep more carefully, but that is a
story, not a measurement.

The cost is numerals, also reproduced and also in one direction:

| sheet | dedicated numerals | combined | delta |
|---|---|---|---|
| 1923 | 126/182 | 106/182 | −20 |
| 1942 | 218/235 | 187/235 | −31 |

So it is a trade, not a free win. Per sheet, at 6 row-calls + 42 tile-calls:

| recipe | calls | cost | names | numbers |
|---|---|---|---|---|
| names alone + numerals alone | 48 | $0.35 | 241 | 218 |
| combined alone | 6 | $0.53 | **326** | 187 |
| **combined + dedicated numerals** | 48 | $0.65 | **326** | **218** |

The third row is the recommendation: +85 names for ~$0.30, both weaknesses
cancelling.

### What is NOT established

- **Against the two-pass production baseline.** Every row above is one pass.
  Production runs the grid twice and votes (41/43 vs 39/43, above). Whether
  combining still wins against that is untested.
- **The 1942 sheet already held 230/235 numerals** in `ocr_extractions` from the
  September `2026-09-11-idx` / `idx2x-20260912` runs — better than anything
  measured here. Read what those did before changing the pipeline.
- **Names have no ground truth on either sheet.** "Distinct folded cores" is a
  denominator-free count, exactly the metric §2 of *Getting more out of OCR*
  warns about. `eval.py index-agreement` against a printed street directory is
  the honest version and was not run.

### Incidental: the level0 fetcher had no tile cache

Not a model finding, but it is why these runs took as long as they did. On the
1942 combined pass the split was **12.2 min fetching tiles against 5.1 min of
model time**, repeated in full for each of three runs over the same crop.
`fetch_crop` (level2) has cached since the start; `fetch_crop_level0` — the path
every mirrored sheet in the archive uses — never did. Now does, per tile, in the
same `.tile_cache/ocr`. Measured on one 2400px crop: 29.0 s cold, 0.1 s warm.
Covered by `iiif_tiles.py --self-check`.


---

## The index_key bug: `seq-v1-idx` could not return its own category (2026-09-12)

`seq-v1-idx` instructs the model to return `category="index_key"`. That value was
never added to `EXTRACTION_SCHEMA`'s category enum. Structured output is
constrained to the enum, so the model could not answer with it: **every index
numeral silently landed in `other`.**

It had been hit before and treated as a one-off — `scripts/oneoff/rescan_1942_to_2x.mjs`
reclassifies `other` + numeric text to `legend_ref` after the fact, with the note
"the prompt's own `index_key` never made it into a response." The cause was never
fixed, so it repeated on the next new sheet.

Measured on the 1878 Plan de la Ville de Saigon (`dc2eda7d`), whose layout pass
found a `name_list` region described as "Numbered reference list … (1 to 29)":

| | numerals in DB as `legend_ref` | scored against the 29-entry index |
|---|---|---|
| before the fix | 0 | **0/29** (28 present, all `other`) |
| after the fix | 28 | **22/29**, 1 orphan |

The fix is two parts, both in this commit:

- `prompt.schema_for(prompt_key)` returns `EXTRACTION_SCHEMA_IDX` — a copy with
  `index_key` appended — for `seq-v1-idx` only. Kept separate from the shared
  schema **on purpose**: the Gemini result cache keys on `schema_version`, and
  `ocr.py` pins it with `assert … == SCHEMA_VERSION, "cache went cold"`.
  Widening the shared enum would cold-cache every run of every other prompt.
- `ocr._db_category` maps `index_key` → `legend_ref` on both write paths (batch
  and merge). One name at the model boundary, one in the database — `legend_ref`
  is what the column, the review UI's Numbers tab and the `legend_entry` join
  already speak.

Two things this sheet also showed, worth carrying:

- **`ocr legend` only reads regions categorised `legend`.** This sheet's numbered
  list is categorised `name_list`, so the command returned **0 entries and exited
  0**. A sheet with an index looks identical to a sheet without one. Pointing
  `--regions` at the box by hand returned 29.
- A silent miscategorisation is paid for twice: the numerals were extracted and
  billed on the first run, then extracted and billed again on the second.

## `--low-thinking` on the body pass (2026-09-12)

`thinking` was plumbed into `extract_labels` but **not** `extract_labels_sequence`,
which is the production row-sequence path — so the finding above could not be
tested where the money is. It is now a parameter there and a `--low-thinking`
flag on `ocr batch`, default off.

**The sequence path's cache key carries the flag** (`schema_version + "+lowthink"`).
`extract_labels`' key does not, which the module's own ponytail note calls out;
an A/B in one `cache_dir` there replays the first run's answers.

1878 sheet, same crop, same recipe, one flag apart:

| | thinking on | **low** |
|---|---|---|
| cost | $0.325 | **$0.143** |
| wall clock | 3.7 min | **1.7 min** |
| numerals | 22/29 | 21/29 |
| distinct names | 121 | **124** |
| orphans | 1 | 1 |
| thinking share of billed output | 60% | 0% |

Less than half the cost and half the time, for one numeral. Three sheets now say
low thinking is free or better (1923 and 1942 numerals, 1878 body); none says it
costs recall. It stays opt-in until a fourth agrees — score any run against the
sheet's printed index before trusting it.

## 2026-09-18 — colour blocks: the gate is not cleared, and the metric says why

`work/ocr/scripts/colour_blocks.py` on the whole 1882 Plan Cadastral, from the
cached full scan, `--render 6051` (2x), `--close 5`, splits found by vote:
`r - g` +0.0725 from 20/64 crops, `r - b` +0.072 from 32/64. **189 blocks, 124
salmon + 65 blue-grey, 5.9 s of CPU** — no GPU, no checkpoint, no network.

Scored against the sheet's hand traces with `seg_eval.py`. **The 118-row count
recorded here was contamination, not growth** — see the correction at the head
of this file. `load_gt` was returning 46 traces plus 72 `sam-auto` label boxes;
it now filters on `source`. The `land_plot` figures below are unaffected (24/24
volunteer); any `building` figure at n=89 is void.

| land_plot (n=24) | mean | med | @.5 | @.3 | cover |
|---|---|---|---|---|---|
| **as `seg_eval` prints it** | 0.124 | 0.003 | 2 | 4 | **0.01** |
| the 8 pigmented plots | **0.352** | 0.295 | 2 | 4 | **0.97** |
| the 16 cream plots | 0.010 | 0.000 | 0 | 0 | 0.00 |

**The gate was "beat `--blocks-from-roads` at 0.262 / 0.87 on the 24 land_plot
traces". It is not cleared, and not for a reason a threshold can fix.** This
pass emits only the pigmented classes; cream *non affectées* parcels are
excluded by design. The plan assumed from the deleted pipeline's tally that
cream was about a quarter of the blocks. In the actual ground truth it is
**16 of 24 land_plots — two thirds** — so the metric is dominated by the one
class the method cannot see, and the pooled 0.124 pools 16 structural zeros
with 8 real answers.

Measured, not inferred: splitting the 24 by the pigment share inside each
traced polygon gives 15 uncovered plots at **82% cream, 3% salmon** and 7
covered ones at **44% salmon, 22% blue**. The bimodality in the per-plot
coverage — plots at 0.000 and plots at 0.99, spatially interleaved — is that
split and nothing else.

**Read the 0.352 with the caveat it deserves.** n=8, and the subset was chosen
by the classifier under test, which is the same selection bias the `--near-gt`
Gemini run carries three sections up. It is a reason to finish P2, not a number
to pin.

### Why cream cannot simply be added, measured

Including cream in the componented mask collapses the sheet:

| mask | components | in the 200-120,000 m² band | largest |
|---|---|---|---|
| pigment only | 14,052 | **189** | 0.99 km² (36% of the mask) |
| pigment + cream | 362 | **0** | **11.91 km² (100% of the mask)** |

The street network welds every cream parcel to every other one, so there is no
band, no block and no polygon. **P2 is therefore a prerequisite for P1's own
score, not a follow-on** — the plan in `docs/journals/260918-colour-blocks.md`
had the order wrong, and the order is now P2 before any re-score.

Two other readings worth keeping:

- **`building` is capped as expected and for the known reason** — 0.057 pooled,
  0.088 over the 36 pigmented ones, cover 1.00. A block-level prediction
  against a building-level truth; the ink is found and the subdivision is not,
  which is the same ceiling the block-prior runs hit at 0.160.
- **`waterway` scores 0.432, the highest of any class here, by accident.** The
  Genouilly canal is blue-grey, so it lands in the cool class and comes back as
  a "block". Correctly coloured, wrongly typed.

## 2026-09-18 — P2: the missing class was green, not the street

The section above closed on "P2 is a prerequisite: separate the street ribbon
from the cream parcel." **That was the wrong diagnosis, and the picture said so
before any metric did.** Cropping the sheet around the uncovered `land_plot`
traces and drawing them shows what they actually sit on: *Direction des Travaux
Publics*, *Hôtel du Procureur Général*, *Direction de l'Intérieur*, *Conseil de
Guerre* — the pale grey-green **administrative parcels under fine diagonal
hatching**. Not unassigned land, and not street.

Two attempts on the wrong diagnosis, both rejected by measurement:

- **Erosion to separate ribbon from parcel.** Cream is 72.9% of this sheet — it
  is mostly open country, not a street network — so the mass survives erosion
  at 8.86 km² at every radius from 6 to 24 px, and "street" comes to 2% of
  cream. There is no ribbon to peel.
- **Local ink density as the hatching signal.** Real but not specific: hatched
  parcels read 0.120 against open cream's 0.000, yet built-up areas score just
  as high, so `cream & density > t` reaches cover 1.00 at IoU 0.137 — it finds
  the right places with the wrong extents.

**The axis was the one already in use.** Scoring six candidates against the
traced pixels themselves — the share of hatched pixels falling inside cream's
10-90 range, lower is better:

| axis | hatched p50 | cream p50 | overlap |
|---|---|---|---|
| **r - g** | 0.027 | 0.059 | **0.17** |
| r - b | 0.094 | 0.149 | 0.22 |
| g - b | 0.059 | 0.090 | 0.29 |
| S | 0.119 | 0.169 | 0.28 |
| V | 0.824 | 0.875 | 0.37 |
| local ink | 0.013 | 0.000 | 0.42 |

The hatched class sits *below* cream on `r - g`, and `find_split` only ever
searches right of the global peak, which is where salmon is. At `RG_BINS` the
two modes are two bins apart and invisible; at 48 bins over (-0.05, 0.19) the
structure is plain — green peak +0.025 (13.4%), valley +0.030 (5.0%), cream
peak +0.045 (15.5%). So the fix is the same primitive mirrored, exactly as
`cool_split` does it: negate, and the left mode becomes a right one.
`green_split` votes +0.032 on **53 of 64 crops**.

| land_plot (n=24) | n | @.5 | @.3 | mean | med | cover |
|---|---|---|---|---|---|---|
| P1, pigment only | 189 | 2 | 4 | 0.124 | 0.003 | 0.01 |
| **P2, + green** | 253 | 4 | 5 | **0.247** | 0.161 | **0.98** |
| `--blocks-from-roads` | 1184 | — | — | 0.262 | — | 0.87 |

**Class precedence is load-bearing.** Blue-grey (r-g 0.024) and hatched green
(0.027) both sit low on the same axis, so claiming green first swallows the
military parcels: blue went from 65 blocks to **1**. Blue is claimed first
because `r - b` distinguishes it and `r - g` does not. `--self-check` pins that
the two masks never overlap.

### The closing sweep, and why it is not a result

| `--close` | blocks | land_plot mean | med | cover | building cover | blue blocks |
|---|---|---|---|---|---|---|
| 0 | 424 | **0.273** | 0.207 | 0.90 | 0.66 | 188 |
| 2 | 401 | 0.246 | 0.169 | 0.87 | — | — |
| 3 | 353 | 0.253 | 0.181 | 0.94 | 0.92 | 97 |
| 5 (default) | 253 | 0.247 | 0.161 | **0.98** | **0.97** | 44 |
| 9 | 175 | 0.125 | 0.086 | 0.97 | — | — |

k=0 clears 0.262 and k=5 does not. **Do not read that as a ranking.** The
spread across k=0..5 is 0.027 at n=24, the same magnitude as the 0.035 this
file records between two *identical* repeat passes of the Gemini run, and the
ends trade against each other: k=0 fragments blue into 188 components where
k=5 gives 44, and building cover falls 0.97 to 0.66. The default stays 5.
Tuning a knob on 24 polygons is how the pooled 0.194 happened.

### What is left, and it is P3

The predictions that match a traced plot are **3.72x its area**: the hatched
quarter comes back as one block where the survey drew four or five parcels
inside it, divided by the same 1-2 px lines that divide buildings inside a
salmon block. Coverage is solved (0.98); granularity is not. That is the same
ceiling the block-prior runs hit at `building` 0.160, and it is what P3 — the
within-block split — exists for.

`building` itself is unchanged by any of this, as expected for a coarse pass:
0.093 mean, cover 0.97.

## 2026-09-18 — P3: the null was measured on lettering. RETRACTED the same day.

P3 was "the two-reds within-block split", on the hypothesis that the pale
salmon wash is the plot and the darker red-brown fills inside it are the
buildings, so the subdivision would be a second threshold rather than a
segmenter. It was recorded as a firm null. **The null was measured against 89
`building` traces, 72 of which are OCR label boxes** — see the correction at the
head of this file. A label box sits on open wash by construction, so it is
indistinguishable from the plot around it, and 72 of them dragged every axis to
chance. The reading below replaces it.

**Re-measured against the 17 real traces, a colour axis does separate a
building from the plot it stands on.** Same measure as the green axis: share of
building pixels inside the open plot's 10-90 range, lower is better.

| axis | building p50 | plot p50 | overlap (17 real) | overlap (89 contaminated) |
|---|---|---|---|---|
| r - g | 0.098 | 0.027 | **0.23** | 0.65 |
| r - b | 0.176 | 0.094 | 0.30 | 0.67 |
| S | 0.231 | 0.125 | 0.29 | 0.68 |
| V | 0.745 | 0.827 | 0.49 | 0.65 |
| g - b | 0.075 | 0.059 | 0.94 | 0.87 |

The green/cream pair scores **0.17** on this measure and was accepted as
separable. `r - g` at 0.23 is in that neighbourhood; 0.65 was not.

**And it is the wash, not the outlines.** A building trace holds 0.257 ink
against open plot's 0.091, so the whole shift could have been the printed
outlines inside the polygon rather than a second fill. Excluding every ink pixel
(V < 0.55) from both sides and re-running, the separation does not weaken — it
**sharpens to 0.18 on `r - g`** (building p50 0.098 vs plot 0.027), 0.23 on
`r - b`, 0.25 on `S`. The paper inside a building outline really is redder and
more saturated than the paper beside it. There are two reds.

**What this does not yet establish.** n=17, 0.13 Mpx of building against 6.8 Mpx
of open plot, all traced by one person on one sheet. It says an axis exists, not
that a threshold on it beats 0.160 — that is a run, and it has not been made.
The recorded exit condition stands unmet in both directions: not a null any
more, not a cleared gate either.

The rest of P3's finding is unaffected, because it was never measured against
the building traces: the hatch arithmetic below, and SAM2 earning its place at
0.249 against 0.161 for the same boxes used raw.

### Isotropic morphology cannot cut the parcel dividers either

The other half of the granularity gap is `land_plot`: a matched block is 3.72x
the traced plot, because the hatched quarter returns as one block where the
survey drew four or five parcels. Measured on the admin quarter at native
resolution, scanning horizontally across the hatching:

| | source px | at `--render 6051` |
|---|---|---|
| ink run width (= a divider) | p50 **2** | **1** |
| gap between ink runs | p50 6 | 3 |
| hatch period | **8** | **4** |

A closing that rejoins a block across its hatching must span the *period*; a
divider is one ink run, which is **narrower**. So no isotropic kernel can
bridge the first and not the second — it is not a tuning problem, it is
arithmetic. That is also why the `--close` sweep trades land_plot against blue
fragmentation rather than finding a setting that wins both.

### Orientation: the one route left, and why it was not built

The hatch is directional and a divider generally is not parallel to it, so an
opening with a line at the hatch angle should keep hatch and drop dividers.
Measured on the admin quarter, ink retained by a length-15 line opening peaks
twice — **40° at 11.2% and 140° at 11.4%** — because two adjacent blocks hatch
in different directions. So the angle is **per block, not per sheet**, and the
peak retains only ~11% of the ink: the other 89% is building outlines, block
outlines and lettering, which such a filter would hand back mixed together.

A working version therefore needs per-block angle estimation *and* a way to
tell a divider from a building outline from a letter. That is a large build
with no measured promise behind it, so it is recorded rather than attempted.
**Revisit only if SAM2 on colour-block prompts leaves parcel granularity as the
top remaining error.**

### What P3 hands to the GPU instead

The colour blocks load as a SAM2 prior unchanged — `load_seeds_from_prior`
clips 253 blocks to 246 seeds inside `main_map`, median box 265 x 227 source
px. Against the modern-geodata prior's **950 prompts** on the same sheet that
is ~4x fewer encoder-bound prompts, and they sit on the ink rather than 11.3 m
RMSE and 141 years away from it.

    python work/MapSAM2/inference_tiles_as_video.py \
      --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \
      --prior <out>/blocks.geojson --mode prompted --lora ...

That run is the real test of the within-block split, and it needs a GPU.

## Colour blocks + cream parcels (2026-09-18)

`colour_blocks.py --render 6051 --cream --drop-furniture`, whole 1882 sheet,
8.6 s of CPU, no GPU and no checkpoint. Scored against the 46 hand traces
(re-scored 2026-09-18 after `load_gt` was found to be returning model output
alongside them — see the correction at the head of this file).

| run | n | @.5 | @.3 | mean | med | cover |
|---|---|---|---|---|---|---|
| **land_plot (n=24)** | | | | | | |
| blocks only | 253 | 4 | 5 | 0.247 | 0.161 | 0.98 |
| + cream parcels | 1103 | 7 | 8 | **0.346** | 0.218 | 1.00 |
| + furniture drop | 1082 | 7 | 8 | 0.346 | 0.218 | 1.00 |
| + cream hulls cut off the blocks | 1044 | 7 | 8 | **0.350** | 0.218 | 1.00 |
| + `--recut` oversized blocks | 1296 | 7 | 8 | 0.358 | 0.232 | 1.00 |
| `modern_prior --blocks-from-roads` | — | — | — | 0.262 | — | 0.87 |
| **building (n=17, re-scored)** | | | | | | |
| + cream hulls cut off the blocks | 1044 | 1 | 3 | **0.122** | 0.050 | 1.00 |
| ~~building (n=89)~~ | ~~1082~~ | ~~3~~ | ~~10~~ | ~~0.114~~ | ~~0.064~~ | ~~1.00~~ |

The struck row is the contaminated one, kept so the correction is legible: 72
of its 89 "traces" were OCR label boxes. Scoring against them *depressed* the
figure, because a block prior cannot match a word of lettering — the honest
number is higher than the one it replaces, not lower. It is still the ceiling
the block prior hits, and still what P3 exists to lift.

The cream pass is a second componenting of the *cream* class at its own ink
threshold and with no closing — `cream_ink` sweeps V up to the sheet's paper
peak and keeps the value that puts the most banded area in the band (0.80 here;
the block pass stays at 0.55). Rationale, the sweep table and the failure it
corrects: `docs/journals/260918-colour-blocks.md` § P2b.

**The n column is not decoration.** These runs are 253 vs ~1100 predictions and
`score()` takes the best match per trace, so the mean can only rise with count.
The defensible claims are the ones that do not depend on n: missed land_plot
traces 2 → 0, @0.5 4 → 7, and claimed area 14.4% → 32.9% of the scan.

**Repeatability holds only when the input image is pinned, and that turned out
to matter more than any knob in this table.** Two runs of the identical command
on 2026-09-18, minutes apart, both fetching over IIIF, returned 1109 and 1314
features and scored `land_plot` **0.375 and 0.243** — a 0.13 spread, wider than
every improvement this section records. `fetch_crop` falls back to stitching the
tile pyramid when the region endpoint is slow, and `fetch_crop_level0`
deliberately refuses to cache a stitch with a hole in it, so a run can silently
work from a differently-complete image; a hole reads as blank paper, which moves
the swept splits, which moves every class.

Run with `--local-image` against the cached full scan and it is exact: two runs
byte-for-byte identical, 1044 features, blue 41 · cream 802 · green 106 ·
salmon 95, reproducing this table's committed row. **Every figure in this
section is the pinned run.** Score over the network and you are measuring the
fetch as much as the threshold.


## 2026-09-18 — the legend key, and the first check that can see a class label

Reported from the rendered layers, not from a number: blue misses blocks, salmon
claims white plots with red buildings, and there is a grey class nobody handles.
All three trace to the legend, which defines **five** classes where `classify`
implements four. Swatches sampled from the `legend` triage region, median
(r - g, r - b) and ink share:

| legend class | r - g | r - b | ink% |
|---|---|---|---|
| ...aux services militaire et de la marine | 0.000 | 0.008 | 21.6 |
| **...au service local** | 0.039 | **0.067** | **59.6** |
| ...non affectées | 0.059 | 0.149 | 8.5 |
| propriétés communales | 0.016 | 0.122 | 2.0 |
| propriétés particulières | 0.165 | 0.263 | 10.6 |

*Service local* is a hatch, not a tint, and its `r - b` band straddles the cool
split at 0.073 — so it lands on both sides pixel by pixel and welds the military
blocks to the administrative ones. Communales and service local also **swap order
between the two axes**, which no cascade of 1-D cuts with a fixed precedence can
separate. Full reasoning: `docs/journals/260918-colour-blocks.md`.

**`--swatch-labels`** names each finished polygon against those swatches, diluted
by one fitted scalar (**alpha 0.52**, fitted on the pigmented blocks only —
including the ~800 bare-paper cream parcels drags it to 0.38 and costs a point on
the check below). It runs after the geometry is fixed, so it is label-only:

| | n | land_plot mean | med | building mean | med |
|---|---|---|---|---|---|
| pinned baseline | 1044 | 0.350 | 0.218 | 0.122 | 0.050 |
| `--swatch-labels` | 1044 | 0.350 | 0.218 | 0.122 | 0.050 |

Identical, as intended — **and that is the problem with scoring it here.**
`seg_eval` scores geometry against `land_plot`/`building` and never reads
`feature_type`, so every number in this file is blind to classification. The
check is ten blocks named on the sheet, located by their OCR label, verified by
hand: **4/10 → 6/10**, with *Magasins des Travaux Publics* and *Nouveau Palais de
Justice* newly correct as `admin`.

The key cannot hold the cream/green boundary on its own — the two sit 0.043 apart
on `r - g` and dilution closes that further, and green came back 470 times. The
pass's own voted `green_split` is fitted from the sheet's pixels and is better
for that one cut, so the two sources are used where each is stronger:

| | green | cream | admin | blue | salmon | named |
|---|---|---|---|---|---|---|
| before | 106 | 802 | — | 41 | 95 | 4/10 |
| legend key alone | 470 | 261 | 233 | 42 | 38 | 6/10 |
| key + voted trough | **53** | **678** | 233 | 42 | 38 | **6/10** |

The 53 are the Jardin de la Ville, the Cimetière Européen and the Château d'Eau.
The two measures are not interchangeable — a swatch is an all-pixel median (two
classes *are* ink) and the trough is paper-only — so `wash_points` returns both
and the arbitration compares paper to paper. Known-wrong after all of it:
`admin` takes tree stipple in both gardens and part of the Champ de Manœuvres.

Two nulls on the way, both reverted, neither to be re-attempted as stated:
**ink density** as the hatch detector (land_plot 0.247 → 0.242, legend agreement
42.7% → 30.7%) and **thin-ink density** (→ 0.244). A densely built block carries
as much ink as a hatched one; the distinguishing property is orientation, which
is priced in the journal.


## 2026-09-18 — orientation: the class the sheet draws as ink, not as colour

The last known-wrong thing in the row above — `admin` taking tree stipple in
both gardens and part of the Champ de Manœuvres — closed on the only route the
journal had left. A hatch is directional and stipple is not.

**Measured as the structure tensor of the greyscale gradient**, per finished
polygon, `sqrt((Jxx - Jyy)² + 4Jxy²) / (Jxx + Jyy)`:

| block | what it is | coherence |
|---|---|---:|
| Magasins des Travaux Publics | black hatch | 0.738 |
| Nouveau Palais de Justice | black hatch | 0.589 |
| Champ de Manœuvres | faint blue ruling | 0.118 |
| Jardin Botanique | tree stipple | 0.036 |
| Cimetière Européen | tree stipple | 0.029 |

`--hatch-coherence`, default 0.30, applied only to polygons the legend key has
already called `admin`; 61 of 233 fail it and fall back to the nearest of the
three *tint* classes, matched on their paper.

| | n | land_plot mean | med | building mean | med |
|---|---|---|---|---|---|
| `--swatch-labels` | 1044 | 0.350 | 0.218 | 0.122 | 0.050 |
| + hatch test | 1044 | 0.350 | 0.218 | 0.122 | 0.050 |

| | admin | cream | green | blue | salmon | named |
|---|---:|---:|---:|---:|---:|---:|
| key + voted trough | 233 | 678 | 53 | 42 | 38 | 6/10 |
| + hatch test | **172** | 735 | 57 | **42** | 38 | **6/10** |

**The named check does not move and that is the honest headline.** What moves is
the rendered layer: `admin` no longer claims either garden or the Champ, and
both genuinely hatched blocks keep it. The Champ and the Botanique go from
`admin ✗` to `cream ✗`; the Botanique misses `green` by 0.007 on the voted
trough, which is the trough's resolution and not this test's to fix. Blue stays
at exactly 42 — no block *gains* a class from the fallback, which is the check
that one error is not being laundered into another.

**Three measurements rejected on the way, none to be re-attempted as stated:**

- **Directional line opening** — the route this journal had priced. Swept over
  12 angles at 7 / 11 / 15 render px, the Jardin Botanique's stipple survives
  *better* than the *Magasins* hatch at every length (0.118/0.042/0.032 against
  0.108/0.030/0.017). A hatch line is one source pixel of grey, so at `INK_V` it
  is already broken and has no length to open along.
- **Coherence on the thresholded ink mask** rather than on the gradient, for the
  same reason: 0.215 for *Magasins* against 0.064 for *Palais de Justice*, both
  hatched. No separation.
- **Falling back on the all-pixel median.** Scores *better* on the named check
  (7/10) and paints both gardens military, because a dense black stipple's
  median (0.039, 0.078) *is* the diluted blue prototype (0.030, 0.079). Blue
  42 → 73. Rejected on the picture; the extra point was luck, the Champ's
  polygon being indistinguishable from the garden's on every colour axis
  measured.

Cost: about +1.5 s on the whole sheet. Geometry untouched by construction, and
the default path without `--swatch-labels` is byte-for-byte identical.
