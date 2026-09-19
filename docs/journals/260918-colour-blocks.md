# 260918 — the sheet knows where its own blocks are

**Date:** 2026-09-18 · **Severity:** medium · **Component:** seg / Track C · **Status:** P1 + P2 built and scored, P3 a recorded null, P4 open

## The goal

Get the coarse-seg level — city blocks and parcels — **from the sheet's own ink
instead of from 2023 geodata**, and get two things that currently do not exist
anywhere in the archive as by-products: a named 1882 street network, and a
within-block split that is not a segmentation problem.

This is not a new idea. Track C's flow line has said `colour pre-pass → OCR →
coarse seg (blocks, rivers) → fine seg (buildings) → level-aware join` since the
2026-08-08 design. What drifted is where the colour pre-pass landed: C2
implemented it as **tile triage** (`compute_tile_colours` demotes a washed tile
one resolution step) and the block prior went to `modern_prior.py` instead. The
colour never became a geometry source. This note is about making it one.

## Why the current prior is the weak link

`modern_prior.py` builds blocks from a 2.1M-polygon 2023 HCMC building layer
(buffer-dissolved) or from TASCO road-surface polygons (complemented), then
warps them into the sheet's pixel grid through its georeference annotation. Both
paths inherit two errors the ink does not have:

- **the georeference**, whose floor on this sheet is 11.3 m RMSE, worst point
  23.0 m (`docs/worked-example-1882.md`);
- **141 years of epoch drift.** The file says it itself: inside the 1882 extent
  the modern layer holds 51,382 buildings on 38% of the ground while the sheet
  draws a colonial town in paddy, so "the modern buildings are NOT a positive
  seed source as they stand."

EVAL-BASELINE describes SAM2's job against that prior as *snapping drifted
modern geometry onto 1882 ink*. A colour block starts on the ink. It also works
where the modern prior is worst — **District 4**, which is where the series
review is blocked and where the archive holds zero footprints.

## What was measured, 2026-09-18

One tile, `4142_4032_2048_2048_tile.png` from the cached 1882 Plan Cadastral run
(`work/ocr/outputs/0e02b9d9-…/`, gitignored) — a 2048 px source region rendered
to 1024, so **1 tile px ≈ 0.685 m** at the sheet's 0.3426 m/px. numpy + PIL +
scipy, no cv2, no GPU. This is a **census, not a score**: it says the colour
separates, not that the polygons are right.

```python
a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255.
r, g = a[..., 0], a[..., 1]
np.histogram(r - g, bins=24, range=(-0.10, 0.26))   # the whole test
```

`r − g` comes back **bimodal**: a cream mode at ≈ +0.045, a salmon mode at
≈ +0.14, and a trough at **+0.065 carrying 3.4%**. The threshold is read off the
sheet rather than chosen, which is the part that matters — the old colour
pipeline (`scripts/vectorize.py`, deleted `27f8e79f`) calibrated its palette by
hand and never published a separation figure.

Classifying on that trough, with `V < 0.55` taken out first as ink:

| class | share of tile | components ≥ 2000 px | median (big) | max |
|---|---:|---:|---:|---:|
| ink (line, hatch, text) | 10.2% | — | — | — |
| salmon (*particulières*) | 40.7% | 12 | 5,756 px ≈ 2,700 m² | 250,247 px |
| cream (street + *non affectées*) | 48.2% | 2 | — | 544,072 px |

Two readings, one encouraging and one not:

- **Salmon components are parcel-sized.** Median ≈ 2,700 m² is a plausible
  colonial block. This is the result the plan rests on.
- **Cream is one connected mass.** Two components cover 52% of the tile, because
  the streets and the unassigned *non affectées* parcels are the same tone.

## The three pieces, and which one is load-bearing

**1. Colour → blocks.** Supported by the measurement above. The number to beat
is on record in EVAL-BASELINE: `--blocks-from-roads` scores land_plot IoU
**0.262** at cover **0.87** (1,184 blocks), against the 8 m buffer's 0.197 /
0.60 (666 blocks).

**2. Negative space → roads.** *Partly.* The cream mass is "not built", not
"road". A large cream parcel and a boulevard are the same ink, and connectivity
alone will not separate them because the parcels touch the streets.

**3. Join with OCR — this is the discriminator, not a garnish.** It resolves
piece 2 and it un-strands work that is currently thrown away.
`to_sam2_seeds.py` drops `street_name` extractions deliberately (a street name
labels a line, so prompting its box segments the lettering's background) and
hands them to `join_labels.py`, which is **smallest-containing-polygon** — and
nothing contains a street name, because it sits in the gap between blocks. So
those extractions presently go nowhere at all. Given the cream ribbon they have
a home: a street-name centroid inside a cream component both **names** that
component and **proves it is a street** rather than a parcel.

The by-product is a named 1882 street network. The archive has one in no form
today.

## The unverified part worth testing early

There appear to be **two reds** on this sheet: the pale salmon wash is the
*plot*, and the darker saturated red-brown fills inside it are *individual
buildings*. If that holds, the within-block split is a second threshold rather
than a segmenter.

That split is precisely what the seg side is capped on — `building` IoU 0.160
against `land_plot` 0.249, recorded as "the ink is found, the subdivision is
not", with a within-block split named as the next piece of work.

**Not established — and later disproved.** The value-split probe run that
morning was confounded: the dark tail of the red family mixes building fill
with the black outlines and the lettering, so `V < T` selected all three. The
clean test, with ink excluded and scored against the 89 building traces, is
P3 below: **there are no two reds.** V is unimodal in every class, and no
colour axis separates a building from its plot (best 0.64 overlap against the
green pair's 0.17). Buildings are outlines over the same wash.

## Failure modes already visible

- **Salmon merges across thin streets.** Largest component 250,247 px ≈ 11.7 ha
  — several blocks fused. The cut should come from the 10.2% ink class, which is
  the printed block outline, used as a watershed boundary.
- **Polychrome sheets only.** 1882 and 1898 qualify. The D4 series is
  1882 · 1895 · 1923 · 1942 · 1959 · 1968, and the later sheets almost certainly
  do not. This is a per-sheet capability, and the pass must decline cleanly on a
  monochrome scan rather than return noise — the same shape as C2's
  "a monochrome scan scores ~0 and changes nothing".
- **Hatched classes fragment.** The deleted pipeline hit this and never fixed
  it: 7 of its 91 blocks were the cross-hatched local-service class, flagged for
  review. Nothing since has addressed it.
- **One tile, and the best one.** This is the dense, clean city centre. The
  sheet's margins are paddy and the neatline furniture is not blocks at all.

## Plan

Each step is gated on the one before it producing a number.

- **P1 — `work/ocr/scripts/colour_blocks.py`. Built 2026-09-18.** Emits
  `blocks.geojson` (the `crs: source-pixels-y-down` contract
  `to_sam2_seeds.load_seeds_from_prior` checks) and `blocks.run.json`
  (`seg_eval.py`'s shape) from the same polygons. `--census` prints the
  histogram and the pass refuses a unimodal sheet. `--self-check` runs with no
  network and no data files. Both contracts verified end to end: the file
  loads as 44 SAM2 seeds and as 44 scoreable polygons.
  **Scored 2026-09-18, and the gate is not cleared.** Whole sheet in 5.9 s of
  CPU: 189 blocks, 124 salmon + 65 blue-grey. Against the 24 `land_plot`
  traces it returns mean 0.124 / median 0.003 / cover 0.01, against
  `--blocks-from-roads` at 0.262 / 0.87. Full row in
  `work/ocr/EVAL-BASELINE.md`.

  **The reason is structural, and it reorders this plan** — see *P2 is a
  prerequisite* below.
- **P2 — roads from the cream complement**, separated by OCR `street_name`
  centroids; unlabelled cream components stay `non affectées`.
  **Exit:** a count of named streets on the sheet, and the fraction of cream
  area that a street name claims.
- **P3 — the two-reds test**, ink removed first. **Done 2026-09-18: the null.**
  No colour axis separates a building from the plot it stands on — best is
  `r − g` at **0.64 overlap** against the 89 building traces, where the
  green/cream pair scores 0.17 on the same measure. V is unimodal in every
  class. What differs is ink, not colour: 0.182 of a building trace is ink
  against 0.067 of open plot, so buildings here are **outlines over the same
  wash**, not a second fill.

  The parcel half is closed off too, by arithmetic rather than tuning: a
  divider is one ink run (2 source px, 1 at `--render 6051`) while the hatch
  *period* is 8 source px (4 render px), so any closing that rejoins a block
  across its hatching necessarily bridges a divider. Orientation is the one
  route left — and the hatch angle is **per block, not per sheet** (40° and
  140° in one crop), retaining only ~11% of ink, the rest being outlines and
  lettering. Recorded, not built.

  **So the within-block split is not a colour problem, and colour is now
  exhausted at the block level.** It is ink geometry, which is what SAM2 is
  for and where EVAL-BASELINE measures it earning its place (0.249 against
  0.161 for the same boxes raw). The blocks hand off unchanged: 253 → **246
  SAM2 seeds** after `main_map` clipping, against the modern prior's 950
  prompts on the same sheet, and on the ink instead of 11.3 m away from it.
- **P4 — write-back**, only if P1 clears: blocks as `footprint_submissions` with
  `feature_type` carrying the cadastral class, which is the half of the old
  pipeline's design worth keeping.

## What building P1 changed about the plan

Three things the measurement overturned, all on tile `4142_4032`. They are
recorded because each one was the obvious design an hour earlier.

**The first architecture was wrong.** The plan above says blocks are the
connected components of *not-ink*, separated by the printed outline. They are
not, at any scale. At 1:1 the building lines and the hatching are barriers too,
so the sheet breaks into **2,927 fragments** and 3 survive the area band. By 6×
downscale the outlines have greyed past the ink threshold and everything floods
into **one** component. There is no resolution where block outlines are
barriers and building lines are not, because they are the same ink.

**The rescue for that was also wrong.** The obvious fix — open the ink mask so
thin building lines vanish and heavy block outlines survive — assumes the two
line weights differ. They do not: a 2×2 opening takes ink from 10.2% to 3.0%
and a 3×3 takes it to 0.3%. Rejected in one command.

**What works is the pigment, and the separator is the street.** Componenting
the union of the pigmented classes gives blocks directly, because what divides
two blocks is 10–20 px of cream street while what divides two buildings inside
one block is a 1–2 px line. A closing kernel between those widths rejoins the
block and cannot bridge the street. Without it the tile's pigment is 1,674
fragments; at k=3 it is 208, and the kept-block count is then **flat from k=3
to k=15** (29–31 blocks, median ≈ 4,700 m²) — the knob is not doing the work.
Default 5, mid-plateau.

**The pale washes are not the colours they look like.** The *Parc du Génie*
blue-grey measures rgb(0.737, 0.713, 0.685) — `b > r` is never true, so a
channel-order test finds nothing and the first run silently dropped every
military parcel. What it does have is a much smaller `r − b` than the street
beside it, 0.052 against 0.123. Running the *same* `find_split` on that second
axis recovers them: 24 blocks → **44 blocks (22 salmon, 22 blue)**, and the
overlay puts Parc du Génie, Direction du Génie, Bouillerie de l'Opium and
Manutention de la Marine where they belong.

That cool split needed its own valley ratio (0.80 against 0.60). The asymmetry
is structural rather than a fudge: cream is most of the paper and the military
wash is a handful of parcels, so the smaller peak is low and the valley between
them is shallow *relative to it* by construction. A monochrome sheet still
refuses, because it has no second peak at all, and `--self-check` pins that on
both axes.

**Two things the overlay shows that no number reported.** The water — the
Genouilly canal — comes back in the cool class, correctly cool and wrongly a
block. And the green communal parcels are still missing: that wash differs from
cream in *value*, not hue, so it has no axis yet. Both are in the ledger.

## P2 is a prerequisite, not a follow-on

The plan above runs P1 → P2 → P3. Scoring P1 showed that order is wrong.

P1 emits only the pigmented classes, and this note estimated from the deleted
pipeline's tally that the cream *non affectées* parcels it skips were about a
quarter of the sheet. **In the actual ground truth they are 16 of the 24
`land_plot` traces — two thirds.** So the gate metric is dominated by the one
class P1 cannot see, and its pooled 0.124 pools 16 structural zeros with 8 real
answers. On the 8 it can see, it returns mean 0.352 / median 0.295 / cover
0.97, which would beat 0.262 / 0.87 — at n=8, on a subset chosen by the
classifier under test, so it is a reason to keep going and not a number to pin.

The obvious shortcut — just include cream — was measured and does not exist:

| mask | components | in band | largest |
|---|---|---|---|
| pigment only | 14,052 | **189** | 0.99 km² |
| pigment + cream | 362 | **0** | **11.91 km² (100% of the mask)** |

The street network welds every cream parcel to every other, so there is no
band, no block, no polygon. Separating the ribbon from the parcel — P2, using
the `street_name` extractions — is what makes the cream two thirds of the
ground truth reachable at all, and therefore what makes P1 scoreable.

**Revised order: P2, then re-score P1, then P3.**

### P2, done 2026-09-18 — and the diagnosis above was wrong

"Separate the street ribbon from the cream parcel" is not what was missing.
Cropping the sheet around the uncovered traces and drawing them shows they sit
on the pale grey-green **administrative parcels under diagonal hatching** —
*Direction des Travaux Publics*, *Hôtel du Procureur Général*, *Conseil de
Guerre*. Not unassigned land, not street. The picture said so before any metric
did, which is twice now on this track.

Two attempts on the wrong diagnosis died first: erosion (cream is 72.9% of the
sheet, mostly open country, so the mass survives at 8.86 km² at every radius
and "street" is 2% of cream) and local ink density (real at 0.120 against
0.000, but built-up areas score the same, so cover 1.00 at IoU 0.137).

The axis turned out to be the one already in use. Of six candidates scored
against the traced pixels, `r − g` separates best at 17% overlap — and the
hatched class sits *below* cream on it, where `find_split` never looked. At 48
bins the structure is plain: green +0.025, valley +0.030, cream +0.045. Same
primitive, mirrored, as `cool_split` already does.

**land_plot: 0.124 → 0.247 mean, 0.003 → 0.161 median, cover 0.01 → 0.98**
against `--blocks-from-roads` at 0.262 / 0.87. The `--close` sweep straddles
the target (0.273 at k=0, 0.247 at k=5) but the spread is 0.027 at n=24 —
noise, and the ends trade blue fragmentation against building cover, so the
default stays 5.

Full numbers, the axis table and the precedence finding: `work/ocr/EVAL-BASELINE.md`.

**What remains is P3.** Matched predictions are 3.72x the traced plot's area:
the hatched quarter returns as one block where the survey drew four or five
parcels, divided by the same 1-2 px lines that divide buildings inside a salmon
block. Coverage is solved; granularity is not — which is the ceiling the
block-prior runs already hit at `building` 0.160.

Two smaller findings from the same run:

- ~~**The ground truth has grown to 118 rows**~~ — **wrong, corrected later the
  same day.** It had not grown. `load_gt` filtered on `map_id` alone, and the
  `seg` run of 2026-09-16 wrote 72 of its own outputs back into
  `footprint_submissions` typed `building`. The sheet has 46 traces. Worse, the
  72 are OCR label boxes (median IoU 0.83 to their own prompt box), so they are
  not buildings in any sense. `seg_eval.load_gt` now filters
  `source=eq.volunteer`. `land_plot` numbers here are unaffected — 24/24
  volunteer — but everything this journal says about `building`, **including
  P3's null, was measured against lettering**. See the end of this file.
- **The split has to be voted, not pooled.** Run on the whole sheet the `r − g`
  histogram is unimodal and `find_split` correctly refuses it: salmon is ~6% of
  the paper and decays monotonically off the cream peak, because most of the
  sheet is margin and paddy. The bimodality is a property of the built-up area,
  not of the paper. Splitting the render into an 8×8 grid and taking the median
  of the crops that are bimodal recovers +0.0725 from 20 of 64 crops — the same
  value the dense city-centre tile gives on its own, and crops with no pigment
  abstain rather than drag it.

## Why the score from this will be worth more than the ones above it

Every SAM2 figure in EVAL-BASELINE is scored against the 46 hand traces that the
LoRA was **fine-tuned on** — train-set scores, flattered by an unknown amount,
as that file says in its own first lines. A colour threshold is trained on
nothing. Its score against those 46 is the first honest segmentation number this
sheet will have produced.

It is still only 46 polygons on one sheet, and C5's real blocker — a held-out
trace set — is untouched by any of this.

## Explicitly not in scope

The 2026-03 blog post this came out of, `/blog/buildings-as-ground-control`,
also proposed matching buildings across the 1882 and 1898 sheets with Hu moments
and RANSAC to auto-georeference the second one. **Not revived, and not on this
plan.** It needs building-granularity polygons on both sheets; nothing clears
IoU 0.5 on a single one of the 12 scored plots today, from any model. It also
solves a problem the archive no longer has — 132 maps are georeferenced, and
1898 is out of the D4 series because its georeference puts it wholly north of
the Bến Nghé canal.

## P2b — the cream parcels, and the constant that was hiding them (2026-09-18, same day)

The recorded dead end above says adding cream to the mask gives one component of
11.91 km², 100% of the mask, 0 blocks in the band, because the street network
welds every cream parcel to every other. That measurement is real and it is also
an artefact of a number: it was taken at `INK_V = 0.55`, the block pass's
threshold. At 0.55 a 2 px cadastral divider is grey rather than ink, so the
parcels leak into the street through their own boundaries.

Swept instead, on a quarter-scale probe, counting banded area:

```
 ink_v   ink%   comps   biggest%   in-band   band-area(m²)
 0.50     5.9   15404      97.9        0             0      ← everything welded
 0.65    11.2   20267      79.9       18         33954
 0.75    17.5   24939      35.8       70        218069      ← argmax
 0.85    26.2   29652      21.9       98        206038
 0.90    81.1   85337       0.1        0             0      ← paper becomes ink
```

The cliff at 0.90 is the sheet's own paper tone: V peaks there, so above it the
paper classifies as ink and there is nothing left to component. That is why
`cream_ink` bounds its sweep at `paper_peak(rgb) - 0.03` and takes the argmax of
banded *area* — the threshold is read off the sheet rather than carried between
sheets, which is the mistake this whole section is about.

The invariant that makes it measurable without ground truth: **a street network
is one component and parcels are many.** The street survives as the single
oversized component the area band already drops (6.19 km² on this sheet).

Whole sheet, `--render 6051 --cream`, 850 parcels, +4 s:

| run | n | @.5 | @.3 | mean | med | cover |
|---|---|---|---|---|---|---|
| blocks only | 253 | 4 | 5 | 0.247 | 0.161 | 0.98 |
| + cream | 1103 | 7 | 8 | **0.346** | 0.218 | 1.00 |
| + furniture drop | 1082 | 7 | 8 | 0.346 | 0.218 | 1.00 |

Target was 0.262. Missed land_plot traces go 2 → **0**; claimed area goes 14.4%
→ 32.9% of the scan.

**Read the n column before quoting the mean.** `seg_eval` takes the best match
per trace, so 4× the predictions can only raise it; the run prints that warning
itself. What the picture adds, and the metric cannot: the Batavia/Hamelin grid,
blank under the block pass, comes out as individual plots respecting the printed
dividers.

The two passes must not share knobs. At 0.80 the salmon class shatters into
10,078 components (20 in band) and the hatched green vanishes, because hatching
*is* ink at that threshold. Cream is the only class clean enough to read this
way, and that is a property of the class, not of the sheet.

**1:1 is not required, and I thought it was.** The plateau survives downscale to
1.37 m/px on the test crop; at `--render 6051` the pass scores 0.346 against
0.342 at full resolution. One fetch, one render, two passes.

### Map furniture, from the sheet's own labels

`furniture_mask` unions the padded `title` and `legend` OCR label boxes: 8
regions, 7.4% of the sheet, dropping 21 polygons (11 of the 253 blocks, 10 cream
parcels). The journal counted 10 furniture blocks by hand; the labels find 11.
The score does not move, which is the point — it drops things that were never
scoreable.

A convex *hull* of those boxes is wrong and was tried first: `legend` also tags
the boundary annotations strung along the neatline, so the hull spans
(349, 372)–(11655, 8525), very nearly the whole sheet. Per-label boxes, unioned.

### Still open

- **Water.** The river stipple fragments into in-band components along the whole
  bank. The 16 `hydrology` labels locate it but do not fence it — only 4 parcels
  hold a label centre, because the fragments are smaller than the lettering. A
  flood-fill from the labelled parcels through their neighbours is the obvious
  next primitive, unbuilt.
- **The green conflation, now with a measured cause.** Sampling the legend
  swatches at their caption rows gives the sheet's own key: *particulières*
  r−g +0.149, *non affectées* +0.059/r−b +0.149, *communales* +0.016/+0.122,
  *militaire et marine* +0.000/+0.008, and *service local* **r−b +0.075** against
  a detected cool split of **+0.073**. That class sits exactly on the boundary,
  so it is sliced between blue and cream by local paper tone. The fix is to
  classify by nearest swatch in (r−g, r−b) rather than by ordered 1-D troughs,
  which also deletes the precedence rule that currently has to be defended in a
  comment. Swatch V is printed ink (0.76–0.85) where the body is ink over paper,
  so the centroids need normalising against the cream swatch — cream being the
  one class whose on-sheet value is already known, because it is the paper.

## Nearest-legend-swatch classification — tried, measured, rejected (2026-09-18)

Prompted by Giraldo Arteaga, *Historical map polygon and feature extractor*
(NYPL Labs, MAPINTERACT '13), whose §3.2 calibration is a hand-enumerated list
of `basecolors` including the paper, and whose §3.6 assigns each polygon a class
by Euclidean distance from its average colour to that list. The paper even
records "there are two shades of red and two shades of blue" — the same problem
as this sheet's two blues. We have the list for free: the five legend captions
come out of the OCR with their y positions, and sampling the strip right of each
caption (taking the decile furthest from the local median, so the paper the
swatch sits on does not dominate) recovers the key automatically:

| caption | r−g | r−b |
|---|---|---|
| domaniales militaire et marine | +0.000 | +0.000 |
| domaniales service local | +0.039 | +0.067 |
| domaniales non affectées | +0.051 | +0.129 |
| communales | +0.016 | +0.122 |
| particulières | +0.153 | +0.255 |

Within 0.008 of a hand sample, and no hardcoded swatch column.

**A swatch is solid ink and a wash is that ink diluted over paper**, so the
swatches cannot be used as centroids directly: raw nearest-swatch puts 3.00M px
in *service local* and only 0.46M in *particulières*, where the trough
classifier finds 3.00M blue and 1.70M salmon. Classifying by *bearing* from the
paper swatch, which is scale-free and therefore immune to dilution, is worse
still — 44% of the sheet comes back *particulières*, because near the paper
point the bearing is noise.

Scaling the swatches toward paper by a dilution factor α does work, and α is
fittable without ground truth by agreeing with the trough classifier — a single
clean peak, 91.03% at **α = 0.60**, which reproduces the four known shares
(militaire 2.99M vs blue 3.00M, non affectées 17.78M vs cream 18.80M,
communales 0.93M vs green 1.00M, particulières 1.37M vs salmon 1.70M) and adds
*service local* as a fifth class at 1.38M px. Estimating α from the sheet's own
saturation tail instead does not work: p98–p99.9 of body chroma over the
strongest swatch gives 0.82–1.75, because the tail is the boundary crosses, the
seal and the dark building fills rather than wash.

**Scored at its own best α it is a regression, so it is not landed:**

| run | n | @.5 | @.3 | mean | med |
|---|---|---|---|---|---|
| troughs + cream (landed) | 1082 | 7 | 8 | **0.346** | 0.218 |
| nearest swatch, α = 0.60 | 1222 | 6 | 7 | 0.307 | 0.179 |

Building goes 0.114 → 0.081 as well, and it loses *with more predictions*, which
under a best-match-per-trace metric makes it unambiguous.

The likely mechanism, unverified: a fifth class interleaved with the fourth cuts
the pigment union differently, so blocks that were one component under four
classes fragment under five — the run labels 192 blocks *service local* against
8 *militaire*, which is not a plausible reading of the sheet and is the same
blue confusion arriving from the other side.

**So the precedence rule stays and is earning its keep.** What the swatches are
good for is naming and diagnosis, not boundaries: the boundary that matters is
where the *data* is sparse, which is what a trough is and what a swatch cannot
know. The diagnosis stands — *service local* at r−b +0.067 against a cool split
of +0.073 is genuinely on the line — but the fix is not this.

## The hull closing over the block it surrounds (2026-09-18, found by eye)

A cream component is very often the paper *around* a block — a street corner, a
margin, an L. `component_polygon` returns a concave hull, and the hull of a ring
is a disc, so that component came back as a polygon lying on top of the block it
surrounds. In an overlay it reads as the wrong class: a salmon block outlined in
cream.

Measured after it was spotted in a crop: **188 of 840 cream polygons were more
than a quarter pigment inside their own outline**, 22.1 Mpx in total. My earlier
check missed it because I measured polygon area ÷ *mask* area (median 1.02) —
these rings have large masks too. The diagnostic that finds it is pigment inside
the outline, not inflation over the mask.

Two fixes measured. Dropping the offenders outright is nearly free but treats the
symptom (t = 0.4: −72 polygons, 0.346 → 0.345). Subtracting the block polygons —
already in hand from the first pass, so no new geometry and no new dependency —
is better on both axes:

| run | n | @.5 | mean | med |
|---|---|---|---|---|
| before | 1082 | 7 | 0.346 | 0.218 |
| `subtract_blocks` | 1044 | 7 | **0.350** | 0.218 |

156 hulls cut back, 40 dropped as a block with a rim. A better score with fewer
predictions is an improvement twice over under a best-match metric.

It leans on the block hulls being roughly right, since it subtracts hull from
hull. The clean version is a raster trace of both — `rasterio.features.shapes`,
which is installed in this environment but is a GDAL dependency the script does
not declare, so it is not used.

### Still visible after the fix

- **Hatched areas emit sliver parcels.** Inside the *Prisons* block and other
  hatched administrative land, the cream pass finds the paper *between* the
  hatch lines and returns it as thin parcels. They survive `subtract_blocks`
  when the hatched area was not itself claimed as a block.
- **The blue wash keeps its internal lines, and could stop.** Swept on the
  Parc du Génie quarter at 1:1, the blue class has its own plateau and it is not
  cream's: in-band components go 19 at V<0.55 → 23 at 0.65 → **58 at 0.75** →
  1 at 0.80 → 0 at 0.85. So the parcel dividers inside blue *are* recoverable,
  at a threshold of blue's own, and the pass collapses a step earlier than
  cream's because the blue-grey is itself a hatch. The generalisation is a
  per-class sweep rather than one cream-only threshold — unbuilt.

## The blue quarter was never a classification problem (2026-09-18, found by eye)

Reported as "fails to detect the edge on blue": in the Arsenal / Casernes
quarter the blue-grey wash came back unclaimed and the cream pass drew ragged
orange around it. Neither the cool split nor the closing is at fault — blue is
20.5% of that crop either way. **The naval quarter is one blue component of
397,560 m² against a `MAX_AREA_M2` of 120,000, so it was dropped whole**, every
run, and the line `dropped 1 as too large` was it.

The cap is right about a merge failure and wrong about this. A legitimate
single-tint domain — a naval arsenal washed across many blocks *and the streets
between them* — trips it honestly. Re-cutting that blob at a higher ink
threshold, by the same banded-area sweep the cream pass uses, recovers it:

```
V≥0.55:  10 in band, largest 304,911 m²,  62,491 m² banded   ← today
V≥0.65:  37 in band, largest  79,620 m², 295,678 m² banded   ← argmax
V≥0.70:  81 in band, largest  43,288 m², 228,120 m²
V≥0.75: 115 in band, largest   4,669 m²,  81,906 m²          ← fragmenting
```

Three quarters of the blob comes back, and the largest piece now fits under the
cap. Sheet-wide: **blue 41 → 216 blocks, green 106 → 178, salmon 95 → 141**, and
land_plot 0.350 → 0.358 / median 0.218 → 0.232.

**It is behind `--recut` and off by default**, for two measured reasons.

1. **It costs ~60 s** against the 8.6 s default — the sweep re-labels a very
   large mask several times.
2. **It rescues the river too.** The water tint is blue-grey, so with the cap
   lifted the Rivière de Saigon comes back as dozens of blue "blocks". The
   `hydrology` labels ought to fence it and *cannot*: the arsenal's wash touches
   the river along the quay, so parent and river are the same component, and
   testing the parent drops the arsenal with the water — measured, blue 216 → 41.
   Moving the test onto the re-cut parts keeps the arsenal but stops catching
   the river, because 16 labels do not land in dozens of pieces. Sparse labels
   fence a region only when the region is already one blob.

Never on cream: an oversized cream component is the street network, one
connected surface by construction, and its oversize is the guard rather than a
failure. Re-cutting it returns ~240 street fragments and costs another 40 s.

### A contract bug found on the way

`write_outputs` built `blocks.run.json` from `shapely.get_coordinates(geom)`,
which returns *every* ring. `subtract_blocks` can leave a cream polygon with a
hole — a rim around a block — and flattening exterior and interior into one
coordinate list builds a self-crossing polygon: seg_eval rebuilt a true 0.20 Mpx
rim as 0.64 Mpx, and it cost land_plot 0.350 → 0.337 across 36 of 1044 polygons.
The run file now carries the exterior ring only, which is what its one-ring
contract can express; `blocks.geojson` beside it keeps the true geometry.

## What it would take to claim "no GPU" in public

Asked from the outreach side, where "a CPU threshold does this in 8.6 s" is the
part that travels further than the IoU. The claim is true of the run and not yet
defensible as a result. Four things stand between.

**1. There is no precision number, and the metric cannot produce one.**
`seg_eval` takes the best-matching prediction per trace. It never looks at a
prediction that matched nothing, so 1,044 polygons against 113 traces score
exactly as well as 113 good ones would, and every false positive in this journal
— the river ribbons, the hatch slivers — is invisible to it. Recall-flavoured
numbers are the only ones this pass has. A public claim needs precision, and
precision needs a sheet where *every* parcel is traced, not 118 of roughly a
thousand. That is a tracing job, not a code job, and it is the real blocker.

**2. One sheet, one era, one style.** Every number here is the 1882 Plan
Cadastral. The knobs are self-calibrating by design — the colour troughs vote,
the ink threshold sweeps against the paper peak, the area band is in metres — but
self-calibrating is a claim about the method, and it has been run on exactly one
sheet. Two more, from different decades and different printers, is the minimum.

**3. The comparison would be apples to oranges unless stated.** The SAM2 rows in
`EVAL-BASELINE.md` are scored against traces the LoRA was fine-tuned on — train
-set scores, flattered by an unknown amount, as that file says itself. A colour
threshold is trained on nothing, which is the honest strength here and is worth
saying plainly; it is also why "beats SAM2" would be a misleading sentence. The
defensible form is narrower: *this is the first segmentation number on this sheet
that is not a train-set score.*

**4. What the pass actually produces is a prior, not footprints.** 1,044 blocks
and parcels are prompts for the within-block split, and that split still needs
SAM2 and a GPU. "No GPU" is true of the prior; it is not true of the pipeline,
and the 3.9× merge measured at the top of this journal is exactly the part the
GPU is still for.

So the sentence that is currently true: **a CPU-only colour pass, calibrated from
the sheet itself and trained on nothing, produces a block-and-parcel prior for a
polychrome cadastral sheet in about nine seconds, and on the one sheet measured
it covers every hand-traced land plot.** Everything stronger needs item 1.


## The 118-row trace set was 46 traces and 72 label boxes (2026-09-18, found while rendering an overlay)

Drawing the predictions over the sheet to look at them, the ground-truth rows
rendered too, and 72 of them sat squarely on the map's *lettering* — a cyan box
around `HÔPITAL MARITIME`, around `MESSAGERIES MARITIMES`, around `Vge de Vĩnh
Hội`. They came from the `seg-20260916T1632` run, which wrote its output back to
`footprint_submissions` with `source='sam-auto'`, into the same table `load_gt`
reads with no filter but `map_id`.

Measured: median IoU from each `sam-auto` polygon to its nearest
`ocr_extractions` box is **0.829**, with 60 of 72 above 0.5, and each carries the
label text as `name`. They are the prompt box, barely moved — SAM2 segmenting the
lettering's background from OCR seeds, which is exactly what C4 predicted would
happen if a line feature's box were used as a prompt. The control is the 17
volunteer buildings at **0.054** on the same measure.

What it cost, by class:

| feature_type | volunteer | sam-auto | effect |
|---|---:|---:|---|
| land_plot | 24 | 0 | none — every headline number stands |
| building | 17 | 72 | every n=89 figure void |
| road / waterway | 5 | 0 | none |

So the whole cream-parcel result — 0.247 → 0.350, cover 1.00, missed traces
2 → 0 — is untouched, because `land_plot` was never contaminated. And `building`
re-scores *upward*, 0.114 → **0.122**, because a block prior cannot match a word
of lettering and 72 words were dragging it down.

**The expensive part was P3.** Its null — "there are no two reds" — is the reason
this track was written up as *colour exhausted, hand it to the GPU*. It was
measured against the 89. Re-measured against the 17, `r - g` overlap is 0.23
rather than 0.64, and with ink excluded from both sides it sharpens to 0.18
against the 0.17 that made green separable. The null is retracted; the table is
in `EVAL-BASELINE.md`.

### Two process notes, because neither is about this sheet

**A results table that a pipeline writes into is not a ground truth.** The bug is
one missing query parameter, and it was introduced by nothing — `load_gt` was
always written that way, and it was correct until the day something started
writing predictions into the table it reads. Nothing failed, no test broke, and
the number moved in the direction that looks like progress: 46 → 118 reads as
more tracing, and it was reported that way in three documents.

**The picture caught it and the metric could not.** That is now three times on
this track — the missing green class, the cream hulls closing over their own
blocks, and this. `seg_eval` takes the best match per trace, so it is structurally
incapable of seeing a prediction that matched nothing, and equally incapable of
seeing a *truth row* that should never have been there. Rendering the run over
the sheet costs about forty lines and has beaten the metric every time.


## The sheet has five classes and the pass had four (2026-09-18, found by looking at the legend)

Reported from the rendered layers: blue misses the river and many blocks, salmon
claims white plots that merely have red buildings on them, some salmon blocks are
missed, "and there's green and grey — check that."

All three are one finding. **The legend is the sheet's own class definition and
nobody had read it into the code.** Sampled from the `legend` triage region at
[9681, 6961, 1754, 988], median (r - g, r - b) and ink share inside each swatch:

| legend class | r - g | r - b | ink% | the pass calls it |
|---|---|---|---|---|
| domaniales affectées aux services militaire et de la marine | 0.000 | 0.008 | 21.6 | blue ✓ |
| **domaniales affectées au service local** | 0.039 | **0.067** | **59.6** | **blue ✗** |
| domaniales non affectées | 0.059 | 0.149 | 8.5 | cream ✓ |
| propriétés communales | 0.016 | 0.122 | 2.0 | green ✓ |
| propriétés particulières | 0.165 | 0.263 | 10.6 | salmon ✓ |

**The grey is a whole class, and it is a hatch rather than a tint** — 59.6% ink
where nothing else reaches 22%. No trough on `r - g` or `r - b` can find a class
that has no hue of its own, which is why five months of threshold work never
turned it up. Its `r - b` band is 0.047-0.078 against a cool split of 0.073, so
it falls on *both sides* pixel by pixel, welding the military blocks to the
administrative ones into components the area cap then drops whole. That is why
blue returns 41 blocks on a sheet that plainly has more.

**And no cascade of 1-D cuts can fix it, whatever the order.** Communales and
service local *swap* between the axes — on `r - g`, communales 0.016 < service
local 0.039; on `r - b`, service local 0.067 < communales 0.122. A precedence
rule picks one axis per class and cannot separate a pair that reverses. This is
the same shape as the note already in `classify` about green-first taking blue
from 65 blocks to 1, and it says that note was a symptom rather than a quirk.

### Salmon claiming white plots is a different bug, and it is structural

`dominant_class` votes over `PIGMENT_CLASSES = (salmon, green, blue)`. Cream is
deliberately not a candidate — "a block is a component *of* the pigment union, so
cream is not an answer here" — which is right for *finding* blocks and wrong for
*naming* them. A *non affectée* plot with red buildings drawn on it has no cream
pixels among the candidates, so it comes back salmon every time. It cannot do
anything else. Measured: 88 of 99 salmon blocks have a wash nearer the cream
swatch than the salmon one.

### Two nulls before the thing that worked

**Ink density does not isolate the hatch.** The obvious read of 59.6% is a
density threshold, and it fails because a densely built block carries just as
much ink as a hatched one. Added as a fifth class behind `--admin`, swept:

| | land_plot | legend agreement |
|---|---|---|
| baseline blocks | 0.247 | 42.7% |
| density 0.30 | 0.242 | 30.7% |
| density 0.45 | 0.243 | — |

**Nor does the density of *thin* ink**, which should have been better — a hatch
line is 2 source px where a building fill is not, so the ink that vanishes under
a 3x3 opening ought to be hatch and little else. 0.244 at t=0.20, 0.242 at 0.30,
0.124 at 0.10. Both reverted. The remaining route is orientation, which this
journal has already measured and priced.

### What worked: the legend key, diluted, applied per component

A swatch is the tint at full strength and a block is that tint laid thin, so
matching a block straight against the legend drops everything to the palest
class — salmon collapsed 95 → 8 on the first try. Fitting one global scalar
along each swatch's own direction away from bare paper, `paper + alpha * (swatch
- paper)`, chosen to minimise total distance from each block's wash to its
nearest prototype:

**alpha = 0.52** — the printed wash is about half the legend's ink. The fit has
one trap worth recording: fitted over all 1044 polygons it returns 0.38, because
~800 of them are cream parcels that are bare paper by definition, carry no tint,
and drag every prototype inward. Fitted over the pigmented blocks only it returns
0.52, and the hand check below moves 5/10 → 6/10 on that difference alone.

Applied **per finished component**, which is the whole difference from the
per-pixel nearest-swatch pass rejected earlier the same day: that one interleaved
two classes inside one block and fragmented it, 0.346 → 0.307. Per component it
cannot move a boundary — `land_plot` is 0.350 and `building` 0.122 before and
after, identically — only the name on it.

`colour_blocks.py --swatch-labels`, off by default.

### Scored on ten named blocks, because nothing else can see a label

`seg_eval` scores geometry against `land_plot`/`building` and never reads
`feature_type`. **There is no measurement in this repo for the thing that was
reported**, and the swatch-distance figure quoted above cannot referee it either,
since it is the same rule the classifier minimises. So: ten blocks named on the
sheet whose class is unambiguous, located by their OCR label, checked by hand.

| block | expected | before | after |
|---|---|---|---|
| Hôpital Maritime | blue | blue ✓ | blue ✓ |
| Caserne et Ateliers de l'Artillerie | blue | blue ✓ | blue ✓ |
| Hôtel du Directeur de l'Arsenal | blue | blue ✓ | blue ✓ |
| Manutention et Boucherie de la Marine | blue | blue ✓ | blue ✓ |
| Champ de Manœuvres | blue | cream ✗ | admin ✗ |
| Magasins des Travaux Publics | admin | green ✗ | **admin ✓** |
| Nouveau Palais de Justice | admin | green ✗ | **admin ✓** |
| Jardin Botanique | green | cream ✗ | admin ✗ |
| Prisons | admin | (no polygon) | (no polygon) |
| Jardin de la Ville | green | (no polygon) | (no polygon) |
| | | **4/10** | **6/10** |

**Where it is still wrong, and visibly so.** `admin` over-claims onto tree
stipple — it takes both the Jardin Botanique and the Jardin du Gouverneur's
grounds, which are dense fine ink and not a hatch — and it bleeds into the
Champ de Manœuvres.

### Each source of evidence where it is the stronger one

`green` first came back **470 times** on a sheet with nothing like 470 communal
parcels. Green and cream sit 0.043 apart on `r - g`, and diluting the swatches to
alpha 0.52 brings the prototypes closer still, so the key cannot hold that one
boundary. But the pass already computes a better boundary for exactly this pair:
`green_split`, the `r - g` trough voted from the sheet's own pixels, found at
`RG_FINE_BINS` precisely because the two modes are two bins apart at normal
resolution.

So the two are used where each is stronger — the swatches order the classes the
troughs *cannot* (communales and service local swap between the axes), the trough
cuts cream from green:

| | green | cream | admin | blue | salmon | named check |
|---|---|---|---|---|---|---|
| before any of this | 106 | 802 | — | 41 | 95 | 4/10 |
| legend key alone | 470 | 261 | 233 | 42 | 38 | 6/10 |
| key + voted trough | **53** | **678** | 233 | 42 | 38 | **6/10** |

The 53 are the Jardin de la Ville, the Cimetière Européen, the Château d'Eau and
a handful of small parcels — communal property, which is what the legend says.
Nothing else moved: the two administrative blocks stay correct, and geometry is
untouched at 0.350 / 0.122 throughout.

**The trap this closes, and it is subtle.** The two measures are not
interchangeable and mixing them silently is how the key ends up overruling a
better boundary. A legend swatch is an *all-pixel* median, ink included, because
two of the five classes *are* ink — measure only the paper between a hatch and
you throw away what defines it. `green_split` is a trough in the *paper-only*
histogram. `wash_points` therefore returns both per polygon, and the arbitration
compares paper to paper.

So: the class the sheet has and the code did not now exists and hits its named
targets, three classes are better, none is worse, and for the first time there is
a check that can tell. What remains wrong is `admin` on tree stipple, which is
the same dense-fine-ink confusion the two density nulls above ran into, and the
same place orientation is the only measured route left.


## Orientation, and the two ways of measuring it that do not work (2026-09-18)

The one route left on `admin` over-claiming tree stipple, priced twice in this
journal and now built. A hatch runs one way and stipple runs none, so the
question is only how to measure "one way" on a block that also holds building
outlines, lettering and a printed border.

**The route this journal priced is the one that fails.** A length-15 line
opening swept over 12 angles, at the render the pass works in: the *Magasins*
hatch keeps 0.017 of its ink at its best angle and the Jardin Botanique's
stipple keeps 0.032 — the garden survives a line opening **better** than the
hatch does. Same at 11 px (0.030 against 0.042) and at 7 px (0.108 against
0.118). The cause is the same one behind both density nulls: the hatch line is
one source pixel of grey, so at `INK_V` it comes back broken, and a broken line
has no length to open along. Measuring coherence on that same thresholded mask
fails identically — *Magasins* 0.215 against *Palais de Justice* 0.064, which is
not a separation at all, since the second is a hatched block too.

**What works is to stop thresholding.** The structure tensor of the greyscale
gradient, summed over the polygon and read as `sqrt((Jxx - Jyy)² + 4Jxy²) /
(Jxx + Jyy)`:

| block | what it is | coherence | at full source res |
|---|---|---:|---:|
| Magasins des Travaux Publics | black hatch | **0.738** | 0.809 |
| Nouveau Palais de Justice | black hatch | **0.589** | 0.753 |
| Champ de Manœuvres | faint blue ruling, 2.9% ink | 0.118 | 0.269 |
| Jardin Botanique | tree stipple | **0.036** | 0.070 |
| Cimetière Européen | tree stipple | **0.029** | 0.087 |

An order of magnitude, where every density measure tried got a few percent. It
is a ratio of the tensor's eigenvalue gap to its trace, so it is blind to *how
much* ink a block holds — which is exactly what ink density could never get
past, a densely built block carrying as much ink as a hatched one. Its ink runs
two ways at once and cancels; a garden's runs every way; only a ruling runs one.

`--hatch-coherence`, default **0.30**, applied to the polygons the key has
already called `admin`. 61 of 233 fail it.

### Where a demoted block goes, which took three tries

**Nearest tint on the all-pixel median: rejected on the picture.** It scores
*better* on the named check — 7/10, because the Champ de Manœuvres lands on blue
— and it paints both gardens military. A dense black stipple's all-pixel median
is (0.039, 0.078) and the diluted blue prototype is (0.030, 0.079): they are the
same point, so **any** heavily stippled block goes blue whatever wash is under
it. Blue 42 → 73. The extra point was luck, not signal: the Champ's polygon and
the garden's are indistinguishable on every colour measure taken — ink (0.035,
0.082) against (0.039, 0.078), paper (0.035, 0.110) against (0.039, 0.110).
Getting the Champ right required calling the Jardin Botanique military.

**Nearest tint on the paper median, blue still on the ballot: also rejected.**
It fixes the Botanique and still sends the Jardin du Gouverneur's grounds to
blue, at blue 63.

**The rule that holds** drops both ink classes from the ballot. The legend draws
two of its five classes as ink rather than as tint — *service local* at 59.6%
and the military class at 21.6%, against 10.6% for the densest tint — so a block
whose ink has just been shown **not** to be a ruling cannot be either of them,
whatever colour that ink is. It falls back to the nearest of the three tints,
matched on its paper. Blue then stays at exactly **42**: not one block gains the
class, which is the check that the fallback is not laundering one error into
another.

| | admin | cream | green | blue | salmon | named |
|---|---:|---:|---:|---:|---:|---:|
| key + voted trough | 233 | 678 | 53 | 42 | 38 | 6/10 |
| + hatch test | **172** | 735 | 57 | **42** | 38 | **6/10** |

### The named check does not move, and the layer does

This is the honest result: 6/10 before and 6/10 after. What changed is which
rows are wrong and what the rendered layer looks like. `admin` no longer claims
the Jardin Botanique, the Jardin du Gouverneur's grounds or the Champ de
Manœuvres — the three failures this was built for, all visible in
`06_admin_service_local.png` and all gone — while both genuinely hatched blocks
keep the class. The Champ moves from `admin ✗` to `cream ✗` and the Botanique
from `admin ✗` to `cream ✗`.

The Botanique misses `green` by 0.007: its paper `r - g` is 0.039 against the
sheet's voted trough at 0.032. That is the trough's own resolution and not
something the hatch test can reach — it is the same cream/green pair that needed
the trough in the first place.

Geometry is untouched by construction, `land_plot` 0.350 and `building` 0.122 to
the digit, and the default path without `--swatch-labels` is byte-for-byte
identical. About +1.5 s on the whole sheet.

**What it says about the method.** Three of the five legend classes are a tint
and colour names them. Two are ink, and no amount of colour work was ever going
to name those — the r − b band of a hatch straddles the cool split, its wash is
the paper it is drawn on, and its density is a built block's density. Naming
them needs a measure of *how the ink is laid down*, and orientation is the
cheapest one that exists. Colour was not exhausted at the block level; it was
being asked a question that is not about colour.


## The river is not blue, and that is why blue never found it (2026-09-18)

Reported from the layers for the second time — "blue still not able to
correctly find the river". It cannot, and the measurement says why in one line:
**the open river is bare paper.**

| patch | wash (r − g, r − b) | ink (r − g, r − b) | ink % |
|---|---|---|---:|
| open river, mid-channel | +0.059, +0.141 | — | 0.3 |
| river ripple, off the quay | +0.051, +0.125 | +0.020, **+0.031** | 3.7 |
| dry land, NW quarter | +0.047, +0.133 | +0.035, +0.102 | 8.9 |
| Hôpital Maritime (the blue class) | +0.027, **+0.067** | +0.016, +0.024 | 5.1 |

Mid-channel the water is the same tone as dry land to three decimals. What
makes it read blue to the eye is the engraved ripple, which genuinely is blue
ink — r − b +0.031, next door to the military class's +0.024 — laid over 0.3 to
4% of the surface. `classify` reads the *wash*, per pixel, so the river comes
back cream everywhere except on the lines themselves. No threshold on a wash can
find a thing that has none. The blue along the quay in the reported crop is the
*Arsenal de la Marine*, which is military property and correctly blue.

So water is the one feature on this sheet that is **drawn rather than washed**,
and finding it takes all three of its parts at once:

- its ink is blue — `r - b < 0.060` over the ink pixels
- there is very little of it — under 15% of the polygon
- and the paper underneath carries no wash at all — `r - b > 0.100`

Each condition alone is wrong. Sparse blue ink is also a military block; bare
paper is also every *non affectée* plot. **The paper test is the one that keeps
the naval quarter**: Hôpital Maritime's ink is blue too (+0.024) and sparse too
(5.1%), and the only thing that differs is that it has a wash at all.

`--drop-water`, off by default and **the only flag here that removes geometry**.
It drops 55 of 1044 polygons, 0.75 km²:

| | polygons | ribbons (circ < 0.10) | ribbon area | land_plot | building |
|---|---:|---:|---:|---:|---:|
| before | 1044 | 110 | 1.17 km² | 0.350 | 0.122 |
| `--drop-water` | 989 | **76** | **0.48 km²** | 0.350 | 0.122 |

**Nothing is lost, and that is the whole result.** `seg_eval` takes the best
match per trace, so a drop that touched a real parcel would show up immediately
as a fall in `land_plot`; 55 polygons leave and both scores hold to the digit,
cover stays 1.00 and the named check stays 6/10. Every one of the 55 was a false
positive. Rendered, they are the Rivière de Saigon, the Arroyo de l'Avalanche,
the Arroyo Chinois at Tam Hội and the scan margin outside the neatline —
`10_dropped_as_water_55.png`.

**It is a precision improvement and the metric still cannot see it.** This is
the first change on the track that makes the run *smaller*, and the file has no
number that rewards that — a recall-flavoured score is indifferent to 55 fewer
false positives, which is exactly the blind spot item 1 of *what it would take
to claim "no GPU"* describes. The honest way to state it is as the count and
the area, not as a score that moved.

It also does not find the whole river: 76 ribbons remain, and the pass only ever
sees water where the cream pass already drew a polygon.

**Superseded the same day — see the next section.** Looking at the rendered
zoom, the surviving ribbons are as plainly on the water as the dropped ones, and
the reason the test abstained on them turns out to be structural rather than a
threshold that needs loosening.



## Water is a region, and a polygon inside it holds no evidence at all (2026-09-18)

Reported a third time, with the zoom: orange ribbons still lying across the
river beside the blue ones that had gone. The per-polygon test above was not
too strict, it was **reading the wrong thing** — and the diagnostic says so
immediately. Of the 48 polygons in that window south of the quay:

| why it survived | how many | what it looks like |
|---|---:|---|
| **too little ink to judge** — 0 to 17 pixels | 38 | it sits *between* the ripple lines |
| ink not blue | 6 | it clips the lettering RIVIÈRE or a quay line |
| has a wash | 3 | it is up against the bank |

Thirty-eight of forty-eight contain no evidence whatsoever. A polygon drawn in
the gap between two ruled lines is bare paper and nothing else, and no
per-polygon measure can ever call it water, because the thing that makes it
water is *outside* it. Water is a region.

### The obvious region fails, and it fails big

Flood the `hydrology` labels through the blue ink, which is what this journal
had proposed two sections earlier: at `V < 0.80` and `r - b < 0.060` the blue
ink mask is **12.25% of the whole sheet** and closes into **one component** that
covers everything. Black ink is neutral, so `r - b` near zero does not mean blue
— it means *dark*, and at a threshold loose enough to catch a pale ripple line
it catches every printed line on the sheet. Rejected in one command.

### What is true of water and of nowhere else

Not colour, and not per polygon: over a **cell** of a few dozen pixels, the
water's line work all runs one way, there is no wash, and the ink is sparse.
That is `ink_coherence` again, from the hatch test, measured on a grid instead
of on a polygon:

- 64 render px cells, coherence > **0.45**, wash `r - b` > 0.100, ink < 25%
- component the passing cells, keep the components holding one of the sheet's
  16 `hydrology` labels
- drop any polygon more than a **third** inside the result

The label seeding is the whole safety of it. Ruled, washless, sparsely inked
cells describe the river, the two arroyos **and the ruled neatline margin** —
and the labels are what say which of those to believe. (Dropping the margin is a
bonus: it is furniture.) The wash test is what keeps the naval quarter, which is
ruled too but at `r - b` +0.067 against bare paper's +0.133.

Only **3 of the 16 labels** actually seed anything, and all three seed the *same*
component — the other thirteen land on mixed cells along the narrow arroyos — so
it is one seed's worth of evidence, enough here because the main river is that
component. On a sheet of many small ponds it would not be.

### And a shape filter, which is a different claim

A parcel is compact and a ripple is not: `4πA/P²` is 1 for a circle, above 0.2
for a cadastral parcel on this sheet, and under 0.1 for what the cream pass
traces between ripple lines. `--drop-slivers` at **0.10**. Swept: at 0.10 it
drops 110 and both scores hold to the digit; at **0.15 land_plot falls to
0.326**, so the ceiling is measured two steps away. It is not a water
detector — it takes a sliver wherever one is, including the rims
`subtract_blocks` leaves — but on this sheet the slivers are the river.

### Together

| | polygons | ribbons (circ < 0.10) | claimed area | land_plot | building | named |
|---|---:|---:|---:|---:|---:|---:|
| the legend key alone | 1044 | 110 | 4.85 km² | 0.350 | 0.122 | 6/10 |
| `--drop-water` (region) | 892 | — | — | 0.350 | 0.122 | 6/10 |
| + `--drop-slivers` | **832** | **0** | **3.51 km²** | **0.350** | **0.122** | **6/10** |

212 polygons and 1.34 km² leave — **28% of the claimed area** — and `land_plot`
0.350 / 0.218 and `building` 0.122 / 0.050 do not move at all. The only number
that does is `road` cover, 0.68 → 0.59: some of the dropped ribbons lay across
the quay roads, and covering a road with a false parcel was never worth
anything. Ribbons reach zero.

The overlap `share` was swept at 0.50, 0.35 and 0.25 — 121, 152 and 163
polygons dropped, and `land_plot` 0.350 / cover 1.00 at every one. **The sweep
is bounded by the picture, not by a score**, which is the same blind spot as
before: nothing in `seg_eval` rewards a smaller run, so the stopping rule was
"open the zoom". 0.35 is the setting where the river reads clean and four small
fragments remain at the region's square edge.

### Three mechanisms for one problem, and why two stayed

The per-polygon colour test is now **subsumed**: measured against the region, its
unique contribution was 21 polygons and 0.06 km², so it is gone and its
constants with it. What remains is one region test and one shape test, which
make different claims — *this is water* and *this is not a parcel* — and the
second is the one that generalises, being a single line with no threshold
fitted to this sheet's ink.

## The region was not the river — reopened the same day

The claim above, that "the river reads clean and four small fragments remain at
the region's square edge", does not survive looking at the rendered layer. The
river is still full of kept ribbons. Shading the region itself over the sheet
says why, and it is not a fragment at an edge.

**The region is mostly the neatline margin.** Its component's bounding box is
x 128–5888, y 128–4352 of a 6051 × 4491 render, because the ruled frame around
the sheet and the river are one connected component. The docstring's safety
argument — the labels say which regions to believe — is weaker than it reads: a
label only has to seed one cell of something that already spans the sheet.

**And inside the river it is a checkerboard.** Per cell over the Messageries
Maritimes window, 225 cells, of which 77 pass:

| rejected on | cells | median `r − b` | ink | coherence |
|---|---:|---:|---:|---:|
| **no wash (`r − b` ≤ 0.100)** | **65** | **+0.071** | 0.029 | **0.861** |
| coherence ≤ 0.45 | 53 | +0.133 | 0.047 | 0.189 |
| too little gradient | 30 | +0.141 | 0.000 | — |
| *passed* | 77 | +0.125 | 0.009 | 0.849 |

The first row is this note's own headline contradicting itself. Those cells are
ruled better than the ones that pass and their ink is sparse; they fail only
because the **all-pixel** median is dragged under the threshold by the ripple
ink itself. The denser the ripple, the more certainly the cell is thrown away —
and the dense ripple is the band along the bank, exactly where the cream pass
fragments worst. The other two rows are the sheet's own lettering across the
water, and open channel with nothing drawn on it to measure.

### What was tried on the wash test, and why none of it is in the code

Every attempt to loosen the wash test floods, because the safety was never the
labels — it was that the city's cells happen not to *connect* to the river's.

| | cells | region | drops | traces eaten |
|---|---:|---:|---:|---:|
| median `r − b` (as shipped) | 1910 | 10.4% | 152 | 0/46 |
| paper-only median (ink masked) | 1929 | 10.6% | 157 | 0/46 |
| 90th percentile of `r − b` | — | 31.7% | 563 | **21/46** |
| median over low-gradient pixels only | — | 31.2% | 547 | **15/46** |
| strict seed, grown through the loose test | — | 31.2% | 547 | **15/46** |

Masking the ink does nothing because the ripple is blue at `V ≈ 0.6` and `INK_V`
is 0.55 — the lines are not in the ink mask at all. The percentile and
low-gradient measures do separate river from wash cell by cell (63 of the 65
recover; the Arsenal blocks stay at +0.047…+0.059), but they also admit every
bare-paper city block with a ruled street grid, and once those are candidates
the whole sheet is one component. **The cell test does not describe water. It
describes bare paper with ruled lines, which is also most of the city.**

### What is in the code instead

Two changes that leave the region test alone:

- `WATER_HOLE = 12` cells. Fill the holes the lettering and the open channel
  punch through the region. The sheet's region has 19 holes: eighteen of 1–3
  cells, then one of 384. Any cut between 3 and 384 is the same cut.
- `WATER_RIPPLE_CIRC = 0.25`. A polygon that touches the region **at all** and
  is too stringy to be a parcel is ripple. The region's edge is a 64 px
  staircase, so a ribbon along the bank keeps most of its area outside it
  however good the region is — the share test can never reach those.

The second is safe for a measured reason rather than an assumed one: **not one
of the 46 hand traces overlaps the region by a single pixel** (max share 0.000),
so it cannot reach a trace.

| | polygons | water | slivers | land_plot | med | building | med | road cover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| share test only | 832 | 152 | 60 | 0.350 | 0.218 | 0.122 | 0.050 | 0.59 |
| + holes + ripple | **811** | **179** | 54 | 0.350 | 0.218 | 0.122 | 0.050 | 0.59 |

All 21 newly dropped polygons were checked by eye: twelve are ripple ribbons
off the Dock Flottant, the rest lie along the bank. The default path is still
byte-for-byte identical to `a41134eb`. The self-check now carries a water
fixture — ruled bare paper over blank paper, one cell scribbled out to punch a
hole — and it fails if either new constant is disabled.

**Still wrong:** the ribbons at the mouth of the Arroyo Chinois. The region does
not reach into a channel that narrow, so their share is zero and neither test
applies.

**And the named check is not reproducible.** Ten labels, resolved against
`ocr_extractions`, is ambiguous — several of the ten have duplicate rows at
different positions, and which one you take changes the answer. A rebuild of
the check scores 7/10 where this note records 6/10, on the same polygons. It is
unchanged by this fix either way, which is all it can honestly be used for
until the script is committed.

## The water is a blue line, and the grid is gone

Two further rounds, both driven by looking at the rendered layer.

**The region walked up a canal.** At Vge de Tam Hoi it had claimed whole
cadastral parcels on dry land. The cause was not a threshold: the region had
**no barrier at all**. What kept it off the city was only that the city's cells
did not happen to *connect* to the river's, which is why every loosening of the
wash test in the table above floods.

So land bounds it, taken from the pass's own output: any polygon compact enough
to be a parcel, since the cream pass fragments water into ribbons and nothing
else on the sheet is a ribbon. With a real barrier the wash test could finally
be measured between the lines rather than over all of a cell's pixels — but
that was still a 64 px grid, and a grid cannot follow a quay.

**Then: the water is a blue line.** Not blue as `b > r` — nothing on this sheet
is, the ripple's own `b - r` is −0.051 — but *less red than black ink*. Over the
dark pixels:

| | `r − b` of the dark pixels |
|---|---:|
| river ripple, mid-channel | **+0.051** |
| river ripple at the quay | **+0.031** |
| the Tam Hoi canal | **+0.035** |
| black ink, a city block | +0.086 |
| lettering | +0.169 |

Threshold that, close the gaps between the lines, subtract land, keep the
components a `hydrology` label seeds, fill the holes the sheet's own lettering
punches: the result is the water's shape to the pixel. The whole cell grid —
`WATER_CELL`, `WATER_COHERENCE`, `WATER_PAPER_RB`, `WATER_INK_MAX` — is gone,
and with it the staircase edge along every bank.

**Hue alone is not enough, and the trap was expensive.** The military class's
wash is blue-grey too. It ran down the streets of the Arsenal quarter, joined
the river, and took the Jardin Botanique and 0.14 km² of the Magasins de la
Marine: `land_plot` **0.350 → 0.326**, `road` cover **0.59 → 0.14**. The water
is a *line*. Erode by a line's own width and a wash survives while a ruling
disappears, so what survives is exactly what to exclude.

**And one measurement was wrong everywhere it was used.** `4πA/P²` taken on a
polygon with holes loses the courtyard from `area` and gains its ring in
`length`, so an ordinary city block scores below a ribbon. That is how a
0.14 km² piece of the Jardin Botanique came to be called ripple. Circularity is
now taken on the outline (`outline_circularity`), for both the land mask and
the stringiness test.

| | polygons | water | slivers | land_plot | med | building | road cover | waterway |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| the cell grid | 832 | 152 | 60 | 0.350 | 0.218 | 0.122 | 0.59 | 0.64 |
| + holes + ripple rule | 811 | 179 | 54 | 0.350 | 0.218 | 0.122 | 0.59 | 0.64 |
| + land bound, wash between the lines | 783 | 224 | 37 | 0.350 | 0.218 | 0.122 | 0.59 | **0.51** |
| blue line, before the wash filter | 792 | 209 | 43 | **0.326** | **0.191** | 0.122 | **0.14** | 0.51 |
| **blue line, wash filtered, outline circularity** | **798** | **203** | 43 | 0.350 | 0.218 | 0.122 | **0.52** | 0.64 |

The last row is what is in the code. `road` cover 0.59 → 0.52 is the only number
that moved, and it is the quay roads losing the false ribbons that lay across
them. Default path still byte-identical to `a41134eb`. The self-check carries a
blue-line fixture and fails if any of the six mechanisms is switched off.

### What is still wrong: the Arsenal's dockyard apron

The region runs past the Quai into the Arsenal de la Marine's yard — the strip
of slipways, sheds and the dry dock between the quay line and the water. It is
claimed at 1.00.

Nothing separates it, and that was measured rather than assumed:

- **Not colour or line.** It is bare paper ruled in the same fine blue-grey as
  the river, because a dockyard apron and a tidal foreshore are drawn the same
  way on this sheet.
- **Not black ink.** The yard has buildings on it, but its black-ink density is
  2.91–4.84% against the river's 2.31–4.77%. They overlap.
- **Not a wall.** Cutting the region at every black line (`V < 0.55` and
  `V < 0.65`, dilated 0, 1 and 2 px) leaves the yard claimed at 1.00 in every
  one. The quay line does not disconnect it, and it should not: the slipways
  run into the water, so on the paper the yard *is* continuous with the river.
- **Not the land bound**, because the land bound is polygons and **no polygon
  covers the yard**. The block pass emits nothing there, so the barrier has
  nothing to work with. That is visible directly in the layer: the land mask
  stops dead at the quay line.

So the fix is not in the water test. It is that `Arsenal de la Marine` should
be a block — it is a named military parcel, and the pass already calls its
neighbours blue — and once it is, the land bound removes the yard for free.
Filed against the block pass, not this one.

## The Arsenal yard was never a filter's fault — the block pass drops it whole (2026-09-18)

Picking up the item above. The yard is claimed as water because no polygon
covers it; the question was which of the block pass's filters drops the
component that should.

**It is the area cap, and it is the only one.** On the 1882 sheet at
`--render 6051`, `blocks_from_colour` drops exactly one component as
`too large`: 3,769,338 render px, **1.77 km²** against the 120,000 m² cap. Its
bbox is y 287–4120, x 296–5544 — most of the sheet. It is the naval quarter's
blue-grey wash welded to the river's ripple band, the Arroyo Chinois, the
Magasins and the citadel blocks, all one connected blue component. The Arsenal
label at source px (7517, 6749) sits inside it. Nothing else touches it: the
closing is not involved, and neither bound of the area band is near.

Two things were measured and are not the answer:

- **Opening the blue class before the closing**, to strip the ripple back to
  lines and leave the washes solid — disks of radius 1, 2 and 3. The component
  shrinks (3.77 → 3.46 → 3.04 → 2.03 M px) and **never disconnects**. At render
  6051 the river's ripple band is not stripes in the blue class, it is solid:
  the class picks up the paper between the lines as readily as the lines.
- **Subtracting the pixel water region from the pigment** before componenting.
  The region claims the yard at 1.00 — that is the defect — so this deletes the
  yard instead of rescuing it.

### `--recut` already does it, and the water test paid off its old cost

`--recut` is the existing rescue for an oversized component: re-cut it at a
higher ink threshold and keep the pieces that land in the band. Its help text
warned it "costs ~60 s and river false positives", which is why the previous
sessions left it off. With `--drop-water` in the tree that warning is stale —
the pieces that land on the river are dropped by the water test, and the pieces
that land on the Arsenal are kept, because a piece *is* a compact polygon and
`land_mask` bounds the region at it. The yard comes out as an **81,764 m² blue
block**, the region stops at the shoreline, and the river beside it is untouched.

| | polygons | water | slivers | land_plot | med | building | road cover | waterway |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| shipped (`9a2fe561`) | 798 | 203 | 43 | 0.350 | 0.218 | 0.122 | 0.52 | 0.64 |
| `--recut`, as it stood | 892 | 348 | 56 | 0.331 | 0.218 | 0.122 | **0.14** | 0.99 |
| **`--recut`, named-label rule** | **888** | **352** | 56 | 0.331 | 0.218 | 0.122 | **0.14** | 0.99 |

`road` cover 0.52 → 0.14 is the re-cut taking the quay roads back out of the
blocks that lay across them, and it is the largest single move that number has
made. `land_plot` mean 0.350 → 0.331 (@.5 7 → 6) is the real price: the re-cut's
new blue blocks make `subtract_blocks` cut 259 cream hulls rather than 156, and
one traced plot loses its match. `waterway` cover 0.64 → 0.99 is **not** the
river — it is the Abattoir's grounds, correctly claimed as one parcel, with a
small traced ditch inside them.

### The one thing the re-cut did break, and the one line that fixes it

The re-cut emits a 28,000 m² polygon over the **Arroyo Chinois** at 0.315
outline circularity — compact enough for `land_mask` to call it a parcel. So it
enters the land bound, carves itself out of the water region, and vouches for
itself. Circularity cannot separate it: the arroyo polygon scores **0.415** and
the Arsenal yard **0.363**, the wrong way round.

What separates them is that **the sheet names one of them**. The arroyo polygon
holds a `hydrology` label at source px (1353, 3740); the Arsenal polygon holds
none, and on the whole 798-polygon shipped run *no* polygon holds one. So:

> A polygon that holds a `hydrology` label is water, and is never land.

Same evidence the oversize path has always used (`_holds_point` at
`colour_blocks.py:526`), now read on the polygon side too. It removes exactly
the arroyo polygon and the three it was shielding (348 → 352 dropped as river
surface, 892 → 888 kept), changes nothing on the shipped run — `blocks.geojson`
md5 unchanged against `9a2fe561` — and costs no new constant.

### Still open

- **`--recut` stays opt-in.** It is 25 s → 80 s and it costs `land_plot` 0.019.
  Whether the Arsenal yard, the Abattoir grounds and the quay roads are worth
  that is the user's call, not the script's default.
- One small admin ribbon survives on the arroyo's near bank under `--recut`.
- `Prisons` and `Nouveau Palais de Justice` still have no polygon. They are
  *not* this problem — the oversize component is the only one dropped that way,
  so whatever drops those two is a different filter.

## 2026-09-19 — the creek is the same ruling, packed

Reported from the layers for the fourth time, and this one is not the river:
the **Rach Cầu Chông** reach at Khánh Hội and the inlet at Hội An are drawn in
the same engraved ripple as the Rivière de Saigon, and the pass claimed
neither. Both are narrow.

The measurement separates them in one line. Of the blue the hue test finds,
the open river keeps **91%** through the wash cut and the creek keeps **21%**:

| window | blue (hue) | after the wash cut | survives |
|---|---:|---:|---:|
| open river | 24.45% | 22.34% | 91% |
| Rach Cầu Chông | 9.63% | **2.02%** | **21%** |

The wash cut is `blue &= ~dilate(erode(blue, W), W + 2)`, and its premise is
that water's line work is *sparse ruling*, which erodes to nothing, while a
military or administrative wash is an area fill, which survives. That premise
holds for a river 400 px wide. A creek is the same ruling packed into a
ribbon, and wherever two lines touch, the pair survives the erosion as a
crumb. The creek window threw **305 crumbs, none larger than 140 px**, against
the river window's 62 totalling 243 px — and each crumb is then *dilated* by
`W + 2`, so 1,869 px of crumb blanketed 8,200 px of creek.

So the fix is not on the erosion, it is on what the erosion is allowed to
call a wash: **component the survivors and keep only the ones big enough to be
an area fill.** `WATER_WASH_MIN_PX = 200`. The creek's largest crumb is 140 px
and the Arsenal quarter's genuine wash component is 1,140 px, so the threshold
sits in a gap that is an order of magnitude wide, not a tuned number.

Swept against the five windows that must **not** become water, and none of
them moves at any setting:

| `wash_min` | sheet | creek | pond | river || Botanique | Hôpital | Magasins | Champ | city |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 0 (was) | 10.85% | **0.1%** | 0.0% | 86.7% || 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 100 | 11.03% | 11.2% | — | 87.6% || 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| **200** | **11.04%** | **12.6%** | claimed | 87.6% || 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 400 | 11.05% | 12.6% | — | 87.6% || 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

**It is free on every score in `EVAL-BASELINE`**: 798 → 797 polygons, 203 →
204 dropped as river surface, and `land_plot` 0.350 / 0.218, `building` 0.122 /
0.050, `waterway` 0.409, road cover 0.52 all hold to the digit. That is the
point rather than a footnote — the pictures are the only instrument that can
see this class of defect, which is the precision blind spot stated for the
fourth time.

**A seeding radius was measured and is not needed.** The `Rach Cầu Chông`
label's centre lands on its own lettering and seeds nothing, so the obvious
second fix is to seed from a disk. Swept at 0/30/60/120/200 source px it
changes **no** component and **no** score, because once the mask is intact the
creek is connected to the river it drains into and the river's own labels
already seed it. Not built. It would be needed on a sheet of unconnected
ponds, which this is not.

### `--recut` is now the default

The Arsenal's water/land edge was reported in the same round, and it is the
2026-09-18 finding unchanged: the naval quarter is one 1.77 km² component, the
area cap drops it, nothing bounds the region there, and the water runs over the
quay, the sheds and the dockyard apron. `--recut` is the only thing that fixes
it, and with the edge now the reported defect the flag has stopped being
optional. `--no-recut` restores the old run.

The price is unchanged and still real: `land_plot` mean **0.350 → 0.331**
(@.5 7 → 6), 25 s → 80 s. What it buys, beside the Arsenal: road cover
**0.52 → 0.14**, `waterway` 0.409 → **0.582** with cover 0.64 → **0.99**.

### Two things measured and NOT built

- **Dedup.** 797 kept polygons hold **0 pairs above IoU 0.90** — there are no
  duplicates. What looks doubled is **89 pairs where the smaller polygon is
  ≥95% inside a larger one** (0.176 km²), which is a sub-parcel inside a block,
  not noise. Dropping the contained one costs `land_plot` 0.350 → **0.324**;
  dropping the container costs 0.350 → **0.312**. Neither improves anything.
  The traces match the nested polygons, so the nesting is carrying the score.
- **Simplifying the rings.** They are already sparse — **12 vertices per
  polygon**, 9,547 over the whole run — so there is no staircase to clean.
  `simplify` at 4 source px removes 23% of the vertices and buys nothing.

What *was* dirty is the picture: `review_figs.py` drew every dropped polygon,
which on a river window is hundreds of ripple ribbons over the thing being
checked. Now `--dropped`, off by default, and the kept outline is 2 px.

## 2026-09-19 (ii) — the crumb rule let the garden in, and direction took it back

`WATER_WASH_MIN_PX` rescued the creeks and then flooded the **Jardin
Botanique's stipple beds** — but only under `--recut`, which is why the first
sweep missed it. The land polygon that had been covering the garden is one of
the ones the re-cut rearranges; take it away and the stipple, now surviving the
weakened wash cut, joins the river's component.

**No crumb size separates them.** Swept under `--recut`, the garden floods at
`wash_min` **20** and the creek does not come back until **100**. The bands do
not overlap, they invert.

Direction does separate them, and it is P2d's own measure read on a grid —
`ruling_mask`, 16 render px cells, coherence ≥ 0.30:

| | median coherence | cells ≥ 0.30 |
|---|---:|---:|
| open river | 0.892 | 97% |
| creek (Rach Cầu Chông) | 0.831 | 90% |
| **Jardin Botanique lake** | **0.757** | **76%** |
| Jardin Botanique stream | 0.147 | 21% |
| Jardin Botanique stipple | 0.153 | 11% |

**Gating cell by cell killed the creek**, which is the same mistake as dilating
every erosion crumb, one level up: the 10% of a creek's cells that fail sever a
thin ribbon into fragments under `WATER_MIN_PX`. Only a *bed* of unruled cells
is stipple, so the unruled cells are componented and only components of
**≥ 8 cells** are dropped. The plateau is flat from 8 to 64, so it is a shape
rather than a tuning. Free on every score: `land_plot` 0.331 / 0.218,
`building` 0.122, `waterway` 0.582, road cover 0.14, and the counts return to
exactly 888 / 352 / 56 — the gate removes the stipple and nothing else.

### The garden's stream is below this instrument's resolution

Reported as "there truly is a lake and some river on the JB", and that is
right. The measurement above says what can be done about each:

- **The lake is separable** — 0.757, next door to the open river — and is lost
  for a different reason: a compact land polygon covers it and `solid &= ~land`
  removes it, and it carries no `hydrology` label to seed it back.
- **The stream is not separable.** At 0.147 against the stipple's 0.153 it is
  the same number. At this render a 32 source px cell is wider than the stream,
  so the cell is mostly bed. Nothing here can claim the stream without claiming
  the beds, and the blue that used to be there was the beds *with* the stream
  inside them — the right answer for the wrong reason.

### The one open defect, now named: enclosed water inside a land polygon

The garden's lake and the **Arsenal's dry docks, basins and slipways** are the
same failure. Each is drawn as ruled water, each scores like water, and each
sits *inside* a compact block polygon, so `land_mask` subtracts it and the
label seeding cannot reach it. This is what is left of "the Arsenal edge is
still not perfect": the shoreline is now right, and the water drawn **inside**
the yard is called land.

The upgrade is not a threshold: it is to let a strongly-ruled region punch a
hole in the land mask when the polygon containing it is much larger than it —
a dock inside a yard, a lake inside a park. Not built, not measured.

### `--recut` costs the creeks it was not supposed to touch

Worth recording against the default decision: the re-cut's extra land polygons
lie over the narrow water the same pass just rescued.

| window | `--no-recut` | `--recut` |
|---|---:|---:|
| Rach Cầu Chông | **12.6%** | 7.8% |
| Hội An inlet | **6.5%** | 1.5% |
| Arsenal yard as land | 31.2% | **62.8%** |

So the default trades creek coverage for the Arsenal. Both defects are real and
the flag cannot fix both; the enclosed-water upgrade above is what would.

## 2026-09-19 (iii) — four pattern axes on the Arsenal edge, and all four are null

Reported with a zoom on the quay: the water/land boundary is a **straight
orange chord**, which is the block polygon's edge, because `water_region` cuts
the region with `solid &= ~land_mask(...)`. The shoreline is therefore a
polygon edge and not the drawn ripple, and the basins cut into the yard are
inside that polygon, so they are land. Asked directly: *we only use colour —
how about patterns?*

Patterns are already in — `ruling_mask` is a texture measure — so the question
is whether a texture rule can lift the land mask's veto where the pattern says
*water*. Four axes, all measured per 16 px cell on the 1882 sheet, and the two
windows that matter are **arsenal apron** (land, hatched) and **arsenal
basins** (water, the dry docks cut into it):

| axis | apron | basins | verdict |
|---|---:|---:|---|
| coherence (is it ruled) | 0.842 | 0.948 | **null** — both are ruled; the apron *is* hatched |
| washless paper (r−b ≥ 0.10) | 6.2% | 6.7% | **null**, and it admits admin hatch at 76% |
| coherence c128/c16 (does it curve) | 0.55 | 0.23 | separates *these two* and **breaks elsewhere** |
| ink density (sparse vs dense) | 0.078 | 0.021 | **null** — overlapping, and the Champ goes 91% |

The multi-scale ratio is the interesting failure. A hatch is straight at every
scale and a ripple curves, which is true of the creek (0.18) and the lake
(0.12) — but the **open river reads 0.77**, because over 128 render px its
ripple is nearly straight, and the **Hôpital Maritime reads 0.25**, like water.
It would drop the river and admit the hospital: backwards on the two cases that
carry the pass.

Ink density fails for the reason the legend already gave — the hatch classes
are dense *in their swatch* — but on the ground the apron's hatching is broken
by buildings and roads and its per-cell density lands on the ripple's.

**What this closes.** The Arsenal's remaining edge is not separable by any
per-cell texture statistic measured here, and per-cell texture is what a
colour pass can see. What actually distinguishes the basin from the apron is
that the sheet *draws a line around the basin* — the evidence is the outline,
not the fill. Reading an outline is ink geometry, which is C6's standing
conclusion for the within-block split and is SAM2's job, not this pass's.

So the water pass is done at the edge it can reach: the shoreline where the
river's own ripple runs is correct, and the water drawn **inside** a block is
left to the segmenter. Recorded as a null, with the numbers, so the four axes
are not re-attempted as stated.
