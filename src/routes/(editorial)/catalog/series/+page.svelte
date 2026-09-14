<!--
  /catalog/series — the surveys, and how much of each the archive holds.

  The rows themselves are `SeriesList`, shared with the band at the top of
  /catalog: the fraction a reader saw there is the fraction they find here.
-->
<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import SeriesList from '$lib/features/catalog/SeriesList.svelte';
  import type { PageData } from './$types';

  export let data: PageData;

  $: series = data.series;
</script>

<svelte:head>
  <title>Map series — Vietnam Map Archive</title>
  <meta
    name="description"
    content="The survey series the archive holds part of, and how much of each is held."
  />
</svelte:head>

<PageHero title="Map series" sub="Systematic surveys, sheet by sheet" />

<div class="page-wrap">
  <p class="lead">
    A survey is one map printed as many sheets. These are the ones the archive holds part of — each
    page lists every sheet the survey contains, held or not.
  </p>

  {#if series.length}
    <SeriesList {series} />
  {:else}
    <p class="lead">No series are published yet.</p>
  {/if}
</div>

<style>
  .page-wrap {
    max-width: 46rem;
    margin: 0 auto;
    padding-block: var(--space-6);
    padding-inline: var(--space-4);
  }
  .lead {
    margin: 0 0 var(--space-4);
    color: var(--color-gray-500);
  }
</style>
