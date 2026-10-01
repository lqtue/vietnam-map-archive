<script lang="ts">
  import { t, splitHighlight } from '$lib/core/i18n';
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import PageHero from '$lib/ui/PageHero.svelte';
  import { fetchUserRole } from '$lib/data/supabase/role';

  $: heroTitle = splitHighlight($t('Pin a map **to the world.**'));
  import {
    allmapsEditorUrl,
    fetchGeorefQueue,
    fetchGeorefFixList,
    type GeorefMapItem,
    type GeorefFixItem,
  } from '$lib/data/maps/georef';

  const { supabase, session } = getSupabaseContext();

  let maps: GeorefMapItem[] = [];
  let fixable: GeorefFixItem[] = [];
  let role: 'user' | 'mod' | 'admin' = 'user';
  let loading = true;
  let fixSearch = '';

  onMount(async () => {
    [maps, role] = await Promise.all([
      fetchGeorefQueue(supabase),
      fetchUserRole(supabase, session?.user?.id).then((r) => r ?? 'user'),
    ]);
    // Same gate as the share page's "Fix georeference" button.
    if (role === 'admin' || role === 'mod') fixable = await fetchGeorefFixList(supabase);
    loading = false;
  });

  $: pending = maps.filter((m) => !m.georef_done);
  $: canFix = role === 'admin' || role === 'mod';
  $: fixShown = (() => {
    const q = fixSearch.trim().toLowerCase();
    if (!q) return fixable;
    return fixable.filter(
      (m) => m.name.toLowerCase().includes(q) || String(m.year ?? '').includes(q)
    );
  })();
</script>

<svelte:head>
  <title>Georeference a map — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Pin a historical map to real-world coordinates in the Allmaps Editor. No specialist software — just a browser."
  />
</svelte:head>

<div class="page">
  <PageHero
    sub="Place control points in the Allmaps Editor to anchor each map to real-world coordinates. No specialist software needed — just a browser."
  >
    <svelte:fragment slot="eyebrow"
      ><a href="/contribute" class="chip-back">← Contribute</a></svelte:fragment
    >
    <svelte:fragment slot="title">
      {heroTitle[0]}{#if heroTitle[1]}<br /><span class="text-highlight">{heroTitle[1]}</span
        >{/if}{heroTitle[2]}
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <section class="section-card how-to-card">
      <div class="section-card-header">
        <div>
          <h2 class="section-title-sm">{$t('How it works')}</h2>
        </div>
      </div>
      <ol class="steps-list">
        <li>Pick a map below and hit <strong>{$t('Open in Allmaps')}</strong>.</li>
        <li>
          {$t(
            'Drop at least 3 ground control points — match a spot on the map to the same spot on the modern world.'
          )}
        </li>
        <li>
          {$t(
            'Save in Allmaps. Nothing to send back: the archive checks Allmaps for finished maps and marks them georeferenced by itself.'
          )}
        </li>
      </ol>
    </section>

    {#if loading}
      <section class="state-card">
        <div class="spinner"></div>
        <span>{$t('Loading maps…')}</span>
      </section>
    {:else}
      <section class="section-card">
        <h2 class="section-label">
          {$t('Needs georeferencing')} <span class="count-badge">{pending.length}</span>
        </h2>
        {#if pending.length === 0}
          <p class="empty-state">
            {$t('Every map is georeferenced. Check back later — new ones land every few weeks.')}
          </p>
        {:else}
          <ul class="map-list">
            {#each pending as map (map.id)}
              <li class="map-row">
                <div class="map-meta">
                  <span class="map-name">{map.name}</span>
                  {#if map.year}<span class="map-year">{map.year}</span>{/if}
                </div>
                <a class="chip" href={allmapsEditorUrl(map)} target="_blank" rel="noopener">
                  {$t('Open in Allmaps')}
                </a>
              </li>
            {/each}
          </ul>
        {/if}
      </section>

      {#if canFix}
        <section class="section-card">
          <h2 class="section-label">
            {$t('Fix an existing georeference')}
            <span class="count-badge chip-green">{fixable.length}</span>
          </h2>
          <p class="fix-help">
            Reopens the map's control points in Allmaps so you correct them rather than start over.
            Same button as the share page, without having to know the map's id.
          </p>
          <input
            class="fix-search"
            type="search"
            placeholder={$t('Find by name or year…')}
            bind:value={fixSearch}
            aria-label="Find a georeferenced map"
          />
          {#if fixShown.length === 0}
            <p class="empty-state">{$t('No georeferenced map matches.')}</p>
          {:else}
            <ul class="map-list done-list">
              {#each fixShown as map (map.id)}
                <li class="map-row done">
                  <div class="map-meta">
                    <span class="map-name">{map.name}</span>
                    {#if map.year}<span class="map-year">{map.year}</span>{/if}
                    {#if map.status === 'draft'}<span class="map-year">draft</span>{/if}
                  </div>
                  {#if map.editorUrl}
                    <a class="chip" href={map.editorUrl} target="_blank" rel="noopener">
                      {$t('Fix in Allmaps')}
                    </a>
                  {:else if map.pipelineMade}
                    <span
                      class="badge-chip is-sm"
                      title={$t(
                        'Georeference made by our pipeline (scripts/indochine100k_georef.py), not on Allmaps. Fix it by re-running the pipeline; an edit in Allmaps would be overwritten.'
                      )}>{$t('Pipeline-maintained')}</span
                    >
                  {:else}
                    <span
                      class="badge-chip is-sm"
                      title="R2-only source and no manifest: the editor has nothing to open"
                      >{$t('no source')}</span
                    >
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {/if}
    {/if}
  </main>
</div>

<style>
  .fix-help {
    margin: 0 0 0.75rem;
    font-size: 0.9rem;
    opacity: 0.75;
  }
  .fix-search {
    width: 100%;
    box-sizing: border-box;
    margin-bottom: 0.75rem;
    padding: 0.5rem 0.75rem;
    font: inherit;
    border: var(--border-thin);
    border-radius: var(--radius-md);
    background: var(--color-white);
    color: var(--color-text);
  }
  :global(body) {
    margin: 0;
    background-color: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-family-base);
  }

  .chip-back {
    color: inherit;
    text-decoration: none;
    font-weight: 600;
  }
  .chip-back:hover {
    text-decoration: underline;
  }

  .section-label {
    font-family: var(--font-family-display);
    font-size: 0.8125rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text);
    opacity: 0.5;
    margin: 0 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .count-badge {
    font-size: 0.75rem;
    font-weight: 700;
    background: var(--color-border);
    color: var(--color-white);
    padding: 0.1rem 0.5rem;
    border-radius: var(--radius-pill);
    opacity: 1;
  }

  .count-badge.chip-green {
    background: var(--color-green);
    color: var(--color-on-accent);
  }

  .steps-list {
    margin: 0;
    padding-left: 1.5rem;
    color: var(--color-text);
    line-height: 1.8;
    font-size: 0.9375rem;
  }

  .steps-list li {
    margin-bottom: 0.25rem;
  }

  .map-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .map-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.875rem 1rem;
    background: var(--color-white);
    border: var(--border-thin);
    border-radius: var(--radius-sm);
  }

  .map-row.done {
    background: color-mix(in srgb, var(--color-green) 8%, var(--color-white));
    border-color: var(--color-green);
  }

  .map-meta {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    min-width: 0;
  }

  .map-name {
    font-weight: 600;
    font-size: 0.9375rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .map-year {
    font-size: 0.8125rem;
    color: var(--color-text);
    opacity: 0.5;
    flex-shrink: 0;
  }

  .state-card {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 3rem;
    border: var(--border-thin);
    border-radius: var(--radius-md);
    color: var(--color-text);
    opacity: 0.6;
  }
</style>
