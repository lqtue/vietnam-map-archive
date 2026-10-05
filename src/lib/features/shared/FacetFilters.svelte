<!--
  FacetFilters.svelte — one search, the facets and a group-by, for any list.

  The catalog's filter bar knows maps; this one knows nothing about its rows. A
  caller hands it `facets` (see `$lib/core/utils/facets`), the `rows` the counts
  describe, and gets back a `selected` choice, a `query` and a `groupBy` to apply
  with `filterRows` / `groupRows`. Text review is its first caller; shapes and
  the map lists are the next two, which is why the OCR-specific parts (the
  Save button, the batch verdicts) arrive through slots rather than props.

  It wears `FilterBar`, so it is the same search box and the same `Filters · N`
  disclosure as /catalog, the legend rail and /explore. A `primary` facet is
  drawn on the line under the search; the rest fold behind the disclosure.

  The search is debounced here — one keystroke would otherwise re-filter, re-sort
  and redraw every loaded row, and typing a street name is a dozen of those.
  `query` is what has settled, not what is in the box.

  `change` fires on a facet the user touched, with its key, so a caller whose
  facet is also a server query (status, run) knows to reload. `reset` fires after
  everything is back at its default, for the same reason.
-->
<script lang="ts" generics="T">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import FilterBar from './FilterBar.svelte';
  import FacetControl from './FacetControl.svelte';
  import {
    facetCounts,
    facetChoices,
    activeCount,
    isDefault,
    type Facet,
    type Selection,
  } from '$lib/core/utils/facets';
  import { debounce } from '$lib/core/utils/debounce';

  export let facets: Facet<T>[];
  /** The rows the counts describe: everything the facets could narrow. */
  export let rows: T[];
  export let selected: Selection;
  /** What reset returns to. A facet absent here defaults to "nothing chosen". */
  export let defaults: Selection = {};
  /** The settled search. Start it empty; reset clears it. */
  export let query = '';
  /** What a row's search matches against. */
  export let text: (row: T) => string = () => '';
  export let placeholder = 'Search…';
  export let groups: { key: string; label: string }[] = [];
  export let groupBy = '';
  /** Counts the caller knows better than the loaded rows, by facet key then value. */
  export let totals: Record<string, Record<string, number>> = {};

  const dispatch = createEventDispatcher<{ change: { key: string }; reset: void }>();

  let typed = query;
  const settle = debounce((v: string) => (query = v), 150);
  $: settle(typed);
  onDestroy(settle.cancel);

  $: counts = facetCounts(rows, facets, selected, { query, text });
  $: primaries = facets.filter((f) => f.primary);
  $: folded = facets.filter((f) => !f.primary);
  $: active = activeCount(facets, selected, defaults) + (groupBy ? 1 : 0);
  $: changed = !!typed.trim() || !!groupBy || facets.some((f) => !isDefault(f, selected, defaults));

  const choicesOf = (f: Facet<T>, tallies: typeof counts, sel: Selection, known: typeof totals) =>
    facetChoices(f, tallies[f.key] ?? {}, sel[f.key] ?? [], known[f.key]);

  function toggle(f: Facet<T>, value: string) {
    const now = selected[f.key] ?? [];
    const next = now.includes(value) ? now.filter((v) => v !== value) : [...now, value];
    selected = { ...selected, [f.key]: next };
    dispatch('change', { key: f.key });
  }

  function set(f: Facet<T>, value: string) {
    // A floor at its lowest is no floor, so it is not counted as a filter.
    const none = !value || (f.kind === 'min' && Number(value) <= (f.min ?? 0));
    selected = { ...selected, [f.key]: none ? [] : [value] };
    dispatch('change', { key: f.key });
  }

  function reset() {
    settle.cancel();
    typed = '';
    query = '';
    groupBy = '';
    selected = Object.fromEntries(Object.entries(defaults).map(([k, v]) => [k, [...v]]));
    dispatch('reset');
  }
</script>

<FilterBar bind:query={typed} {placeholder} {active} resettable={changed} on:reset={reset}>
  <svelte:fragment slot="before">
    <div class="primary">
      {#each primaries as f (f.key)}
        <FacetControl
          label={f.label}
          kind={f.kind}
          choices={choicesOf(f, counts, selected, totals)}
          chosen={selected[f.key] ?? []}
          min={f.min}
          max={f.max}
          step={f.step}
          format={f.format}
          on:toggle={(e) => toggle(f, e.detail)}
          on:set={(e) => set(f, e.detail)}
        />
      {/each}
      <slot name="primary" />
    </div>
  </svelte:fragment>
  {#each folded as f (f.key)}
    <FacetControl
      label={f.label}
      kind={f.kind}
      choices={choicesOf(f, counts, selected, totals)}
      chosen={selected[f.key] ?? []}
      min={f.min}
      max={f.max}
      step={f.step}
      format={f.format}
      on:toggle={(e) => toggle(f, e.detail)}
      on:set={(e) => set(f, e.detail)}
    />
  {/each}
  {#if groups.length}
    <select bind:value={groupBy} aria-label="Group by">
      <option value="">Group by: none</option>
      {#each groups as g (g.key)}
        <option value={g.key}>Group by: {g.label}</option>
      {/each}
    </select>
  {/if}
  <svelte:fragment slot="more"><slot name="more" /></svelte:fragment>
</FilterBar>

<style>
  .primary {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.5rem;
    padding-top: 0.3rem;
  }
</style>
