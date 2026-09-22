# Reading a sheet

An operator guide to `/scan?mode=prepare` and `?mode=text` — where a scanned map becomes searchable
text pinned to real ground.

Audience: whoever is working through the corpus, one sheet at a time. It assumes no knowledge of the
codebase. For the architecture behind it see [`system-guidelines.md`](system-guidelines.md); for the
command-line side see [`pipelines.md`](pipelines.md).

---

## What the page is for

A scanned historical map is a picture. Searching inside it — "find Khánh Hội" — needs every printed
name as **text with a position on the ground**. That is what this page produces, and it takes a
person and a model working together: the model reads fast and is wrong in ways only a human notices,
and a human reads accurately but cannot do 39 sheets by hand.

The output is rows in `ocr_extractions`: one per label, carrying the text, a box in sheet pixels, a
category, a confidence, and — once warped through the sheet's georeference — a longitude and
latitude. Those rows are what make `/catalog` and `/explore` able to search *inside* the maps and
land you on the spot.

## Before you start

Two things must be true, and both are easy to forget.

**1. You are signed in as `admin` or `mod`.** Every API this page uses is role-gated. Signed out,
the page loads and does nothing.

**2. A worker is running.** This is the one that surprises people.

```bash
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --worker $(hostname)
```

Leave that running in its own terminal for the whole session. Nothing in the browser does any
reading. Pressing **Detect** or **Run OCR** writes a row to a queue and returns immediately; the
worker claims the row and does the work.

The reason is the Gemini API key. It lives on your machine and deliberately **never** in the web
app, because the web app's code is public. So the website can only ever *ask* for work. If no worker
is running, jobs sit queued forever — not a bug, and `/admin?tab=status` shows the count under "The
work queue".

**Checkpoint.** The worker prints a line per poll. `queue empty` means it asked and there was
nothing — which is now trustworthy; before September 2026 it also printed that when the network was
down.

## The two modes

They share one image viewer, so you keep the same pan and zoom moving between them. The switcher is
at the foot of the left rail, under the sheet list.

| Mode | Question it answers |
|-----|--------------------|
| **Prepare** (`?mode=prepare`) | What on this sheet should be read, and how finely? |
| **Text** (`?mode=text`) | Did the model read it correctly? |

Segmentation — handing the sheet to MapSAM2 for building footprints — is **not here**. It moved to
`/scan?mode=shapes` in September 2026, with the tracing and the footprint review, because it is
about shapes rather than words.

Pick a sheet from the left rail. It badges each map **Triaged** and **OCR'd**, which is how you find
your place across a long session.

### The four reading jobs

`?mode=text` is four tabs at the foot of the panel, each badged with how many rows it holds. They
divide the sheet's rows between them with nothing left over, so clearing all four clears the sheet.

| Job | What you are checking |
|-----|----------------------|
| **Names** | The names printed on the terrain: streets, places, water, institutions. |
| **Index** | The sheet's own printed tables — the numbered legend and the name list. The canvas frames the table; the rows beside it *are* the table, in the order the paper prints them. |
| **Numbers** | The numerals on the map, against the index that explains them. The **suspect** chip is what the index contradicts. |
| **Other** | Title block, scale bar, stamp, anything that fell off the sheet. |

This replaced a row of category chips. A category cuts across all four jobs: the 1942 sheet's
printed index alone contributed 719 `street` rows and 630 `institution` rows, none of them marks on
the map, all of them sitting in the same chip as the street names you were trying to check.

---

## Triage, step by step

**Since September 2026 the sheet arrives already proposed.** A `layout` job asks
the model where everything is, adopts its own `main_map` answer as the rectangle
to tile, and the tile priorities are computed from the sheet's own ink when the
job runs. So the five steps below are now mostly a *check*: you are looking at a
proposal and agreeing with it, not building one.

What that means in practice:

| The sidebar says | What is true | What you do |
|------------------|--------------|-------------|
| **Proposed — needs a look** | The AI worked out the border. Nobody has agreed. | Glance at it, press **Save triage**. |
| **Accepted** | A person agreed. The batch script will take this sheet. | Nothing. |
| **Layout found no main map** | The model could not find the map body. | Open it — **Suggest** reads the ink instead. |
| **No layout pass yet** | Nothing has run. | `scripts/enqueue_layout_all.mjs`, then a worker. |

Nothing is read, and nothing is paid for, until a person has accepted. That is
the only manual gate left, and it is there because a wrong crop is silent: the
sheet comes back looking merely disappointing.

### 1. Layout — ask what the sheet is made of

Press **Detect**. The model looks at the whole sheet once, at low resolution, and returns labelled
rectangles:

| Category | What it is |
|----------|-----------|
| `sheet` | The whole printed object, paper edge to paper edge |
| `main_map` | The cartographic body — the terrain itself |
| `title` | The cartouche or title block |
| `legend` | The key explaining symbols and hatching |
| `name_list` | An index of street or place names, usually in columns |
| `inset` | A smaller separate map at its own scale |
| `scale_bar`, `north_arrow` | Furniture, worth skipping |
| `stamp` | Archival stamps, accession numbers, pencil shelf marks |

**Why this step exists.** A sheet is not one thing. Without it, the legend gets tiled and read as if
it were terrain — full price per tile to OCR a key — and an alphabetical street index produces
hundreds of labels at ground positions they never had.

`sheet` and `main_map` differ by exactly the furniture, and that difference is the point.

Correct what comes back: click a rectangle to select it, drag the body to move it, pull a corner to
resize. Change its category from the row in the sidebar, delete one with `×`, or **Add region** to
draw one the model missed.

**A dashed edge is the model's proposal; a solid edge is yours.** Correcting a region marks it as
human-decided and it stops being dashed.

**Checkpoint.** On two sheets measured in September 2026 the model scored 8/8 and 7/7 by eye, and
correctly returned *no* `name_list` for a sheet that has none — it does not fill slots to please the
form. But it has only been measured on two sheets. Look at what it gives you.

### 2. Neatline — the rectangle that gets tiled

**Normally already filled in.** The layout job adopts its own `main_map` region
as the crop and stamps `neatline_src: 'main_map'`, so the sidebar tells you the
rectangle came from the model rather than from a person. Check it and move on.

Press **Main map → neatline** if you want to re-adopt it after changing
something. Anything *you* draw is marked as yours and a later layout run will
not overwrite it.

This is better than tracing the printed border by hand, because a legend printed *inside* the border
is inside the border. If there is no layout, **Suggest** reads the sheet's ink profile and finds the
printed rule instead — an independent method that agreed with the model to within 8 pixels on the
1882 cadastral.

**Full image** resets to the whole scan.

### 3. Tiles — how finely to read

The neatline is cut into overlapping squares, one Gemini call each. Click a tile to cycle its
priority:

```
normal  →  low-res (amber)  →  skip (grey)  →  normal
```

Skip the water. Skip the blank margins. Every tile is a paid call.

**The number that matters is how much *ground* one tile covers, not its pixel size.** Measured on
the 1959 sheet, same crop and same rendering, changing only the tile:

| Ground per call | Labels found inside District 4 |
|-----------------|-------------------------------|
| 5.7 km | 1 |
| 2.9 km | 2 |
| 1.4 km | 6 |

A fixed pixel size is a different amount of ground on every sheet — 2048 px is 1.7 km on the 1923
sheet and 5.7 km on the 1959 one. That is why coarse sheets looked empty and got blamed on their
scans. Aim for roughly **1.4 km per call**.

Rendering is *not* the lever. A tile rendered at 1:1 and the same tile upsampled 2× gave
byte-identical output; the scan is the ceiling.

### 4. Save triage — the step that counts

Everything above autosaves to your browser as a draft. **Nothing on a server can see that.**

**Save triage** writes it to the database (`maps.triage`) *and records that you
accepted it* (`validated_at`). That acceptance is what the batch script gates
on — a proposal nobody has looked at is not queued, however confident the model
was. The sidebar shows exactly one primary button at a time, and it reads
**Accept triage** while the sheet is still only proposed.

It writes one key at a time. It used to replace the whole triage object with
whatever the page had in memory, which quietly deleted the printed reference
grid and the crop's provenance along with it.

**Checkpoint.** `/admin?tab=status` → "Sheets a person has accepted" should go
up by one, and "Proposed, waiting to be looked at" down by one.

### 5. Run OCR — queue the work

Queues the job and returns. Watch the worker's terminal, or come back later.

---

## Text, the second mode

Pick a job from the tabs at the foot of the panel; the table lists that job's rows — text, category,
confidence, or for the Index job the printed cell and number. Click a row and its box highlights on
the scan; click a box and the row focuses. Edit text or category inline; it saves when you click
away. Draw a box the model missed with draw mode (`Escape` cancels a draw in progress). Validate or
reject in bulk from the run bar.

Choosing a job also frames the canvas on the part of the sheet that job reads, and over a printed
block it takes the boxes down — there the boxes are the crop each call covered, not the lines it
read (235 rows of the 1942 index share six rectangles), so they hide the table you are there to
read. The left rail turns them back on.

You will need this mode. Two things to expect:

**The `category` field is noisier than the text.** The same sheet run twice disagreed mostly on
classification, and on transcription variants — `KINH BẾN NGHÉ` vs `Kinh Bến Nghé`. Do not read a
single run's small difference as a result.

**Some misreads only become obvious in a list**, not one box at a time: `ARSENAL DE L`,
`HOTEL DU GNRAL`, a bare `Rue` seen fourteen times. `work/ocr/scripts/dictionary.py` writes the
whole corpus as an alphabetical file for exactly this.

When the sheet is right, mark it **reviewed** — one of the three stages a person asserts rather than
the machine deriving.

## Shapes, the third mode

`/scan?mode=shapes&tab=validate` is the equivalent human check for segmentation. Click a proposed
polygon to frame it, drag its vertices when its contour is wrong, change its class when needed, then
approve or reject it. Before the verdict, add one or more **Model feedback** tags and, when a tag
cannot say enough, a note. The tags distinguish errors the tuning pass needs to count — a too-wide
boundary, an unwanted split or merge, a wrong class, map text mistaken for a shape, water/land
confusion, and a missed neighbour. The note records the specific visual rule.

That decision is stored with the polygon's `run_id`: accepted polygons are positive examples;
rejected polygons and their tags are false-positive evidence; an edited approval becomes
`sam-corrected`, preserving both the original model provenance and the corrected contour. Do not
bulk-decide a group when its failure has a diagnosis worth retaining; open one representative result
and record it.

The 1882 colour-pass run `colour-20260919` is already in the Validate queue: 1,443 proposals. Open
`/scan?mode=shapes&tab=validate&map=0e02b9d9-9d40-4cca-8e41-8c8373d54d3b` to review it. The
normalized GeoJSON at
`work/ocr/outputs/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/colour-20260919-normalized/blocks.normalized.geojson`
retains all 1,443 geometries and maps their washes to review classes. Ten source polygons have
interior holes that `pixel_polygon` cannot store; their indices and bounds are in the adjacent
`audit.json`. The queue-safe file in that directory excludes those ten for any future reimport. The
existing run may contain their filled exterior rings, so check those proposals before approving
them.

For a new colour-pass run, use `scripts/import-seg-geojson.mjs` with its raw `blocks.geojson`, a new
run ID, and `--dry` first. The importer maps washes to review classes, retains the cadastral
category, removes only exact duplicate rings, and rejects polygons with holes instead of silently
filling them. It keeps buildings inside parcels as separate proposals and refuses a repeated map/run
pair.

## The pipeline stages

`/scan?mode=shapes` → **Segment** shows where the sheet is:

```
idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported
```

Four of those are **derived** from the sheet's latest job — you cannot set them by hand, and the API
returns 400 if you try. The three a person asserts are `reviewed`, `seg_reviewed` and `exported`,
plus `idle` to start over.

---

## When it goes wrong

### Nothing happens after Detect or Run OCR

No worker is running, or it is running with `--kinds` that exclude what you queued. The default set
is `ocr,join,layout`. Check `/admin?tab=status` → "The work queue".

### A region comes back obviously wrong

Correct it and move on — that is what the step is for. The model proposes; you decide.

### `level0: N of M tiles unreadable` in the worker log

**Take this seriously.** The sheet is assembled from tiles in R2, and some tiles *hang* rather than
fail. In September 2026 a sheet assembled with white holes across 31.8% of its area and the model
still read it correctly — a hole is indistinguishable from blank paper. Any OCR run on that sheet
would have quietly lost a third of its labels.

It now retries, reports coverage and refuses below 90%. That log line means the map's tiles need
re-uploading: re-run its `tile_to_r2` job.

### A sheet reads as nearly empty

Before blaming the scan, check the ground per call (step 3). That was the wrong diagnosis once
already — the 1959 sheet was recorded as needing re-acquisition when it needed smaller tiles.

---

## Doing the whole corpus

Triage a handful by hand first. Then queue the rest:

```bash
# See what it would do, and read the km/call column
node --env-file=.env scripts/enqueue_ocr_all.mjs --dry --tile-metres 1400

# Queue it
node --env-file=.env scripts/enqueue_ocr_all.mjs --tile-metres 1400
```

By default this queues **only** sheets a person has accepted. Two escape
hatches, both worse and both opt-in: `--unvalidated` queues proposals nobody has
looked at, and `--untriaged` queues sheets with no crop at all, letting the
scout pass guess — the oldest behaviour, and the worst.

The `--dry` line now tells you which state every sheet is in, so run it first:

```
39 georeferenced · 0 accepted · 37 proposed (not accepted) · 0 no main_map ·
2 no layout pass · 6 already OCR'd · 0 in flight → 0 to queue (dry run)
```

That reads: 37 sheets are one glance each from being queueable, and 2 need a
layout pass. The whole-corpus order is therefore:

```bash
# 1. Propose everything (cents for the corpus — one call per sheet)
node --env-file=.env scripts/enqueue_layout_all.mjs
python work/worker/vma_worker.py --worker $(hostname)   # drains it

# 2. Accept them at /scan?mode=prepare — the only manual step

# 3. Queue the reading
node --env-file=.env scripts/enqueue_ocr_all.mjs --tile-metres 1400
```

`--tile-metres` is opt-in and only ever makes a tile **finer**, never coarser: a saved triage
carries the tile size *you* chose, and a fixed ground target once coarsened the 0.34 m/px 1882
cadastral and cost it labels.

Expect roughly **+19% corpus-wide** from ground-referenced tiling, concentrated in the coarse
sheets. Sheets already under ~1.5 km per call gain nothing.

Budget: about **$31–63** for the whole corpus on `gemini-3.8-flash`, measured at 5,156 input / 1,810
output tokens per call and 30–60 calls per sheet. (**Corrected 2026-09-19.** This line read $12–24,
which is the same per-call token figures costed on the *visible* `output_tokens` field. Gemini bills
`total_tokens − input_tokens`, thinking included, ~3.5–4× that — see `docs/pipelines.md` §Cost.
`docs/ROADMAP.md` already carried the corrected range; this file did not.) Cost is not the
constraint; unattended quality is. Set `GEMINI_API_KEYS` with a second key before a long run — the
client rotates when one hits its daily cap.

---

## The habit worth keeping

Every defect found in this pipeline during the September 2026 pass returned *plausible output while
dropping data*:

- `fetch_crop` asked for image regions the tile server cannot serve — OCR was dead for all 39
  georeferenced sheets, and looked like empty maps.
- The layout pass never passed its prompt or its schema, so it returned no regions — and looked like
  the model declining.
- Tiles assembled with a third of the sheet missing, and the model read the rest correctly.
- The worker reported "queue empty" when the network was down.
- Every queued job silently downsampled 2.34×, for months.
- The batch script gated on a saved neatline. **No sheet in the corpus had
  one** — 101 georeferenced maps, zero neatlines — so its default mode queued
  nothing at all and exited reporting success, while 37 sheets already carried
  the `main_map` region it would have preferred anyway.
- The OCR upsert key ignored where a label was, so eight distinct `Rue` labels
  in one tile became one row, and the count returned was the count *after* the
  loss.

None of these were found by reading the code. All were found by **measuring something that already
appeared to work.** When a sheet looks finished, check a number.
