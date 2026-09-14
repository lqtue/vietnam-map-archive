<!--
  CatalogDetailDrawer — side panel that shows full metadata for a map and
  three primary actions (Map / Image / Studio).
  Open by setting `item`; close fires `close` event (parent should null out the binding).
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { mapHref, exploreHref, mapRef } from '$lib/core/utils/mapSlug';
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';

  export let item: any | null = null;
  /** Staff get an Edit action that opens the admin map editor. */
  export let role: 'user' | 'mod' | 'admin' = 'user';

  const dispatch = createEventDispatcher();

  $: open = !!item;

  function close() {
    dispatch('close');
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) close();
  }
  onMount(() => window.addEventListener('keydown', onKey));
  onDestroy(() => typeof window !== 'undefined' && window.removeEventListener('keydown', onKey));

  $: isScout = item?._table === 'scout';
  $: canEdit = item && !isScout && (role === 'admin' || role === 'mod');
  $: canMap = item && !isScout && item.georef_done;
  $: canAnnotate = item && !isScout && item.georef_done;

  function statusLabel(): string {
    if (!item) return '';
    if (isScout) return '✨ Scout queue';
    return item.georef_done ? 'Available on map' : 'Image only';
  }

  // Metadata rows in display order. Filter out empties before render.
  $: fields = item
    ? ([
        ['Original title', item.original_title],
        ['Creator', item.creator],
        ['Publisher', item.dc_publisher],
        ['Year', item.year_label || item.year],
        ['Area', item.location],
        ['Type', item.map_type],
        ['Collection', item.collection],
        ['Holding institution', item.holding_institution],
        ['Shelfmark', item.shelfmark],
        ['Physical', item.physical_description],
        ['Rights', item.rights],
        ['Language', item.language],
        ['Source URL', item.source_url],
        ['Allmaps ID', item.allmaps_id],
      ].filter(([_, v]) => v != null && v !== '') as [string, string][])
    : [];
</script>

{#if open && item}
  <div class="drawer-backdrop" on:click={close} role="presentation"></div>
  <div class="drawer" role="dialog" aria-label="Map details">
    <header class="drawer-head">
      <h2 class="drawer-title">{item.name}</h2>
      <button class="btn is-icon dr-close" on:click={close} aria-label={$t('Close')}>×</button>
    </header>

    {#if item.thumbnail}
      <div class="thumb-wrap">
        <img src={item.thumbnail} alt={item.name} loading="lazy" />
      </div>
    {/if}

    <div class="badge-chip status-pill">{statusLabel()}</div>

    {#if item.dc_description}
      <p class="description">{item.dc_description}</p>
    {/if}

    <dl class="meta">
      {#each fields as [k, v] (k)}
        <div class="meta-row">
          <dt>{k}</dt>
          <dd>
            {#if k === 'Source URL'}
              <a href={v} target="_blank" rel="noopener">{v}</a>
            {:else}
              {v}
            {/if}
          </dd>
        </div>
      {/each}
    </dl>

    <div class="actions">
      {#if canEdit}
        <button type="button" class="chip act" on:click={() => dispatch('edit', item)}
          >✎ Edit</button
        >
      {/if}
      {#if canMap}
        <a class="chip is-primary act" href={exploreHref(item)}>{$t('Map')}</a>
      {/if}

      {#if canAnnotate}
        <a class="chip act" href="/explore?mode=studio&map={mapRef(item)}">✏️ Studio</a>
      {/if}
      <!-- One chip, not two: "Image" pointed at /scan?map= and "Share page" at
           /catalog/[id], and those became the same page. A draft is included —
           it resolves there for a signed-in reader, and the drawer only ever
           lists rows this reader can already see. -->
      {#if !isScout}
        <a class="chip act" href={mapHref(item)}>{$t('Sheet page')}</a>
      {/if}
      {#if isScout && (item._scout?.source_url || item._scout?.manifest_url)}
        <a
          class="chip is-primary act"
          href={item._scout.source_url || item._scout.manifest_url}
          target="_blank"
          rel="noopener">↗ Open source</a
        >
      {/if}
    </div>
  </div>
{/if}

<style>
  .drawer-backdrop {
    position: fixed;
    inset: 0;
    background: var(--sb-scrim);
    /* Over `.top-nav`, which is sticky at 100 (editorial.css). At 50 the scrim
       stopped at the nav's bottom edge and left it lit and clickable above an
       open modal — so the page behind could be navigated away from without the
       drawer ever closing. Under NavBar's own fixed 299/300, which is its
       mobile menu and never open at the same time as this. */
    z-index: 150;
    animation: fade 0.15s ease-out;
  }
  .drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(460px, 100vw);
    background: var(--color-white);
    border-left: 2.5px solid var(--color-border);
    box-shadow: -6px 0 0 var(--color-border);
    z-index: 151;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    animation: slidein 0.18s ease-out;
    font-family: var(--font-family-base);
  }
  .drawer-head {
    position: sticky;
    top: 0;
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    background: var(--sb-head-bg);
    border-bottom: var(--border-thin);
    z-index: 1;
  }
  .drawer-title {
    flex: 1;
    margin: 0;
    font-family: var(--font-family-display);
    font-weight: var(--font-extrabold);
    font-size: 1.1rem;
    line-height: 1.25;
  }
  /* Size only — the round face and hover are `.btn.is-icon`. 32px, not the 48px
     map control: it sits on the drawer's header line beside the title. */
  .dr-close {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    font-size: 1.3rem;
    line-height: 1;
  }

  .thumb-wrap {
    padding: 1.25rem 1.25rem 0;
  }
  .thumb-wrap img {
    width: 100%;
    max-height: 280px;
    object-fit: contain;
    background: var(--sb-thumb-bg);
    border: 1.5px solid var(--color-border);
    border-radius: var(--radius-sm);
    display: block;
  }
  /* A badge, not a control — it states what the sheet is, and nothing happens
     when you press it. Placement and the soft tint are all that stay local:
     the shared `.chip-yellow` is a white face, which reads as no badge at all. */
  .status-pill {
    margin: 1rem 1.25rem 0;
    align-self: flex-start;
    background: var(--sb-accent-yellow);
  }
  .description {
    margin: 1rem 1.25rem 0;
    font-size: 0.92rem;
    line-height: 1.5;
    color: var(--sb-text-meta);
  }
  .meta {
    margin: 1rem 0 0;
    padding: 0 1.25rem;
  }
  .meta-row {
    display: grid;
    grid-template-columns: 7rem 1fr;
    gap: 0.6rem;
    padding: 0.4rem 0;
    border-bottom: var(--sb-border-soft);
    font-size: 0.85rem;
  }
  .meta-row:last-child {
    border-bottom: none;
  }
  .meta-row dt {
    font-weight: var(--font-bold);
    color: var(--sb-text-meta);
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    align-self: center;
  }
  .meta-row dd {
    margin: 0;
    color: var(--color-text);
    word-break: break-word;
  }
  .meta-row dd a {
    color: var(--sb-accent);
  }

  .actions {
    position: sticky;
    bottom: 0;
    margin-top: auto;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 1rem 1.25rem;
    background: var(--sb-head-bg);
    border-top: var(--border-thin);
  }
  /* Width only: the actions share the footer row equally and wrap together.
     Everything else is `.chip` / `.chip.primary`. */
  .act {
    flex: 1;
    min-width: 110px;
  }

  @keyframes slidein {
    from {
      transform: translateX(20px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  @keyframes fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @media (max-width: 600px) {
    .drawer {
      width: 100vw;
      border-left: none;
      box-shadow: none;
    }
  }
</style>
