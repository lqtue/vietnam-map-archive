# Time walk — plan (2026-09-12)

**Status:** proposed · **Owner:** lqtue · **Baseline:** VMA `main` @ fbfbfc2e;
HACW-rebuild `main` @ 2026-09-11 (`~/Downloads/Personal/test/HACW-rebuild`);
`docs/time-machine-plan.md` and `docs/platform-design.md` read 2026-09-12.

Track F of `docs/ROADMAP.md`. Track E turns the raster corpus into searchable
text and dated vector fabric; this is the surface a person **walks through** —
one district, on foot, with the sheets underneath and the old names on top.

**For the hurried reader.** Hội An got an event PWA (HACW) that works with no
signal: MapLibre over a shipped PMTiles extract, frozen JSON content, a GPS +
quiz check-in, a local passport. It is well designed and it is built to be
**forked per event**. HCMC has the opposite substrate — no usable L7014 topo
(the 25 ungeoreferenced JPGs in the series are exactly the ones over Saigon),
but **17 georeferenced city plans, 1799→1968, and a complete District 4 series
of 6**. So: fork the event app for a District 4 walk, and replace its single
modern basemap with a **stack of warped historical sheets and a year slider**.
The two codebases link through frozen JSON and PMTiles files, never a shared
runtime — that is what keeps the walk working underground.

---

## 0. The decision, and the one question that could overturn it

**Decided: fork HACW rather than extend VMA's `/trip/[id]`.**

VMA already has a walking-tour player — `/trip/[id]` is 1,273 lines with
`requestGeolocation` (in-context prompt), `createWalkTracker` (80 m spike
rejection), proximity auto-complete on *reach* stops, and
Intro → Itinerary → Playback → Complete. Printed QR codes point at it. On
capability alone it is most of the product.

What it does not have is the thing the event app exists for: **it does not work
without a network**. VMA is Supabase-backed, `ssr = false`, OL + Allmaps warping
client-side, ~321 kB gzipped on /explore's first load. Retrofitting a 12 MB
raster precache and an account-free local passport onto it is a rewrite of its
data layer, not a feature.

The fork is also what HACW was designed for — `platform-design.md` §2 records it
as "forked per event: code here, content in `content/<event>/`".

**Kill condition.** If the District 4 walk turns out not to need offline —
coverage is good, nobody is roaming, there are no prizes to hand out — then this
whole track collapses into *`/trip/[id]` plus a year slider*, and the right move
is to delete the fork rather than maintain a second app. Test it by walking the
route on a phone before F4 starts.

---

## 1. The substrate — why HCMC is the opposite of Hội An

| | Hội An | HCMC (District 4) |
|---|---|---|
| L7014 topo | sheet `6640-1`, 1984, ed. 003, `crs_forced: false`, graticule error 4.18e-12 — **already warped into `overlay/l7014-*.pmtiles`** | **hole.** The 25 JPG-only sheets are the ones over Saigon; `6641-3` (Da Nang) is one of them |
| Archive sheets | none georeferenced | **17 city plans** 1799 · 1862 · 1863 · 1864 · 1878 · 1882 (cadastral) · 1882 · 1895 · 1898 · 1900 · 1912 · 1922 · 1923 · 1930 · 1942 · 1959 · 1968 |
| D4 series | — | **1882 → 1895 → 1923 → 1942 → 1959 → 1968** (6 sheets, one AOI) |
| Labels / footprints | none | `ocr_extractions` 1,404 rows on **1 map**, 14 validated; `footprint_submissions` 46 rows, 1 map, zero SAM2 |

So Hội An ships one raster and no archive content; HCMC ships eight decades and
(today) one sheet's worth of names. **Make the walk District 4**: the series is
already complete there and it is the thesis AOI, so the tour and
`work/analysis/district4/` are the same dataset.

### The trap

`tiles.maparchive.vn` serves **IIIF level0 pixel tiles, not web-mercator XYZ**.
MapLibre cannot take them as a raster source, and Allmaps warps in the browser,
on OpenLayers, online — exactly what the event app cannot do. Every sheet the
walk draws has to be warped server-side, once, into PMTiles.

---

## 2. Warping a sheet — the pipeline already exists

`scripts/l7014_mosaic.py` is already control points → `gdalwarp -t_srs EPSG:3857
-r cubic -dstalpha` → mbtiles → `pmtiles convert` → R2. A sibling
`scripts/sheet_pmtiles.py <mapId> --bbox` changes two things:

1. GCPs come from the map's **Allmaps annotation** instead of `ds.GetGCPs()`.
2. The crop comes from `maps.triage.regions` — `tilingCrop()` in
   `src/lib/data/maps/triageTypes.ts` already returns `main_map` over the
   neatline, which is what keeps the legend and the paper edge out of the
   overlay.

Its three named failure modes carry over unchanged and are in `docs/pipelines.md`:
a datum code silently defaulting to WGS84, alpha-less tiles painting holes black,
and tiling past what the paper actually holds. Keep the `check` subcommand.

**The route defines the bbox, and the bbox defines whether this ships.** Hội An
is 0.027° × 0.017° ≈ 2.9 × 1.9 km → 1.3 MB of vector. A whole-city bbox at z17 is
several MB *per sheet* × 17 and unshippable; a route corridor is ~1–2 MB per
sheet. Measure with `pmtiles show`, do not trust an estimate.

`ponytail:` precache three sheets (1882 cadastral · 1923 · 1968 — three regimes,
the argument in miniature) and fetch the other five on demand. Widen only if an
offline complaint is real.

**Before anything outside this repo reads it:** `L7014_PMTILES_URL` still points
at `overlay/l7014-test.pmtiles`. A derived artifact behind a long edge TTL needs
its build date in the key, same rule as `basemap/vietnam-20260906.pmtiles`.

---

## 3. Time travel is a basemap choice, not an overlay

VMA already reads a PMTiles archive as a **basemap entry** (`l7014` in
`BASEMAP_DEFS`, `src/lib/map/basemapStyle.ts`). The walk does the same: one
raster source per year, a slider crossfading opacity between them. No new engine,
no Allmaps on a phone — 151 kB of `@allmaps/*` and the per-tile client warp both
drop out.

Most of the work lands in HACW's `SiteMap.svelte` (298 lines): add the raster
sources and the year control.

## 4. Space travel is the names, and that is what a raster cannot give you

`scripts/gen-hero-fabric.mjs` already generates exactly the needed artifact —
one sheet's footprints and validated labels, warped to lng/lat, frozen as a
module, **5.9 kB gzipped**. Run it per sheet clipped to the route bbox and ship
the JSON. Standing on Bến Vân Đồn and reading what the street was called in 1912
is the product; the raster underneath is the evidence.

---

## 5. How the two apps link

Three seams. None of them is a shared runtime.

**Identity — by coordinate, not by id.** Destinations already carry
`lat`/`lng`/`radius`; `GET /api/context?lng&lat&radius` (mig 066, `context_at`,
`contracts/context.schema.json`) already answers *what the archive knows about
this spot*, each row with `year`, `distance_m` and `geom_rmse`. Nothing to keep
in sync and no key that rots when a name changes. `place_key` (mig 067) is the
wrong key here — it is a Saigon OCR gazetteer, and a walk stop has no attested
label in it until the corpus is OCR'd.

**Transport — build time, never runtime.** `scripts/pull-archive.mjs` in the
fork: the story JSON plus one `/api/context` call per stop → `src/lib/data/archive/`,
committed as frozen content like everything else in `src/lib/data/`. No Supabase
client in the event app, no runtime fetch, offline intact.

**Validation — one module, two callers, on each side.** HACW's `src/lib/editor.js`
already gates both `scripts/check-data.mjs` (CI) and the organizer's download
button. VMA's `contracts/` + `tests/schemaCheck.ts` validates live API responses
in the write smoke. Join them at the file that crosses: `story.schema.json`
checked in `tests/write.spec.ts`, and a `checkStory()` in `editor.js` (~20 lines,
which `check-data.mjs` already imports). A shape change then fails on the side
that made it.

`contracts/story.schema.json` is VMA's `Story` serialized with two relaxations:
`title`/`description` may be a string **or** `{lang: string}`, and a stop gets an
optional `checkin` block. HACW keeps `destinations.json` as it is and writes a
~30-line `story-to-tour.js` adapter. Do not push HACW's model onto VMA or the
reverse.

**One direction only: VMA exports, the fork imports, never back.** Two content
editors owning one field is a sync loop with no winner. Canonical by subject:

| Content | Canonical | Why |
|---|---|---|
| hours, quiz banks, ticketClass, rewards, spotlight, event copy | fork `/organizer` | VMA has no concept of any of it |
| stops, years, sheets, labels, places, the story itself | VMA | it holds the maps, the review queue, the gazetteer |

### A correction worth keeping

`story.schema.json` sits at step 3 of `platform-design.md` §6, behind the engine
(1.5) and `packages/contracts` (2). It needs **neither** — no PostGIS, no
`context_at`. It can jump the queue, and Track F is why it should.

---

## 6. What of HACW actually reuses

28 components, ~3,900 lines. It is small because the decisions were made, not
because it is thin — and most of what is good is *written down* rather than
coded.

| Bucket | Contents | Moves how |
|---|---|---|
| **Decisions** | `DESIGN-SYSTEM.md`'s structure; the one rule that governs everything (*only one or two things loud per surface*, so the basemap is desaturated and the pins are the only saturated objects); pins as a real symbol layer drawn on canvas, not DOM markers; validate-in-two-places; frozen JSON *is* the app | Free. Carry the rules, re-derive the hexes |
| **Plain JS, node-tested** | `score.js` `route.js` `hours.js` `geo.js` `backup.js` `editor.js` `counts.js` `fraud.js` `sql.js` — no Svelte, no runes, each with its own `.test.js` | Verbatim into the fork; into VMA `$lib/core/` only if VMA gains a second consumer |
| **Svelte components** | 28 files, runes + Hội An tokens | Stay in the fork. VMA is legacy syntax and another brand — porting rewrites both halves |

Two ideas worth carrying **back** to VMA, neither of them runtime:

- **Spotlight** (`score.js`): live check-in counts push a bonus at the quieter
  half of the map, rebalancing itself with nobody editing anything, and falling
  back to survey columns when there is no API. VMA has no mechanism that pushes
  attention at the under-visited part of the corpus, and `map_opens` is already
  the count it would need.
- **Validation inside the editor**, not only in CI.

## 7. The delta to build

| | Hội An | D4 fork |
|---|---|---|
| basemap | `hoian.pmtiles`, Protomaps LIGHT overridden to the event palette | Saigon extract, same `pmtiles_extract.sh` recipe |
| **historical layer** | *(none)* | **N warped sheets as raster sources + year slider** ← the new thing |
| names | destination JSON | + per-sheet fabric from `gen-hero-fabric` |
| pins | mắt cửa on canvas | a Saigon motif, same symbol-layer technique |
| palette | peach / oxblood / gold | its own; the rule carries, the hexes do not |
| quiz · stamps · passport · rewards · spotlight · fraud · staff | ✅ | keep all of it, already built and tested |

---

## 8. Sequencing — each step ≤ 15 files

| Step | Does | Proven by | Not before |
|---|---|---|---|
| F0 | Walk the route with a phone; decide whether offline is real | the kill condition in §0 | now |
| F1 | `scripts/sheet_pmtiles.py` on the 1882 cadastral over one D4 bbox → a raster basemap entry in VMA | one sheet drawing in MapLibre proves the whole chain | now |
| F2 | Warp 1923 + 1968; the year slider | the slider means something at three positions | F1 |
| F3 | `contracts/story.schema.json` + `GET /api/stories/[id].json`, validated in the write smoke | VMA API + the fork | — (independent of F1/F2) |
| F4 | Fork HACW → D4 content, Saigon extract, `pull-archive.mjs`, `checkStory()` | the walk exists | F0 says offline is real; F2; F3 |
| F5 | `gen-hero-fabric --bbox` per sheet → names layer | 1882 today, more as OCR lands | F4 |
| F6 | Stops, quizzes, stamps — content only, machinery unchanged | — | F4 |

## 9. Honest limits

- **Rasters are ready for all 17 sheets; names are ready for one.** The year
  slider works now; the name layer is 1882 and nothing else until
  `scripts/enqueue_ocr_all.mjs` has run the corpus and the rows are reviewed.
- **Warp error is per sheet.** 1799 has few GCPs and metres of residual. Every
  row carries `geom_rmse`; show it, never pretend.
- **Eight languages of content** is the largest line in the fork's cost. The i18n
  machinery comes free; the translations do not.
- **Two Svelte dialects, two design systems, two deploys.** `platform-design.md`
  §4 already accepted this trade ("different brands by design"). It is still real.

## 10. Non-goals, with reopen conditions

- **Porting components in either direction** — reopen when a third app needs the
  same component twice.
- **One Svelte dialect** — reopen when a runes-only dependency or a measured DX
  cost forces the archive's hand.
- **The monorepo (`platform-design.md` §6 steps 4–5)** — reopen after F3 ships,
  so the import carries a real shared dependency rather than a hope.
- **A runtime API between the two apps** — reopen if a walk must update without a
  redeploy. It costs the offline guarantee, which is the fork's whole reason.
- **Satellite imagery in the walk** — HACW dropped it deliberately: it was the one
  part of the map that needed the network. Reopen never.
