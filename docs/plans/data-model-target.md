# Data model — the target, and the moves to reach it

Status: proposal, 2026-10-16. Nothing built. Serves bet 2 (`review-events`) and bet 1a (`place-links`);
the rest is Debt or Later. Branch `model-dedup`, worktree `vma-model-dedup`.

This plan does not replace the object model in `knowledge-system-plan.md`. It uses that plan's layer
numbers (§9), keeps `evidence-chain-plan.md`'s identity rules, and adds what an outside review of the
field found missing. Sources: the schema audit and the field survey of 2026-10-16 (both local
scratch reports; their findings are restated here, so nothing below depends on them).

**Question.** The owner asked whether the whole database should be rebuilt around clear layers:
people, map, metadata, features. What do established models (IFLA LRM, IIIF Georeference, Linked
Places Format, OpenHistoricalMap, W3C PROV, Recogito, World Historical Gazetteer) say, and what would
VMA change?

**Answer.** No rebuild. VMA already has most of the target under other names, and three things are
missing: **places** (real things, apart from any map), **the link from a feature to a place**, and
**a record of what each process used**, which is what makes "is this check independent?" a query.
Two smaller gaps: non-map **sources** and a user's **workspace**.

**So what.** The first two missing things are bet 1a's result (owner-confirmed links), and the third
is bet 2's (independent checks, measured). Everything else waits.

## 1. Layers: today and target

Layer numbers are `knowledge-system-plan.md` §9's. "People" is new.

| Layer | Today | Target | Move |
|---|---|---|---|
| **People** | `profiles` (role), `favorites`, `stories`, `user_layers`; no workspace | `profiles` + **`workspaces`** (owner, name, visibility); a user's layers, stories and saved maps carry `workspace_id` | Later |
| **0. Sources and surveys** | `series`, `series_cells`, `sheet_printings` (0 rows), `cell_printings`; no non-map sources | same, plus **`sources`** (decree, archive file, book, period text: kind, citation, URL, date) | Later; `model-dedup-plan.md` cleans the duplicates |
| **1. Holdings** | `maps` (one scan workspace: a held sheet or one E/W half), `map_images` | same. A `maps` row already *is* what Allmaps calls a map: the part of a scan that gets georeferenced. No new region table | none |
| **2. Placement** | `georef_versions` (103, 118), `map_georef_current` | same | none |
| **3. Readings** | `ocr_labels`, `footprints`, `label_pins`, legend in three places | same tables; each reading names the **activity** that made it | bet 2 |
| **4. Entities** | `place_names` view (text groups, not entities) | **`places`**, **`place_names`** (dated, cited), **`place_geometries`** (dated), **`place_relations`** (part of, successor of: admin units over time), **`place_links`** (OSM, Wikidata, OHM ids) | bet 1a |
| **4 → 3 link** | none; place-links writes a local file | **`feature_place`**: this reading shows this place | bet 1a |
| **5. Assertions** | `evidence-chain` claims, not built; `review_events` on branch `review-store` (122) | `review_events` for every human decision; **`activities`** for every machine or human process | bet 2 |

## 2. Before and after, one 1882 label

**Before.**

```text
ocr_labels  "Marché"  (run_id v1b, map 1882)
     │
verdicts.jsonl, one local line:  relation "moved", target {source: topo, id, name, lng, lat}
```

The link is a file on one laptop, and "moved" mixes two facts in one field.

**After.**

```text
activities     v1b: OCR model + prompt version, used = [scan image, overview]
     │ made
ocr_labels     "Marché"  (activity v1b)
     │ shows (feature_place: status accepted, review_events row → Tue, 9 s, blind)
places         Chợ Bến Thành (market)
     ├─ place_names       "Marché"  1882   cited: this label
     ├─ place_geometries  the 1882 site, with an end date   cited: this label
     ├─ place_geometries  today's site, with a start date   cited: OSM way
     └─ place_links       OSM way …, Wikidata Q…
```

(The shape is real; the market's dates and the 9 s are placeholders, not looked up.)

"Moved" is now a fact about the place: two dated geometries. The link only says that the label
shows the place. A second map's label that shows the same place links the two maps.

## 3. The new tables

Every claim row carries the same evidence columns: `activity_id`, `status`
(`proposed | accepted | rejected | deferred | superseded`), `confidence`, `supersedes_id`. Reviews
stay in `review_events`, not in columns.

- **`activities(id, kind, agent, on_behalf_of, software, version, params, used, started_at, ended_at)`.**
  `kind` is `model_run | script | human_session | import`. `used` lists the input rows or files.
  Seed it from what exists: OCR `run_id`, `georef_versions.method_ref`, `pipeline_jobs`.
- **`places(id, type, label, start, end)`.** Thin. Dates as text in EDTF (`1882`, `188X`, `1880/1885`).
- **`place_names(place_id, name, lang, script, start, end, source_label_id | source_id)`.** Each name
  cites the label or source it came from (Linked Places Format requires a citation per name).
- **`place_geometries(place_id, geom, start, end, certainty, source_label_id | source_id)`.** Each
  map's drawing is one dated claim about where the place was.
- **`place_relations(place_id, rel, other_place_id, start, end, source_id)`.** `rel` is
  `part_of | successor_of | split_from | merged_into`. This is where admin units over time live.
- **`place_links(place_id, scheme, ext_id, match)`.** `scheme` is `osm | wikidata | ohm | whg`;
  `match` is `close | exact`.
- **`feature_place(label_id, place_id, status, confidence, activity_id)`.** One row per accepted or
  proposed link. Labels only, for now: every place-link item is an `ocr_labels` row. Add a
  `footprint_id` when a shape needs a link.

Not new tables: workspace and sources (above, Later); a `terms` vocabulary table (with
`knowledge-system-plan.md` gap 5, `vocabularies`).

## 4. Order

Migration numbers are assigned when each is written. 120–121 belong to Codex, 122 to `review-store`.

1. **Bet 2. `review-store` lands** (another stream; 122). Nothing to do here but wait.
2. **Bet 2. `activities`** (~half a day). Table, plus a backfill from OCR runs and georef versions.
   **Test:** one query answers, for the 1882 place-links score, "do the check and the claim share an
   input?". The 14 landmark rows should come out *not independent*: they were chosen because they sit
   on a known outline (`place-links/README.md`).
3. **Bet 1a. Places and `feature_place`** (~1 day). Tables, and a loader from the place-links
   `verdicts.jsonl` (or from `review_events`, once it has them).
   **Test:** every decided item loads; no field of the verdict line is lost; "moved" and "gone" come
   out as place dates, not as link values.
4. **Debt. `model-dedup-plan.md` steps 1–2** (~3 h).
5. **Later:** sources, workspaces, the series technical profile (grid, units, datum on `series`,
   per-sheet override), `terms`.

## Idea gate

1. **Bet:** step 2 → bet 2, step 3 → bet 1a. Steps 4–5 serve no bet now.
2. **Smallest test:** step 3's loader on the place-links verdicts so far. One afternoon, one sheet
   (1882), one number: verdict fields lost (target 0).
3. **Kill result:** if the loader loses a field, or the owner's sitting shows the relation split
   doesn't match how a person thinks about the item, the table design is wrong: redesign before
   writing a migration.

## Not in scope

A single `features` table merging `ocr_labels` and `footprints` (the survey suggested it; the cost is
every reader of both, for no bet). A generic subject-predicate-object table, RDF or a graph store (the
same position as `knowledge-system-plan.md` §6 and `evidence-chain-plan.md`). Editing admin
boundaries by hand: cite OpenHistoricalMap or Wikidata and store only what VMA's maps show.

## Reading for the PhD pitch

- Chiang et al., *Machines Reading Maps* (DH2022), https://dh-abstracts.library.virginia.edu/works/11808
  — the closest prior work: machine proposes, person accepts, links go to gazetteers.
- Arnaud, *Carte en série / monographie* (ABES, 2023),
  https://documentation.abes.fr/guide/html/ContributionsReseau/20230505CarteEnSerieVsMonographie.pdf
  — why series and grids resist cataloguing; uses an Indochine 1942 sheet.
- David Rumsey Map Collection, *Text on Maps* (Stanford, 2023), https://purl.stanford.edu/wc461hp2261
  — a large machine-only label set published as unverified: the contrast to a measured review.
- Linked Places Format, https://github.com/LinkedPasts/linked-places-format — the export shape for §3.
- W3C PROV-O, https://www.w3.org/TR/prov-o/ — `used` and `wasDerivedFrom`, the terms behind `activities.used`.
