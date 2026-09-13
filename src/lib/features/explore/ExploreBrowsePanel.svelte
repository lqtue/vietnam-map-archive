<!--
  ExploreBrowsePanel.svelte — map list for /explore, with an in-place "show
  all" expansion.

  Default view: just the maps that cover the user's location (GPS coverage),
  with a big tick-circle first cell for add/remove. "Browse the full archive →"
  swaps in ArchiveBrowser (shared catalog engine + facets). Both modes
  render the same ArchiveMapRows — tap to add, tap again to remove.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import type { ResolvedMap } from './spatialLookup';
  import type { CatalogSearchController } from '$lib/features/shared/catalogSearch';
  import ArchiveMapRows from '$lib/features/shared/ArchiveMapRows.svelte';
  import ArchiveBrowser from '$lib/features/shared/ArchiveBrowser.svelte';
  import { layersStore, toggleRasterOverlay } from '$lib/map/stores/layersStore';
  import { L7014_OVERLAY } from '$lib/map/constants';

  export let matches: ResolvedMap[] = [];
  // Admins/mods may browse draft maps in the viewer; everyone else is
  // capped to public/featured (mirrors /catalog's role gating).
  export let role: 'user' | 'mod' | 'admin' = 'user';
  // When the parent's welcome-mode is "Show all maps", force-expand so the
  // user lands on the full archive immediately. When the parent's mode is
  // location-based, leave `expanded` user-controlled — never auto-expand on
  // empty matches, since that hides the location's "no map here" status
  // after the tour ends.
  export let forceExpanded = false;
  // The desktop rail owns one filter bar above its two tabs and hands the
  // engine down; the mobile drawer has no such bar, so null leaves the browser
  // to create and render its own.
  export let search: CatalogSearchController | null = null;

  let expanded = false;

  // Parent owns the "Show all maps" decision. When it flips on, expand;
  // when off, leave whatever the user chose manually.
  $: if (forceExpanded) expanded = true;

  // Oldest → newest, matching /catalog's default sort. Undated maps sink
  // to the bottom; ties break by name so the order is stable.
  function byYear(
    a: { year?: number | null; name?: string },
    b: { year?: number | null; name?: string }
  ): number {
    const ay = a.year ?? Infinity;
    const by = b.year ?? Infinity;
    if (ay !== by) return ay - by;
    return (a.name ?? '').localeCompare(b.name ?? '');
  }

  // Default view: maps covering the user's GPS spot. `matches` comes from the
  // RLS-readable map list (which leaks drafts), so role-gate it here too.
  $: canSeeDrafts = role === 'admin' || role === 'mod';
  $: visibleMatches = [...matches]
    .filter((m) => canSeeDrafts || m.status === 'public' || m.status === 'featured')
    .sort(byYear);

  // Sheet series — whole pre-warped archives. They sit above the sheet rows
  // rather than among them because they are not catalogue entries: no record
  // page, no year to sort by, no single scan behind them. Same gesture though
  // — tap to put it on the map, tap again to take it off.
  const SERIES = [{ ref: L7014_OVERLAY, sheets: 435, note: '1963–89 · 1:50,000' }];
  $: seriesOn = new Set(
    $layersStore.overlays
      .filter((o) => o.ref.kind === 'raster')
      .map((o) => (o.ref as { key: string }).key)
  );
</script>

<div class="ebp" class:is-expanded={expanded}>
  <div class="head">
    <strong class="title">
      {#if expanded}{$t('Browse the archive')}{:else if matches.length}
        {matches.length === 1
          ? $t('1 map covers this spot')
          : $t('{N} maps cover this spot', { N: matches.length })}
      {:else}{$t('No archival map here')}{/if}
    </strong>
    {#if !expanded && matches.length}
      <span class="hint">{$t('Tap a row to add it as a layer · tap again to remove.')}</span>
    {/if}
  </div>

  <ul class="series">
    {#each SERIES as s (s.ref.key)}
      <li>
        <button
          type="button"
          class="series-row"
          class:is-on={seriesOn.has(s.ref.key)}
          aria-pressed={seriesOn.has(s.ref.key)}
          on:click={() => toggleRasterOverlay(s.ref)}
        >
          <span class="series-mark" aria-hidden="true">{seriesOn.has(s.ref.key) ? '✓' : '+'}</span>
          <span class="series-text">
            <span class="series-name">{s.ref.name}</span>
            <span class="series-note">{s.sheets} sheets · {s.note}</span>
          </span>
        </button>
      </li>
    {/each}
  </ul>

  {#if expanded}
    <ArchiveBrowser
      sortRows={byYear}
      {search}
      showFilters={search === null}
      on:pick
      on:remove
      on:pickLabel
    />
  {:else if visibleMatches.length}
    <ArchiveMapRows rows={visibleMatches} on:pick on:remove />
  {/if}

  <button type="button" class="browse-toggle" on:click={() => (expanded = !expanded)}>
    {#if expanded}{$t('← Back to maps at this location')}{:else}{$t(
        'Browse the full archive →'
      )}{/if}
  </button>
</div>

<style>
  .series {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .series-row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.5rem;
    background: var(--sb-card-bg);
    border: 1px solid var(--sb-border);
    border-radius: var(--sb-radius);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    color: var(--sb-text);
  }
  .series-row:hover {
    background: var(--sb-row-hover);
  }
  .series-row.is-on {
    border-color: var(--sb-accent);
  }
  .series-mark {
    flex: none;
    width: 1.4rem;
    height: 1.4rem;
    display: grid;
    place-items: center;
    border-radius: 50%;
    border: 1px solid var(--sb-border);
    font-size: 0.8rem;
    line-height: 1;
  }
  .series-row.is-on .series-mark {
    background: var(--sb-accent);
    border-color: var(--sb-accent);
    color: var(--color-on-accent);
  }
  .series-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .series-name {
    font-size: 0.82rem;
    font-weight: 600;
  }
  .series-note {
    font-size: 0.7rem;
    color: var(--sb-text-muted);
  }

  .ebp {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    padding: 0.6rem 0.7rem 0.8rem;
    font-family: var(--sb-font-base);
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .title {
    font-family: var(--sb-font-display);
    font-size: var(--text-base);
    font-weight: var(--font-extrabold);
  }
  .hint {
    color: var(--sb-text-meta);
    font-size: 0.78rem;
  }

  .browse-toggle {
    align-self: flex-start;
    margin-top: 0.3rem;
    padding: 0.45rem 0.7rem;
    background: transparent;
    border: none;
    color: var(--sb-accent);
    text-decoration: none;
    font-family: inherit;
    font-size: 0.84rem;
    font-weight: var(--font-bold);
    cursor: pointer;
    border-bottom: 1.5px dashed var(--sb-accent);
  }
  .browse-toggle:hover {
    color: var(--sb-accent-dark);
  }
</style>
