---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #fafaf7;
    color: #111;
    padding: 60px 70px;
  }
  h1 { font-weight: 800; letter-spacing: -0.02em; }
  h2 { border-bottom: 3px solid #111; padding-bottom: 8px; }
  strong { background: #fde68a; padding: 0 4px; }
  code { background: #111; color: #fafaf7; padding: 2px 6px; border-radius: 3px; }
  table { font-size: 0.75em; }
  section.lead { background: #111; color: #fafaf7; }
  section.lead h1 { font-size: 2.6em; }
  section.appendix { background: #f0ece0; }
  blockquote { border-left: 6px solid #111; padding-left: 18px; color: #444; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
  .small { font-size: 0.78em; }
---

<!-- _class: lead -->

# Vietnam Map Archive

### Research infrastructure for a spatial history of Saigon

A working platform · A PhD apparatus · An open civic archive

<br>

`maparchive.vn` · Tuệ Lê-Quang · 2026

---

## The problem

Colonial Saigon (1859–1954) is one of the **best-documented** non-European cities of its era — and one of the **least computationally accessible**.

- Thousands of sheets: Service Géographique de l'Indochine cadastres, BnF topo series, IA scans, panoramas
- Dispersed across **BnF Gallica, David Rumsey, EFEO, Internet Archive, UT Austin, VVA Texas Tech**
- Each in different IIIF dialects, metadata schemas, file formats — many not on IIIF at all
- No georeferenced corpus, no shared toponym KG, no continuous-time city model

**Today every researcher rebuilds this from scratch.**

---

## What VMA is

> A web-native research platform that turns dispersed colonial map archives into a queryable, georeferenced, crowdsourceable model of Saigon — and the apparatus for a PhD on how planning regimes encoded spatial inequality into built form.

Two readings of the same system:

<div class="cols">

**As a platform**
- Public archive at `maparchive.vn`
- Crowdsource UX for OSM, students, diaspora
- Stories, annotations, IIIF deep-zoom

**As research infrastructure**
- Automated georef pipeline (L7014 series)
- OCR → KG of toponyms / ownership
- 4D city model (L1 → L5 stack)
- Reproducible runs, versioned prompts

</div>

---

## The 6-Layer Data Stack

The city as a data stack — modern signals translated to historical sources.

| Layer | Modern world | VMA / historical | Status |
|-------|--------------|------------------|--------|
| **L1** | Satellite imagery | Georeferenced + vectorized historical maps | **~45%** — 38/100 georef, OCR + SAM2 live |
| L2 | LiDAR | LoD1 mass from 1882/1898 panoramas | designed |
| L3 | Road + facade | Road network + LoD2 roofscape | designed |
| L4 | Building meshes | LoD3 via SfM on archival photos | designed |
| **L5** | POI / economic activity | **Knowledge graph: places, owners, events** | schema drafted |
| L6 | Human interaction | Stories, annotations, oral history | stories shipped (mig. 039) |

Dependency rule: **N requires N–1**. KG is cross-cutting.
PhD scope: L1 (colonial georef + vectorization) + L5 (property ownership KG).

---

## How the pipeline works today

```
  Archive source (BnF / Rumsey / IA / SGI scans)
       │
       ▼
  [/admin/bulk]  paste paths ──► vips dzsave (IIIF v3) ──► R2 + CF Worker
       │                          iiif.maparchive.vn/iiif/<uuid>/info.json
       ▼
  [Allmaps Editor] manual GCPs  →  [Fetch from Allmaps] writes allmaps_id
       │
       ▼
  [maps + map_iiif_sources]  multi-source · is_primary · DC metadata
       │
       ▼
  [OCR pipeline]  Gemini Flash 2.0 · prompt v8 · scout + batch tiles
       │
       ▼
  [/contribute/digitalize]  3-phase HITL  →  ocr_extractions (1,028 rows)
       │   Phase 1 Triage  → neatline + tile grid
       │   Phase 2 Review  → validate text/category bboxes
       │   Phase 3 Segment → trigger MapSAM2
       ▼
  [MapSAM2]  LoRA · OCR-seeded · watershed  →  footprint_submissions
       │
       ▼
  [/contribute/review]  approve/reject polygons  →  verified
       │
       ▼
  [map_pipeline_status]  idle → ocr_queued → ocr_done → reviewed →
                         seg_queued → seg_done → seg_reviewed → exported
```

---

## Architecture: one map shell, many modes

<div class="cols">

**Core stack**
- SvelteKit 5 + OpenLayers + MapLibre
- Supabase (Postgres + RLS + Storage)
- Cloudflare Pages + Workers + R2
- Python: SAM2 / MapSAM2 (LoRA), Gemini OCR

**Allmaps integration**
- `@allmaps/openlayers` — warped overlay
- `@allmaps/maplibre` — embed
- `@allmaps/id` — canonical image hashing
- W3C Georeference Annotations end-to-end

</div>

**MapShell** owns the single OL Map; modes (view / create / annotate / contribute) attach via Svelte context.
**ImageShell** handles IIIF pixel-coordinate canvases for Label Studio + Digitalize.

---

## Crowdsourcing layer — three tiers

| Role | Task | Feeds | Target community |
|------|------|-------|------------------|
| **Cartographer** | Trace building outlines on georef maps | L1 vectorization | **OSM mappers** |
| **Architect** | Adopt a building → SfM photogrammetry → 3D mesh | L4 LoD3 | Architecture students |
| **Historian** | KG entities, citations, family histories, oral records | L5–L6 | Diaspora, journalists, families |

Volunteer-driven (~10 contributors @ ~10 hrs/wk). Mobile-friendly. Low-friction.
Status: Cartographer track active (Label Studio + Digitalize). Architect + Historian designed, not yet launched.

---

## What's working today

- **100 maps ingested**, 38 georeferenced, 37 public-facing
- **62 self-hosted maps** from **Service Géographique de l'Indochine** (bulk pipeline → R2)
- Plus **20 BnF Gallica** + **18 Internet Archive** maps mirrored
- **105 IIIF sources** across the corpus (multi-source per map supported)
- **Self-hosted IIIF** at `iiif.maparchive.vn` (R2 + Worker, on-the-fly `info.json` patching)
- **1,028 OCR extractions** from Gemini Flash 2.0 pipeline (HITL review live at `/contribute/digitalize`)
- **46 SAM2 footprint submissions** under review at `/contribute/review`
- **368 label pins** placed by volunteers (Label Studio)
- **MapSAM2 fine-tuned** (LoRA) with OCR-seeded prompting + watershed post-processing
- Editorial coverage in Saigoneer · open codebase · ~10 active volunteers

---

## What's next — funding asks

<div class="cols">

**Near term (6 mo)**
- **Auto-segmentation at scale** — MapSAM2 LoRA on full 62-sheet SGI corpus (GPU credits)
- Push from 38 → 200+ georeferenced maps
- **KG live**: lift 1,028 OCR extractions → first ~500 entities with provenance
- OSM partnership for Cartographer track

**Medium term (12–18 mo)**
- L2 mass model from panoramas (Morlighem / TU Delft method)
- L4 photogrammetry pilot (20 landmark buildings)
- Bilingual UI (VI/EN), diaspora outreach
- Academic partnership: TU Delft 3DGI, ETH IKG, GSAPP

</div>

**The technical bottleneck is no longer software — it's GPU time, storage, and a dedicated annotation lead.**

---

## Why this matters

> Saigon is a city designed three times — by colonial planners, by socialist reconstruction, by post-Đổi Mới capital — and each regime overwrote the last's spatial grammar without erasing it.

**For the field:** First open, georeferenced, vectorized corpus of French colonial Indochina maps. Methodological contribution: OBIA calibration for French colonial Indochina symbology (gap in literature).

**For the public:** A spatial memory infrastructure for a diaspora that lost access to its own urban past.

**For the PhD:** Empirical apparatus for tracing how planning inheritance shapes contemporary climate-adaptive design in HCMC.

---

<!-- _class: lead -->

# Thank you

**Tuệ Lê-Quang**
lequangtuevn@gmail.com · `maparchive.vn`

VnExpress journalist · Fulbright MPP
PhD applicant, GSAPP urban planning

---

<!-- _class: appendix -->

# Appendix A — For Bert Spaan / Allmaps

How VMA uses, extends, and depends on Allmaps.

---

<!-- _class: appendix -->

## Allmaps as VMA's georef substrate

**Libraries in production:**
- `@allmaps/openlayers` — warped tile rendering inside MapShell
- `@allmaps/maplibre` — embed-only `Map.svelte` component
- `@allmaps/id` — derive image IDs in `POST /api/admin/maps/lookup-allmaps-id`
- W3C Georeference Annotations as the canonical interchange format

**Editor workflow:**
- Admin clicks IIIF source → opens `editor.allmaps.org/?url=<info.json>`
- After placing GCPs, "Fetch from Allmaps" button probes `annotations.allmaps.org/images/<id>` and writes `allmaps_id` back
- Self-hosted R2 maps store the annotation JSON in Supabase Storage; `allmaps_id` field points to that URL

---

<!-- _class: appendix -->

## Where VMA extends Allmaps

1. **Self-hosted IIIF at scale** — `iiif.maparchive.vn` worker patches vips dzsave `info.json` on the fly (injects `tiles[0].height` and `sizes` array OL's IIIFInfo parser requires).
2. **Bulk pipeline** — `/admin/bulk` ingests file lists, auto-parses sheet numbers from filenames (`<sheet#> <Place> <YYYY>.jpg`), batch-creates `maps` rows, emits shell scripts of `tile_map.sh` calls, then backfills thumbnails. Already used to ingest **62 Service Géographique de l'Indochine cadastres**.
3. **Multi-source per map** — `map_iiif_sources` table (105 rows across 100 maps) with `is_primary` partial unique index; trigger syncs to `maps.iiif_image`. Source types: `ia | bnf | efeo | gallica | rumsey | self | r2 | other`.
4. **Allmaps ID lookup after R2 mirror** — `POST /api/admin/maps/lookup-allmaps-id` derives the canonical image hash via `@allmaps/id` from the self-hosted IIIF service URL, then probes `annotations.allmaps.org/images/<id>` to confirm a georef annotation exists.
5. **DC metadata layer** — 13 Dublin Core fields with completeness scoring + per-map progress bars in admin catalog (migration 031).

---

<!-- _class: appendix -->

## Where we'd love to collaborate

- **Annotation review API** — VMA HITL flow could feed back into Allmaps annotation server as reviewed/verified GCP sets
- **Batch georef standards** — propagation conventions for uniform military series (L7014 today; SE Asia & MENA tomorrow)
- **Footprint trace interchange** — `footprint_submissions` schema → could we standardize a W3C-style polygon annotation alongside georef?
- **Quality scoring** — exposing per-GCP residuals + map completeness in the annotation
- **IIIF self-hosting pattern** — share the info.json patching worker as a reference implementation for archives without IIIF infrastructure

---

<!-- _class: appendix -->

# Appendix B — For funders

Budget, comparables, ask.

---

<!-- _class: appendix -->

## Comparable projects

| Project | Scope | What VMA shares |
|---------|-------|-----------------|
| **SODUCO** (ANR, Paris 1789–1950) | OCR + georef + KG of Paris directories | Closest methodological peer; we extend with auto-georef propagation |
| **NYPL Building Inspector** | Crowdsource trace of 1850s Manhattan footprints | Cartographer track is direct descendant |
| **Allmaps** (Bert Spaan et al.) | W3C georef standard + viewer | VMA's substrate |
| **histo3d** (Morlighem, TU Delft) | LoD2 city from historical maps | L2 method, dependency on VMA's L1 |
| **CHGIS** (Peter Bol, Harvard) | China historical GIS | Long-term model for VMA's research arc |

---

<!-- _class: appendix -->

## Budget envelope (24-month roadmap)

| Item | Range | Why |
|------|-------|-----|
| GPU credits (auto-seg at scale) | $8–15k | MapSAM2 LoRA training + batch inference on 500+ sheets |
| R2 + Supabase storage | $3–5k | ~2 TB tiles + Postgres + annotation JSONs |
| Annotation lead (part-time) | $20–30k | Domain expert curating KG + HITL gold set |
| Volunteer infrastructure | $4–6k | Mobile UX polish, OSM integration, bilingual UI |
| Field acquisition (Vietnam) | $5–8k | Travel to Saigon archives, panorama scan rights |
| Academic partnerships | $3–5k | TU Delft / ETH co-supervision visits |
| **Total** | **$45–70k** | over 24 months |

---

<!-- _class: appendix -->

# Appendix C — General / vision

For talks, press, public outreach.

---

<!-- _class: appendix -->

## What you can do today

- **Browse** maparchive.vn — explore georeferenced colonial Saigon
- **Trace** a building on a 1898 cadastral (Cartographer)
- **Add** an entity to the knowledge graph (Historian)
- **Adopt** a landmark for photogrammetry (Architect)
- **Tell** a story — pin oral history to a place + a year

---

<!-- _class: appendix -->

## The long arc

> "A city designed three times, never erased once."

- **1859–1954** colonial planning — French cadastres, Haussmann-on-the-Saigon-River
- **1954–1975** divided modernism — Saigon plans collide with US AID grids
- **1975–1986** socialist reconstruction — collectivization, name changes, demolitions
- **1986–present** Đổi Mới capital — high-rise overlay, climate vulnerability inherited

VMA's PhD question: **how does each regime's spatial grammar survive into the next, and what does that inheritance mean for climate-adaptive planning today?**
