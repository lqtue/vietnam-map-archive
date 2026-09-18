# VMA Deck v2 — Outline

**Working title:** *Deconstructing the World, Reconstructing the Past — A Method for Historical Maps*
**Speaker:** Lê Quang Tuệ · the Vietnam Map Archive project
**Status:** outline for iteration (drafted May 2026, post-EWV15 Dec 2025)
**Source decks:** `docs/vma-deck.md` (Marp, pitch-oriented) · `VMA Deck - EWV15-2.pdf` (Dec 2025 conference)

---

## Design principles

- **One spine, no parallel vocabularies.** The 4-stage method is the only mental model the audience has to learn. The 6-layer stack is dropped from the core deck (kept as an optional academic appendix).
- **Philosophical arc, not project tour.** Deconstruct (modern world as data) → past doesn't have this → can we retroactively deconstruct the past? → method → reconstruct.
- **Lit review earns the method.** Before showing the pipeline, show what others have done and where the gaps are.
- **Modular.** Core deck works for general public; technical deep-dives, funder asks, and PhD-framing slides plug in as appendices.
- **Visual aesthetic:** carry forward EWV15 dark navy + serif title, sparse text, evidence-heavy.

---

## Arc (one sentence per beat)

1. The modern world has been **deconstructed into data**.
2. The past has not — it survives only as evidence.
3. Question: can we retroactively deconstruct the past the way we deconstruct the present?
4. Others have tried — here's where the field stands.
5. Gaps remain — here's what's missing.
6. Our solution: a 4-stage method, demonstrated on colonial Saigon.
7. Reconstruction: stack the stages into a 4D past.
8. The reconstructed past is never neutral — what kind of "world" do we get?

---

## Slide-by-slide outline

### Section 0 — Open (3 slides)

| # | Slide | Content | Notes |
|---|---|---|---|
| 0.1 | Title | "Deconstructing the World, Reconstructing the Past" — Saigon panorama bg | Keep EWV15 aesthetic |
| 0.2 | QR codes | Stable PC + experimental mobile | Update URLs |
| 0.3 | Speaker | Short VTV/VnExpress credibility frame | **Modular — drop for academic** |

### Section 1 — Premise: the world as data (3 slides)

| # | Slide | Content |
|---|---|---|
| 1.1 | Hook visual | Modern satellite / OSM / IoT collage |
| 1.2 | "The world has become data" | Continuous deconstruction into queryable layers — any place, any moment, can be queried |
| 1.3 | Examples from VnExpress | Population density map, Thái Nguyên flood viz — your own work as evidence of "world-as-data" journalism |

### Section 2 — Problem: the past is not (4 slides)

| # | Slide | Content |
|---|---|---|
| 2.1 | "But the past..." | Switch to historical map (Plan de Saigon 1898) |
| 2.2 | Why maps specifically | Pre-satellite era — densest spatial record we have. Keep Sputnik + EO acquisition slides |
| 2.3 | Maps as evidence | White (2010) "history on the head of a pin" quote |
| 2.4 | But historical maps... | Not queryable / readable / analysable / enrichable. **Digitized (pixels) ≠ Digitalized (knowledge)** |

### Section 3 — Question (1 slide)

| # | Slide | Content |
|---|---|---|
| 3.1 | Research question | *Can we retroactively deconstruct the past the way we deconstruct the present — and make the result open and crowdsourceable?* |

### Section 4 — Lit review (2 slides)

| # | Slide | Content |
|---|---|---|
| 4.1 | Comparable projects (table) | Allmaps · SODUCO · NYPL Building Inspector · histo3d (Morlighem) · ETH IKG (Hurni/Wu/Chen) · CHGIS · MapSAM2. Group by what each solves and what it doesn't |
| 4.2 | The gaps | (1) no end-to-end open pipeline; (2) no calibration for French colonial Indochina symbology; (3) no crowdsourcing-as-method; *[opt 4: no SE Asia spatial-history infrastructure]* |

### Section 5 — Our solution: the 4-stage method (1 slide intro + 8 stage slides)

| # | Slide | Content |
|---|---|---|
| 5.0 | Method overview | Input → Initial (Vectorized) → Standardized (Georectified) → Enriched (Materials embedded). State explicitly: extends Allmaps + MapSAM2 |
| 5.1 | **Stage 1: Input** | Open framework (IIIF) + crowdsourced materials (manhhai, Stanford, BnF Gallica, Internet Archive) |
| 5.1d | *Deep-dive* | IIIF protocol; IIIF-C members; **self-hosted IIIF at `iiif.maparchive.vn`** (R2 + Worker, on-the-fly info.json patching) — used to ingest 62 SGI cadastres |
| 5.2 | **Stage 2: Vectorize** | Segmentation → polygons |
| 5.2d | *Deep-dive* | MapSAM2 (LoRA fine-tune, OCR-seeded prompting, watershed post-processing); HITL review at `/contribute/review` |
| 5.3 | **Stage 3: Georectify** | Allmaps editor + propagation |
| 5.3d | *Deep-dive* | Vector-to-vector alignment; wide-baseline matching; L7014 sheet-grid propagation method (extrapolate from neighbor seeds, no feature matching needed) |
| 5.4 | **Stage 4: Enrich** | KG + photos + oral history embedded onto the georef base |
| 5.4d | *Deep-dive* | KG schema; source-citation provenance; then/now slider |

### Section 6 — Demonstration: Chợ Cũ worked example (4 slides)

Walk one place through all four stages. This is the talk's strongest narrative moment — keep the Chợ Cũ slides from EWV15 verbatim, just re-cast as "method demonstration" rather than "example in stage 4".

| # | Slide | Content |
|---|---|---|
| 6.1 | 1893 Plan Cadastral de Saigon | Full sheet |
| 6.2 | Zoom — Marché Central + aerial perspective alignment | Cadastre ↔ bird's-eye view |
| 6.3 | Photo + Vietnamese text (Chợ Cũ history) | Materials embedded |
| 6.4 | Then/now slider | Saigon Hôtel de Ville ↔ HCMC today |

### Section 7 — Crowdsourcing layer (2 slides)

| # | Slide | Content |
|---|---|---|
| 7.1 | Three contributor roles | **Cartographer** (OSM mappers → vectorize) · **Architect** (photogrammetry → 3D) · **Historian** (KG entries → narrative) |
| 7.2 | Live contribute tools | Screenshots of `/contribute/georef`, `/contribute/digitalize` (Triage + OCR review), `/contribute/trace`, `/contribute/review` |

### Section 8 — Results (3 slides)

| # | Slide | Content |
|---|---|---|
| 8.1 | 100+ historical maps | Grid screenshot (keep) |
| 8.2 | By the numbers | *[fill from current state: N georeferenced / N self-hosted / N OCR extractions / N SAM2 polygons reviewed / N volunteers]* |
| 8.3 | QR codes (mid-deck) | Audience opens live |

### Section 9 — Reconstruction: the 4-phase roadmap (2 slides)

Frame as **"the 4 stages, scaled across 4 layers of representation."**

| # | Slide | Content |
|---|---|---|
| 9.1 | 4-phase diagram | Phase 1 Geometric Foundation (map) → Phase 2 Semantic Core (KG) → Phase 3 Visual Validation (SemPinPnP, photos) → Phase 4 Neural Reconstruction (3D). Keep existing diagram |
| 9.2 | Generalizability | Method portable beyond Saigon — Hanoi, Angkor, any place with a paper trail |

### Section 10 — Discussion (2 slides)

| # | Slide | Content |
|---|---|---|
| 10.1 | Contributions | Technical: open end-to-end pipeline · Epistemological: "ground truth" is negotiated, not given |
| 10.2 | Absolute vs Relative perception of space | Chinese-style map (keep) — colonial cadastres encode one kind of space, Vietnamese/Sinitic maps encode another. The reconstructed past inherits whichever we choose |

### Section 11 — Close (2 slides)

| # | Slide | Content |
|---|---|---|
| 11.1 | Thank you | Centered |
| 11.2 | Contact | Facebook + email + project URL |

---

## Modular append-ons (drop in per venue)

### A. For funders / partnerships
- Comparables table (extends Section 4 with budget context)
- Budget envelope (24-month)
- Asks: GPU credits, annotation lead, R2 storage, OSM partnership

### B. For Allmaps / IIIF community
- "Where VMA extends Allmaps" — self-hosted IIIF at scale, bulk pipeline, multi-source per map, lookup by Allmaps ID, DC metadata layer
- Where we'd love to collaborate — annotation review API, batch georef standards, footprint trace interchange

### C. For PhD audiences (GSAPP, EFEO, ICOMOS)
- VMA as the research apparatus for a spatial history of Saigon
- Long arc: 1859 → present, three planning regimes, climate-adaptive design question
- Field positioning vs CHGIS, SODUCO, Felicity Scott, Hiba Bou Akar

### D. For OSM / crowdsourcing audiences
- Cartographer track deep-dive
- Direct call to action: tools, onboarding, recognition

### E. Optional academic framing — 6-layer data stack
- Single slide: "the modern world model has 6 layers; we rebuild them backwards in time"
- L1 maps · L2 mass · L3 road & facade · L4 mesh · L5 KG · L6 oral history
- Use only if audience needs conceptual scaffolding (museums, theorists)

---

## Open questions / decisions pending

- [ ] Final numbers for Section 8.2 (corpus, OCR, SAM2, volunteers) — needs live DB pull
- [ ] Lit review depth — single-table version (above) for general; add inline-citation version for academic?
- [ ] Confirm 4-phase diagram labels are still current (TopoTPS, SemPinPnP) or have been renamed
- [ ] Decide whether to ship the deck as Marp `.md` (text-iterable) or hand off to Keynote (visual control)
- [ ] Confirm public URL: is it `maparchive.vn` yet, or still `vietnammaparchive.github.io/v3-beta/`?

---

## Build order (next steps)

1. Lock the arc above. ✅ pending your sign-off
2. Fill in current numbers (Section 8.2) — needs you or a DB query
3. Draft slide-by-slide text + speaker notes
4. Decide format (Marp vs Keynote handoff)
5. Pull/regenerate screenshots for live contribute tools (Section 7.2)
6. Refine 4-phase diagram (Section 9.1) if labels have shifted
