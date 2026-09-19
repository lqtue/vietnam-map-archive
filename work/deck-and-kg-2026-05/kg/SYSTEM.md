# How the Vietnam Map Archive Works

*Plain-language system reference. Written so a non-technical reader can follow it, but precise
enough to rebuild the system from. Verified against the live code on 2026-06-04 (route list,
stores, shell components, migration head).*

> **FROZEN — this is a 2026-06-04 snapshot, not the current state.** It was written as the
> plain-language reference behind the May 2026 deck and the knowledge graph, and it says so in
> numbers that have since moved: migration head **048** (the head is 091), **101 map records**, no
> series layer, no `/catalog/[id]` page, no OCR gate. It previously claimed to be the canonical
> current-status doc that wins when others disagree; that claim is withdrawn — it is a dated
> artefact of the deck work. For current state read `/CLAUDE.md` and the tree-local `CLAUDE.md`
> files, which are maintained against the code. Do not cite this file for a figure.

---

## 1. What VMA is, in one breath

The Vietnam Map Archive (VMA) is a website for **exploring old maps of Vietnam laid on top of
the real modern map**. Saigon / Ho Chi Minh City is the project's heart and densest coverage,
but the catalogue now spans the country: the single largest block is a French *Indochine
1:25,000* topographic series of **Tonkin & Thanh Hóa** (northern Vietnam), alongside US Army
city maps (AMS L909) and the 1:50,000 L7014 series. You can fade a 1898 French map in and out
over today's streets, follow a guided walking tour on your phone, and — if you volunteer —
help turn those old maps into usable data by tracing buildings, fixing where a map sits on the
globe, or correcting text the computer read off the map.

Under the hood it does three jobs:
1. **Show** historical maps accurately positioned over a modern basemap.
2. **Collect** human contributions (traces, corrections, georeferencing) and **AI output**
   (text and building shapes read automatically) on top of those maps.
3. **Turn** all of that into structured, queryable data — the long-term goal being a
   layered, time-aware digital model of the city.

It is built as one web app (SvelteKit) talking to one database (Supabase), with map images
served from cloud storage (Cloudflare). About ten volunteers contribute. **The catalogue holds
101 map records** (verified in Supabase 2026-06-04): 37 `public`, 64 `draft`; **39 are marked
georeferenced** (`georef_done`). By collection: Indochine 1:25,000 Tonkin & Thanh Hóa (62),
the original Saigon-focused "Vietnam Map Archive" set (35), AMS L909 city maps (3), AMS L7014
(1). Top holding institutions: Cartomundi / Aix-Marseille (62) and the Bibliothèque nationale
de France (16). *(Earlier drafts said "~20+ georeferenced maps of Saigon" — that undercounted
and over-narrowed; corrected against the live database.)*

---

## 2. The mental model (how the pieces fit)

Think of four moving parts:

- **A map image** — a scanned old map (a big picture).
- **A georeference** — the instructions that say *where on the globe each corner of that
  picture belongs*, so the software can stretch ("warp") the picture to line up with reality.
- **The viewer** — the part of the website that draws a normal modern map and then paints the
  warped old map on top as a see-through **overlay**.
- **The contributions** — points, traced shapes, text boxes, and approvals that people and AI
  attach to a specific map.

A few terms used throughout:
- **IIIF** — a standard way of serving very large images in tiles so they load fast at any
  zoom. Most source institutions (national libraries, archives) publish their scans this way.
- **Allmaps** — an open-source toolkit VMA builds on. It stores georeferencing as a small
  open file (a "georeference annotation") and warps IIIF images live in the browser.
- **Overlay** — the historical map drawn semi-transparently over the modern map.
- **Basemap** — the modern reference map underneath (streets or satellite).

---

## 3. The pages (what each part of the site is for)

VMA's pages fall into two families. **Editorial** pages are normal public pages with the site
header and footer. **App** pages are full-screen map tools with their own minimal chrome.

### Public / editorial pages
| Page | What it's for |
|---|---|
| `/` | Home — featured maps, intro to the project. |
| `/catalog` | The full catalogue of maps; searchable/filterable. Admins & moderators get inline editing tools here. |
| `/about`, `/blog`, `/blog/[slug]` | Project info and articles. |
| `/contribute` | A hub page explaining the ways to help; what you see adapts to your role. |
| `/contribute/georef` | Georeference a map (place it correctly on the globe) using the Allmaps editor. |
| `/login`, `/profile` | Accounts. `/profile` sends you to `/login` if you're not signed in. |
| `/admin/bulk`, `/admin/scout` | Admin-only: bulk-create map records; review maps auto-discovered from external libraries. |

### The map surfaces (where you actually look at maps)
| Page | What it's for |
|---|---|
| **`/explore`** | **The canonical map viewer.** Modern map + historical overlays, with a one-time "use my location / show all maps" chooser, a first-visit guided tour, coverage lookup at your GPS position, and story playback. Share links (`?map=`, `?story=`) and the URL hash are honored. |
| **`/studio`** | **The canonical drawing/annotation surface** (`StudioMode`). Draw points, lines, and polygons on maps; also drives an animation/keyframe timeline for animated story scenes. |
| `/create` | Build stories and "adventures" (guided point-to-point tours) — `CreateMode`. |
| `/trip/[id]` | A tourist-grade **mobile story player**: a phone walks you stop-to-stop using GPS, no account needed. Designed for QR-code scanning in the field. |
| `/image` | An inspector for a single IIIF image in pixel coordinates. |

> **Redirects you must know (these changed recently):**
> - `/view` → **301 → `/explore`** (the old viewer was folded into Explore).
> - `/annotate` → **301 → `/studio`** (drawing moved to Studio).
> - `/contribute/label` → **301 → `/contribute/digitalize`** (labeling was absorbed into Digitalize).
> Query strings are preserved through all three. Older docs that call `/view` or `/annotate`
> the "real" pages, or claim `/studio → /annotate`, are **out of date** — it is now the reverse.

### Contribution tools (turning maps into data)
| Page | What a volunteer does there |
|---|---|
| `/contribute/georef` | Pin matching points between the old map and the real world so it lines up. |
| `/contribute/trace` | Trace building footprints (polygons) and roads/rivers (lines) directly on a map image. |
| `/contribute/digitalize` | Two-phase workflow: **Triage** (mark the map's edges + which tiles matter) → **OCR Review** (correct the text the computer read). |
| `/contribute/review` | Approve or reject building shapes the AI proposed. |

---

## 4. How a historical map gets onto the screen

This is the core data flow. Steps:

1. **Find a scan.** A map comes from a source institution (BnF/Gallica, David Rumsey, Library
   of Congress, Humazur, etc.), usually as an **IIIF** image. The `/admin/scout` tool helps
   discover candidates automatically; `/admin/bulk` helps create many records at once.
2. **Mirror the tiles (optional).** For reliability VMA can copy the image tiles to its own
   **Cloudflare R2** storage (served at `iiif.maparchive.vn`). A small worker patches the
   tile metadata on the fly.
3. **Georeference it.** Using the Allmaps editor (`/contribute/georef`), a human places
   control points so the software knows where each part of the picture sits on Earth. The
   result is a small open **georeference annotation** file.
4. **Record it.** The map gets a row in the `maps` database table (title, dates, institution,
   image link, the georeference link, status, etc.).
5. **Show it.** When you open `/explore`:
   - A single map engine (**`MapShell`**, built on OpenLayers) draws one modern map.
   - A list of "what to render" lives in the **`layersStore`** — a base layer (modern streets,
     satellite, or none) plus a stack of historical **overlays**, each with its own opacity
     and order.
   - One component, **`LayerRenderer`**, reads that list and paints everything: the basemap
     and every warped historical overlay. (This replaced an older trio of overlay components —
     `HistoricalOverlay` / `HistoricalBaseLayer` / `StackedOverlay`, now removed.)
   - View modes: **Stacked** (overlays fade on top), **Lens** (a spyglass circle), and
     **Side-by-side** (two panes, the second drawn by `DualMapPane`).
   - `MapWorkspace` is the shared "chrome" (panels, mobile drawers) wrapped around the map by
     both `/explore` and `/trip`.

**The relevant stores (shared state):**
- **`layersStore`** — *the single source of truth for what the map renders*: the base layer +
  the ordered overlay stack (each overlay has its own opacity/visibility). Saved to the
  browser so your view persists.
- **`mapStore`** — where the map is looking: longitude, latitude, zoom, rotation, and which
  map is "active." Defaults to Saigon, zoom 14.
- **`layerStore`** (no "s") — *legacy* display settings (view mode, lens radius, etc.); older
  opacity/visibility fields here no longer drive rendering — `layersStore` owns that now.
- **`urlStore`** — keeps the web address in sync with the view, so a link reproduces exactly
  what you see (`#@lat,lng,zoom,rotation&map=…&base=…`).

---

## 5. The contribution pipelines (step by step)

VMA mixes **human work** and **AI helpers**. The AI proposes; humans approve. The shared
"where are we" tracker for each map is the `map_pipeline_status` table, with a lifecycle:

```
idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported
```

### A. Georeferencing (`/contribute/georef`)
Place control points old-map ↔ real-world → produces the georeference annotation → the map
can now be shown warped. This is the prerequisite for everything spatial.

### B. Tracing (`/contribute/trace`)
On a fixed map image (pixel coordinates), a volunteer draws **polygons** for building
footprints and **lines** for roads/waterways. Saved to `footprint_submissions`. (Tracing and
the digitalize tools use `ImageShell` — a pixel-coordinate canvas — not the geographic
`MapShell`.)

### C. Digitalize = Triage → OCR Review (`/contribute/digitalize`)
1. **Triage:** mark the map's printed edge (the "neatline") and click tiles to set priority
   (normal / low-res / skip). Then trigger OCR.
2. **OCR (automatic):** a Gemini model reads text off the map tiles and stores each piece as a
   box in `ocr_extractions`.
3. **OCR Review:** a human fixes the text, category, and position of each box; bad ones are
   rejected. Boxes can also be drawn by hand.

### D. Footprint Review (`/contribute/review`)
The **MapSAM2** model (a fine-tuned segmentation AI) proposes building outlines from the map
tiles. A reviewer approves or rejects each, then marks the map "segmentation reviewed."

### E. The automated helpers (run outside the website)
- **OCR pipeline** (`work/ocr/`) — Gemini Flash reads text → `ocr_extractions`.
- **MapSAM2 pipeline** (`work/MapSAM2/`) — turns map tiles into building polygons →
  `footprint_submissions`, and can advance the pipeline status automatically.
> In the live cloud environment these heavy jobs can't run inside the website, so the relevant
> buttons return a copy-paste command to run locally instead.

---

## 6. Where the data lives (the database)

One PostgreSQL database (Supabase). The tables that matter:

| Table | Holds | Note |
|---|---|---|
| `maps` | The map catalogue | One row per map: title, dates, institution, image links, georeference link, `status` (`draft` / `public` / `featured`), and full descriptive fields. |
| `map_iiif_sources` | Multiple image sources per map | One is marked "primary." |
| `scout_candidates` | Maps auto-discovered from external libraries, awaiting review | `pending` → `approved`/`rejected` → `ingested`. |
| `footprint_submissions` | Traced/AI building & road shapes | `needs_review` → `submitted`/`rejected`. |
| `ocr_extractions` | Text boxes read off maps | Each has full-image pixel coordinates + a status. |
| `map_pipeline_status` | Where each map is in the lifecycle | The 8-stage track in §5. |
| `label_tasks`, `label_pins` | Point-labeling tasks and pins | |
| `annotation_sets` | User-drawn GeoJSON annotations | |
| `hunts`, `hunt_stops` | Stories / guided tours | Legacy table names; the app calls them "Stories." |

Database changes are tracked as numbered migration files in `supabase/migrations/`. **The
current head is `048_seed_walk_around_saigon`** (the auto-generated TypeScript types were last
regenerated from `047`, since `048` only seeds data).

Two status facts worth remembering (common mistakes):
- A map's `status` is only ever `draft` / `public` / `featured`. Older lifecycle words
  (`pending_georef`, `published`, …) are gone and will be rejected by the database.
- The image source type is `ia / bnf / efeo / gallica / rumsey / self / other` (plus `r2`).

---

## 7. How it's built and deployed

- **Framework:** SvelteKit 5 — but written in **legacy Svelte syntax** on purpose (`$:`,
  `export let`, `createEventDispatcher`, `$store`), *not* the new "runes." New code must match.
- **Maps:** OpenLayers is the main map engine (used by `MapShell` and the pixel-coordinate
  `ImageShell`); MapLibre GL is used only for lightweight embeds. Allmaps warps the historical
  images.
- **Database & auth:** Supabase (Postgres + Storage + Auth), project in Sydney.
- **Image hosting:** Cloudflare R2 + a small Worker serve mirrored map tiles; original scans
  are also pushed to the Internet Archive.
- **Hosting:** Cloudflare Pages. The build output is `.svelte-kit/cloudflare`.
- **Styling:** all CSS lives in `src/styles/`; two themes (neo-brutalist / archival) driven by
  design tokens, no per-component overrides.

---

## 8. What recently changed (so this doesn't drift again)

Verified against code 2026-06-04, correcting the older docs/memory:
- **`/explore` is the viewer** (not `/view`); **`/studio` is the drawing surface** (not
  `/annotate`). `/view` and `/annotate` are now 301 redirect stubs.
- **`LayerRenderer` + `layersStore`** own all map rendering; the old `HistoricalOverlay` trio
  is removed.
- New shared shell pieces exist: `MapWorkspace`, `MapModeOverlays`, `DrawTool`, `GpsTracker`.
- `/trip/[id]` (mobile tourist story player) and `/contribute` (hub) are real pages.
- New API endpoints since the last doc sweep: `…/ocr/apply`, `…/ocr-review/revert-recent`,
  `…/sync-georef`, `/api/admin/upload-image`.
- Migration head is **048**.
