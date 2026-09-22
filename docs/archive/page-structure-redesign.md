# Page Structure & Module Redesign Plan

> Created: 2026-04-13. Reference document for the UI/IA restructure.
> Phases 1–4 are the current sprint. Phase 5 is a separate sprint.

## Context

The app has 16 routes with copy-pasted nav/footer, three separate catalog/admin interfaces, a
monolithic LabelStudio, and an AnnotateMode that bypasses MapShell entirely. This plan restructures
around **composable shells** and **four page types**: geo map viewer, image viewer, catalog,
editorial. Maximize module reuse; eliminate duplication.

---

## Audit findings driving this work

| Finding | Impact |
|---------|--------|
| Footer copy-pasted 6x with different links per page | Maintenance burden, inconsistent UX |
| Hero uses `.hero` on some pages, `.editorial-hero` on others | CSS confusion |
| NavBar scoped styles duplicate editorial.css (8 classes) | Style drift between nav and shared CSS |
| LabelStudio is 365-line monolith combining pin + trace + task mgmt | Can't reuse image viewer or individual tools |
| AnnotateMode uses StudioMap (own OL Map) instead of MapShell | Draw tools not pluggable into other modes |
| 3 separate catalog/admin routes with overlapping features | Users navigate 3 places to manage maps |
| Missing `--color-gray-400` token (used in 5+ files) | Broken styling |
| No `ssr = false` on tool pages using OL (browser-only) | Potential SSR crashes |
| No back navigation from tool pages (`/view`, `/create`, `/annotate`) | Users get stranded |

---

## Architecture: Three shared layers

### Layer 1: ToolLayout (RENAME from GeoMapShell)

`GeoMapShell.svelte` is already a pure layout component — zero map-specific logic. Rename to
`ToolLayout.svelte` and share across BOTH viewers.

**Provides:** sidebar + map/image stage + floating controls + mobile drawer + responsive
breakpoints.
**File:** `src/lib/map/shell/ToolLayout.svelte` (rename from `src/lib/map/shell/GeoMapShell.svelte`)
**Slots:** `sidebar`, `default` (main content), `floating`, `mobile-sidebar`

```
ToolLayout (shared responsive layout)
├── /view         → ToolLayout > MapShell > overlays
├── /create       → ToolLayout > MapShell > story editor
├── /annotate     → ToolLayout > StudioMap (Phase 5: MapShell + DrawTool)
├── /image        → ToolLayout > ImageShell (read-only)
├── /contribute/label → ToolLayout > ImageShell + PinTool
├── /contribute/trace → ToolLayout > ImageShell + TraceTool
```

All tool pages get the same sidebar collapse, mobile drawer, floating controls, and SearchPanel
pattern for free.

### Layer 2: ImageShell (NEW) — IIIF image viewer base

Extracted from `LabelCanvas.svelte` lines 467-537. Provides:
- OL Map in pixel coordinates (no projection)
- IIIF tile layer loading via `loadIIIFImage()`
- Vector layers: `pinLayer` (zIndex 10), `footprintLayer` (zIndex 5), `drawLayer` (zIndex 4)
- Zoom/pan controls
- Keyboard: Escape, Ctrl+Z undo last point, Enter finish drawing, Delete
- Y-axis negation (IIIF y+ down, OL y+ up) handled consistently
- Context exposed via `setImageShellContext()` for child tools

**File:** `src/lib/map/shell/ImageShell.svelte`
**Context:** `src/lib/map/shell/imageContext.ts`

```
ImageShell (base IIIF viewer)
  +-- PinTool overlay    -> /contribute/label
  +-- TraceTool overlay  -> /contribute/trace
  +-- (nothing)          -> /image (read-only)
```

### Layer 3: MapShell (EXISTING) — geo map viewer base

Already well-structured. Provides OL Map, basemap switching, bidirectional store sync, URL hash
sync. Context via `getShellContext()`. Children compose in slot.

**Current composability: ~50%.** AnnotateMode bypasses it via StudioMap.

```
MapShell (base geo viewer)
  +-- StoryPlayer + GpsTracker  -> /view
  +-- DrawTools (from StudioMap) -> /annotate  (Phase 5 refactor)
  +-- StoryEditor + MapClick    -> /create
```

### Shared search integration

`SearchPanel.svelte` and `MapSearchBar.svelte` already exist as reusable components. Both viewers
use them in the same position (top of map-stage, above the canvas). The search panel has two tabs
(Maps catalog search + Location geocoding). For image viewer pages, the Maps tab is the primary
entry point for selecting which map to view/label/trace. The panel emits events (`selectMap`,
`navigate`) — each page handles them appropriately.

---

## Proposed IA

### Nav (desktop) with dropdowns

```
VMA  |  Maps v  Contribute v  About  Blog  |  [avatar/signin] [VN] [theme]

Maps v:                          Contribute v:
+----------------------------+   +--------------------------------+
| Browse Catalog   /catalog  |   | Label Maps    /contribute/label|
| View on Map      /view     |   | Trace Maps    /contribute/trace|
| View Image       /image    |   | Georeference  /contribute/georef|
+----------------------------+   +--------------------------------+
```

**Mobile (<=640px):** Hamburger -> bottom-anchored drawer with flat section list.

### Route classification

**Editorial** (NavBar + footer from shared layout):
`/`, `/catalog`, `/about`, `/blog`, `/blog/[slug]`, `/contribute`, `/contribute/georef`, `/login`,
`/signup`, `/profile`

**App/tool** (fullscreen, no NavBar):
`/view`, `/image`, `/create`, `/annotate`, `/contribute/label`, `/contribute/trace`

**Merged routes** (features absorbed into unified `/catalog`):
- `/admin` — admin CRUD features moved to `/catalog` (role-gated, admin only)
- `/contribute/catalog` — Dublin Core metadata editing moved to `/catalog` (role-gated, mod+)

**Deprioritized routes** (kept but not in nav):
- `/contribute/review` — SAM2 review not working yet; route stays but hidden from nav until
  functional

**Auth pages note:** `/login` and `/signup` are in the `(editorial)` group, so they get NavBar from
the shared layout. This lets users navigate away from auth pages — the auth card renders below the
nav.

### Unified /catalog

Single route with role-based progressive disclosure:

| Role | Features |
|------|----------|
| Public | Browse, search, filter, sort, favorites |
| Mod+ | + "Edit" toggle -> inline Dublin Core metadata editing, completeness bar |
| Admin | + "New Map" button, delete, upload image, IIIF source mgmt, label config, featured toggle |

Reuses existing API routes (`/api/contribute/catalog/[mapId]` for mod edits, `/api/admin/maps/*` for
admin ops). Existing modals (`MapEditModal`, `MapUploadModal`) from `AdminDashboard` are imported
conditionally.

---

## Route group file tree

```
src/routes/
  +layout.svelte                  <- root (Supabase context, unchanged)
  +layout.server.ts               <- session load (unchanged)

  (editorial)/
    +layout.svelte                <- NEW: NavBar + slot + EditorialFooter
    +page.svelte                  -> /
    about/+page.svelte            -> /about
    blog/+page.svelte             -> /blog
    blog/[slug]/+page.svelte      -> /blog/[slug]
    catalog/+page.svelte          -> /catalog  (UNIFIED: browse + mod edit + admin)
    contribute/
      +page.svelte                -> /contribute (hub)
      georef/+page.svelte         -> /contribute/georef
    login/+page.svelte            -> /login
    signup/+page.svelte           -> /signup
    profile/+page.svelte          -> /profile (NEW)

  (app)/
    +layout.svelte                <- bare slot (no chrome)
    view/+page.svelte             -> /view
    image/+page.svelte            -> /image (NEW)
    create/+page.svelte           -> /create
    annotate/+page.svelte         -> /annotate
    contribute/
      label/+page.svelte          -> /contribute/label (PinTool on ImageShell)
      trace/+page.svelte          -> /contribute/trace (NEW: TraceTool on ImageShell)

  auth/callback/+server.ts        <- unchanged
  api/...                         <- unchanged
```

---

## Component inventory

### NEW components to create

| Component | Location | Purpose |
|-----------|----------|---------|
| `ToolLayout.svelte` | `src/lib/map/shell/` | RENAME from GeoMapShell — shared responsive layout for all tool pages |
| `ImageShell.svelte` | `src/lib/map/shell/` | IIIF OL viewer base (extracted from LabelCanvas) |
| `imageContext.ts` | `src/lib/map/shell/` | Context for ImageShell (map, sources, layers) |
| `PinTool.svelte` | `src/lib/features/contribute/pin/` | Pin draw interaction + PinSidebar |
| `PinSidebar.svelte` | `src/lib/features/contribute/pin/` | Legend selection, placed pins list |
| `TraceTool.svelte` | `src/lib/features/contribute/trace/` | Polygon/line draw + TraceSidebar |
| `TraceSidebar.svelte` | `src/lib/features/contribute/trace/` | Shapes table, type/category filters |
| `EditorialFooter.svelte` | `src/lib/ui/` | Single source of truth footer |
| `PageHero.svelte` | `src/lib/ui/` | Standardized hero (eyebrow, title, highlight, badges) |
| `NavDropdown.svelte` | `src/lib/ui/` | Reusable dropdown panel for NavBar |
| `(editorial)/+layout.svelte` | `src/routes/` | NavBar + slot + footer |
| `(app)/+layout.svelte` | `src/routes/` | Bare slot |
| `/image/+page.svelte` | `src/routes/(app)/` | Read-only IIIF viewer |
| `/contribute/trace/+page.svelte` | `src/routes/(app)/` | TraceTool page |
| `/profile/+page.svelte` | `src/routes/(editorial)/` | User profile |

### MODIFY existing components

| Component | Changes |
|-----------|---------|
| `NavBar.svelte` | Rewrite: dropdowns, hamburger, remove scoped style duplication |
| `catalog/+page.svelte` | Merge mod metadata editing + admin CRUD features (role-gated) |
| `contribute/label/+page.svelte` | Rewrite: ImageShell + PinTool (instead of LabelStudio) |
| `editorial.css` | Add dropdown/drawer CSS; unify `.footer`/`.editorial-footer` |
| `tokens.css` | Add `--color-gray-400`, `--nav-height` |
| All 6 editorial pages | Strip inline NavBar + footer (provided by layout) |

### DEPRECATE (keep until migration complete, then delete)

| Component | Replaced by |
|-----------|-------------|
| `GeoMapShell.svelte` | `ToolLayout.svelte` (rename + update all imports) |
| `LabelStudio.svelte` | ImageShell + PinTool / TraceTool orchestrators |
| `LabelCanvas.svelte` | ImageShell (IIIF loading) + tool-specific interactions |
| `LabelSidebar.svelte` | PinSidebar + TraceSidebar |
| `AdminDashboard.svelte` | Unified /catalog with admin features |
| `/contribute/catalog/+page.svelte` | Unified /catalog with mod features |
| `/admin/+page.svelte` | Unified /catalog with admin features |

### LEAVE ALONE (for now)

| Component | Reason |
|-----------|--------|
| `StudioMap.svelte` | AnnotateMode refactor is Phase 5 (separate sprint) |
| `ViewMode.svelte` | Already uses MapShell correctly |
| `CreateMode.svelte` | Already uses MapShell correctly |
| `ReviewMode.svelte` | Deprioritized (user says not working) |
| `MapCard.svelte` | Keep for home page; consolidation is separate |

---

## ImageShell decomposition detail

### What moves from LabelCanvas to ImageShell

| LabelCanvas lines | What | Goes to |
|-------------------|------|---------|
| 467-493 | `loadIIIFImage()` — IIIF fetch + tile layer | ImageShell |
| 495-537 | `onMount` — map init, vector sources, layers | ImageShell |
| 84-96 | Color palette for labels | ImageShell (shared) |
| 98-156 | `createPinStyle`, `createFootprintStyle`, `createSelectedStyle` | ImageShell |
| 165-177 | `syncPins()` reactive | ImageShell (receives pins as prop) |
| 179-214 | `syncFootprints()` reactive | ImageShell (receives footprints as prop) |
| 404-463 | Keyboard handling (Esc, Ctrl+Z, Enter, Delete) | ImageShell |

### What stays in tool-specific components

| LabelCanvas lines | What | Goes to |
|-------------------|------|---------|
| 250-303 | Draw interaction (polygon/line) + snap | TraceTool |
| 305-348 | Select + Modify interaction (footprint edit) | TraceTool |
| 351-401 | Pin-edit Select + Modify interaction | PinTool |
| 525-530 | Pin click handler (map click -> placePin) | PinTool |

### ImageShell props

```ts
export let iiifInfoUrl: string;         // IIIF info.json URL
export let pins: LabelPin[] = [];       // rendered on pin layer
export let footprints: FootprintSubmission[] = []; // rendered on footprint layer
export let myUserId: string | null = null;  // for ownership checks
// + exposes map, sources, layers via context
```

### ImageShell context

```ts
interface ImageShellContext {
  map: OlMap;
  pinSource: VectorSource;
  footprintSource: VectorSource;
  drawSource: VectorSource;       // temporary, for in-progress shapes
  pinLayer: VectorImageLayer;
  footprintLayer: VectorLayer;
}
```

Tools call `getImageShellContext()` and add their own OL interactions to the map.

### Map selection UX change (label/trace pages)

Currently LabelStudio has a custom task-based map picker (fetches `label_tasks`, cycles through
maps). The new label/trace pages use the shared `SearchPanel` instead — the same search used in
`/view` and `/create`. Users search for a map by name, then the page resolves its IIIF URL and loads
it.

**Task data** (legend items, categories, pin/footprint lists) is still fetched from `label_tasks` +
`label_pins` + `footprint_submissions` after a map is selected. The change is the map discovery
mechanism, not the data model.

---

## Unified /catalog detail

### Data loading strategy

```ts
onMount(async () => {
  // Always load public maps
  maps = await fetchMaps(supabase);

  // Check role
  if (session) {
    const { data } = await supabase.from('profiles').select('role').eq('id', session.user.id).single();
    role = data?.role;
  }

  // Admin gets extra fields (allmaps_id, source_type, iiif_*, etc.)
  if (role === 'admin') {
    maps = await fetchAdminMaps(supabase); // richer query
  }
});
```

### UI sections by role

```svelte
<!-- Always: search, filters, sort, view toggle -->
<CatalogHeader search={true} sort={true} viewToggle={true}>
  {#if role === 'admin'}
    <button on:click={openNewMapModal}>+ New Map</button>
  {/if}
  {#if role === 'admin' || role === 'mod'}
    <button on:click={() => editMode = !editMode}>
      {editMode ? 'Done' : 'Edit'}
    </button>
  {/if}
</CatalogHeader>

<!-- Card grid (always) -->
<CatalogGrid>
  {#each filteredMaps as map}
    <CatalogCard {map}>
      {#if editMode && (role === 'admin' || role === 'mod')}
        <!-- Inline metadata editor, completeness bar -->
      {/if}
      {#if role === 'admin'}
        <!-- Admin actions: edit all fields, delete, upload -->
      {/if}
    </CatalogCard>
  {/each}
</CatalogGrid>
```

### Existing modals to import

- `MapEditModal` from `src/lib/features/admin/` — full admin editing (6 tabs)
- `MapUploadModal` from `src/lib/features/admin/` — IA image upload + map creation

---

## Phased work order

### Phase 1: Foundation (nav, footer, hero, route groups)

| Step | What | Files |
|------|------|-------|
| 1.0 | Rename `GeoMapShell` -> `ToolLayout`, update all imports | `src/lib/map/shell/`, ViewMode, CreateMode, AnnotateMode |
| 1.1 | Fix `--color-gray-400` + add `--nav-height` | `tokens.css` |
| 1.2 | Create `EditorialFooter.svelte` | `src/lib/ui/EditorialFooter.svelte` |
| 1.3 | Create `PageHero.svelte` | `src/lib/ui/PageHero.svelte` |
| 1.4 | Rewrite `NavBar.svelte` (dropdowns + hamburger) | `NavBar.svelte`, `editorial.css` |
| 1.5 | Create `(editorial)/+layout.svelte` | new layout file |
| 1.6 | Create `(app)/+layout.svelte` | new layout file |
| 1.7 | Move editorial pages into `(editorial)/` | 10 file moves |
| 1.8 | Move app pages into `(app)/` | 7 file moves |
| 1.9 | Strip NavBar + footer from editorial pages | 6 pages |
| 1.10 | Replace inline heroes with `<PageHero>` | about, blog, contribute, georef |
| 1.11 | Update catalog top-bar sticky to `top: var(--nav-height)` | catalog page |

### Phase 2: ImageShell + /image page

| Step | What | Files |
|------|------|-------|
| 2.1 | Create `ImageShell.svelte` + `imageContext.ts` | `src/lib/map/shell/` |
| 2.2 | Add `iiif_image` to `MapListItem` type | `src/lib/data/maps/types.ts` |
| 2.3 | Create `/image` page (read-only IIIF viewer) | `src/routes/(app)/image/` |
| 2.4 | Update catalog card hrefs (georef -> /view, image -> /image) | catalog page |

### Phase 3: PinTool + TraceTool (decompose LabelStudio)

| Step | What | Files |
|------|------|-------|
| 3.1 | Create `PinTool.svelte` + `PinSidebar.svelte` | `src/lib/features/contribute/pin/` |
| 3.2 | Create `TraceTool.svelte` + `TraceSidebar.svelte` | `src/lib/features/contribute/trace/` |
| 3.3 | Rewrite `/contribute/label` to use ImageShell + PinTool | route page |
| 3.4 | Create `/contribute/trace` using ImageShell + TraceTool | new route page |
| 3.5 | Add SearchPanel to both label and trace pages | both route pages |
| 3.6 | Delete old LabelStudio/LabelCanvas/LabelSidebar | cleanup |

### Phase 4: Unified /catalog

| Step | What | Files |
|------|------|-------|
| 4.1 | Add role-gated edit toggle to catalog page | catalog page |
| 4.2 | Add inline Dublin Core editor (from contribute/catalog) | catalog page |
| 4.3 | Import MapEditModal + MapUploadModal for admin features | catalog page |
| 4.4 | Add completeness progress bar for mod+ view | catalog page |
| 4.5 | Delete `/contribute/catalog` and `/admin` routes | cleanup |
| 4.6 | Update nav dropdown links | NavBar |

### Phase 5: MapShell composability (separate sprint)

| Step | What | Files |
|------|------|-------|
| 5.1 | Extract draw tools from StudioMap into pluggable DrawTool | `src/lib/map/shell/DrawTool.svelte` |
| 5.2 | Rewrite AnnotateMode to use MapShell + DrawTool | `AnnotateMode.svelte` |
| 5.3 | Delete StudioMap | cleanup |

### Phase 6: Profile page + polish

| Step | What | Files |
|------|------|-------|
| 6.1 | Create `/profile` page | `src/routes/(editorial)/profile/` |
| 6.2 | Add `ssr = false` to all app/tool pages | each `+page.ts` |

---

## Key risks

| Risk | Mitigation |
|------|------------|
| LabelCanvas is 713 lines; extraction is complex | Extract ImageShell first as a clean new component, verify it works standalone at /image, then incrementally migrate tools |
| Catalog merge touches 3 routes + admin modals | Keep existing API routes unchanged; only merge the UI. Existing modals (`MapEditModal`) are imported, not rewritten |
| Route group migration may break `+page.ts` / `+page.server.ts` co-located files | Move all co-located files together (page, server, ts) |
| StudioMap refactor (Phase 5) is large | Explicitly deferred to separate sprint. AnnotateMode continues working as-is |
| Root layout uses Svelte 5 runes (`$props()`) | New layouts use legacy syntax to stay consistent with editorial pages |

---

## Verification

After each phase:
```bash
npm run check          # type-check
npm run dev            # dev server
```

### Phase 1 checks
- [ ] NavBar dropdowns open/close on click, Escape closes
- [ ] Mobile hamburger opens drawer with all links
- [ ] All editorial pages show NavBar + footer from layout (not inline)
- [ ] Tool pages have no NavBar/footer
- [ ] `/catalog` top-bar sits below NavBar correctly

### Phase 2 checks
- [ ] `/image?map=<id>` loads IIIF tiles and displays zoom controls
- [ ] "View on Map" button appears when map has allmaps_id
- [ ] Catalog cards link to correct viewer based on georef status

### Phase 3 checks
- [ ] `/contribute/label` loads map via search, places pins with legend selection
- [ ] `/contribute/trace` loads map via search, draws polygons/lines with category
- [ ] Both pages share the same ImageShell (same OL + IIIF behavior)
- [ ] Keyboard shortcuts work (Ctrl+Z, Enter, Escape, Delete)

### Phase 4 checks
- [ ] `/catalog` shows browse view for public users
- [ ] Mod users see "Edit" toggle, can edit Dublin Core fields inline
- [ ] Admin users see "+ New Map", can delete, manage IIIF sources
- [ ] `/admin` and `/contribute/catalog` are removed

### Phase 6 checks
- [ ] `/profile` shows avatar + stats when signed in
- [ ] `/profile` redirects to `/login` when not signed in
