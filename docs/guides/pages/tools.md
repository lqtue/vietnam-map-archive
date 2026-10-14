# Tool register and admin — page specs

Scope: `/explore` (3 modes), `/scan` (5 modes), `/trip/[id]`, `/admin` (4 tabs). Read-only audit of the code at `main` (727bec39), 2026-10-14. "unverified" = read from code, not run.

Shared frame for every `(app)` page: `src/routes/(app)/+layout.svelte` (9 lines) mounts `NavBar` and a `<slot />`. There is no mode strip; mode switching lives in NavBar (explore) and the left-rail footer (scan). `/explore` and `/scan` have `ssr = false`. `/trip/[id]` has no `+page.ts`, so it is not marked `ssr = false` (it renders only a spinner on the server; see Findings there).

---

### `/explore` — MapShell dispatcher
Files: `src/routes/(app)/explore/+page.svelte` (51), `+page.ts` (1); `src/lib/core/routeModes.ts` (`resolveExploreMode`, `ADMIN_TABS`)
- **For / job:** every reader of the map tools; picks one of three modes by `?mode=`.
- **Access:** public dispatcher. Each mode applies its own gate (see below).
- **Data:** reads `$page.url.searchParams.mode`; sets `<title>`/description for studio and story. Browse owns its own head.
- **Requirements:**
  - `browse` (default), `studio`, `story`; `annotate` is an alias of `studio` (`routeModes.ts:10`).
  - A missing mode means browse; `resolveExploreMode` returns `null` for a typo, and the dispatcher falls back to browse with `?? 'browse'` (`+page.svelte:30`). `hooks.server.ts:89` repairs the typo on a cold request.
  - One MapShell stays warm across a mode switch (stated goal in the file header).
- **Layout:** each mode root is `position: fixed; inset: var(--nav-height) 0 0 0`, so no strip can sit beside it.
- **Interaction:** none of its own.
- **i18n · a11y · mobile:** n/a.
- **Findings:** none. (`routeModes.ts:16` doc says "null means a misspelling, not Browse" but the dispatcher turns it into Browse; harmless because the server hook redirects first.)

### `/explore?mode=browse` — Browse maps, play stories
Files: `src/lib/features/explore/ExplorePage.svelte` (677); `ExploreSidebar` (201), `ExploreRightSidebar` (274), `ExploreBrowsePanel` (363), `ExploreTour` (300), `ExplorePrivacyNotice` (234), `PressPanel` (393), `ExploreMapContextMenu` (190), `exploreUrl.ts` (149), `exploreKeys.ts` (45); shell `src/lib/map/shell/MapWorkspace.svelte` (207) + `ToolLayout.svelte` (337) + `MapShell.svelte` (254)
- **For / job:** reader who wants to lay one or more historical sheets over today's map, step through years, read a legend, or walk a story.
- **Access:** public. Staff (`admin`/`mod`, from `fetchUserRole`) also see draft maps in coverage and browse; staff opens are not tallied (`exploreUrl.ts` `tallyMapOpen`).
- **Data:** stores `layersStore` (persisted `vma-layers-v1`), `mapStore`, `layerStore`, `createStoryPlayerStore` (localStorage `vma-story-player-v1`). Reads `maps` (via `fetchMaps`, `fetchMapsByIds`, `fetchSeriesSheets`, `map_series`), `stories` (`fetchPublicStories`, approved only), `/api/search` (via `createCatalogSearch`), `/api/maps/[id]/legend-points`, `/api/export/footprints`, `/api/press`. Writes: `POST /api/maps/[id]/open` (open tally, non-staff only), `trackMeasurement('map_open')`. localStorage `vma-explore-welcome-ack-v1`, `vma-explore-tour-ack-v1`. No pipeline jobs.
- **Requirements:**
  - Stack many sheets as overlays; tap a row to add, tap again to remove (`handlePickMap`, "never clears").
  - Deeplinks `?map=<slug|uuid|allmaps id>`, `?at=lng,lat`, `?story=`, `?series=`; `#@lat,lng,zoomz` camera hash wins over the default Saigon view. Own writes use `pushState` and mark themselves applied (`appliedUrl`).
  - Deeplinks skip the welcome chooser; otherwise the chooser offers "Use my location" or "Show all maps", and the choice persists.
  - Keyboard time scrubber on the top sheet (see Interaction).
  - Right rail describes the top sheet: Info · Legend · Control; legend pins and traced footprints can be drawn on the map; paired sheets (two halves of one plan) share one legend.
  - Click a label hit: stack its map, fly to the spot, pulse it, open the press panel for the place and year.
  - Side-by-side view (`viewMode === 'dual'`) via `DualMapPane`.
- **Layout:** MapWorkspace -> ToolLayout (left `ExploreSidebar`, right `ExploreRightSidebar`, drag-resizable, collapsible) -> MapShell -> `LayerRenderer`. Overlays: `ExploreSheet` (no coverage at your spot), loading chip, GPS error, floating `PressPanel`. Left rail: `sb-bar` title, `ArchiveFilters`, `Tabs` All / Picked N, `SidebarCard`. Right rail: same frame, `PlaceSearchBar`, "My location" toggle, Tabs Info / Legend / Control.
- **Interaction:** URL `?map ?at ?story ?series`. Keys (window `keydown`, ignored in inputs and with ctrl/meta/alt): Left / Right = previous / next sheet by year (keeps camera, keeps opacity); Up / Down = top sheet opacity +/- 0.1; Escape = clear focus pulse and lit legend row. Right-click on map = context menu (Escape closes; focus returns). Welcome chooser, guided tour (driver.js) for first visit. States: loading chip ("Looking up maps at your location…" / "Loading archive…"), empty (`ExploreSheet` + "Jump to Saigon"), GPS error (`role="alert"`), no unsaved state. Mobile (< 900px): `MobileDrawerStack` with Browse / Layers / Controls drawers.
- **i18n · a11y · mobile:** `$t()` used for most labels, but not all: "Explore", "Collapse panel", "Hide panel", "GPS on", "My location", "This series", "Show this sheet on the map" and the whole privacy list are raw English (`ExploreSidebar:136`, `ExploreRightSidebar` bar/GPS/series block, `ExplorePrivacyNotice:62-65`). Tabs have `role="tablist"`; welcome modal has `role="dialog" aria-modal` and `aria-labelledby`; context menu restores focus. Welcome modal has no Escape handler and no focus trap (unverified). `viewport` meta sets `maximum-scale=1` (blocks pinch zoom of the page; map still zooms).
- **Findings:**
  - `ExplorePage.svelte` is 677 lines; the Svelte skill lists it at 560 and says "do not add to that list". It also grew past the other eight.
  - `$:` blocks that write state: `ExplorePage:200-203` (sets `choseMode`, `mode`), `:187` (`showLegendPoints`), `:249-252` (`matches`, `loading`), `:267-273` (`tourPending`, `tourOpen`), `:231-242` (writes `appliedUrl`, queues a microtask). The file explains the microtask, but this is the effect-writing-state shape the skill forbids.
  - `ExplorePage:366-400`: arrow keys call `preventDefault` on window, while OL's default `KeyboardPan` / `KeyboardZoom` (`MapShell:157` uses `defaultInteractions`) also bind arrows when the map has focus. Which wins is unverified.
  - `ExplorePrivacyNotice:108` hardcoded `rgba(20,20,20,.45)` scrim (use a token or `color-mix`).
  - `ExploreSidebar:197-201` empty `<style>` block holding only a comment.
  - Hero demo files (`heroFabric.ts` 1231, `HeroDemo`, `HeroMap`, `HeroSequence`) sit in `features/explore/` but belong to the home page, not this surface. Folder boundary is blurred.

### `/explore?mode=studio` — Studio (free-form annotation + timeline animation; alias `annotate`)
Files: `src/lib/features/annotate/AnnotateMode.svelte` (500); `AnnotateRightPane` (226), `AnnotateAnnotationList` (335), `AnnotateAnnotationInspector` (151), `AnnotateAnimationPanel` (412), `AnnotateProjectHeader` (97), `AnnotateOverpassController` (213) + `AnnotateOverpassDialog` (381) + `overpass.ts` (183), `annotationProjectStore.ts` (122), `animation/{playback,timelineStore}.ts`, `map/shell/DrawTool.svelte` (343), shared `MapViewerSidebar`
- **For / job:** signed-in contributor who draws points, lines and polygons on historical sheets, imports OSM data, keys camera frames into an animation, and exports GeoJSON.
- **Access:** signed-in. Signed out sees `AuthGate` ("Sign in to annotate"). A user sees only their own projects (`authorId === userId`, `AnnotateMode:68`).
- **Data:** table `user_layers` (select / insert / update / delete via `data/supabase/annotations.ts`; `mapIds` rides inside the `features` jsonb); localStorage `vma-annotation-projects-v1` (debounced 300 ms cache). Reads `maps`, `/api/maps/[id]/legend-points`, `/api/export/footprints`; Overpass API from the browser (`overpass.ts`); `trackMeasurement` events. No pipeline jobs.
- **Requirements:**
  - Library view (`LibraryGrid`: create, rename, delete, open) and editor view (`activeView`).
  - Draw point / line / polygon; select, rename, recolour, hide, delete, zoom to; undo / redo (100 steps); clear all; GeoJSON import and export; OSM import by bbox.
  - Save is explicit: Save button writes features plus the sheet stack to `user_layers`; failure shows `STUDIO_SAVE_FAILURE`.
  - Restore the project's saved sheet stack once the catalog loads (`handleMapsLoaded`).
  - Keyframe timeline: add from camera, reorder, edit, jump, play / stop with flyTo.
  - Dual view is refused (snaps back to overlay).
- **Layout:** MapWorkspace. Left `MapViewerSidebar` (Layers · Browse; Controls hidden because the right rail has one). Right `AnnotateRightPane`: `sb-bar` "Studio", `AnnotateProjectHeader` (back, inline rename, map name, dot, Save), Tabs Annotate / Animate / Control / Legend / Info. Map children: `DrawTool`, `BboxSelector`, `OverpassPreviewLayer`, legend and footprint layers.
- **Interaction:** URL `?mode=studio` only (no project id in the URL; reload returns to the library). Keys (window `keydown`, ignored in inputs): Ctrl/Cmd+Z undo; Ctrl/Cmd+Shift+Z or Ctrl/Cmd+Y redo. `Escape` in the Overpass dialog closes it unless fetching. Leaving the Annotate tab cancels the active draw mode. States: library loading, empty library CTA, saving (`...`), saved (2 s "Saved"), notice line (info / success / error), no unsaved-changes guard (no `beforeunload`). Mobile: the doc says the editor is desktop-only, but no gate exists (see Findings).
- **i18n · a11y · mobile:** Almost no `$t()`: only the "Studio" title. Tab labels, AuthGate copy, library copy, notices ("All annotations cleared.", "GeoJSON downloaded.") are English-only. Collapse button has `aria-label` (English). Project strip uses `aria-label="Back to library"`.
- **Findings:**
  - Probable save bug: `annotationProjectStore.createProject` (`:34-70`, id swap at `:62`) swaps the local id for the database id after the insert returns, but `AnnotateMode.handleLibraryCreate` (`:280-291`) copied the project 50 ms earlier and keeps the old id in `currentProject`. `handleSave` then updates a row that does not exist and `updateAnnotationSet` returns false (`annotations.ts`: `data?.id === id`), so a brand-new project shows the save-failure notice until reopened from the library. Unverified by running.
  - `AnnotateProjectHeader:46-48` the dot has class `sh-autosave` and the file header calls it an "autosave dot", but nothing autosaves; it shows `•` until Save. Misleading.
  - Race timers not cleared on destroy: `AnnotateMode:204` (2 s), `:265-271` (500 ms import of saved features), `:283-290` (50 ms).
  - `annotationProjectStore.ts:32` `loadFromSupabase()` runs at store creation and again in `onMount` (`AnnotateMode:321`): double fetch. It replaces the cache only when the server has rows (`projects.length > 0`), so a project deleted on another device returns from the local cache (unverified).
  - `deleteProject` / `updateProject` ignore the returned promise: a failed remote write is silent.
  - `AnnotateMode:8` "Mobile is intentionally unsupported" is not enforced: `isMobile` is never read, and the file fills no `mobile-*` slot. Because `MapWorkspace` always forwards all four mobile slots, `ToolLayout`'s two-rail auto split (`splitRailsOnMobile`) likely never fires, so the three phone drawers are probably empty (unverified). `CreateMode` handles it; Studio does not.
  - `AnnotateMode:373` `thumbIcon="📝"` is an emoji in chrome (design system allows glyphs only where they are the content).
  - Raw rgba in canvas styles: `BboxSelector.svelte:39`, `OverpassPreviewLayer.svelte:25,28` (should come from `INK`).
  - `AnnotateMode.svelte` 500 lines (at the edge); `AnnotateAnimationPanel` 412, `AnnotateOverpassDialog` 381 are large for one panel.

### `/explore?mode=story` — Story editor (author guided walks)
Files: `src/lib/features/stories/editor/CreateMode.svelte` (588); `CreateRightPane` (135), `StoryHeaderPanel` (81), `StoryPointsPanel` (216), `PointInspector` (173), `ChallengeConfig` (99), `MapClickCapture` (46), `saigonSeed.ts` (138); shared `stories/shared/{storyStore,pointOps,previewSession,StoryPlayback,StoryMarkers}`, `MapViewerSidebar`
- **For / job:** signed-in author who drops points on a historical map, writes a stop per point, adds a question or "reach" challenge, previews, and submits for review.
- **Access:** signed-in (`AuthGate` "Sign in to build a story"). Mobile users get the library only; tapping a story opens `/explore?story=<id>`.
- **Data:** localStorage `vma-story-library-v1` (the real draft store; `loadFromSupabase` is an empty stub, `storyStore.ts:94`); on Publish: upsert `stories` then delete + insert `story_points` (`syncStoryToSupabase`, `data/supabase/stories.ts:88`). Reads the georeferenced catalog (`fetchGeoreferencedMaps`). Review status values `draft | submitted | approved | rejected` (mig 059); a mod approves in `/admin?tab=stories`.
- **Requirements:**
  - Library (create / rename / delete / open / "Walk" link) then editor.
  - Place mode (many clicks in a row), Move mode, reorder (up / down buttons), remove, zoom to point, undo last point.
  - Each point pins to the top historical overlay when created (`overlayMapId`), has radius (default 15 m), optional challenge.
  - Preview plays the story in the editor with `StoryPlayback`.
  - "Publish" means "submit for review"; withdraw and unpublish go back to draft. Auto-seeds a Saigon example once per seed version.
  - Drafts auto-persist to localStorage on every change.
- **Layout:** MapWorkspace. Left `MapViewerSidebar`. Right `CreateRightPane`: `sb-bar` with "← Library" + title "Story editor" + collapse; three `SidebarCard`s: header (rename + status button), Points, Point editor. Map children: `MapClickCapture`, `StoryMarkers`, `StoryPlayback`.
- **Interaction:** URL `?mode=story` only (editor state not in URL). Keys (window, ignored in inputs): Ctrl/Cmd+Z = undo last point; Escape = deselect point, else leave Place mode, else leave Move mode. States: library loading, empty (desktop and mobile variants), publishing / success (2 s), mobile banner "Editing is desktop-only".
- **i18n · a11y · mobile:** English-only (no `$t`). `aria-label` on move / remove buttons; `role=` on dialogs not checked. Mobile drawers are filled (layers, controls, browse) but the story panel is not reachable on a phone by design.
- **Findings:**
  - `CreateMode.svelte` is 588 lines, on the skill's "over 500" list.
  - `$:` that writes state or runs side effects: `:112` (`selectedPointId = null`), `:117` (`persistDraft` updates a store), `:132-135` (seed). The skill says `$:` computes only.
  - `StoryHeaderPanel:45` the badge is a fixed `Saved` / "Saves as you type": it never changes, and "saved" only means localStorage; the server copy is written only on Publish. The library does not reload from Supabase, so drafts exist on one browser only and publish is the only backup.
  - `CreateMode:227-230` if `syncStoryToSupabase` fails the button just stops spinning; no message.
  - `storyStore.ts:1-2` header says the story tables were dropped (mig 034) and sync is off; `stories` / `story_points` are used today. Stale comment.
  - `storyLibrary.deleteStory` removes only the local copy (`CreateMode:387`); an approved story stays public on the server. Unverified whether a delete route exists elsewhere.
  - Library "Walk" link (`:429`) appears for any story with points, including never-published drafts that `/trip/[id]` cannot load.
  - `thumbIcon="📖"` emoji (`:374`). Sync of points is delete + insert with no transaction (`stories.ts:105-126`): a failed insert leaves the story with zero points.

---
### `/trip/[id]` — Story playback (phone walk)
Files: `src/routes/(app)/trip/[id]/+page.svelte` (394); `src/lib/features/stories/play/{TripIntro (142), TripPlayback (431), TripComplete (140), TripItinerary (103), tripTracking.ts (63)}`; shared `stories/shared/{storyStore, playbackState, applyPoint, StoryMarkers}`, `ui/SnapSheet.svelte` (157), `map/shell/GpsTracker.svelte` (174)
- **For / job:** a visitor, often a tourist who scanned a QR code, who walks a story stop by stop with GPS check-in.
- **Access:** public for stories the database lets them read (`fetchStoryById`, RLS decides; a draft that was never published is not found). No login needed; login is offered at the end.
- **Data:** reads `stories` + `story_points` by id, and the full `maps` list (`fetchMaps`) to pin overlays. Writes only localStorage `vma-story-player-v1` (progress per story). Browser geolocation. No server writes.
- **Requirements:**
  - Cold load shows `TripIntro` (Start; Resume / Restart if progress exists); a finished trip skips the intro.
  - Ask for location before dismissing the intro; on denied or unavailable, the trip still works with manual "Mark visited".
  - GPS inside the stop's trigger radius auto-marks it visited; the user taps Next to advance (no auto-advance).
  - Per-stop card: description, hint, optional question (text answer, wrong / right banner) or "reach" challenge; map reframes and the stop's historical overlay swaps in when the stop changes.
  - Shows live distance and compass direction to the stop; estimated duration = 4 km/h + 4 min per stop.
  - `TripComplete`: stops, metres walked, minutes; Share, Done, "Save your trip" (login).
- **Layout:** fixed layer below NavBar (`top: 56px`), a MapShell with `LayerRenderer`, `GpsTracker`, `StoryMarkers`; `SnapSheet` bottom sheet (peek / mid / full) holds the player; `TripIntro` is a modal scrim; a round GPS toggle top-right.
- **Interaction:** URL `/trip/[id]` only. No keyboard shortcuts. States: loading (spinner + "Loading your trip…"), error ("Trip unavailable" + "← Back to maps"), GPS error banner (`role="alert"`), intro, playing, finished. No unsaved state. Mobile is the primary target.
- **i18n · a11y · mobile:** Mixed: `$t()` on most player strings, raw English in `TripIntro` ("Restart"), `TripComplete` ("Done"), `TripPlayback` ("Reach", "Walk within…", "Tap Next…") and in the page's error strings and GPS messages (`+page.svelte:132,147`). `SnapSheet` has `label` and `toggleLabel`. Intro has `role="dialog" aria-modal`. Viewport meta sets `maximum-scale=1` (`:228`), which blocks pinch zoom for low-vision users.
- **Findings:**
  - `storyStore.ts:94,219` `loadFromSupabase` is an empty stub, so progress never leaves the device. `handleSave` (`+page.svelte:118-122`) only redirects to `/login?next=`; "Save your trip / Log in to keep this on your profile" (`TripComplete:70`) promises something nothing implements.
  - `+page.svelte:115-117` `handleShare` is a no-op stub with a comment; the `on:share` handler is dead.
  - Design-system breaks: custom `.back-btn` and `.gps-toggle` buttons (`:340`, `:355`) instead of `.btn`; emoji in chrome `📍` / `⊘` (`:299`); hardcoded `top: 56px` instead of `--nav-height` (`:313`); page-scoped `box-shadow: 3px 3px 0` (ends in `var(--shadow-ink)`, allowed). `.gps-toggle` is a 44px round control while the system's round control is `.btn.is-icon`.
  - `(app)` is documented as `ssr = false`, but only `explore/+page.ts` and `scan/+page.ts` set it; `/trip/[id]` has no `+page.ts`. It loads data in `onMount` so the server only renders the spinner. Unverified: the root layout may already set it.
  - Load order is serial: `fetchMaps` (whole catalogue) then `fetchStoryById` (`:214-221`). The story could load in parallel and the map list only matters once the first overlay applies.
  - `elapsedMinutes` (`TripPlayback`) uses `Date.now()` inside `$:`, so it is not reactive to time and can show a stale value at completion until a store change.
  - `isLoggedIn` is read once from context (`:53`); signing in elsewhere does not update it. Documented in the file.

---
### `/scan` — ImageShell dispatcher
Files: `src/routes/(app)/scan/+page.svelte` (63), `+page.ts` (1); `src/lib/core/scanModes.ts` (`SCAN_MODES`, `resolveScanMode`, `CONTRIBUTE_TOOLS`, `toolHref`); redirect copy in `src/hooks.server.ts:76`
- **For / job:** routes a request to one of five pixel-canvas tools by `?mode=`. Has no mode of its own.
- **Access:** public dispatcher. No role gate here or in any mode component (see Findings); gates sit in the API.
- **Data:** reads `?mode`, `?map`, `?kind`.
- **Requirements:**
  - Modes: `inspect`, `prepare`, `text`, `shapes`, `legend`. Aliases kept: `triage`->prepare, `ocr`->text, `trace` and `review`->shapes (`scanModes.ts:26`).
  - No mode, or an unknown mode, redirects to `/catalog` (carrying `?map=` as `/catalog/<id>`): server hook on a cold request, `goto` on client navigation.
  - `?mode=review&kind=stories` redirects to `/admin?tab=stories`.
  - `prepare` and `text` share one `DigitalizePage` instance, so moving between them keeps the canvas, tile source and open sheet.
- **Layout:** each mode root builds `ToolLayout` + `ImageShell`; no mode strip (switcher lives in the left rail footer, shapes tabs in the right rail footer).
- **Interaction:** URL `?mode ?map ?tab`. No keys at this level.
- **i18n · a11y · mobile:** n/a. Tools pass `tabOrder={['browse','controls']}`; with both rails filled `ToolLayout` splits them into two drawers on phones (`splitRailsOnMobile`).
- **Findings:**
  - `+page.svelte:44-46` a `$:` statement calls `goto()` (side effect in a reactive statement; no cleanup issue, but the skill says `$:` computes only).
  - File header says "Each mode owns its own role gate"; none does (grep for `role`, `AuthGate`, `session` in `features/contribute` finds only `ShapesPage` reading the user id). A signed-out visitor sees a full tool that fails on first API call.
  - The mode list exists twice: `scanModes.ts` and a local `SCAN_MODES` array in `ScanLeftRail.svelte:54` (3 entries, no `legend`). They can drift; `legend` is intentionally absent from the switcher but it is undocumented there.

### `/scan?mode=inspect` — Image viewer (unlisted)
Files: `src/lib/features/contribute/inspect/InspectPage.svelte` (157); `shared/ScanLeftRail.svelte` (167), `shared/ToolMapPicker.svelte` (120); `map/shell/ImageShell.svelte` (285)
- **For / job:** anyone with the URL who wants a plain look at a scan, mainly a draft that has no `/catalog/[id]` page. Nothing links here.
- **Access:** no gate in the page. The map list comes from `fetchMaps(includeArchived: true)` over the browser Supabase client, so what a visitor sees is what RLS allows.
- **Data:** reads `maps` via `fetchMaps`; IIIF `info.json` from `maps.iiif_image`. Writes nothing.
- **Requirements:**
  - Pick a sheet from the left rail; `?map=<uuid>` pre-selects it.
  - Only sheets with an IIIF image are listed; georeferencing is not required (`requireGeoref={false}`).
  - Show the scan with an opacity slider; links "Open on map" (if `georef_done`) and "Studio".
- **Layout:** `ToolLayout` with the left rail only; no right sidebar; no mode switcher (`mode` unset on purpose).
- **Interaction:** URL `?map`. No keys. States: loading spinner in `ImageShell`; empty stage; error line "Couldn't load the map list: ...". No saving. Mobile: one browse drawer.
- **i18n · a11y · mobile:** English only (0 `$t`). The two links use a page-local `.inspect-link` class.
- **Findings:**
  - `InspectPage:105-111,138-153` custom `.inspect-link` / `.primary` links styled as buttons instead of `.btn` (design system: never rebuild the button).
  - Title is "Image viewer" / "<name> — scan" while sibling modes use the tool name; fine but inconsistent.
  - Drafts: `includeArchived: true` plus RLS means draft access depends entirely on RLS, not on a role check in the UI. Comment on `ExploreBrowsePanel` notes the map list "leaks drafts" through RLS (unverified at database level).

### `/scan?mode=prepare` — Layout · neatline · tile grid · save · queue OCR
Files: `src/lib/features/contribute/digitalize/DigitalizePage.svelte` (668, shared with `text`); `DigitalizeSidebar` (111), `TriageSidebar` (210) + `TriageLayoutStep` (240), `TriageCropStep` (144), `TriageTilesStep` (172), `TriageRunStep` (139); `TriageTool` (284), `RegionsTool` (301), `DigitalizeBottomBar` (165), `triagePrefs.ts` (123), `layoutJob.ts` (106), `suggestTriage.ts` (257)
- **For / job:** a volunteer or staff member who checks the model's proposed layout and crop for a sheet, accepts it, then queues OCR. Guide: `docs/guides/digitalize-guide.md`.
- **Access:** page open to all; every API it calls needs a session (`requireRole`; triage POST and the accept stamp need admin / mod). A worker must be running for Detect and Run OCR to do anything.
- **Data:** `fetchLabelMaps` (sheet list with triage and OCR badges); `GET/POST /api/admin/maps/[id]/layout` (enqueue + poll a `layout` job); `POST /api/admin/maps/[id]/triage` (writes `maps.triage`, stamps `validated_at`, `validated_by`, `neatline_src: 'human'`); `GET/POST /api/admin/maps/[id]/ocr` (run list; enqueue an `ocr` job); localStorage draft of the triage per sheet (`triagePrefs`). Pipeline jobs: `layout`, `ocr`.
- **Requirements:**
  - Sheet arrives pre-proposed (layout job adopts `main_map` as the neatline); the sidebar says Proposed vs Accepted (`triageState`).
  - Edit regions (move, resize, retype, delete, add), neatline (drag handles, Suggest from ink profile, Full image, Main map -> neatline), tile size and overlap, per-tile priority (click cycles normal / low-res / skip).
  - "Accept triage" / "Update saved triage" writes the server record; server copy wins over the local draft when the sheet is opened.
  - Run OCR enqueues a batch with the neatline, tile params, run id, min confidence and overrides; the panel shows run history and a "Review" jump to Text.
  - Canvas rotation for sideways scans (keys below).
- **Layout:** `ToolLayout` + `ScanLeftRail` (crown "Map", `ToolMapPicker`, "My layers" card with Layout regions / Neatline / Tile grid toggles + Scan opacity, footer mode switcher Prepare / Text / Shapes) + `ImageShell` with `TriageTool` and `RegionsTool` + right `DigitalizeSidebar` -> `ToolSidebarShell` "Prepare" -> `TriageSidebar` (verdict plate, steps 1-4, runs) + `DigitalizeBottomBar` (hint, rotate buttons).
- **Interaction:** URL `?mode=prepare&map=<uuid>`. Keys (window, ignored while typing or with ctrl / meta / alt): `r` rotate canvas +90, `R` -90, `]` +5, `[` -5, `0` reset; `Esc` cancels draw and blurs the field. States: loading ("Loading map…"), empty stage (picker only), layout detecting (job status line), suggesting, saving ("Saving…"), per-step errors, dirty plate (primary button when unsaved). Unsaved triage persists only as a browser draft; no `beforeunload` for it. Mobile: left rail becomes the "Browse" drawer, right becomes "Controls".
- **i18n · a11y · mobile:** English only. Buttons are real `<button>`s; tile/region editing is pointer-only on the canvas (no keyboard path). Collapse button hidden on mobile via `:global` in `ToolPanelHeader`.
- **Findings:**
  - `DigitalizePage.svelte` is 668 lines (skill lists 629; it grew). Also owns Text mode, so the file mixes two modes.
  - `$:` that write: `:286-292` (sets `triage.neatline`), `:296-301` (`triage.tileOverrides = {}` and `prevGridKey`), `:304` (`saveTriageState` on every change, a localStorage side effect), `:178` (`bindRotation`, attaches a listener from a `$:`). The `view.on('change:rotation', read)` listener (`:188`) is never removed.
  - Doc and code disagree: `TriageRunStep`/guide say nothing is read until a person accepts, but the Run OCR button is enabled while the triage is unsaved (only `neatlineValid` and `imgWidth` gate it; styling swaps primary / ghost) and `POST .../ocr` does not check acceptance. The gate exists only in the batch script.
  - `refreshRuns()` (`:339-348`) sends the user to Text whenever the sheet has any OCR run, including right after Run OCR queues a second run. The comment at `runOcr` says "stay on Triage". Re-opening Prepare on an already-read sheet needs a switcher click each time a sheet is selected.
  - `DigitalizeSidebar:9-11` comment says the panel footer carries four reading jobs (Names / Index / Numbers / Other); the component renders no footer. Stale.
  - `TriageLayoutStep.svelte:101` `{#each layoutRegions as r, i (i)}` is keyed by index (skill: never the index).
  - `TriageTool.svelte:70-91` raw `rgba(245,158,11,..)`, `rgba(107,114,128,..)` (use `INK`); `RegionsTool:74` builds `rgba()` from a number.
  - `ToolPanelHeader` re-draws the same collapse SVG that ExploreSidebar, ExploreRightSidebar, AnnotateRightPane and CreateRightPane each repeat (5 copies).

### `/scan?mode=text` — Check what came back (Names · Index · Numbers · Other)
Files: same `DigitalizePage.svelte` (668); `ocr/OcrSidebar.svelte` (658), `OcrRow` (314), `OcrRunBar` (71), `OcrBboxTool` (454), `BboxPanel` (298), `TextGroupPanel` (97), `TextReviewedMark` (71), `ocrReviewController.ts` (432), `ocrDraftSession.ts` (323), `jobs.ts` (125), `shared/ocrApi.ts` (306)
- **For / job:** reviewer who validates, corrects, rejects, draws, rotates and groups the OCR labels on one sheet; then stamps the whole sheet "text reviewed".
- **Access:** page open; API `/api/admin/maps/[id]/ocr-review` and `/pipeline` need a session (writes stamp `user.id`; PATCH uses an RPC that sets `reviewed_at` / `reviewed_by`).
- **Data:** `GET/PATCH/POST/PUT /api/admin/maps/[id]/ocr-review` (rows from `ocr_labels`: `review_status`, `text_corrected`, `category_corrected`, `reviewed_at`); `GET/PATCH /api/admin/maps/[id]/pipeline` (`reviewed` stage, `set_review_mark` RPC); localStorage draft cache `vma-ocr-drafts-v1:<user>:<map>`. No jobs enqueued here.
- **Requirements:**
  - One sheet, rows from every run; filters (search, status, category, confidence, run, group by) plus presets and the four jobs; sort and group.
  - Verdicts are drafts: validate / reject / edit text or category / move or resize box / draw new box / group / duplicate. One "Save" writes all drafts; "Discard" asks `confirm()`.
  - Batch verdict buttons (`OcrRunBar`) with Undo notice; group several boxes into one text.
  - Numbers job checks numerals against the index (`suspectRefs`).
  - "Mark text reviewed" stamps the sheet; no undo by design (the only way back wipes the shape marks).
  - Page leave while dirty is blocked (`beforeunload`); drafts also survive reload via the local cache.
- **Layout:** as Prepare, but `OcrBboxTool` on the canvas, floating `BboxPanel` (one row) or `TextGroupPanel` (several), right `OcrSidebar` + `TextReviewedMark`, bottom bar with Add bbox, Focus, rotate buttons and the selected text.
- **Interaction:** URL `?mode=text&map=`. Keys (window, ignored in fields): `j` / `ArrowDown` next row, `k` / `ArrowUp` previous row, `v` / `Enter` validate and advance, `x` reject and advance, `e` focus the text field, `d` toggle draw box, `f` toggle focus (isolation), `,` `.` turn the label 1 deg, `<` `>` 5 deg, plus the canvas rotation keys from Prepare (`r R ] [ 0`). `Esc` cancels draw, blurs a field, or deselects. `Shift`-click groups. `Enter` in `BboxPanel` saves (not Shift+Enter). States: loading, "Nothing on this sheet for <job>", saving, error toast (only shown when the right rail is collapsed), dirty count on Save, notice + Undo, group/ungroup.
- **i18n · a11y · mobile:** English only. 22 `aria`/`role` uses across all of `digitalize/ocr/trace/review/legend`. Canvas box work is pointer-only; the row table is keyboard-walkable.
- **Findings:**
  - `OcrSidebar.svelte` 658 lines (skill: 588); also `OcrBboxTool` 454, `ocrReviewController` 432.
  - `Enter` validates (`DigitalizePage:240-241`) but the "typing" guard covers only INPUT / TEXTAREA / SELECT / contenteditable, so `Enter` on a focused button or link both activates it and validates the row. Unverified in the browser.
  - `OcrSidebar:333` uses native `confirm()`; the design system has `NameDialog`/modal scaffolding for dialogs. Same native pattern in `MapEditModal`, `ScoutPage`, `MapEditHostingTab`.
  - Client sets `validated_at` itself (`ocrApi.ts:205`, `new Date()`), while the server stamps the real `reviewed_at`; the on-screen time may differ from the stored one until reload.
  - Header comment in `DigitalizePage` and `docs/guides/digitalize-guide.md` describe the old "four jobs in the panel footer" layout; the guide's later text says "All text" plus a preset menu. The two disagree.

### `/scan?mode=shapes` — Draw · Segment · Validate (`?tab=draw|segment|validate`)
Files: `src/lib/features/contribute/trace/ShapesPage.svelte` (450); `TraceTool` (359), `TraceSidebar` (359), `SegSidebar` (239), `traceData.ts` (145), `segCommand.ts` (89); `review/ReviewSidebar` (541), `ReviewTool` (209), `reviewQueue.ts` (342); shared `pipelineApi.ts` (62), `CliCommandBlock` (59)
- **For / job:** Draw: volunteer traces buildings and roads by hand. Segment: operator gets the MapSAM2 Colab command and moves the pipeline stage. Validate: reviewer approves or rejects the machine's polygons.
- **Access:** page open; writes need a session. Draw inserts via the browser Supabase client (RLS); Validate and pipeline calls use `/api/admin/footprints` and `/api/admin/maps/[id]/pipeline` (`requireRole`).
- **Data:** `footprint_submissions` rows (insert, update geometry, delete; status `submitted`); `GET /api/admin/footprints?map_id=&status=needs_review,submitted` (queue); `PATCH /api/admin/footprints` (`set_footprint_status` RPC; body `id, status approved|rejected, pixel_polygon, feature_type, review_tags, review_note`); `GET/PATCH .../pipeline` (`reviewed`, `seg_reviewed`, `exported`, `idle`); localStorage seg config; `trackMeasurement('contribution_open'|'save_success')`. Segment enqueues nothing; a person runs the command on a GPU.
- **Requirements:**
  - Draw: polygon, line, edit tools; draw, drag vertices, delete own shapes only; rename and retype in a table.
  - Segment: show stage badge, gate buttons to advance, build the Colab command from a config.
  - Validate: left rail is a queue of sheets with pending counts; right panel lists polygons with progress "n / total done"; approve or reject one or many; retype; tag a diagnosis and a note; mark sheet "seg reviewed".
  - Tab change keeps the open sheet (`?map=` carried in the tab links).
  - `?map=` deep link from `/admin?tab=status` resolves against whichever list the rail holds.
- **Layout:** `ToolLayout` + `ScanLeftRail` (mode `shapes`, layer toggle "Shapes" or "Machine shapes") + `ImageShell` with `TraceTool` or `ReviewTool` + right `ToolSidebarShell` "Shapes" (panel per tab, `Tabs` strip in the footer) + draw bottom bar (Polygon / Line / Edit).
- **Interaction:** URL `?mode=shapes&tab=&map=`. Keys: Draw (window, skipped in INPUT / TEXTAREA): `Ctrl/Cmd+Z` remove last vertex while drawing, `Enter` finish shape (>= 2 points, polygon needs 3), `Esc` abort / deselect, `Delete` or `Backspace` in Edit mode removes selected shapes you own. Validate (window, ignored in fields): `j` / `ArrowDown` next, `k` / `ArrowUp` previous (wraps), `v` approve, `x` reject. States: queue loading, "Pick a sheet from the queue", per-row deciding, error line with "n of m saved; k failed", empty. Verdicts write at once (no draft) and the row leaves the queue; no undo.
- **i18n · a11y · mobile:** English only. Tabs are links (`aria-current`). Right rail switcher at the footer; mobile gets the two-drawer split.
- **Findings:**
  - Validate writes one PATCH per row, serially (`reviewQueue.ts:305`, noted with a `ponytail:` comment). A decision cannot be undone from the UI and the row disappears at once.
  - `TraceTool.svelte:248` `Backspace` deletes selected shapes in Edit mode with no confirm and no undo. The key guard (`:215`) skips only INPUT / TEXTAREA, not SELECT or contenteditable.
  - Hand-drawn shapes get `status: 'submitted'` and the Validate queue lists `needs_review,submitted`. Whether a reviewer can approve their own drawing is not blocked in the client (unverified server-side).
  - `ShapesPage:159,161,163` `$:` calls (`loadForTab`, `pickWanted`, `saveSegConfig`) run side effects from reactive statements; `loadedFor` is a manual guard against re-entry.
  - `ReviewSidebar` 541 lines; `ReviewTool.svelte:54,58` raw `rgba(249,115,22,..)`, `rgba(234,179,8,..)` canvas fills (use `INK`). `ReviewSidebar:72-76` hex swatches are allowed by the design system (they name printed classes).
  - Mode switcher placement differs: Prepare/Text/Shapes switch in the left rail footer; Draw/Segment/Validate switch in the right rail footer.

### `/scan?mode=legend` — Place the numbered legend on the scan (staff)
Files: `src/lib/features/contribute/legend/LegendPage.svelte` (544); `LegendSidebar` (218), `LegendTool` (267), `legendStage.ts` (87)
- **For / job:** staff member who turns a sheet's numbered legend into pixel positions, by choosing an entry, clicking the scan or accepting a detected numeral.
- **Access:** admin / mod. The page has no client check; `GET/PATCH /api/admin/maps/[id]/legend-points` refuse others and the page then shows "The legend tool is for staff." (`LegendPage:192`).
- **Data:** `GET/PATCH /api/admin/maps/[id]/legend-points` (entries, numeral candidates, index grid, legend rects; PATCH validates with `userId`); `GET /api/admin/maps/legend-stats` (placed / total badges); `fetchSheetWork` (`work-state`); `POST /api/admin/maps/[id]/px-from` (carry a click from a neighbouring scan through both georeferences); `POST /api/admin/maps/[id]/triage` (`legend: 'none'`, "No legend on this sheet"); `invalidateLegend` clears the client cache after a save.
- **Requirements:**
  - Sheet picker with status filter (All / To do / In progress / Done / Legend found, not read / No legend located) and `placed/total` badges.
  - Stage edits; one batch PATCH saves them; a server-refused entry stays staged with its message.
  - Place by click; Shift-click or "Add another point" for a number printed on several plots; accept a detected numeral (one, or all that sit in their index cell); drag a pin to move.
  - "Click on sheet": show a same-year sibling scan instead and carry the click across.
  - Mark a sheet as having no legend.
- **Layout:** `ToolLayout` + `ScanLeftRail` (no mode switcher; filter select in the picker slot; layers Placed points / Numeral candidates / Index grid) + `ImageShell` with `LegendTool` + right `ToolSidebarShell` "Legend" -> `LegendSidebar` (filter, search, rows, Save).
- **Interaction:** URL `?mode=legend&map=`. Keys (window, ignored in fields or with ctrl/meta): `n` select next unplaced entry, `Enter` accept the best numeral for the selected entry, `Esc` stop "add another" or deselect, `Delete` / `Backspace` clear the selected entry's position. States: empty ("Pick a map…"), no legend ("This sheet has no numbered legend."), load error, saving, `Saved N.`, per-row failure (`role="alert"`). Unsaved staged edits are lost silently on switching sheet (`loadLegend` resets `staged`) and on reload (no `beforeunload`). Mobile: two-drawer split.
- **i18n · a11y · mobile:** The only scan mode with `$t()` (45 calls); the picker select has an `aria-label`. Canvas is pointer-only apart from the keys above.
- **Findings:**
  - Data-loss path: `LegendPage:loadLegend` zeroes `staged` and `failures` on every sheet change and there is no `beforeunload` or `confirm`. Text mode has both.
  - `LegendSidebar.svelte:139` `{#each row.more as point, index (index)}` keyed by index.
  - `Delete` and `Backspace` clear a placed point with no confirm (it is staged, so recoverable until Save).
  - `LegendPage` 544 lines, `LegendTool` 267; one more file over the 500 mark.
  - Legend is in `CONTRIBUTE_TOOLS` (catalog row action, `toolHref`) but not in the rail's footer switcher, so from another scan mode it is reachable only by a typed URL or the catalog.

---
### `/admin` — shell (tab dispatcher)
Files: `src/routes/(editorial)/admin/+page.svelte` (66); `src/lib/core/routeModes.ts` (`ADMIN_TABS`, `resolveAdminTab`)
- **For / job:** staff console; one page with four tabs chosen by `?tab=`.
- **Access:** page open; each tab gates itself (Bulk admin only; Scout, Status admin / mod; Stories no client gate, API gates). `noindex`.
- **Data:** none of its own.
- **Requirements:** tabs `bulk`, `scout`, `status`, `stories`; default and fallback is `status` ("read-only and available to mods"); tabs are links so a tab is shareable; `.editorial-main` goes wide for Bulk and Scout.
- **Layout:** editorial register: `.page.admin-page` -> `PageHero` (eyebrow = tab name, title "Admin") -> `main.editorial-main` -> `Tabs` (page tone, href links) -> tab body. Under `(editorial)`, so NavBar and footer show.
- **Interaction:** URL `?tab=`. No keys at shell level (Scout adds its own).
- **i18n · a11y · mobile:** English only. Tabs are links with `aria-current`.
- **Findings:**
  - `+page.svelte:49` widens the measure for `bulk` and `scout`; the design system says `.is-wide` is for `/admin?tab=scout` only.
  - `docs/guides/admin-tooling.md` and `src/routes/CLAUDE.md` still say "there is no general /admin route"; the code now has the dispatcher and a Status default.
  - Each tab sets its own `<title>` (`Bulk Upload — Admin`, `Scout · VMA Admin`, `System status · VMA Admin`) on top of the shell's `Admin — Vietnam Map Archive`; Stories sets none. Three title formats, two `<title>` tags per page.
  - Tab bodies are not in the editorial component vocabulary alike: Status and Stories use `.section-title-sm` / `.empty-state`; Scout and Bulk also use `.sb-card`, `.sb-input`, `.sb-pill` (sidebar-scope classes) on an editorial page.

### `/admin?tab=bulk` — Bulk upload
Files: `src/lib/features/admin/BulkUploadPage.svelte` (329), `GeorefSyncPanel.svelte` (44), style `pages/admin-bulk.css`
- **For / job:** admin who adds a batch of scans as draft `maps` rows and gets the shell script that tiles and uploads them.
- **Access:** admin only (client check via `fetchUserRole`; "Admin only." otherwise). API `POST /api/admin/maps` also needs a role.
- **Data:** `POST /api/admin/maps` per row (`status: 'draft'`, `source_type: 'self'`); `PATCH /api/admin/maps/[id]` (thumbnail, `iiif_image`) after tiling; browser `fetch` to `https://iiif.maparchive.vn/iiif/<id>/info.json`; `POST /api/admin/maps/sync-georef` (GeorefSyncPanel). Enqueues nothing; tiling runs on the admin's machine from the generated `tile_map.sh` lines.
- **Requirements:**
  - Paste paths (tab, CSV, or one path per line); name and year are parsed from `<sheet#> <Place> <YYYY>.jpg`.
  - Editable grid with default collection; "Create N map rows"; row status tick / cross with the error in the title.
  - Output a copy-paste bash script of `./scripts/tile_map.sh <uuid> '<path>'` lines; "Backfill thumbnails" after tiling.
  - A second card runs "Sync georef from Allmaps" (unrelated to bulk upload; the file says so).
- **Layout:** `section-card`s numbered 1 Defaults, 2 Maps, (Sync card), 3 Run this locally. `DataTable` for the grid.
- **Interaction:** URL `?tab=bulk`. No keys. States: role check ("Checking access…"), not admin, creating ("Creating…"), per-row ok / fail, summary line. No unsaved-changes guard; leaving the page loses the pasted rows and the generated script.
- **i18n · a11y · mobile:** English only; remove button has `aria-label`; glyphs `✓ ✗ ✕` in the table and `✓` in the generated script. Wide table: horizontal scroll on phones (unverified).
- **Findings:**
  - `:269` `{#each rows as row, i (i)}` is keyed by index while every cell is `bind:value` to the row; removing a middle row can leave the wrong inputs bound (the skill requires a stable id).
  - `createBatch` (`:131-187`) loops every row, including rows already `created`; a second click POSTs them again and makes duplicate draft maps (no skip on `r.id`).
  - `backfillCreated` (`:201-224`) swallows all errors (`catch {}` at `:219`) and always appends " · thumbnails backfilled" to the summary, even when nothing was patched; the IIIF host is hard-coded in the page.
  - `GeorefSyncPanel` is a maintenance action parked on this tab (its own header says it belongs elsewhere); the "Sync" tab owner is unclear.
  - `copyScript` ignores clipboard failure silently (`catch {}` at `:197`).

### `/admin?tab=scout` — Scout review
Files: `src/lib/features/admin/ScoutPage.svelte` (397), `ScoutCard` (115), `ScoutTable` (118), `ScoutDecision` (138), style `pages/admin-scout.css`
- **For / job:** admin / mod who judges ~1,000 external map candidates (Gallica, Humazur, Rumsey, LoC, AGS) and ingests approved ones as draft maps.
- **Access:** admin / mod (client check; "Admin access required." otherwise). API `/api/admin/scout*` is `requireRole(['admin','mod'])`.
- **Data:** `GET /api/admin/scout?status&source&category&q&order&dir&limit&offset` (reads `scout_candidates`; facets in the response); `PATCH /api/admin/scout/[id]` (`review_status`, `review_note`; server stamps `reviewed_by` and `reviewed_at`; only pending / approved / rejected); `POST /api/admin/scout` (bulk ingest into `maps` as drafts). localStorage `vma-scout-view-v1`. No pipeline jobs.
- **Requirements:**
  - Two views of one queue: card grid or dense table, remembered. Sorting is the server's, 60 rows per page.
  - Filters: status (default pending), source, category, title search; facet counts in the labels.
  - Per-row Approve / Reject with optional reason (presets or free text); bulk approve / reject with one reason; "Select page"; bulk ingest only when the status filter is Approved.
  - A pending decision removes the row at once (optimistic); other views update in place.
  - Keyboard sweep (below).
- **Layout:** header with a keyboard hint line, filter card (`.sb-card`), bulk bar, then `ScoutCard` grid or `ScoutTable` (`DataTable`).
- **Interaction:** URL `?tab=scout` (filters are not in the URL). Keys (window `keydown`; skipped in INPUT / TEXTAREA / SELECT or with ctrl / meta): `j` / `ArrowDown` next, `k` / `ArrowUp` previous, `a` approve (pending rows), `r` reject, `u` revert to pending, `x` toggle selection. In the reason box: `Enter` commits, `Esc` cancels. States: role check, loading ("Loading…"), empty, action message line, no pagination state in URL. `confirm()` before ingest.
- **i18n · a11y · mobile:** English only. Cards: checkbox has `aria-label`; view toggle `aria-pressed`; glyphs `▦ ☰` in the toggle. Phone layout unverified.
- **Findings:**
  - `bulkSetStatus` (`:139-160`): `fetch` does not throw on HTTP errors and the code never reads `r.ok`, so every row counts as ok; the final message "Updated N/N" can be wrong, and the `catch` is empty (`:154`). `decide()` checks `r.ok`; the bulk path should too.
  - `bulkIngest` (`:164-180`) reads `data.ok` / `data.failed` without checking `r.ok`; a 403 shows "Ingested undefined ok".
  - The confirm text says "approved candidates", but the selection can hold rows from any status filter; only the button's visibility is tied to `filterStatus === 'approved'`.
  - Key `r` rejects here and rotates the canvas in `/scan?mode=prepare|text`; `x` selects here and rejects in Text / Validate (see Keyboard map).
  - Filters, page and view are not in the URL, so a filtered queue cannot be shared or restored after reload (view is stored in localStorage only).
  - `ScoutCard.svelte:63` literal `#222` / `#888` inside a placeholder SVG data URI (documented in the file; not a theme token).

### `/admin?tab=status` — System status
Files: `src/lib/features/admin/StatusPage.svelte` (371), style `pages/admin-status.css`; API `src/routes/api/admin/status/+server.ts`
- **For / job:** admin / mod who wants to know what the archive holds, what is stuck and what to do next, without SQL.
- **Access:** admin / mod (client check; "Admin access required."). The API counts under `requireRole(['admin','mod'])`.
- **Data:** `GET /api/admin/status` (head counts over `maps`, `map_pipeline_status`, `ocr_labels`, `place_names`, `footprints`, `pipeline_jobs`). Read-only; writes nothing.
- **Requirements:**
  - Sections with plain-language rows: label, value ("x of y"), detail, tone (good / warn / bad / idle), optional "Next" instruction.
  - A "Biggest blocker" headline chosen from the rows.
  - "What failed": recent failed jobs with kind, tries, error and a map link.
  - Manual Refresh and "Last checked" time; no polling.
  - All wording lives in `build()`; the API only counts.
- **Layout:** `status-bar`, optional headline, sections of `status-row` articles tinted by tone. Standard width.
- **Interaction:** URL `?tab=status` (default tab). No keys. States: role check, loading ("Reading the archive…"), "Checking…" on Refresh, load error line, empty failures list hidden.
- **i18n · a11y · mobile:** English only; numbers use `en-US` grouping. Tone is carried by a class (colour) and the row text; no tone word for a screen reader (unverified).
- **Findings:**
  - `:348` `{#each data.jobs.failures as f, i (i)}` keyed by index.
  - The "Next" lines name routes in plain text (`/scan?mode=prepare`, `/contribute/georef`, `/scan?mode=shapes&tab=validate`), not links; the reader must copy the path.
  - There is no auto refresh (only the Refresh button), so the "queued / running" counts go stale while a worker runs.
  - `docs/guides/admin-tooling.md` does not list this tab at all.

### `/admin?tab=stories` — Story review queue
Files: `src/lib/features/admin/StoryReviewPanel.svelte` (157); API `src/routes/api/admin/stories/+server.ts`
- **For / job:** admin / mod who approves, sends back or rejects stories authors have submitted.
- **Access:** no client check. `GET` and `PATCH /api/admin/stories` use `requireRole(['admin','mod'])`; anyone else sees the server's error text in the error line.
- **Data:** `GET /api/admin/stories?status=submitted` (`stories` with point count); `PATCH /api/admin/stories` `{ id, status: approved | rejected | draft }` (column `review_status`). Approving makes the story public (mig 059).
- **Requirements:**
  - List submitted stories with title (opens `/trip/<id>` in a new tab), point count, mode, updated date, description.
  - Three verdicts per row: Approve, Send back (to draft), Reject; the row leaves the list when the call succeeds.
  - Empty line "Queue's clear — no stories waiting on review."
- **Layout:** `ul.story-list` of bordered rows (page-scoped styles using tokens); standard width.
- **Interaction:** URL `?tab=stories`. No keys. States: loading, error, empty, per-row busy (buttons disabled). No reason field, no confirm, no undo.
- **i18n · a11y · mobile:** English only; rows stack poorly on a narrow screen (unverified: `.story-row` is a flex row with no wrap).
- **Findings:**
  - No role check in the component, unlike its three sibling tabs; a signed-out visitor sees "Loading stories…" then a raw error string.
  - The reviewer opens `/trip/<id>` to read it, a mobile player with GPS prompts, not a read-only preview. For a story that is only `submitted`, `fetchStoryById` must allow the reviewer's role (unverified).
  - `Approve` / `Reject` carry no reason; Scout takes a reason (`review_note`), footprints take tags and a note. Three review forms in one admin area. The server does stamp the reviewer (`set_story_status` RPC with `p_user`), but the panel shows neither who nor when.
  - `Send back` and `Reject` are different statuses (`draft` vs `rejected`), but the author sees "Sent back" for `rejected` (`StoryHeaderPanel` `STATUS_LABEL`) and "Private" for `draft`, so a sent-back-to-draft story looks like an untouched private one.

---

## Keyboard map

All bindings are `keydown` on `window` unless noted. "Typing guard" = what the handler skips: **A** = `isTypingTarget`-style (INPUT / TEXTAREA / SELECT / contenteditable), **B** = INPUT / TEXTAREA only, **C** = INPUT / TEXTAREA / SELECT, **D** = none (checks `defaultPrevented`).

| Key | Surface | Action |
|---|---|---|
| `ArrowLeft` / `ArrowRight` | Explore browse | previous / next sheet by year on the top overlay |
| `ArrowUp` / `ArrowDown` | Explore browse | top overlay opacity +/- 0.1 |
| `Esc` | Explore browse | clear focus pulse and lit legend row |
| `Esc` | Explore map context menu | close menu |
| `Ctrl/Cmd+Z` | Studio | undo last annotation action |
| `Ctrl/Cmd+Shift+Z`, `Ctrl/Cmd+Y` | Studio | redo |
| `Esc` | Studio Overpass dialog | close (unless fetching) |
| `Ctrl/Cmd+Z` | Story editor | undo last point added |
| `Esc` | Story editor | deselect point, else leave Place mode, else leave Move mode |
| `r` / `R` | Prepare, Text | rotate canvas +90 / -90 |
| `]` / `[` | Prepare, Text | rotate canvas +5 / -5 |
| `0` | Prepare, Text | reset canvas rotation |
| `Esc` | Prepare, Text | cancel draw, blur field, deselect |
| `j` / `ArrowDown` | Text | next row |
| `k` / `ArrowUp` | Text | previous row |
| `v` / `Enter` | Text | validate row and advance |
| `x` | Text | reject row and advance |
| `e` | Text | focus the text field |
| `d` | Text | toggle draw-a-box |
| `f` | Text | toggle focus (isolation) |
| `,` `.` / `<` `>` | Text | turn the label 1 deg / 5 deg |
| `Enter` (in box panel) | Text | save the edited box (not with Shift) |
| `Ctrl/Cmd+Z` | Shapes - Draw | remove the last vertex while drawing (not an undo of finished shapes) |
| `Enter` | Shapes - Draw | finish shape (line >= 2 points, polygon >= 3) |
| `Esc` | Shapes - Draw | abort drawing, deselect |
| `Delete` / `Backspace` | Shapes - Draw (Edit tool) | delete selected shapes you own |
| `j` / `ArrowDown`, `k` / `ArrowUp` | Shapes - Validate | next / previous polygon (wraps) |
| `v` | Shapes - Validate | approve selected |
| `x` | Shapes - Validate | reject selected |
| `n` | Legend | select next unplaced entry |
| `Enter` | Legend | accept best numeral for the selected entry |
| `Esc` | Legend | stop "add another point", else deselect |
| `Delete` / `Backspace` | Legend | clear the selected entry's position |
| `j` / `ArrowDown`, `k` / `ArrowUp` | Admin Scout | next / previous candidate |
| `a` | Admin Scout | approve (pending rows) |
| `r` | Admin Scout | reject (pending rows) |
| `u` | Admin Scout | revert to pending |
| `x` | Admin Scout | toggle selection |
| `Enter` / `Esc` (in reason box) | Admin Scout | commit / cancel the reason |
| `Cmd/Ctrl+K` | all pages (root layout) | command palette (not audited here) |
| none | Trip, Inspect, Bulk, Status, Stories | no bindings |

Typing guards: Explore **A** (`isTypingTarget`); Studio and Story **D** (check `defaultPrevented`, then INPUT / TEXTAREA / contenteditable); Digitalize **A**; Legend **A** via `closest`; Validate **A**; Draw **B**; Scout **C**. Eight handlers, four variants, one shared helper (`isTypingTarget`, `core/utils/commandPalette.ts:53`) used only by Explore.

**Clashes (same key, different meaning):**
- `r`: rotate canvas 90 (Prepare / Text) vs reject (Scout).
- `x`: reject (Text, Validate) vs toggle selection (Scout).
- `Enter`: validate and advance (Text) vs accept numeral (Legend) vs finish shape (Draw) vs commit reason (Scout).
- `Ctrl/Cmd+Z`: undo any action (Studio) vs undo last point (Story) vs drop last vertex (Draw only while drawing). Text mode has no `Ctrl+Z`; its undo is a button.
- `Delete` / `Backspace`: delete a shape (Draw) vs clear a position (Legend). `Backspace` aliased to Delete for Mac in both; Studio and Story have no delete key.
- `d`: draw box (Text) but not draw in Draw tab (buttons only). `f` has no equivalent elsewhere.

**Same action, different key:**
- Approve: `v` (Validate), `v` / `Enter` (Text, called validate), `a` (Scout). Reject: `x` (Text, Validate), `r` (Scout). Revert: `u` (Scout), button "Undo" (Text), none (Validate).
- Next row: `j` / `ArrowDown` everywhere in review lists, but `n` in Legend and `ArrowRight` in Explore.
- Cancel: `Esc` is used consistently, but its target differs (deselect, cancel draw, close dialog).
- Rotate: `r` / `R` / `[` / `]` (canvas, Prepare / Text) vs `,` `.` `<` `>` (label, Text) vs `Ctrl`-drag (map, MapShell).

**For the planned `/review/[task]` page** (`docs/plans/review-page-plan.md`, keys `s n m g x ? t u o v w`): `x` = "none" there but reject in Text / Validate; `v` = open satellite there but validate / approve elsewhere; `n` = "same site" there but next-unplaced in Legend; `u` = undo agrees with Scout's revert. `o`, `w`, `t`, `s`, `m`, `g` are free in every surface above.

---

## Patterns across these surfaces

- **Two shell families, one rail grammar.** Map tools (explore, studio, story) use `MapWorkspace` -> `ToolLayout` -> `MapShell`; pixel tools (scan) use `ToolLayout` -> `ImageShell` directly. Both rails use `.sb-rail`/`.sb-bar` crown, `Tabs tone="rail"`, `SidebarCard`. Scan factors the crown into `ToolSidebarShell` + `ToolPanelHeader`; explore, studio and story each repeat the bar and its collapse SVG by hand (5 copies). A review page should mount `ToolSidebarShell`, not copy the bar.
- **Where the mode switch lives is not fixed.** Explore: NavBar. Scan modes: left-rail footer (`ScanLeftRail`, Legend and Inspect omitted). Shapes tabs: right-rail footer. Admin: page-level `Tabs` links. `Tabs` (link vs button, `aria-current` vs `tablist`) is already the one component.
- **Four save models.** (1) Draft session + "Save N" + `confirm` on discard + `beforeunload` + local cache (Text, `OcrDraftSession`). (2) Immediate per-row verdict, row leaves the queue, optional tags and note, no undo (Validate, Stories, Scout). (3) Staged batch with per-row failures kept on screen (Legend); staged edits die on sheet change. (4) Auto-persist to localStorage plus explicit Save (Studio) or Submit (Story); Studio's "autosave dot" and Story's static "Saved" badge show no real server state. Only model 1 guards unsaved work.
- **Review statuses do not share names.** OCR `pending / validated / rejected`; footprints `needs_review / submitted / approved / rejected`; scout `pending / approved / rejected / ingested`; stories `draft / submitted / approved / rejected`; triage `proposed / accepted`; sheet stages `reviewed / seg_reviewed / exported / idle`. "Validate" and "approve" mean the same act in two places. Only stories have "send back"; only Scout has revert; only Text has batch Undo.
- **Human review is stamped on the server, from the session, never from the body.** `set_footprint_status` RPC, `ocr-review` PATCH RPC (`reviewed_at`/`reviewed_by`), `set_story_status` RPC, scout PATCH (`reviewed_by`/`reviewed_at`), triage POST (`validated_by`, `validated_at`, `neatline_src: 'human'`), `set_review_mark` (`p_user`). The client shows the time, never the person. Gaps: no per-item seconds or shown-at anywhere (the planned `review_events` table is what supplies them); stories' stamp is set by the `set_story_status` RPC but never shown; client-side `validated_at` in `ocrApi.ts:205` is a guess shown until reload. The machine/human split is visible in the UI only in Prepare (dashed = proposal, solid = yours; Proposed vs Accepted).
- **Queue-first reviewing.** Validate (`$queue.queue` as the rail list with "N pending" badges), Scout (page of 60 + facets), Stories (list) all show a worklist with counts. Text and Legend use the archive list with `placed/total` or status badges. A review page should reuse the rail-list-with-badge and the "n / total done" progress line (`ReviewSidebar`).
- **Empty, error, loading.** Scan: `EmptyPanel` for rail states, `.loading-stage` + `.spinner` for the canvas, `.empty-state.error` for the picker error. Admin: `.empty-state.is-block` (+ `.error`) for every state. Explore: floating chip + `role="alert"` banner. Trip: its own `.state`. Most errors are one raw string; only Status has a Refresh button, and no surface offers Retry on a failed load.
- **Access is checked in three different places.** Client role check with a message (Bulk, Scout, Status); `AuthGate` (Studio, Story); nothing (all of `/scan`, Stories tab) with the API as the only gate. A review page should gate in `+page.server.ts`, as its plan says, not in the component.
- **Keyboard review is a house idiom, not a shared module.** `j k ArrowUp ArrowDown v x` in Text and Validate; `a r u x j k` in Scout. Eight handlers re-implement the typing guard in four ways (see Keyboard map). `isTypingTarget` exists; the review plan already names it. Buttons with `aria-keyshortcuts` do not exist yet in any of these surfaces.
- **Size and hygiene drift since the skill's last count.** Over 500 lines now: `DigitalizePage` 668 (was 629), `OcrSidebar` 658 (588), `ExplorePage` 677 (560), `CreateMode` 588 (591), `LegendPage` 544, `ReviewSidebar` 541, `AnnotateMode` 500. Keyed-by-index `{#each}` appears six times in scope (`BulkUploadPage:269`, `StatusPage:348`, `LegendSidebar:139`, `TriageLayoutStep:101`, `NeatlineEditor:306,325`), against the skill's "all keyed by a stable id". Raw `rgba()` in canvas styles remains in `TriageTool`, `ReviewTool`, `BboxSelector`, `OverpassPreviewLayer`, `ExplorePrivacyNotice`. Emoji or glyphs in chrome: `📝 📖 📍 ⊘ ▦ ☰ ✓ ✗ ✕`.
- **i18n coverage by surface.** `$t()` calls: Legend 45, Explore 33, Stories play + editor 30 (all in play), Studio 1, Prepare / Text / Shapes / Inspect / Admin 0. A review page for contributors (plan v2) should translate from the first commit; Legend shows the pattern (`$t` at render, labels in `$:`).
