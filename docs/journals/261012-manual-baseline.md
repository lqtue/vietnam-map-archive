# Manual baseline of the map pipeline — 2026-10-12

How much human time and how many corrections each stage has taken so far, from data that already
exists. This is the "before" for the auto-queue. One read-only pass against the live Supabase project
(PostgREST, service key, paged `select`s; nothing written) plus `git log` on `scripts/oneoff/` and
`docs/journals/`. Counts are as of 2026-10-12.

Two rules from `guides/lessons.md` govern every number below. **Say which number you mean:** "elapsed" is wall
clock between two stored timestamps, never effort; "machine" is `started_at` to `finished_at` on a
`pipeline_jobs` row; "wait" is `created_at` to `started_at` on the same row (a queue, not a person);
"events" are distinct stored review timestamps, not clicks. **Measure before tuning:** where the data
cannot support a number, the cell says unknown rather than a proxy.

## The shape of the data, first

- `maps` has 1,562 rows; 1,525 belong to a series and were created by import scripts on a dozen
  days (`select=created_at`, grouped by day: 433 on 2026-10-01, 342 on 09-23, 208 on 09-24, 143 on 09-14).
  `maps.created_by` is null on all 1,562. Only 37 rows have no series: that is the hand-curated
  corpus the owner's chain describes. Any all-rows rate below is therefore dominated by script
  batches, and each row says which population it covers.
- `scout_candidates` produced almost none of those maps: `map_id` is set on 2 of 1,067 rows.
  The series sheets came in through `scripts/oneoff/import_*` and `ingest_*`, not through the
  find -> approve -> ingest queue.
- `pipeline_jobs` has 164 rows in total, `ocr` 35, `layout` 115, `warp` 10, `seg` 3, `tile_to_r2` 1,
  and no `ingest_map`, `mirror_annotation`, `sync_allmaps` or `build_pmtiles` at all. The queue is
  used for the four machine stages only; tiling, ingest and Allmaps sync are CLI runs that leave no
  job row.

## 1. Per stage

Columns: **N** = maps (or rows where stated) that went through it; **machine** = median
`finished_at - started_at` of `done` jobs; **human latency** = elapsed time, with its definition;
**rate** = correction, reject or retry share.

| Stage | N | Machine (median) | Human latency (elapsed, defined) | Correction / reject / retry | Source |
| --- | --- | --- | --- | --- | --- |
| Find (scout) | 1,067 candidates, in two loads (985 on 2026-05-16, 82 on 09-13/09-23) | not in `pipeline_jobs` | unknown: `created_at` is the load time of a batch, not a find time | 0 rejected | `scout_candidates?select=review_status,created_at`, grouped |
| Credibility / approve | 7 decided (5 `approved`, 2 `ingested`); 1,060 `pending` (99.3%) | none | 4 approvals stamped 7 seconds apart on 2026-09-03 (one bulk click); the other 3 carry no `reviewed_at`. Per-item time unknown | reject rate 0 of 7; `maps.classification_reviewed_at` is set on 0 of 1,562, `classification_status` is `provisional` on 1,512 and `needs_review` on 50 | `scout_candidates`, `maps?select=classification_status,classification_reviewed_at` |
| Record (ingest, catalogue fields) | 1,562 maps (1,320 public or featured, 241 draft, 1 archived) | `tile_to_r2`: 1 job, 1.75 min; the rest is CLI | unknown: no editor, no edit history, `created_by` all null. `updated_at - created_at` is >1 day on 1,514 maps but scripts touch whole series, so it is not an edit count | proxy only: 40 one-off scripts (section 2) | `maps`, `pipeline_jobs?kind=eq.tile_to_r2` |
| Georeference | 1,229 georeferenced of 1,562 (79%): 749 with an `allmaps_id` (Allmaps editor or posted), 480 annotation-only (script) ; 333 not (221 are Indochine 1st ed.) | `warp`: 10 jobs on 7 maps, 0.06 min (re-warps, not the fit itself) | unknown. `georef_versions` has 725 rows, but all were written 2026-10-01 to 10-07 (604 on 10-01 as `unrecorded`), so "created to first version" is 193 h and means nothing; the table began then | 66 of 652 versioned maps (10%) have 2+ versions; 10 of 725 versions have <=3 GCPs (RMSE identically 0); `user_id` null on all 725; origin `unrecorded` on 607, `script` on 118 | `maps?select=is_georeferenced,allmaps_id,annotation_url,series_id`, `georef_versions` |
| Layout / triage | 109 maps with a layout job, 107 done; 21 signed off by a person (19.6% of 107) | `layout`: 108 done jobs, 0.54 min, p90 2.0; queue wait 57.5 min | last `layout` job finished -> `maps.triage_reviewed_at`: median 110 h (IQR 95-110 h, n=21; 1 of 21 negative = reviewed before a re-run). All 21 fall on 2026-09-09/10/12, so it is a batch sitting, not 21 independent waits | 6 of 115 layout jobs exhausted 3 attempts (5.2%): 4 tracebacks, 2 sheets under 1024 px (refused by design); 109 maps, 107 with a done job, so 2 maps never got one. On the 21 reviewed sheets 13 of 133 regions are `source: human` (9.8%) and the neatline source is `human` on 21 of 21; the 86 unreviewed keep `main_map` or none | `pipeline_jobs?kind=eq.layout`, `maps.triage` JSON (`regions[].source`, `neatline_src`, `validated_at`) |
| OCR | 15,206 labels on 24 maps, 52 run ids; 35 jobs on 20 maps | `ocr`: 32 done jobs, 4.91 min, p90 29.6; queue wait 14.9 min | not applicable | 0 failed; 1 job retried (attempts 2). 29 of the 52 run ids have no job, so that machine time is outside the queue and unmeasured | `pipeline_jobs?kind=eq.ocr`, `ocr_labels?select=run_id,map_id` vs job `payload.run_id` |
| OCR review | 12 of 24 OCR'd maps have any decision; 1 map (1882 sheet, 530 of 541 decided) is effectively done. 1,228 validated, 3,284 rejected, 10,694 pending (70.3%) | none | label `created_at` -> `reviewed_at`: median 577 h (24 days), IQR 364-621 h, n=1,224 — that is queue age, not effort. Stamped events: 278 distinct timestamps for 1,224 rows, in 32 sessions; summing gaps of <=10 min between consecutive stamps gives >=216 min (lower bound, one reviewer, and bulk "validate all" writes of up to 200 rows share one timestamp) | text edited on 67 of 1,228 validated (5.5%); category edited on 16 (1.3%). Rejects: 2,023 of 3,284 carry a script note (`merged:`, `passes=`, `migration_source`); 1,261 are unattributed and untimed, human or script cannot be told apart | `ocr_labels?select=review_status,text,text_corrected,category,category_corrected,reviewed_at,reviewed_by,notes` |
| Features (footprints) | 1,430 rows on 2 maps: 1,354 `import` (machine), 76 `volunteer` | `seg`: 3 jobs on 1 map; 1 done in 10.53 min | none stamped: `reviewed_at` is null on all 1,430 | `seg` 2 of 3 failed (both closed by hand: a stranded run and a stale clone); machine imports 1,354 of 1,354 still `needs_review`; volunteer 46 `approved`, 30 `submitted` (46 of 76 volunteer rows approved, 60.5%) | `footprints?select=source,review_status,reviewed_at`, `pipeline_jobs?kind=eq.seg` |
| Review (sign-off) | `map_review_marks`: 2 rows, 1 with `reviewed_at`, 0 `seg_reviewed`, 0 `exported` | none | unknown | unknown | `map_review_marks` |
| Link (legend points, joins, context) | 870 placed legend points (`px` in `notes`, all `validated`) on 7 maps, of 1,132 live legend entries on 9; 27 `legend_finds` on 1 map (27 of 27 matched an OSM id, all 2026-10-08); 368 legacy `label_pins` | none | legend points: stamped only by validation, so the times are those of the OCR-review sessions above; `legend_finds.created_at` is per row but all 27 fall on one day | not measurable: a corrected placement overwrites `notes` with no history | `ocr_labels` where `coalesce(category_corrected, category) = legend_entry`, `legend_finds`, `label_pins` |

Machine time against human latency, where both exist: layout runs in about half a minute and waits
about an hour in the queue, then waits 4.6 days for a person; OCR runs about 5 minutes and waits
about 15 minutes, then a validated label waits a median of 24 days for review.

## 2. One-off scripts per stage

`ls scripts/oneoff | wc -l` = 71, all added between 2026-09-06 and 2026-10-08. Each assigned to one
stage by its name and opening comment (`git log --diff-filter=A` for the first commit date,
`git log --format=%h -- <file>` for commits that touch it). The two hue-6541 scripts and
`audit_detail_dump*` have no header; they are placed by name.

| Stage | Scripts | First added | Last added | Commits touching them |
| --- | ---: | --- | --- | ---: |
| Find | 6 | 2026-09-08 | 09-23 | 11 |
| Credibility | 9 | 09-14 | 09-21 | 14 |
| Record | 40 | 09-13 | 10-08 | 76 |
| Georeference | 9 | 09-06 | 10-01 | 23 |
| Layout / triage | 0 | | | |
| OCR | 2 | 09-12 | 09-12 | 2 |
| OCR review | 1 | 09-12 | 09-12 | 1 |
| Features, Review | 0 | | | |
| Link | 4 | 09-24 | 10-05 | 6 |

Record is 56% of the scripts (40 of 71) and 57% of the touching commits (76 of 133): it is the stage with the
most hand-made code and the least recorded human time. Layout, features and review have no one-offs
because their work happens in the app. Journals as a second proxy, classified by title from the
index only (24 dated records): features and colour 6, georeference 5, link 4, find 3, record 3, OCR
review 2, OCR 1.

## 3. Bottlenecks

1. **Human review is the bottleneck, not the machines.** Every machine stage finishes in minutes
   (layout 0.5, OCR 4.9, seg 10.5, warp 0.06 median). What sits behind them: 70.3% of 15,206 OCR labels
   pending, only 1 of 24 OCR'd maps close to fully decided; 86 of 107 laid-out maps (80%) never
   signed off; 1,354 machine footprints with none reviewed; `map_review_marks` has 2 rows. The
   queue behind the person is weeks (24 days median label age) while the machine is minutes.
2. **The front of the chain is not running through its own tools.** 99.3% of the scout queue is
   pending and 0 of 1,562 maps carry a credibility sign-off, while 1,525 maps arrived by script. The
   cost there is script-writing, not review: 55 of 71 one-offs (find, credibility, record) are
   catalogue and provenance repair, and several are corrections of earlier ones (15 scripts are named
   `fix_*`).
3. **Georeferencing is probably the largest human effort and is the least measured.** 333 maps
   (21%) are unreferenced, 221 of them one Indochine edition with no georeference at all, and the
   work happens in the external Allmaps editor whose timing the project does not hold. This is
   an inference from counts and the script list, not a measurement.

## 4. What is not measurable today, and the smallest change

| Gap | Evidence | Smallest change (not made) |
| --- | --- | --- |
| Scout find time | `created_at` is batch load time; 2 of 1,067 have `map_id`; only approvals stamp `reviewed_at` | Stamp `reviewed_at` on any `review_status` change (trigger), including `ingested`; ingest scripts set `map_id`. |
| Credibility sign-off | `classification_reviewed_at` null on 1,562 of 1,562 | Find out whether the UI writes it; if not, wire it. No schema change. |
| Record effort | `created_by` null everywhere, no edit history, `updated_at` overwritten by scripts | A trigger-fed `map_edits(map_id, user_id, field, changed_at)`; or at minimum require `created_by` on ingest. |
| Georeference | `georef_versions` begins 2026-10-01; `user_id` null on 725 of 725; `origin = unrecorded` on 607; Allmaps editing time is not mirrored | Require `origin` and `user_id` on every `mirror_annotation`/`sync_allmaps` write; keep the Allmaps annotation's own modified time. |
| Layout human time | `regions_at` equals `validated_at` on all 21 reviewed sheets (the sign-off rewrites it), so machine time is gone from the JSON; 21 reviews on 3 days | Do not overwrite `regions_at` on sign-off; add `triage_opened_at`. |
| OCR run outside the queue | 29 of 52 run ids have no `pipeline_jobs` row | CLI runs insert a `done` job row with timings. Nothing else changes. |
| OCR-review rejects | `set_extraction_status` nulls `reviewed_at`/`reviewed_by` on reject, so 1,261 rejects have no person or time | Keep the stamp on reject (drop the `case when 'validated'`), or write an append-only `review_events`. |
| Footprint review | `reviewed_at` null on 1,430 of 1,430, including 46 `approved` | Same: find the write path that sets `review_status` without stamping, and stamp it. |
| Effort of any kind | Nothing records time on task; the 216 min above is a floor from gap-clustering | A single `review_events(user_id, stage, map_id, items, started_at, ended_at)` written per sitting by the review tools, with a session break after N idle minutes. Most of the rows above could then be answered directly. |
| Legend placement | A corrected `px` overwrites `notes`; only validation is stamped | Covered by `review_events`; no per-field history needed. |
