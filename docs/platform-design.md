# Platform design — one codebase for VMA, HACW and what comes next (2026-09-02)

**Status:** proposed · **Owner:** lqtue · **Baseline:** VMA `feat/label-search` @ bccd495, HACW
`main` @ 2026-08-30, Tasco `platform/docs` read 2026-09-02.
Detail for the "Platform" idea in `docs/strategy.md`; the Search product plan is
`docs/search-plan.md`, Walk is `docs/walk-plan.md` — which forks the event app rather
than merging it, and jumps §6's queue with `story.schema.json` (it needs neither the engine nor
`packages/contracts`).

**For the hurried reader.** At the core is not an app but a **place-time index**: Postgres + PostGIS
answering *what was here, when, and what was it called* (§0). Three codebases share an author: VMA
(SvelteKit, legacy syntax, OpenLayers + Allmaps, Supabase, Python workers), HACW (SvelteKit, runes,
MapLibre + shipped PMTiles, no backend), and Tasco's mobility platform (employer's Go/React monorepo
— a source of practices, not code). Tasco's docs encode one rule that settles the unification
question: **promote something to shared only when a second real consumer exists**
(`tasco/platform/docs/engineering-workflow.md:79`). Applied honestly, that yields a small pnpm
monorepo whose shared surface is **contracts, basemap recipe, deploy conventions, docs system,
decision register** — and leaves map engine, data store, auth, design tokens and Svelte syntax
per-app. Unify the seams, not the bodies.

---

## 0. The engine — a place-time index in Postgres

Everything above is packaging. The thing being packaged is one query:

> **`(lng, lat, year?)` → everything the archive knows about that spot**, and its inverse **`text` →
places** (E1 shipped that half).

That is what no competitor has. `pastmaps` browses rasters; `hanoimaps` is a static site; a IIIF
viewer serves pixels. An archive that can answer *what was here, when, and what did people call it*
is a data product, and the apps in §2 are its clients.

### Where the geometry is today

| Content | Geometry stored as | Queryable by location in SQL? |
|---|---|---|
| `maps` | `bbox` column | yes, coarse |
| `ocr_extractions` (labels) | source-image pixels `global_*` | **no** — warped in TypeScript per request |
| `footprint_submissions` | source-image pixels `pixel_polygon` | **no** — same |
| legend points | not stored; computed per request | no |
| `story_points` | lng/lat | yes |
| press sources (E3) | not stored; fetched live | no |

Every map-derived row is in pixel space, and the pixel→geo warp happens in
`$lib/server/transformer.ts` on each request. So "what was here in 1923" cannot be one query today.
Closing that is the engine.

### Decision: PostGIS, warped on write, read through RPCs

1. **`create extension postgis`.** Supabase's Postgres ships it; no new infrastructure, no second
   store.
2. **Add derived geometry beside the pixel columns**, never instead of them:
   - `ocr_extractions.geom geography(Point,4326)` — the bbox centre warped.
   - `footprint_submissions.geom geography(Polygon,4326)` — the ring warped.
   - both plus `geom_src text` (the annotation version the warp used) and
     `geom_rmse double precision` (that map's GCP residual).
   - GiST index on each; `geom` is null until warped, and null is a legitimate state
     (ungeoreferenced map).

   Pixel coordinates stay the master; `geom` is **derived, disposable and rebuildable** — the rule
   from `tasco/platform/docs/map-data-operations.md:39-45`. Nothing hand-edits it, and `geom_src` is
   what says whether it is stale.
3. **Warp on write, in the writer that already holds the transformer.** Every path into these tables
   is a server route on the service key: `/api/pipeline/results` (worker OCR rows),
   `/api/contribute/footprints` (hand traces), `/api/admin/maps/[id]/ocr-review` (manual bboxes and
   coordinate edits). Each already resolves the map, so each computes `geom` inline.
   Re-georeferencing is the only other event that invalidates it: `$lib/server/annotationMirror.ts`
   enqueues one `warp` job per map, and the worker recomputes that map's rows through
   `/api/pipeline/execute` — the kind that runs server-side because it needs the service key. One
   new job kind, no new machinery.
4. **Read through RPCs, never PostgREST on a geometry column.** `supabase gen types` renders PostGIS
   types as `unknown`, and a client that selects `geom` gets WKB it cannot use. Two functions, both
   `security definer`, both gated exactly as migrations 063/065 gate their tables:

   ```
   context_at(lng, lat, radius_m default 150, year_from default null, year_to default null,
              public_only default true) → jsonb
     { maps: [...], labels: [...], footprints: [...], legend_points: [...], stories: [...] }
   ```

   Each item carries `map_id`, `year`, `distance_m`, and the warp's own `geom_rmse`, so a caller can
   weigh a 1799 sketch differently from a 1923 cadastral plan. Sister function `map_context(map_id)`
   answers the map-centric view (everything this sheet knows), which is what
   `/api/export/footprints` and the thesis notebook want.

### Why this is the platform's first contract, ahead of stories

`context.schema.json` has more real consumers than anything else on the §3 table:

| Consumer | Uses |
|---|---|
| archive `/explore` | click the map → "here, across time" panel |
| archive E3 | nearby label names → the Gallica query, instead of one clicked label |
| `apps/event` | "what stood here in 1923" on a festival map, no Supabase client needed |
| `work/analysis/district4` | AOI query per year instead of warping in the notebook |
| Tasco / any planner | the same call with a different AOI |
| an LLM tool later | one function, one JSON shape: "ask the archive about this place" |

So step 2 of §6 leads with `context.schema.json`, and `story.schema.json` follows.

### What this changes in the tracker

- **B8 un-defers, re-scoped.** It was written as "PostGIS on footprints + `build_pmtiles`", deferred
  because a geometry column only pays off when /explore wants city-wide layers. That reasoning holds
  for *rendering* and is wrong for *querying*: the index pays for itself the first time anything
  asks a spatial question, which E3 and the thesis both do. Vector tiles stay deferred;
  `build_pmtiles` stays a non-goal.
- **E2's export becomes a view over the index** rather than a warp loop per request.
- **E1 is already the inverse half** of the engine — text → place. `context_at` is place →
  everything.

### Honest limits, carried in the response

- **Warp error is per map and sometimes large.** A 1799 sketch has few GCPs and metres of residual;
  asking for a 150 m radius there is fiction dressed as data. Every row returns `geom_rmse` and the
  UI shows it. Flag, never pretend — `tasco/BUILDINGS_PLAN.md:345-347`.
- **`geom_src` is the staleness contract.** A map re-georeferenced after a warp has rows whose
  `geom_src` no longer matches its annotation; the `warp` job clears that, and a mismatch is a
  queryable defect rather than silent drift.
- **Radius, not containment.** A label's point is its bbox centre, not its extent, so `context_at`
  answers "near here", and the honest unit for a street name is tens of metres.
- **No temporal database.** `year` comes from the map the row was observed on; there is no
  `valid_to` and no attempt at continuity between sheets. Change is computed by comparing two years,
  in the notebook or in the caller.

## 1. What Tasco's docs teach, and what we adopt

| Principle (Tasco) | Source | Adopt as |
|---|---|---|
| Contract-first; generated code is never the editing surface | `engineering-workflow.md:33-40,136-141` | `packages/contracts`: JSON Schema → generated TS types; a contract change is its own commit |
| Promote to shared only on a **second real consumer** | `engineering-workflow.md:79-84`, `operating-model.md:37-38` | The test every shared package must pass (§3) |
| A root path must imply a real ownership/lifecycle difference | `operating-model.md:42,62-69` | `apps/archive` (continuous) vs `apps/event` (per-event fork) vs `packages/*` vs `work/*` (pipelines, notebooks) |
| One entrypoint; CI runs the same targets | `operating-model.md:494-504` | Root `pnpm -r check/lint/test/build`; no per-app CI logic |
| Logic in env-driven scripts; make / jobs are thin shells | `map-data-build-and-release.md:284-296` | Already true for `vma_worker.py` + `ocr.py`; keep for `pmtiles_extract.sh` |
| Master vs derived: derived is disposable, immutable, content-addressed, **no `latest`** | `map-data-operations.md:39-45`, `operating-model.md:441-473` | Postgres + Storage annotations = master; R2 tiles, PMTiles, exports, thumbs = derived, keyed by content hash |
| Machine may create, never overwrite a human edit | `map-data-operations.md:45` | Already in RPCs (`text_validated` wins); written into `db-guidelines.md` as invariant |
| Plain queue jobs, no DAG until a DAG exists; idempotent, keyed | `map-data-build-and-release.md:147-152` | `pipeline_jobs` stays as is |
| Rules live in **absent code paths**, not prose | `map-data-operations.md:280-289` | e.g. anon has no path to draft rows (mig 063/065), workers have no DB creds |
| Evidence discipline: every claim cites a file/query; phase exits are commands, not adjectives | `map-data-operations.md:18-30` | ROADMAP already "measured against production"; add Status/Owner/Baseline headers |
| Advisory first, blocking after two clean weeks | `map-data-operations.md:366-368` | Any new CI gate (bundle check, eval harness) starts advisory |
| MR ≤ 15 files / ≤ 1500 lines / ≤ 1 contract change | `map-data-operations.md:547-551` | PR rule for the platform repo |
| Non-goals recorded **with reopen conditions** | `map-data-operations.md:26-27,555-578` | §6 below |
| Decision register + retraction table + kill conditions; measurement beats spec | `tasco/MATH-AND-DECISIONS.md:13-14,463-499,630-647` | `docs/decisions.md` (§5) |
| Reuse the one approval surface; never a second review UI | `mapops-indexing-tasking-prd.md:33,76` | `/scan?mode=shapes&tab=validate` is the only moderation queue, tab per kind |
| Protected **random audit core** so targeted review cannot self-confirm | `collection-system-plan.md:370`, `MATH-AND-DECISIONS.md:334-345` | 5 % of validated OCR/footprints re-queued blind (E2 HITL) |
| QA at edit time is the cheapest cell and the one most skipped | `collection-system-plan.md:280-291` | Category enums + required fields enforced in the API, before sampled QC |
| Log predictions **before** collecting; score with a proper rule | `collection-system-plan.md:448-479` | C5 eval: freeze the 20-tile set and the metric before the next seg run |
| Blind hand-digitised validation gate | `BUILDINGS_PLAN.md:151-156,360-371` | District 4 review set doubles as that gate |
| `fp_src` / `fp_conf` / disagreement flags on every synthesised geometry; unknown floors emit a flagged range, no model pretends | `BUILDINGS_PLAN.md:262-376,345-347` | E2 footprints already carry `source`/`confidence`; E5 adds `tags` with `*:src` |
| CityJSON is truth, 3D Tiles a render derivative | `FORASPACE-BRIEF.md:66-72` | E5 output shape |
| Handoff = 30-min green run + one executable contract check + "three facts that bite" + runs-today vs doesn't-exist | `handoff-ds/HANDOFF-NOTES.md:14-45,83-88,200-235` | `work/analysis/district4/` and every client deliverable |
| Three-layer docs: root curated / `guides/` / `journals/`, promote rarely; README is an index | `.agents/AGENTS.md:105-113`, `README.md:5-14` | §5 |
| One canonical agent policy, thin per-tool adapters | `.agents/AGENTS.md:5-10` | `docs/AGENTS.md` canonical; `CLAUDE.md` becomes an adapter |

**Explicitly not adopted** (Tasco-scale, wrong here): two-repo Argo release plane; three speed
planes; two-cloud airlock ADR; H3 grid + MAUP apparatus; K ≥ 4 blind-source latent-class model (a
historical sheet is one image, and two OCR engines see the same pixels — the doc's own objection at
`collection-system-plan.md:342`); contributor-history estimators; crew routing / CELF;
ablation-based value; Keycloak SSO.

---

## 2. Shape

```
platform/                          (pnpm workspace; today = the VMA repo, renamed)
├─ apps/
│  ├─ archive/                     VMA. SvelteKit, OL + Allmaps, Supabase, CF Pages. Continuous.
│  └─ event/                       HACW shell. SvelteKit runes, MapLibre + shipped PMTiles, D1, CF Pages.
│                                  Forked per event: code here, content in content/<event>/.
├─ packages/
│  ├─ contracts/                   JSON Schema + generated TS. The platform's public surface (§3).
│  └─ basemap/                     pmtiles_extract.sh <bbox> <out> + Protomaps flavor overrides.
├─ work/                           Python: ocr/, worker/, MapSAM2/, analysis/<study>/   (archive-only today)
├─ docs/                           root curated · guides/ · journals/ · decisions.md · adr/
└─ package.json                    check · lint · test · build → pnpm -r
```

Two apps, two packages. No `packages/ui`, no `packages/map`, no `packages/tokens`. Each of those has
one consumer.

**Why a monorepo at all** (vs. two repos + copy): shared packages without publishing; one
`check/lint/test` lane; one docs tree; one agent policy; HACW's per-event fork becomes
`content/<event>/` instead of a repo per festival. Cost: CF Pages root-dir setting per app, one-time
`git subtree` import of HACW, and the discipline of §6.

---

## 3. The shared surface — each row has ≥ 2 real consumers today or on the next milestone

| Contract / package | Producer | Consumers | Status |
|---|---|---|---|
| `context.schema.json` — `context_at(lng, lat, radius, years)` → maps · labels · footprints · legend points · stories, each with `year`, `distance_m`, `geom_rmse` | archive RPC (§0) | archive `/explore` + E3, event map, thesis notebook, any planner AOI, an LLM tool later | **The engine's contract.** Leads step 2 |
| `story.schema.json` — tour with stops `{id, title, lng, lat, mapId?, year?, body, media[]}` | archive `/explore?mode=story` | archive `/trip`, event `/tours` + check-in | **The unification with teeth.** Author once in the archive, ship frozen JSON in the event PWA. Replaces HACW's hand-edited `tours.json`. |
| `label-hit.schema.json` — `/api/search?include=labels` row | archive API | archive `/catalog` + `/explore`, event map (historical labels as pins), thesis notebook | Shipped in E1; freeze shape |
| `legend-point.schema.json` | archive API | archive `LegendPointsLayer`, event map | Freeze |
| `footprint-feature.schema.json` — GeoJSON properties of `/api/export/footprints` | archive API | thesis `work/analysis`, Tasco QGIS, event map (E2) | E2 export upgrade defines it |
| `packages/basemap` — extract script + style overrides | — | archive (Saigon 37 MB in R2), event (Hội An 1.3 MB shipped), Hanoi/Huế extracts (E4) | Both repos carry the command today, differently |
| Deploy conventions — adapter-cloudflare, env in dashboard, `node:` prefix rule, smoke pattern | — | both apps | Move the hard-won CLAUDE.md deployment section to `docs/guides/cloudflare-pages.md` |
| `docs/` system + `docs/AGENTS.md` | — | both apps, all agents | §5 |

Rule for adding a row: name the second consumer. If it is "future", it is not a row
(`engineering-workflow.md:83-84`).

Type generation: `json-schema-to-typescript` in `packages/contracts` `generate` lane; apps import
`@platform/contracts`. Generated files are committed, never edited; CI regenerates and diffs.

---

## 4. What stays per-app, and why

| Concern | archive | event | Why not unify |
|---|---|---|---|
| Map engine | OpenLayers (Allmaps warping needs `@allmaps/openlayers`; MapLibre removed Aug 2026) | MapLibre (3D massing, shipped PMTiles, offline) | Different jobs. HACW's map is ~2 files; duplication is cheaper than an abstraction over two engines |
| Data store | Supabase (auth, RLS, RPCs, jobs) | JSON + localStorage + D1 counters | Offline-first, no-auth is the event product |
| Auth | Supabase session, roles | staff code + CF Access | Same |
| Design tokens | archive palette, one theme | event palette per festival | Different brands by design |
| Svelte syntax | legacy (`$:`, `export let`) | runes | Both are Svelte 5; they coexist per file. Archive migrates on its own schedule, not for the merge |
| Pipelines | `work/` Python | none | — |

Reopen any row when a second consumer appears (e.g. an archive "field mode" that wants HACW's
precached-PMTiles offline trick → `packages/basemap` grows an `offline` helper; still not a map
package).

---

## 5. Docs and decisions

- **Three layers** (`.agents/AGENTS.md:105-113`): root `docs/*.md` = curated must-read
  (architecture, operating model, this file, ROADMAP); `docs/guides/` = how-to (Cloudflare Pages,
  local Supabase, worker, pmtiles); `docs/journals/YYMMDD-slug.md` = what shipped / decisions /
  loose end / lesson. New docs default to guides or journals.
- **`docs/decisions.md`**: register `| # | Decision | Status | Overturned by |`, retraction table, kill conditions. Seeded from decisions already made but scattered: OL over MapLibre, no PostGIS yet (B8), `word_similarity` over trigram index (065), `security definer` + `p_public_only`, stories publish = submit for review, legacy syntax.
- **ADR** only for a boundary move (new app, new store, engine change): Status / Date / Context /
  Decision / Rationale / What must NOT be split / Alternatives / Consequences
  (`adr-multi-cloud-split.md:1-6`).
- **Every design doc**: Status/Owner/Baseline header with the commit verified against; "for the
  hurried reader" paragraph; changelog in an appendix so the body reads present-tense.
- **`docs/AGENTS.md`** canonical (layering rule, contract-first rule, MR limits,
  no-runes-in-archive, docs placement); `CLAUDE.md` shrinks to an adapter + repo facts. Today's
  300-line CLAUDE.md is content, not an index — the split happens when HACW's CLAUDE.md lands beside
  it and the duplication is visible, not before.

---

## 6. Sequencing — each step ≤ 15 files, product work never waits on structure

| Step | Does | Second consumer proving it | Not before |
|---|---|---|---|
| 0 | E1 → E2 → E3 ship as planned in the archive | — | — |
| 1 | `packages/basemap`: one `pmtiles_extract.sh`, flavor overrides; archive `basemapStyle.ts` and HACW `map-style.js` both point at it | archive + event | now |
| 1.5 | **The engine** (§0): PostGIS, `geom`/`geom_src`/`geom_rmse` on labels and footprints, warp-on-write in the three server writers, one `warp` job kind, `context_at` + `map_context` RPCs. Re-scopes B8 | archive `/explore` + E3 + thesis | E2's seg runner (so footprints exist to index) |
| 2 | `packages/contracts` leading with `context.schema.json`, then `label-hit`, `legend-point`, `footprint-feature`; archive API validates its own output against them in the write smoke | archive API + thesis notebook (E2) | step 1.5 |
| 3 | `story.schema.json`; archive `/explore?mode=story` exports it; HACW `/tours` reads it | archive + event | step 2 |
| 4 | `git subtree add` HACW → `apps/event`; pnpm workspace; root lanes; CF Pages root dir per app | — | step 3 (so the import carries a real shared dependency, not a hope) |
| 5 | Archive moves root → `apps/archive`; CF Pages root dir change; repo rename | — | step 4, one PR, nothing else in it |
| 6 | Docs three-layer split; `docs/AGENTS.md`; CLAUDE.md → adapter; `decisions.md` seeded | both apps' docs | step 4 |
| 7 | Random audit core (5 % blind re-review) in `/scan?mode=shapes&tab=validate`; QA enums in API | E2 HITL volume | when a second reviewer exists |

**Non-goals, with reopen conditions**
- Shared UI package — reopen when a third app needs `LocationSearch`/`MapCard`-class components.
- One map engine — reopen if `@allmaps/maplibre` reaches parity and the archive wants 3D or offline.
- Runes migration of the archive — reopen when a runes-only dependency or a measured DX cost forces
  it.
- PostGIS / vector tiles for footprints (B8) — reopen when /explore wants city-wide fabric layers.
- Tasco code reuse — never; practices only. Its repo is the employer's.

## 7. Kill conditions for this design

| If | Then |
|---|---|
| Step 3 finds HACW tours need fields the archive story model should not carry (GPS radius, quiz, points) | `story.schema.json` becomes a *base* the event extends; if the extension is bigger than the base, drop the shared contract and keep the monorepo for basemap + deploy only |
| Two apps in one workspace slow `check`/`build` past what one did | Per-app lanes only; root lane runs on changed paths (`ci-cd-flow.md:195` — err toward more) |
| No second event ships within a year of step 4 | `apps/event` is a one-off; archive it under `_archive/` and stop paying workspace cost |
| `context_at` returns rows whose `geom_rmse` makes them unusable at any radius a user would ask for, on most maps | The engine is a per-map tool, not a city-wide one: keep `map_context`, drop `context_at` from the public surface, and say so |
| Warp-on-write turns out to need the annotation more often than the three writers hold it | Move the warp wholly into the `warp` job (write null, backfill async) rather than duplicating transformer fetches |
