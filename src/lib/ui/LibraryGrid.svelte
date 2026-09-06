<!--
  LibraryGrid.svelte — the "my projects" landing screen shared by /explore?mode=story and
  /explore?mode=annotate: hero + loading state + empty state + card grid + rename/delete
  actions + the name dialog used for both create and rename.

  Per-item chrome (meta chips, description line, extra actions) comes in via
  slots so each tool keeps its own copy.
-->
<script lang="ts" generics="T extends { id: string; title: string }">
  import { createEventDispatcher } from 'svelte';
  import '$styles/components/library.css';
  import PageHero from './PageHero.svelte';
  import NameDialog from './NameDialog.svelte';
  import CatalogGrid from '$lib/ui/CatalogGrid.svelte';
  import CatalogCard from '$lib/ui/CatalogCard.svelte';

  const dispatch = createEventDispatcher<{
    select: { item: T };
    create: { title: string; description?: string };
    rename: { item: T; title: string; description?: string };
    remove: { item: T };
  }>();

  export let items: T[] = [];
  export let loading = false;
  /** Capitalised singular used in the dialog headings ("New Story"). */
  export let noun = 'Item';
  export let eyebrow = 'Tools';
  export let sub = '';
  export let thumbIcon = '📄';
  export let createLabel = '+ New';
  export let emptyCtaLabel = 'Create';
  export let emptyTitle = '';
  export let emptyText = '';
  /** Hides the create buttons (e.g. the editor is desktop-only). */
  export let showCreate = true;
  /** Hides the per-card rename/delete buttons. */
  export let showItemActions = true;
  /** When set, the dialog also edits a description and prefills it from here. */
  export let descriptionOf: ((item: T) => string) | null = null;

  let dialogOpen = false;
  let dialogHeading = '';
  let dialogValue = '';
  let dialogDescription = '';
  let editing: T | null = null;

  function openCreate() {
    editing = null;
    dialogValue = '';
    dialogDescription = '';
    dialogHeading = `New ${noun}`;
    dialogOpen = true;
  }

  function openRename(item: T) {
    editing = item;
    dialogValue = item.title;
    dialogDescription = descriptionOf ? descriptionOf(item) : '';
    dialogHeading = `Rename ${noun}`;
    dialogOpen = true;
  }

  function handleSubmit(event: CustomEvent<{ title: string; description?: string }>) {
    const { title, description } = event.detail;
    dialogOpen = false;
    if (editing) dispatch('rename', { item: editing, title, description });
    else dispatch('create', { title, description });
    editing = null;
  }

  function confirmRemove(item: T) {
    if (confirm(`Delete "${item.title}"?`)) dispatch('remove', { item });
  }
</script>

<div class="page">
  <PageHero {eyebrow} {sub}>
    <svelte:fragment slot="title"><slot name="title" /></svelte:fragment>
    <div slot="actions">
      {#if showCreate}
        <button type="button" class="action-btn primary-btn" on:click={openCreate}
          >{createLabel}</button
        >
      {/if}
    </div>
  </PageHero>

  <slot name="banner" />

  <main class="editorial-main">
    {#if loading}
      <div class="library-loading">
        <div class="spinner"></div>
        <span>Loading…</span>
      </div>
    {:else if items.length === 0}
      <div class="library-empty">
        <svg
          width="64"
          height="64"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#d4af37"
          stroke-width="1.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <path d="M12 18v-6M9 15h6" />
        </svg>
        <h2 class="empty-title">{emptyTitle}</h2>
        <p class="empty-text">{emptyText}</p>
        {#if showCreate}
          <button type="button" class="library-create-btn large" on:click={openCreate}>
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
            {emptyCtaLabel}
          </button>
        {/if}
      </div>
    {:else}
      <CatalogGrid>
        {#each items as item (item.id)}
          <CatalogCard title={item.title} on:click={() => dispatch('select', { item })}>
            <div slot="thumb" class="story-thumb-placeholder">
              <span class="story-icon">{thumbIcon}</span>
            </div>
            <div slot="meta" class="meta"><slot name="meta" {item} /></div>
            <div slot="description" class="description"><slot name="description" {item} /></div>
            <div slot="actions">
              <slot name="item-actions" {item} />
              {#if showItemActions}
                <button
                  type="button"
                  class="btn-icon-edit"
                  title="Rename"
                  on:click|stopPropagation={() => openRename(item)}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                  >
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                <button
                  type="button"
                  class="btn-icon-delete"
                  title="Delete"
                  on:click|stopPropagation={() => confirmRemove(item)}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                  >
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                    <path d="M10 11v6M14 11v6" />
                  </svg>
                </button>
              {/if}
            </div>
          </CatalogCard>
        {/each}
      </CatalogGrid>
    {/if}
  </main>
</div>

<NameDialog
  open={dialogOpen}
  bind:value={dialogValue}
  showDescription={!!descriptionOf}
  bind:descriptionValue={dialogDescription}
  heading={dialogHeading}
  on:submit={handleSubmit}
  on:close={() => (dialogOpen = false)}
/>
