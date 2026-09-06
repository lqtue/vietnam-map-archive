# VMA User Guide

The Vietnam Map Archive is an open platform for exploring, georeferencing, and digitizing historical maps of Saigon / Ho Chi Minh City. This guide is organised by role.

- **Explorer** — browse maps, stack overlays, play story tours.
- **Volunteer** — review OCR, trace footprints, georeference.
- **Researcher** — search the catalogue, inspect high-resolution IIIF, export GeoJSON.
- **Admin / Mod** — map metadata, pipelines, review queues.

---

## Route map

| Route | What it is |
|---|---|
| `/` | Home — featured maps, project overview |
| `/archive` | Full catalogue, search and filters |
| `/explore` | Main map viewer — layer stack, basemaps, stories |
| `/explore?mode=annotate` | Free-form annotation + timeline animation |
| `/explore?mode=story` | Story / adventure authoring |
| `/trip/[id]` | Story playback |
| `/scan?mode=inspect` | IIIF image inspector (no geo overlay) |
| `/about`, `/blog` | Project background and dev log |
| `/login`, `/profile` | Account and role badges |
| `/contribute` | Contribution hub — where the volunteer tools start |
| `/contribute#georef` | Georeference via the Allmaps editor |
| `/scan?mode=triage` | Triage + OCR review + segmentation review |
| `/scan?mode=trace` | Polygon / line tracing of footprints |
| `/scan?mode=review` | Moderator review of machine-generated footprints |
| `/admin?tab=bulk` | Bulk map upload |
| `/admin?tab=scout` | Review externally discovered map candidates |

**Legacy links.** `/view`, `/annotate`, and `/contribute/label` are 301 redirects to `/explore`, `/explore?mode=annotate`, and `/scan?mode=triage`. Old bookmarks keep working; query strings are preserved.

**There is no `/admin` route.** Map creation and editing live inline in `/archive` for signed-in `admin` and `mod` accounts, alongside the two dedicated pages above.

---

## 1. Explorer

1. **Browse** — start at `/archive`. Search by name, filter by region, type, period, source, and georeferencing status. Star a map to favourite it.
2. **Open** — clicking a map loads it as an overlay in `/explore`.
3. **Stack** — add up to 10 historical overlays. In the Layers panel, drag the row horizontally to change opacity, use ▲ / ▼ to reorder, and × to remove. Tapping a row zooms to that map.
4. **Choose a display mode** — in the Controls panel:
   - **Stacked** — overlays composited over the basemap (the default).
   - **Lens** — a circular window that reveals the layer beneath.
   - **Side-by-side** — two panes; the top overlay left, the next one right (top / bottom on mobile).
5. **Basemap** — Maps, Satellite, or None. "My location" turns on GPS following.
6. **Stories** — play curated tours; GPS-triggered points fire as you walk them.

**URL parameters:** `?map=<id>` loads a specific overlay (UUID or Allmaps ID); the hash `#@lat,lng,zoomz,rotationr&map=…&base=…` captures and restores the exact view, so a copied URL is a shareable position.

**Mobile:** the map is full-bleed with a three-tab bar at the bottom — Layers · Controls · Browse — each opening the same drawer.

---

## 2. Volunteer

Start at `/contribute`, which lists the tools and what each needs.

### Georeference — `/contribute#georef`
1. Open the map in the Allmaps editor via the button.
2. Place at least 3 ground control points on landmarks matching the modern basemap.
3. Copy the resulting annotation URL and share it with the team to record.

If the map has been mirrored to R2, use the **original source** IIIF manifest URL in Allmaps, not the internal storage URL.

### Digitalize — `/scan?mode=triage`
Three phases on one canvas, switched by the tabs at the top.

- **Triage** — drag the neatline rectangle to the map's active area (excluding decorative borders). Set tile size and overlap, or press **Suggest** for a fit based on the image dimensions. Click tiles to cycle their priority: normal → low-res (titles, legends) → skip (empty areas). Then set a run ID and start OCR.
- **OCR review** — click a bounding box on the canvas or a row in the sidebar. Correct the text, set the category, and validate or reject. Text edits save on blur; validate / reject sets the record's status. You can also draw a missing box by hand. Filter the sidebar by category, status, or search string.
- **Segmentation review** — the same canvas, showing machine-generated footprints for approval.

Changing the neatline or tile size resets manual tile-priority overrides.

### Trace — `/scan?mode=trace`
1. Choose **Polygon** for buildings and blocks, or **Line** for roads and waterways.
2. Click to place vertices; double-click to finish.
3. Name and categorise the shape in the sidebar table.

Submissions land in the review queue rather than going live directly.

### Review — `/scan?mode=review`
Moderator tool. Approve or reject submitted and needs-review footprints, adjusting geometry by dragging vertices. "Mark seg reviewed" advances the map's pipeline stage.

---

## 3. Researcher

- **Search** — `/archive` runs a full-text query across titles, institutions, and descriptions, with facets for institution, type, period, and source. Signed-in admins and mods also see scout candidates.
- **Compare across time** — stack several maps of the same area in `/explore` and switch between **Lens** and **Side-by-side** to read change.
- **Inspect the original** — `/scan?mode=inspect` is a plain IIIF viewer for reading fine detail without warping, with the full archival metadata (shelfmark, rights, holding institution).
- **Annotate and export** — `/explore?mode=annotate` draws points, lines, and polygons into named projects, with undo/redo and GeoJSON export for your own GIS.
- **Bulk data** — footprints are available through the export API.

---

## 4. Admin / Mod

Role comes from your profile; the tools appear only when your account carries `admin` or `mod`.

### Map management — inline in `/archive`
- Create a map from an Internet Archive item or a IIIF manifest; metadata is fetched and parsed automatically where the source supports it.
- The edit modal covers descriptive metadata, source and rights, hosting and georeferencing (IIIF sources, R2 mirror, neatline), and pipeline stage.
- Control visibility with the map's status: `draft`, `public`, or `featured`.

### Bulk upload — `/admin?tab=bulk`
Register many maps in one pass from a prepared list.

### Scout — `/admin?tab=scout`
Externally discovered map candidates, with approve / reject / ingest. Approved candidates become catalogue entries.

### Pipelines
Per-map stage runs `idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported`, visible on the digitalize page and advanced by the review tools.

- **OCR** — Gemini Flash over image tiles, writing bounding boxes and text.
- **Segmentation** — a fine-tuned SAM2 model producing candidate footprints for review.
- **Mirror to R2** — copies an external IIIF source to VMA's own storage for speed and long-term availability.

Command reference for both pipelines: `docs/pipelines.md`.

---

## Tips

- **"Run OCR" gives you a command, not a run.** In production there is no local process to invoke, so the button returns a CLI command — copy it and run it on a machine with the pipeline checked out.
- **Nothing in OCR review is destructive.** Rejecting sets a status; the extraction stays in the database.
- **A copied `/explore` URL is a copied view.** Position, zoom, rotation, active overlay, and basemap all live in the hash.
- **Your layer stack survives a reload** — it is stored in your browser, not your account.
