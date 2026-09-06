<!--
  NavBar.svelte — the sheet's running head.

  It lives in the MARGIN, so it is set the way a margin is: mono, small, upper,
  quiet. It never competes with the field.

  There are no dropdowns and no drawer any more. There used to be three menus
  over twelve destinations; the route merge left six, and six flat links fit.
  On a narrow screen the strip scrolls sideways rather than folding into a
  panel — one behaviour instead of two.

  The search button flips the store in core/utils and nothing else: NavBar is
  in `ui`, which the layering rule bars from importing `features`, and the
  palette itself is mounted once by the root layout.
-->
<script lang="ts">
  import type { Session } from '@supabase/supabase-js';
  import { page } from '$app/stores';
  import { openPalette } from '$lib/core/utils/commandPalette';

  // ui/ is domain-free (layering rule): the layout that mounts NavBar passes
  // the session in.
  export let session: Session | null = null;

  const LINKS = [
    { href: '/archive', label: 'Archive' },
    { href: '/explore', label: 'Explore' },
    { href: '/scan', label: 'Scan' },
    { href: '/contribute', label: 'Contribute' },
    { href: '/about', label: 'About' },
    { href: '/blog', label: 'Blog' },
  ];

  $: path = $page.url.pathname;

  /** '/archive' matches '/archive/place/thi-nghe'; '/' matches only itself. */
  function isCurrent(href: string): boolean {
    return path === href || path.startsWith(href + '/');
  }

  $: displayName =
    (session?.user?.user_metadata?.full_name as string | undefined) ?? session?.user?.email ?? '';
  $: avatarUrl = session?.user?.user_metadata?.avatar_url as string | undefined;
  $: initials = displayName
    ? displayName
        .split(' ')
        .map((n: string) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : '?';
</script>

<nav class="nav" aria-label="Main">
  <a href="/" class="nav__mark" aria-label="Vietnam Map Archive, home">VMA</a>

  <ul class="nav__links">
    {#each LINKS as link (link.href)}
      <li>
        <a href={link.href} aria-current={isCurrent(link.href) ? 'page' : undefined}>
          {link.label}
        </a>
      </li>
    {/each}
  </ul>

  <div class="nav__end">
    <button type="button" class="nav__search" on:click={openPalette}>
      Search
      <kbd>⌘K</kbd>
    </button>

    {#if session}
      <a href="/profile" class="nav__avatar" title={displayName || 'Your profile'}>
        {#if avatarUrl}
          <img src={avatarUrl} alt="" />
        {:else}
          <span>{initials}</span>
        {/if}
      </a>
    {:else}
      <a href="/login" class="nav__signin">Sign in</a>
    {/if}
  </div>
</nav>

<style>
  /* Inherits the margin's mono/upper/letterspaced treatment from .sheet__margin
     rather than restating it, so the nav and the scale bar always match. */
  .nav {
    display: flex;
    align-items: baseline;
    gap: var(--s-4);
    min-width: 0;
    width: 100%;
  }

  .nav__mark {
    font-family: var(--font-display);
    font-size: var(--t-sm);
    font-weight: var(--w-semi);
    letter-spacing: 0.02em;
    text-transform: none;
    color: var(--ink);
    flex-shrink: 0;
  }

  .nav__links {
    display: flex;
    align-items: baseline;
    gap: var(--s-3);
    list-style: none;
    margin: 0;
    padding: 0;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .nav__links::-webkit-scrollbar {
    display: none;
  }

  .nav__links a {
    display: block;
    padding-bottom: 2px;
    white-space: nowrap;
    color: var(--ink-soft);
    border-bottom: var(--rule-hair) solid transparent;
    transition:
      color var(--ease),
      border-color var(--ease);
  }

  .nav__links a:hover {
    color: var(--ink);
    text-decoration: none;
  }

  /* The current page is marked by a rule under it, the way a running head is
     ruled off from the text block. */
  .nav__links a[aria-current='page'] {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }

  .nav__end {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    margin-left: auto;
    flex-shrink: 0;
  }

  .nav__search {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    padding: 0;
    font: inherit;
    color: var(--ink-soft);
    background: none;
    border: 0;
    cursor: pointer;
    transition: color var(--ease);
  }

  .nav__search:hover {
    color: var(--accent);
  }

  .nav__search kbd {
    font-size: var(--t-2xs);
    padding: 1px var(--s-1);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
  }

  .nav__signin {
    color: var(--accent);
  }

  .nav__avatar {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    overflow: hidden;
    border-radius: 50%;
    border: var(--rule-hair) solid var(--rule);
    font-size: var(--t-2xs);
    color: var(--ink-soft);
    align-self: center;
  }

  .nav__avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  @media (max-width: 600px) {
    .nav {
      gap: var(--s-3);
    }

    /* Sign-in stays; the shortcut hint does not — there is no ⌘ to press. */
    .nav__search kbd {
      display: none;
    }
  }
</style>
