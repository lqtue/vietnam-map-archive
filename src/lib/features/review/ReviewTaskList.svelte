<!--
  ReviewTaskList.svelte — /review: the open tasks, each with how many items are left for you.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import LoadError from '$lib/ui/LoadError.svelte';
  import { fetchTasks } from './reviewApi';
  import { taskFor } from './tasks/placeLink';
  import type { TaskSummary } from './types';

  let tasks: TaskSummary[] = [];
  let loading = true;
  let failed = '';

  async function load() {
    loading = true;
    failed = '';
    try {
      tasks = await fetchTasks();
    } catch (e) {
      failed = e instanceof Error ? e.message : 'Could not load the tasks';
    }
    loading = false;
  }

  onMount(load);
</script>

<svelte:head>
  <title>Review — Vietnam Map Archive</title>
</svelte:head>

<main class="list">
  <h1>Review</h1>
  {#if failed}
    <LoadError message={failed} on:retry={load} />
  {:else if loading}
    <p aria-busy="true">Loading…</p>
  {:else if !tasks.length}
    <p>No open tasks.</p>
  {:else}
    <ul>
      {#each tasks as t (t.key)}
        <li class="section-card">
          <h2>{t.title}</h2>
          <p>{t.question}</p>
          <p class="meta">{t.total - t.done} left for you · {t.done} of {t.total} done</p>
          {#if taskFor(t.key)}
            <a class="btn" href="/review/{t.key}">{t.done ? 'Continue' : 'Start'}</a>
          {:else}
            <p class="meta">This page cannot draw this task yet.</p>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</main>

<style>
  .list {
    max-width: 44rem;
    margin: 0 auto;
    padding: var(--space-8) var(--space-4);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-4);
  }
  h2 {
    margin-top: 0;
  }
  .meta {
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }
</style>
