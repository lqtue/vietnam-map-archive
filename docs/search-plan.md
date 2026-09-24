# Search — plan (2026-09-02)

Was "Time machine"; renamed 2026-09-22 because it and "Time walk" were indistinguishable.

Design detail for **Search** in `docs/ROADMAP.md` (the single tracker). Vision in
`docs/strategy.md` / `docs/theory.md`; this file is the engineering plan only.

**One sentence.** Turn the georeferenced raster corpus into searchable text, dated
vector fabric and linked period sources, so a visitor can type a place name, land on
it across decades, watch the fabric change, and read what the press said at the time.

Five products on one substrate (jobs → HITL → RPC-gated tables):

| # | Product | Gives the user | Gives the thesis / Tasco |
|---|---------|----------------|--------------------------|
| E1 | Label search | "Khánh Hội" → every map that names it, jump to the spot | Gazetteer of attested names by year |
| E2 | Temporal fabric | Blocks/buildings/canals per map as vectors on the modern basemap; slider across years | District 4 morphology metrics 1878→1968; same recipe for any AOI |
| E3 | Period sources | Click a label → press clippings from that decade (Gallica) | L5/L6 context, citable |
| E4 | Corpus growth | More decades, more sheets | Coverage per decade for the AOI |
| E5 | Building attributes | (later) levels / roof / material per footprint → OSM tags, LoD2 | Deferred until E2 fabric is stable |

Measured against production, 2026-09-02:

| Fact | Value | Consequence |
|------|-------|-------------|
| `ocr_labels` | 1,404 rows, **1 map**, 14 validated | E1 is empty until OCR runs on the corpus |
| `footprints` | 46 rows, 1 map, all `submitted/volunteer`, **zero SAM2** | E2 needs the `seg` runner first |
| Georeferenced Saigon city plans | 1799 · 1862 · 1863 · 1864 · 1878 · 1882 (cadastral) · 1882 · 1895 · 1898 · 1900 · 1912 · 1922 · 1923 · 1930 (Gia Định) · 1942 · 1959 · 1968 | District 4 series is already there: **1882 → 1895 → 1923 → 1942 → 1959 → 1968**. The 1878 and 1898 plans are wholly north of the Bến Nghé canal. |
| Drafts, ungeoreferenced | 62, all 1900–1929 | E4 is a georef sprint, not an ingest problem |
| Corpus scope | Saigon **plus Hanoi and Huế** sheets already georeferenced | Basemap PMTiles is a Saigon extract only; a Hanoi view needs a second extract |

---

## E1 — Label search

**Data.** `ocr_labels(text, text_corrected, category, global_x/y/w/h, map_id, run_id, review_status)`.
Read `coalesce(text_corrected, text)`, skip `rejected`. Categories worth indexing:
`street hydrology place building institution`; drop `legend* title other` (noise).

**Why trigram, not tsvector.** Labels are 1–3 words, OCR'd (typos), French *and*
Vietnamese (accents). `pg_trgm` similarity handles all three; tsvector handles none of
them well on this corpus. Accents: `unaccent` is not immutable, so wrap it.

```sql
-- 065_ocr_label_search.sql
create extension if not exists pg_trgm;
create extension if not exists unaccent;
create or replace function public.f_unaccent(text) returns text
  language sql immutable parallel safe strict
  as $$ select public.unaccent('public.unaccent', $1) $$;
create index ocr_extractions_label_trgm
  on ocr_labels using gin (lower(f_unaccent(coalesce(text_corrected, text))) gin_trgm_ops);
-- rpc: search_labels(q text, lim int) → (map_id, text, category, x, y, w, h, sim)
--   where f_unaccent(lower(q)) % f_unaccent(lower(coalesce(text_corrected,text)))
--   and review_status <> 'rejected' and category in (…)
--   and (maps.status in ('public','featured') or auth.uid() is not null)   -- mig 063 rule
--   order by sim desc, confidence desc; dedupe (map_id, lower(f_unaccent(text))) keep best
```

RPC (not a view) because the caller passes `q`; `security invoker` so RLS on `maps`
(mig 063) gates draft labels exactly as it gates draft maps.

**API.** Extend `/api/search` (one endpoint, the catalog already calls it):
`include=labels` → `labels: [{ map_id, map_name, year, text, category, bbox:[x,y,w,h], lng, lat }]`.
Warp `bbox` centre through `getTransformer()` (`$lib/server/transformer.ts`), one fetch
per distinct map, ≤ 20 maps per query; mirror URLs live on Storage so this is fast.
`lng/lat` null when the map has no annotation.

**UI.**
- `/catalog` search → a third result block "On the map": *text · map name · year* →
  `/explore?map=<id>&at=<lng>,<lat>`.
- `/explore` Browse pane search box → same call, same links, in place.
- `applyExploreUrlParams` reads `at=` → after `zoomToMap`, `view.animate({center, zoom:17})`
  and a 3 s pulse marker. One param, one reader, done.

**Feeder.** E1 is worth nothing on one map. `scripts/enqueue_ocr_all.mjs`: for every
`is_georeferenced` map with no `ocr` job, insert one `pipeline_jobs` row (worker already
runs `ocr,join`). Gemini Flash cost is cents per map. Run the worker on M1 overnight.

**Gazetteer (E1b, after E1 ships).** A view, no table:
`place_names(norm_text, variants[], years[], map_ids[], lng, lat)` grouped by
`lower(f_unaccent(text))` over validated + high-confidence rows. Powers "this street had
three names under three regimes" and feeds E3 queries with all variants at once.

**Check.** One write smoke: seed 2 extractions on the local stack (one on a draft map),
query anon → draft label absent, typo'd query still hits.

---

## E2 — Temporal fabric (District 4 first)

**Goal.** For an AOI polygon and the maps that cover it, per-year WGS84 vectors of
`building / land_plot / road / waterway / water_body / green_space` → morphology metrics
(built-area %, block size, road density, canal length) → figures + a slider on /explore.

**What exists.** `footprints.pixel_polygon` + `feature_type`; SAM2 writer fixed
(C0); `join` job; `/api/export/footprints?format=geojson` **already warps** px→geo via the
same transformer. `/scan?mode=shapes&tab=validate` is the HITL.

**What is missing, in build order.**

1. **`seg` runner.** The worker fails `seg` back today. MapSAM2 runs on Colab; the worker
   already talks to the API with a bearer key and no DB creds, so run
   `python work/worker/vma_worker.py --kinds seg` **inside the Colab notebook** (GPU
   session = a worker). One cell. Mint a `seg`-scoped key.
2. **AOI-focused triage.** `iiif_tiles.py --aoi minLng,minLat,maxLng,maxLat`: warp the
   AOI corners to source px with `transformToResource`, mark tiles outside as `skip`.
   Same knob in `TriageSidebar` ("Limit to area", takes the current /explore viewport).
   Cuts OCR + seg cost to the study area; also makes the HITL queue District-4-sized.
3. **Export upgrade** (`/api/export/footprints`): `map_id` accepts CSV; default
   `status=approved` (anon must never receive `submitted`); `year` from `maps` join in
   properties; `bbox=` geo filter applied after warping. Still anon-key + RLS.
4. **Footprint overlay on /explore.** Per row in `LayerStackPanel`, a "vectors" toggle that
   adds an OL `VectorLayer` from the export URL for that map. Year order = the stack order
   the user already controls; opacity slider already exists. **That is the slider.**
5. **Analysis lives outside the app.** `work/analysis/district4/` — geopandas notebook:
   pull export per map, clip to AOI, metrics table per year, figure series
   (1878 / 1898 / 1923 / 1942 / 1959 / 1968). Reproducible, citable, QGIS-openable.
   Tasco: same notebook, different AOI + maps.

**Time semantics.** Each footprint is *observed on map year Y*. No `valid_to`, no temporal
DB. Change = geopandas overlay of two years. `valid_from` stays nullable and unused
until a real need shows.

**B8 (PostGIS) stays deferred.** Re-open only when /explore wants *city-wide* fabric
layers or live metrics. Per-map GeoJSON + geopandas covers E2 as specified.

**Eval by-product.** C5 is blocked on ~20 hand-labelled tiles. Reviewing District 4 on 6–8
maps produces exactly that set — export the approved polygons as the seg ground truth.

**Check.** Export smoke on the local stack: seed 1 approved + 1 submitted footprint,
anon call returns only the approved one, warped, with `year`.

---

## E3 — Period sources ("news of that time")

**Sources with APIs** (ranked):

| Source | Covers | API | Note |
|--------|--------|-----|------|
| Gallica SRU + ContentSearch | *L'Écho annamite* 1920–44, *Le Courrier saïgonnais*, *La Dépêche d'Indochine*, *Bulletin officiel de l'Indochine*, **Annuaire général de l'Indochine** (street-by-street directories) | `gallica.bnf.fr/SRU?…&query=(gallica all "…") and dc.date>=…` → ark → `ContentSearch?ark=…&query=…` for page snippets; page images via IIIF | Slow (1–3 s); full text is OCR, mostly unaccented |
| Internet Archive full-text | books, US-era reports | `archive.org/advancedsearch.php` | Second |
| Chronicling America (LoC) | US press to 1963 | JSON | Marginal for Saigon |
| Wikidata / vi.wikipedia | street-name history | `wbsearchentities` | Feeds E1b variants |

**Design — no table.** `/api/press?q=<label>&year=<Y>&window=10&limit=10` → server builds the
query from `place_names` variants (or the raw label), OR's spelling forms
(`Khanh Hoi`, `Khanh-Hoi`, `Khánh Hội`), calls Gallica, returns
`[{ title, date, snippet, url, thumb }]`. `Cache-Control: public, max-age=86400` so the
CF edge absorbs repeats; Gallica sees each (q, decade) once a day. (The route is
`/api/press`, not `/api/context` — that name belongs to the place-time index in
`docs/platform-design.md` §0.)

**UI.** On /explore, clicking an E1 result marker or a `LegendPointsLayer` point opens a
compact "In the press, ±10 y" list in the sidebar. /explore only; the SSR share page must
not call Gallica per request.

**Later, when someone asks.** Pinning a clipping to a map/point = a `sources` table with
`status/submitted_by/reviewed_by`, moderated in `/scan?mode=shapes&tab=validate` like stories.
*Annuaire* ingestion (merchants by street → L5 POI) is its own project; note only.

**Check.** Unit-level: the query builder emits the expected CQL for a two-word
Vietnamese label with diacritics.

---

## E3b — Period text sources and the attested gazetteer (planned 2026-09-22)

E3 queries two archives with **three guessed spellings** of a place name. This section is how
they stop being guesses. It was opened by one thing arriving: Tim Doling's *Historic Vietnam*
export (268 posts, 3.1M chars, 2013–2026), given by the author, who agreed on 2026-09-22 to be
cited.

`src/lib/server/gallica.ts:60` had already named the gap and the fix:

> Historical *renamings* ("rue de Canton" → "Triệu Quang Phục") are still not derivable from
> spelling and this function does not pretend otherwise — those come from the gazetteer too,
> **once someone links them.**

`scripts/oneoff/extract_doling_placenames.mjs` produced `rue de Canton → Hàm Nghi boulevard` on
its first run. This is that link.

### The two archives are not the same kind of source

Verified by request on 2026-09-22, not inferred:

| | Gallica (BnF) | NLV (`baochi.nlv.gov.vn`) |
|---|---|---|
| Full text | **Yes** — SRU + `ContentSearch`, OCR mostly unaccented | **Not retrievable.** Search is full-text, so the OCR exists server-side; the article view offers `img` mode only, and `imageserver.pl?...&getpdf=true` without a session `key` returns **404** |
| Role here | a **source** of names, and a corpus to harvest | a **consumer** of names — `press-from-gazetteer`, nothing more |
| Feed shape | `spellingVariants(name, extra)`, keyed by modern name | quoted phrases, because Veridian's `txq` ANDs an unquoted query |

NLV carries French colonial titles too (a probe hit *Journal officiel de l'Indochine Française*,
6 Aug 1896), so the colonial forms are worth querying on **both**.

Getting NLV's Vietnamese text would mean OCR'ing page images ourselves (~220 kB/page at 2000px).
That is a project, not a script, and the pipeline we own is tuned for map sheets, not newsprint
columns. **Not planned.** Revisit only if E3b's extraction proves worth scaling.

### Phases, in order, each gated

- [ ] **`doling-review`** — send the 89-row sheet (`work/doling/street-name-pairs.csv`) to its
      author. 43 `street`, 34 `unclear`, 10 `address`, 2 `building`; the `unclear` bucket is where
      the value and the errors both are. **This is the measurement, and it comes first for the same
      reason `shape-precision` exists**: there is a name-extraction pipeline with no accuracy
      number, so every change to it is currently unfalsifiable. Exit: a precision figure for the
      extractor with its sample and limitations recorded beside it, and his corrections kept as the
      eval set for any later pass.

- [ ] **`gallica-text-harvest`** — polite, offline, its own script. **Not through
      `src/lib/server/gallica.ts`**, which is a live per-reader lookup with a 6 s deadline, three
      snippets and no rate limiter; harvesting through it would be rude to BnF and wrong for the
      job. Model it on `scripts/scout_nlv_press.mjs`: sequential, resumable offsets, a saved
      fixture, `--selftest` pinning the parser so a template change fails loudly. Titles, and they
      are the three `docs/private/network.md` names as Ian Gregory's material: *Annuaires de
      l'Indochine*, *L'Opinion*, *La Dépêche d'Indochine*. Exit: text on disk with per-document
      provenance, and the same pair extractor run over **primary** sources rather than Doling's
      secondary prose.

- [ ] **`attested-variants`** — the reviewed pairs into the gazetteer, not beside it.
      `work/doling/gallica-variants.json` feeds `spellingVariants`' `extra`; the store of record is
      `place_names.variants[]` (mig 067). **One normalisation rule, not a third** —
      `dictionary-on-place-names` already records that two will drift. Exit: `/api/press` for
      "Đồng Khởi" returns a hit reachable only via "rue Catinat", and the response cites where the
      variant came from.

- [ ] **`ocr-suggestions`** — a suggestion side-table (`suggested_text`, `source`, `score`,
      `evidence_url`), reviewed by a person, and **nothing writes `text_corrected` but a human**.
      That column is what `eval.py ocr` scores against; a dictionary writing it launders model
      output as ground truth. This archive has already paid for that error once — 72 `sam-auto`
      rows in `footprints` voided every `building` figure at n=89
      (`work/ocr/EVAL-BASELINE.md`, corrected 2026-09-18), which is why `shape-precision` says *by
      construction*. The matching needs no new code: `f_unaccent` + `word_similarity` ship in mig
      065. Target the class the roadmap already names — `ARSENAL DE L`, `HOTEL DU GNRAL`, a bare
      `Rue` seen 14 times. Exit: the eval baseline is **unchanged** after a suggestion run, and an
      accepted fix carries its citation.

- [ ] **`source-agreement`** — the better half. A name read off a sheet that also appears in a
      dated period source is two independent sources agreeing, which is a quality signal the corpus
      does not have today. Feeds `ocr-merge-evidence`'s "store agreement as structured data".
      Exit: a reviewer can see *which* sources agree on a reading, not a single blended score.

### Scope, stated so it stops competing

63 place names against 1,544 extractions cleans a handful, not a corpus. The value is that each
fix is citable and that agreement becomes measurable — not volume. And **none of this is on the
critical path.** `docs/private/priority-2026q4.md` still runs: the traced window → `seg_eval
--window` → the Zenodo DOI → the letter-writer packet. E3b is good work that must not displace it.

## E4 — Corpus growth

**Bottleneck is georef, not ingest.** Scout already covers gallica / rumsey / loc /
humazur; 62 drafts wait for a human in `/contribute/georef`.

- **Sprint list, by value:** `select year, name from maps where not is_georeferenced order by year`
  filtered to sheets covering the District 4 peninsula; target ≥ 3 georeferenced city plans per
  decade 1860–1975.
- **Series propagation** (proven on L7014) for any uniform series in the drafts.
- **New scout sources:** UT Austin PCL (Vietnam city plans), NARA aerial indexes, ANOM
  where IIIF exists. hanoimaps.github.io is a link list, mine it for sources; pastmaps
  is a competitor, not a source.
- **Hanoi / Huế views:** sheets exist; needs a second PMTiles extract per city and a
  basemap key per region. Not before E1–E3 land for Saigon.

---

## E5 — Building attributes → OSM tags → LoD2 (deferred)

Needs per-building imagery: Flickr *manhhai* collection (huge, CC), Gallica postcards, 1960s
NARA aerials. Pipeline: photo ↔ footprint link (HITL "which building is this"), VLM
extract `building:levels`, `roof:shape`, `building:material`, `start_date`, human
verify, write `footprints.tags jsonb`. LoD2 = footprint × levels × 3 m + roof
shape → CityJSON. **Add the `tags` column with the first writer, not before.**
Start only after E2 shows stable, reviewed fabric on ≥ 3 maps.

**Why OSM tags and not CityJSON first** (recorded 2026-09-20). Simple 3D Buildings is a schema
the owner already worked in at Tasco, and it renders today in open-source WebGL clients
(StreetGL, OSM Buildings) with nothing written. CityJSON needs a pipeline before anything is
visible. Tags first is the shorter path to a picture, and it closes no door: tags → CityJSON is
the `× levels × 3 m` line above, and `cjio` is there when a geomatics collaborator wants the
standard format. `docs/archive/4d-city-model-plan.md` is CityJSON-first; it is frozen, and E5
supersedes it on this point.

**And the tag split is the honesty mechanism, so do not collapse it.** `building:levels` is a
**count** — an oblique view can support it, because storeys are countable in an engraving.
`height` is **metres**, which no pictorial panorama can establish. Write `building:levels`;
leave `height` unset and let the renderer apply its own default. The `× 3 m` above is a
rendering convenience, **never a value to store** — the moment it lands in a `height` tag the
archive is asserting a measurement it does not have. Same rule as `geom_rmse`: carry the
uncertainty, do not launder it.

**Where it goes to be seen.** OSM tags plus `start_date`/`end_date` is OpenHistoricalMap's own
model, and OHM is already listed as an open-ecosystem home in `docs/private/network.md` §5. So
the chain is tags → OHM → renders, with no new format anywhere in it.

---

## Cross-cutting

- **HITL surfaces already exist** for everything E1–E3 write: OCR → `OcrSidebar`;
  footprints → `/scan?mode=shapes&tab=validate`. No new review screens.
- **Every write is a job or an RPC** (Track B rule). New job kinds: none. New RPC:
  `search_labels`. New migration: 065.
- **Visibility.** Labels and footprints inherit the map's gate: anon sees `public/featured`
  only (mig 063); export defaults to `approved`.
- **Layering.** Search UI in `features/catalog` + `features/explore`; warp in
  `$lib/server/transformer.ts`; Gallica client in `$lib/server/gallica.ts`; nothing
  domain-specific in `ui/`.
- **Cost.** OCR: Gemini Flash, cents/map. Seg: Colab GPU hours. Gallica: free, be polite.

## Risks

| Risk | Mitigation |
|------|------------|
| E1 launches empty | Run `enqueue_ocr_all` + worker before shipping the UI |
| Seg quality on 1880s hand-drawn plans unknown | AOI-limited runs; District 4 review doubles as the C5 eval set |
| Warp accuracy varies by map's GCPs | Export carries `geo_converted`; notebook reports RMSE per map from the annotation |
| Gallica latency / outage | Edge cache; UI degrades to "no sources found" |
| Draft labels leak to anon | RPC is `security invoker`; write smoke asserts it |

## Milestones

| | Ships | Demo |
|-|-------|------|
| **M1** | 065 + `search_labels` · `include=labels` · catalog + explore results · `at=` deeplink · `enqueue_ocr_all` run on all georeferenced maps | Type "Khánh Hội", land on it on the 1923 plan |
| **M2** | `seg` on Colab · `--aoi` triage · export upgrade · vectors toggle · `work/analysis/district4/` with the 6-map series | District 4 built-area % 1882→1968, slider on /explore |
| **M3** | `/api/press` + press panel | Click "Khánh Hội" on the 1923 plan, read *L'Écho annamite* 1920s |
| **M4 (ongoing)** | Georef sprint by decade gap · new scout sources | ≥ 3 city plans per decade |
| **E5** | after M2 is stable | — |

Order: M1 → M2 → M3; M4 in parallel whenever there is human time; E5 not before M2 is reviewed.

## E1 as built (2026-09-02)

Diverged from the sketch above in two places, both measured:

- **RPC is `security definer` with `p_public_only`**, not `security invoker`. `/api/search` runs on
  the service client and already knows the role; invoker would have made the RPC useless from there.
- **No trigram index.** `<%` reads `pg_trgm.word_similarity_threshold`, which the `postgres` role
  gets *permission denied* setting on a function under Supabase, and its 0.6 default misses
  one-letter typos ("khan hoy" → "khanh hoi" = 0.55). Explicit `word_similarity() >= 0.5` instead;
  the upgrade path is in the migration's `ponytail:` note.
- Bonus fix: `ocr_extractions` read policy had been `using (true)` since 040 — every draft map's
  labels were readable with the publishable key. Now gated like `maps` (mig 063).
