<!--
  NavBar.svelte — Shared top navigation for editorial pages.

  Two tiers. The bar itself carries only what a visitor came to read —
  Catalog, About, Blog — and every tool sits behind one Tools menu, which is
  also where the staff pages appear once a role is known. A tool is something
  you go and do; putting eight of them in the bar made the bar the tool.

  Tools ▾:  Map viewer /explore
            Story Builder /explore?mode=story | Studio /explore?mode=studio
            ── Contribute /contribute | Georeference /contribute/georef
               Prepare a sheet /scan?mode=prepare | Check the text /scan?mode=text
               Shapes /scan?mode=shapes
            ── Admin /admin (mod)
               Design system /screens (admin)
            ── All pages /directory

  "Inspect a scan" came out in Sept 2026: /catalog/[id] shows the tiled scan
  itself now, so the catalog is that door. /scan keeps only the staff modes,
  which is why it is still in `activeTools` below.

  `role` gates the staff rows the same way the pages do — hidden rather than
  shown and then refused. It arrives from the (editorial) layout, because ui/
  may not import from data/ (layering rule).

  The search button opens the app-wide command palette (⌘K). NavBar is in `ui`,
  which may not import `features`, so it only flips the store in core/utils —
  the palette itself is mounted by the root layout.

  Mobile (<=640px): hamburger → bottom-anchored drawer with flat link list.

  Styles use editorial.css globals (.top-nav, .nav-logo, .nav-links, .nav-link) and `.btn`.
  Dropdown + drawer styles live here (scoped).
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { onMount } from 'svelte';

  import type { ClientSession } from '$lib/data/supabase/context';

  import NavDropdown from './NavDropdown.svelte';
  import { page } from '$app/stores';
  import { openPalette, pageOwnsSearch } from '$lib/core/utils/commandPalette';
  import { theme, setTheme, nextTheme, themeLabel } from '$lib/core/utils/theme';

  // ui/ is domain-free (layering rule): the layout that mounts NavBar passes
  // the session and the resolved role in.
  export let session: ClientSession | null = null;
  export let role: string | null = null;

  let drawerOpen = false;
  /** ⌘K on a Mac, Ctrl K everywhere else. Corrected after hydration, not at
      init: a server-rendered text node is reused as it stands. */
  let paletteKey = '⌘K';

  /**
   * Two things the front page does better than the bar does, so the bar stops
   * doing them there:
   *
   * `$pageOwnsSearch` — the hero carries the same field this button opens.
   * While that field is on screen there is no reason to offer a second one;
   * the moment it scrolls away this takes the job back.
   *
   * `quietCta` — "Open the map" is the only red thing on the front page, which
   * means the loudest element on screen is chrome rather than content, and it
   * outranks both the wordmark and the title. The hero *is* the map, and its
   * slider is the gesture the page exists to show. Everywhere else the red is
   * right: the reader is reading, and the map is the thing to go and do.
   */
  $: isHome = $page.url.pathname === '/';
  $: quietCta = isHome;

  function closeDrawer() {
    drawerOpen = false;
  }

  function handleDrawerKey(e: KeyboardEvent) {
    if (e.key === 'Escape') closeDrawer();
  }

  onMount(() => {
    if (!/mac/i.test(navigator.platform ?? '')) paletteKey = 'Ctrl K';
    // app.html already put the attribute on <html>; this only re-syncs the
    // store with what it wrote, in case this is a fresh document.
    setTheme($theme);
    document.addEventListener('keydown', handleDrawerKey);
    return () => {
      document.removeEventListener('keydown', handleDrawerKey);
    };
  });

  $: path = $page.url.pathname;
  // One page lights one nav item. The old rules overlapped on /explore, so
  // Catalog and Tools both looked active there.
  $: activeCatalog = path.startsWith('/catalog');
  $: activeAbout = path.startsWith('/about');
  $: activeBlog = path.startsWith('/blog');
  $: activeTools = ['/explore', '/scan', '/contribute', '/admin', '/screens', '/directory'].some(
    (p) => path.startsWith(p)
  );

  $: isStaff = role === 'admin' || role === 'mod';

  $: avatarUrl = session?.user?.user_metadata?.avatar_url as string | undefined;
  $: displayName =
    (session?.user?.user_metadata?.full_name as string | undefined) ?? session?.user?.email ?? '';
  $: initials = displayName
    ? displayName
        .split(' ')
        .map((n: string) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : '?';
</script>

<!-- ─── Main nav bar ─────────────────────────────────────────────── -->
<nav class="top-nav">
  <a href="/" class="nav-logo">VMA</a>

  <!-- Desktop links: what you read stays in the bar -->
  <div class="nav-links">
    <a href="/catalog" class="nav-link" class:active={activeCatalog}>{$t('Catalog')}</a>
    <a href="/about" class="nav-link" class:active={activeAbout}>{$t('About')}</a>
    <a href="/blog" class="nav-link" class:active={activeBlog}>{$t('Blog')}</a>

    <NavDropdown label="Tools" active={activeTools}>
      <a href="/explore" class="dropdown-item" on:click={closeDrawer}>{$t('Map viewer')}</a>
      <a href="/explore?mode=story" class="dropdown-item" on:click={closeDrawer}
        >{$t('Story Builder')}</a
      >
      <a href="/explore?mode=studio" class="dropdown-item" on:click={closeDrawer}>Studio</a>

      <span class="dropdown-rule" role="separator"></span>
      <a href="/contribute" class="dropdown-item" on:click={closeDrawer}>{$t('Contribute')}</a>
      <a href="/contribute/georef" class="dropdown-item" on:click={closeDrawer}
        >{$t('Georeference')}</a
      >
      <a href="/scan?mode=prepare" class="dropdown-item" on:click={closeDrawer}
        >{$t('Prepare a sheet')}</a
      >
      <a href="/scan?mode=text" class="dropdown-item" on:click={closeDrawer}
        >{$t('Check the text')}</a
      >
      <a href="/scan?mode=shapes" class="dropdown-item" on:click={closeDrawer}
        >{$t('Draw shapes')}</a
      >

      {#if isStaff}
        <span class="dropdown-rule" role="separator"></span>
        <a href="/scan?mode=shapes&amp;tab=validate" class="dropdown-item" on:click={closeDrawer}>
          {$t('Review queue')}
        </a>
        <a href="/admin?tab=status" class="dropdown-item" on:click={closeDrawer}
          >{$t('Admin console')}</a
        >
        {#if role === 'admin'}
          <a href="/screens" class="dropdown-item" on:click={closeDrawer}>{$t('Design system')}</a>
        {/if}
      {/if}

      <span class="dropdown-rule" role="separator"></span>
      <a href="/directory" class="dropdown-item is-quiet" on:click={closeDrawer}>All pages →</a>
    </NavDropdown>
  </div>

  <!-- Auth + utils -->
  <div class="nav-auth">
    <button
      type="button"
      class="nav-search"
      class:is-hidden={$pageOwnsSearch}
      on:click={openPalette}
      title="Search ({paletteKey})"
      tabindex={$pageOwnsSearch ? -1 : 0}
      aria-hidden={$pageOwnsSearch}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" />
      </svg>
      <span class="nav-search-label">{$t('Search')}</span>
      <kbd class="nav-search-kbd">{paletteKey}</kbd>
    </button>
    <button
      type="button"
      class="nav-theme"
      on:click={() => setTheme(nextTheme($theme))}
      title={themeLabel($theme)}
      aria-label={themeLabel($theme)}
    >
      {#if $theme === 'light'}
        <!-- sun -->
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="4" />
          <path
            d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"
          />
        </svg>
      {:else}
        <!-- moon -->
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M20 14.5A8.5 8.5 0 019.5 4a7 7 0 108.5 10.5z" />
        </svg>
      {/if}
    </button>
    <!-- The one action the whole site is for. It is inside `Tools ▾` as well,
         but a menu is somewhere to look and this is somewhere to click. -->
    <a href="/explore" class="chip nav-cta" class:is-quiet={quietCta}>{$t('Open the map')}</a>
    {#if session}
      <a href="/profile" class="avatar-pill" title={$t('Your profile')}>
        {#if avatarUrl}
          <img src={avatarUrl} alt={displayName} class="avatar-img" />
        {:else}
          <span class="avatar-initials">{initials}</span>
        {/if}
      </a>
    {:else}
      <!-- Ghost, not another outlined pill: with the front page's CTA quiet the
           two sat side by side as twins and neither read as the action. Signing
           in is a utility — it belongs with the theme toggle, not with "open
           the map". -->
      <a href="/login" class="btn is-ghost signin-link">{$t('Sign in')}</a>
    {/if}
  </div>

  <!-- Hamburger (mobile only) -->
  <button
    class="hamburger"
    type="button"
    aria-label={$t('Open menu')}
    aria-expanded={drawerOpen}
    on:click={() => (drawerOpen = !drawerOpen)}
  >
    <span></span><span></span><span></span>
  </button>
</nav>

<!-- ─── Mobile drawer ────────────────────────────────────────────── -->
{#if drawerOpen}
  <div class="drawer-overlay" role="presentation" on:click={closeDrawer}></div>
  <div class="drawer" role="dialog" aria-modal="true" aria-label={$t('Navigation')}>
    <div class="drawer-header">
      <span class="nav-logo">VMA</span>
      <button
        class="drawer-close"
        type="button"
        aria-label={$t('Close menu')}
        on:click={closeDrawer}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
        >
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>

    <nav class="drawer-nav">
      <a href="/catalog" class="drawer-link" on:click={closeDrawer}>{$t('Catalog')}</a>
      <a href="/about" class="drawer-link" on:click={closeDrawer}>{$t('About')}</a>
      <a href="/blog" class="drawer-link" on:click={closeDrawer}>{$t('Blog')}</a>

      <p class="drawer-section-label">{$t('Tools')}</p>
      <a href="/explore" class="drawer-link" on:click={closeDrawer}>{$t('Map viewer')}</a>
      <a href="/explore?mode=story" class="drawer-link" on:click={closeDrawer}
        >{$t('Story Builder')}</a
      >
      <a href="/explore?mode=studio" class="drawer-link" on:click={closeDrawer}>Studio</a>

      <p class="drawer-section-label">{$t('Contribute')}</p>
      <a href="/contribute" class="drawer-link" on:click={closeDrawer}>{$t('Where to start')}</a>
      <a href="/contribute/georef" class="drawer-link" on:click={closeDrawer}
        >{$t('Georeference')}</a
      >
      <a href="/scan?mode=prepare" class="drawer-link" on:click={closeDrawer}
        >{$t('Prepare a sheet')}</a
      >
      <a href="/scan?mode=text" class="drawer-link" on:click={closeDrawer}>{$t('Check the text')}</a
      >
      <a href="/scan?mode=shapes" class="drawer-link" on:click={closeDrawer}>{$t('Draw shapes')}</a>

      {#if isStaff}
        <p class="drawer-section-label">{$t('Staff')}</p>
        <a href="/scan?mode=shapes&amp;tab=validate" class="drawer-link" on:click={closeDrawer}>
          {$t('Review queue')}
        </a>
        <a href="/admin?tab=status" class="drawer-link" on:click={closeDrawer}
          >{$t('Admin console')}</a
        >
        {#if role === 'admin'}
          <a href="/screens" class="drawer-link" on:click={closeDrawer}>{$t('Design system')}</a>
        {/if}
      {/if}

      <p class="drawer-section-label">{$t('Everything')}</p>
      <a href="/directory" class="drawer-link" on:click={closeDrawer}>{$t('All pages')}</a>
    </nav>

    <div class="drawer-footer">
      {#if session}
        <a href="/profile" class="drawer-link" on:click={closeDrawer}>{$t('Your profile')}</a>
      {:else}
        <a href="/login" class="btn signin-link" on:click={closeDrawer}>{$t('Sign in')}</a>
      {/if}
    </div>
  </div>
{/if}

<style>
  /* Search opener. Reads as a field on desktop so people look for it there,
     and collapses to the icon before the nav links start wrapping. */
  /* Not `display: none`: the bar would reflow as the reader scrolled past the
     hero field and everything to its left would jump. It keeps its box and
     stops being visible or reachable. */
  .nav-search.is-hidden {
    opacity: 0;
    pointer-events: none;
  }

  .nav-search {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.6rem;
    background: var(--color-bg);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    font-family: var(--font-family-base);
    font-size: 0.8rem;
    color: var(--color-text);
    cursor: pointer;
    opacity: 0.75;
    transition:
      opacity 0.1s,
      background-color 0.1s;
  }
  .nav-search:hover {
    opacity: 1;
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
  }
  .nav-search-label {
    padding-right: 0.15rem;
  }
  .nav-search-kbd {
    font-family: var(--font-family-display);
    font-size: 0.62rem;
    font-weight: var(--font-bold);
    padding: 0.05rem 0.28rem;
    border: 1.5px solid currentColor;
    border-radius: 4px;
    opacity: 0.6;
  }
  @media (max-width: 900px) {
    .nav-search-label,
    .nav-search-kbd {
      display: none;
    }
    .nav-search {
      padding: 0.35rem;
    }
  }

  /* Divider between the groups inside Tools. */
  .dropdown-rule {
    display: block;
    height: 1px;
    background: var(--color-gray-300);
    margin: 0.35rem 0.35rem;
  }

  /* Theme toggle: light ⇄ dark. Same weight as the search opener so
     the two read as one cluster of utilities. */
  .nav-theme {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    flex-shrink: 0;
    background: var(--color-bg);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    color: var(--color-text);
    cursor: pointer;
    opacity: 0.75;
    transition:
      opacity 0.1s,
      background-color 0.1s;
  }
  .nav-theme:hover {
    opacity: 1;
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
  }

  /* The way out of the menu, not another tool. */
  .dropdown-item.is-quiet {
    color: var(--color-gray-500);
    font-size: 0.8rem;
  }

  /* ── Dropdown item (inside NavDropdown panel) ── */
  .dropdown-item {
    display: block;
    padding: 0.6rem 0.875rem;
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: 0.875rem;
    text-decoration: none;
    color: var(--color-text);
    border-radius: var(--radius-sm);
    border: 2px solid transparent;
    transition:
      background 0.12s,
      border-color 0.12s;
  }
  .dropdown-item:hover {
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
    border-color: var(--color-border);
  }

  /* ── Auth controls ── */
  /* `.is-ghost` supplies the face; only the link reset is local. */
  .signin-link {
    text-decoration: none;
  }

  .avatar-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    border: var(--border-thin);
    overflow: hidden;
    box-shadow: 2px 2px 0 var(--shadow-ink);
    transition:
      transform 0.1s,
      box-shadow 0.1s;
    flex-shrink: 0;
  }
  .avatar-pill:hover {
    transform: translate(-2px, -2px);
    box-shadow: 4px 4px 0 var(--shadow-ink);
  }
  .avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .avatar-initials {
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: 0.7rem;
    color: var(--color-text-on-yellow);
    background: var(--color-yellow);
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* ── Hamburger (mobile only) ── */
  .hamburger {
    display: none;
    flex-direction: column;
    gap: 4px;
    background: none;
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    padding: 6px 8px;
    cursor: pointer;
    box-shadow: 2px 2px 0 var(--shadow-ink);
  }
  .hamburger span {
    display: block;
    width: 18px;
    height: 2px;
    background: var(--color-text);
    border-radius: 2px;
  }

  /* ── Mobile drawer ── */
  .drawer-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 299;
  }
  .drawer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--color-white);
    border-top: var(--border-thick);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    box-shadow: 0 -4px 0 var(--color-border);
    z-index: 300;
    padding: 0 1.25rem 2rem;
    max-height: 85vh;
    overflow-y: auto;
  }
  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 0 0.75rem;
    border-bottom: var(--border-thin);
    margin-bottom: 1rem;
  }
  .drawer-close {
    background: none;
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    padding: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 2px 2px 0 var(--shadow-ink);
  }
  .drawer-nav {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }
  .drawer-section-label {
    font-family: var(--font-family-display);
    font-weight: var(--font-extrabold);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-gray-500);
    margin: 1rem 0 0.25rem;
    padding: 0;
  }
  .drawer-link {
    display: block;
    padding: 0.625rem 0.75rem;
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
    font-size: 1rem;
    text-decoration: none;
    color: var(--color-text);
    border-radius: var(--radius-sm);
    border: 2px solid transparent;
    transition:
      background 0.12s,
      border-color 0.12s;
  }
  .drawer-link:hover {
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
    border-color: var(--color-border);
  }
  .drawer-footer {
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: var(--border-thin);
  }

  /* ── Responsive ── */
  @media (max-width: 640px) {
    .hamburger {
      display: flex;
    }
  }
</style>
