<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let facets: Record<string, Record<string, number>> = {};
  export let periods: { key: string; label: string }[] = [];
  // Selections by facet key — kept in sync via two-way bind:
  export let selected: Record<string, string[]> = {};
  export let showScoutFacets = false;

  const dispatch = createEventDispatcher();

  function toggle(group: string, value: string) {
    const cur = new Set(selected[group] ?? []);
    if (cur.has(value)) cur.delete(value);
    else cur.add(value);
    selected = { ...selected, [group]: Array.from(cur) };
    dispatch('change');
  }

  function sortedEntries(o: Record<string, number>, max = 12): [string, number][] {
    return Object.entries(o)
      .sort((a, b) => b[1] - a[1])
      .slice(0, max);
  }

  const STATUS_LABELS: Record<string, string> = {
    map: '🌍 On map',
    image: '🖼️ Image only',
    scout: '✨ Scout',
  };
  function labelFor(group: string, val: string): string {
    if (group === 'status') return STATUS_LABELS[val] ?? val;
    return val;
  }

  type Group = { title: string; key: string; entries: [string, number][] };
  $: groups = [
    { title: 'Area', key: 'area', entries: sortedEntries(facets.area ?? {}) },
    { title: 'Type', key: 'type', entries: sortedEntries(facets.map_type ?? {}) },
    { title: 'Status', key: 'status', entries: sortedEntries(facets.status ?? {}) },
    ...(showScoutFacets
      ? [
          {
            title: 'Scout category',
            key: 'category',
            entries: sortedEntries(facets.scout_category ?? {}, 12),
          },
        ]
      : []),
  ] as Group[];
</script>

<aside class="facet-rail">
  <!-- Period (special: labels come from API) -->
  {#if periods.length}
    <section class="facet-group">
      <h4>Period</h4>
      <div class="chips">
        {#each periods as p}
          {@const n = (facets.period ?? {})[p.key] ?? 0}
          {@const on = (selected.period ?? []).includes(p.key)}
          <button
            class="chip"
            class:on
            disabled={!n && !on}
            on:click={() => toggle('period', p.key)}
          >
            <span class="lbl">{p.label}</span>
            <span class="n">{n}</span>
          </button>
        {/each}
      </div>
    </section>
  {/if}

  {#each groups as g}
    {#if g.entries.length}
      <section class="facet-group">
        <h4>{g.title}</h4>
        <div class="chips">
          {#each g.entries as [val, n]}
            {@const on = (selected[g.key] ?? []).includes(val)}
            <button class="chip" class:on on:click={() => toggle(g.key, val)} title={val}>
              <span class="lbl">{labelFor(g.key, val)}</span>
              <span class="n">{n}</span>
            </button>
          {/each}
        </div>
      </section>
    {/if}
  {/each}
</aside>

<style>
  .facet-rail {
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
    padding: 1rem;
    background: var(--ground-raised);
    border: var(--rule-hair) solid var(--rule);
    border-radius: 10px;
    box-shadow: 3px 3px 0 var(--rule);
    font-family: var(--font-body);
    min-width: 240px;
    max-width: 280px;
  }
  .facet-group h4 {
    margin: 0 0 0.5rem;
    font-family: var(--font-display);
    font-weight: var(--w-semi);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ink);
    padding-bottom: 0.3rem;
    border-bottom: 1.5px dashed var(--rule);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.55rem;
    background: var(--sb-bg);
    border: 1.5px solid var(--rule);
    border-radius: var(--radius-pill);
    font-family: inherit;
    font-size: 0.78rem;
    font-weight: var(--w-semi);
    cursor: pointer;
    max-width: 100%;
  }
  .chip:hover:not(:disabled) {
    background: var(--ground-raised);
    transform: translate(-1px, -1px);
    box-shadow: 1.5px 1.5px 0 var(--rule);
  }
  .chip.on {
    background: var(--ink);
    color: var(--ground-raised);
  }
  .chip.on .n {
    background: var(--ground-raised);
    color: var(--ink);
  }
  .chip:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .lbl {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 170px;
  }
  .n {
    background: var(--ink);
    color: var(--ground-raised);
    padding: 0.05rem 0.4rem;
    border-radius: var(--radius-pill);
    font-size: 0.68rem;
    font-weight: var(--w-semi);
    min-width: 1.4rem;
    text-align: center;
  }
  @media (max-width: 900px) {
    .facet-rail {
      max-width: none;
      width: 100%;
    }
  }
</style>
