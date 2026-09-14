# Vietnam Map Archive — Strategy

_Funder-facing: what VMA is, what exists, where it goes, how it pays for itself._
_Last updated: August 2026. Supersedes `strategy-roadmap.md` and `startup-strategy.md`._

---

## What We Are Building

VMA reconstructs Saigon's urban history as a navigable, time-layered digital city — starting with the 1880–1930 French colonial period, when the city was remade from a river port into a modern metropolis.

Not a map app. **The spatial memory of a city most of the world has only seen in wartime.** The end product: stand at what is now Nguyễn Huệ Boulevard and watch, decade by decade, the canal fill in, the opera house rise, the merchant families move, the street names change three times under three regimes.

**The problem.** Historical maps of Vietnam are scattered across French national archives, American military repositories, university libraries, and private collections — unlinked to each other or to modern geography, inaccessible to Vietnamese researchers, rich in physical data but stripped of social and political context, and exposed to link rot. The gap is not the maps. It is the infrastructure to connect them.

**The frame.** The city as a six-layer data stack, built bottom-up, with political and economic context cutting across every layer. Full argument in [`docs/theory.md`](./theory.md) — not repeated here.

---

## What Kind of Organisation This Is

Not a SaaS startup, not a conventional nonprofit. Closer to **Wikipedia meets Hugging Face**: community-owned data infrastructure, open by default, sustained by the value of the methodology and the models it produces.

The product is not the platform — it is the HITL pipeline. Community contributions train models that make contribution cheaper, which attracts contributors, which produces better models. The outputs (data, weights, method) are open; the moat is the community, the archive relationships, and the documented know-how.

VMA is simultaneously (1) a public infrastructure project on the OSM/Wikipedia model and (2) the research infrastructure for a PhD in urban planning & design on the spatial history of Saigon. These are not in tension — Peter Bol built CHGIS as both field infrastructure and his own research instrument.

---

## What Is Already Built

Verified against the tree, August 2026.

| Capability | Status | Notes |
|---|---|---|
| Platform live (SvelteKit 5, Cloudflare Pages, Supabase) | ✅ | |
| Map corpus, georeferenced via Allmaps | ✅ | **~101 maps** |
| IIIF hosting + redundancy (Internet Archive, R2 mirror) | ✅ | `/api/admin/maps/[id]/mirror-r2` |
| Automated georef pipeline, L7014 US Army series (~500 sheets) | ✅ **proven** | Datum correction Indian 1960 → WGS84 (Helmert) |
| GCP propagation across uniform map series | ✅ **proven** | |
| Public browse + layer stack viewer (`/explore`) | ✅ | Display modes: Stacked / Lens / Side-by-side |
| Free-form annotation + timeline (`/explore?mode=annotate`) | ✅ | |
| Story authoring + GPS playback (`/explore?mode=story`, `/trip/[id]`) | ✅ | |
| IIIF viewer, on the sheet's own page (`/catalog/[id]`) | ✅ | |
| OCR pipeline: Gemini Flash → `ocr_extractions` | ✅ | `work/ocr/` |
| OCR triage + human review UI (`/scan?mode=prepare`) | ✅ | Neatline, tile grid, bbox review |
| MapSAM2 footprint segmentation → `footprint_submissions` | ✅ | `work/MapSAM2/` (fine-tuned SAM2, LoRA) |
| Footprint tracing (`/scan?mode=shapes`) and HITL review (`/scan?mode=shapes&tab=validate`) | ✅ | |
| Georeferencing hand-off to Allmaps (`/contribute/georef`) | ✅ | |
| Admin map CRUD, bulk upload, external-source scout | ✅ | Inline in `/catalog` (role `admin`/`mod`), plus `/admin?tab=bulk`, `/admin?tab=scout` |
| Full-text search over corpus + scout candidates | ✅ | `/api/search` |
| Featured in Saigoneer (January 2026) | ✅ | Credibility |

**Route surface.** Editorial (public, nav + footer): `/`, `/catalog`, `/about`, `/blog`, `/profile`, `/login`, `/contribute`, `/contribute/georef`, `/admin?tab=bulk`, `/admin?tab=scout`. Full-screen tools: `/explore`, `/explore?mode=annotate`, `/explore?mode=story`, `/trip/[id]`, `/scan`, `/scan?mode=prepare`, `/scan?mode=shapes`, `/scan?mode=shapes&tab=validate`.

**Not built, despite appearing in older drafts:**
- **Knowledge graph.** No entity/relation/source schema exists in any migration (head: 051). The KG is a Phase 2 target, not a shipped component. Earlier docs cited migration numbers for it; those numbers are long since taken by shipped work.
- **Label Studio.** Retired. The crowdsourced-extraction flow is now `/scan?mode=prepare` — triage plus OCR review — and `/scan?mode=shapes`.
- **Admin pipeline dashboard.** There is no dashboard component and no pipeline API surface beyond per-map stage endpoints. Admin work happens inline in `/catalog` and in the two dedicated admin pages.
- **3D / LoD2 / 4D timeline.** Phase 3. No code.

**Proven vs. built.** The georeferencing pipeline is both — 500 sheets processed, datum corrections validated, propagation working. The OCR and segmentation pipelines are built and running on real maps but not yet proven at corpus scale. The HITL improvement loop — corrections feeding back into model quality — remains a thesis, not a demonstrated cycle.

---

## Engineering vs. Research: An Honest Map

The most important section for understanding what is being asked for.

| Component | Type | Status | Risk |
|---|---|---|---|
| Georef automation, uniform series | Engineering | Proven | Low |
| Datum correction | Engineering | Proven | Low |
| Georef extension to irregular colonial maps | Engineering | Buildable | Low–Med |
| Community tracing + OCR review UI | Engineering | Built | Low |
| ML feature detection from historical maps | Research | Running, unproven at scale | Medium |
| HITL improvement loop (AI + community) | Research hypothesis | Unproven | Medium |
| Knowledge graph (schema + query) | Engineering | Unbuilt, buildable | Low |
| KG quality at scale (contested dates, uncertain sources) | Research | Unproven | Medium |
| LoD2 3D city model (Morlighem pipeline) | Engineering | Proven method, adaptation needed | Low–Med |
| LoD3+ landmark photogrammetry (SfM from archival photos) | Research | ~30 buildings, bounded | Medium |
| Height inference (probabilistic roof table, no LiDAR) | Engineering | Documented method | Low |
| Community scaling beyond ~10 volunteers | Open question | Gamification is the bet | Med–High |

**On L2 (LiDAR).** Modern LiDAR of Ho Chi Minh City exists but describes a 2020s city. LiDAR of colonial Saigon does not exist and never will. VMA's L2 for this period is typological 3D inference from archival photographs, building typology standards, and shadow geometry — approximate and uncertainty-scored, not surveyed.

---

## The Three-Phase Roadmap

### Phase 1 — Maps to Geometry
_"Turn colonial maps into spatial datasets" · 6–9 months from funding_

The first open, structured dataset of 1880–1930 Saigon's urban footprint: building outlines, road networks, canal traces, land use zones, derived from map rasters. You cannot build a knowledge graph of a city until you know where things were.

| Output | Type |
|---|---|
| 30–50 georeferenced colonial maps from BnF Gallica + EFEO | Engineering |
| Georef pipeline extended from uniform grid (L7014) to irregular colonial sheets | Engineering |
| Gamified tracing UI — Photo Hunter + Cartographer tiers, leaderboards, missions | Engineering |
| OSM / HOT / OSM Vietnam outreach | Community |
| ML vectorization at corpus scale (MapSAM2 fine-tune + OCR join) | Research |
| 1880–1930 footprint dataset v0.1, open GeoJSON | Output |

Milestones: 10 colonial maps through the extended pipeline · gamified tracing UI live · segmentation model trained on reviewed extractions · first public dataset release (1900 Saigon footprints) · 5 temporal snapshots across 1880–1930.

**Honest note:** the dataset release is deliverable through community tracing alone. The ML model is an accelerant, not a prerequisite, and the release will not wait on it.

**Key constraint:** primary sources are in French. Volunteers working with archival text need French reading ability, or the project needs a researcher dedicated to translation and contextualisation.

### Phase 2 — Geometry to Knowledge
_"Give every building a story, every street a history" · 9–18 months_

The knowledge graph: a structured, citeable, queryable record of what existed where and when, under which political and economic conditions. Phase 1 gives *where*; Phase 2 gives *who, what, why*.

| Output | Type |
|---|---|
| KG schema — entities, relations, sourced claims (**nothing exists today**) | Engineering |
| Historical source ingestion — cadastral records, land titles, newspapers | Engineering + research |
| Political/social context layer — administrative regimes as queryable filters | Engineering |
| Temporal uncertainty model — approximate, contested, unknown dates | Research |
| Public entity explorer + research library of citeable sources | Engineering |

The population method is geographical text analysis over the colonial corpus — see [`docs/theory.md`](./theory.md).

**Honest note:** 1880–1930 is unusually well documented; French colonial administration kept land registers, business permits, and censuses, much of it now digitised. The KG is structured indexing of existing material, not research from scratch. The hard problem is temporal uncertainty — most buildings have a range, not a date. Uncertainty fields are built in from day one.

### Phase 3 — Knowledge to Dimension
_"Lift the city off the page" · 18–30 months_

LoD2 3D models of 1880–1930 Saigon in CityJSON for all buildings, plus hand-crafted LoD3+ landmarks, anchored to Phase 1 footprints and Phase 2 entities. 3D without footprints is unanchored; 3D without a KG is decoration.

**Method:** adapt Morlighem (2021), *Automatic reconstruction of 3D city models from historical maps* (TU Delft MSc, CC-BY, `github.com/CamilleMorlighem/histo3d`) — OBIA segmentation → text removal + vectorisation → 2D procedural plots → height inference via probabilistic roof-type table → LoD2 CityJSON. VMA's automated georeferencing is precisely the prerequisite Morlighem needed and did not automate; the two are a clean complement.

**The one bounded research question:** how well does OBIA colour classification transfer from Dutch/Belgian sheets to French colonial Indochina symbology? One study area, known colour scheme — a calibration problem, not an open-ended bet.

**Partnership:** TU Delft 3D Geoinformation (Hugo Ledoux, Morlighem's supervisor, creator of CityJSON) is the natural collaborator and strengthens every grant application. Volunteer roles: GRASS GIS calibration, Blender landmark modelling, architecture historians on typology, CityJSON validation.

---

## Economic Model

If everything is open, what sustains the work?

**1 · The models.** Georeferencing and vectorization models trained on community-validated historical map data — the first open models purpose-built for this material. Value via commercial licensing on top, Hugging Face hosting, and consulting engagements teaching institutions to run the pipeline on their own collections.

**2 · The methodology.** A reproducible method for historical urban reconstruction, documented and published. Value via academic publication (authority, citation, doors at archives and universities), workshops for archivists and urban researchers, and co-grant applications where VMA brings method and tools and a university brings researchers and overhead.

**3 · Institutional membership.** OSM/Wikipedia/Mozilla model. Free forever for individuals, researchers, non-commercial use. Voluntary-but-expected membership for organisations building commercially on VMA data. Founding-partner recognition for archives providing early access or co-funding.

**4 · Grants.** The honest truth: Phases 1–2 are grant-fundable, not revenue-fundable.

### Why open is the strategy, not a sacrifice

| Closed model | Open model (VMA) |
|---|---|
| Data is the moat | Methodology is the moat |
| Users are customers | Users are contributors |
| Scale by hiring | Scale by community |
| Trust earned commercially | Trust built in — open is auditable |
| Archives are suspicious | Archives are partners |
| Forking is a threat | Forking is proof the method works |

Decentralised in practice: any institution can self-host the pipeline; data lives in Internet Archive and an open Supabase schema and is exportable; any city or era can fork the approach (Hanoi, Phnom Penh, Manila, Nairobi, Algiers); governance trends toward a foundation model rather than founder control. Code MIT/Apache 2.0, weights on Hugging Face, data CC-BY/ODbL.

### Sustainability tiers

```
Years 1–2 · Grant-funded
├─ Crowdfunding (community proof + seed)              $20–30K
├─ 2–3 institutional grants                          $150–250K
└─ In-kind volunteer time (~1,000 hrs/yr)             ~$30K/yr

Years 2–3 · Mixed
├─ Grants (renewed + new)                         $100–200K/yr
├─ Institutional memberships (5–10 orgs)            $25–50K/yr
├─ Consulting / training workshops                  $20–40K/yr
└─ Model API (commercial tier)                       $5–20K/yr

Year 3+ · Community-sustained
├─ Model API (commercial tier)                     $50–100K/yr
├─ Institutional memberships (20+ orgs)           $100–200K/yr
├─ Workshops / training programme                      $50K/yr
└─ Grants (smaller, project-specific)              $50–100K/yr
```

**The target:** cover two full-time people (founder + one engineer) by end of Year 2. Everything else is community. Lean, mission-driven, sustainable without extraction.

### Funding tranches

| Tranche | Covers | Ask | Use |
|---|---|---|---|
| Seed (crowdfunding) | Phase 1, through first dataset release | $15–25K | Map corpus research, tracing UI, dataset v0.1 |
| Grant Round 1 | Rest of Phase 1 + Phase 2 schema/entities | $60–100K | Part-time French-sources researcher, KG build, ML at scale |
| Grant Round 2 | Phase 2 library/release + Phase 3 start | $80–150K | Research library, photo corpus, typology, 3D partnership |

### Grant landscape

| Funder | Fit | Size |
|---|---|---|
| French Institute / Institut français (Vietnam cultural programme) | High — French colonial archive | $30–80K |
| EFEO partnership grant | High — co-application, map corpus + KG | $30–80K |
| Wikimedia Foundation | High — open data infrastructure | $20–50K |
| Asia Foundation | High — SE Asia open knowledge | $30–100K |
| NEH (with a US university partner) | Med-High — Phase 2–3 digital heritage | $50–300K |
| UNESCO Memory of the World | High — credibility plus small grants | $10–30K |
| EU Horizon (Digital Heritage) | Medium — needs an EU partner (TU Delft) | $100–500K |

**Not targeting:** Ford Foundation (civil society / democracy, not digital heritage). Mellon Foundation (reduced DH infrastructure funding post-2022).

**Sequence:** lead with French Institute + EFEO, the natural fit for 1880–1930 French colonial sources. First grant funds a part-time researcher and one engineer. The TU Delft partnership opens EU Horizon. Wikimedia and Asia Foundation supply open-data credibility. Everything compounds from there.

---

## Transparency for Funders

Small, volunteer-driven project. Deep work needs protected time. Funders should see progress without asking for it.

| Layer | How | Cadence |
|---|---|---|
| This document | Status tables updated on completion, versioned in git | On completion |
| Dataset changelog | Release notes per data version | Per release |
| Monthly digest (2 paragraphs) | What shipped, what didn't and why, what's next | Monthly |
| Live platform | The platform is the demo | Always |
| Open repository | Commit history is the activity log | Continuous |

The rule: no progress meetings, no slide decks on demand. The digest is the contract. Late milestone — the digest says why. Failed research bet — the digest says what was learned.

---

## Why This Is Fundable Now

1. **The hardest part is proven.** Automated georeferencing of 500 sheets is done, not promised. The ask is to extend a working method, not invent one.
2. **The data gap is real.** No open dataset of French colonial Saigon's urban fabric exists anywhere.
3. **The method transfers.** What works for Saigon 1880–1930 works for Hanoi, Phnom Penh, Manila, Algiers — any city built under a colonial mapping administration that kept records.
4. **Uncertainty is labelled.** Every research bet is marked as one. Projects that overpromise destroy funder trust.
5. **The output is permanently open.** A public good that outlasts the project.

## What We Are Not

Not a tourism app. Not a game. Not a startup seeking exit. Not a closed archive. Not a project that will claim a finished 3D city on a timeline it cannot keep.

Public infrastructure for historical memory — open, honest about what it knows and doesn't, and designed to still be useful in fifty years.

---

_Progress: the live platform · the GitHub repository · vietnam.ma.project@gmail.com_
