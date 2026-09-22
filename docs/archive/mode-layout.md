# Mode Layout Reference

Canonical layout implemented in `/view` mode. All modes should follow this structure for
consistency.

## Template Structure

```
.mode-root                          (full viewport, flex column)
├── .workspace                      (CSS grid, fills remaining space)
│   ├── <Sidebar>                   (desktop only, collapsible, left column)
│   └── .map-stage                  (relative, overflow:hidden, holds everything below)
│       ├── <MapShell>              (creates OL map, exposes context)
│       │   ├── <HistoricalOverlay> (headless: warped map layer, load events)
│       │   ├── <GpsTracker>        (headless: GPS vector layer)
│       │   ├── <StoryMarkers>      (headless: numbered point markers)
│       │   └── <StoryPlayback>     (positioned UI inside shell overlay)
│       │
│       ├── .top-controls           (top-left, show-panel button when sidebar collapsed)
│       ├── .floating-controls      (bottom-right, vertical stack of circle buttons)
│       ├── .map-toolbar            (bottom-center, horizontal control bar)
│       ├── .lens-overlay           (center, spy mode only)
│       ├── .overlay-loading        (center, loading spinner)
│       ├── .overlay-error          (bottom-center above toolbar, error banner)
│       ├── .gps-error              (top-center, error banner)
│       ├── .top-search-bar         (top-center, search trigger — same width as toolbar)
│       └── .search-anchor          (full area, repositions SearchPanel to top-center)
│           └── <SearchPanel>       (maps + location search, dropdown panel)
│
└── mobile sidebar                  (fixed overlay + sliding panel, mobile only)
```

## Z-Index Stack (within `.map-stage`)

| z-index | Element               | Notes                                  |
|---------|-----------------------|----------------------------------------|
| —       | MapShell `.shell`      | No z-index, contains OL viewport       |
| 10      | `.shell-overlay`       | pointer-events:none, children get auto  |
| 40      | `.map-toolbar`         | Bottom-center control bar              |
| 45      | `.lens-overlay`        | Spy mode resize knob                   |
| 50      | `.top-controls`        | Top-left show-panel button             |
| 50      | `.floating-controls`   | Bottom-right circle buttons            |
| 50      | `.top-search-bar`      | Top-center search trigger              |
| 55      | `.overlay-loading`     | Center loading spinner                 |
| 60      | `.gps-error`           | Top-center error                       |
| 60      | `.overlay-error`       | Bottom error banner                    |
| 100     | `.search-anchor`       | Full area, pointer-events:none         |
| 100     | `SearchPanel`          | Dropdown (inside search-anchor)        |
| 100     | `StoryPlayback`        | Inside shell-overlay stacking context  |

## Grid Layout

```css
/* Default: map fills everything */
.workspace {
  grid-template-columns: minmax(0, 1fr);
}

/* With sidebar visible (desktop) */
.workspace.with-sidebar {
  grid-template-columns: minmax(260px, 0.25fr) minmax(0, 1fr);
}

/* Compact (1400px breakpoint) */
.workspace.with-sidebar.compact {
  grid-template-columns: minmax(200px, 0.24fr) minmax(0, 1fr);
}

/* Mobile: always single column */
.view-mode.mobile .workspace {
  grid-template-columns: minmax(0, 1fr);
}
```

## Responsive Breakpoints

| Breakpoint  | Variable    | Effect                                        |
|-------------|-------------|-----------------------------------------------|
| ≤ 900px     | `isMobile`  | Single column, hamburger menu, sliding sidebar|
| ≤ 1400px    | `isCompact` | Narrower sidebar column                       |

## Shared Components (from `$lib/`)

### MapShell (`$lib/map/shell/MapShell.svelte`)
- Creates and owns the single OL Map instance
- Manages basemap tile layers
- Exposes `map`, `mapStore`, `layerStore` via Svelte context (`getShellContext()`)
- Bidirectional OL View ↔ mapStore sync
- URL hash sync (can be disabled via `disableUrlSync` prop)
- Slot renders inside `.shell-overlay` (pointer-events:none, children auto)

### HistoricalOverlay (`$lib/map/shell/HistoricalOverlay.svelte`)
- Headless, goes inside MapShell slot
- Reacts to `mapStore.activeMapId`
- Hides canvas immediately on map switch (prevents ghosting)
- Tracks tile loading via `allrequestedtilesloaded` event
- Dispatches: `loadstart`, `loadend`, `loaderror`
- 20s timeout for unresponsive tile sources

### SearchPanel (`$lib/ui/SearchPanel.svelte`)
- Two tabs: Maps (client-side filter) and Location (Nominatim + coordinates)
- Props: `open`, `maps`, `selectedMapId`
- Events: `close`, `navigate`, `selectMap`, `addToAnnotations`
- Position overridden via parent `.search-anchor :global(.search-panel)` CSS

### Stores (`$lib/map/stores/`)
- `mapStore` — `lng`, `lat`, `zoom`, `rotation`, `activeMapId`
- `layerStore` — `basemap`, `overlayOpacity`, `overlayVisible`, `viewMode`, `sideRatio`,
  `lensRadius`
- `urlStore` — bidirectional URL hash ↔ stores sync

## Toolbar Width Sync

The top search bar and SearchPanel are width-synced to the bottom toolbar:

```js
let toolbarEl: HTMLDivElement;
let toolbarWidth = 0;

// ResizeObserver on the toolbar
toolbarRo = new ResizeObserver(() => {
  if (toolbarEl) toolbarWidth = toolbarEl.offsetWidth;
});
```

```html
<!-- Search bar matches toolbar width -->
<div class="top-search-bar" style:width={toolbarWidth ? `${toolbarWidth}px` : undefined}>

<!-- SearchPanel matches via CSS variable -->
<div class="search-anchor" style:--toolbar-width={toolbarWidth ? `${toolbarWidth}px` : '320px'}>
```

```css
.search-anchor :global(.search-panel) {
  width: var(--toolbar-width);
}
```

## Overlay Loading Pattern

```html
<HistoricalOverlay
  on:loadstart={() => { overlayLoading = true; overlayError = null; }}
  on:loadend={() => { overlayLoading = false; }}
  on:loaderror={(e) => { overlayLoading = false; overlayError = e.detail.message; }}
/>

{#if overlayLoading}
  <div class="overlay-loading">
    <div class="loading-spinner"></div>
    <span>Loading map overlay...</span>
  </div>
{/if}

{#if overlayError}
  <div class="overlay-error">
    <span>{overlayError}</span>
    <button on:click={() => (overlayError = null)}>dismiss</button>
  </div>
{/if}
```

## Mobile Sidebar Pattern

Desktop: sidebar is a grid column, toggled via `sidebarCollapsed`.
Mobile: sidebar is a fixed overlay with backdrop.

```html
<!-- Desktop sidebar (grid column) -->
{#if !sidebarCollapsed && !isMobile}
  <Sidebar on:toggleCollapse={() => (sidebarCollapsed = !sidebarCollapsed)} />
{/if}

<!-- Mobile sidebar (fixed overlay) -->
{#if isMobile && !sidebarCollapsed}
  <div class="mobile-overlay" on:click={() => (sidebarCollapsed = true)}></div>
  <div class="mobile-sidebar">
    <Sidebar on:toggleCollapse={() => (sidebarCollapsed = true)} />
  </div>
{/if}
```

## Floating Controls Pattern

Bottom-right vertical stack of 40px circle buttons:

```html
<div class="floating-controls">
  <button class="ctrl-btn" ...>Basemap toggle</button>
  <button class="ctrl-btn" ...>GPS toggle</button>
  {#if isMobile}
    <button class="ctrl-btn" ...>Hamburger menu</button>
  {/if}
</div>
```

Each mode can add/remove buttons. Common ones: basemap toggle, GPS. Mode-specific: undo/redo
(annotate), save (create).

## Bottom Toolbar Pattern

Centered bar with groups separated by `.toolbar-sep`:

```html
<div class="map-toolbar" bind:this={toolbarEl}>
  <div class="toolbar-group">
    <span class="toolbar-label">Label</span>
    <div class="toolbar-btns">
      <button class="tb" class:active={...}>...</button>
    </div>
  </div>
  <div class="toolbar-sep"></div>
  <div class="toolbar-group">...</div>
</div>
```

Separators hidden on mobile. Toolbar wraps with `flex-wrap` on mobile.

## Design Tokens

| Token                          | Value                                              |
|--------------------------------|----------------------------------------------------|
| Gold accent                    | `#d4af37`                                          |
| Gold dark                      | `#b8942f`                                          |
| Background gradient            | `#f4e8d8 → #e8d5ba` (160deg)                      |
| Panel background               | `rgba(244, 232, 216, 0.95)` → `rgba(232, 213, 186, 0.95)` |
| Text primary                   | `#2b2520`                                          |
| Text secondary                 | `#4a3f35`                                          |
| Text muted                     | `#8b7355`                                          |
| Text light                     | `#6b5d52`                                          |
| Border gold                    | `2px solid #d4af37`                                |
| Border subtle                  | `1px solid rgba(212, 175, 55, 0.3)`                |
| Shadow panel                   | `0 8px 24px rgba(0, 0, 0, 0.15)`                  |
| Shadow toolbar                 | `0 4px 18px rgba(0, 0, 0, 0.18)`                  |
| Shadow button                  | `0 4px 12px rgba(0, 0, 0, 0.15)`                  |
| Font heading                   | `'Spectral', serif`                                |
| Font body                      | `'Be Vietnam Pro', sans-serif`                     |
| Font serif body                | `'Noto Serif', serif`                              |
| Button radius                  | `3px` (toolbar), `50%` (circle ctrl-btn)           |
| Panel radius                   | `4–6px`                                            |
| Backdrop blur                  | `blur(12px)`                                       |

## Per-Mode Customization

Each mode replaces:
1. **Sidebar content** — different panels, actions, lists
2. **Toolbar groups** — mode-specific tools (drawing modes, view modes, etc.)
3. **Floating control buttons** — mode-specific actions
4. **MapShell slot children** — mode-specific headless components (markers, draw interactions)
5. **Top search bar behavior** — can remain the same or be customized

The shell (`MapShell` + `HistoricalOverlay` + stores + search bar + loading/error) stays identical
across modes.
