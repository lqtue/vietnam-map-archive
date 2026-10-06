# What the 1882 OCR review teaches the other District 4 sheets

This record covers the human review of OCR on the 1882 *Plan Cadastral de Saigon*
(`0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`, 12102 × 8982 px at 0.3416 m/px), read from `ocr_labels` on
2026-10-06, and which of its patterns should carry over to the 1895 (`f08aa539`), 1923 (`1bce28f0`), 1942
(`eca788e5`), 1959 (`34d4edb2`) and 1968 (`3a446d85`) sheets. Everything is produced by
`work/ocr/scripts/review_patterns.py`, which writes `work/ocr/outputs/<map>/review_patterns.json` and can be
rerun on any sheet with `--map`. **Scope warning:** 1882 is the only District 4 sheet whose body text has been
reviewed. The others hold 1–8 validated body rows each (1923 has 182 validated legend rows, 1959 has 156
validated street-index rows, which is a different task), so every rule below is a hypothesis drawn from one
French sheet until its sheet is reviewed and the script is rerun. Proposed prompt changes need the user's approval
and none has been made.

## The numbers

| status | rows | note |
|---|---|---|
| validated | **212** | 192 label rows + 20 text-group rows; 176 model-read, 16 `manual` (human-added boxes) |
| rejected | 318 | 313 model-read rows were classified (below) |
| pending | 11 | |

By run: `v1b` 104 validated / 92 rejected / 5 pending; `post0910` 105 / 193 / 6; `2026-09-04T0527` 3 / 33 / 0.
The old eval gate scored 43 validated `v1b` rows; the truth is now 212 (EVAL-BASELINE.md, 2026-10-06 entry).

## Findings

### 1. A rejection is mostly not an error

Three runs read the same sheet and the reviewer kept one reading per label. Sorting the 313 rejected model rows
by what sits under them:

| class | rows | meaning |
|---|---|---|
| dup | 133 | a validated row sits on it (IoU ≥ 0.3) with the same folded text: another run's copy of a good label |
| fragment | 119 | at least half its box lies inside a validated box, text differs: the model cut one printed name into pieces |
| orphan | 19 | nothing validated near it: 15 are legend text (including the scale bar), 4 are `Ge B 9`-style marks |
| text-wrong | 16 | a validated row sits on it with different text |
| box-off | 16 | same text validated nearby, box barely overlapping |
| part | 4 | one text contains the other |
| adjacent | 6 | small overlap, unrelated text |

So **20 rows (6%) are genuine misreadings, and 19 more are the reviewer scoping the legend out**. There is no
hallucination class worth the name: the model did not invent text. Its failure on this sheet is geometry (the
fragments) and what it leaves out (road numbers), not transcription.

The 133 dup twins sit a median 9.5 px (3.2 m) from the row that was kept; p90 32 px, p95 40 m, p99 77 m.

### 2. Confidence barely predicts anything

On the 356 validated or rejected-non-dup model rows, the chance that a rejected row has lower confidence than a
validated one is 0.70 (0.63 against any rejection, 0.63 against the 20 wrong-text rows). Confidence takes about
ten values and has run-specific habits: `v1b` says 1.0 for 70 rows, `post0910` says 0.95 for 146.

| cutoff (flag if below) | flagged | precision vs rejected-non-dup | recall | precision vs wrong text | recall |
|---|---|---|---|---|---|
| 0.80 | 19 | 0.95 | 0.10 | 0.67 (3 flagged) | 0.10 |
| **0.90** | 47 | **0.89** | **0.23** | 0.44 | 0.20 |
| 0.95 | 118 | 0.72 | 0.47 | 0.21 | 0.45 |

Reading it: below 0.9 almost everything is rejected (49 of 54), but that is a sixth of what gets rejected (49 of 313), and the rows at 1.0 are still rejected 42% of the time (34 of 81; 19 of the 34 are dups, 6 fragments, 4 wrong text). Confidence is a triage
hint, never an accept signal.

### 3. What the human changed in the text (validated model rows)

Of 144 ungrouped validated model rows, **115 (80%) were accepted unchanged**. The rest:

| class | rows | example |
|---|---|---|
| extended (human added words) | 14 | `Rue Thu duc` → `Rue de Thu duc No. 11`; `Rue Bourdais` → `Rue Bourdais No. 32` |
| wrong word | 5 | `Rue Thabert N° 4` → `Rue Thabert No. 21` |
| rewrite | 5 | `Boulevard Charner` → `Quai Charner No. 18` |
| truncated (human trimmed) | 3 | `Rue de Singapore` → `Rue Singapore`; `POSTES ET TÉLÉGRAPHES` → `TÉLÉGRAPHES` |
| diacritic/accent | 2 | `MARCHE CENTRAL` → `MARCHÉ CENTRAL`; `CHATEAU D'EAU` → `CHÂTEAU D'EAU` |

Of 32 group members: 22 unchanged, 5 trimmed (`Arroyo Chinois` → `Arroyo`: the model wrote the whole name into
one fragment's box and the human split it), 2 numeral fixes (`N° 7` → `No. 7`), 2 punctuation (`l ' Avalanche` →
`l'Avalanche`). Mean character similarity of raw against effective text: `v1b` 0.987 (93% exact), `post0910` 0.892 (63%
exact). The `v1b` figure is flattered: it is the older run and the reviewer favoured its good rows.

Diacritics are not the problem on this sheet: 2 of 60 validated rows with a mark in the final text lacked it in the raw
text, both in capitals.

The dominant change is **road numbers**. 30 of the 76 validated road and river rows end in `No. NN`; in 19 of the 22
model-read ones the model's raw text lacked the number. The reviewer typed `No.` 21 times and kept `N°` in 6 more
rows, so the final corpus has both spellings.

### 4. Categories are fine; one boundary leaks

Only 3 of 176 model-read validated rows had a category corrected (`other` → `hydrology` ×2, `legend` → `title`). 18 of the 22 manual boxes came in as the review tool's default `other`; the human set the category on 19 of 22 (13 street, 2 hydrology, 2 place, 2 institution), so the `other → street` entries in a naive confusion matrix are the tool's default, not the model.
The eval harness also shows `institution → building` 5–6 times in every run: the same barracks or post office is read
as an institution by one run and a building by another.

### 5. The sparse layout of road and river names

76 validated road and river rows (68 street, 8 hydrology; effective category, with manual boxes and group members
assigned by group or generic word). All 75 with a measurable box carry `label_w/label_h`, because they are the rows a
human drew or edited; the original model boxes are gone, so these are **human-drawn boxes**, and the ones the model
missed or fragmented are the most likely to have been redrawn. Read the spacing as a property of the printed
names, not of the model.

**Letter spacing** (long side ÷ non-space characters ÷ short side): median 1.23 letter heights per character,
p10 0.58, p90 2.37, max 3.83.

| spacing tercile | rows | ok | minor/misread | split (grouped) | missed (manual) |
|---|---|---|---|---|---|
| tight (< 1.01) | 25 | 10 | 5 misread | 5 | 5 |
| mid (1.01–1.59) | 25 | 5 | 7 misread | 9 | 4 |
| wide (≥ 1.59) | 25 | 5 | 10 misread | 7 | 3 |

This looks like a spacing effect and is partly a number-tail effect: the human box encloses the road number, which
is printed some way along the line, so a name with `No. NN` measures wider. Splitting by tail: **wide rows with a
tail: 10 misread, 3 missed, 0 ok (13); wide rows without one: 5 ok, 7 split (12).** The model also cut wide names into
more pieces: mean rejected fragments per validated name box 0.95 (tight), 0.95 (mid), **2.45 (wide)**; 31 of 64
model-read name boxes hold at least one rejected fragment (up to 10).

**Fragments.** Of 21 text groups, 14 are a street plus a separate road-number box (`Rue Vannier` + `N° 5`) and 7
are one name in pieces (`Route Basse de` + `Cholon`, `Arroyo` + `Chinois`, `Rue` + `Mac` + `Rue Mac-Mahon`). The 35
bare-number fragments among the rejected rows are the same road numbers read as their own boxes. Only the 7 name-piece
groups (12 member pairs) bear on a grouping heuristic. Pieces of one name (13 of the 21 groups have one name piece plus a number, 6 have two pieces, 2 have three) sit:

| measure (12 pairs) | median | p90 | max |
|---|---|---|---|
| gap between pieces, letter heights | 14.5 (970 px, 330 m) | 28 | 58 |
| perpendicular offset from the shared line, letter heights | 0.85 | 5.6 | 9.9 |
| difference in `rotation_deg` | 25° | 54° | 58° |
| connecting line against each piece's rotation | 17° | 33° | 44° |


**`rotation_deg` is not a usable gate for grouping**: pieces the human joined disagree by 25° at the median. Position
carries the signal. Tested over all 1953 candidate pairs within 3500 px (positives: the 12 human pairs, in-sample):

| rule | TP | FP | precision | recall |
|---|---|---|---|---|
| geometry only: Δrot ≤ 30°, offset ≤ 0.5 h, gap ≤ 30 h | 4 | 3 | 0.57 | 0.33 |
| **plus one piece looks incomplete**: Δrot ≤ 45°, offset ≤ 1.5 h, gap ≤ 30 h | 6 | 4 | **0.60** | **0.50** |
| same, no rotation gate | 7 | 10 | 0.41 | 0.58 |
| same, Δrot ≤ 5° | 2 | 0 | 1.00 | 0.17 |

"Incomplete" means a bare generic (`Rue`, `Arroyo`), a trailing connective (`Route Basse de`, `R. aux`) or no generic
word (`Mac`, `Chinois`); it removes 69% of the negative pairs (607 of 1941 stay). **Ranking is better than thresholding:**
for each incomplete piece with a human partner, the candidate with the smallest perpendicular offset (gap ≤ 30 h)
is the partner in **10 of 13 cases**, against a mean of 20 candidates. A suggestion, not an auto-merge.

**Repeats.** 70 name instances (ungrouped rows plus one per group), 60 distinct names (`name_key`), 9 seen more than
once: 8 twice, 1 (`Rue Nationale`) three times. Spacing of repeats of the same name: nearest-neighbour median 505 m;
the 8 pairs lying along one line are 168–1219 m apart (median 888 m). The one close pair (39 m, `Boulevard de Canton`)
is two boxes side by side, not along the line, and may be a duplicate validated twice.

**Orientation.** Name rows sit at the diagonal: 57 of 76 have |rotation| between 30° and 60° (45 between 40° and 50°); only 3 are within 15° of horizontal and 5 within 15° of vertical. This is the 1882 street grid, not a property of the model. Validated share of non-dup model rows by
`rotation_deg` bucket: 0–15° 0.67 (n 3), 15–35° 0.45, **35–55° 0.32** (50 validated against 105 rejected non-dup),
55–90° 0.46. Character similarity of the validated rows: 0.80, 0.88, 0.92 for the three bigger buckets. The diagonal band
is where fragments pile up.

**Misses (12 manual street or hydrology boxes).** The model skipped nothing for being small, rotated or widely spaced:
long side median 959 px against 1100 for the ones it found, spacing median 1.12 against 1.26, rotation bucket
35–55° in 8 of 12 against 43 of 64, characters 15 against 14. What they share is the number tail: 8 of 12 manual rows
end in `No. NN` (against 22 of 64 found), and 5 of 12 had rejected model fragments inside them (up to 7). A "miss" here
is mostly "no single box covered the whole line".

### 6. Vocabulary

Not in `LABEL_PREFIXES`: `arroyo` (3 mentions in validated text, always a river; the one river generic the sheet uses that the list lacks),
`r.` (abbreviation of `Rue`, 2), `vge` (`Vge de Tân An`, 15 validated place rows: the single most frequent first
word after `Rue`), and `n°`/`no` which are road numbers, not generics, but arrive as the first token of 10 street
rows and defeat `label_core`. Printed abbreviations in validated text: `No.` 29, `R.` 2, `Imp.` 1.

## Transfer rules for the District 4 sheets

Evidence counts are rows on the 1882 sheet. "French" rules assume the French typography and generics of 1882, 1895,
1923 and 1942; 1959 and 1968 are Vietnamese and English.

1. **Treat road numbers as part of the street line** *(prompt proposal, needs approval)*. n = 30 name rows end in a
   number; the model omitted it in 19 of 22; 35 rejected fragments are bare numbers; 14 of 21 groups are
   name + number; the reviewer typed `No.` 21 times. Ask the street pass to return one box and one string per printed
   line (`Rue Bourdais No. 32`), or to return the number as its own typed item so it can be attached
   deterministically. The number is the colonial **road number** (the road's administrative number), not a house
   number. *Applies to:* French-era sheets that print road numbers — check each sheet first. 1882 prints them; 1898 does not (`261006-1898-ocr-prep.md`); 1923 and 1942 are unchecked. Under the RVN roads carry Vietnamese
   names and the number drops away, so 1959 and 1968 should not get this rule (correction from the user, 2026-10-06).
2. **Normalise the numeral token in post-processing, not in the prompt.** n = 29 `No.` against ≥ 6 `N°` in
   validated text; the reviewer fixed `N°` → `No.` in 3 diffs and left it in 6. Fold `N°`, `N.°`, `No`, `No.` to
   `No.` (French-only). Low risk: it also lets the dedupe and the eval stop disagreeing about spelling.
3. **Confidence gate: hold anything below 0.9 for review; never auto-accept on confidence.** n = 356 (AUC 0.70);
   at 0.9: precision 0.89, recall 0.23 against rejected-non-dup (47 flagged); precision 0.44 against genuine
   misreadings. Recompute the cutoff per run (distributions differ: `v1b` 70 rows at 1.0, `post0910` 146 at 0.95). All
   sheets, but expect it to catch little.
4. **Cross-run dedupe is the biggest single cleanup.** n = 133 of 313 rejected rows are another run's copy of a
   validated label. Same folded name (`name_key`), rotation within 15°, centre distance ≤ 75 m (p99 of 133 twins is
   77 m; p95 40 m) is one print. Leave anything ≥ 150 m apart alone (nearest real along-line repeat: 168 m, n = 8
   pairs; 9 of 60 names repeat at all). Work in metres, not pixels: `px × metres-per-pixel` differs on every sheet
   (1882: 0.3416). Applies wherever more than one run reads the same body text: 1942 has at least two body runs (`2026-09-11T1004`, `2026-09-11T1628`) plus `idx2x`; the 1923, 1959 and 1968 runs are mostly different tasks (legend, index, numerals), so check which overlap before applying it.
5. **Suggest a group, rank by perpendicular offset.** For a piece that looks incomplete (bare generic, trailing
   connective, no generic word), propose the candidate within 30 letter heights along the line with the smallest
   perpendicular offset: partner in 10 of 13, mean 20 candidates. As a pair filter the same idea gets precision 0.60 /
   recall 0.50 in-sample on 12 pairs (offset ≤ 1.5 h, gap ≤ 30 h, Δrot ≤ 45°). **Do not gate on `rotation_deg`
   similarity**: joined pieces differ by 25° at the median. Suggest only; the reviewer confirms. The connective list is
   French; for 1959 and 1968 use Vietnamese generics (`Đường`, `Đại Lộ`) and treat a name with no generic as the
   incomplete piece.
6. **Merge fragments inside a street box before review.** n = 119 rejected rows lie inside a validated box, 98 of them
   labelled street; 31 of 64 model-read name boxes contain at least one, up to 10. A pass that clusters street-category
   boxes that overlap or sit on one line, joins them into one box and string, and shows the human one row instead of
   four would remove most of the rejection work. Applies to every sheet with sparse diagonal street names; 1882 is the
   extreme case.
7. **Tiling: size by ground, not by pixels, and expect long names to straddle tiles.** n = 12 groups with a gap
   > 1 letter height; median gap 330 m, p90 ~ 650 m; the validated name boxes have a median long side of 1100 px
   (≈ 376 m) and p90 ~ 2000 px, with an outlier at 6081 px (`RIVIÈRE DE SAIGON`). The 1882 tile is 2400 px with 300 px
   overlap, so a name longer than the overlap lands in two tiles. But **fragments are not a tile-edge artefact**: the
   rejected fragments touch a tile edge 19% of the time, the validated rows 34%. Tiling is not the first fix; test
   the merge in rule 6 first. *Hint for later:* overlap ≥ the p90 name length in metres on each sheet.
8. **Rotation hint, per sheet.** 75% of the 1882 name rows (57 of 76) lie at 30–60° from horizontal; the model's validated share is
   lowest there (0.32). Rerun `review_patterns.py` on the first reviewed batch of each sheet and read the orientation
   histogram before deciding on a rotated-tile pass; do not assume 1882's grid. Do not use the model's `rotation_deg`
   to group pieces (rule 5).
9. **Scope the legend and margin text out of the body pass.** n = 19 orphans, 15 legend text (`Propriétés domaniales…`,
   `Echelle de 1/4000`, scale numerals) the reviewer rejected. Either filter `category = 'legend'` rows outside the body
   neatline or accept the cost. 1923 already has a separate legend run; check that the body pass does not read it
   again.
10. **Vocabulary additions** (`labels.py` and `dictionary.py`): add `arroyo` (river, n = 3) and the abbreviation `r.`
    (n = 2) to `LABEL_PREFIXES`; consider `vge`/`village` as a place generic (n = 15); strip a trailing road number
    before `label_core` so `Rue Dayot No. 5` and `Rue Dayot` share a key (n = 30 rows with tails). French-only except
    the number strip. `Quai` → `Rue` and `Boulevard` → `Rue` swaps happened 3 times (`Quai Charner No. 18` was
    `Rue Charner No. 18`): a watch item, too few to act on.
11. **Accent restoration is low value here.** n = 2 rows (both capitals). Do not add a pass for 1882; check the rate on
    1923 and 1942 before deciding.

## What this does not show

The effective category for the manual boxes comes from the human-set `category_corrected`; no category was inferred. The
spacing and fragment geometry rest on boxes a human drew, so they describe the printed names and the human's choice of
box, not the model's original output. The grouping heuristic is fitted and scored on the same 12 pairs. Only one
sheet is covered. The pending 11 rows and the 20 group rows were not counted as model readings.
