<!--
  WorkPips — the tracks of `$lib/core/sheetWork` for one sheet. `pips` is five
  small dots (a table row has no room for words; the name is on hover and for
  screen readers), the default is labelled chips (the record page does).

  Green = done, yellow = in between, hollow = not yet.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { sheetTracks, type TrackState, type WorkFacts } from '$lib/core/sheetWork';

  export let state: WorkFacts | undefined = undefined;
  export let pips = false;

  const CHIP: Record<TrackState, string> = {
    done: 'chip-green',
    doing: 'chip-yellow',
    todo: 'chip-gray',
  };

  $: tracks = sheetTracks(state);
</script>

<span class="wp" class:is-pips={pips}>
  {#each tracks as tr (tr.key)}
    {#if pips}
      <span
        class="pip is-{tr.state}"
        role="img"
        title="{$t(tr.label)} — {$t(tr.hint)}"
        aria-label="{$t(tr.label)}: {tr.state}"
      ></span>
    {:else}
      <span
        class="badge-chip is-sm {CHIP[tr.state]}"
        class:wp-todo={tr.state === 'todo'}
        title={$t(tr.hint)}>{$t(tr.label)}</span
      >
    {/if}
  {/each}
</span>

<style>
  .wp {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem;
  }
  .wp.is-pips {
    gap: 0.2rem;
  }
  .wp-todo {
    opacity: 0.55;
  }
  .pip {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 50%;
    border: 1.5px solid var(--color-text);
    background: transparent;
  }
  .pip.is-done {
    background: var(--color-green);
  }
  .pip.is-doing {
    background: var(--color-yellow);
  }
</style>
