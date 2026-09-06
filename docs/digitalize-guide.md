# Digitalize: reading a sheet

An operator guide to `/scan?mode=triage` — the page where a scanned map becomes searchable text pinned to real ground.

Audience: whoever is working through the corpus, one sheet at a time. It assumes no knowledge of the codebase. For the architecture behind it see [`system-guidelines.md`](system-guidelines.md); for the command-line side see [`pipelines.md`](pipelines.md).

---

## What the page is for

A scanned historical map is a picture. Searching inside it — "find Khánh Hội" — needs every printed name as **text with a position on the ground**. That is what this page produces, and it takes a person and a model working together: the model reads fast and is wrong in ways only a human notices, and a human reads accurately but cannot do 39 sheets by hand.

The output is rows in `ocr_extractions`: one per label, carrying the text, a box in sheet pixels, a category, a confidence, and — once warped through the sheet's georeference — a longitude and latitude. Those rows are what make `/archive` and `/explore` able to search *inside* the maps and land you on the spot.

## Before you start

Two things must be true, and both are easy to forget.

**1. You are signed in as `admin` or `mod`.** Every API this page uses is role-gated. Signed out, the page loads and does nothing.

**2. A worker is running.** This is the one that surprises people.

```bash
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --worker $(hostname)
```

Leave that running in its own terminal for the whole session. Nothing in the browser does any reading. Pressing **Detect** or **Run OCR** writes a row to a queue and returns immediately; the worker claims the row and does the work.

The reason is the Gemini API key. It lives on your machine and deliberately **never** in the web app, because the web app's code is public. So the website can only ever *ask* for work. If no worker is running, jobs sit queued forever — not a bug, and `/admin?tab=status` shows the count under "The work queue".

**Checkpoint.** The worker prints a line per poll. `queue empty` means it asked and there was nothing — which is now trustworthy; before September 2026 it also printed that when the network was down.

## The three tabs

All three share one image viewer, so you keep the same pan and zoom as you move between them.

| Tab | Question it answers |
|-----|--------------------|
| **Triage** | What on this sheet should be read, and how finely? |
| **OCR Review** | Did the model read it correctly? |
| **Segmentation** | Hand off to MapSAM2 for building footprints |

Pick a sheet from the floating map picker. It badges each map **Triaged** and **OCR'd**, which is how you find your place across a long session.

---

## Triage, step by step

The sidebar is five numbered steps. Work them in order; each one narrows what the next has to do.

### 1. Layout — ask what the sheet is made of

Press **Detect**. The model looks at the whole sheet once, at low resolution, and returns labelled rectangles:

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

**Why this step exists.** A sheet is not one thing. Without it, the legend gets tiled and read as if it were terrain — full price per tile to OCR a key — and an alphabetical street index produces hundreds of labels at ground positions they never had.

`sheet` and `main_map` differ by exactly the furniture, and that difference is the point.

Correct what comes back: click a rectangle to select it, drag the body to move it, pull a corner to resize. Change its category from the row in the sidebar, delete one with `×`, or **Add region** to draw one the model missed.

**A dashed edge is the model's proposal; a solid edge is yours.** Correcting a region marks it as human-decided and it stops being dashed.

**Checkpoint.** On two sheets measured in September 2026 the model scored 8/8 and 7/7 by eye, and correctly returned *no* `name_list` for a sheet that has none — it does not fill slots to please the form. But it has only been measured on two sheets. Look at what it gives you.

### 2. Neatline — the rectangle that gets tiled

Press **Main map → neatline** to adopt the model's answer.

This is better than tracing the printed border by hand, because a legend printed *inside* the border is inside the border. If there is no layout, **Suggest** reads the sheet's ink profile and finds the printed rule instead — an independent method that agreed with the model to within 8 pixels on the 1882 cadastral.

**Full image** resets to the whole scan.

### 3. Tiles — how finely to read

The neatline is cut into overlapping squares, one Gemini call each. Click a tile to cycle its priority:

```
normal  →  low-res (amber)  →  skip (grey)  →  normal
```

Skip the water. Skip the blank margins. Every tile is a paid call.

**The number that matters is how much *ground* one tile covers, not its pixel size.** Measured on the 1959 sheet, same crop and same rendering, changing only the tile:

| Ground per call | Labels found inside District 4 |
|-----------------|-------------------------------|
| 5.7 km | 1 |
| 2.9 km | 2 |
| 1.4 km | 6 |

A fixed pixel size is a different amount of ground on every sheet — 2048 px is 1.7 km on the 1923 sheet and 5.7 km on the 1959 one. That is why coarse sheets looked empty and got blamed on their scans. Aim for roughly **1.4 km per call**.

Rendering is *not* the lever. A tile rendered at 1:1 and the same tile upsampled 2× gave byte-identical output; the scan is the ceiling.

### 4. Save triage — the step that counts

Everything above autosaves to your browser as a draft. **Nothing on a server can see that.**

**Save triage** writes it to the database (`maps.triage`), and that is what the batch script reads. It is a deliberate assertion: *this sheet is triaged*. The sidebar shows exactly one primary button at a time — Save while the triage is unsaved, Run once it is on the server.

**Checkpoint.** `/admin?tab=status` → "Sheets triaged by a person" should go up by one.

### 5. Run OCR — queue the work

Queues the job and returns. Watch the worker's terminal, or come back later.

---

## OCR Review, the second tab

The table lists every extraction — text, category, confidence. Click a row and its box highlights on the scan; click a box and the row focuses. Edit text or category inline; it saves when you click away. Draw a box the model missed with draw mode (`Escape` cancels a draw in progress). Validate or reject in bulk from the run bar.

You will need this tab. Two things to expect:

**The `category` field is noisier than the text.** The same sheet run twice disagreed mostly on classification, and on transcription variants — `KINH BẾN NGHÉ` vs `Kinh Bến Nghé`. Do not read a single run's small difference as a result.

**Some misreads only become obvious in a list**, not one box at a time: `ARSENAL DE L`, `HOTEL DU GNRAL`, a bare `Rue` seen fourteen times. `work/ocr/scripts/dictionary.py` writes the whole corpus as an alphabetical file for exactly this.

When the sheet is right, mark it **reviewed** — one of the three stages a person asserts rather than the machine deriving.

## The pipeline stages

The bottom bar shows where the sheet is:

```
idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported
```

Four of those are **derived** from the sheet's latest job — you cannot set them by hand, and the API returns 400 if you try. The three a person asserts are `reviewed`, `seg_reviewed` and `exported`, plus `idle` to start over.

---

## When it goes wrong

### Nothing happens after Detect or Run OCR

No worker is running, or it is running with `--kinds` that exclude what you queued. The default set is `ocr,join,layout`. Check `/admin?tab=status` → "The work queue".

### A region comes back obviously wrong

Correct it and move on — that is what the step is for. The model proposes; you decide.

### `level0: N of M tiles unreadable` in the worker log

**Take this seriously.** The sheet is assembled from tiles in R2, and some tiles *hang* rather than fail. In September 2026 a sheet assembled with white holes across 31.8% of its area and the model still read it correctly — a hole is indistinguishable from blank paper. Any OCR run on that sheet would have quietly lost a third of its labels.

It now retries, reports coverage and refuses below 90%. That log line means the map's tiles need re-uploading: re-run its `tile_to_r2` job.

### A sheet reads as nearly empty

Before blaming the scan, check the ground per call (step 3). That was the wrong diagnosis once already — the 1959 sheet was recorded as needing re-acquisition when it needed smaller tiles.

---

## Doing the whole corpus

Triage a handful by hand first. Then queue the rest:

```bash
# See what it would do, and read the km/call column
node --env-file=.env scripts/enqueue_ocr_all.mjs --dry --tile-metres 1400

# Queue it
node --env-file=.env scripts/enqueue_ocr_all.mjs --tile-metres 1400
```

By default this queues **only** sheets with a saved triage. `--untriaged` includes the rest, which fall back to letting the scout pass guess the neatline — the old behaviour, and worse.

`--tile-metres` is opt-in and only ever makes a tile **finer**, never coarser: a saved triage carries the tile size *you* chose, and a fixed ground target once coarsened the 0.34 m/px 1882 cadastral and cost it labels.

Expect roughly **+19% corpus-wide** from ground-referenced tiling, concentrated in the coarse sheets. Sheets already under ~1.5 km per call gain nothing.

Budget: about **$12–24** for the whole corpus on `gemini-3.8-flash`, measured at 5,156 input / 1,810 output tokens per call and 30–60 calls per sheet. Cost is not the constraint; unattended quality is. Set `GEMINI_API_KEYS` with a second key before a long run — the client rotates when one hits its daily cap.

---

## The habit worth keeping

Every defect found in this pipeline during the September 2026 pass returned *plausible output while dropping data*:

- `fetch_crop` asked for image regions the tile server cannot serve — OCR was dead for all 39 georeferenced sheets, and looked like empty maps.
- The layout pass never passed its prompt or its schema, so it returned no regions — and looked like the model declining.
- Tiles assembled with a third of the sheet missing, and the model read the rest correctly.
- The worker reported "queue empty" when the network was down.
- Every queued job silently downsampled 2.34×, for months.

None of these were found by reading the code. All were found by **measuring something that already appeared to work.** When a sheet looks finished, check a number.
