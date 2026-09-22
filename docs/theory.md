# VMA Theoretical Framework
_The intellectual foundation of the Vietnam Map Archive_

---

## The Core Claim

A city is not just geometry. It is geometry + time + political economy + memory.

Most digital heritage projects recover the geometry and call it done. VMA recovers all four — using
a layered data stack, a HITL pipeline, and a Public Policy interpretive lens that asks not just
*where* a building was, but *why it was built, for whom, under what regime, and what replaced it*.

---

## The 6-Layer World-as-Data-Stack

The city understood as ascending layers of spatial abstraction:

```
L6 · Human interaction      — memory, stories, oral history, community knowledge
L5 · POI / economic         — commerce, land use, named places, merchant networks
L4 · Building fabric        — footprints, block morphology, cadastral structure
L3 · Road & facade          — street networks, building facades, photogrammetry
L2 · LiDAR / 3D model       — volumetric geometry, CityJSON
L1 · Macro signal (map)     — georeferenced historical map rasters
```

**Dependency rule:** You cannot build layer N without layer N-1. This is the build sequence. Value
compounds as you ascend: L1 is a picture, L6 is a city that can be asked questions.

**This is the canonical layer scheme.** A rival L1–L6 keyed on pipeline stages (source → capture →
georeferencing → KG → interaction → civic) circulated in earlier drafts; it is retired.

**Context rule:** Political, social, and economic context is not a layer — it is a cross-cutting
dimension that reframes the meaning of data at every layer and every time period. The same building
footprint means something different under French colonial administration (1900), RVN governance
(1960), and post-reunification (1980).

---

## Lefebvre's Triad Mapped to the Stack

Henri Lefebvre's three-part theory of space (*The Production of Space*, 1974) maps across the full
stack:

| Lefebvre | Standard reading | VMA equivalent |
|---|---|---|
| Espace conçu (conceived) | Abstract, planned space — representations produced by planners, experts, technocrats | L1 + L4: historical maps, cadastral plans, georef annotations, admin boundaries — the city as designed and measured |
| Espace perçu (perceived) | Spatial practice — everyday, embodied use; habitual routes, lived movement | L3 + L5: road networks, commercial activity, land use patterns — the city as actually navigated and used |
| Espace vécu (lived) | Representational space — symbolic, imaginary, emotional; art, ritual, community memory | L6: stories, oral histories, annotations, community memory — the city as remembered and felt |

**Key clarification:** Lefebvre's espace conçu encompasses *both* L1 (the historical map as a
cartographic representation of planned space) *and* L4 (the cadastral plan as administrative
conception). The separation into geometry-first (L1–L4) vs meaning-later (L5–L6) is a VMA
operational distinction, not a Lefebvre distinction — Lefebvre would say conception and lived
experience co-produce space at every scale simultaneously.

VMA's work is to climb the full stack — from a scanned map (espace conçu crystallized on paper) to a
living community memory (espace vécu restored through crowdsourced annotation).

---

## The Progression Axis

`digitized → digitalized → digitally reconstructed`

| Stage | Layer | What exists |
|---|---|---|
| Digitized | L1 | A scan of a map exists in a system |
| Digitalized | L2–L4 | Geometry, structure, and fabric are extracted from the scan |
| Digitally reconstructed | L5–L6 | Meaning, activity, and memory are restored |

Most archives are stuck at "digitized." VMA is building the infrastructure to reach "digitally
reconstructed."

---

## The HITL Loop (How We Get There)

Human-in-the-Loop is not just a technical method — it is a community model. The loop:

```
Historical map raster
        ↓
Community traces buildings, roads, land use   ← humans do what AI can't (yet)
        ↓
Labeled training data
        ↓
ML model trains on validated annotations
        ↓
Model suggests outlines on new maps           ← AI accelerates humans
        ↓
Community validates, corrects, enriches       ← humans keep quality high
        ↓
Corrections → better model + richer dataset
        ↑___________________________________|
```

**Where humans are essential (L4–L6):** Contextual interpretation, historical naming, ambiguous
boundaries, oral history capture, political/social framing. Machines cannot do this reliably.

**Where AI accelerates (L1–L3):** Repetitive tracing at scale, datum correction, GCP propagation,
building outline detection. Humans are too slow and expensive for this volume.

The community does specialized annotation work motivated by mission — the same work that costs
$20–50/hr commercially. This produces a training dataset and model weights that have real value and
are shared openly.

**Gamification as motivation layer:** Four contribution tiers map directly to the stack layers:
- *Photo Hunter* — find and tag archival photos (the raw material for L1–L3)
- *Cartographer* — trace building footprints from georeferenced maps (L4 conceived space)
- *Architect* — produce 3D models via photogrammetry (L2–L3 volumetric + facade space)
- *Historian* — add KG entities, oral histories, personal connections (L5–L6 perceived + lived
  space)

The OSM (OpenStreetMap) community is a natural partner for the Cartographer tier — they already know
how to trace building footprints and share VMA’s commitment to open data. HOT (Humanitarian
OpenStreetMap Team) and local OSM Vietnam chapters are the primary Phase 1 community outreach
channel.

See `docs/archive/gamification.md` for the full system design (archived — unbuilt).

---

## The Urban Planning & Design Lens

Tuệ's intellectual home is **urban planning & design**. The technical work (GIS pipeline, historical
maps, vectorization, KG) and the historical research are instruments for answering planning
questions: how did this city become what it is, and what does that mean for what it should become?

This reframes VMA from a digital heritage project into **research infrastructure for urban planning
scholarship** — specifically the spatial history of Saigon's transformation from French colonial
city (1880–1930) through wartime urbanism to post-1975 reconstruction and Doi Moi.

The driving questions are urban planning questions:
- Why did the French fill in the Nguyễn Huệ canal? (land speculation + tax revenue — a planning
  decision with spatial consequences readable on maps)
- Why were Chinese merchants concentrated in Cholon? (colonial segregation policy — a zoning
  decision encoded in cadastral records)
- How did post-1975 socialist planning alter the colonial street grid? (a morphological question
  answerable by comparing georeferenced maps across time)
- Why were certain streets renamed three times? (each regime asserting legitimacy through toponymy —
  readable in the KG's temporal layer)

**The MPP background is methodology, not background.** Public Policy asks: *Who benefits? Who
decides? What were the constraints? What were the incentives?* Urban planning asks the same
questions about space. The KG encodes the answers — political periods as first-class entities, land
tenure regimes as queryable filters, colonial administrators as named actors linked to spatial
decisions.

**The VnExpress series "50 năm quy hoạch TP.HCM"** (50 years of HCMC urban planning) is the
public-facing expression of this lens — demonstrating that VMA's founder already understands and can
communicate the city's planning history to a Vietnamese public audience.

These questions cannot be answered by geometry alone. They require structured context in the
Knowledge Graph — and the geographical text analysis method (geo-parsing colonial newspapers, trade
directories, and administrative reports) is the pipeline that populates it at scale.

**This is the differentiator.** A GIS lab can build L1–L4. A DH lab can build a KG. Only a team with
urban planning training + cartographic expertise + policy background + community infrastructure can
build L5–L6 with the interpretive integrity this material requires.

---

## Body and Soul (After the Saigoneer Article)

Tuệ frames the VMA mission as recovering both the *body* and the *soul* of the city:

- **Body** = physical structures, streets, rivers, geometry (L1–L4)
- **Soul** = sensory details, social histories, economic logic, human narratives (L5–L6)

The gap between body and soul is what VMA exists to fill. A georeferenced map gives you the body.
The Knowledge Graph + community layer gives you the soul.

---

## Precedents and Reading List

Tier 1 — the technical precedents this framework is built against:

| Source | Relevance |
|---|---|
| **Morlighem 2021** (TU Delft MSc) | OBIA → vectorization → LoD2 CityJSON from historical maps. The L2–L4 blueprint. Code: `github.com/CamilleMorlighem/histo3d` |
| **Bauckhage 2025** (ETH Zürich) | Static historical map → dynamic 3D VR landscape; extends Morlighem to 4D |
| **Gao 2024** | Diffusion models for urban change detection from historical maps → L1 automation |
| **Liu 2025** | Spatio-temporal KG + LLMs for geospatial Q&A on historical maps → L5 |
| **Jiao 2024** | Deep-learning road extraction from historical maps → L3 |
| **Kapoor et al. 2019** (Google/KDD, "Nostalgin") | 3D city from historical images → LoD3 photogrammetry |
| **NYPL Building Inspector** | Gamified crowdsourced historical building cataloguing → Cartographer-tier UX |
| **SODUCO** (ANR, Paris 1789–1950) | 113 Parisian trade directories → historical KG. Direct precedent for the pipeline below |

**The open gap:** no published work exists on OBIA calibration for French colonial Indochina map
symbology (contrast fills, hachure, street colour conventions). Morlighem calibrated for
Dutch/Belgian sheets. This is VMA's primary research-contribution opportunity.

---

## Geographical Text Analysis → Knowledge Graph

How L5–L6 get populated at a scale crowdsourcing alone cannot reach. The method is Ian Gregory's
geographical text analysis (Lancaster, Spatial Humanities):

```
Colonial text corpus (BnF/Gallica, EFEO — much already OCR'd by BnF)
         ↓
Geo-parsing — extract place references, disambiguate, assign coordinates
         ↓
Named Entity Recognition — persons, organizations, businesses, events
         ↓
Relation extraction — who owned what, where, when
         ↓
Knowledge graph population — entities, relations, and their source citations
         ↓
Spatial linking — connect entities to georeferenced map footprints (L1/L4)
```

**Status: unbuilt.** No knowledge-graph schema exists in the database. Nothing in
`supabase/migrations/` creates entity, relation, or source tables — the only trace is a comment in
`040_ocr_extractions.sql`. Treat this section as a design target, not a description of the system.

**Primary source corpus:**

| Source | Content | Layer |
|---|---|---|
| *Annuaire de la Cochinchine / de l'Indochine* | Merchant names, addresses, business types, year | L5 — who was where, in what year |
| *L'Opinion*, *La Dépêche d'Indochine* | Events, property transactions, street openings, public works | L6 events, L5 commercial activity |
| Rapports annuels, budgets coloniaux | Administrative boundaries, public works, census | L1 admin boundaries, L4 land use |
| EFEO field notes and published research | Vernacular names, ethnic quarters, temple records | Disambiguation layer |

The population method is three-layered: automated (geo-parsing + NER), community-validated (HITL
correction and enrichment), spatially linked (entities bound to footprints from the vectorization
pipeline). That keeps human interpretive judgment in the loop without making every entity a manual
task.

---

## The Open Source Commitment

Open is not a constraint — it is the strategy.

| What is open | Why |
|---|---|
| All data (CC-BY / ODbL) | Archives trust open projects; community contributes to what they own |
| All model weights | Published on Hugging Face; reproducible by anyone |
| All methodology | Published as papers; VMA becomes the authority, not a gatekeeper |
| The pipeline | Self-hostable; any archive can run it on their own collection |

The moat is not the code or the data. It is the community that built it, the trust of the archives
that contributed to it, and the methodology that VMA proved and published first.

---

## The Publication Strategy

Two tracks running simultaneously — methods papers (technical credibility) and urban planning papers
(intellectual contribution):

**Track 1: Methods papers (short-term, 1–2 years)**
1. **Automated georeferencing of historical military map series using GCP propagation** — the L7014
   pipeline (target: ISPRS Annals or CHR conference)
2. **OBIA calibration for French colonial Indochina map symbology** — the gap no one has filled
   (target: *Imago Mundi* or *International Journal of Geographical Information Science*)
3. **Geographical text analysis of colonial trade directories for geotemporal KG construction** —
   the Annuaire de l'Indochine pipeline (target: *Digital Scholarship in the Humanities* or Spatial
   Humanities Conference)

**Track 2: Urban planning papers (medium-term, 3–5 years)**
4. **The spatial history of Saigon urban planning, 1880–1975** — what the maps and KG reveal about
   colonial planning inheritance and post-war reconstruction (target: *Planning Perspectives* or
   *Urban History*)
5. **Dissecting Space: reconstructing the body and soul of a colonial city as a layered data stack**
   — the theoretical framework (target: *Journal of Urban History* or *Journal of Vietnamese
   Studies*)

Each methods paper is a grant application. Each urban planning paper is evidence that the tools
produce genuine historical knowledge — not just infrastructure.

**The VnExpress series** ("50 năm quy hoạch TP.HCM") is the public engagement track running
alongside both — demonstrating that this scholarship reaches Vietnamese audiences, not just
international academics.
