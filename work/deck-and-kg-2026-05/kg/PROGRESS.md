# Knowledge Graph build — progress ledger

> **FROZEN — 2026-06-04 snapshot.** Figures here (migration head 048, the corpus counts) are
> the state when the May 2026 deck and knowledge graph were built. See `SYSTEM.md`'s banner.

Resume anchor for the sectioned audit→graph→deck workflow.
Full plan: `~/.claude/plans/foamy-giggling-parnas.md` · Instruction: `memory/project_kg_workflow.md`.

**Discipline:** one stage per session → write artifact → tick here → STOP + compact before next stage.

| Stage | Artifact | Status |
|---|---|---|
| 1. System code audit (plain-language) | `docs/kg/SYSTEM.md` | ✅ done 2026-06-04 |
| 2. Project-realm graph nodes | `docs/kg/graph.json` | ✅ done 2026-06-04 (102 nodes / 116 edges) |
| 3. Field audit + field-realm nodes | `docs/kg/AUDIT.md` + `graph.json` | ✅ done 2026-06-04 (168 field nodes / 135 field edges) |
| 4. Bridge edges + viewer | `docs/kg/index.html` | ✅ done 2026-06-04 (23 bridge edges; data-driven viewer) |
| 5. Deck derivation (seminar + EWV skins) | `docs/kg/deck.html` | ⬜ |

## Resume here → Stage 5
Deck derivation → `docs/kg/deck.html` (two skins from the same spine: **seminar** for juniors,
**EWV** = Engaging With Vietnam for scholars). Plus the PhD SOP outline.
- The graph is now complete (270 nodes / 274 edges, both realms + bridges). Stage 5 reads
  `graph.json` + `AUDIT.md` + `SYSTEM.md` and **populates `deck:[]`** on the spine nodes
  (`'seminar' | 'ewv'` tags) so each slide traces to graph nodes — then renders `deck.html`.
- Likely narrative spine (confirm against AUDIT.md "career model" + theory.md body/soul):
  the 6-layer data stack → digitized→digitalized→reconstructed → the HITL loop → the 4 gaps as
  contributions → the build-the-tool-then-argue career model (Bol / McDonough / Mostern).
- EWV skin = scholarly framing (colonial cartography critique: Harley, Thongchai geo-body, Scott
  legibility); seminar skin = "how the machine works" for volunteers/juniors.
- Tag nodes by editing `graph.json` (single source of truth), then derive both skins from the tags.

## Stage 4 — done (2026-06-04)
- **23 cross-realm bridge edges** authored (project node → field node), validated: 0 dangling, 0 dup,
  all confirmed `project → field`. `graph.json` now **270 nodes / 274 edges** (was 270/251).
- Bridges by rel: `instanceOf` 3 (x:Allmaps→f:allmaps; x:Gallica→i:bnf; x:Rumsey→i:rumsey),
  `implements` 5 (georef→gcp-propagation/datum-helmert; MapSAM2→transformer-seg/hitl; ocr_extractions→geotext),
  `feeds` 4 (georef→histo3d; footprints→histo3d/ohm; ocr_extractions→whg), `addresses` 4 (the four gaps:
  MapSAM2→obia-indochina, georef→georef-indian1960, ocr_extractions→kg-sea-colonial, maps→spatial-saigon),
  `inheritsFrom` 3 (review→nypl-bi/rapid; trace→hot), `peerOf` 2 (MapSAM2→soduco; ocr_extractions→globalise),
  `runs` 1 (MapSAM2→mapsam2), `uses` 1 (georef→allmaps).
- New bridge rels added to `meta.schema.rels`: instanceOf, implements, feeds, addresses, runs, peerOf,
  inheritsFrom. `meta.stage` + `meta.description` updated.
- **Viewer:** `docs/kg/index.html` — data-driven Cytoscape reading `graph.json` (replaces the hardcoded
  `docs/knowledge-graph.html`). Realm shapes (project=rect, field=ellipse) + colors; filter by realm /
  status / kind; gaps red-bordered; **bridge edges drawn thick red with rel labels**; "Bridges only" view;
  click → detail panel (tags, source refs, in/out neighbors). NOTE: uses `fetch('./graph.json')` so it must
  be **served over HTTP** (`cd docs/kg && python3 -m http.server 8000`) — `file://` is blocked by CORS
  (the viewer shows that exact instruction if fetch fails). `deck:[]` left empty for Stage 5.

## Stage 3 — done (2026-06-04)
- `docs/kg/AUDIT.md` written: plain-language field landscape (5 clusters + HGIS/morphology/theory/planning),
  the 167-PDF library mapped by folder, the 4 research gaps + library-gap books, and the career-model through-line.
- `graph.json` extended to **270 nodes / 251 edges** (project 102/116 + field 168/135), validated (0 dup, 0 dangling).
  Field by kind: person 64, institution 30, fieldproject 22, method 11, concept 10, gap 4, work 9, venue 12, funder 6.
- New kinds: person, institution, fieldproject, method, concept, gap, work, venue, funder. New rels: affiliated,
  supervises, built, spawned, partOf, authored, proposes, influences, adjacent, publishesIn, funds. New status `gap`
  (research gaps + library-missing canonical works — Thongchai *Siam Mapped*, Anderson *Imagined Communities*,
  Cherry, Brocheux, Mostern *Yellow River*). `meta.kindColors` extended for all field kinds.
- **Edges are intra-field only** (person→institution, supervisor→student, builder→project, project lineage,
  person→concept/method, concept influence, exists-but-not-this→gap `adjacent`, gap→target `venue`, funder→project).
  Cross-realm bridges deliberately deferred to Stage 4.

## Stage 2 — done (2026-06-04)
- `docs/kg/graph.json` written: **102 project-realm nodes, 116 edges**, validated (no dup ids,
  no dangling edges). By kind: route 21, component 24, store 5, module 4, table 11, api 15,
  pipeline 2, script 8, external 12. By status: current 95, redirect-stub 3, legacy 3, removed 1.
- Schema: `{id,label,realm,kind,detail,status,source:[{ref,date}],deck[]}` + `{from,to,rel}`.
- Applied all SYSTEM.md corrections (explore/studio/trip/contribute hub; view/annotate/label
  redirect stubs; layersStore/LayerRenderer/MapWorkspace/MapModeOverlays/DrawTool/GpsTracker;
  HistoricalOverlay kept as a `removed` tombstone; new APIs ocr/apply, ocr-review/revert-recent,
  sync-georef, upload-image). Also added StudioMode/ReviewMode (live) and dropped dead
  ViewMode/AnnotateMode mode components.
- **Corpus numbers corrected against Supabase** (user flag): catalogue = **101 maps** (37 public
  / 64 draft; 39 georef_done), **country-wide not Saigon-only** — largest block is Indochine
  1:25,000 Tonkin & Thanh Hóa (62). Old "~20+ Saigon maps" estimate was wrong on count AND
  geography. Fixed in SYSTEM.md §1 and recorded in `graph.json` meta.corpus + t:maps node.

## Stage 1 — key findings (verified vs live code, 2026-06-04)
- Canonical surfaces flipped: **/explore = viewer** (/view→301), **/studio = drawing** (/annotate→301). Reverse of MEMORY.md.
- `LayerRenderer`+`layersStore` own rendering; `HistoricalOverlay` trio removed.
- Migration head **048** (types last regenerated from 047).
- New since last doc sweep: `/trip/[id]`, `/contribute` hub, shell `MapWorkspace`/`MapModeOverlays`/`DrawTool`/`GpsTracker`; APIs `ocr/apply`,`ocr-review/revert-recent`,`sync-georef`,`upload-image`.
- `StudioMode` carries an `animation/` keyframe system (playback + timelineStore).
