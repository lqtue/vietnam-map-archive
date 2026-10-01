# Knowledge system — plan (2026-10-01)

VMA stores many kinds of things: maps, scans, georeferences, OCR labels, polygons and place names.
They are classified in many ways, and they point at each other. Until now each kind grew its own
categories and its own links, one plan at a time. This document describes them as **one object
model**. The sheet organization (survey → cell → printing → map) is one part of that model, not the
whole of it.

This document sits above three existing plans, and it does not repeat them:

| Plan | Owns |
|---|---|
| `docs/evidence-chain-plan.md` | Identity and citation: the identity table, claims, `cited_value` snapshots, invariant 8 (naming the error measure) |
| `docs/search-plan.md` | Finding things: label search, the temporal fabric, period sources |
| `docs/platform-design.md` §0 | The place-time index: PostGIS geometry warped on write, `geom_src`/`geom_rmse` |

This plan adds four things the others do not have:

1. the full grid of objects;
2. one rule for classifying any of them;
3. every link between them, with how much of each link is actually filled in;
4. the gaps, ranked.

Every count below was taken from production on 2026-10-01.

## 1. The question that started it: series and collection overlap

**Yes, they overlap.** `maps.collection` is meant as a display string, but in practice it is the
identity of the series:

- `series_key(collection)` is the key that both `series_cells` and the `map_series` view join on;
- `map_series.name` is the same string as `collection`.

Facts about a sheet's series are stored in five places:

| Fact | Where | Rows |
|---|---|---|
| Which series (the identity) | `maps.collection`, folded by `series_key()` | 822 of 859; the other 37 are free-standing plans |
| CartoMundi's name for the series | `extra_metadata.cartomundi_serie` | 786 |
| Series, as an older importer wrote it | `extra_metadata.series` | 34 |
| Edition | `extra_metadata.edition`, and inside the collection string itself (`2nd édition SGI`) | 20 |
| Sheet number | the `maps.sheet_number` column (634) **and** `extra_metadata.sheet_number` (822) | The two agree on all 634 rows that have both. The 188 rows that have only the JSON copy are all 1st-edition Indochine sheets, so that series cannot appear in `map_series`. |

The archival meaning of "collection", **who holds the sheet**, is stored somewhere else:
`maps.holding_institution`, and per printing in `cell_printings.institution`.

So one word carries two meanings, and the meaning it actually carries in the data (the survey) is
not the meaning the column name suggests (a holding). Renaming the collection string on some rows
silently moves those rows into a different series.

The 37 sheets with no collection are mostly the city plans: Saigon 1882, 1898, 1942, Hà Nội and
others. They are not a survey. They are a curated group of sheets that do not form a survey grid.
That is a third concept, and today it has no home at all.

## 2. The object grid

The tables below cover every kind of object the archive holds today, with where it lives, how it is
identified and how it is classified. An empty cell in these tables is a finding, not an oversight.

### 2a. Identity and storage

| Object | Lives in | Identity | Count |
|---|---|---|---|
| **Survey** (series) | `maps.collection` text; the `map_series` view summarises it | `series_key(collection)`. There is no table. | 5 named; 4 appear in the view |
| **Cell** | `series_cells` | `(series_key, sheet_number)` | 1,046 |
| **Printing** | `cell_printings` | row id. It deliberately has no foreign key, so a printing we do not hold still has a home. | 1,131 |
| **Map** (a held sheet, or an E/W half) | `maps` | `id`; `slug` is its address | 859 (528 published) |
| **Image** (a scan or IIIF service) | `map_images`, plus R2 tiles | row id | 481 published maps have **no image row at all**: the Indochine halves, plus one L7014 sheet |
| **Georeference version** | Storage: `annotations/<id>.json` for the live version, `annotations/<id>/<stamp>.json` for history | `geom_src` (a hash of the GCP set), but only as a copy on derived rows. The georeference is **not a database object**. | 592 live |
| **GCP set** | Inside the annotation JSON, `body.features` | none | readable only by parsing the JSON |
| **Transformation** | Inside the annotation JSON, `body.transformation` | none | polynomial 566, helmert 20, thin-plate spline 5 |
| **Mask** | Three different things; see §2c | none | — |
| **Fit quality** (RMSE) | `geom_rmse`, copied onto each label and polygon row | none | no figure stored per map or per version |
| **Text label** | `ocr_labels` | `id`; `run_id` groups the output of one OCR run | 14,506 labels on 22 maps |
| **Polygon** | `footprints` | `id` | 1,519 polygons on 2 maps |
| **Pin** | `label_pins` | `id`, located by pixel x/y | 368 |
| **User layer** | `user_layers` (`annotation_sets` is only its compatibility view) | `id` | 15 |
| **Place-name group** | the `place_names` view | `name_key` / `core_key` | derived |
| **Story point** | `story_points` | `id`, located by longitude/latitude | 6 |
| **Discovery candidate** | `scout_candidates` | `id` | 1,067 |

### 2b. Classification, provenance, review and quality

| Object | Classified by | Made by | Review state | Quality measure |
|---|---|---|---|---|
| Survey | name only. Scale, edition and producer are buried in the name string. | importer scripts | — | survey coverage: held cells ÷ all cells (411 of 1,046) |
| Map | `map_type` (820 topographic, 30 plan…); `holding_institution`; `location` (608 null); `year` | importers, admins | `status` (draft, public or featured); `triage` | — |
| Georeference | `transformation` type | an Allmaps editor (`allmaps_id` is the key on Allmaps' side) or our pipeline (`annotation_url` with no `allmaps_id`) | none. The `sync-georef` flip copies an annotation into our storage without any review step. | RMSE, but there are three figures for 1882 alone (`evidence-chain-plan.md` invariant 8) |
| Text label | `category`, a fixed set of 10 values (street 4,806, place 3,620, legend_ref 1,801…), with `category_corrected` for corrections | `run_id`, `model`, `prompt`; `reviewed_by` | 11,245 pending, 3,143 rejected, **118 validated** | `confidence` |
| Polygon | `feature_type` (5 values) and `category` (free text, see §3) | `source`: 1,443 imported, 76 by volunteers; `run_id`; `user_id` | 1,443 needs_review, 30 submitted, 46 approved | `confidence`; `temporal_status`, which is unclassified on all 1,519 rows |
| Legend | `maps.label_config.legend`, filled on **1** map | hand | — | — |

### 2c. One word, three masks

| Name to use | What it is | Where | Used for |
|---|---|---|---|
| **georef mask** | The SvgSelector polygon in the annotation: the part of the scan that gets warped onto the map | Annotation JSON, on all 592 | display (the warped overlay) |
| **neatline** | The printed frame of the map face, detected or drawn on the scan | `triage.neatline` (91 maps) | cropping for OCR |
| **layout regions** | The map face, legend, title and margins as separate regions | `triage.regions` (108 maps) | sending each region to the right OCR prompt |

Today the neatline editor builds the **georef mask** out of its four corner GCPs (the
`PATCH /api/admin/maps/[id]/annotation` route). That route mixes the two ideas: it writes the
neatline into the georeference.

## 3. One classification rule: printed → normalized → who mapped it

Two things hold at every level, from survey down to polygon:

- An object is classified on several independent axes at once: survey, edition, scale, map type,
  holder, place and period for a sheet; feature type, legend class, period and name for a feature.
  A series is **one axis**, not the container that everything else sits in.
- On each axis, the value has a printed form and a normalized form, and those are two different
  values.

The repo has already paid to learn this once, for rights. Migration 096 merged `domaine public`
into `Public domain`, and `evidence-chain-plan.md` §Rights now needs the provider's wording back.
The same loss is happening on the other axes right now:

- `footprints.category` holds the same classes in several spellings: `non_affect` (682) and
  `Non-affect` (2); `militaire` (82) and `Military` (2); `communal` (65) and `Communal` (6); plus
  `Private`, `Local Service` and `Others`. 585 rows are null.
- A sheet's own legend is its printed vocabulary for its features, and it is recorded on 1 map
  out of 859.
- Labels in category `legend_ref` (1,801, the legend symbols as they appear on the map face) are not
  linked to `legend_entry` (867, the rows of the legend itself), so a symbol on the map cannot be
  looked up in its own legend.

**The rule.** Every axis stores three things:

1. **Printed:** the value exactly as the source says it — the legend entry, the catalogue title,
   the rights statement.
2. **Normalized:** a term from a small cross-map vocabulary for that axis.
3. **The mapping:** which printed value became which normalized term, made by whom or by which
   run, and when.

For features, the sheet's legend is the printed vocabulary, which makes `label_config.legend` the
start of it rather than a side feature. One vocabulary table keyed by axis
(`vocabulary(axis, term, parent, label_en, label_vi)`) is worth having once four or more axes use
it. Map type, feature category, label category and rights already make four.

## 4. Links, with how much of each is filled in

| From → to | Stored as | Filled | Gap |
|---|---|---|---|
| cell → printing | `(series_key, sheet_number)`, with no foreign key | 1,131 printings | by design (see `multi-printing-cells`) |
| cell → map | `series_cells.map_id` | 411 of 1,046: L7014 9 of 627, 1st ed. 130 of 143, 1:25k 75 of 79, 2nd ed. 197 of 197 | — |
| map → image | `map_images.map_id` | 132 of 859 maps | 727 maps have none: 481 published (mostly the Indochine halves) and 246 drafts |
| map → georeference | a storage path, plus `annotation_url` | all 528 published and 64 drafts | no row in the database; history exists only as file names |
| georeference → image | the annotation's `target.source` id, width and height | all 592 | not a foreign key. `map_images` stores no dimensions (owned by `evidence-chain`). |
| label or polygon → map | `map_id` | always | — |
| label or polygon → image | — | **none** | which scan's pixels were measured is not recorded (owned by `evidence-chain`) |
| label or polygon → georeference version | `geom_src` | 13,529 labels; 46 polygons | **stale**: see below |
| label → polygon | `ocr_labels.footprint_id` | **8 of 14,506** | the OCR ↔ shape join (Shapes) |
| label → legend entry | — | none | see §3 |
| polygon → legend class | `footprints.category`, free text | 934 of 1,519 | see §3 |
| label → place-name group | implicit, by `name_key` in a view | derived | does not prove that two spellings are one place (owned by `evidence-chain`) |
| story point → map | `overlay_map_id` | 6 | — |
| claim → evidence | planned: `claim_evidence` | — | `evidence-chain` step 2 |

**The derived geometry is already stale.** I hashed the GCPs in each live annotation the way
`gcpSrcHash` does (`src/lib/server/warp.ts:69`), reimplemented in a script, so check the result
against the real function before you act on it:

- **1882:** the live annotation (8 GCPs) hashes to `93c4487e621f83c9`. Its 499 labels and 46
  approved polygons still carry `245d98f7f8d61572`, the hash of the old 10-GCP set. That is the very
  value `evidence-chain-plan.md` step 1 pins as "as of 2026-09-30".
- **1898:** the live annotation (9 GCPs) hashes to `c741978dab027258`. Its 472 labels carry
  `6a9d98830937123e`.

The staleness check works as designed: the hashes differ, so the drift is visible. But nothing
re-warps when an annotation is synced, and the georeference has no database row a query could
compare those hashes against.

## 5. Gaps, ranked

Each gap is named for its subject. "Owner" points at the plan that already holds it, if any.

1. **`georef-versions`: make the georeference a database object.** This is the one genuinely new
   table. Proposed: `georef_versions(map_id, image_id, stamp, geom_src, transformation, gcp_count,
   rmse_m, rmse_method, origin, allmaps_id, created_by)`, with `origin` one of `allmaps`,
   `pipeline` or `neatline`. Every writer appends a row: `mirrorAnnotation`, the neatline `PATCH`,
   `sync_district4_annotations.mjs`, and the pipeline scripts (`tonkin_georef.py`,
   `indochine100k_georef.py`, `l7014_annotate.py`). Defer a table with one row per GCP until a
   query needs one.
   **Exit:** one query lists every 1882 version with its GCP count and its named RMSE, and a join
   on `geom_src` shows which labels are stale.
2. **`rewarp-on-sync`: re-warp after a georeference changes.** 1882 and 1898 are stale now. Fix it
   once by hand now; later, make the sync script and `mirrorAnnotation` queue the re-warp.
   **Exit:** every label's and polygon's `geom_src` matches its map's current version. Update the
   pinned value in `evidence-chain-plan.md` step 1 at the same time.
3. **`mask-names`: one name for each of the three masks** (§2c). Record the names in
   `docs/conventions.md`. Decide whether the neatline editor should keep writing the georef mask.
   **Exit:** no code comment or document uses a bare "mask" for more than one of the three.
4. **`series-identity`: make the series an explicit key, not a side effect of the display string.**
   Smallest step: a generated `maps.series_key` column, with `collection` treated as the display
   string. Fill the `sheet_number` column for the 188 first-edition rows. Move
   `extra_metadata.series`, `cartomundi_serie` and `edition` into columns, or drop them. Give
   curated groups that are not surveys (the city plans) a separate concept rather than a fake
   series.
   **Exit:** no fact about a series exists only in `extra_metadata`, and the first edition appears
   in `map_series` once any of its sheets is georeferenced.
5. **`vocabularies`: apply the printed → normalized rule** (§3). Start with
   `footprints.category`, because its spelling variants are measurable, then label category against
   each sheet's legend.
   **Exit:** each distinct normalized category is one vocabulary term, and the printed spelling is
   kept on every row.
6. **`image-identity`: image dimensions, and an image row for every map.** Owned by
   `evidence-chain` step 5, "Differing images". This plan only adds the 481 published maps that have
   no image row.
7. **Label ↔ polygon and label ↔ legend links.** Owned by Shapes (the OCR ↔ shape join).
   `legend_ref` → `legend_entry` falls under the same join.
8. **Naming the RMSE.** Owned by `evidence-chain` invariant 8. `georef_versions.rmse_method` is
   where that name gets stored.

## 6. Scale and what this is not

OCR has run on 22 maps and polygons exist on 2. Only 118 labels and 46 polygons have been reviewed
by a person. This document is the model to grow into, not a migration plan for a corpus that does
not exist yet.

- **Not a graph database, and no universal node/edge table.** These are ordinary typed tables and
  foreign keys in Postgres, the same position as `evidence-chain-plan.md`.
- **Gaps 1–3 are cheap and fix things that are wrong today.** Gaps 4–5 change how the data is
  shaped; do them after the `evidence-chain` pilot shows which axes its queries actually use.
- Each new table follows `docs/db-guidelines.md` and copies the
  `map_images_select_visible_parent` RLS shape, so a draft map's derived rows stay private.

## 7. Recommendation: three groupings, three names

"Collection" names nothing that the data actually needs to group by. Retire it as a concept. Split
what it carries today into three groupings that differ in kind:

| Name | What it is | How many per map | Where |
|---|---|---|---|
| **series** | A survey: one producer, scale and sheet grid, with cells that exist whether we hold them or not | 0 or 1 | `series_key`, today generated from `collection` (`series-identity`); later a `series` table when scale, producer and edition need columns |
| **holder** | Who keeps the physical sheet or the scan | 1 per printing | `holding_institution` and `cell_printings.institution`, as today |
| **set** | A curated group of sheets put together by a person: the Saigon city plans, the District 4 pilot, a story's sheets | any number | a new `sets` table plus a `set_maps` join table, when the first page needs one |

Why three:

- A series has a grid and can be measured for coverage, which makes it a fact about the source.
- A holder is a fact about provenance.
- A set is an editorial choice and has neither of those.

Using one column for all three is why the 37 city plans have nowhere to go, and why "collection"
reads as the archive's holding when it actually keys the survey. `maps.collection` stays as the
display string until `series-identity` lands. After that it is only a label.

The open items are in `docs/ROADMAP.md`: `georef-versions`, `rewarp-on-sync` and `mask-names`
under Evidence and legibility, and `series-identity` under Survey layer and catalog.

## 8. Found while writing this (2026-10-01)

- **1942 Saigon–Cho Lon.** The fit is 112 m RMSE (worst point 299 m) on 9 GCPs. One point,
  `[10504, 2356] → (106.6950, 10.7795)`, misses by about 300 m; without it the RMSE is 26 m.
  `drop_1942_gcp1.mjs` removed that point on 2026-09-22. It is still on Allmaps, though, and the
  sync on 2026-10-01 put it back. This is the first regression caused by having no review step
  before syncing. The repair is in `scripts/oneoff/fix_saigon_1942_1968.mjs`, and the point must
  also be deleted in the Allmaps Editor.
- **1968 Sài Gòn.** `allmaps_id` is keyed to an Internet Archive scan that has no `map_images` row,
  so no editor link can be built. The same script adds the row.
- **1959 Đô thành Sài Gòn** is consistent: its stored copy matches upstream, the fit is 14 m, and
  it has an editor link.
