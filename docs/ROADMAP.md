# Roadmap — open work (updated 2026-10-05)

**Everything in this file is open.** Nothing closed lives here: the record of finished passes, with
the measurements and the defects each one turned up, is `docs/roadmap-record.md` (frozen
2026-09-22), and the rules that keep getting re-learned are `docs/lessons.md`. **Close an item by
deleting it**, never by ticking it: the commit that deletes it carries the closing measurement, and
anything worth re-learning goes into `docs/lessons.md`. Remove its name from
`docs/knowledge-system-plan.md` §9 in the same commit.

Ordered where order is claimed. Each item names the check that says it is finished.

**An item's name is what it acts on, not the pass it was born in.** `l7014-iiif`, not `N1`. The
old letter codes were unmemorable, and worse, they moved: one item was `I3` and then `N1`, another
shipped as `E2b` while its `B8` box stayed unticked, and two code comments ended up pointing at
sections that no longer existed. A name taken from the subject survives every reordering. Use it in
prose ("the L7014 rebuild"), in a commit (`fix(georef): l7014-rebuild phase C`), and in a code
comment. The map from the old codes to these names is at the bottom of this file.

## Do next

The foundations pass, opened 2026-09-21 and superseding the OCR-corpus list that ran before it.
Why foundations rather than another method: every elaborate pass in the record ended by finding a
basic thing broken — no OCR run could read an R2-hosted map at all, a 31.8% white-hole overview the
model scored 7/7 on, a fixed pixel tile being a different amount of ground on every sheet, the
L7014 mixed-datum fault, 56 published sheets drawing nothing. So: georeference quality, segmentation
measurement, metadata that maintains itself, and corpus size.

- [ ] **`l7014-iiif`** — L7014 as one IIIF series from three sources (PCL, TTU, ANU). The PCL
      ingest shipped 2026-10-03 (510 GeoPDFs public; the PMTiles mosaic retired) — record in
      [L7014 inventory audit](journals/261003-l7014-audit.md), metadata recovery in
      [261004](journals/261004-l7014-metadata.md). Open:
      1. The 15 plain PCL scans are annotated (fits 1–43 m) but still `draft`, none looked at in
         `/explore`.
      2. **TTU** (140 raster PDFs): of 137 rows ingested as `draft`, 85 are unplaced
         (`l7014_ttu_corners.py` fits about half; the rest need a person); 52 placed sheets await
         visual acceptance; 34 rough readings are unmerged; margin reading stopped on API limits.
         Seven TTU map rows lack source records, three source records lack map rows.
      3. **ANU** (159 masters) adds no new cell: record its handle on the PCL/TTU row instead of
         ingesting duplicates.
      4. 43 cells are in none of the three sources.
      5. Seven `--hand` sheets are 30–80 m off a parallelogram and want an eye; `6835-4`'s seams to
         its neighbours are unchecked.
      6. Remaining medium/low-confidence title readings need review; Gò Công 6329-4 and Quản Bạ
         5955-2 are undated.
      7. The paper's §7.6 / `blind-by-construction.tex` still cite the unrebuilt archive.
      8. `work/l7014/cogs*` and the old PMTiles R2 object are no longer needed — delete when sure.

- [ ] **`series-sheets-bbox-datum`** — `series_cells.bbox` holds the raw, unshifted Indian 1960
      graticule straight from `index.geojson`, not the corrected WGS84 lattice `l7014_mosaic.py
      corners` already derives (Everest 1830 (1937 Adjustment) → WGS84). Measured 448–498 m off, NW
      of the true lattice position, on the three cells checked (6150-4, 6330-4, 6541-4) — the same
      direction and rough size as the L7014 datum fault (fixed), but this is a
      separate bug: it's every unheld cell's ground rectangle, not a warped sheet's position. Affects
      all 627 cells in the L7014 index, so every gap the coverage page draws is ~470 m off from
      where the survey actually places it. A database backfill, independent of any mosaic build — re-derive each cell's bbox from `index.geojson` through `cell_corners()`
      (`scripts/l7014_mosaic.py`), the same function `lattice.json` already uses. Exit: every
      `series_cells` row in `series-l7014-vietnam-1-50-000` measures inside `geo_audit.mjs`'s
      `CELL_TOL` (150 m) against `lattice.json`.
- [ ] **`three-point-residuals`** — give the 11 remaining three-point sheets a measurable one. A
      3-GCP affine fit
      has zero degrees of freedom, so its RMSE is identically 0 and a sheet can be badly wrong
      while reporting nothing. This is not a backlog item, it is a hole in the quality signal
      itself. A 4th point on each buys a number where there currently cannot be one. Do the five
      one-point GCP fixes and the 1912 Saigon-Cholon (three near-collinear points in one corner) in
      the same sitting. The 1880 *Plan annamite d'Hanoi* is 802 px and needs a new scan before it
      needs GCPs. (Was 12 — `hue-l7014-6541-4` dropped off the list 2026-09-22: the L7014 rebuild
      swap
      promoted the 4-GCP `hue-l7014-6541-4-2` in its place.) Exit: no georeferenced sheet in the
      corpus sits on fewer than 4 points, and `modern_prior.py --sweep` reports a residual for
      every one.
- [ ] **`indochine-100k-georef`** — auto-georeference both 100k series from what they print, the
      way `tonkin_georef.py` does for the sibling 1:25,000 survey. **561: pipeline built and
      working, first batch published 2026-09-24** — `scripts/indochine100k_georef.py`
      (`calibrate`/`place`/`check`/`annotate`) mirrors Tonkin's catalogue-driven
      `from_catalogue()`/`calibrate()` fallback against `extra_metadata.cartomundi_fkeys[0]`'s own
      UNIMARC bbox (not the unioned `series_cells.bbox` — see the journal). Calibration accepted
      on 6 sheets (10.5–20.9°N) after **excluding Tri Binh** (741m residual outlier, judged too
      clean to be an OCR error but excluded anyway to unblock — an open question, not a resolved
      one: docs/journals/260923-indochine100k-georef.md). Accepted fit: 76m mean / 188m max
      residual. **2026-09-24 update:** 132 additional sheets cleared the per-sheet gate and the
      series lattice check (Pursat E was held for its offset outlier) and were published at the
      user's request. Together with the first 3, 135 of 360 rows are public; they represent 98
      distinct cells. The live page is `/catalog/series/indochine-1-100-000-2nd-edition-sgi-1947-1959`.
      The sheets cleared programmatic gates but were not individually eyeballed in `/explore`.
      **New finding this pass: the per-sheet frame-detection gate
      itself holds a majority of sheets**, independent of calibration — 4 of 4 freshly-sampled
      sheets outside the calibration set (Gia Ray, Kratié, Sop Cop, Hà Giang) held on
      `rim offsets spread`/`axes disagree`, matching the ~44% clear rate the calibration pass
      already saw. Tuning `detect()`'s constants (`ACROSS`/`MAXIN`/rim-spread tolerance) against a
      wider sample is the real remaining work before a full-series batch, not just accepting a
      calibration. Of the 225 unpublished sheets, 168 now clear locally and 57 remain held.
      **325: WKT matching grid built** from
      CartoMundi's IGN geometry and matched to all 221 VMA rows, but no image-placement pipeline
      exists yet; its third frame convention (thick neatline → ticked band → gap → thin inner line,
      plus a K-grid overlay) still needs its own detector.
      Exit: same as `tonkin-review` — every sheet that clears the gate carries
      `is_georeferenced = true`, a person reviews before publishing (the 3 published sheets above
      were geometry + lattice + landmark-bbox checked, not eyeballed in `/explore` — do that before
      trusting them fully).
      **Local detection update 2026-09-28:** the last-blank-run rim search skipped visible borders
      on some held sheets, and the overview sometimes picked the printed scale bar as the bottom
      frame. Gated edge retries, patch-supported rim candidates, a direct-boundary check, and a
      source-transition check for spread outliers, source-reviewed special cuts, and four-edge
      printed-tick placements bring the read-only lattice to 303 clear placements, up from 170;
      33 non-span holds remain, including explicit exclusions. Kompong Sralao (W) recovered
      per-sheet but overlaps another cell and has a persistent hold. The pending local records
      have not been published; see the 2026-09-28 journal entry. Thirty-three scale holds now have eight
      source-checked ticks and a skewed four-corner placement: catalogue extrema had exaggerated
      their frame spans. Nine unusual cuts/full sheets have source-pinned span exceptions. The
      remaining 3 scale-only, 30 mixed, and 24 catalogue-span holds require further sheet-level
      investigation. Version 28 passes the lattice and regression checks (303 placements, zero
      conflicts or corner movements over 2px).
      **2026-09-29 update:** 11 of the 13 version-28 boundary trials landed (version 31); one
      (Muong Ou Tay W) stayed held on an isolated 2.0% axis-scale gap now that its boundary is
      fixed, and one (Lang Son E) was found wrong on re-review — a second interior-grid-line
      pick that passed two visual review methods and was caught only by a per-pixel profile —
      and reverted to held. 314 placements clear, zero lattice conflicts, zero corner movements
      over 2px against a version-28 snapshot. 46 holds remain: 24 catalogue-span, 4 axis-scale-only,
      12 mixed, 3 shape/aspect, 3 persistent exclusions. Resume from
      `docs/journals/260929-series561-handoff.md`.
- [ ] **`indochine-100k-licence`** — **premise moved (2026-10-01):** the ingest is done, and all
      581 rows already carry `CC BY 4.0 — IGN, deposited in Nakala`, not the NC-SA string below.
      Still open: whether CC BY is right for the 100,000 series. The exit is now "the minted rows
      carry a verified licence", not "settle before minting". Original text: settle it before the
      ingest run mints 578 rows.
      Probed 2026-09-21 with the same
      per-item method that settled the 25,000 series, `10.34847/nkl.3490q3l6` (serie 561) also
      returns `"CC-BY-4.0"`, not NC-SA — and both series' CartoMundi records name the *same* Nakala
      collection DOI (`10.34847/nkl.d2a82952`). So the per-item field does not discriminate between
      them, and whatever established NC-SA for the 100,000 series was not re-verifiable: the Nakala
      collection page now demands SSO. `scripts/oneoff/ingest_indochine_100k_nakala.mjs` writes
      CC-BY-NC-SA-4.0 into every row it mints. Settle this **before** the ingest run mints 578
      more of them — over-claiming a restriction is cheaper than under-claiming one, but a
      collection of 578 rows carrying the wrong licence string is expensive to correct.
- [ ] **`shape-precision`** — measure shapes before tuning them. There is a recall-ish number and
      **no
      precision number at all**, so every segmentation change to date is unfalsifiable. Trace one
      bounded 1882 window completely, run `seg_eval --window` (already built and self-checked —
      `python work/image-processing/scripts/seg_eval.py --self-check`), keep machine predictions out of the
      ground truth by construction. **A candidate window is scoped, not traced** (2026-09-22): the
      triangular îlot bounded by Rue Mac, Rue No. 15 and Rue Pellerin, source pixels roughly
      `4420,3800,650,550` on map `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b` (the 1882 cadastral).
      9 of the sheet's 46 volunteer traces (6 `building`, 3 `land_plot`, all `approved`) already
      sit inside it — checked against `footprints` directly, not estimated — against
      roughly 11 real parcels/buildings visible in an IIIF crop of the same box. That leaves on the
      order of **one or two features** to add before the window is exhaustive, which is a single
      sitting at `/scan?mode=shapes`, not a research task — a person has to do the actual tracing
      and confirm nothing was missed, an LLM producing plausible polygons here would be fabricating
      the exact ground truth this item exists to make trustworthy. Related and blocking the
      District 4 table: **there are no footprints inside District 4** — all 46 volunteer traces are
      in District 1, the nearest 68 m north of the Bến Nghé canal. Review is not the blocker;
      tracing the peninsula is. Exit: a precision figure alongside the recall one, with its sample
      and limitations recorded beside it.
- [ ] **`tonkin-review`** — a person looks at all 62. `graticule-georef` (the machine half of this
      item) is done and was already shipped before this list existed: `scripts/tonkin_georef.py`
      reads each sheet's own printed corners (grades from the Paris meridian,
      `grades × 0.9 + 2.337229` = degrees east), cross-checks against the pixel quad and the
      series' own lattice, and placed 121 sheets by 2026-09-15, then 84 more by hand-corners and
      catalogue polygons where the detector had no anchor — **205 of 207** sheets in "Indochine
      1:25,000 — Tonkin & Thanh Hóa" now carry a georeference (`work/tonkin/*.json` per sheet,
      committed). The two that do not are the two that cannot: An Thi 1904 (serie 243 does not hold
      that year) and Phat Diem 1927 (IGN never digitised the east half) — a permanent gap, not a
      bug. What is left is the pipeline's own last step, by design
      (`annotate()`'s docstring in `scripts/tonkin_georef.py`): every one of the 62 sits at
      `status = draft` with `is_georeferenced = true`, visible to a signed-in reviewer at `/explore` and
      nowhere else, on purpose, because nobody has looked at all of them yet. Exit: each reviewed,
      then `annotate(write=True, only_new=True)` plus a status flip to `public` for the ones that
      pass — check tiles and thumbnails actually render before flipping, the way
      `publish_l7014_city_sheets.mjs` did for L7014, not just the DB gate.


## Also open — cheap, no ordering claim

Do them when the surrounding work opens the file.

- [ ] **`drop-compat-views`** — migration 095 renamed eight tables and left a view under each old
      name (`series_sheets`, `footprint_submissions`, `ocr_extractions`, `sheet_sources`,
      `map_iiif_sources`, `map_opens`, `user_favorites`, `annotation_sets`) to bridge `db push` to
      deploy. That deploy shipped long ago and the drop migration was never written. No app,
      worker or `scripts/*.mjs` code reads the old names; 28 files under `scripts/oneoff/` still
      mention them (measured 2026-10-01). Exit: `grep -rlE
      "series_sheets|footprint_submissions|ocr_extractions|sheet_sources|map_iiif_sources"
      src worker work scripts` returns only filenames and comments, then a migration drops the
      eight views.
- [ ] **`held-by-derived`** — `series_cells.held_by` / `map_id` is a snapshot, and nothing
      maintains it — no trigger,
      no function, only the one-off importers. So the day anyone georeferences one of the 123
      obtainable L7014 sheets, or publishes a draft, the index still says *gap* and the coverage
      page still draws it missing: right about the survey, wrong about us, with no symptom but a
      plausible-looking number. Real fix: derive `held_by`/`map_id` in a view, or a trigger on
      `maps`. Pending migrations 105–106 add role-gated `series_cell_coverage` and
      `series_printing_availability` views. These derive distinct public cells and printings, but
      production readers still consume legacy snapshots until rollout. Exit: publishing a draft
      moves its cell to *held* with nobody running anything, and service-role readers preserve the
      same public gate.
      **Until then there is a detector, which is not the same thing** —
      `node --env-file=.env scripts/check_series_index.mjs` catches an adrift cell, a dangling
      `map_id` and (since 2026-09-15) a `maps` row whose `sheet_number` the index does not contain
      at all, which is the typo case drift can never see. Clean on production 2026-09-15: 0/0/0 over
      706 sheets. Run it after any publish, georeference or re-import.
- [ ] **`scripts-apply-flag`** — sixteen one-off scripts write on a bare invocation; nine converted,
      seven not. The
      note said four such scripts existed, the next morning's audit found nine, and the real
      number is **sixteen**: `scripts/enqueue_seg.mjs`, `enqueue_layout_all.mjs`,
      `enqueue_ocr_all.mjs`, `collection_aoi.mjs`, `import-seg-geojson.mjs`,
      `enqueue_warp_all.mjs` and `oneoff/backfill_map_bbox.mjs` are each still
      `const dry = args.includes('--dry')` over a real write. Verified 2026-09-21: every one
      of the seven contains an insert/update/upsert and writes on a bare invocation. Six of
      them queue `pipeline_jobs`, which is cheaper to undo than publishing a sheet but is
      still an unattended write nobody asked for. **Three times now this item has been closed
      on a count that was too low** — so the exit is the grep, not a number:
      `grep -rn "includes('--dry')" scripts/` returns only `lib/cli.mjs`'s own
      both-flags guard, and nothing under `scripts/` writes without `--apply`.
- [ ] **`colour-hue-window`** — the colour/wash pre-pass is a **confirmed null**, not an unknown:
      every saturated pixel on
      the 1882 sheet is hue 0–60° and `compute_tile_colours` looks at 60–260°. If colour
      segmentation is to do real work, that window is the starting point — and it needs a second
      sheet's histogram before the new one is trusted.
- [ ] **`saigon-cholon-1912`** — it cannot be fit at all. `saigon-cholon-et-environs`: 3 points, SVD
      condition ratio **0.0302** against `scale.py`'s `MIN_GCP_CONDITION` floor of 0.05, so
      `fit_sheet()` returns `None` rather than an exact-but-uninformative transform. Recorded on
      2026-09-11 as "three near-collinear points in one corner", which understates it. Folded into
      `three-point-residuals`; noted here because it is the corpus's clearest single example of the
      guard working.
- [ ] **`hue-rescans`** — two Huế sheets (800×628, 754×877) are under the scout's 1024 px floor.
      They need larger
      scans, which is sourcing, not code.


## The OCR corpus drain — the queue behind every empty Search surface

6 georeferenced sheets of 39 carry extractions, which is why label search, the `/place/` hubs, the
gazetteer and `/api/press`'s spelling variants all look thin for one single reason. Measured budget
is **$31–63 for all 38 maps** on `gemini-3.8-flash`, so cost is not the constraint; unattended
quality is. This run is also the gate on the project's first paper
(private planning notes) — the toponym measurement needs all 39 sheets, not 6.
Full context and the per-call measurements: `docs/roadmap-record.md`, "The OCR pass".

- [ ] **`hand-triage`** — the first sheets, by hand, one at a time at `/scan?mode=prepare`: draw the
      neatline, click the blank and water tiles down to skip, press **Save triage**. Exit:
      `select count(*) from maps where triage ? 'neatline'` equals the number you meant to do, and
      `enqueue_ocr_all.mjs --dry` lists exactly those.
- [ ] **`gemini-second-key`** — and know the tier. `gemini_client.py` already rotates across
      `GEMINI_API_KEYS`; 38 maps unattended is the run that needs the spare. Google no longer
      publishes per-model limits — read <https://aistudio.google.com/rate-limit>. Exit: two keys
      set, and the daily request cap written down here.
- [ ] **`queue-the-pass`** — `scripts/enqueue_ocr_all.mjs --dry`, then without. It queues only
      triaged sheets, so 3h comes first or nothing is queued at all. Exit: the queued count matches
      the script's own.
- [ ] **`drain-the-queue`** — `python work/worker/vma_worker.py --worker $(hostname)`. Hours, not
      minutes.
      Exit: `select count(distinct map_id) from ocr_labels` > 30.
- [ ] **`auto-priority`** — in the worker, deferred on purpose. Reopen once ~5 sheets have been
      triaged and OCR'd by hand, so there is a baseline to judge the automatic grid against. Exit:
      on a triaged sheet it picks a grid within a tile or two of the human one.
- [ ] **`dictionary-on-place-names`** — fold one onto the other. The script reimplements grouping
      that
      migration 067's view does better (`place_key` folds accents as well as punctuation: 394
      grouped names against the script's 434 + 66 accent twins). Two normalisation rules for one
      corpus will drift. Keep its own pass only for what the view drops — `legend_entry` rows,
      `--min-confidence`, per-sighting provenance. Exit: the script's ground-name count equals the
      view's, and `--self-check` still passes.
- [ ] **`dictionary-review`** — after the drain. The first artefact a human can check against the
      sheets: errors invisible one bbox at a time (`ARSENAL DE L`, `HOTEL DU GNRAL`, a bare `Rue`
      seen 14 times) are obvious in an alphabetical list. Exit: the 20 most-sighted names are each
      validated or rejected.
- [ ] **`search-acceptance`** — on production. Search "Khánh Hội" on /catalog and /explore, land on
      the spot, read the press panel, check a draft's labels are absent when signed out. Exit: hits
      from ≥ 5 maps, and `/api/context?lng=106.70098&lat=10.77653` returns labels.

**Then, in order** (detail in `docs/search-plan.md`, engine design in
`docs/platform-design.md`):

- [ ] **`colab-seg-run`** — mint a `seg`-scoped worker key, run `vma_worker.py --kinds seg`.
      Exit: one `seg` job goes `queued → done` and writes `footprints` rows with
      `source='sam-auto'`.
- [ ] **`district4-table`** — the review that fills it. `work/analysis/district4/` is built and
      self-checking; what is left
      is human. The series is **six** sheets, generated not remembered: 1882 · 1895 · 1923 · 1942 ·
      1959 · 1968. **Blocked on tracing, not on review: there are no footprints inside District 4**
      —
      all 46 volunteer traces sit in District 1, the nearest 68 m north of the Bến Nghé canal. Exit:
      real numbers for those six years, and the approved polygons exported as the `seg-eval-set`.
- [ ] **`clahe-measurement`** — measure it against `work/ocr/EVAL-BASELINE.md`. Exit: a numbered row
      in that
      file, including a null result.
- [ ] **`press-from-gazetteer`** — feed it instead of its three guessed spelling forms.
      Waiting only on a corpus with more than one map OCR'd.
- [ ] **`street-name-pairs`** — colonial ↔ current with namesake notes. Needs the source data, not
      code.
- [ ] **`district4-figures`**, once it has numbers. Deliberately absent until then:
      a chart of three zero rows is worse than no chart.

## Evidence and legibility (planned 2026-09-19)

Deliberately not first, but no longer blocked on it either: `stale-after-change` closed 2026-09-22
(`docs/lessons.md`, `tests/stale-after-change.spec.ts`) — a corrected sheet's rebuild set is now
named, not remembered. The three I-items that duplicated live work are gone: they were
`l7014-iiif`, `shape-precision` and `stale-after-change`. Rationale for the whole
system — what a result must retain, and the two kinds of check — is in the record.

- [ ] **`next-action-view`** — show the next action for each sheet. Extend the staff status view
      with the next
      eligible action and what blocks it; reuse `map_pipeline_status` and the review marks, do not
      build a second queue. Exit: an operator can see whether a sheet needs a worker, a person, an
      image repair or a placement check without reconstructing its history.
- [ ] **`ocr-merge-evidence`** — preserve it. `ensemble_items()` keeps the largest self-reported
      confidence even though confidence is not comparable across prompts, and reduces agreement to
      `n_passes` plus a note. Retain every contributing run, reading and box; store agreement as
      structured data. Replay saved run directories into a report before changing database writes.
      Exit: a reviewer can see why two readings agree or disagree, and every signal traces to a run.
- [ ] **`review-ordering`** — optional, after measurement. A "Needs attention first" ordering built
      from `ocr-merge-evidence`'s output, compared against the present order on a held-out sample,
      with
      a random audit of apparently easy rows retained. Do not call a score calibrated until it has
      been tested against human outcomes. Exit: reviewers find more confirmed errors in the same
      time without raising residual error.
- [ ] **`evidence-chain`** — one reviewed feature on the 1882 cadastral sheet, cited from claim to
      pixels, then a frozen research packet. Most of the chain exists — pixel-master geometry
      (mig 016/066), `geom_src`, `ocr_labels.footprint_id`, `cell_printings` — so the pilot adds
      `subjects`/`claims`/`claim_evidence` and closes three gaps: an approved footprint can be
      deleted by its owner (cited rows get `ON DELETE RESTRICT` plus a `cited_value` snapshot),
      `rights` is normalised not verbatim (mig 096), and nothing records which image the pixels
      were measured on. Not blocked by `ocr-merge-evidence`; `source-agreement` and
      `attested-variants` build on its `claim_evidence` rather than beside it. Exit: a public
      claim opens its exact source region; the packet survives an OCR or georeference correction;
      draft evidence stays private. Plan: `docs/evidence-chain-plan.md`.
- [ ] **`georef-versions`** — the georeference is not a database object. GCPs, transformation,
      mask and RMSE exist only inside `annotations/<id>.json`; only `geom_src` and a copied
      `geom_rmse` reach the DB. One table, one row per stored version, appended by every writer
      (`mirrorAnnotation`, the neatline PATCH, the sync script, the pipeline georef scripts). Exit:
      one query lists every 1882 version with GCP count and named RMSE, and a `geom_src` join shows
      stale labels. Plan: `docs/knowledge-system-plan.md` §5. **Built 2026-10-01, not pushed:**
      migration 103, the three TS/JS writers, `scripts/backfill_georef_versions.mjs`, one write
      test. Left: `db push` **before** the app deploy, regenerate types, run the backfill with
      `--apply` (it prints the exit query; the 2026-10-01 dry run counted 592 maps, 21 history
      files, 584 live files needing a history copy, 0 unparseable, one history name that is not a
      stamp and five root files not keyed by uuid), then the four writers named in plan §5 record
      their own rows.
- [ ] **`rewarp-on-sync`** — a synced georeference leaves its labels on the old one. Measured
      2026-10-01: 1882, 1895, 1898, 1923 and 1942 carried stale `geom_src`. The one-off repair
      **ran 2026-10-01**: `scripts/oneoff/fix_saigon_1942_1968.mjs` queued 5 `warp` jobs, and all
      5 maps' labels and footprints now carry the current `geom_src`. The item is making the sync
      script and
      `mirrorAnnotation` queue the `warp` job themselves. Exit: after a sync, no label or footprint
      on that map carries an old `geom_src`.
- [ ] **`georef-flag-one-meaning`** — the code has three different tests for "is this map
      georeferenced", and they disagree:
      - `api/search/+server.ts:368,395` (the facet) tests `allmaps_id` alone, so the 480 Indochine
        halves made by our pipeline count as not georeferenced;
      - `data/supabase/footprints.ts:62` (the label-map picker) also requires `allmaps_id`, which
        excludes the same halves;
      - `fetchGeoreferencedMaps` (`data/maps/service.ts:119`) accepts `allmaps_id` with no status
        filter, so signed-in users get 267 drafts whose `allmaps_id` has nothing behind it on
        Allmaps.

      `is_georeferenced` already exists. Exit: every "georeferenced" test in `src/` reads that one
      column.
- [ ] **`size-check-fails-open`** — `sourceSizeMismatch` (`src/lib/core/iiif/sourceSize.ts`, and
      its copy in `sync_district4_annotations.mjs`) returns "no mismatch" whenever `info.json`
      does not load. That was meant for the first mirror of a map. But while the worker was 404ing
      the 1942 sheet, the 2026-10-01 sync ran with no size check at all. Exit: an unreachable
      `info.json` on a map that already has tiles refuses the write; only a map with no tiles yet
      passes.
- [ ] **`allmaps-drift`** — review what volunteers have changed on Allmaps before anything syncs
      it. `node --env-file=.env scripts/georef_contributions.mjs`, 2026-10-01:
      - Vinh Yen `2bd040e9` (draft) went from 4 to 25 GCPs and needs review.
      - Hà Nội `0a8b92dc` has a suspicious 3-point mask; don't sync.
      - Palanca `876dc3c6` was redone on a different scan size; don't sync.
      - 1942 `eca788e5`: the bad GCP `[10504, 2356]` still has to be deleted in the Allmaps
        Editor.

      Exit: the report shows no drifted map whose difference is unexplained.
- [ ] **`georef-figures-refresh`** — the published georeference error figures predate this
      week's re-georeferencing. Re-measured 2026-10-01 with `georef_error.py`, similarity
      RMSE / worst point:

      | Sheet | GCPs | RMSE | Worst | Old figure |
      |---|---:|---:|---:|---|
      | 1882 | 8 | 12.3 m | 19.9 m | 12.7 m / 27.7 m on 10 GCPs |
      | 1895 | 10 | 26.7 m | 55.0 m | |
      | 1923 | 10 | 15.4 m | 31.0 m | |
      | 1942 | 8 | 33.6 m | 53.0 m | |
      | 1959 | 10 | 14.0 m | 22.9 m | |
      | 1968 | 15 | 9.0 m | 20.1 m | |

      Still citing the old numbers: `work/analysis/district4/georef_error.md`,
      `docs/journals/260921-sheet-overlap.md:82`, `docs/paper/related-work.md:628` and the 1882
      hash pinned in `evidence-chain-plan.md` step 1 (now `93c4487e621f83c9`). Exit: each cites
      a figure together with the GCP set it was measured on.
- [ ] **`mask-names`** — "mask" names three things: the georef mask (annotation SvgSelector), the
      neatline (`triage.neatline`) and layout regions (`triage.regions`). The neatline editor
      writes the first from the second. Name them in `docs/conventions.md`. Exit: no doc or comment
      uses a bare "mask" for more than one.

## Survey layer and catalog

- [ ] **`series-identity`** — migration 105 (in production, verified 2026-10-04) adds stable
      `series` UUIDs and synchronized `series_id` links on maps, cells and institution items, so
      renaming a map's display label preserves membership; 104's `series_key` stays as a
      compatibility key. Still open: the catalog series facet and `seriesIndex.ts` still match
      `maps.collection`; persisted layer references; and curated non-survey groups such as city
      plans.
      Do not close on local SQL checks. Exit: no series fact lives only in `extra_metadata` and the
      deployed readers use stable identity. Plan: `docs/knowledge-system-plan.md` §1.

- [ ] **`multi-printing-cells`** — preserve `series_cells` as one index row per cell; do not widen
      its primary key and count printings as cells. Pending branch migration 106 adds independent
      `sheet_printings` rows linked by cell UUID, with optional reviewed links from source items and
      map scans. It does not guess printing identity from years/edition labels or backfill old rows.
      Still open: review margin/catalog evidence, exercise the approved pilot cells, roll out readers
      and preserve W/E/assemblage and standalone cases. Exit: the deployed coverage page lists every
      public printing and every unresolved item without inflating the cell denominator.
- [ ] **`cochinchine-index`** — Cochinchine 1:25,000 is the next survey to index — 826 sheets across
      three series, Saigon
      and the Mekong delta, top of the scout queue at `/admin?tab=scout`. Pattern is
      `scripts/oneoff/import_indochine_series_sheets.mjs`; union every edition of the survey, not
      one.
- [ ] **`l909-index`** — no coverage page, no /explore link. Narrower than it looks: the DB-filing
      half is already done in production — `fix_l909_series_index.mjs --apply` has run, all three
      sheets carry one `collection` string (`AMS L909 — Việt Nam City Maps 1:12,500`) and
      consistent `extra_metadata.series`/`edition`. What's missing is a `series_cells` row set —
      someone still has to decide what the survey contains beyond the three held sheets.
- [ ] **`titles-from-sheet`** — not from the catalogue. CartoMundi's spellings are
      French colonial transcriptions — `Yên-Dinh` is half-accented for Yên Định and reads as an
      error. Deliberately not applied; it sits behind `--names` in
      `backfill_indochine_descriptions.mjs`. OCR the title block instead.
- [ ] **`vi-survey-string`** — `'All sheets in this survey'` was written by a non-speaker. Wants a
      native check.
- [ ] **`coverage-page-weight`** — the L7014 page is ~500 kB of HTML for 627 rows, server-rendered
      per request. Fine
      today; revisit before Cochinchine's 826 lands.

- [ ] **`catalog-list-speed`** — `/api/search` rebuilds the same public list for every reader:
      2.4–3.3 s unfiltered, `cf-cache-status: DYNAMIC`, two sequential 1,000-row pages
      (`readAll`), then a 1.3 s blocking render of 1,038 rows (15,350 DOM nodes). Measured
      2026-10-05 from a laptop against production; the gzipped body is only 153 kB, so the cost is
      server time and first paint, not bandwidth. Do: `Cache-Control: public, s-maxage=300,
      stale-while-revalidate` on non-staff responses only (staff see drafts; a publish may take up
      to 5 minutes to reach the public — accepted); fetch the pages in parallel; render ~100 rows
      and extend on scroll, table and grid, slicing after grouping; stop sending `extra_metadata`
      once no reader is confirmed. Cloudflare Pages may not honour the header on a Function
      response — if `cf-cache-status` never reads `HIT`, build a static snapshot on deploy/edit.
      Exit: rows visible in about 1 s on a cold load (was 4.5 s), `HIT` on the second request.
      **Built, not yet deployed:** the Cache API (Functions run before the CDN, so the header alone
      caches nothing; `X-VMA-Cache: HIT|MISS` says which path answered), two pages in parallel,
      100-row slices, `extra_metadata` dropped. What is left is the production probe.
      Plan for this item and the four after it: `docs/catalog-plan.md`.
- [ ] **`catalog-columns`** — the public list shows columns that do not vary. Of 1,038 public
      maps: all are `is_georeferenced`, 1,000 of 1,036 `map_type` are "topographic", `location`
      is filled on 46 (34 of the 36 maps with no series — the city plans — and almost none of the
      1,002 survey sheets). Replace Status/Type/Area in the public table and in `ArchiveMapRows`
      with series + sheet number + institution; keep Status/Type for staff. Promote the series
      facet out of the collapsed Filters disclosure and into /explore's rail; swap the six period
      buckets for a year range with a histogram (1950s + 1960s hold 680 of 1,038); add an
      institution facet; a "Surveys / Plans & other" switch decides whether Area applies. Show the
      sheet number beside the name — 23 names repeat. Long fields load when the drawer opens.
      Depends on `georef-flag-one-meaning`. Exit: no public column that is a single value.
      **Built, not yet deployed:** the table columns, year range + histogram, institution facet,
      Surveys / Plans switch, Type for staff only, Area as the province (`region`); the rail's rows
      (`ArchiveMapRows`: sheet number and survey under the title, no Type column), the series
      select above the Filters disclosure (the engine derives the surveys from its rows when a
      caller passes none), and the description, rights and physical description fetched when the
      drawer opens (`fetchMapLongFields`, 170 kB off the list). Close it once it is live.
- [ ] **`catalog-local-search`** — search the public maps in the browser instead of through
      `/api/search`: every field `search_vector` indexes is already in the list row. Accent-fold
      and prefix-match per token — `hue` cannot find `Huế` today, because the index is the
      `simple` config. Keep the server call for OCR labels and places only; the palette's slim
      mode is unchanged. The `^\d{4}-\d$` sheet-number match moves with it. A library
      (MiniSearch) only if typo tolerance is wanted. Exit: typing never waits on the network.
      **Built, not yet deployed** (`localSearch.ts`; the server's map search stays for the
      palette). Close it once it is live.
- [ ] **`map-json-to-columns`** — **Built, not yet pushed or deployed** (mig 110 adds `maps.edition`
      and copies `source_archive = 'PCL'` into `holding_institution`; the search API, the series
      page and `SeriesManage` read the columns; `LIST_COLUMNS` and the API's full set share
      `MAP_BASE_COLUMNS`; the edit form and `bulk_upload_local.sh` stop writing the JSON copies).
      Left: `extra_metadata.mirrors_original_for` is still filtered in JSON
      (`catalog/[id]/+page.server.ts`, `fetchSeriesSheets`), and `source_archive` stays a JSON tag
      the L7014 scripts use to tell PCL from TTU. The old JSON copies of `sheet_number`,
      `sheet_half` and `edition` stay on rows nobody re-saves. Close it once 110 is pushed and the
      code is live.

## After 7.3

- [ ] **`inspect-mode-fate`** — it may now be dead weight. /catalog/[id] serves the same tiles,
      drafts
      included, which was inspect's last stated job. Check the two things the record page does not
      obviously carry over — the tool map picker, and the plain level0 look — before deleting
      `features/contribute/inspect/`. Exit: either the directory is gone and `SCAN_MODES` has three
      entries, or `scanModes.ts` says which job keeps it alive.
- [ ] **`slug-alias-proof`** — `map_slug_aliases` is empty on production, so the retired-name 301 is
      exercised only by
      the local write test. Exit: after the first re-mint, one `curl -sI` on the retired name
      showing a 301 to the live slug.
- [ ] **`slug-in-payloads`** — a label hit and a footprint submission carry only `map_id`, so those
      links
      take the uuid fallback and cost a redirect. Adding `slug` to the two payloads lands the common
      path directly. Exit: no `/catalog/<uuid>` link is generated by a page the archive renders.
- [ ] **`cells-test-ci`** — it cannot run in CI — it needs the 42 MB gitignored catalogue
      dumps. Run it by hand after any catalogue re-fetch; that is when a new spelling arrives.
- [ ] **`unify-mirror-step`** — `tile_map.sh` and `bulk_upload_local.sh` each do their own `maps`
      insert, and
      `ingest_indochine_nakala.mjs` shells into the first. Unifying the mirror step waits on the
      container decision in `docs/journals/260914-iiif-space-efficiency.md` — packaging it first
      means packaging it twice.

## Shapes — segmentation, and the OCR ↔ shape join

- [ ] **`river-reconstruction`** — ship approved 1882 water from the frozen v3 mask
      `water-1006337f.png`, with hand correction of creek heads, the hatched Canal de ceinture
      and dry citadel ramparts. The v1 method scored 96.5% on 289 blind owner point labels;
      v3's 74/74 on batch 4 also holds for v2 and does not establish an improvement.
      Exit: owner-reviewed 1882 water polygons approved and rendered on `/explore`.
      1898 is deferred until 1882 ships. Current scope: `docs/image-processing-1882-plan.md`;
      evidence: `docs/research/river-reconstruction.md`.
- [ ] **`seg-eval-set`** — the eval harness is blocked on data, not code. The OCR side exists
      (`work/ocr/EVAL-BASELINE.md`); segmentation needs ~20 hand-labelled Saigon tiles before any
      number means anything. Same blocker as `district4-table`.
- [ ] **`colour-blocks`** — the sheet-colour pipeline exists (`colour_blocks.py`, CPU only), and
      later passes moved 1882 best-match mean IoU to **0.343** on 24 `land_plot` traces and
      **0.355** on 17 `building` traces. The early P1 null and its retracted P3 interpretation
      remain in `docs/journals/260918-colour-blocks.md` as the method history, not the current
      verdict. The traces are selected and do not measure precision; the 46-trace SAM2 LoRA has
      no independent test set. Exit: the bounded `shape-precision` reference window, a measured
      false-positive rate, and a MapSAM2 run prompted by the *same* colour prior before claiming
      one method improves the other. River is tracked separately under `river-reconstruction`.
      1882 and 1898 are run independently: swapping their auto-derived constants costs 1882 0.08
      land_plot IoU and its road proposals (`docs/journals/261001-colour-pair-1882-1898.md`).
- [ ] **`shapes-deferred`** — the gazetteer link and the LoRA shot set. Neither has a gate;
      both wait on `seg-eval-set` having data.

**The old B8 is done**, delivered as the engine (migration 066 — PostGIS,
`geom`/`geom_src`/`geom_rmse`), despite an unticked box surviving in the record.

## Search — label search, gazetteer, press, the context API

- [ ] **`doling-review`** — measure the extractor before growing it. Tim Doling's *Historic
      Vietnam* export (268 posts, 3.1M chars) yielded **89 colonial ↔ modern name pairs** —
      `work/research/doling/street-name-pairs.csv`, 43 `street`, 34 `unclear`, 10 `address`, 2 `building`,
      every row carrying its post title, date and URL. He agreed on 2026-09-22 to be cited. There
      is no accuracy number for the extraction, which is `shape-precision`'s problem in another
      corpus: unfalsifiable until measured. The author's own markup is the cheapest ground truth
      available. Exit: a precision figure with its sample recorded, and his corrections kept as the
      eval set. Detail: `docs/search-plan.md` §E3b.
- [ ] **`gallica-text-harvest`** — primary sources, politely, offline. Gallica exposes OCR'd full
      text; **NLV does not** — verified 2026-09-22, the article view offers `img` only and the
      issue PDF 404s without a session `key`, so NLV stays a consumer of names
      (`press-from-gazetteer`) and never a source of them. Its query file is already generated at
      `work/research/doling/nlv-queries.txt`. Write a harvester on the `scout_nlv_press.mjs` pattern —
      resumable, fixtured, `--selftest` — **never through `src/lib/server/gallica.ts`**, which is a
      per-reader lookup with no rate limiter. Titles: *Annuaires de l'Indochine*, *L'Opinion*,
      *La Dépêche d'Indochine* — the same three that make the Ian Gregory letter concrete.
- [ ] **`attested-variants`** — reviewed pairs into `place_names.variants[]` (mig 067), feeding
      `spellingVariants`' `extra`. One normalisation rule, not a third — see
      `dictionary-on-place-names`. Exit: `/api/press` for "Đồng Khởi" returns a hit reachable only
      via "rue Catinat", and says where the variant came from.
- [ ] **`ocr-suggestions`** — a suggestion side-table, never `text_validated`. That column is what
      `eval.py ocr` scores against, and a dictionary writing it launders model output as ground
      truth — the n=89 contamination in `work/ocr/EVAL-BASELINE.md` is the same error already paid
      for once. Matching needs no new code (`f_unaccent` + `word_similarity`, mig 065). Exit: the
      eval baseline is unchanged after a suggestion run, and an accepted fix carries its citation.
- [ ] **`source-agreement`** — a reading attested on a sheet *and* in a dated period source is two
      sources agreeing. Feeds `ocr-merge-evidence`. Exit: a reviewer sees which sources agree, not
      a blended score.
- [ ] **`gazetteer-depth`** — `place_names` exists; the view is only as good as the corpus, so this
      waits on ≥ 20 maps carrying extractions. Same queue as 4b/4c.
- [~] **`temporal-fabric`** — code done 2026-09-02. Left: one real Colab `seg` run
      (`colab-seg-run`) and review of what it writes.
- [~] **`corpus-growth`** — the georef sprint by decade gap. `three-point-residuals` and
      `tonkin-review` are its two halves; runs
      whenever there is human time.
- [~] **`sheet-overlap-floor`** — sheets on one ground (2026-09-21). Two Saigon plans sixteen years
      apart, each warped by its own GCPs, overlap to ~50–100 m, and the limit is the scan rather
      than the transform. Detail: `docs/journals/260921-sheet-overlap.md`.
- [ ] **`district4-mirror-sync`** — **status 2026-10-01:**
      - (1) is done: `georef_contributions.mjs` reports the D4 mirrors in sync, and every label on
        them was re-warped.
      - (2) is still open.
      - (3) has changed: Allmaps still holds the bad 1942 point. Our copy dropped it again
        (`fix_saigon_1942_1968.mjs`; 33.6 m RMSE on 8 points), so the two now differ on purpose
        until the point is deleted in the Allmaps Editor.

      Original: three separate faults found chasing "the 1942 sheet looks off"
      (2026-09-22/23), none yet closed. The tooling bug is fixed (`allmapsEditorSourceUrl` now
      trusts the annotation's real source instead of always skipping R2, `0607cc26`, shipped but
      not confirmed deployed) — this item is what's left, which is data, not code. (1) 4 of the 6
      District 4 sheets' stored annotation mirrors are stale against the live Allmaps annotation
      (1923 worst: 13 months out of sync, 501 OCR extractions resting on it) — `sync-allmaps` is
      the fix but is a manual button with no trigger, needs an authenticated admin session to run.
      (2) `/explore` shows confirmed real (not display-bug) misalignment near "Pont tournant" —
      the 1942 sheet's genuine 15.9m/27.3m RMSE floor — fixable with one more independent ground
      point on the actual swing bridge, not yet sourced (satellite cross-reference needed;
      `drop_1942_gcp1.mjs` is mid-flight on the one known-bad point). (3) the *official*
      Allmaps-hosted copy of 1942 is broken at 117m RMSE and undecided whether to fix — production
      doesn't read it (`maps.annotation_url` wins over `allmaps_id`) unless someone clicks "Sync
      from Allmaps" for that map, so it's a landmine, not live damage. Exit: all three resolved or
      explicitly deferred with a reason; full trail in the `georef-tooling-district4` memory.
- [ ] **`building-attributes`** — → OSM tags → LoD2 — deferred until the fabric is reviewed on ≥ 3
      maps. `tags jsonb` lands with its first writer.

## Walk — one route on a phone, the sheets underneath

One District 4 route on foot, warped sheets underneath, old names on top — HACW forked for Saigon.
Plan: `docs/walk-plan.md`.

- [ ] **`walk-the-route`** — on a phone, and decide whether offline is real. If it is not, this
      whole
      track collapses into `/trip/[id]` plus a year slider, and the fork should be deleted rather
      than maintained. **Nothing else in Walk is worth starting first.**
- [ ] **`field-photo-pilot`** — after `walk-the-route`, test geotagging and present-day building
      height estimates with Quang Huy Nguyen on one short District 4 segment (about 10–20 photos).
      Record each photo's location, how it was located, positional uncertainty, candidate building
      match, height estimate, estimation method and validation evidence. Check failures from missing
      GPS and distant/oblique views before designing any archive write path. These are observations
      of the **present-day** scene: never attach a height inferred from a current photo to an 1882
      or other historical footprint as though it described that map year. Exit: a small reviewable
      dataset and error/uncertainty report; only then decide whether photos belong in Walk and
      whether validated present-day heights should feed `building-attributes`.
- [ ] **`sheet-pmtiles`** — `scripts/sheet_pmtiles.py <mapId> --bbox` — one sheet drawing in
      MapLibre proves the
      chain. IIIF level0 tiles are not web-mercator XYZ, which is why every sheet must be warped
      once, server-side. **The PMTiles-vs-COG container choice is gated here** on one question: is
      on-the-fly rendering — a real IIIF level 2 — ever wanted? If yes, build COGs; if no, PMTiles
      is simpler. PMTiles saved 0% of bytes when measured 2026-09-14, so the decision is about
      capability, not size.
- [ ] **`year-slider`** — warp 1923 + 1968, then the slider — one raster basemap entry per year, the
      `l7014` pattern already in `BASEMAP_DEFS`.
- [ ] **`story-contract`** — `contracts/story.schema.json` + `GET /api/stories/[id].json`, validated
      in the write
      smoke. Independent of the two above and it jumps `platform-design.md` §6's queue: it needs
      neither the
      engine nor `packages/contracts`.
- [ ] **`hacw-fork`** — fork HACW → D4 content, Saigon extract, `pull-archive.mjs`, `checkStory()` —
      linked by
      frozen JSON + PMTiles, never a shared runtime.
- [ ] **`names-layer`** — `gen-hero-fabric --bbox` per sheet → the names layer.
- [ ] **`stops-and-quizzes`** — stops, quizzes, stamps — content only, machinery unchanged.
- [ ] **`district4-change-story`** — after the current georeference pass: improve georeference
      quality
      with the river-edge colour pass, then segment and process the D4 sheets alongside the 1882 and
      1898 work (1898 is outside the six-sheet AOI).
- [ ] **`ohm-vector-pilot`** — with the sheet visible in its editor — one compact 1882 Saigon area,
      one
      class. VMA's IIIF image plus its accepted georeference can be exposed as a warped XYZ URL via
      the Allmaps Tile Server and loaded as custom imagery.

## OCR setup — open improvements from the 1959 re-run (2026-09-10)

Measured in `docs/pipelines.md` §"Reading a sheet's margins". Cheapest fix first.

- [ ] **`triage-scan-identity`** — triage must record which image it was computed for. Store
      `img_width`/`img_height` in the
      saved triage and refuse a triage computed against a different scan. This is the smallest
      concrete case of
      `stale-after-change`.
- [ ] **`queue-age-in-status`** — report the oldest queued job's age. One `layout` job sat queued
      24 h because no worker was up and nothing said so.
- [ ] **`ocr-reads-regions`** — not just `main_map`, not just `main_map`. The
      margins were the best-value calls on the sheet (9.8 rows/call vs 8.7 for a body pass) and the
      pipeline never made them: `title` → metadata, `legend` → symbol key, `name_list` → the index.
- [ ] **`legend-flag-fails-loud`** — `--legend` fails silently today. Both 1959 passes carried it
      and it did nothing — it needs a
      scout cartouche, `--scout` is skipped when a neatline pins the crop, and it aims at the title
      block anyway. Make it fail the job.
- [ ] **`index-region-reader`** — `ocr.py index --region`, the working table reader as a subcommand:
      ruled columns found
      locally, one column group per call, contiguity invariant, refuse the write when it fails. Most
      city plans in the corpus carry a directory like this one's.
- [ ] **`grid-from-ticks`** — not from a 2048 px overview. `ocr.py grid` read 12 rows
      where the sheet has 9. Correct, it also lets index entries whose numeral was never found sit
      at cell centre, and arbitrates numeral collisions.
- [ ] **`integer-gate`** — gate integer extraction per sheet (`seq-v1-idx` vs `seq-v1`) on whether
      the layout pass
      found a numbered index, not on a person remembering. Classify bare integers as `legend_ref` by
      regex; the model ignored an `index_key` category in 114 of 114 cases.
- [ ] **`merge-keeps-box`** — `merge` drops the label box today. 514 of the 1959 rows carry a
      non-zero `rotation_deg` but no
      `label_w`/`label_h`, so the review canvas only ever gets a point.
- [ ] **`legend-numeral-misses`** — hand review of numbered legends done 2026-10-05 (positions now
      `px=` image pixels, PR #40). **1959:** numeral detection is good; it misses numbers in dense
      blocks and numbers sitting on a grid line or cell corner (likely cut at a tile edge — tile
      overlap, plus a check that the in-cell test tolerates a boundary). **1923:** poor — no printed
      grid, so no in-cell check and no fallback; the numerals are hard to read; other numbers on the
      sheet compete; and the model reads numbers *inside the legend* as map references. Fix: read
      numerals only inside the layout pass's map body (`ocr-reads-regions`). 168 of 182 entries are
      hand-placed; **14 still sit at a wrong OCR numeral position and were not corrected:** 36, 53,
      73, 74, 78, 93, 94, 97, 102, 109, 145, 146, 177, 179. Place them in `/scan?mode=legend`.

## Debt — burn down when it hurts

- [ ] `/scan?mode=shapes&tab=validate` back-link: the round icon button overlaps the "Contribute"
      label.
- [ ] `/explore` Display row: the "Side-by-side" button label is clipped.
- [ ] `/explore`: adding a series layer switches the left rail to the Picked tab, which unmounts the
      browse list — so the "tap again to remove" the hint promises is not reachable from where the
      reader just tapped (pre-existing, found 2026-09-13).
- [ ] API response shapes → `{ ok, data }`.
- [ ] `tokens.css` grey ramp → fold the `color-mix` hacks.
- [ ] 69 eslint warnings, mostly unkeyed `{#each}`.
- [ ] Files > 400 lines: MapEditHostingTab 584, CreateMode 583, OcrSidebar 562 (→ OcrTable, needs
      OCR test data), MapEditPipelineTab 467, TripPlayback 462, CatalogTable 450,
      StudioAnimationPanel 412, explore/+page 407, TriageSidebar 407, trip/[id]/+page 405,
      StudioMode 405.

## Infrastructure

- [ ] **`preview-env-vars`** — the Preview environment has none. Production holds all five, Preview
      holds none, so
      every preview build fails at the first `$env/static/*` import. Dashboard only —
      `wrangler pages secret` has no environment flag in any current version.

## Order

**Do next**, top to bottom, supersedes everything below it. `corpus-growth` still runs whenever
there is human time — `three-point-residuals` and `tonkin-review` are its two halves.
`walk-the-route` comes before anything else in Walk is worth starting; `story-contract` is
independent and can run alongside Search. `evidence-chain` needs only the 1882 sheet, whose
evidence is already reviewed, so it waits on nothing above it — but its step 1 must confirm the
1882 annotation mirror against `district4-mirror-sync` first. Debt never blocks.

Previously: A1–A4 → B1 → B2 → C0 → C1 → B3 → B4 → B5 → C2, then E1 → E2 → E3. Those codes are
history; they still name the closed items in `docs/roadmap-record.md`, and the map from them to
the names used here is at the bottom of this file.


## Renamed from

The record and older commits use letter codes. This is what they are called now. Codes not listed
belong to work that is closed; they still name it in `docs/roadmap-record.md`.

| Old | Now | Old | Now |
| --- | --- | --- | --- |
| N1, I3 | `l7014-iiif` | 3b | `auto-priority` |
| N2 | `three-point-residuals` | 3c | `gemini-second-key` |
| N3 | `indochine-100k-ingest` | 3h | `hand-triage` |
| N3a | `indochine-100k-licence` | 3 | `queue-the-pass` |
| N4, I5 | `stale-after-change` | 4 | `drain-the-queue` |
| N5, I4 | `shape-precision` | 4b | `dictionary-on-place-names` |
| N6 | `graticule-georef` | 4c | `dictionary-review` |
| I1 | `next-action-view` | 6 | `search-acceptance` |
| I2 | `ocr-merge-evidence` | 7 | `colab-seg-run` |
| I6 | `review-ordering` | 8 | `district4-table` |
| C5 | `seg-eval-set` | 9 | `clahe-measurement` |
| C6 | `colour-blocks` | 10 | `press-from-gazetteer` |
| E1b | `gazetteer-depth` | 11 | `street-name-pairs` |
| E2 | `temporal-fabric` | 12 | `district4-figures` |
| E4 | `corpus-growth` | F0 | `walk-the-route` |
| E5 | `building-attributes` | F1 | `sheet-pmtiles` |
| E6 | `sheet-overlap-floor` | F2 | `year-slider` |
| B8 | done, shipped as E2b | F3 | `story-contract` |
| Track C | Shapes | F4 | `hacw-fork` |
| Track D | Debt | F5 | `names-layer` |
| Track E, "Time machine" | Search | F6 | `stops-and-quizzes` |
| Track F, "Time walk" | Walk | | |
