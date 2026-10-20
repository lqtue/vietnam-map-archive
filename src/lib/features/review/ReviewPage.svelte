<!--
  ReviewPage.svelte — the frame of one review task: header, the item's views, the decision column.

  One item fills the screen. The views take the left, the decision a fixed column on the right;
  below 1280 px they stack. There is **no timer on screen**: the offline pages have none, and a
  clock changes how fast people work, so it would break the comparison. Seconds per item show on
  the all-done screen only.

  Keys come from the task definition plus `u`, `/`, `t` and the See-today keys, through `use:keys`
  (which skips typing fields). Each key calls the same function as its button.
  Plan: docs/plans/review-page-plan.md §5–§7.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { keys, type KeyMap } from '$lib/core/utils/keys';
  import LoadError from '$lib/ui/LoadError.svelte';
  import { reviewApi } from './reviewApi';
  import { createReviewSession } from './reviewSession';
  import ReviewViews from './ReviewViews.svelte';
  import PlaceLinkDecision from './tasks/PlaceLinkDecision.svelte';
  import type { ReviewTaskDef } from './tasks/placeLink';

  /** How to draw this kind of task; `taskKey` is the row it is working on (`place-link-2` is a place-link task). */
  export let task: ReviewTaskDef;
  export let taskKey: string;

  const session = createReviewSession(taskKey);
  let decision: PlaceLinkDecision | undefined;

  onMount(() => {
    void session.load();
  });

  $: s = $session;
  $: item = s.item;

  const search = (q: string) => reviewApi.search(taskKey, item?.item_id ?? '', q);

  function seeToday(i: number) {
    const links = document.querySelectorAll<HTMLAnchorElement>('.see-today a');
    const href = links[i]?.href;
    if (href) window.open(href, '_blank', 'noopener');
  }

  $: keyMap = ((): KeyMap => {
    const map: KeyMap = {
      u: () => void session.undo(),
      '/': () => decision?.focusSearch(),
      t: () => decision?.focusNote(),
      o: () => seeToday(0),
      v: () => seeToday(1),
      w: () => seeToday(2),
    };
    for (const k of [1, 2, 3]) map[String(k)] = () => session.pickCandidate(k);
    for (const r of task.relations) map[r.key] = () => void session.send(r.relation);
    return map;
  })();
</script>

<svelte:head>
  <title>{s.title || 'Review'} — Vietnam Map Archive</title>
</svelte:head>

<svelte:document on:visibilitychange={() => session.setHidden(document.hidden)} />

<div class="review-page" use:keys={keyMap}>
  <header class="bar">
    <h1>{s.title || 'Review'}</h1>
    <span class="count">{s.done} / {s.total}</span>
    <progress max={s.total || 1} value={s.done} aria-label="Progress"></progress>
    <a class="back" href="/review">All tasks</a>
  </header>

  {#if s.phase === 'failed'}
    <div class="center"><LoadError message={s.failure} on:retry={() => session.retry()} /></div>
  {:else if s.phase === 'done'}
    <div class="center done">
      <h2>All {s.total} done</h2>
      {#if s.medianSeconds !== null}
        <p>Your median this sitting: {s.medianSeconds} seconds per item.</p>
      {/if}
      <p class="actions">
        <button type="button" class="btn is-sm" on:click={() => session.undo()}
          >undo last <kbd>u</kbd></button
        >
        <a class="btn is-sm" href="/review">Back to the tasks</a>
      </p>
      <p class="message" role="status" aria-live="polite">{s.message}</p>
    </div>
  {:else if item}
    <div class="body">
      <div class="views">
        {#key item.item_id}
          <ReviewViews {session} {item} picked={s.pick} overlay={task.overlay} />
        {/key}
      </div>
      <aside class="side">
        {#key item.item_id}
          <PlaceLinkDecision bind:this={decision} {task} {session} state={s} {search} />
        {/key}
      </aside>
    </div>
  {:else}
    <p class="center" aria-busy="true">Loading…</p>
  {/if}
</div>

<style>
  .review-page {
    display: grid;
    grid-template-rows: auto 1fr;
    height: calc(100dvh - var(--nav-height));
    background: var(--color-bg);
    color: var(--color-text);
  }
  .bar {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-2) var(--space-4);
    border-bottom: var(--border-thin) solid var(--color-border);
  }
  h1 {
    margin: 0;
    font-size: var(--text-lg);
  }
  .count {
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }
  progress {
    flex: 1;
    max-width: 24rem;
  }
  .back {
    margin-left: auto;
    font-size: var(--text-sm);
  }
  .body {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    min-height: 0;
  }
  .views,
  .side {
    padding: var(--space-4);
    overflow: auto;
  }
  .side {
    border-left: var(--border-thin) solid var(--color-border);
  }
  .center {
    padding: var(--space-8);
    max-width: 40rem;
  }
  .done h2 {
    margin-top: 0;
  }
  .actions {
    display: flex;
    gap: var(--space-3);
  }
  .message {
    color: var(--color-error-600);
  }
  @media (max-width: 1279px) {
    .body {
      grid-template-columns: 1fr;
      overflow: auto;
    }
    .side {
      border-left: 0;
      border-top: var(--border-thin) solid var(--color-border);
    }
  }
</style>
