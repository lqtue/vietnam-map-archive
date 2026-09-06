<!--
  ExploreBrowsePanel.svelte — map list for /explore, with an in-place "show
  all" expansion.

  Default view: just the maps that cover the user's location (GPS coverage),
  with a big tick-circle first cell for add/remove. "Browse the full archive →"
  swaps in ExploreArchiveBrowser (shared catalog engine + facets). Both modes
  render the same ExploreMapRows — tap to add, tap again to remove.
-->
<script lang="ts">
  import type { ResolvedMap } from './spatialLookup';
  import ExploreMapRows from './ExploreMapRows.svelte';
  import ExploreArchiveBrowser from './ExploreArchiveBrowser.svelte';

  export let matches: ResolvedMap[] = [];
  // Admins/mods may browse draft maps in the viewer; everyone else is
  // capped to public/featured (mirrors /archive's role gating).
  export let role: 'user' | 'mod' | 'admin' = 'user';
  // When the parent's welcome-mode is "Show all maps", force-expand so the
  // user lands on the full archive immediately. When the parent's mode is
  // location-based, leave `expanded` user-controlled — never auto-expand on
  // empty matches, since that hides the location's "no map here" status
  // after the tour ends.
  export let forceExpanded = false;

  let expanded = false;

  // Parent owns the "Show all maps" decision. When it flips on, expand;
  // when off, leave whatever the user chose manually.
  $: if (forceExpanded) expanded = true;

  // Oldest → newest, matching /archive's default sort. Undated maps sink
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
</script>

<div class="ebp" class:is-expanded={expanded}>
  <div class="head">
    <strong class="title">
      {#if expanded}
        Browse the archive
      {:else if matches.length}
        {matches.length} map{matches.length === 1 ? '' : 's'} cover this spot
      {:else}
        No archival map here
      {/if}
    </strong>
    {#if !expanded && matches.length}
      <span class="hint">Tap a row to add it as a layer · tap again to remove.</span>
    {/if}
  </div>

  {#if expanded}
    <ExploreArchiveBrowser sortRows={byYear} on:pick on:remove on:pickLabel />
  {:else if visibleMatches.length}
    <ExploreMapRows rows={visibleMatches} on:pick on:remove />
  {/if}

  <button type="button" class="browse-toggle" on:click={() => (expanded = !expanded)}>
    {#if expanded}
      ← Back to maps at this location
    {:else}
      Browse the full archive →
    {/if}
  </button>
</div>

<style>
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
    font-size: var(--t-md);
    font-weight: var(--w-semi);
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
    font-weight: var(--w-semi);
    cursor: pointer;
    border-bottom: 1.5px dashed var(--sb-accent);
  }
  .browse-toggle:hover {
    color: var(--sb-accent-dark);
  }
</style>
