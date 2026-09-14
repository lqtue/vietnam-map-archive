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
| `/catalog` | Full catalogue, search and filters |
| `/explore` | Main map viewer — layer stack, basemaps, stories |
| `/explore?mode=annotate` | Free-form annotation + timeline animation |
| `/explore?mode=story` | Story / adventure authoring |
| `/trip/[id]` | Story playback |
| `/catalog/[id]` | One sheet: its record, and the scan itself at full resolution |
| `/about`, `/blog` | Project background and dev log |
| `/login`, `/profile` | Account and role badges |
| `/contribute` | Contribution hub — where the volunteer tools start |
| `/contribute/georef` | Georeference via the Allmaps editor |
| `/scan?mode=prepare` | Crop the sheet and queue the reading |
| `/scan?mode=text` | Check what was read: Names · Index · Numbers · Other |
| `/scan?mode=shapes` | Draw · Segment · Validate |
| `/admin?tab=bulk` | Bulk map upload |
| `/admin?tab=scout` | Review externally discovered map candidates |

**Legacy links.** `/view`, `/annotate`, and `/contribute/digitalize` are 301 redirects to `/explore`, `/explore?mode=annotate`, and `/scan?mode=prepare`. Old bookmarks keep working; query strings are preserved.

**`/admin` is the staff console** — one page, tab chosen by `?tab=bulk|scout|status|stories`. Map creation and editing are separate: they live inline in `/catalog` for signed-in `admin` and `mod` accounts.

---

## 1. Explorer

1. **Browse** — start at `/catalog`. Search by name, filter by region, type, period, source, and georeferencing status. Star a map to favourite it.
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

### Georeference — `/contribute/georef`
1. Open the map in the Allmaps editor via the button.
2. Place at least 3 ground control points on landmarks matching the modern basemap.
3. Copy the resulting annotation URL and share it with the team to record.

If the map has been mirrored to R2, use the **original source** IIIF manifest URL in Allmaps, not the internal storage URL.

### Prepare — `/scan?mode=prepare`
Five steps down the right-hand panel, on one canvas.

**Detect** asks the model what the sheet is made of — where the map itself is, and where the title block, legend and name lists are printed. Then check the neatline it proposes (drag it if it is wrong), set tile size and overlap, click tiles to cycle their priority (normal → low-res for titles and legends → skip for empty paper), press **Save triage** to accept, and **Run OCR** to queue the reading. Nothing runs until a worker picks the job up.

Changing the neatline or tile size resets manual tile-priority overrides.

### Text — `/scan?mode=text`
What came back, in four jobs — the tabs at the foot of the panel, each showing how many rows it holds. Clearing all four clears the sheet.

- **Names** — the names printed on the map itself: streets, places, water, institutions.
- **Index** — the sheet's own printed tables, the numbered legend and the name list. The canvas frames the table and the rows beside it *are* the table, ordered the way the paper orders them.
- **Numbers** — the numerals printed on the map, against the index that explains them. The **suspect** chip is the ones the index contradicts: not a number, a number the index does not list, or one claimed twice.
- **Other** — title block, scale bar, stamp, anything off the sheet.

Click a box on the canvas or a row in the panel. Correct the text, set the category, validate or reject. Text edits save on blur. You can draw a missing box by hand. `j`/`k` step, `v` validates, `x` rejects, `e` edits.

### Shapes — `/scan?mode=shapes`
Three tabs over one sheet: draw a few by hand, let the model do the rest, check what it did.

- **Draw** — choose **Polygon** for buildings and blocks or **Line** for roads and waterways, click to place vertices, double-click to finish, then name and categorise it in the panel. Submissions land in the review queue rather than going live.
- **Segment** — the sheet's pipeline stage and the MapSAM2 command to run on a GPU elsewhere. This tab starts nothing itself.
- **Validate** — moderator tool. Approve or reject what the model drew, adjusting geometry by dragging vertices; the edit is sent with the verdict. "Mark seg reviewed" advances the map's pipeline stage.

---

## 3. Researcher

- **Search** — `/catalog` runs a full-text query across titles, institutions, and descriptions, with facets for institution, type, period, and source. Signed-in admins and mods also see scout candidates.
- **Compare across time** — stack several maps of the same area in `/explore` and switch between **Lens** and **Side-by-side** to read change.
- **Inspect the original** — `/scan` is a plain IIIF viewer for reading fine detail without warping, with the full archival metadata (shelfmark, rights, holding institution).
- **Annotate and export** — `/explore?mode=annotate` draws points, lines, and polygons into named projects, with undo/redo and GeoJSON export for your own GIS.
- **Bulk data** — footprints are available through the export API.

---

## 4. Admin / Mod

Role comes from your profile; the tools appear only when your account carries `admin` or `mod`.

### Map management — inline in `/catalog`
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
