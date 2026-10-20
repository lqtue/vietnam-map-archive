<script lang="ts">
  import { page } from '$app/stores';
  import ReviewGate from '$lib/features/review/ReviewGate.svelte';
  import ReviewPage from '$lib/features/review/ReviewPage.svelte';
  import { taskFor } from '$lib/features/review/tasks/placeLink';

  $: task = taskFor($page.params.task ?? '');
</script>

<ReviewGate>
  {#if task}
    {#key $page.params.task}
      <ReviewPage {task} taskKey={$page.params.task ?? ''} />
    {/key}
  {:else}
    <p class="gone">No review page for “{$page.params.task}”. <a href="/review">All tasks</a></p>
  {/if}
</ReviewGate>

<style>
  .gone {
    padding: var(--space-8);
  }
</style>
