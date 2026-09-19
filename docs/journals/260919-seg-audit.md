# 260919 — audit of 1882 detection + segmentation, and the work list

**Date:** 2026-09-19 · **Severity:** —  · **Component:** seg / Track C · **Status:** audit, nothing built

Companion to `docs/journals/260918-colour-blocks.md`, which is the working record of how the
colour pass got here. This file asks a different question: **on the 1882 Plan Cadastral, what is
actually wrong today, and what is the shortest list of work that fixes it.**

Every number below was re-run on this machine, not copied from the write-ups.

## The reference run, reproduced

```bash
python3 work/ocr/scripts/colour_blocks.py \
  --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \
  --local-image .tile_cache/ocr/full_c03b7f44a1d8d455c2b476d248651265.jpg \
  --render 6051 --cream --drop-furniture --drop-water --drop-slivers --swatch-labels \
  --out <dir>
```

80 s of CPU, 888 polygons — admin 28 · blue 82 · cream 682 · green 65 · salmon 31. Scored against
the 46 volunteer traces:

| kind | n_gt | n | @.5 | @.3 | mean | med | cover |
|---|---:|---:|---:|---:|---:|---:|---:|
| land_plot | 24 | 888 | 6 | 7 | 0.331 | 0.218 | 0.98 |
| building | 17 | 888 | 1 | 3 | 0.122 | 0.050 | 1.00 |
| road | 3 | 888 | 0 | 0 | 0.137 | 0.133 | 0.14 |
| waterway | 2 | 888 | 1 | 2 | 0.582 | 0.582 | 0.99 |

Label coverage: **areal recall 0.78** (153/195), street leak 0.37 (80/216). Every figure matches
`EVAL-BASELINE.md` to the digit, so the write-ups are trustworthy and this audit is about what
they *do not* measure.

**The reference image is on disk and is not pinned.** `.tile_cache/ocr/full_c03b7f…jpg` is the
12102 x 8982 scan every quoted number was measured on. It is a cache under an md5 name; clear the
cache and no number in either file can be reproduced, because a re-fetch moves `land_plot` by 0.13
(recorded, EVAL-BASELINE "Repeatability holds only when the input image is pinned").

## What is wrong, ranked

### 1. There is no precision number anywhere, and four defect classes were found only by eye

`seg_eval.score` is `max(iou(g, q) for q in preds)` per ground-truth polygon. It never looks at a
prediction that matched nothing. 888 polygons against 46 traces therefore score exactly as well as
46 good ones would.

Everything the last two days fixed — the cream hulls closing over their own blocks, the river
ribbons, the hatch slivers, the Jardin Botanique flooding — moved **no number in this repo**. Each
was caught by rendering the run and looking at it. The journal states this four separate times and
calls it the real blocker; it is still true and it is the first thing to fix, because without it
every further change is a guess bounded by a picture.

The fix is not a code problem so much as a data one: precision needs a window where *every* parcel
is traced, not 46 of roughly a thousand. The code around it is small.

### 2. The ground truth is 46 traces, the LoRA trained on them, and 72 of the table's rows are lettering

Still live on production, verified this session:

```
72  ('sam-auto', 'building', 'needs_review', 'seg-20260916T1632-0e02b9d9')
24  ('volunteer', 'land_plot', 'approved')
17  ('volunteer', 'building',  'approved')
 3  ('volunteer', 'road',      'approved')
 2  ('volunteer', 'waterway',  'approved')
```

`seg_eval.load_gt` now filters `source=eq.volunteer`, so the scores are clean. The rows are not:
they sit in the human review queue as `needs_review`, they are OCR label boxes rather than
buildings (median IoU 0.83 to their own prompt box), and any consumer that forgets the filter
reads them as truth. They should be deleted, not left for a reviewer to reject one at a time.

Separately: every SAM2 figure in `EVAL-BASELINE.md` is scored against the traces the LoRA was
fine-tuned on. C5's held-out set is still the standing blocker and is a tracing job.

### 3. The colour prior cannot reach the segmenter by any supported route

`colour_blocks.py` is called by nothing. Verified: the only references in the tree are
`review_figs.py`, `legend_probe.py`, and two lines of `ponytail-debt.md`.

- `work/worker/vma_worker.py:seg_argv` builds the MapSAM2 command line and **has no `--prior`**.
- `src/lib/features/contribute/trace/segCommand.ts` — the Segment panel — has no prior either.

Both instead pass `--mode prompted --ocr-run-id <run>`, which seeds SAM2 from OCR label boxes.
That is the exact recipe that produced the 72 rows in item 2, and C4 predicted it would.
`inference_tiles_as_video.py` already accepts `--prior` and `colour_blocks` already writes the
geojson contract `to_sam2_seeds.load_seeds_from_prior` reads (verified handoff: 253 blocks -> 246
seeds). Nothing joins the two ends.

Two defaults on the same path are wrong on the evidence in this repo:

- **`--text-mask` defaults ON** in both the worker and the panel. It is the *worst* prompting
  variant measured — 0.062 against 0.089 for the same run without it — because filling a label box
  with flat paper tone creates a rectangular object exactly where the prompt is.
- **`--watershed` defaults ON** and appears in `EVAL-BASELINE.md` **zero** times. It has never been
  measured in either direction.

### 4. The measured-best recipe is not the default

`--cream`, `--drop-furniture`, `--drop-water`, `--drop-slivers` and `--swatch-labels` are all off.
A bare `colour_blocks.py --map-id …` returns the 253-block pass at `land_plot` 0.247, not the 888
at 0.331. Five flags stand between the script and its own best result, and `--recut` already
demonstrates the opposite convention (`--no-recut` restores the old run) in the same file.

### 5. The pass's inputs are not pinned to a run, so its output is not a function of the sheet

`load_labels` and `fetch_ocr_extractions(map_id)` are called with **no run filter**. On the 1882
sheet that pools three OCR runs:

| run | labels | areal recall | street leak |
|---|---:|---:|---:|
| pooled, as shipped | 499 | 0.78 | 0.37 |
| `post0910` | 287 | 0.81 | 0.32 |
| `v1b` | 177 | 0.77 | 0.48 |
| `2026-09-04T0527` | 35 | 0.70 | 0.44 |

Three consequences, in rising order of seriousness:

- the eval denominator counts one object up to three times (`195` areal labels, not 195 objects),
  and `leak` swings 0.32–0.48 between runs while the docs say to compare it between runs;
- `--explain` reports a label twice at two different positions, which is exactly what made the old
  named check irreproducible — `MARCHE CENTRAL` reads **0% covered** at (1874, 7553) and **100%
  covered** at (3938, 5452), and both rows are live;
- `water_points` seeds the water region from 16 pooled `hydrology` labels (12 + 4 from two runs),
  `furniture_mask` unions legend and title boxes from all three, and `--legend-swatches auto` picks
  *the largest* legend box across all three. **Re-OCR the sheet and the colour pass returns
  different geometry, with nothing in the output recording why.** This is the same shape as the
  `load_gt` contamination: a table a pipeline writes into is not a fixed input.

`load_labels` also has no PostgREST limit handling, so a sheet with more than 1000 extractions
silently truncates at 1000.

### 6. The within-block split is the ceiling, and the cheapest test of it has never been run

`building` sits at 0.122 (colour prior) / 0.160 (SAM2 on the modern prior), cover 1.00 — the ink is
found, the subdivision is not. P3 declared colour exhausted on a null that was **retracted the same
day**: it had been measured against the 89 contaminated rows. Re-measured on the 17 real traces,
`r − g` overlap is 0.23, and with ink excluded from both sides 0.18 — next door to the 0.17 that
made green separable. There are two reds.

What that does *not* establish is a threshold that beats 0.160, and **that run has never been
made.** It is a CPU threshold on one class, and it is the cheapest open lead in the file.

### 7. Enclosed water inside a land polygon — the last known-wrong thing in the water pass

The Jardin Botanique's lake (coherence 0.757 — it reads as water) and the Arsenal's dry docks,
basins and slipways are each inside a compact block polygon, so `land_mask` subtracts them and no
`hydrology` label can seed them back. Named in the journal, measured, not built. It is also what
would remove the `--recut` trade-off in item 8.

### 8. `--recut` buys the Arsenal and costs the creeks

Default since `d1da01f1`. It is the only thing that bounds the water region at the Arsenal quay,
and it costs `land_plot` 0.350 -> 0.331, 25 s -> 80 s, and creek coverage (Rach Cầu Chông 12.6% ->
7.8%, Hội An inlet 6.5% -> 1.5%). Both defects are real and the flag cannot fix both.

### 9. Streets: 80 of 216 labels hit, and the named street network was never built

P2's stated by-product — a street-name centroid inside a cream component both names that component
and proves it is a street — was overtaken when the diagnosis turned out to be the green class, and
never returned to. `to_sam2_seeds.py` still drops `street_name` extractions deliberately and
`join_labels.py` (smallest-containing-polygon) cannot place them, because nothing contains a street
name. Those extractions currently go nowhere at all. `road` cover is 0.14 under `--recut`.

### 10. Small, named, and cheap

- `PRISONS` reads 22–24% covered. `--explain` says its largest in-band component is 3,385 m² and
  squarely in band, so it is dropped *after* the area test by the ring, the furniture box, the
  water test or the sliver filter. Which one is still unnamed.
- `POSTE DE POLICE` 17–21%, `MESSAGERIES MARITIMES` 45%, `JARDIN BOTANIQUE` 45%.
- `DOCK FLOTTANT` 0% is probably correct — a floating dock is on the water.
- `HATCH_COHERENCE = 0.30` is a hard-coded constant that scales with `--render`, in a file where
  every other knob is voted or swept from the sheet.
- `--legend-swatches auto` (uncommitted) is inert at every render the pass uses; it needs a border
  finder that allows shared edges.

## The work list

Ordered so each item unblocks the next. Owner is who should do it, not who thought of it.

| # | item | owner | unblocks |
|---|---|---|---|
| W1 | delete the 72 `sam-auto` rows | Claude + Tue (production write) | 2, and the review queue |
| W2 | `seg_eval --window`: the first precision/recall pair | Codex, then Tue traces one window | everything |
| W3 | pin the reference image and the OCR run | Codex | reproducibility of 2–9 |
| W4 | promote the measured-best flags to defaults | Codex | W5, W7 |
| W5 | wire `--prior` into the worker + panel; fix `--text-mask` | Codex | W7 |
| W6 | the two-reds within-block split, measured | Codex (tight spec) | `building` |
| W7 | one Colab run of SAM2 on the colour prior | Tue (GPU) | C6 P4 |
| W8 | enclosed water punches a hole in the land mask | Codex | the `--recut` trade |
| W9 | the named street network from cream + `street_name` | Codex | `road`, C6 by-product |

### The preamble every brief carries

> Before writing code: **sanity-check this plan and say whether it is the best way to do it.**
> Read the file first. If the spec is wrong, if a simpler route exists, if the exit criterion
> cannot be met as written, or if the change would move a number the brief claims it will not —
> say so and propose the alternative *before* implementing. A brief that turns out to be wrong is
> the expected outcome some of the time; implementing it anyway is not.
>
> Repo rules that bind every change here: `AGENTS.md` is `CLAUDE.md`. Python work under `work/`
> follows `work/CLAUDE.md`. Any `.svelte` edit is **legacy mode, never runes** (`$:`, `export let`,
> `createEventDispatcher`) and layering is `core → data → map → features → routes`. Deliberate
> shortcuts get a `ponytail:` comment naming the ceiling and the upgrade path. Non-trivial logic
> leaves one runnable check behind — `colour_blocks.py --self-check` is the convention in this
> tree, and it must stay green and network-free.
>
> The reference command, against which "no number moves" is checked:
> ```
> python3 work/ocr/scripts/colour_blocks.py --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \
>   --local-image .tile_cache/ocr/full_c03b7f44a1d8d455c2b476d248651265.jpg \
>   --render 6051 --cream --drop-furniture --drop-water --drop-slivers --swatch-labels --out <dir>
> python3 work/ocr/scripts/seg_eval.py --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b <dir>/blocks.run.json
> ```
> Baseline: 888 polygons, land_plot 0.331 / 0.218, building 0.122 / 0.050, waterway 0.582,
> road cover 0.14, areal recall 0.78.

### W2 — `seg_eval --window`, the first precision number

**Why:** item 1. Every improvement of the last two days was invisible to the metric and was caught
by eye. `--drop-water` removed 55 false positives and moved nothing.

**Build:** `seg_eval.py --window x,y,w,h`. Inside that window only, and against the volunteer
traces whose centroid falls inside it, report **precision** (a prediction whose best IoU to any
trace is below a threshold is a false positive), **recall**, and the false positives listed by
area, largest first, with their `feature_type`. Keep the existing per-trace table; this is a second
report, not a replacement. Default IoU threshold 0.3, `--iou` to override.

**Exit:** on the reference run, a precision figure and a ranked FP list. The number is meaningless
until Tue traces the window exhaustively; the code lands first so the tracing has somewhere to go.

**Watch for:** a prediction straddling the window edge, and a trace that is only half inside. State
the rule chosen and why. Do not score a partial polygon as a false positive for being clipped.

### W3 — pin the inputs

**Why:** item 5. The pass's output is currently a function of whatever OCR rows are in the table.

**Build:** (a) `colour_blocks.py --ocr-run-id`, threaded through `furniture_rows`, `water_points`
and `labels_matching`, recorded in `blocks.run.json` alongside the flags. When it is not given,
print the runs the rows came from rather than pooling silently. (b) the same option on
`seg_eval.py --labels`. (c) `load_labels` must page PostgREST rather than truncate at 1000.
(d) a documented, stable path for the reference scan — `work/ocr/outputs/<map>/reference.jpg` or a
symlink — so clearing `.tile_cache` does not destroy every quoted number.

**Exit:** the reference run with `--ocr-run-id post0910` prints its run id in `blocks.run.json`,
and the pooled default is byte-identical to today's output.

### W4 — the defaults

**Why:** item 4.

**Build:** `--cream`, `--drop-furniture`, `--drop-water`, `--drop-slivers`, `--swatch-labels`
become defaults with `--no-…` escapes, matching the `--recut` / `--no-recut` precedent already in
the file. Update the module docstring's usage block and `EVAL-BASELINE.md`'s recipe line.

**Exit:** `colour_blocks.py --map-id … --local-image … --render 6051 --out <dir>` produces a
`blocks.geojson` **byte-identical** to the reference command's, and every `--no-…` reproduces the
run it names.

**Watch for:** `--drop-furniture` and `--drop-water` need `--map-id` for their OCR rows. Today they
warn and skip. As defaults they must still degrade cleanly on a sheet with no labels, and say so.

### W5 — wire the prior into the seg path

**Why:** item 3. This is what turns the colour work into segmentation instead of a side project.

**Build:** (a) `work/worker/vma_worker.py:seg_argv` gains `--prior` from `payload.prior`.
(b) `src/lib/features/contribute/trace/segCommand.ts` gains a prior path in `SegConfig` and emits
`--prior` when set; the two must stay in step, as that file's docstring already requires. (c) flip
`text_mask` to default **false** in both, with the measured reason in the comment (0.062 against
0.089); leave `--text-mask` available. (d) leave `watershed` alone but add a one-line comment that
it is unmeasured, so the next person does not read the default as evidence.

**Exit:** `npm run check` green, the existing `segCommand` tests updated, and a printed command line
that carries `--prior` and no `--text-mask`.

**Sanity-check this one hardest.** `--prior` in `inference_tiles_as_video.py` documents itself as
"modern_prior.py blocks.geojson"; confirm `colour_blocks`' output actually satisfies
`to_sam2_seeds.load_seeds_from_prior` (the journal says 253 -> 246 seeds, verify it) and say so
before changing any UI.

### W6 — the two reds, measured

**Why:** item 6, and it is the cheapest thing on this list that could move `building`.

**Build:** a probe — a flag on `colour_blocks.py`, or a small script, whichever is less code — that
for each `salmon` polygon splits its interior on `r − g` at the trough voted from that polygon's
own pixels, emits the redder components above the area floor as candidate buildings, and scores
them with `seg_eval` against the **17 volunteer `building` traces**. Exclude ink from both sides:
a building trace carries 0.257 ink against open plot's 0.091, and the outlines are the known
confound that produced the retracted null.

**Exit:** one number, `building` mean IoU, against 0.122 (colour prior) and 0.160 (SAM2 on the
modern prior). **A null is a result** and gets written up in `EVAL-BASELINE.md` the same way the
four pattern-axis nulls were. Do not tune past one honest measurement.

**Do not re-attempt, all recorded as nulls with numbers:** isotropic morphology to cut parcel
dividers (a divider is 1 render px, the hatch period is 4); ink density as a class axis; a line
opening for orientation; per-cell coherence, washless paper, or the c128/c16 ratio on the Arsenal
edge.

### W8 — enclosed water

**Why:** items 7 and 8.

**Build:** let a strongly-ruled region punch a hole in the land mask when the polygon containing it
is much larger than it — a dock inside a yard, a lake inside a park. The measure exists:
`ruling_mask`, 16 px cells, coherence ≥ 0.30, the same gate that already separates the creek from
the Jardin Botanique's stipple.

**Exit:** the Jardin Botanique's lake and the Arsenal's basins come back as water, and **none** of
`land_plot` 0.331, `building` 0.122, `waterway` 0.582 or the five trap windows (Jardin Botanique,
Hôpital Maritime, Magasins des Travaux Publics, Champ de Manœuvres, city core, all at 0.0% water)
moves. Then re-measure `--no-recut` — if the enclosed-water fix bounds the region at the Arsenal
without the re-cut, the 0.019 `land_plot` cost and the 55 s come back for free, and that is the
real prize here.

### W9 — the named street network

**Why:** item 9, and the archive holds a named 1882 street network in no form today.

**Build:** a cream component holding a `street_name` centroid is a street and takes that name;
unlabelled cream stays `non affectées`. The extractions are already fetched and already discarded.

**Exit:** a count of named streets, and the fraction of cream area a street name claims. Watch
`road` cover (0.14 under `--recut`, 0.52 without) and `land_plot`, neither of which should fall.

## Not on this list, deliberately

- **Cross-sheet building matching for auto-georeferencing** (Hu moments + RANSAC, the 2026-03 blog
  post). Needs building-granularity polygons on two sheets; nothing clears IoU 0.5 on a single
  plot on one.
- **A second polychrome sheet.** It is the trigger for the `--legend-swatches auto` border finder
  and for the scale-dependent constants, and it is the honest answer to "does this generalise" —
  but every item above is measurable on 1882 today, and none of them needs it.
- **Anything that claims "no GPU" in public.** Four conditions stand between the run and that
  sentence, and item 1 is the load-bearing one.

---

# Results, 2026-09-19

Worked in the order the list gives. Numbers here were measured on this machine
against the pinned scan; the baseline they are compared to is the reference run
at the head of this file (888 polygons, `land_plot` 0.331, `building` 0.122).

## W1 — done. The table is a ground truth again

72 rows deleted (`footprint_submissions`, `run_id = seg-20260916T1632-0e02b9d9`).
46 volunteer traces remain: land_plot 24 · building 17 · road 3 · waterway 2.

60 `ocr_extractions` rows were joined to those footprints and are now `null` by
the mig 050 FK's `on delete set null` — correctly, since the "footprint" each was
joined to was its own label box. Both sets are backed up on the Desktop pack
(`before/deleted-72-sam-auto-rows.json`, `before/nulled-60-ocr-joins.json`).

## W4 — done. The script no longer withholds its own best run

`--cream`, `--drop-furniture`, `--drop-water`, `--drop-slivers` and
`--swatch-labels` now default **on**, each with a `--no-…` escape carrying what
turning it off costs, following `--recut`'s precedent in the same file.

Verified: `colour_blocks.py --map-id … --local-image … --render 6051 --out <dir>`
with **no flags** produces `blocks.geojson` with md5 `7092494d851ea22f1a55a7912e42e484`
— byte-identical to the five-flag reference command. `--self-check` green.

## W3 — done. The pass says which OCR rows it read

`--ocr-run-id` pins the rows that seed the water, the furniture mask, the legend
panel and `--explain`; `blocks.run.json` records it. Pooling stays the default so
nothing existing moves, but it is printed now instead of silent:

```
  499 OCR rows from 3 pooled run(s): post0910 287, v1b 177, 2026-09-04T0527 35
```

Geometry byte-compared against the baseline: **identical**, 888 features, the only
new key in the output being `ocr_run_id`. The three separate `fetch_ocr_extractions`
round-trips are now one cached read.

**And a real bug found on the way.** `supabase_client.fetch_ocr_extractions` was
unpaged, so it returned at most PostgREST's 1,000 rows and reported the truncation
as nothing at all. Measured against production: of the 22 sheets with extractions,
**4 are over the cap** — the 1942 Plan de Saigon-Cho Lon at 4,287 rows, i.e. 77%
of that sheet was invisible to every caller, the label join included. Now paged.
1882 is unaffected at 499, which is why nothing here ever showed it.

## W8 — the enclosed-water rule is a NULL, and it closes the approach

Built as specified: a ruled blob lying **wholly** inside one land polygon and
covering no more than a quarter of it is a dock or a lake, punched out of the
land barrier and admitted to the water region without a `hydrology` seed.

`land_plot` 0.331 / 0.218, `building` 0.122 / 0.050, `road` 0.137 cover 0.14,
`waterway` 0.582 cover 0.99 — **every score identical to the digit**, 888 → 885
polygons. By the standard this file's earlier water work was accepted on, that
reads like another free precision win.

**It is not. The pictures' quantitative stand-in says the opposite**, which is
the fifth time on this track that the metric could not see the thing that
matters. Water share per window, rule off against rule on:

| window | off | on | |
|---|---:|---:|---|
| Jardin Botanique (the lake) | 9.5% | 9.7% | the target — **not recovered** |
| Arsenal yard (the basins) | 28.9% | 28.9% | the target — **not recovered at all** |
| open river (control) | 92.2% | 92.2% | unchanged, correctly |
| **city core (TRAP)** | **0.0%** | **1.3%** | must be zero |
| **Champ de Manœuvres (TRAP)** | **0.0%** | **0.6%** | must be zero |

It misses both things it was built for and puts water in two windows that have
none. Reverted, and `--self-check` is green on the reverted file.

### Why, measured — and this is the part worth keeping

`solid`, the ruled-blue mask the water region is built from, **before** any land
subtraction:

| window | `solid` | `solid & land` | admitted |
|---|---:|---:|---:|
| Jardin Botanique (lake) | 21.9% | 8.3% | 0.2% |
| Arsenal yard (basins) | 75.6% | 43.1% | 0.0% |
| open river | 91.5% | 0.0% | 0.0% |
| **city core** | **17.5%** | 17.4% | 1.3% |
| **Champ de Manœuvres** | **38.2%** | 38.1% | 0.6% |

**`solid` is not a water mask.** It is *dark, bluish and ruled*, and an ordinary
city block satisfies that over 17% of its area, the Champ de Manœuvres over 38%.
What makes the pass work today is not that `solid` finds water — it is the two
guards that come after it: `land_mask` subtracts nearly all of it, and the
`hydrology` seeding keeps only what a label touches. The enclosed rule bypasses
**both** guards by construction, for exactly the blobs too small to be a river.

And the two bounds that were supposed to make that safe are what lose the
targets. The basins and the lake are large, and they straddle their parcels'
edges, so "wholly inside" and "at most a quarter of its parcel" exclude them
while admitting the small gaps between hatch lines everywhere else. Loosening
either bound floods the city — the same shape as every loosening of the wash
test recorded in the 2026-09-18 journal.

**So: containment and scale cannot separate enclosed water from a hatched
block, because the mask they are applied to does not distinguish them.** That
is the same conclusion §(iii) reached from the other side — the discriminator
is the *drawn outline* around the basin, not the fill, which is ink geometry and
therefore SAM2's job. Two independent routes now land on it.

**Do not re-attempt containment-and-scale on `solid` as stated.** A real
enclosed-water rule needs a mask that is water rather than ruled ink, and
nothing measured on this sheet produces one.

## W6 — the within-parcel split. The biggest single move this sheet has made

`building` **0.122 → 0.355 mean, 0.050 → 0.314 median, 1 → 5 traces over IoU
0.5, 3 → 9 over 0.3.** Whole sheet, CPU, +3 s on an 80 s run, no GPU and no
checkpoint. `colour_blocks.py --no-split-buildings` restores the old run.

| | n | @.5 | @.3 | mean | med | cover |
|---|---:|---:|---:|---:|---:|---:|
| **building (n=17)** | | | | | | |
| blocks + parcels (the baseline) | 888 | 1 | 3 | 0.122 | 0.050 | 1.00 |
| **+ within-parcel split** | 1443 | **5** | **9** | **0.355** | **0.314** | 1.00 |
| SAM2 LoRA on the modern prior | 950 | — | — | 0.160 | — | 0.98 |
| **land_plot (n=24)** | | | | | | |
| baseline | 888 | 6 | 7 | 0.331 | 0.218 | 0.98 |
| + split | 1443 | 6 | 8 | 0.343 | 0.232 | 0.98 |
| **areal (n=41)** | 888 → 1443 | 7 → **11** | 10 → **17** | 0.245 → 0.348 | | |

**Read the median, not the mean.** The run is 1443 predictions against 888 and
`score()` takes the best match per trace, so a mean can rise on count alone —
this file has said so three times and it applies here. The median cannot be
bought that way, and it went **0.050 → 0.314**; nor can @0.5, which went 1 → 5.
`land_plot` is the control: 1.6× the predictions moves it 0.331 → 0.343, which
is what count alone buys, and is the right size for "the split did not touch
the parcels".

### Two things the plan had wrong, both measured before any code was written

**P3 was scoped to salmon, and no building on this sheet is in a salmon
polygon.** The premise was that a building stands on a *propriétés
particulières* plot, so splitting salmon internally would find it. Of the 17
volunteer `building` traces, **15 fall inside a cream polygon, 2 inside a
green one, and 0 inside a salmon one.** A salmon-scoped rule could not have
reached a single trace. The split runs over every class.

**And the threshold is local, not global.** P3's retracted null looked for two
reds in the *sheet's* histogram; what exists is a delta between a building and
the parcel it stands in — median **+0.035**, 10 of 17 positive. So the baseline
is each polygon's own ink-excluded wash median, re-derived per polygon, and the
sheet-wide trough is not used at all. That is why five months of sheet-level
threshold work never found this and why one afternoon of per-parcel work did.

### The seven traces it does not find, and why that is two different reasons

| | traces | ink inside | what it is |
|---|---:|---:|---|
| redder than its parcel | 10 | 0.05–0.35 | the wash convention — found |
| **darker than its parcel** | 4 | **0.21–0.44** | a dense black fill; its own ink drags its wash median *below* the plot's |
| neither | 3 | 0.05–0.08 | differs from its surroundings in neither colour nor ink |

The four dark ones are the sheet's **second building convention** and an ink
axis was the obvious fix. It was tried and is a null: a candidate mask of
`r − g` OR local ink density explodes the component count across the whole
sheet, because dense ink is also the lettering, the hatching and every block
outline. Not built, and the ordering is recorded so it is not re-attempted as
stated.

### What this does NOT establish

- **There is still no precision figure.** 1443 polygons against 46 traces, and
  `seg_eval` cannot see a prediction that matched nothing. `seg_eval --window`
  now exists (W2) and no window has been exhaustively traced, so the tool is
  ready and the measurement is not. **This is the one thing that would change
  how much the numbers above are worth**, and it is a tracing job.
- **The threshold is one measured point, not a swept plateau.** 0.035 is the
  measured median delta over the 17 traces, and a sweep at 0.020 / 0.050 /
  0.070 was started and abandoned — each point is a full re-run and a *higher*
  threshold is slower, not faster, because it fragments the redder core into
  more components. Outstanding.
- It is still one sheet, and the traces are 17.

## W9 — the street network: NOT BUILT, and the reason is a design fault in the item

The plan reads "a cream component holding a `street_name` centroid is a street
and takes that name". Working through it before writing any code, it does not
survive contact with how this pass represents geometry.

**The street network is not a polygon this pass can emit.** It is the *oversized*
cream component — one connected surface by construction, 6.19 km², which the
area cap drops and whose being over the cap is the guard rather than a failure
(`blocks_from_colour`, the `too large` branch). To emit it, `component_polygon`
would take a concave hull of a connected street grid, and the hull of a network
is a disc: the result is one polygon lying over the whole city. That is the
exact defect the 2026-09-18 journal already recorded and fixed once, when cream
hulls closed over the blocks they surrounded.

The correct cheap form is the component's mask minus the kept block polygons,
which `subtract_blocks` could do with no new dependency. What stopped me is the
second half: **nothing on this sheet can tell me whether it worked.** `road` is
3 traced centrelines, and this file already measures that a block-shaped
prediction scores 0.042 against a centreline by construction, so `road` cover
cannot referee a street-surface polygon. Naming individual streets needs the
ribbon split at junctions, which is a skeleton and a real piece of work.

Building an unmeasurable layer at the end of a session is precisely what W8 has
just demonstrated the cost of — it scored flat, read as free, and was wrong in
two trap windows. So this is recorded rather than shipped.

**When to pick it up:** with `seg_eval --window`, after a window has been
traced. A traced window gives the street surface a denominator, and the same
window answers the precision question the whole pass is currently missing.

## Summary of the session

| item | outcome |
|---|---|
| W1 purge the contaminated traces | **done** — 72 rows deleted, 46 remain, backed up |
| W2 `seg_eval --window` precision | **done** (Codex) — verified against known numbers |
| W3 pin image + OCR run | **done** — plus a real truncation bug in the shared client |
| W4 measured-best flags as defaults | **done** — byte-identical output verified |
| W5 wire `--prior` into the seg path | **done** (Codex) — verified, `npm run check` clean |
| W6 the within-parcel split | **done** — `building` 0.122 → **0.355**, median 0.050 → **0.314** |
| W7 one Colab run on the colour prior | **not started** — needs a GPU, and is yours |
| W8 enclosed water | **null, reverted**, with the cause measured |
| W9 the street network | **not built**, design fault recorded above |
| W10 Desktop comparison pack | **done** — `~/Desktop/vma-1882-seg-260919/` |

**Two things from the audit's own ranking are still true and unchanged by any
of this.** There is no precision number, because no window has been traced; and
every SAM2 row in `EVAL-BASELINE.md` is still a train-set score, because the
held-out trace set does not exist. Item 1 of *what it would take to claim "no
GPU" in public* is still the blocker it was this morning, and it is a tracing
job rather than a code one.

## Three review examples: 1882 parcel outlines

The 19 September review screenshots add three concrete boundary failures to
the precision work above:

1. At **Caserne et Ateliers de l'Artillerie**, a blue proposal makes a long
   straight edge through a genuine street corner.
2. At **Arsenal de la Marine / Dock Flottant**, the blue proposal's quay edge
   continues into the water and does not follow the printed shore.
3. At **Nouveau Palais de Justice**, the administrative wash proposals cover
   pieces of the plots instead of their printed cadastral perimeters. The
   missing pieces are part of the plot, not separate parcels.

These are different failure points. The first two expose overreach by the
`component_polygon` concave hull. The third starts earlier: the colour mask
itself only claims part of a plot. Changing the polygonizer alone cannot
recover pixels the mask omitted.

I tested replacing the hull with a pixel-edge trace on the pinned 1882 scan.
Under identical offline settings (`--local-image`, `--render 6051`,
`--mpp 0.34`, no database labels), the current hull returns 1,135 proposals;
the pure trace returns 648, because narrow ink channels make otherwise useful
parcels too stringy for the sliver filter. A hybrid that keeps the hull for
stringy components returns 1,109, but visual crops around the Arsenal and
Palais de Justice still show jagged boundaries and the incomplete courthouse
plots. These counts are **not** the published 1,443-proposal run: the offline
pass has no database water or furniture labels and chooses a different cream
threshold. They compare geometry methods against the same input, not production
quality. The trace and hybrid were not kept.

The next check needs complete hand-traced windows around both the Arsenal quay
and the justice plots, including every parcel and the street/water surfaces.
Score coverage *and* false overlap there before changing the polygonizer or
approving these proposals. The present masks should be treated as review
proposals, not corrected cadastral outlines.
