# 260918 — the sheet knows where its own blocks are

**Date:** 2026-09-18 · **Severity:** medium · **Component:** seg / Track C · **Status:** plan, one tile measured, nothing built

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

**Not established.** The value-split probe run today was confounded: the dark
tail of the red family mixes building fill with the black outlines and the
lettering, so `V < T` selected all three. It needs a test that removes ink
first, and it has not had one.

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
- **P3 — the two-reds test**, ink removed first. **Exit:** either a `building`
  IoU against the 17 building traces that beats 0.160, or a recorded null.
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

- **The ground truth has grown to 118 rows** — building 89 · land_plot 24 ·
  road 3 · waterway 2 — where `EVAL-BASELINE.md` and
  `docs/worked-example-1882.md` both say 46. Those sections are comparing
  against a different truth set than anything measured today.
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
