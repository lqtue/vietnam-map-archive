<!--
  LoadError.svelte — a read that failed, said so, with a way to try again.
  A failed load must not look like an empty result ("Every map is georeferenced",
  "Nothing matches"): the reader would believe it. Styling is the global
  `.empty-state.error` (components/feedback.css).
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { t } from '$lib/core/i18n';

  export let message: string;

  const dispatch = createEventDispatcher<{ retry: void }>();
</script>

<div class="empty-state is-block error" role="alert">
  <p>{message}</p>
  <button type="button" class="btn is-sm" on:click={() => dispatch('retry')}>{$t('Retry')}</button>
</div>

<style>
  button {
    margin-top: var(--space-3);
  }
</style>
