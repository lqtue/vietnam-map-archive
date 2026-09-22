# 4D City Model — Architecture & Roadmap
_Saigon / Ho Chi Minh City · Historical Urban Reconstruction_
_Drafted: 2026-03-10_

---

## Project Identity

**Vietnam Map Archive (VMA)** — publicly launched, featured in Saigoneer (Jan 2026).
- Founded by Tuệ (data journalist, VnExpress / Fulbright MPP)
- ~10 volunteers across maps, research, tech, and operations (~10 hrs/week each)
- Currently: ~20 historical maps (1791–present), sourced from BnF Gallica, David Rumsey, Historic
  Vietnam
- Tech stack: IIIF, Internet Archive (3-location redundancy), SvelteKit, Supabase, Allmaps
- Stated long-term vision: _"3D immersive reconstruction allowing virtual time travel"_

**Primary focus period: 1880–1930** (French colonial Saigon — when the city was physically remade
from a river port into a modern metropolis). This is the best-documented period with the richest map
and archival sources.

**Approach: HITL (Human-in-the-Loop)** — community contributors create training data that improves
AI models that accelerate future contributions. Free, open source, community-owned. Sustainable
through grants + hosted AI API + institutional membership. See `docs/startup-strategy.md` for full
economic model.

---

## Vision

A web-native platform that reconstructs Saigon's urban fabric across time — **primary focus
1880–1930** (the French colonial transformation) — through:

1. **Geotemporal Knowledge Graph (KG)** — the data spine: buildings, streets, people, events and
   their relationships, each stamped with temporal validity
2. **Crowdsourced footprints** — community vectorization of building outlines from georeferenced
   historical maps (Cartographer tier; OSM community as natural partner for tracing volunteers)
3. **Automated 3D city model** — Morlighem pipeline (histo3d, CC-BY, TU Delft 2021) adapted to VMA's
   IIIF georef output → LoD2 CityJSON for all buildings. See `docs/pipeline-3d.md`.
4. **Photo + photogrammetry pipeline** — archival EFEO/BnF/Manhhai photos → SfM meshes
   (COLMAP/Meshroom) → LoD3+ hero models for ~30 landmark buildings
5. **Research library** — books, articles, archive documents cited against specific entities
6. **4D viewer** — timeline scrubber through the city's spatial evolution, from 2D footprints to 3D
   reconstruction
7. **Community model (OSM + Wikipedia)** — OSM-style tracing (Cartographer), Wikipedia-style
   per-building discussion pages (Phase 2+), building adoption for 3D (Architect), citation-based
   knowledge editing (Historian). See `docs/gamification.md`. Photo Hunter (photo tagging workflow)
   is deprioritized until the building dataset is published — photos are contributed via building
   pages in Phase 2.

---

## Community Model

VMA is built on the same principles as OpenStreetMap and Wikipedia — the two most successful
community knowledge projects in the world. This is a deliberate architectural choice, not a
metaphor.

### From OpenStreetMap
- **Anyone can trace.** No credential, no gatekeeping. The barrier is a browser.
- **Every edit is attributed and versioned.** Nothing disappears; disputes are traceable.
- **Community validation replaces central authority.** Agree / flag / correct. Trust accumulates
  through track record.
- **Machine-assisted tools scale the community.** OSM's RapiD (AI-assisted road tracing) lets a
  small community cover enormous area. VMA's AI building detector plays the same role — it proposes,
  the community validates.
- **Open license (ODbL) creates a self-reinforcing commons.** Researchers use the data → publish
  results → attract more contributors.

### From Wikipedia
- **Every subject gets a page.** Every building in the archive gets: geometry, history, sources,
  photos, discussion.
- **Anyone can add a fact — with a citation.** Citations resolve disputes. No argument from
  authority.
- **A talk/discussion page alongside every article.** The community debates, corrects, and
  cross-references. The discussion itself is a historical record.
- **Edit history is the audit trail.** Who added what, when, with what source.

### VMA's Application

| Phase | Community model |
|---|---|
| Phase 1 (dataset) | OSM-style tracing: Cartographer tier traces building footprints; AI assists; community validates |
| Phase 2 (knowledge) | Wikipedia-style building pages: each building has an editable page with history, photos, discussion |
| Phase 3 (3D) | Building adoption: Architect tier produces 3D meshes; community validates; visual reveal |

**Decentralized by design:** No single organisation controls what is true. Citations resolve
disputes. The dataset is openly licensed (ODbL) and self-hostable. Any city with a map archive and a
community can fork VMA and run the same pipeline without asking permission.

**Photo contribution model:** Photos are not a separate upload workflow (which requires its own
moderation and storage infrastructure). In Phase 2, photos are attached to building pages — the same
model Wikipedia uses for images. This defers the storage/moderation problem until the dataset that
gives photos context actually exists.

---

## System Architecture

```
L1 — HISTORICAL MAP LAYER
  BnF Gallica / EFEO / David Rumsey / Private archives
  IIIF + Internet Archive (3-location redundancy)
        |
        | georef pipeline (datum correction + GCP propagation)
        | + vectorization (roads, plots, building outlines)
        v
COMMUNITY LAYER  [OSM model for geometry; Wikipedia model for knowledge]
  Cartographer  -- trace building footprints on georef maps    [feeds L1 vectorization]
    (OSM community: natural partner — same skills, open data values)
  Architect     -- adopt a building, run SfM, submit 3D mesh   [feeds L4]
  Historian     -- add KG entities, citations, discussion      [feeds L5-L6]
  Photo Hunter  -- DEPRIORITIZED; photos contributed via building pages in Phase 2

  Phase 1: Cartographer tracing → open dataset published
  Phase 2: Wikipedia discussion layer unlocks (per-building pages, editable,
           photo attachments, discussion threads, versioned edits)
  Phase 3: Architect tier opens with Morlighem pipeline + photogrammetry missions

  Leaderboards | District completion map | Photogrammetry missions
        |
        +------------------+------------------+
        | validated        | archival photos  |
        | geometry (L1)    | (EFEO/Manhhai)   |
        v                  v                  v
L2 LoD1 MASS MODEL    L5 KNOWLEDGE GRAPH   L4 LoD3 MESH
+ L3 LoD2 ROOFSCAPE   (POI & economic      (landmark buildings)
                       activity)
Morlighem pipeline    Entities             COLMAP / Meshroom
OBIA segmentation     Relations            -> hero meshes
Height from panoramas Temporal validity    -> textured GLB
-> LoD1/LoD2 CityJSON Sources
  calibrated against  Links to L1 geometry
  1881 engraving (B&W) + 1882 map
  1901 lithograph (color) + 1898 map
        |                  |                  |
        +------------------+------------------+
                    3D Mesh Archive (Supabase Storage / R2)
                    Research Library (books, archive docs)
                    L6 — Human interaction (KG-backed)
                           |
                           v
PRESENTATION LAYER

  /kg              -- Entity explorer + graph browser
  /timeline        -- 4D timeline scrubber (2D -> 3D)
  /sources         -- Research library
  /contribute      -- Gamified hub: tier selector + active missions
  /leaderboard     -- Global + district + team leaderboards
  /missions/[id]   -- Mission detail + progress + contributors
  /profile/[id]    -- Public contributor profile + badge showcase
  /adopt/[id]      -- Building adoption flow
  /view            -- Map viewer (KG-aware, temporal filter)
  /story           -- Narrative layer (KG-linked)
```

---

## Knowledge Graph: Data Model

### Entities — `kg_entities`

The atomic unit. Everything with a location and a lifetime is an entity.

```sql
CREATE TABLE kg_entities (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type            TEXT NOT NULL CHECK (type IN (
                    'building', 'street', 'district', 'quarter',
                    'infrastructure', 'green_space',   -- spatial
                    'person', 'organization',           -- social
                    'event', 'period',                  -- temporal
                    'document', 'photo', 'map'          -- documentary
                  )),

  -- Multilingual names
  name_vi         TEXT,     -- Vietnamese
  name_fr         TEXT,     -- French colonial
  name_en         TEXT,     -- English (often military)
  name_other      JSONB,    -- { "zh": "...", "km": "..." }
  preferred_name  TEXT,     -- display name (computed or manual)

  -- Spatial (WGS84 GeoJSON)
  geometry        JSONB,    -- Point | LineString | Polygon | MultiPolygon
  bbox            JSONB,    -- [minLon, minLat, maxLon, maxLat]

  -- Temporal validity
  valid_from      TEXT,     -- ISO 8601 partial: '1878', '1905-03', '1921-06-15'
  valid_to        TEXT,     -- null = still exists / destroyed unknown
  valid_certainty TEXT NOT NULL DEFAULT 'approximate'
                  CHECK (valid_certainty IN ('certain', 'approximate', 'disputed', 'unknown')),

  -- Provenance
  external_ids    JSONB,    -- { "wikidata": "Q...", "osmid": 123, "anom_ref": "..." }
  properties      JSONB,    -- type-specific: { "floors": 3, "style": "colonial" }
  confidence      REAL NOT NULL DEFAULT 0.5,

  -- Workflow
  status          TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'review', 'published', 'deprecated')),
  created_by      UUID REFERENCES auth.users(id),
  verified_by     UUID REFERENCES auth.users(id),
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### Relations — `kg_relations`

Subject → predicate → object, each with temporal validity and source citations.

```sql
CREATE TABLE kg_relations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id  UUID NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
  predicate   TEXT NOT NULL,  -- see Predicate Vocabulary below
  object_id   UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
  object_text TEXT,           -- free text if object is not a KG entity
  valid_from  TEXT,
  valid_to    TEXT,
  confidence  REAL DEFAULT 0.8,
  notes       TEXT,
  created_by  UUID REFERENCES auth.users(id),
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE kg_relation_sources (
  relation_id UUID REFERENCES kg_relations(id) ON DELETE CASCADE,
  source_id   UUID REFERENCES kg_sources(id) ON DELETE CASCADE,
  page_ref    TEXT,
  quote       TEXT,
  PRIMARY KEY (relation_id, source_id)
);
```

### Predicate Vocabulary (controlled)

| Category | Predicates |
|----------|-----------|
| Spatial | `locatedIn`, `partOf`, `contains`, `adjacentTo`, `facesStreet` |
| Construction | `builtIn`, `demolishedIn`, `renovatedIn`, `renamedIn`, `expandedIn` |
| Ownership | `ownedBy`, `usedBy`, `administeredBy`, `designedBy`, `builtBy` |
| Social | `residedAt`, `workedAt`, `bornIn`, `diedAt`, `foundedBy` |
| Documentary | `mentionedIn`, `depictedIn`, `describedIn`, `photographedIn` |
| Functional | `functionedAs`, `convertedTo`, `demolishedFor` |

### Sources — `kg_sources`

Single table for all evidence types: maps, photos, books, archive documents.

```sql
CREATE TABLE kg_sources (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type          TEXT NOT NULL CHECK (type IN (
                  'historical_map', 'photo', 'postcard', 'aerial_photo',
                  'book', 'journal_article', 'thesis',
                  'archive_doc', 'cadastral_record',
                  'oral_history', 'newspaper'
                )),

  -- Bibliographic
  title         TEXT NOT NULL,
  author        TEXT,
  year          INT,
  publisher     TEXT,
  collection    TEXT,    -- e.g. "ANOM", "BnF Gallica", "NAVC II"
  call_number   TEXT,
  doi           TEXT,
  url           TEXT,

  -- File
  storage_path  TEXT,    -- Supabase storage path
  thumbnail_path TEXT,
  mime_type     TEXT,
  file_size_kb  INT,

  -- Geospatial (for maps)
  map_id        UUID REFERENCES maps(id) ON DELETE SET NULL,
  bounds        JSONB,   -- [minLon, minLat, maxLon, maxLat]

  -- For photos: shooting location
  photo_lat     DOUBLE PRECISION,
  photo_lon     DOUBLE PRECISION,
  photo_date    TEXT,
  photographer  TEXT,
  rights        TEXT,    -- e.g. "Public domain", "CC BY 4.0"

  -- Use for photogrammetry?
  use_for_photogrammetry BOOLEAN DEFAULT FALSE,

  metadata      JSONB,
  created_by    UUID REFERENCES auth.users(id),
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Junction: entity ↔ source citations
CREATE TABLE kg_entity_sources (
  entity_id   UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
  source_id   UUID REFERENCES kg_sources(id) ON DELETE CASCADE,
  page_ref    TEXT,
  quote       TEXT,
  notes       TEXT,
  PRIMARY KEY (entity_id, source_id)
);
```

### Footprints — `footprint_tasks` + `footprint_submissions`

Crowdsourcing vectorization from georeferenced historical maps.

```sql
CREATE TABLE footprint_tasks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  map_id          UUID REFERENCES maps(id) ON DELETE CASCADE,
  -- Tile region to display (in map pixel coords)
  region          JSONB NOT NULL,  -- { x, y, width, height }
  time_period     TEXT,            -- e.g. '1900', '1920s'
  entity_type_hint TEXT,           -- 'building', 'street', etc.
  status          TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'in_progress', 'consensus', 'verified')),
  min_submissions INT DEFAULT 3,   -- for consensus
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE footprint_submissions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id     UUID NOT NULL REFERENCES footprint_tasks(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  -- GeoJSON polygon in WGS84 (after georef transform from pixel coords)
  geometry    JSONB NOT NULL,
  entity_type TEXT,
  label       TEXT,
  notes       TEXT,
  confidence  REAL DEFAULT 0.5,
  status      TEXT NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending', 'accepted', 'rejected', 'merged')),
  -- Set when merged into KG
  entity_id   UUID REFERENCES kg_entities(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

### Photogrammetry — `photogrammetry_sessions`

```sql
CREATE TABLE photogrammetry_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id       UUID NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','processing','done','failed')),
  photo_count     INT DEFAULT 0,
  -- Output files in Supabase Storage
  mesh_url        TEXT,
  point_cloud_url TEXT,
  texture_url     TEXT,
  -- Bounding box of reconstruction
  bbox_3d         JSONB,   -- { minX, minY, minZ, maxX, maxY, maxZ }
  processor       TEXT DEFAULT 'colmap',  -- 'colmap', 'openmvg', 'metashape', 'external'
  metadata        JSONB,
  processed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## New Routes

### User-facing

| Route | Purpose |
|-------|---------|
| `/kg` | Entity explorer — search, filter by type/period, map view of entities |
| `/kg/[id]` | Entity detail — name, geometry, timeline, relations, photos, sources |
| `/kg/[id]/edit` | Edit entity (auth required) |
| `/timeline` | 4D timeline scrubber — move through time periods, see footprint layers evolve |
| `/sources` | Research library — search bibliography, browse by type/collection |
| `/sources/[id]` | Source detail — view photo/doc, linked entities |
| `/contribute/footprint` | Footprint vectorization — extends LabelCanvas with polygon drawing |
| `/contribute/photo` | Photo contribution — upload + attribution + link to entity |
| `/contribute` | Gamified contribution hub — tier selector, active missions, points dashboard |
| `/leaderboard` | Global + district + team leaderboards |
| `/missions` | Active and upcoming photogrammetry/collection missions |
| `/missions/[id]` | Mission detail — progress, contributor list, photo coverage |
| `/profile/[id]` | Public contributor profile — badge showcase, contribution history |
| `/adopt/[building_id]` | Building adoption flow (Architect tier) |

### Admin

| Route | Purpose |
|-------|---------|
| `/admin/kg` | KG admin — batch operations, review queue, stats |
| `/admin/sources` | Source management — upload maps/photos, bulk import bibliography |
| `/admin/footprint` | Footprint task creation + review + merge to KG |
| `/admin/photogrammetry` | Photogrammetry session management |

### API

| Endpoint | Purpose |
|----------|---------|
| `GET/POST /api/kg/entities` | List / create entities |
| `GET/PATCH/DELETE /api/kg/entities/[id]` | Single entity |
| `GET/POST /api/kg/entities/[id]/relations` | Entity relations |
| `GET/POST /api/kg/entities/[id]/sources` | Entity source citations |
| `GET /api/kg/entities/[id]/timeline` | Temporal state of entity at each period |
| `GET /api/kg/graph` | Graph query (BFS from entity) |
| `GET/POST /api/kg/sources` | Source library |
| `GET/POST /api/footprint/tasks` | Footprint tasks |
| `POST /api/footprint/tasks/[id]/submit` | Submit polygon |
| `POST /api/footprint/tasks/[id]/merge` | Admin: merge submissions → KG entity |
| `GET/POST /api/photogrammetry/sessions` | Photogrammetry sessions |
| `POST /api/photogrammetry/sessions/[id]/upload` | Upload photos to session |
| `POST /api/contributions` | Log contribution + award points |
| `GET /api/leaderboard` | Leaderboard queries (global, district, team) |
| `POST /api/missions/[id]/contribute` | Add contribution to mission |

---

## New `src/lib/` Structure

```
src/lib/
├── kg/
│   ├── types.ts           — KgEntity, KgRelation, KgSource, predicates
│   ├── kgApi.ts           — CRUD wrappers for kg_* tables
│   ├── kgStore.ts         — Svelte store: current entity, graph state
│   ├── EntityCard.svelte  — Entity summary card (used in list + map popup)
│   ├── EntityDetail.svelte — Full entity page
│   ├── RelationGraph.svelte — D3/force graph of entity relations
│   ├── EntitySearch.svelte — Typeahead + filter
│   └── predicates.ts      — Predicate vocabulary + display labels
│
├── sources/
│   ├── types.ts
│   ├── sourcesApi.ts
│   ├── SourceCard.svelte
│   ├── SourceUpload.svelte   — Drag-drop upload + metadata form
│   ├── Bibliography.svelte   — Citation list with anchor links
│   └── PhotoViewer.svelte    — Lightbox with metadata
│
├── footprint/
│   ├── types.ts
│   ├── footprintApi.ts
│   ├── FootprintCanvas.svelte  — LabelCanvas extended: polygon draw mode
│   ├── FootprintTask.svelte    — Task UI (wraps FootprintCanvas)
│   ├── FootprintReview.svelte  — Admin: side-by-side submissions + merge
│   └── PolygonDraw.ts          — OL Draw interaction helper (reuses annotate pattern)
│
├── timeline/
│   ├── types.ts            — TimePeriod, TemporalSlice
│   ├── TimelineScrubber.svelte  — Horizontal timeline UI
│   ├── PeriodSelector.svelte    — Named period chips (colonial, wartime, etc.)
│   ├── temporalQuery.ts    — Filter kg_entities by valid_from/valid_to
│   └── periods.ts          — Named time periods for Saigon history
│
├── photogrammetry/
│   ├── types.ts
│   ├── photogrammetryApi.ts
│   ├── PhotoUploader.svelte   — Multi-photo upload for a session
│   ├── MeshViewer.svelte      — Three.js / model-viewer for 3D mesh
│   └── SessionStatus.svelte   — Processing status display
│
├── gamification/
│   ├── types.ts              — Contribution, Achievement, Mission, Team types
│   ├── gamificationApi.ts    — Supabase CRUD for contributions, achievements, missions
│   ├── ContributeHub.svelte  — Tier selector + mission browser + points dashboard
│   ├── Leaderboard.svelte    — Global / district / team leaderboard tabs
│   ├── MissionCard.svelte    — Mission progress card (photo coverage, status)
│   ├── BadgeGrid.svelte      — Badge showcase for profile page
│   ├── PointsLog.svelte      — Recent points history
│   └── TierProgress.svelte   — Tier unlock progress bar
│
└── i18n/
    ├── index.ts           — Language store + t() helper
    ├── vi.json            — Vietnamese strings
    ├── fr.json            — French strings
    └── en.json            — English strings
```

---

## Integrations with Existing Systems

### LabelStudio → FootprintCanvas
The existing `LabelCanvas.svelte` does **point placement** in pixel coordinates.
`FootprintCanvas.svelte` extends it with:
- OL `Draw` interaction for `Polygon` type (pattern already exists in `AnnotateMode`)
- On submit: transform pixel coords → WGS84 via Allmaps `pixelToGeo` (from the warped map transform)
- Store as GeoJSON in `footprint_submissions.geometry`

### Pipeline → KG ingestion
After Stage 4 (annotate) + Stage 5 (propagate), auto-create KG entities:
- Each `pipeline_sheet` → `kg_entity` of type `map`
- Sheet bounds → polygon geometry
- `valid_from` = map publication date

### Story System → KG narratives
- `StoryPoint.overlayMapId` → link to `kg_entity` (map)
- `StoryPoint.coordinates` → spatial anchor on KG entity
- New `StoryPoint.entityId` field → link directly to a KG building/place

### mapStore + layerStore → Temporal queries
- Add `timeline.activePeriod: TimePeriod` to `layerStore`
- `HistoricalOverlay` reacts: filter visible maps by `valid_from/valid_to`
- KG entity layer reacts: show only entities valid in the active period

### Gamification → KG attribution
- Every `contributions` row references `entity_id` — the KG entity that contribution affected
- When a `footprint_submission` is merged → KG entity, a `contributions` row with type
  `footprint_trace` is created
- Attribution is permanent: KG entity pages show who traced, photographed, and modelled each
  building
- Quality weighting: contributors with high validation scores get higher confidence weight in
  consensus

---

## 3D Pipeline: Morlighem Adaptation

Full technical detail: `docs/pipeline-3d.md`

**Summary:** VMA adapts the Morlighem (2021) pipeline (*histo3d*, TU Delft MSc, CC-BY) — proven on
Belgian/Dutch historical maps, open-source at `github.com/CamilleMorlighem/histo3d`. VMA's automated
georeferencing is the exact prerequisite the Morlighem pipeline required but left manual. The two
projects are a clean complement.

**Two-tier 3D output:**

| Tier | Method | Output | Coverage |
|------|--------|--------|----------|
| LoD2 (automated) | Morlighem pipeline: OBIA → vectorise → procedural model → height inference | CityJSON — all buildings | Full 1880–1930 city |
| LoD3+ (hand-crafted) | Blender artists + architecture historians; SfM for facade texture | GLB/GLTF hero models | ~30 landmark buildings |

**Height inference (no LiDAR):** Probabilistic roof type table (hipped / gabled / flat) × building
typology × colonial construction standards → height estimate with uncertainty score. Calibrated by
two contemporaneous painting-map pairs:
- **1881 B&W engraving + 1882 cadastral map** — full oblique city view; height classes + roof
  massing
- **1901 colored lithograph + 1898 cadastral map** — full-color oblique view; additionally confirms
  terracotta roof tile dominant across residential/commercial stock at city scale, providing
  independent validation of the NYPL color classifier's semantic accuracy

The two paintings together also provide visual ground-truth for the temporal change classification:
blocks that appear stable in both paintings cross-validate the automated "stable" label from the
`match` command. Results cited as approximate; see `docs/pipeline-3d.md` §Stage 5 for full
methodology.

**Photogrammetry (L3 facade mesh):**
- Source photos: EFEO (largest French Indochina collection), BnF Gallica postcards, Manhhai
  collection, family archives
- Saigon postcard industry 1900–1930 provides natural multi-angle coverage
- SfM pipeline: COLMAP (open-source) or Meshroom → point cloud → textured mesh → GLB export
- Locked to KG entity via `photogrammetry_sessions.entity_id`

**Volunteer team roles:**

| Role | Tool | Output |
|------|------|--------|
| GRASS GIS specialists | GRASS GIS | OBIA colour calibration for colonial Saigon cartographic symbology |
| Blender artists | Blender (BCGA workflow) | LoD3+ landmark building meshes |
| Architecture historians | KG + spreadsheet | Probabilistic roof type table + building typology classification |
| CityJSON validators | cjio | Valid, clean 3D dataset |

**Academic partnerships:**

**TU Delft 3D Geoinformation Group** (Hugo Ledoux + Anna Labetski — both supervised Morlighem;
Francesca Noardo co-reader) is the natural collaborator for the 3D pipeline. VMA brings colonial
Vietnamese maps; TU Delft brings the pipeline expertise.

**ETH Zürich IKG (Institute of Cartography and Geoinformation)** — Prof. Dr. Lorenz Hurni's group
(advisors: Dr. Sidi Wu, Dr. Yizi Chen) is a second key cluster. Three recent theses from this group
are directly relevant:
- Bauckhage 2025 ("EvolutionMap") — temporal 4D **visualization** of landscape from historical map
  stacks; relevant to VMA's `/timeline` scrubber and animated transitions (not building
  reconstruction)
- Gao 2024 — diffusion model synthetic map generation for training change detection models; relevant
  to VMA's future ML training data pipeline on colonial map styles
- Liu 2025 — KG + LLM geospatial Q&A using SPARQL; relevant if VMA adds a natural language query
  interface to the KG

Note: Liu's approach requires a formal RDF/SPARQL ontology. VMA's current PostgreSQL/JSONB KG cannot
support this without a separate RDF layer or SPARQL endpoint. The "CIDOC-CRM is too complex" design
decision needs a stronger scholarly justification given this gap.

---

## Named Time Periods (Saigon)

```typescript
export const SAIGON_PERIODS = [
  { id: 'pre-colonial',   label: 'Pre-colonial',     from: null,   to: '1859'  },
  { id: 'early-colonial', label: 'Early French',      from: '1859', to: '1885'  },
  { id: 'colonial-peak',  label: 'Colonial Peak',     from: '1885', to: '1920'  },
  { id: 'interwar',       label: 'Interwar',          from: '1920', to: '1940'  },
  { id: 'ww2',            label: 'WWII / Japanese',   from: '1940', to: '1945'  },
  { id: 'first-indochina',label: 'First Indochina War',from:'1945', to: '1954'  },
  { id: 'republic',       label: 'Republic of Vietnam',from:'1955', to: '1968'  },
  { id: 'tet-offensive',  label: 'Tet & Late War',    from: '1968', to: '1975'  },
  { id: 'reunification',  label: 'Reunification',     from: '1975', to: null    },
];
```

---

## Database Migrations Plan

| # | Migration | New tables |
|---|-----------|-----------|
| 016 | `kg_core` | `kg_entities`, `kg_relations`, `kg_relation_sources` |
| 017 | `kg_sources` | `kg_sources`, `kg_entity_sources` |
| 018 | `footprints` | `footprint_tasks`, `footprint_submissions` |
| 019 | `photogrammetry` | `photogrammetry_sessions` |
| 020 | `gamification` | `contributions`, `achievements`, `building_adoptions`, `missions`, `teams`, `team_members` |
| 021 | `gamification_rls` + `kg_rls` | RLS policies for gamification + all KG tables |

See `docs/gamification.md` for the full SQL schema of the gamification tables.

---

## Phased Roadmap

### Phase 1 — KG Foundation (weeks 1–3)
**Goal**: Entity and source CRUD is live. First buildings can be entered.

- [ ] Write migrations 016–017 (kg_entities, kg_relations, kg_sources, junctions)
- [ ] `src/lib/kg/types.ts` — TypeScript types for all KG tables
- [ ] `src/lib/kg/kgApi.ts` — Supabase CRUD wrappers
- [ ] `/kg` route — entity list + map view (entities as OL vector layer)
- [ ] `/kg/[id]` route — entity detail (geometry, timeline bar, relations list, source list)
- [ ] `/admin/kg` — entity create/edit form + source attach
- [ ] `src/lib/sources/SourceUpload.svelte` — upload photo/doc to Supabase Storage
- [ ] API routes: `/api/kg/entities`, `/api/kg/sources`

**First dataset target**: 20–30 key Saigon landmarks manually entered (Cathedral, City Hall, Opera
House, Majestic Hotel, Ben Thanh Market, key streets)

---

### Phase 2 — Footprint Crowdsourcing (weeks 4–6)
**Goal**: Community can draw building footprints on georeferenced Saigon maps.

- [ ] Migration 018 (`footprint_tasks`, `footprint_submissions`)
- [ ] `src/lib/footprint/FootprintCanvas.svelte` — OL polygon draw on IIIF georef map
- [ ] `src/lib/footprint/PolygonDraw.ts` — pixel → WGS84 transform via Allmaps
- [ ] `/contribute/footprint` route — task queue + canvas UI
- [ ] `/admin/footprint` — task creation from any georef map region, submission review
- [ ] API routes: `/api/footprint/tasks`, `/api/footprint/tasks/[id]/submit`,
      `/api/footprint/tasks/[id]/merge`
- [ ] Ingest Saigon colonial maps: target BnF Gallica / ANOM plans (1880–1930)

**First dataset target**: 200+ building footprints from 1900–1920 Saigon cadastral maps

---

### Phase 3 — Photo + Research Library (weeks 7–9)
**Goal**: Sources are browsable and citeable. Photos link to entities.

- [ ] `/sources` route — searchable bibliography grid
- [ ] `/sources/[id]` — photo viewer / document viewer
- [ ] `/contribute/photo` — upload + metadata form + link to entity
- [ ] `src/lib/sources/Bibliography.svelte` — citation list component (used in `/kg/[id]`)
- [ ] `src/lib/sources/PhotoViewer.svelte` — lightbox with metadata + entity links
- [ ] Admin: bulk import bibliography from Zotero export (CSL JSON)
- [ ] API: `/api/kg/sources`, `/api/kg/entities/[id]/sources`

**First dataset target**: 50 key archival photos (BnF Gallica postcards, EFEO collection); 30
bibliographic entries (key DH/HGIS works on colonial Saigon)

---

### Phase 4 — 4D Timeline (weeks 10–12)
**Goal**: The map viewer has a temporal dimension. Moving the scrubber changes what you see.

- [ ] `src/lib/timeline/periods.ts` — `SAIGON_PERIODS` constants
- [ ] `src/lib/timeline/TimelineScrubber.svelte` — horizontal scrubber component
- [ ] Add `activePeriod` to `layerStore`
- [ ] `HistoricalOverlay` — filter maps by period
- [ ] KG entity OL vector layer — filter by `valid_from/valid_to`
- [ ] Footprint layer — show polygon evolution over time
- [ ] `/timeline` route — full-screen 4D view
- [ ] `temporalQuery.ts` — utility for ISO 8601 partial date comparison

---

### Phase 5 — Photogrammetry (weeks 13–16)
**Goal**: 3D meshes can be attached to KG entities and viewed in browser.

- [ ] Migration 019 (`photogrammetry_sessions`)
- [ ] `/contribute/photo` enhanced — group photos into photogrammetry session
- [ ] `src/lib/photogrammetry/PhotoUploader.svelte`
- [ ] `src/lib/photogrammetry/MeshViewer.svelte` — `<model-viewer>` web component for GLB/GLTF
- [ ] Admin: trigger external processing (COLMAP via cloud function or manual)
- [ ] `/kg/[id]` — show 3D mesh tab when session is `done`
- [ ] `/timeline` — 3D city view mode (WebGL, Three.js scene with period-appropriate meshes)

---

### Phase 6 — KG Enrichment + Export (weeks 17–20)
**Goal**: The KG is rich enough to be citable and reusable.

- [ ] Wikidata reconciliation — match KG entities to Wikidata items, store `external_ids.wikidata`
- [ ] JSON-LD export endpoint (`/api/kg/entities/[id].jsonld`) — W3C compatible
- [ ] GeoJSON export (`/api/kg/export.geojson?period=1900&type=building`)
- [ ] IIIF Manifest generation for photo collections per entity
- [ ] NLP entity extraction from uploaded texts (link mentions in books to KG entities)
- [ ] Public API docs page

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| KG storage | Supabase (PostgreSQL) | Already in use; PostGIS-compatible JSONB for geometry; no graph DB needed at this scale |
| Geometry format | GeoJSON (JSONB column) | Compatible with OL, Allmaps, and standard GIS tools |
| Temporal encoding | ISO 8601 partial strings (`'1905'`, `'1905-03'`) | Human-readable, supports uncertain dates |
| 3D format | GLB/GLTF | Browser-native via `<model-viewer>`, Three.js compatible |
| Photogrammetry | COLMAP (external) or Metashape | Best open-source option; results uploaded manually first |
| i18n | Simple JSON store | 3 languages (vi, fr, en); no heavy i18n framework needed at this stage |
| KG ontology | Custom controlled vocabulary | CIDOC-CRM is too complex for volunteer editors; Dublin Core too flat; custom predicates + Wikidata IDs for interop. Trade-off: this forfeits SPARQL/RDF compatibility (see Liu 2025 for what a SPARQL-based KG enables). Phase 6 adds JSON-LD export to partially bridge this. If LLM Q&A becomes a priority, a SPARQL wrapper or separate RDF layer would be needed. |
| Footprint transform | Allmaps `pixelToGeo` | Already used in georef pipeline; gives accurate WGS84 from pixel coords |

---

## What Doesn't Change

The existing pipeline, story system, and map viewer continue working as-is.
This plan **extends** them — it doesn't replace them:

- L7014 pipeline → feeds `maps` table → maps table feeds KG source linking
- Stories → narrative layer on top of KG entities
- LabelStudio → footprint mode is a new task type, existing point tasks still work
- MapShell + HistoricalOverlay → gains a temporal filter from `layerStore.activePeriod`
