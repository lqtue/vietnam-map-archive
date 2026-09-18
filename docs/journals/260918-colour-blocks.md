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
