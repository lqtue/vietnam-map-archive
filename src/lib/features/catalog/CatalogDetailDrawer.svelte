<!--
  CatalogDetailDrawer — side panel that shows full metadata for a map and
  three primary actions (Map / Image / Annotate).
  Open by setting `item`; close fires `close` event (parent should null out the binding).
-->
<script lang="ts">
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
  $: canImage = item && !isScout && item.iiif_image;
  $: canAnnotate = item && !isScout && item.georef_done;

  function statusLabel(): string {
    if (!item) return '';
    if (isScout) return '✨ Scout queue';
    return item.georef_done ? '🌍 Available on map' : '🖼️ Image only';
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
      <button class="close-btn" on:click={close} aria-label="Close">×</button>
    </header>

    {#if item.thumbnail}
      <div class="thumb-wrap">
        <img src={item.thumbnail} alt={item.name} loading="lazy" />
      </div>
    {/if}

    <div class="status-pill">{statusLabel()}</div>

    {#if item.dc_description}
      <p class="description">{item.dc_description}</p>
    {/if}

    <dl class="meta">
      {#each fields as [k, v]}
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
        <button type="button" class="act" on:click={() => dispatch('edit', item)}>✎ Edit</button>
      {/if}
      {#if canMap}
        <a class="act primary" href="/explore?map={item.id}">🌍 Map</a>
      {/if}
      {#if canImage}
        <a class="act" href="/scan?map={item.id}">🖼️ Image</a>
      {/if}
      {#if canAnnotate}
        <a class="act" href="/explore?mode=annotate?map={item.id}">✏️ Studio</a>
      {/if}
      {#if !isScout && (item.status === 'public' || item.status === 'featured')}
        <a class="act" href="/archive/{item.id}">🔗 Share page</a>
      {/if}
      {#if isScout && (item._scout?.source_url || item._scout?.manifest_url)}
        <a
          class="act primary"
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
    z-index: 50;
    animation: fade 0.15s ease-out;
  }
  .drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(460px, 100vw);
    background: var(--ground-raised);
    border-left: 2.5px solid var(--rule);
    box-shadow: -6px 0 0 var(--rule);
    z-index: 51;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    animation: slidein 0.18s ease-out;
    font-family: var(--font-body);
  }
  .drawer-head {
    position: sticky;
    top: 0;
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    background: var(--sb-head-bg);
    border-bottom: var(--rule-hair) solid var(--rule);
    z-index: 1;
  }
  .drawer-title {
    flex: 1;
    margin: 0;
    font-family: var(--font-display);
    font-weight: var(--w-semi);
    font-size: 1.1rem;
    line-height: 1.25;
  }
  .close-btn {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    background: var(--ground-raised);
    border: 1.5px solid var(--rule);
    border-radius: var(--radius-pill);
    font-size: 1.3rem;
    line-height: 1;
    font-weight: var(--w-semi);
    cursor: pointer;
    padding: 0;
  }
  .close-btn:hover {
    background: var(--ink);
    color: var(--ground-raised);
  }

  .thumb-wrap {
    padding: 1.25rem 1.25rem 0;
  }
  .thumb-wrap img {
    width: 100%;
    max-height: 280px;
    object-fit: contain;
    background: var(--sb-thumb-bg);
    border: 1.5px solid var(--rule);
    border-radius: var(--radius);
    display: block;
  }
  .status-pill {
    margin: 1rem 1.25rem 0;
    padding: 0.35rem 0.8rem;
    align-self: flex-start;
    background: var(--sb-accent-yellow);
    border: 1.5px solid var(--rule);
    border-radius: var(--radius-pill);
    font-size: 0.8rem;
    font-weight: var(--w-semi);
    display: inline-block;
    width: fit-content;
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
    font-weight: var(--w-semi);
    color: var(--sb-text-meta);
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    align-self: center;
  }
  .meta-row dd {
    margin: 0;
    color: var(--ink);
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
    border-top: var(--rule-hair) solid var(--rule);
  }
  .act {
    flex: 1;
    min-width: 110px;
    padding: 0.65rem 0.9rem;
    background: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    font: inherit;
    font-weight: var(--w-semi);
    font-size: 0.9rem;
    text-decoration: none;
    color: var(--ink);
    text-align: center;
    cursor: pointer;
    transition:
      transform 0.1s,
      box-shadow 0.1s;
  }
  .act:hover {
    transform: translate(-1px, -1px);
    box-shadow: 3px 3px 0 var(--rule);
  }
  .act.primary {
    background: var(--ink);
    color: var(--ground-raised);
  }
  .act.primary:hover {
    background: var(--sb-text-meta);
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
