# Ponytail debt ledger

Deliberate shortcuts marked with `ponytail:` comments. Each names its ceiling
and the trigger to revisit.

Regenerate with:

```bash
grep -rn 'ponytail:' src/ work/ scripts/ tests/ supabase/ eslint.config.js playwright.config.ts
```

then drop the one hit under `work/cleanup/` (a prose mention in a scratch TODO,
not a marker) and write the rows by hand. **The plugin that used to generate
this file is gone (Sept 2026)** — nothing regenerates it automatically, so it
only tells the truth right after someone runs that grep. Every `file:line`
below is copied from its output.

Scanned **2026-09-15**, six rows added by hand 2026-09-18. **72 markers, 14 with no trigger.** Against the
2026-09-10 scan that is +19 markers, and a great many line numbers have moved —
the ledger had gone stale in both directions, so this is a full rewrite rather
than a patch. See *What changed since 2026-09-10* at the foot.

## src/lib/core/geo/wkb.ts

- **:9** — the EWKB parser handles points only, little-endian only. ceiling: every row Supabase has ever returned; a LINESTRING or big-endian order returns `null` rather than a wrong coordinate. upgrade: take a real WKB library if the archive ever stores non-point geometry — do not grow this.

## src/lib/core/iiif/annotationUrl.ts

- **:28** — `allmapsTileUrl` leans on `allmaps.xyz`, a free public service. ceiling: someone else's rate limit and uptime. upgrade: self-host `@allmaps/tileserver` on the R2 worker if it ever throttles us.

## src/lib/core/iiif/thumbUrl.ts

- **:44** — `atWidth()` rewrites the IIIF size with a regex rather than parsing the URL. ceiling: the only failure it can cause is a width the server will not cut, and `stepDown` is what catches that. upgrade: _none named_ — `no-trigger`.

## src/lib/core/utils/id.ts

- **:4** — `randomId()` calls `crypto.randomUUID()` with no fallback. ceiling: needs a secure context — true for localhost dev, HTTPS prod and Cloudflare Workers. upgrade: add a `Math.random` fallback only if this ever has to run over plain http on a LAN address.

## src/lib/core/utils/tween.ts

- **:5** — hand-rolled tween that replaced `animejs`, a dependency carried for one job. ceiling: deliberate — no stagger, no keyframe sequencing, no spring. upgrade: take a library back rather than growing this, if the timeline needs any of those.

## src/lib/data/supabase/realtimeStub.ts

- **:1** — a stub `RealtimeClient` aliased in `vite.config.ts`. ceiling: `SupabaseClient`'s constructor builds a realtime client unconditionally, which would drag phoenix and a websocket stack into the root layout on every page; the app has no `.channel()` and no `.subscribe()`, so the stub satisfies the constructor and nothing else. upgrade: delete the alias the day a `.channel()` appears.

## src/lib/map/shell/warpedOverlay.ts

- **:69** — monkey-patch instead of forking `@allmaps/render`. ceiling: six lines against an upstream beta that may fix this itself. upgrade: drop it when `@allmaps/render` clears the frame for itself.

## src/lib/features/annotate/animation/playback.ts

- **:189** — the second half of the same `animejs` removal: a proxy object with one numeric property. ceiling: no stagger, no keyframes, no spring. upgrade: take the dependency back rather than growing this.

## src/lib/features/explore/exploreUrl.ts

- **:46** — `syncMapParam` mirrors only the topmost overlay into `?map=`, not the whole stack. ceiling: `applyExploreUrlParams()` reads a single id, so a stack encoding needs a reader change too. upgrade: when sharing multi-map stacks is actually asked for.

## src/lib/features/explore/FocusPulse.svelte

- **:54** — the pulse is driven by `requestAnimationFrame`, not OL's `postrender`. ceiling: it stops on its own and nothing else on the map animates. upgrade: reach for `postrender` only if a second animated layer shows up.

## src/lib/features/explore/FootprintsLayer.svelte

- **:75** — one request per set of ids, re-fetched whenever the set changes, no per-map cache. ceiling: a sheet's fabric is a few hundred polygons and the response is edge-cacheable. upgrade: add a cache only if switching sheets feels slow.

## src/lib/features/explore/ExploreBrowsePanel.svelte

- **:110** — an inbound `?series=` selects the series but does not fit the map to its bounds. ceiling: the key is accepted in either spelling — the database series or the raster archive's own — so a reader copying one out of a URL cannot take the wrong half, and the param is consumed once and dropped. upgrade: wire the bounds fit through if a bare `?series=` is ever shared.

## src/lib/features/explore/ExploreRightSidebar.svelte

- **:89** — the Legend tab issues the same GET `LegendPointsLayer` makes, so an open tab fetches it twice. ceiling: one small request per map. upgrade: give it a store if a third reader turns up.

## src/lib/features/explore/HeroMap.svelte

- **:184** — `fitSheet` runs once, when the map appears; not on resize. ceiling: a refit would undo a reader who has panned or ⌘-zoomed, and the frame only has to be right for the beats. upgrade: re-fit on `change:size` the day the stage becomes resizable.

## src/lib/features/explore/HeroSequence.svelte

- **:142** — reaches for `boundHandleBrowserEvent_`, an OpenLayers private, to drop a wheel listener. ceiling: a plain instance field, and `removeEventListener` matches on type and function alone, so it is stabler than a monkey-patch — but an OL rename makes the wheel sluggish again rather than throwing. upgrade: none available to us; the real fix is OL registering the listener only when an interaction wants it.
- **:262** — one label query, no paging, capped at 150. ceiling: the 1882 sheet has 85 validated rows, so the cap has headroom; a sheet with hundreds would need thinning by zoom. upgrade: OL declutter is where to start — and `HeroMap`'s caption quotes the same number by hand, so bump both together.

## src/lib/features/contribute/ocr/legendIndex.ts

- **:175** — three suspect checks, not four: the numeral sitting outside the cell its entry names is not tested. ceiling: that fourth check needs `maps.triage.grid`, which most sheets do not have yet. upgrade: add it beside the others when the grid is fitted — `_cell_rect`/`cellBox` already turn a reference into a rectangle.

## src/lib/features/contribute/ocr/ocrReviewController.ts

- **:120** — the canvas copy of a status change is optimistic and never reverted. ceiling: a failed write surfaces only in the sidebar's error line. upgrade: revert here if that proves confusing to reviewers.
- **:172** — one PATCH per keypress when rotating a label. ceiling: no debounce at all. upgrade: debounce if holding a key ever matters.

## src/lib/server/auth.ts

- **:77** — `assertUnderRateLimit` counts the target table directly instead of keeping a rate-limit store. ceiling: trades exactness under bursts for having no moving parts — a counter table would need its own writer, cleanup and migration. upgrade: a real limiter if a single count query ever shows up in the slow log.

## src/lib/server/gallica.ts

- **:41** — no per-IP rate limit. ceiling: the platform has no shared counter to keep one in (the existing helper counts rows per signed-in user); the defences are the item cap, the 24 h edge cache and no retries. upgrade: a real limiter in KV or D1 if either archive complains — not a smaller number here.
- **:120** — the CQL carries no `dc.type` filter. ceiling: restricting to `fascicule` would return press issues only and drop the Annuaire directories, which are the better source. upgrade: _none — deliberately closed_ — `no-trigger`.
- **:148** — entity decode and tag match by regex, not a parser. ceiling: both payloads are flat, machine-generated XML from one publisher. upgrade: _none named_; a real parser is a dependency, and Workers have no `DOMParser` — `no-trigger`.

## src/lib/server/press.ts

- **:160** — `parseNlvRows` reads Veridian's HTML with regexes, not a parser. ceiling: Workers have no `DOMParser` and the markup is flat and machine-generated from one publisher; a template change shows up as zero rows against a non-zero total, which the caller reports as a degradation rather than as an empty archive. upgrade: _none named_ — `no-trigger`.
- **:231** — results carry no snippet, only the page image. ceiling: the archive returns no matched text, so the crop *is* the evidence for this source. upgrade: a snippet would need the upstream OCR — nothing we can trigger on — `no-trigger`.

## src/lib/server/warp.ts

- **:104** — `pointEwkt` hands PostgREST EWKT text rather than a geometry object. ceiling: the string goes straight to the geography input function, so there is nothing to install — but the numbers are not readable back out of it. upgrade: use `transformToGeo` directly if a writer ever needs them, rather than parsing this.

## src/routes/(editorial)/+page.svelte

- **:59** — the hero's demo sheet is hardcoded, not queried. ceiling: it is the only sheet carrying all three layers the sequence shows — a georeference, traced footprints and validated OCR labels — so it is the only one where the demo tells the truth. upgrade: when a second sheet is this complete, write the join then.

## src/routes/api/export/footprints/+server.ts

- **:63** — `ringIntersectsBbox` includes a polygon whose bounding box clips the AOI even when its ring does not. ceiling: over-inclusive, which is the safe direction for an export the notebook clips precisely anyway. upgrade: a real predicate only if an export has to be exact without post-processing.

## scripts/check-bundle.mjs

- **:9** — regex over the emitted JS, not a real module graph. ceiling: assumes plain quoted import specifiers, which built output always emits. upgrade: parse with `es-module-lexer` if a future bundler emits computed specifiers.

## scripts/catalog_audit.mjs

- **:41** — joins in JS over one paged read per table. ceiling: the same trade as `check_series_index`, at the same threshold. upgrade: write the view when a survey makes this slow, and delete this.

## scripts/check_series_index.mjs

- **:26** — joins in JS over one paged read of each table rather than a SQL view. ceiling: fine to ~10k sheets. upgrade: if a survey lands that makes this slow, that is the moment to write the view and delete this.

## scripts/dedupe_ocr.mjs

- **:19** — `IOU` fixed at 0.3. ceiling: the cut is flat from 0.1 to 0.5, so tuning buys nothing. upgrade: _none named_ — `no-trigger`.
- **:244** — `JITTER_SCALE` 1.5 and `JITTER_CAP` 300px are a judgement call, not a measurement. ceiling: same-name distances run smoothly from 25px to 5000px with no gap to cut at; both are set low, so obvious jitter merges and anything arguable is left for a reviewer. upgrade: _none named_ — `no-trigger`.

## scripts/geo_audit.mjs

- **:21** — no adjacency or seam check. ceiling: the generic version needs sheet-neighbour topology the database does not carry, and `l7014_mosaic.py fit` already covers the one series where seams found the bug. upgrade: add it when a second lattice-less survey exists.

## scripts/legend_timeline.mjs

- **:17** — a lexicon of ~25 type words, not a translation model. ceiling: the proper name is a proper name in both languages (Bình Tây, Khánh Hội, Grall, Phúc Kiến), which is what makes the match work at all; an institution whose *name* changed, not just its type word, lands in the unmatched list on purpose rather than being guessed at. upgrade: a real model only when the unmatched list stops being readable by hand.

## scripts/scout_nlv_press.mjs

- **:24** — HTML regexes, not a DOM parser. ceiling: Veridian's output is machine-generated and has not moved in years, and a template change breaks loudly — zero results on a query whose total is non-zero, which `--selftest` pins. upgrade: reach for a parser when that actually happens.

## scripts/l7014_ttu_fetch.py

- **:38** — `PAUSE = 1.5`, a fixed courtesy delay with no backoff. ceiling: a 25-file run, once. upgrade: _none named_ — `no-trigger`.

## scripts/pmtiles_extract.sh

- **:32** — no date argument; the script walks back from today until a build answers. ceiling: Protomaps keeps daily builds for about a week, so a pinned date rots faster than the script. upgrade: pass `PMTILES_SOURCE` to override with any archive URL or path. Note the *uploaded* key does carry the date (`vietnam-20260906.pmtiles`) — the archive sits behind a one-month edge TTL, so overwriting a key in place would strand every reader on stale bytes.

## scripts/oneoff/backfill_indochine_descriptions.mjs

- **:38** — writes `dc_description`, `source_url` and (opt-in) `name`; leaves `rights` at "Public domain". ceiling: a 1900s French colonial survey probably is public domain, but CartoMundi's Nakala items for the neighbouring 1:100,000 series are CC-BY-NC-SA-4.0, and guessing a licence is the same error as guessing a source. Flagged, not changed. upgrade: _none named_ — `no-trigger`.

## scripts/oneoff/backfill_iiif_widths.py

- **:33** — writes 200/400/800 and nothing else. ceiling: those are the three widths `atWidth()` callers ask for (48px rail, 96px table cell, 400px card, 800px OG image); the 1200 a featured plate wants is deliberately absent, because no sheet in this state is featured and `stepDown` covers it if one ever is. upgrade: _none named_ — `no-trigger`.

## scripts/oneoff/normalize_map_locations.mjs

- **:31** — no constraint or trigger stops the bad spellings recurring. ceiling: two rows in one ingest is not a pattern yet, and a CHECK over a free-text column holding 27 legitimate values would be a list to maintain rather than a rule. upgrade: if a third spelling turns up, the fix is a gazetteer FK, not a longer list.

## supabase/migrations/065_ocr_label_search.sql

- **:8** — no trigram index; the label search uses an explicit `word_similarity() >= 0.5`. ceiling: the indexable operator `<%` reads `pg_trgm.word_similarity_threshold`, which Supabase's `postgres` role cannot `SET` on a function (the GUC belongs to an extension in another schema), and the 0.6 default misses one-letter typos; a seq scan is fine at the ~10⁵ rows a fully OCR'd corpus will hold. upgrade: have the dashboard run `alter database postgres set pg_trgm.word_similarity_threshold = 0.5`, then switch to the indexable operator.

## supabase/migrations/083_series_sheets.sql

- **:81** — the `held_by` constraint leaves one stale state reachable: `held_by = 'map'` with a null `map_id`, after the map it pointed at was deleted. ceiling: it reads as "held, served by nothing", is visible in one query (`where held_by = 'map' and map_id is null`), and is the correct thing to look at after retiring a sheet anyway. upgrade: add a trigger only if that query starts coming back non-empty for reasons nobody remembers.

## eslint.config.js

- **:16** — `@typescript-eslint/no-explicit-any` is off. ceiling: ~100 `as any` casts today, tracked as debt rather than a lint failure. upgrade: _none named in the comment_ — `no-trigger`. (The route is known and worth writing down: pass `<Database>` to every `createClient(...)`, which removes most of them, then flip the rule to `warn`.)

## playwright.config.ts

- **:3** — chromium only, no fixtures, no global setup. ceiling: one engine. upgrade: add firefox/webkit projects when a browser-specific bug actually shows up.

## tests/smoke.spec.ts

- **:15** — read-only smokes against the dev server and the real Supabase project; nothing here writes a row. ceiling: the two write paths worth covering — saving an OCR bbox and submitting a footprint — need a logged-in user and would insert into production tables. upgrade: **already delivered, and this comment is stale.** `npm run db:test` seeds a local stack and `tests/write.spec.ts` covers 31 write paths against it. Reword the marker or drop it.

## tests/write.spec.ts

- **:22** — the write smokes drive supabase-js on the same contract the data layer uses, not the drawing UI. ceiling: canvas-dragging tests would cost far more than the coverage they add. upgrade: add them when a UI wiring bug actually escapes.

## tests/press.spec.ts

- **:24** — the pure checks ride the Playwright suite as browser-less tests. ceiling: the repo has no unit-test runner, and nothing here touches the network or the dev server. upgrade: _none named_ — `no-trigger`.

## tests/schemaCheck.ts

- **:4** — a ~50-line subset walker instead of a validator library. ceiling: supports `type` (including unions with `"null"`), `required`, `properties`, `items` and `enum`; anything else is reported through `unsupportedKeywords` rather than silently passed, so adding `pattern` to a contract fails loudly here. upgrade: adopt `ajv` properly if the contracts outgrow that subset (the path is written down in `contracts/README.md:22`, not in the comment).

## work/ocr/scripts/ocr.py

- **:1185** — two distinct same-text features on one tile collapse to one DB row, sharing a unique key. ceiling: the same limit the old raw path had. upgrade: add a location suffix to the key only if it ever bites.
- **:3346** — legend entries carry their number and grid in `notes` as a parseable `"n=..; grid=.."`, with `text` holding `"n. name"`. ceiling: `ocr_extractions` has no number/grid columns; this keeps the row key unique (duplicate names exist) and carries the body-numeral join key. upgrade: add real columns if the number-join gets clumsy.

## work/ocr/scripts/iiif_tiles.py

- **:492** — CLAHE in pure numpy + Pillow, ~30 lines. ceiling: there is no cv2 wheel for Python 3.14 and this must add no dependency; a full 2048px tile costs ~0.2 s and four 256-entry float32 LUT gathers (~64 MB peak), and the bilinear interpolation matches cv2's so output is equivalent but not bit-identical. upgrade: if it ever shows up in the profile, `cv2.createCLAHE(clipLimit, tileGridSize).apply(L)` on the same L channel, same flag surface, then delete `_clahe_lut`.
- **:762** — the AOI is an axis-aligned rectangle in pixel space. ceiling: a rotated or skewed map means the caller's pixel bbox over-covers the true geo polygon, so a few extra tiles survive; over-covering costs API calls where under-covering would lose labels, so this is the safe side. upgrade: _none named_ — `no-trigger`.

## work/ocr/scripts/join_labels.py

- **:77** — ray-cast point-in-polygon plus an O(labels × footprints) scan. ceiling: fine for one map at hundreds of each. upgrade: grid-bucket the footprints if a map ever holds tens of thousands.

## work/ocr/scripts/eval_metrics.py

- **:49** — char accuracy via `difflib.SequenceMatcher.ratio()`, a 2·M/T similarity, not a true CharACC/CER. ceiling: tracks regressions fine, but the absolute number is not a CER. upgrade: swap for `rapidfuzz.normalized_similarity` if an exact CER is ever needed.

## work/ocr/scripts/local_vision.py

- **:16** — pure scipy + Tesseract. ceiling: chosen because cv2 and PaddleOCR have no clean Python 3.14 wheel today. upgrade: if digit recall is too low, swap `spot_numerals()` for a PaddleOCR detector in a 3.11 venv — keep the `[{text, bbox, confidence}]` return shape and nothing downstream changes.

## work/ocr/scripts/name_masks.py

- **:37** — `MIN_INSIDE = 0.7`, one containment threshold for every sheet. ceiling: a single number across a corpus whose polygons vary in tightness. upgrade: tune it per sheet when a run names things across a street, or drop to centroid-in-polygon once the polygons are tight enough to make containment exact.

## work/ocr/scripts/colour_blocks.py

- **:84** — a block's ring is a concave hull over its boundary pixels, not a trace. ceiling: a block with a genuine notch comes back filled, and `blocks_to_seeds` reads only the bounds anyway. upgrade: marching squares on the component mask; the signal to do it is `seg_eval` cover running high while IoU stays flat, which is what over-coverage looks like.

## work/ocr/scripts/seg_eval.py

- **:88** — the ground truth is filtered on `source=volunteer` alone, not on
  `status`. ceiling: a volunteer trace counts the moment it is submitted, so a
  careless or mid-edit trace is ground truth until someone deletes it. upgrade:
  add `status=eq.approved` if volunteer tracing ever gets a review queue worth
  gating on — today all 46 approved rows are also all the volunteer rows, so the
  two filters select the same set and the weaker one fails safe. Added
  2026-09-18 after `load_gt` was found returning 72 `sam-auto` rows as truth.

## work/ocr/scripts/colour_blocks.py — legend key

- **`LEGEND_SWATCHES`** — the five legend swatches of the 1882 sheet, hard-coded
  as measured. ceiling: every other sheet; a second polychrome map gets the wrong
  key silently, because nothing checks that the numbers belong to the sheet being
  read. upgrade: read them off the `legend` triage region directly — they are the
  saturated rectangles in it — and it is worth building the moment a second
  polychrome sheet arrives.
- **`HATCH_COHERENCE` (:870)** — one constant, 0.30, for the hatch test, not a
  trough voted from the sheet the way every other knob in this file is. ceiling:
  the number scales with `--render`, because a hatch aliases away as the sheet is
  shrunk — the same two blocks score 0.74/0.59 at `--render 6051` and 0.81/0.75
  at full source resolution, so a run at another render is measuring against a
  threshold fitted elsewhere. upgrade: sweep it against banded counts the way
  `cream_ink` sweeps its ink threshold, or re-measure per render; the trigger is
  the first run at a render other than 6051.
- **`WATER_CELL` / `WATER_COHERENCE` / `WATER_PAPER_RB` / `WATER_INK_MAX` /
  `WATER_SHARE`** — a 64 px grid and four constants for the water region, one
  sheet. ceiling: the seeds. A `hydrology` label that lands on a mixed cell
  seeds nothing, and here 1 of 16 does all the work — enough because the main
  river is one component, and not enough on a sheet of many small ponds.
  upgrade: seed from the label's neighbourhood rather than its own cell.
  Trigger: a sheet whose water is several disconnected bodies.
- **`MIN_CIRCULARITY`** — 0.10, one shape prior for every parcel. ceiling: a
  sheet with genuinely long thin parcels — a canal frontage, a rice-field
  strip — where the prior is simply false; measured here, 0.15 already breaks
  land_plot to 0.326. upgrade: none needed on this sheet; elsewhere lower it or
  leave the flag off.
- **`fit_dilution`** — one global alpha for every class. ceiling: a sheet whose
  printer laid one tint heavier than another; per-class alphas are five scalars
  fitted the same way, and the trigger is a class that is systematically
  mis-assigned in one direction while the others are right.

## work/ocr/scripts/modern_prior.py

- **:133** — `BLOCK_BUFFER_M = 8.0`, one constant for the whole corpus. ceiling: it is a per-sheet quantity really — alley width varies by district and by era. upgrade: pass `buffer_m` explicitly if a sheet comes back visibly over- or under-merged.
- **:429** — `difference` against the whole page in one call. ceiling: fine at one sheet — 1.3 s over a 3.3 km window with 1,783 road polygons. upgrade: a grid if a sheet ever covers the full 74k, and measure before splitting it.
- **:461** — junction counting by vertex, not true noding. ceiling: it finds junctions where ways are split, which OSM does at every intersection, and misses a crossing where one way passes over another unsplit. upgrade: swap in `shapely.node` if bridges and flyovers start mattering.
- **:481** — buildings are binned by centroid and counted whole, not clipped to the cell. ceiling: a building is ~10 m across and a cell here is hundreds, so the error is edge-only. upgrade: clip properly if the grid ever gets fine enough that a cell and a building are the same size.

## work/MapSAM2/to_sam2_seeds.py

- **:234** — the block's ring is thrown away and only its box is prompted. ceiling: a block is L- or U-shaped often enough that its box covers a chunk of the street beside it, and SAM2 gets the box either way. upgrade: if prompts start bleeding into the roadway, add a point prompt at the polygon's representative point alongside the box — `seeds_for_tile` already carries a slot for it.
- **:253** — the size floor is strictly zero, not a pixel. ceiling: on the 1959 sheet 21 of 13,037 blocks come back thinner than 1 px (buffer-shrink residue, not buildings) and a quarter of those are under 16 px on a side, which is one tube house rather than a block — both are prompts SAM2 answers badly. upgrade: a `MIN_BLOCK_PX` floor here, set from a run's measured mask IoU rather than from taste.
- **:365** — `MAX_BOX_TILE_FRACTION = 0.9`: an oversized block is dropped, not rescued. ceiling: the count is a rounding error today. upgrade: segment an oversized block on a coarser scale factor where it does fit — a second pass at another zoom — when that stops being true.

## work/worker/vma_worker.py

- **:398** — the seg runner reads its checkpoint and MapSAM2 directory from the environment. ceiling: they are properties of the machine, not the job; a job payload may still override either. upgrade: _none named_ — `no-trigger`.

## work/analysis/district4/metrics.py

- **:18** — areas and lengths are computed in a metre CRS picked once for the AOI (UTM zone from its centroid), not on a geodesic. ceiling: over a few square kilometres the error is far below the warp error the export already reports, and a projected CRS keeps this to shapely calls. upgrade: swap `_to_metres` for a geodesic measure if this is ever run on something continent-sized.

---

**66 markers, 14 with no trigger.**

## What changed since 2026-09-10

**The ledger was stale in both directions**, which is why this is a rewrite and
not a patch.

- **+19 markers.** The 2026-09-10 scan recorded 47; there are 66. The new ones are almost all in trees that scan never covered properly: the `/explore` feature components (`FootprintsLayer`, `ExploreBrowsePanel`, `ExploreRightSidebar`, `FocusPulse`, `HeroMap`, `HeroSequence` ×2, `exploreUrl`), the server helpers (`auth`, `gallica` ×3, `press` ×2, `warp`), `warpedOverlay`, `realtimeStub`, `playback`, `legendIndex`, `ocrReviewController` ×2, the editorial front page, the footprints export route, six more scripts, `083_series_sheets.sql`, and the `modern_prior` / `to_sam2_seeds` / `name_masks` markers in the pipeline trees.
- **Line numbers had moved a long way.** `ocr.py` 913 → 1185 and 2613 → 3346; `iiif_tiles.py` 406 → 492 and 676 → 762; `vma_worker.py` 322 → 398; `dedupe_ocr.mjs` 216 → 244; `pmtiles_extract.sh` 28 → 32; `write.spec.ts` 21 → 22; `press.spec.ts` 19 → 24.
- **Dropped rows.** Nothing in the 2026-09-10 ledger pointed at a file with no marker left, but `FeaturedSheet.svelte` — cited in the `backfill_iiif_widths.py` row — no longer carries one, so that row now describes the 1200px plate without naming a component that would have to be checked.
- **One row is out of date in its source, not here.** `tests/smoke.spec.ts:15` still says the write paths are uncovered; `tests/write.spec.ts` covers 31 of them against the local stack. The marker itself wants rewording or deleting.

## Ledger hygiene

**The grep at the top is the whole method now.** The plugin that used to
generate this file is gone (Sept 2026). Its scan pattern was also wrong in a way
worth remembering: it required a comment prefix (`#`, `//`, `/*`, `*`, `<!--`),
which drops every marker written inside a Python docstring — where this repo
puts most of its module-level ones — and every SQL `--` comment. A bare
`grep -rn 'ponytail:'` catches all of them.

**Hand-drop the prose mentions.** The grep scope above returns one non-marker
hit, `work/cleanup/TODO.md`, which is a scratch note rather than a comment on
code. Widen the scope beyond it and you also pick up this file's own header,
`CLAUDE.md`, `contracts/README.md:22` and `docs/time-machine-plan.md:232` — all
cross-references to the convention, none of them markers.
