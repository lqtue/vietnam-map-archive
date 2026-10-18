# Ontology — the words VMA uses for what it holds

For anyone naming a thing in code, a doc or the paper. Kind: guide. One line per term: what it
is, and where it lives. Why each one exists, with counts and gaps, is in the
[knowledge system plan](plans/knowledge-system-plan.md) §2–§7. Open work on each layer is in its §9.

Two parts. **Built** is what the database holds today (production head: migration 124).
**Proposed** is under discussion: nothing there is decided, and its names are placeholders.
Names may still change after a standards crosswalk (PROV-O, LRMoo, Linked Places).

## Where this page sits

The ontology is the top of four levels. Each level implements the one above it:

| Level | Says | In VMA |
| --- | --- | --- |
| **Ontology** (conceptual) | what kinds of things exist and how they relate | this page |
| **Schema** (logical) | how they are stored: tables, columns, keys | `supabase/migrations/` |
| **Storage** (physical) | where the bytes sit | Postgres, R2 tiles, annotation JSON |
| **Data** (instances) | the actual rows: this sheet, this label | production |

Below all four is the world: the paper sheet in a holder's drawer, the street it shows.
The "Lives in" column on this page maps each term to its place in the schema. A term with
no table, or a table with no term, means one of the two is wrong.

VMA was built bottom-up: the data taught us the terms (`collection` turned out to mean three
things). From here, new work goes top-down:

1. **A new thing gets its term here first**, then its migration.
2. **An old gap gets fixed when a bet touches it**, not in a redesign.
3. **CI checks every table is named on this page** (`scripts/check_workspace_layout.py`).

How a term becomes schema:

| The ontology says | The schema does | Example |
| --- | --- | --- |
| X is a kind of thing | a table, with a stable key | series → `series` |
| X has property P | a column | a map's status → `maps.status` |
| every X has exactly one Y | a foreign key on X | a map's series → `maps.series_id` |
| an X has many Y, and a Y many X | a join table | printings and holders |
| P takes only these values | a check constraint or lookup table | the seven map types |
| we must know who said so, and when | provenance columns | `georef_versions` origin and method |
| this is proposed, not decided | a review state | `ocr_labels.review_status` |

## The layers

Six layers, 0–5. Each rests on the one below, and an error low in the stack spreads upward
without any sign, so fix the lowest broken layer first. Two more groups sit outside the stack.

| Layer | Holds |
| --- | --- |
| **0. Sources and surveys** | providers, surveys, cells, printings, holders, rights, period texts |
| **1. Holdings** | the map row, its scans and tiles, its address |
| **2. Placement** | georeference versions, GCPs, transformation, masks, fit |
| **3. Readings** | OCR labels, polygons, legend, triage regions; each with its run or reviewer |
| **4. Entities and vocabularies** | place-name groups, attested spellings, street-name pairs, classification terms |
| **5. Assertions and studies** | claims, evidence, the figures a study cites |
| *Surfaces* | pages and apps that read the layers: search, Walk, stories, staff views |
| *Outside the model* | operations, CI, the language of the UI |

## Built

### 0. Sources and surveys

| Term | What it is | Lives in |
| --- | --- | --- |
| **series** (survey) | One producer, scale and sheet grid. Its cells exist whether we hold them or not. | `series` (mig 105); `maps.series_id` |
| **cell** | One position in a series grid | `series_cells`, keyed `(series_key, sheet_number)`; `series_id` (mig 105) |
| **printing** | One impression or revision of a cell, as a bibliographic fact. Reviewed, never inferred from year or edition. | `sheet_printings` (mig 106); `printing_id` on `maps` and `cell_printings` |
| **holder** | Who keeps the physical sheet or the scan | `cell_printings.institution`; `maps.holding_institution` |
| **discovery candidate** | A sheet found at a provider but not yet ingested | `scout_candidates` |

### 1. Holdings

| Term | What it is | Lives in |
| --- | --- | --- |
| **map** (scan workspace) | One digitised copy of a sheet, or one E/W half, plus its processing. Its address is its `slug`. | `maps` |
| **image** | A scan or IIIF service for a map, with its content role | `map_images`, plus R2 tiles |
| **map type** | One of seven primary types, with subjects and depicted state on separate axes | `maps.map_type` and friends (mig 116) |
| **region** | Today's province(s) a map covers. A locator, not what the sheet's era called the place. | `maps.region`, `region_2025`, `regions` (mig 109, 111) |
| **status** | draft, public, featured or archived. Archiving keeps identity and history. | `maps.status` (mig 107) |
| **old address** | A slug a map once answered on; it 301s to the current one | `map_slug_aliases` (mig 088) |

### 2. Placement

| Term | What it is | Lives in |
| --- | --- | --- |
| **georeference version** | One set of control points and a transformation for a map, with who made it, how, and from what | `georef_versions` (mig 103, 118); the JSON in storage |
| **GCP** | A control point: scan pixel → ground coordinate | inside the annotation JSON |
| **transformation** | polynomial, helmert or thin-plate spline | inside the annotation JSON |
| **georef mask** | The part of the scan that is warped onto the map | the annotation's SvgSelector |
| **neatline** | The printed frame of the map face | `maps.triage.neatline` |
| **fit** (RMSE) | How far the points miss after the transformation. Always name which measure. | `geom_rmse` on derived rows |

### 3. Readings

| Term | What it is | Lives in |
| --- | --- | --- |
| **run** | One pass of a machine reader over a map; groups its output | `run_id` on each row |
| **label** | A piece of printed text read from a scan, with a category and review state | `ocr_labels` |
| **text group** | Labels joined into one reading, in click order; the originals stay | `ocr_labels.text_group_id` (mig 112) |
| **polygon** | A traced shape (block, water, building…) | `footprints` |
| **pin** | A point placed on the scan by pixel | `label_pins` |
| **layout regions** | The map face, legend, title and margins as separate boxes | `maps.triage.regions` |
| **legend entry** | A numbered legend item and where it is on the map | `maps.label_config.legend`; `legend_finds` (mig 119) |

### 4. Entities and vocabularies

| Term | What it is | Lives in |
| --- | --- | --- |
| **place-name group** | Spellings that normalise to the same key. Groups text; does not prove one place. | `place_names` view |

### 5. Assertions and studies

| Term | What it is | Lives in |
| --- | --- | --- |
| **review task** | One kind of review question, with the seed and blind share that decide who sees a proposal | `review_tasks` (mig 122) |
| **review item** | What a reviewer judges: what both arms see, the machine's proposal, a hash of exactly what is judged | `review_items` (mig 122) |
| **review event** | One verdict or undo: who, when shown, when decided, whether the proposal was shown. Insert-only. | `review_events` (mig 122) |

Studies cite figures from journals and the paper's number ledger (`paper/CLAUDE.md`).

### Surfaces

| Term | What it is | Lives in |
| --- | --- | --- |
| **user layer** | A contributor's own set of annotations | `user_layers` |
| **story** | A guided sequence of stops over the maps | `stories` |
| **story point** | A located stop in a story | `story_points` |

### Outside the model

| Term | What it is | Lives in |
| --- | --- | --- |
| **job** | One queued pipeline task, claimed and run by a worker | `pipeline_jobs` (mig 053) |
| **worker key** | The credential a worker claims jobs with | `worker_keys` |
| **review mark** | A person saying a pipeline stage is done for a map. The seed of the proposed *decision* (below). | `map_review_marks` |
| **profile** | A signed-in person and their role | `profiles` |
| **quota** | How much a contributor may write per period | `contribution_quotas` (mig 097) |
| **favorite** | A map a person saved | `favorites` |
| **map view** | One anonymous open of a map, counted for usage | `map_views` |

## Words to avoid

| Don't say | Say | Why |
| --- | --- | --- |
| collection | series, holder or set | It mixed all three. `maps.collection` is display text only. |
| mask (alone) | georef mask, neatline or layout regions | Three different things |
| validated (for a georeference) | reviewed by whom, when | `sync-georef` copies without review |

## Proposed, not built

Under discussion. Names are placeholders until reviewed.

| Idea | Points to |
| --- | --- |
| A **set**: a curated group of sheets (the Saigon city plans, a story's sheets) | knowledge plan §7 |
| Place, name and feature as three separate things (evidence-chain calls the first a "subject") | [evidence chain](plans/evidence-chain-plan.md) |
| A **decision** record for every review: who, what, verdict, seconds. Review-page tasks have it (review event, §5); the in-app tools and `map_review_marks` do not yet. | `review-events` in ROADMAP, [review page](plans/review-page-plan.md) |
| A **link** between two things, carrying who proposed it, who decided, the verdict, the seconds and the basis | [digest pipeline](plans/digest-pipeline-plan.md) |
| A "derived from" edge between sources, so "independent check or echo" becomes a graph query | [digest pipeline](plans/digest-pipeline-plan.md), paper |
| A **check** that lists its inputs | paper, `review-events` in ROADMAP |
| **Claim** and **claim evidence** | [evidence chain](plans/evidence-chain-plan.md) |
| Separate dates for the world, the survey, the printing, the scan, the reading and the decision | not yet written up |
