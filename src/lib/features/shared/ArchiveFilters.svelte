<!--
  ArchiveFilters.svelte — the search box, the facet dropdowns and the
  reset link that steer a catalog list.

  Extracted from `ArchiveBrowser` (Sept 2026) so one bar can steer more than
  one list: /explore's left rail renders it once above its two tabs and hands
  the same controller to the archive browser and to the layer stack. The
  browser still renders it itself by default, so its other callers — the /scan
  map picker among them — are untouched.

  The bar owns no state: everything it reads and writes lives on the
  `CatalogSearchController` the caller passes in.

  Only what is set shows: the kind pills, one native `<details>` "+ Filter" menu
  holding the selects for facets not yet chosen, a chip per chosen facet, and
  the year timeline in the open. They stay separate controls — area AND type
  AND series AND year still combine.
-->
<script lang="ts">
  import { mapTypeLabel } from '$lib/core/mapTaxonomy';
  import { t, locale } from '$lib/core/i18n';
  import { CATALOG_REGIONS } from '$lib/core/catalogRegions';
  import Tabs from '$lib/ui/Tabs.svelte';
  import type { CatalogSearchController } from '$lib/features/shared/catalogSearch';
  import FilterBar from './FilterBar.svelte';
  import YearTimeline from './YearTimeline.svelte';

  /** The search engine this bar drives. Created by the caller, because the
   *  point of the component is that several lists can share one. */
  export let search: CatalogSearchController;
  /** Draw the search box. /catalog turns it off: its own field is the page's
   *  `.sb-search.is-page`, at the top of the page above everything. */
  export let showSearch = true;
  /**
   * The surveys offerable as a filter, `{ value: maps.series_key, label }`.
   *
   * /catalog passes them from `map_series`, which is where a survey is named, and with them gets the
   * Surveys / Plans switch. A caller with no server load (the /explore rail, the /scan picker) passes
   * none, and the bar offers the surveys the engine's own rows carry, labelled by their collection.
   */
  export let seriesChoices: { value: string; label: string }[] = [];

  /** Staff get the Type select; for a reader it is one value in 96% of rows, so it filters nothing. */
  export let staff = false;
  /** Filters the caller adds inside the same disclosure (default slot), counted on its summary. */
  export let extraActive = 0;
  /** Removable chips for filters the caller owns (the slot's), drawn after the facets' own. */
  export let extraChips: { label: string; clear: () => void }[] = [];

  const {
    query,
    areaChoices,
    regionChoices,
    typeChoices,
    institutionChoices,
    seriesChoices: corpusSeries,
    yearBins,
    selected,
  } = search;

  /** The caller's own list of surveys when it passed one, else the surveys the corpus holds. */
  $: seriesOpts = seriesChoices.length ? seriesChoices : $corpusSeries;

  /** The caller that offers surveys also offers the Surveys / Plans switch — same reason. */
  $: hasKinds = seriesChoices.length > 0;
  $: kind = $selected.kind?.[0] ?? '';
  $: KINDS = [
    { key: '', label: $t('All') },
    { key: 'surveys', label: $t('Surveys') },
    { key: 'plans', label: $t('Plans') },
  ];
  function setKind(k: string) {
    search.setSingle('kind', k);
  }

  $: [yFrom, yTo] = [$selected.year?.[0] ?? '', $selected.year?.[1] ?? ''];
  function setYears(from: string, to: string) {
    selected.update((s) => ({ ...s, year: from || to ? [from, to] : [] }));
  }

  /** How many facets are set — the number on the summary. */
  $: activeFacets =
    ($selected.kind?.length ? 1 : 0) +
    ($selected.series_key?.length ? 1 : 0) +
    ($selected.area?.length ? 1 : 0) +
    ($selected.region?.length ? 1 : 0) +
    ($selected.type?.length ? 1 : 0) +
    ($selected.institution?.length ? 1 : 0) +
    ($selected.year?.length ? 1 : 0);

  $: hasFilters = !!$query.trim() || activeFacets > 0 || !!kind || !!$selected.series_key?.length;

  /** One removable chip per set facet, prefixed with the facet's name. */
  $: chips = [
    ...($selected.kind?.[0]
      ? [{ key: 'kind', label: KINDS.find((k) => k.key === kind)?.label }]
      : []),
    ...($selected.series_key?.[0]
      ? [
          {
            key: 'series_key',
            facet: 'Series',
            label: seriesOpts.find((s) => s.value === $selected.series_key[0])?.label,
          },
        ]
      : []),
    ...($selected.area?.[0] ? [{ key: 'area', facet: 'Place', label: $selected.area[0] }] : []),
    ...($selected.region?.[0]
      ? [
          {
            key: 'region',
            facet: 'Region',
            label: CATALOG_REGIONS.find((r) => r.key === $selected.region[0])?.[$locale],
          },
        ]
      : []),
    ...($selected.type?.[0]
      ? [{ key: 'type', facet: 'Type', label: mapTypeLabel($selected.type[0], $locale) }]
      : []),
    ...($selected.institution?.[0]
      ? [{ key: 'institution', facet: 'Held by', label: $selected.institution[0] }]
      : []),
    ...($selected.year?.length
      ? [{ key: 'year', facet: 'Year', label: `${yFrom || '…'}–${yTo || '…'}` }]
      : []),
  ].map((c) => {
    const label = c.label || $selected[c.key][0];
    return {
      label: 'facet' in c ? `${$t(c.facet as string)}: ${label}` : label,
      clear: () => (c.key === 'year' ? setYears('', '') : search.setSingle(c.key, '')),
    };
  });
  $: allChips = [...chips, ...extraChips];

  /** A "what" value is `series:<key>` or `type:<t>`; set that key, clear the other. */
  function setWhat(v: string) {
    const [group, ...rest] = v.split(':');
    const value = rest.join(':');
    search.setSingle('series_key', group === 'series' ? value : '');
    search.setSingle('type', group === 'type' ? value : '');
  }
  /** A "where" value is `region:<key>` or `area:<province>`; same shape. */
  function setWhere(v: string) {
    const [group, ...rest] = v.split(':');
    const value = rest.join(':');
    search.setSingle('region', group === 'region' ? value : '');
    search.setSingle('area', group === 'area' ? value : '');
  }

  /** The "+ Filter" menu: a native <details>, closed after a pick or a click outside it. */
  let menuOpen = false;
  let menu: HTMLDetailsElement;
  /** Facets with nothing chosen yet are the only ones the menu offers. */
  $: showWhat = !$selected.series_key?.length && !$selected.type?.length;
  $: showWhere = !$selected.region?.length && !$selected.area?.length;
  $: showInstitution = !$selected.institution?.length;
  $: showMenu =
    (showWhat && (seriesOpts.length > 1 || (staff && $typeChoices.length > 0))) ||
    (showWhere && ($areaChoices.length > 0 || $regionChoices.length > 0)) ||
    (showInstitution && $institutionChoices.length > 1) ||
    (!!$$slots.default && !extraActive);

  function resetFilters() {
    query.set('');
    selected.set({});
  }
</script>

<svelte:window
  on:click={(e) => {
    if (menuOpen && menu && !menu.contains(e.target as Node)) menuOpen = false;
  }}
/>

<FilterBar bind:query={$query} placeholder={$t('Search maps…')} {showSearch} flat>
  <div class="primary">
    {#if hasKinds}
      <div class="kinds">
        <Tabs
          tone="rail"
          tabs={KINDS}
          active={kind}
          label={$t('Kind of map')}
          on:change={(e) => setKind(e.detail.key)}
        />
      </div>
    {/if}
    {#if showMenu}
      <details class="add-filter" bind:open={menuOpen} bind:this={menu}>
        <summary class="chip">+ {$t('Filter')}</summary>
        <!-- A pick fires `change` on its select; it bubbles here and folds the menu. -->
        <div class="menu" on:change={() => (menuOpen = false)}>
          {#if showWhat && (seriesOpts.length > 1 || (staff && $typeChoices.length))}
            <!-- Series and type are both "what kind of map": one select, two groups. -->
            <label
              >{$t('Series or type')}
              <select value="" on:change={(e) => setWhat(e.currentTarget.value)}>
                <option value="">{$t('Any series or type')}</option>
                {#if seriesOpts.length > 1}
                  <optgroup label={$t('Series')}>
                    {#each seriesOpts as s (s.value)}
                      <option value={`series:${s.value}`}>{s.label}</option>
                    {/each}
                  </optgroup>
                {/if}
                {#if staff && $typeChoices.length}
                  <optgroup label={$t('Type')}>
                    {#each $typeChoices as t (t)}
                      <option value={`type:${t}`}>{mapTypeLabel(t, $locale)}</option>
                    {/each}
                  </optgroup>
                {/if}
              </select>
            </label>
          {/if}
          {#if showWhere && ($areaChoices.length || $regionChoices.length)}
            <!-- Region and province are both "where": one select, two groups. -->
            <label
              >{$t('Place')}
              <select
                value=""
                on:change={(e) => setWhere(e.currentTarget.value)}
                title={$t(
                  'Modern province, as it stood until mid-2025 — a locator, not the name the map used'
                )}
              >
                <option value="">{$t('Anywhere')}</option>
                {#if $regionChoices.length}
                  <optgroup label={$t('Regions')}>
                    {#each CATALOG_REGIONS.filter( (region) => $regionChoices.includes(region.key) ) as region (region.key)}
                      <option value={`region:${region.key}`}>{region[$locale]}</option>
                    {/each}
                  </optgroup>
                {/if}
                {#if $areaChoices.length}
                  <optgroup
                    label={`${$t('Provinces')} · ${$locale === 'vi' ? 'trước 7/2025' : 'before July 2025'}`}
                  >
                    {#each $areaChoices as a (a)}
                      <option value={`area:${a}`}>{a}</option>
                    {/each}
                  </optgroup>
                {/if}
              </select>
            </label>
          {/if}
          {#if showInstitution && $institutionChoices.length > 1}
            <label
              >{$t('Held by')}
              <select
                value=""
                on:change={(e) => search.setSingle('institution', e.currentTarget.value)}
              >
                <option value="">{$t('All institutions')}</option>
                {#each $institutionChoices as i (i)}
                  <option value={i}>{i}</option>
                {/each}
              </select>
            </label>
          {/if}
          {#if $$slots.default && !extraActive}
            <label>{$t('Work')} <slot /></label>
          {/if}
        </div>
      </details>
    {/if}
  </div>
  <svelte:fragment slot="more">
    {#if $yearBins.length}
      <YearTimeline
        bins={$yearBins}
        from={yFrom}
        to={yTo}
        on:change={(e) => setYears(...e.detail)}
      />
    {/if}
  </svelte:fragment>
</FilterBar>

{#if allChips.length || hasFilters}
  <div class="active-chips">
    {#each allChips as c (c.label)}
      <span class="chip is-on">
        {c.label}
        <button
          type="button"
          class="chip-x"
          aria-label={$t('Remove {X}', { X: c.label })}
          on:click={c.clear}>×</button
        >
      </span>
    {/each}
    {#if hasFilters}
      <button type="button" class="reset" on:click={resetFilters}>{$t('Clear all')}</button>
    {/if}
  </div>
{/if}

<style>
  .add-filter {
    flex-basis: 100%;
  }
  .add-filter summary {
    display: inline-block;
    cursor: pointer;
    list-style: none;
  }
  .add-filter summary::-webkit-details-marker {
    display: none;
  }
  /* In flow, not floating: a 300px rail clips an absolute panel. */
  .menu {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    padding-top: 0.35rem;
  }
  .menu label {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    flex: 1 1 8rem;
    min-width: 0;
    font-size: 0.72rem;
    font-weight: var(--font-bold);
  }
  .menu :global(select) {
    max-width: 100%;
    padding: 0.3rem 0.45rem;
    font-family: inherit;
    font-size: 0.82rem;
    background: var(--sb-card-bg);
    border: var(--border-thin);
    border-radius: var(--sb-radius-sm);
    box-shadow: 1px 1px 0 var(--shadow-ink);
    cursor: pointer;
  }

  .active-chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
  }
  .reset {
    background: transparent;
    border: none;
    padding: 0;
    font: inherit;
    font-size: 0.76rem;
    font-weight: var(--font-bold);
    color: var(--sb-accent);
    text-decoration: underline;
    cursor: pointer;
  }
  .chip-x {
    all: unset;
    cursor: pointer;
    margin-left: 0.3rem;
    padding: 0 0.2rem;
  }

  .primary {
    display: flex;
    flex-wrap: wrap;
    flex-basis: 100%;
    align-items: center;
    gap: 0.5rem;
  }
  /* The pill row shrinks inside a flex line and clips its longest label. */
  .kinds :global(.sb-pill) {
    flex: none;
    white-space: nowrap;
  }
</style>
