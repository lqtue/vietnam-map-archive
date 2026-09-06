<!--
  GeorefQueue.svelte — the georeference worklist, shown on /contribute.

  Georeferencing is the one contribution task with no canvas of its own: it
  hands off to the Allmaps Editor and waits for the annotation to come back.
  So it lives on the on-ramp page rather than in /scan with the four tools
  that do own a canvas.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import PageHero from '$lib/ui/PageHero.svelte';
  import { fetchUserRole } from '$lib/data/supabase/role';
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
  let mounted = false;
  let fixSearch = '';

  onMount(async () => {
    mounted = true;
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

<div class="page" class:mounted>
  <PageHero
    sub="Place control points in the Allmaps Editor to anchor each map to real-world coordinates. No specialist software needed — just a browser."
  >
    <svelte:fragment slot="eyebrow"
      ><a href="/contribute" class="chip-back">← Contribute</a></svelte:fragment
    >
    <svelte:fragment slot="title">
      Pin a map<br />
      <span class="text-highlight">to the world.</span>
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <section class="section-card how-to-card">
      <div class="section-card-header">
        <div class="icon-blob color-blue">📖</div>
        <div>
          <h2 class="section-title-sm">How it works</h2>
        </div>
      </div>
      <ol class="steps-list">
        <li>Pick a map below and hit <strong>Open in Allmaps</strong>.</li>
        <li>
          Drop at least 3 ground control points — match a spot on the map to the same spot on the
          modern world.
        </li>
        <li>
          Save in Allmaps. Nothing to send back: the archive checks Allmaps for finished maps and
          marks them georeferenced by itself.
        </li>
      </ol>
    </section>

    {#if loading}
      <section class="state-card">
        <div class="spinner"></div>
        <span>Loading maps…</span>
      </section>
    {:else}
      <section class="section-card">
        <h2 class="section-label">
          Needs georeferencing <span class="count-badge">{pending.length}</span>
        </h2>
        {#if pending.length === 0}
          <p class="empty-msg">
            Every map is georeferenced. Check back later — new ones land every few weeks.
          </p>
        {:else}
          <ul class="map-list">
            {#each pending as map (map.id)}
              <li class="map-row">
                <div class="map-meta">
                  <span class="map-name">{map.name}</span>
                  {#if map.year}<span class="map-year">{map.year}</span>{/if}
                </div>
                <a
                  class="action-btn secondary-btn map-btn"
                  href={allmapsEditorUrl(map)}
                  target="_blank"
                  rel="noopener"
                >
                  Open in Allmaps →
                </a>
              </li>
            {/each}
          </ul>
        {/if}
      </section>

      {#if canFix}
        <section class="section-card">
          <h2 class="section-label">
            Fix an existing georeference <span class="count-badge chip-green">{fixable.length}</span
            >
          </h2>
          <p class="fix-help">
            Reopens the map's control points in Allmaps so you correct them rather than start over.
            Same button as the share page, without having to know the map's id.
          </p>
          <input
            class="fix-search"
            type="search"
            placeholder="Find by name or year…"
            bind:value={fixSearch}
            aria-label="Find a georeferenced map"
          />
          {#if fixShown.length === 0}
            <p class="empty-msg">No georeferenced map matches.</p>
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
                    <a
                      class="action-btn secondary-btn map-btn"
                      href={map.editorUrl}
                      target="_blank"
                      rel="noopener"
                    >
                      Fix in Allmaps →
                    </a>
                  {:else}
                    <span
                      class="badge-chip done-chip"
                      title="R2-only source and no manifest: the editor has nothing to open"
                      >no source</span
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
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
    color: var(--ink);
  }
  :global(body) {
    margin: 0;
    background-color: var(--ground);
    color: var(--ink);
    font-family: var(--font-body);
  }

  .page {
    min-height: 100vh;
    opacity: 0;
    transition: opacity 0.4s ease;
  }
  .page.mounted {
    opacity: 1;
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
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink);
    opacity: 0.5;
    margin: 0 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .count-badge {
    font-size: 0.75rem;
    font-weight: 700;
    background: var(--rule);
    color: var(--ground-raised);
    padding: 0.1rem 0.5rem;
    border-radius: var(--radius-pill);
    opacity: 1;
  }

  .count-badge.chip-green {
    background: var(--status-ok);
    color: var(--ink);
  }

  .steps-list {
    margin: 0;
    padding-left: 1.5rem;
    color: var(--ink);
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
    background: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
  }

  .map-row.done {
    background: color-mix(in srgb, var(--status-ok) 8%, var(--ground-raised));
    border-color: var(--status-ok);
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
    color: var(--ink);
    opacity: 0.5;
    flex-shrink: 0;
  }

  .map-btn {
    font-size: 0.8125rem;
    padding: 0.4rem 0.875rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .done-chip {
    font-size: 0.75rem;
    flex-shrink: 0;
  }

  .empty-msg {
    color: var(--ink);
    opacity: 0.6;
    font-size: 0.9375rem;
    margin: 0;
  }

  .state-card {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 3rem;
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    color: var(--ink);
    opacity: 0.6;
  }
</style>
