<script lang="ts">
  import { t, splitHighlight } from '$lib/core/i18n';
  import { onMount } from 'svelte';

  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import PageHero from '$lib/ui/PageHero.svelte';

  $: heroTitle = splitHighlight($t('All the pages, **one list.**'));
  import {
    DESTINATION_GROUPS,
    DESTINATIONS,
    destinationsFor,
  } from '$lib/features/shared/paletteDestinations';

  const { session, supabase } = getSupabaseContext();

  let role: string | null = null;

  onMount(async () => {
    role = await fetchUserRole(supabase, session?.user?.id);
  });

  // The same list the command palette offers, gated the same way, minus this
  // page — a directory that lists itself is a hall of mirrors.
  $: visible = destinationsFor(role, !!session?.user).filter((d) => d.href !== '/directory');
  $: groups = DESTINATION_GROUPS.map((name) => ({
    name,
    items: visible.filter((d) => d.group === name),
  })).filter((g) => g.items.length > 0);

  $: hiddenCount = DESTINATIONS.length - 1 - visible.length;
</script>

<svelte:head>
  <title>All pages — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Every page in the Vietnam Map Archive in one list: the catalog, the map viewer, the contribution tools, and the writing."
  />
</svelte:head>

<div class="page directory-page">
  <PageHero
    eyebrow="Directory"
    sub="Every page in the archive, in one list. The same list ⌘K searches — so if you would rather type than click, press it from anywhere."
  >
    <svelte:fragment slot="title">
      {heroTitle[0]}{#if heroTitle[1]}<br /><span class="text-highlight">{heroTitle[1]}</span
        >{/if}{heroTitle[2]}
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    {#each groups as group (group.name)}
      <section class="section-card">
        <div class="section-card-header">
          <h2 class="section-title-sm">{group.name}</h2>
        </div>
        <ul class="dir-list">
          {#each group.items as d (d.href)}
            <li>
              <a href={d.href} class="dir-row">
                <span class="dir-label">{d.label}</span>
                <span class="dir-hint">{d.hint}</span>
                <code class="dir-href">{d.href}</code>
              </a>
            </li>
          {/each}
        </ul>
      </section>
    {/each}

    {#if hiddenCount > 0}
      <p class="dir-note">
        {hiddenCount}
        {hiddenCount === 1 ? 'page is' : 'pages are'} not listed because this account cannot open
        {hiddenCount === 1 ? 'it' : 'them'}.
        {#if !session?.user}<a href="/login">{$t('Sign in')}</a> to see the contribution tools.{/if}
      </p>
    {/if}
  </main>
</div>

<style>
  /* .section-card-header is sized for a title plus a paragraph; here it holds
     one word, so the gap below it comes back down. */
  .directory-page :global(.section-card-header) {
    margin-bottom: 0.35rem;
  }

  .dir-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .dir-row {
    display: grid;
    grid-template-columns: minmax(9rem, 14rem) 1fr auto;
    align-items: baseline;
    gap: 0.75rem;
    padding: 0.6rem 0.5rem;
    text-decoration: none;
    color: var(--color-text);
    border: 2px solid transparent;
    border-radius: var(--radius-sm);
    transition:
      background 0.12s,
      border-color 0.12s;
  }
  .dir-row:hover {
    background: var(--color-yellow);
    color: var(--color-text-on-yellow);
    border-color: var(--color-border);
  }

  .dir-label {
    font-family: var(--font-family-display);
    font-weight: var(--font-bold);
  }
  .dir-hint {
    font-size: 0.875rem;
    color: var(--color-gray-500);
  }
  .dir-href {
    font-size: 0.75rem;
    color: var(--color-gray-500);
  }

  .dir-note {
    font-size: 0.875rem;
    color: var(--color-gray-500);
  }

  /* On a phone the three columns stack; the URL is the least useful, so it goes. */
  @media (max-width: 640px) {
    .dir-row {
      grid-template-columns: 1fr;
      gap: 0.15rem;
    }
    .dir-href {
      display: none;
    }
  }
</style>
