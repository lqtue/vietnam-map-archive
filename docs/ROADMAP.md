# Roadmap — open work (updated 2026-09-22)

**Everything in this file is open.** Nothing closed lives here: the record of finished passes, with
the measurements and the defects each one turned up, is `docs/roadmap-record.md`, and the rules that
keep getting re-learned are `docs/lessons.md`. Close an item by moving it there, not by ticking it.

Ordered where order is claimed. Each item names the check that says it is finished.

## Do next

The foundations pass, opened 2026-09-21 and superseding the OCR-corpus list that ran before it.
Why foundations rather than another method: every elaborate pass in the record ended by finding a
basic thing broken — no OCR run could read an R2-hosted map at all, a 31.8% white-hole overview the
model scored 7/7 on, a fixed pixel tile being a different amount of ground on every sheet, the
L7014 mixed-datum fault, 56 published sheets drawing nothing. So: georeference quality, segmentation
measurement, metadata that maintains itself, and corpus size.


Ordered. Each item names the check that says it is finished; the detail is in the section it links.

- [ ] **N1 — Rebuild and verify L7014** (= I3). The live `l7014-20260913` mosaic places sheets
      about **470 m out**, the datum fix is committed, and the warp/tile/upload has never run. This
      is the only item on this list that is serving wrong data to readers right now, which is why
      it is first. Preserve the old build until the replacement passes. Exit: `fit` and
      `geo_audit.mjs` both clear on the new build, and the old one is retired only after.
      **Phases A+B run 2026-09-21** on key `l7014-20260921` (436 sheets, matches the 2026-09-20 dry
      run). `geo_audit.mjs` found one real FAIL beyond the known `fit` outliers: `hue-l7014-6541-4`
      (public, 3 GCPs) sat 5,391 m from printed cell 6541-4, while a draft duplicate
      `hue-l7014-6541-4-2` (4 GCPs) sat correctly on it. **Fixed 2026-09-22**: swapped the two
      rows' status and re-pointed `series_sheets` cell 6541-4 at the `-2` row.
      `geo_audit.mjs --key l7014-20260921` now reports **0 FAIL** (47 WARN, all pre-existing
      draft-sheet annotation gaps, unaffected by the swap). `fit`'s two known-bad sheets (`6630-4`,
      `6349-4`, distorted outlines, see `work/l7014/regen/REGEN.md`) are expected on every run and
      not part of this gate. Still open before N1 closes: `tile`/`upload` have never run — gated on
      a paper-framing decision (`docs/paper/draft.md` §7.6 / `blind-by-construction.tex` cite the
      *unrebuilt* archive as evidentiary) that belongs to the user; and `rasterSeries.ts`'s
      hand-carried `sheets: 452` needs updating to 436 (with `tests/series-rows.spec.ts:20,96`) as
      part of that same pass. Separately, **a new bug surfaced while checking this**:
      `series_sheets.bbox` stores the raw unshifted Indian-1960 graticule instead of the corrected
      WGS84 lattice, off by 448–498 m on every one of the 627 cells in the L7014 index — not yet
      fixed, not yet its own item; do that first if picking this back up. See `.claude/handoff.md`
      for the full trail.
- [ ] **N2 — Give the 11 remaining three-point sheets a measurable residual.** A 3-GCP affine fit
      has zero degrees of freedom, so its RMSE is identically 0 and a sheet can be badly wrong
      while reporting nothing. This is not a backlog item, it is a hole in the quality signal
      itself. A 4th point on each buys a number where there currently cannot be one. Do the five
      one-point GCP fixes and the 1912 Saigon-Cholon (three near-collinear points in one corner) in
      the same sitting. The 1880 *Plan annamite d'Hanoi* is 802 px and needs a new scan before it
      needs GCPs. (Was 12 — `hue-l7014-6541-4` dropped off the list 2026-09-22: its N1 swap
      promoted the 4-GCP `hue-l7014-6541-4-2` in its place.) Exit: no georeferenced sheet in the
      corpus sits on fewer than 4 points, and `modern_prior.py --sweep` reports a residual for
      every one.
- [ ] **N3 — Finish the Indochine 1:100,000 ingest.** 578 of 581 half-sheet scans un-ingested; the
      path is proved on 3 (real rows, tiled, serving). Cheapest corpus growth available — a batch
      run, not a project. 561 first (100% ready IIIF URLs), then 325 (exercises the constructed
      `f110IdNakala` path at scale). Grep each run for `TILING FAILED`; the script leaves a
      pixel-less `draft` row rather than failing loudly. Exit: `/catalog/series` renders both
      surveys sensibly, and `scripts/check_series_index.mjs` is still clean. See
      `.claude/handoff.md`.
- [ ] **N3a — Settle the 1:100,000 licence before N3's ingest run mints 578 rows.**
      Probed 2026-09-21 with the same
      per-item method that settled the 25,000 series, `10.34847/nkl.3490q3l6` (serie 561) also
      returns `"CC-BY-4.0"`, not NC-SA — and both series' CartoMundi records name the *same* Nakala
      collection DOI (`10.34847/nkl.d2a82952`). So the per-item field does not discriminate between
      them, and whatever established NC-SA for the 100,000 series was not re-verifiable: the Nakala
      collection page now demands SSO. `scripts/oneoff/ingest_indochine_100k_nakala.mjs` writes
      CC-BY-NC-SA-4.0 into every row it mints. Settle this **before** the N3 ingest run mints 578
      more of them — over-claiming a restriction is cheaper than under-claiming one, but a
      collection of 578 rows carrying the wrong licence string is expensive to correct.
- [ ] **N4 — Mark stale work after an upstream change** (= I5). Already bit us once and left no
      trace: re-scanning the 1959 sheet emptied `maps.triage`, and had the triage survived, the
      saved neatline would have cropped the **old** scan's pixels while looking entirely valid.
      Record the two observed dependencies — a replaced scan invalidates triage and all pixel work;
      a changed georeference invalidates ground coordinates, warps, exports and mosaic checks — and
      show the rebuild set. Exit: a test correction names exactly what must be redone and keeps
      what is still reusable.
- [ ] **N5 — Measure shapes before tuning them** (= I4). There is a recall-ish number and **no
      precision number at all**, so every segmentation change to date is unfalsifiable. Trace one
      bounded 1882 window completely, run `seg_eval --window`, keep machine predictions out of the
      ground truth by construction. Related and blocking the District 4 table: **there are no
      footprints inside District 4** — all 46 volunteer traces are in District 1, the nearest 68 m
      north of the Bến Nghé canal. Review is not the blocker; tracing the peninsula is. Exit: a
      precision figure alongside the recall one, with its sample and limitations recorded beside
      it.
- [ ] **N6 — The 62 ungeoreferenced drafts, by machine.** Biggest single jump available (40 usable
      sheets → 102) and the least verified thing on this list. The SGI Tonkin series prints a
      graticule in **grades from the Paris meridian** (`grades × 0.9 + 2.337229` = degrees east),
      each sheet's number, and an 8-neighbour index diagram, on a 7-column series grid. **Evidence
      is one sheet read by eye** (Cua Thai Binh 1905), whose latitude labels were too small to be
      sure of. Read the graticule on three sheets and confirm the latitudes **before building
      anything**. Gate on `modern_prior.py --sweep`. The named-institution lead (3 confirmed
      survivors out of 28 names on one sheet) is a seed and a cross-check, never a fit on its own —
      do not oversell it.


## Also open — cheap, no ordering claim

Do them when the surrounding work opens the file.

- [ ] **`series_sheets.held_by` / `map_id` is a snapshot, and nothing maintains it** — no trigger,
      no function, only the one-off importers. So the day anyone georeferences one of the 123
      obtainable L7014 sheets, or publishes a draft, the index still says *gap* and the coverage
      page still draws it missing: right about the survey, wrong about us, with no symptom but a
      plausible-looking number. Real fix: derive `held_by`/`map_id` in a view, or a trigger on
      `maps`. Exit: publishing a draft moves its cell to *held* with nobody running anything.
      **Until then there is a detector, which is not the same thing** —
      `node --env-file=.env scripts/check_series_index.mjs` catches an adrift cell, a dangling
      `map_id` and (since 2026-09-15) a `maps` row whose `sheet_number` the index does not contain
      at all, which is the typo case drift can never see. Clean on production 2026-09-15: 0/0/0 over
      706 sheets. Run it after any publish, georeference or re-import.
- [ ] **Sixteen one-off scripts write on a bare invocation; nine are converted, seven are not.** The
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
- [ ] The colour/wash pre-pass is a **confirmed null**, not an unknown: every saturated pixel on
      the 1882 sheet is hue 0–60° and `compute_tile_colours` looks at 60–260°. If colour
      segmentation is to do real work, that window is the starting point — and it needs a second
      sheet's histogram before the new one is trusted.
- [ ] **21 draft L7014 sheets carry an `annotation_url` that 404s or 500s** — all created
      2026-09-13/14, `georef_done` true in the row while the annotation store holds nothing
      (measured 2026-09-21 by the `modern_prior.py --sweep` re-run). A different failure from N2's
      point-count trap: there is no thin fit to distrust, there is no fit. Exit: every row
      claiming a georeference resolves to a real annotation, or stops claiming one.
- [ ] **The 1912 Saigon-Cholon cannot be fit at all.** `saigon-cholon-et-environs`: 3 points, SVD
      condition ratio **0.0302** against `scale.py`'s `MIN_GCP_CONDITION` floor of 0.05, so
      `fit_sheet()` returns `None` rather than an exact-but-uninformative transform. Recorded on
      2026-09-11 as "three near-collinear points in one corner", which understates it. Folded into
      N2; noted here because it is the corpus's clearest single example of the guard working.
- [ ] Two Huế sheets (800×628, 754×877) are under the scout's 1024 px floor. They need larger
      scans, which is sourcing, not code.


## The OCR corpus drain — the queue behind every empty Track E surface

6 georeferenced sheets of 39 carry extractions, which is why label search, the `/place/` hubs, the
gazetteer and `/api/press`'s spelling variants all look thin for one single reason. Measured budget
is **$31–63 for all 38 maps** on `gemini-3.8-flash`, so cost is not the constraint; unattended
quality is. This run is also the gate on the project's first paper
(`docs/private/260912-postgrad-route.md`) — the toponym measurement needs all 39 sheets, not 6.
Full context and the per-call measurements: `docs/roadmap-record.md`, "The OCR pass".

- [ ] **3h. Triage the first sheets by hand**, one at a time at `/scan?mode=prepare`: draw the
      neatline, click the blank and water tiles down to skip, press **Save triage**. Exit:
      `select count(*) from maps where triage ? 'neatline'` equals the number you meant to do, and
      `enqueue_ocr_all.mjs --dry` lists exactly those.
- [ ] **3c. A second API key, and know the tier.** `gemini_client.py` already rotates across
      `GEMINI_API_KEYS`; 38 maps unattended is the run that needs the spare. Google no longer
      publishes per-model limits — read <https://aistudio.google.com/rate-limit>. Exit: two keys
      set, and the daily request cap written down here.
- [ ] **3. Queue the pass** — `scripts/enqueue_ocr_all.mjs --dry`, then without. It queues only
      triaged sheets, so 3h comes first or nothing is queued at all. Exit: the queued count matches
      the script's own.
- [ ] **4. Drain it** — `python work/worker/vma_worker.py --worker $(hostname)`. Hours, not minutes.
      Exit: `select count(distinct map_id) from ocr_extractions` > 30.
- [ ] **3b. `--auto-priority` in the worker, deferred on purpose.** Reopen once ~5 sheets have been
      triaged and OCR'd by hand, so there is a baseline to judge the automatic grid against. Exit:
      on a triaged sheet it picks a grid within a tile or two of the human one.
- [ ] **4b. Fold `dictionary.py` onto `place_names`.** The script reimplements grouping that
      migration 067's view does better (`place_key` folds accents as well as punctuation: 394
      grouped names against the script's 434 + 66 accent twins). Two normalisation rules for one
      corpus will drift. Keep its own pass only for what the view drops — `legend_entry` rows,
      `--min-confidence`, per-sighting provenance. Exit: the script's ground-name count equals the
      view's, and `--self-check` still passes.
- [ ] **4c. Review the dictionary**, after 4. The first artefact a human can check against the
      sheets: errors invisible one bbox at a time (`ARSENAL DE L`, `HOTEL DU GNRAL`, a bare `Rue`
      seen 14 times) are obvious in an alphabetical list. Exit: the 20 most-sighted names are each
      validated or rejected.
- [ ] **6. E1 + E3 acceptance on production.** Search "Khánh Hội" on /catalog and /explore, land on
      the spot, read the press panel, check a draft's labels are absent when signed out. Exit: hits
      from ≥ 5 maps, and `/api/context?lng=106.70098&lat=10.77653` returns labels.

**Then, in order** (detail in `docs/time-machine-plan.md`, engine design in
`docs/platform-design.md`):

- [ ] **7. E2 step 1 on Colab** — mint a `seg`-scoped worker key, run `vma_worker.py --kinds seg`.
      Exit: one `seg` job goes `queued → done` and writes `footprint_submissions` rows with
      `source='sam-auto'`.
- [ ] **8. District 4 review.** `work/analysis/district4/` is built and self-checking; what is left
      is human. The series is **six** sheets, generated not remembered: 1882 · 1895 · 1923 · 1942 ·
      1959 · 1968. **Blocked on tracing, not on review: there are no footprints inside District 4**
      —
      all 46 volunteer traces sit in District 1, the nearest 68 m north of the Bến Nghé canal. Exit:
      real numbers for those six years, and the approved polygons exported as the C5 seg eval set.
- [ ] **9. Measure `--clahe`** against `work/ocr/EVAL-BASELINE.md`. Exit: a numbered row in that
      file, including a null result.
- [ ] **10. Feed `/api/press` from the gazetteer** instead of its three guessed spelling forms.
      Waiting only on a corpus with more than one map OCR'd.
- [ ] **11. Colonial ↔ current street names** with namesake notes. Needs the source data, not code.
- [ ] **12. Figures for the District 4 table**, once it has numbers. Deliberately absent until then:
      a chart of three zero rows is worse than no chart.

## Evidence and legibility (I-series, planned 2026-09-19)

Deliberately not first: both compound better once N4 means a corrected sheet does not silently
invalidate six downstream artefacts. I3/I4/I5 are live above as N1/N5/N4. Rationale for the whole
system — what a result must retain, and the two kinds of check — is in the record.

- [ ] **I1 — Show the next action for each sheet.** Extend the staff status view with the next
      eligible action and what blocks it; reuse `map_pipeline_status` and the review marks, do not
      build a second queue. Exit: an operator can see whether a sheet needs a worker, a person, an
      image repair or a placement check without reconstructing its history.
- [ ] **I2 — Preserve OCR merge evidence.** `ensemble_items()` keeps the largest self-reported
      confidence even though confidence is not comparable across prompts, and reduces agreement to
      `n_passes` plus a note. Retain every contributing run, reading and box; store agreement as
      structured data. Replay saved run directories into a report before changing database writes.
      Exit: a reviewer can see why two readings agree or disagree, and every signal traces to a run.
- [ ] **I6 — Optional review ordering, after measurement.** A "Needs attention first" ordering built
      from I2's disagreement evidence, compared against the present order on a held-out sample, with
      a random audit of apparently easy rows retained. Do not call a score calibrated until it has
      been tested against human outcomes. Exit: reviewers find more confirmed errors in the same
      time without raising residual error.

## Survey layer and catalog

- [ ] **`series_sheets` can name only one printing of a cell.** Its key is
      `(series_key, sheet_number)`, one row per cell — but the archive holds **10 cells in more than
      one edition**, three with two *published* printings fourteen years apart. Migration 086 hangs
      a printing off the existing key, so the page can say which printing it serves and that others
      exist; the index still cannot enumerate them. Widening the key is the whole item. Exit: a
      coverage page lists both published printings of Indochine cell 1 without either hiding the
      other.
- [ ] **Cochinchine 1:25,000 is the next survey to index** — 826 sheets across three series, Saigon
      and the Mekong delta, top of the scout queue at `/admin?tab=scout`. Pattern is
      `scripts/oneoff/import_indochine_series_sheets.mjs`; union every edition of the survey, not
      one.
- [ ] **AMS L909 has no `series_sheets` index**, so no coverage page and no link from its /explore
      row. Three sheets; someone must decide what that survey contains.
- [ ] **Sheet titles should come off the sheet, not the catalogue.** CartoMundi's spellings are
      French colonial transcriptions — `Yên-Dinh` is half-accented for Yên Định and reads as an
      error. Deliberately not applied; it sits behind `--names` in
      `backfill_indochine_descriptions.mjs`. OCR the title block instead.
- [ ] **The Vietnamese string `'All sheets in this survey'`** was written by a non-speaker. Wants a
      native check.
- [ ] **The L7014 coverage page is ~500 kB of HTML for 627 rows**, server-rendered per request. Fine
      today; revisit before Cochinchine's 826 lands.

## After 7.3

- [ ] **`/scan?mode=inspect` may now be dead weight.** /catalog/[id] serves the same tiles, drafts
      included, which was inspect's last stated job. Check the two things the record page does not
      obviously carry over — the tool map picker, and the plain level0 look — before deleting
      `features/contribute/inspect/`. Exit: either the directory is gone and `SCAN_MODES` has three
      entries, or `scanModes.ts` says which job keeps it alive.
- [ ] **`map_slug_aliases` is empty on production**, so the retired-name 301 is exercised only by
      the local write test. Exit: after the first re-mint, one `curl -sI` on the retired name
      showing a 301 to the live slug.
- [ ] **A label hit and a footprint submission reach the UI carrying only `map_id`**, so those links
      take the uuid fallback and cost a redirect. Adding `slug` to the two payloads lands the common
      path directly. Exit: no `/catalog/<uuid>` link is generated by a page the archive renders.
- [ ] **`scripts/lib/cells.test.mjs` cannot run in CI** — it needs the 42 MB gitignored catalogue
      dumps. Run it by hand after any catalogue re-fetch; that is when a new spelling arrives.
- [ ] **`tile_map.sh` and `bulk_upload_local.sh` still each do their own `maps` insert**, and
      `ingest_indochine_nakala.mjs` shells into the first. Unifying the mirror step waits on the
      container decision in `docs/journals/260914-iiif-space-efficiency.md` — packaging it first
      means packaging it twice.

## Track C — OCR ↔ SAM2 join

- [ ] **C5 Eval harness — blocked on data, not code.** The OCR side exists
      (`work/ocr/EVAL-BASELINE.md`); segmentation needs ~20 hand-labelled Saigon tiles before any
      number means anything. Same blocker as item 8.
- [ ] **C6 Blocks from the sheet's own colour, not from 2023 geodata.** Plan and full measurement
      trail: `docs/journals/260918-colour-blocks.md`. P1 landed 2026-09-18
      (`colour_blocks.py`, CPU only) and **did not clear its gate** — 189 blocks on the whole sheet
      in 5.9 s, but 0.124 mean IoU against the 24 `land_plot` traces. P3's null was **retracted the
      same day** (it was measured against 89 traces of which 72 are OCR label boxes, which sit on
      open wash and cannot differ from the plot); re-measured on the 17 real traces, `r − g` overlap
      is 0.23, sharpening to 0.18 with ink excluded. So an axis exists; a threshold that beats
      `building` 0.160 has not been shown. Number to beat overall is `--blocks-from-roads` at
      land_plot IoU 0.262 / cover 0.87. Cheapest next test: a salmon-internal `r − g` threshold at
      the measured trough, scored against the 17 traces. Needs one GPU run for P4 write-back.
- [ ] **Deferred inside Track C:** the gazetteer link and the LoRA shot set. Neither has a gate;
      both wait on C5 having data.

**B8 is done**, delivered as E2b (migration 066 — PostGIS, `geom`/`geom_src`/`geom_rmse`), despite
an unticked box surviving in the record.

## Track E — Time machine

- [ ] **E1b Gazetteer** — `place_names` exists; the view is only as good as the corpus, so this
      waits on ≥ 20 maps carrying extractions. Same queue as 4b/4c.
- [~] **E2 Temporal fabric** — code done 2026-09-02. Left: one real Colab `seg` run (item 7) and
      review of what it writes.
- [~] **E4 Corpus growth** — the georef sprint by decade gap. N2 and N6 are its two halves; runs
      whenever there is human time.
- [~] **E6 Sheets on one ground — the overlap floor (2026-09-21).** Two Saigon plans sixteen years
      apart, each warped by its own GCPs, overlap to ~50–100 m, and the limit is the scan rather
      than the transform. Detail: `docs/journals/260921-sheet-overlap.md`.
- [ ] **E5 Building attributes → OSM tags → LoD2** — deferred until E2 fabric is reviewed on ≥ 3
      maps. `tags jsonb` lands with its first writer.

## Track F — Time walk

One District 4 route on foot, warped sheets underneath, old names on top — HACW forked for Saigon.
Plan: `docs/time-walk-plan.md`.

- [ ] **F0 Walk the route on a phone and decide whether offline is real.** If it is not, this whole
      track collapses into `/trip/[id]` plus a year slider, and the fork should be deleted rather
      than maintained. **Nothing else in F is worth starting first.**
- [ ] **F1 `scripts/sheet_pmtiles.py <mapId> --bbox`** — one sheet drawing in MapLibre proves the
      chain. IIIF level0 tiles are not web-mercator XYZ, which is why every sheet must be warped
      once, server-side. **The PMTiles-vs-COG container choice is gated here** on one question: is
      on-the-fly rendering — a real IIIF level 2 — ever wanted? If yes, build COGs; if no, PMTiles
      is simpler. PMTiles saved 0% of bytes when measured 2026-09-14, so the decision is about
      capability, not size.
- [ ] **F2** Warp 1923 + 1968, then the year slider — one raster basemap entry per year, the
      `l7014` pattern already in `BASEMAP_DEFS`.
- [ ] **F3 `contracts/story.schema.json` + `GET /api/stories/[id].json`**, validated in the write
      smoke. Independent of F1/F2 and it jumps `platform-design.md` §6's queue: it needs neither the
      engine nor `packages/contracts`.
- [ ] **F4** Fork HACW → D4 content, Saigon extract, `pull-archive.mjs`, `checkStory()` — linked by
      frozen JSON + PMTiles, never a shared runtime.
- [ ] **F5** `gen-hero-fabric --bbox` per sheet → the names layer.
- [ ] **F6** Stops, quizzes, stamps — content only, machinery unchanged.
- [ ] **District 4 change story**, after the current georeference pass: improve georeference quality
      with the river-edge colour pass, then segment and process the D4 sheets alongside the 1882 and
      1898 work (1898 is outside the six-sheet AOI).
- [ ] **OHM vector pilot, with the sheet visible in its editor** — one compact 1882 Saigon area, one
      class. VMA's IIIF image plus its accepted georeference can be exposed as a warped XYZ URL via
      the Allmaps Tile Server and loaded as custom imagery.

## OCR setup — open improvements from the 1959 re-run (2026-09-10)

Measured in `docs/pipelines.md` §"Reading a sheet's margins". Cheapest fix first.

- [ ] **Triage must record which image it was computed for.** Store `img_width`/`img_height` in the
      saved triage and refuse a triage computed against a different scan. This is N4's smallest
      concrete case.
- [ ] **`/api/admin/status` should report the oldest queued job's age.** One `layout` job sat queued
      24 h because no worker was up and nothing said so.
- [ ] **The `ocr` job should read the regions the layout pass found**, not just `main_map`. The
      margins were the best-value calls on the sheet (9.8 rows/call vs 8.7 for a body pass) and the
      pipeline never made them: `title` → metadata, `legend` → symbol key, `name_list` → the index.
- [ ] **`--legend` fails silently.** Both 1959 passes carried it and it did nothing — it needs a
      scout cartouche, `--scout` is skipped when a neatline pins the crop, and it aims at the title
      block anyway. Make it fail the job.
- [ ] **`ocr.py index --region`** — the working table reader as a subcommand: ruled columns found
      locally, one column group per call, contiguity invariant, refuse the write when it fails. Most
      city plans in the corpus carry a directory like this one's.
- [ ] **Derive the grid from margin ticks, not from a 2048 px overview.** `ocr.py grid` read 12 rows
      where the sheet has 9. Correct, it also lets index entries whose numeral was never found sit
      at cell centre, and arbitrates numeral collisions.
- [ ] **Gate integer extraction per sheet** (`seq-v1-idx` vs `seq-v1`) on whether the layout pass
      found a numbered index, not on a person remembering. Classify bare integers as `legend_ref` by
      regex; the model ignored an `index_key` category in 114 of 114 cases.
- [ ] **`merge` drops the label box.** 514 of the 1959 rows carry a non-zero `rotation_deg` but no
      `label_w`/`label_h`, so the review canvas only ever gets a point.

## Burn-down — when it hurts (Track D)

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

- [ ] **Preview environment has no variables.** Production holds all five, Preview holds none, so
      every preview build fails at the first `$env/static/*` import. Dashboard only —
      `wrangler pages secret` has no environment flag in any current version.

## Order

**N1 → N6**, the foundations pass, supersedes everything below it. E4 still runs whenever there is
human time (N2 and N6 are its two halves). F0 before any of F1–F6 is worth starting; F3 is
independent and can run alongside E. Track D never blocks.

Previously: A1–A4 → B1 → B2 → C0 → C1 → B3 → B4 → B5 → C2, then E1 → E2 → E3. That ordering is
history now and is kept in `docs/roadmap-record.md`.
