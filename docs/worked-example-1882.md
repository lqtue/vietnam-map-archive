# One sheet, all the way through

A record of taking a single map from scan to exported geometry, with the number
each stage actually produced. Written 2026-09-16 against production.

Its purpose is not to describe the pipeline — `docs/pipelines.md` and
`docs/digitalize-guide.md` do that. It is to say what happens when you run the
whole thing on one sheet, because until this week **no sheet had ever been
through all of it**, and four of the stages had never completed once.

---

## The sheet

**Plan Cadastral de la ville de Saigon, Cochinchine Française (1882)** ·
`0e02b9d9-9d40-4cca-8e41-8c8373d54d3b` ·
[`/catalog/plan-cadastral-de-la-ville-de-saigon-cochinchine-francaise`](https://maparchive.vn/catalog/plan-cadastral-de-la-ville-de-saigon-cochinchine-francaise)
· source [Gallica btv1b52508901z](https://gallica.bnf.fr/ark:/12148/btv1b52508901z)

12102 × 8982 px, **0.34 m/px**. Chosen because it is the only sheet where every
stage already had material:

- the finest scan in the corpus, and a *cadastral* — plots are drawn, which is
  what a footprint pass is for
- the only sheet in the archive carrying polygons at all (46, hand-traced by a
  volunteer in April 2026)
- the most-reviewed sheet: 152 of its 177 `v1b` labels have a human verdict
- the anchor year of the District 4 series (1882 · 1895 · 1923 · 1942 · 1959 ·
  1968)

---

## The georeference, checked rather than assumed

10 GCPs, Allmaps `helmert`. Fitted independently from the annotation rather
than trusting the stored figure:

| model | result |
|---|---|
| similarity, no y-flip | RMSE 989 m — the wrong model, listed only because it is what you get if you forget the image axis points down |
| **similarity + y-flip** (what Allmaps applies) | **0.3426 m/px, rotation 89.65°, RMSE 11.3 m, worst point 23.0 m** |
| affine, 6 dof | 0.3417 / 0.3445 m/px, RMSE 10.6 m, worst 17.4 m |

Three things follow.

**The sheet is rotated ~90°.** 12102 × 8982 px is 4.14 × 3.09 km of ground,
while `maps.bbox` reads 3.06 × 4.19 km — swapped, and consistent. Any naive
pixel-to-ground check on this sheet looks wrong until you notice that.

**Affine barely beats helmert** (10.6 m against 11.3 m). There is no shear and
no differential scale, so the scan is undistorted and the 1882 survey is
internally consistent. Helmert is the right model; adding control points buys
very little.

**11 m RMSE is the floor on every ground claim made from this sheet.** A Saigon
cadastral plot is roughly 20–40 m across, so a label can land one plot off. It
does not affect the label↔footprint join, which is pure pixel space, but it
bounds anything compared against the modern city.

`ocr_extractions.geom_rmse` is **16.50 for all 499 rows** — it is a per-*map*
constant, not a per-point residual, and cannot be used to weigh an individual
label.

## The crop

`maps.triage.neatline` is `[459, 413, 11073, 7913]`, `neatline_src: human`.
Worth recording because three independent methods agree on it:

| method | origin, size |
|---|---|
| Gemini layout pass (`main_map` region) | 447, 431, 11085, 7886 |
| ink-profile detector (`suggestTriage.ts`) | 443, 423, 11093, 7932 |
| the human who accepted it | 459, 413, 11073, 7913 |

Two unrelated automatic methods within 8 px of origin, and the person landed
between them. The layout pass returned 6 regions — `sheet`, `main_map`,
`title`, `legend`, `scale_bar`, `stamp` — and correctly returned **no**
`name_list`, because this sheet has none.

---

## The chain, with its numbers

### Read — `ocr`

Three runs exist on this sheet and **they are not equivalent**:

| run | rows | human verdict | date |
|---|---|---|---|
| `post0910` | 287 | **0** | 2026-09-10 |
| `2026-09-04T0527` | 35 | 1 | 2026-09-04 |
| `v1b` | 177 | **84 validated · 68 rejected · 25 pending** | 2026-05-03 |

A trap worth naming, because it produced a wrong number in the first draft of
this file: **`ocr_extractions.text_validated` is a text column, not a boolean.**
It holds the human's corrected string, and is null when nobody retyped the text.
Counting `text_validated is not null` therefore counts *corrections*, not
verdicts. The verdict is `status` — `validated | rejected | pending`. The seed
loader for segmentation takes `status neq.rejected`, which is why 109 seeds
reach SAM2 rather than 84.

`v1b` is canonical for this sheet: it is the only one anybody has checked.
Every later stage is pinned to it explicitly, because nothing derives that by
itself (see *The newest run is not the reviewed run* below).

### Warp — `warp`

All 499 rows carry `geom`. `geom_src` `245d98f7f8d61572` is a hash of the GCP
set, so a row whose georeference has since moved is queryable rather than
silently stale.

### Trace and review — `/scan?mode=shapes`

46 polygons, `source: volunteer`, all **approved** 2026-09-16 — the first
footprints in the archive ever to reach that state. `land_plot` 24 ·
`building` 17 · `road` 3 · `waterway` 2.

### Join — `join_labels.py`

```bash
python3 work/ocr/scripts/join_labels.py 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b v1b
```

**19 of 177.** The first `join` ever to complete in this project.

What it linked, unedited:

```
ANCIEN CAMP DES LETTRES        [institution] → land_plot "Ancien Camp des Lettres"
COLLÈGE D'ADRAN                [institution] → building  "College D'Adran"
JUSTICE DE PAIX                [institution] → land_plot "Justice de Paix"
DIRECTION DE L'INTÉRIEUR       [institution] → land_plot "Direction de L'Intrerieur"
DIRECTION DES TRAVAUX PUBLICS  [institution] → land_plot "Directeur des Travaux Public"
INSTITUTION MUNICIPALE         [institution] → land_plot "Institution Municipal"
HOTEL DU PROC. GÉNÉRAL         [building]    → land_plot "Hotel du Proctor Generale"
MARCHÉ CENTRAL                 [building]    → land_plot "Marche Central"
JARDIN BOTANIQUE               [place]       → land_plot "Jardin Botanique"
PRISONS                        [institution] → land_plot "Prisons"
CONSEIL DE GUERRE HYDROGRAPHIE [institution] → building  "Conseil de Guerre Hydrographie"
Boulevard de Canton            [street]      → road      "Boulevard de Canton (No 1)"
POUDRIÈRE / CASERNES /
CHAMP DE MANOEUVRES            [various]     → land_plot "Citadelle"
JARDIN DE LA VILLE             [place]       → land_plot (unnamed)
POSTE DE POLICE                [institution] → land_plot (unnamed)
Rue Ste Catherine              [street]      → land_plot (unnamed)
```

**14 of 19 are exact name agreement between two sources that never saw each
other** — Gemini reading the ink in May, a volunteer tracing shapes in April.
That is the corroboration the "named institutions as control points" lead in
`ROADMAP.md` was looking for, now measured rather than asserted.

Three observations worth carrying:

1. **The join corrects the volunteer as often as the reverse.** `Direction de
   L'Intrerieur`, `Directeur des Travaux Public`, `Institution Municipal`,
   `Hotel du Proctor Generale` are all volunteer misspellings that OCR gets
   right. Nobody designed the join as a two-way QA pass; it is one.
2. **It names unnamed polygons.** Four links landed on polygons carrying
   `name: null`. That is the pipeline's actual product working.
3. **The granularity ceiling is visible and benign.** `POUDRIÈRE`, `CASERNES`
   and `CHAMP DE MANOEUVRES` all land in one `Citadelle` plot. Correct
   containment; no finer polygon exists yet.

### Segment — `seg`

```bash
node --env-file=.env scripts/enqueue_seg.mjs --map-id 0e02b9d9-…   # seeds off v1b
# a Colab T4 running work/MapSAM2/vma_seg_worker.ipynb claims it
```

**72 polygons in 10 min 31 s** — the first `seg` job ever to complete in this
project. Prompted mode off `v1b`, LoRA checkpoint `epoch_010.pth`, written
through `/api/pipeline/results` on a worker token with no service key on the GPU
machine.

**All 72 carry a name.** A seeded polygon knows its own toponym at birth, which
is the entire reason for running OCR before segmentation rather than after. It
also found features no volunteer had traced: `MARCHÉ DE CẦU ÔNG LÃNH`,
`COLLÈGE CHASSELOUP LAUBAT`, `Vge de Vĩnh Hội` — that last one in District 4,
the series this sheet anchors.

Confidence (SAM2 predicted IoU) has a median of 0.946 and a long bad tail:
`CIMETIÈRE EUROPÉEN` 0.0027, `NOUVEAU PALAIS DE JUSTICE` 0.0054,
`JARDIN DE LA VILLE` 0.0109. Areas run 95 – 7,766 m², median 2,036 — these are
blocks and plots, not buildings, though every row is written
`feature_type: building` because the seed's category never reaches the row.

### Join, again — and why the bigger number is the weaker one

```bash
python3 work/ocr/scripts/join_labels.py 0e02b9d9-… v1b seg-20260916T1632-0e02b9d9
```

**68 of 177**, against 19 before. The rate went 11% → 38%. That is the number
not to quote on its own.

```
68 links = 60 to sam-auto polygons + 8 to volunteer polygons
63 of 68 have label text identical to polygon name
```

**The 63 is circular.** The polygon's name came *from* the label, through the
seed that prompted it; the same string is round-tripping. It is not two sources
agreeing.

And the number that carried the evidence went **down**. The 19 earlier links
were all to independently hand-traced polygons. Only **8** still are: the
machine polygons are tighter (median 2,036 m² against the volunteer land plots),
so `join_labels`' smallest-containing rule prefers them, and 11 labels that used
to corroborate a human's tracing now corroborate a machine's own seed.

Nor does containment test the mask much. `_run_prompted`'s own docstring records
that a box-prompted mask tends to redraw its prompt box — median IoU 0.87
against the seed in the 0.90–1.00 band. A mask that reproduces its prompt always
contains the label's centre.

So the honest reading of the two runs together: **the archive gained 49 links and
lost 11 pieces of independent evidence.** Both are true and only one is visible
in the headline.

### Export

```
GET /api/export/footprints?map_id=0e02b9d9-…
→ 46 features, 28 with a name, first vertex [106.70214, 10.77206]
```

Also a first: with `status=approved` as its default filter and nothing in the
archive ever reaching `approved`, this endpoint had returned an empty
collection since it was written.

---

## What broke, and how each failure looked

Every defect found while running this chain returned **plausible output while
dropping data**, or refused work while looking like something else. That is the
habit `docs/digitalize-guide.md` already names, and it held again four times.

**1. The newest run is not the reviewed run.** `join_labels.py` pins the most
recent OCR run when it is not told which to use. On this sheet that is
`post0910`, which has **zero** validated labels, while all 94 sit in the oldest
run. Meanwhile `enqueue_seg.mjs` picks the run with the most validated labels —
correctly, it wants human-checked boxes. So the two halves of the pipeline
would have run on **disjoint label sets** and nothing would have said so. Run
against `v1b` instead, the join rate doubles: 9/287 → 19/177.

**2. Every queued `seg` job would have died on argparse.** `seg_argv` passes
`--run-id` whenever the payload carries one, and `enqueue_seg.mjs` always mints
one — but `inference_tiles_as_video.py` had no such argument. Invisible because
no `seg` job had ever completed. Fixed `7cda3704`; the run id now also reaches
`footprint_submissions` instead of being derived from the output filename,
which had labelled every run `"footprints"`.

**3. The review queue could not approve anything** (`7942b1ec`, migration 090).
Three faults in one path:

- Two definitions of the queue — the list selects `status='submitted'`, the RPC
  updated only `status='needs_review'`. Every row a reviewer could see was a row
  the RPC refused, answering `409 That footprint is not awaiting review` on a
  polygon it had just drawn for review.
- `submitted` was the *approving verdict*, so approval left the row in the state
  it was already in. Nothing could reach `approved`.
- The list showed one inbox, not the queue. MapSAM2 writes `needs_review`, so
  the first seg run's output would have been invisible there too.

**4. Seedless tiles were fetched and encoded anyway.** `_run_prompted` called
`predictor.set_image()` — the ViT image-encoder forward pass, the most expensive
operation in a run — before checking whether it had any seeds, and `infer_tile`
had already fetched the IIIF crop by then. With 109 seeds spread over 154 tiles,
most of the run was downloading and encoding tiles it would never prompt. The
pass is I/O bound, not GPU bound: 4.1 s per tile, of which roughly 0.2 s is the
GPU. Guarded in both places; 59 of 154 tiles carry a seed, so the next run on
this sheet should take about 4 minutes rather than 10.5.

**5. A run printed nothing for ten minutes.** The worker used
`subprocess.run(capture_output=True)`, which reads nothing until the child exits,
so a long pass showed its command line and then silence — indistinguishable from
a wedged process, and one healthy run was nearly killed for looking dead. It
streams now, keeping the last 200 lines for the job row.

**6. A job that exhausts `attempts` while `running` becomes unclaimable, and
blocks its sheet forever.** `claim_job`'s stale-reclaim branch requires
`attempts < max_attempts`, and `idx_pipeline_jobs_one_live` makes
`(kind, map_id)` unique across queued/claimed/running — so the sheet can never be
re-queued, with no error anywhere and `/admin?tab=status` showing it in flight
indefinitely. Recovered by hand with a
`POST /api/pipeline/results {job_id, status:"failed"}`. Migration 077's own
header records this happening once before to an OCR job, which makes it a
pattern rather than an incident. **Still open.**

**7. The existing write smoke asserted the bug.** It approved a footprint and
checked `status === 'submitted'` — exactly the no-op. A green gate over a
feature that could not work, for the fourth time this month.

---

## What this does *not* establish

- **Volume.** 118 polygons over a 12102 × 8982 sheet is still thin, and the
  machine's 72 came from 109 seeds — so the ceiling is the OCR pass, not the
  segmenter. A sheet is only as segmentable as it is readable.
- **Segmentation quality.** The LoRA checkpoint was fine-tuned on *these* 46
  polygons on *this* sheet. Running it back on 1882 legitimately produces
  polygons for this example, but measures nothing. An honest number needs a
  different sheet — 1923 or 1942, both already OCR'd.
- **Independence.** The archive has more links than it did and less independent
  evidence: 19 corroborations by an unrelated human tracing became 8. Any future
  claim about agreement has to count only the volunteer polygons.
- **Generality.** One sheet, and an unusually good one: undistorted, finest
  scan in the corpus, no printed name index. A sheet with a street directory
  (1942 contributed 719 `street` rows from its printed index alone) behaves
  differently.
- **The `pool = preferred or containing` fallback** in `join_labels.py:113`
  links a label to *any* containing polygon when none of the wanted level
  contains it, and marks nothing. With three road polygons on the sheet it
  fires often — `N° 25` → `Citadelle`. Harmless at scale, misleading here.

## Reproducing it

```bash
# 0. the georeference, checked
#    (the fit above is in scratch; the stored figure is maps → annotation_url)

# 1. read — already done; v1b is canonical for this sheet
node --env-file=.env scripts/enqueue_ocr_all.mjs --dry --tile-metres 1400

# 2. shapes — a Colab GPU session as a worker
#    work/MapSAM2/vma_seg_worker.ipynb, then from here:
node --env-file=.env scripts/enqueue_seg.mjs --map-id 0e02b9d9-… --dry

# 3. review at /scan?mode=shapes&tab=validate
#    click / ctrl-click / shift-click, then Approve N

# 4. join, pinned to the reviewed run on both sides
python3 work/ocr/scripts/join_labels.py 0e02b9d9-… v1b <seg-run-id>

# 5. export
curl 'https://maparchive.vn/api/export/footprints?map_id=0e02b9d9-…'
```
