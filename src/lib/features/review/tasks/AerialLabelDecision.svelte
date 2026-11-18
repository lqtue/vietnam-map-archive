<!--
  AerialLabelDecision.svelte — the right-hand column for an aerial-label item: the question, a hint,
  the three labels, undo. No candidates, no search, no note: there is nothing to pick from, and a
  fast key per item is the point (seconds per item is what the task measures).
-->
<script lang="ts">
  import type { ReviewSession, SessionState } from '../reviewSession';
  import type { ReviewTaskDef } from './placeLink';

  export let task: ReviewTaskDef;
  export let session: ReviewSession;
  export let state: SessionState;

  $: busy = state.phase !== 'ready';
</script>

<div class="decision" aria-busy={busy}>
  <p class="question">{state.question}</p>
  <p class="hint">
    Built = roof or house visible in the middle of the cross; open = field, marsh, bare ground,
    water edge without roof. Unsure = cannot tell; do not guess.
  </p>
  <div class="relations">
    {#each task.relations as r (r.key)}
      <button
        type="button"
        class="btn is-sm"
        aria-keyshortcuts={r.key}
        disabled={busy}
        on:click={() => session.send(r.relation)}>{r.label} <kbd>{r.key}</kbd></button
      >
    {/each}
  </div>
  <p class="message" role="status" aria-live="polite">{state.message}</p>
  <p class="foot">
    <button
      type="button"
      class="btn is-sm"
      aria-keyshortcuts="u"
      disabled={busy}
      on:click={() => session.undo()}>undo last <kbd>u</kbd></button
    >
  </p>
</div>

<style>
  .decision {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .question {
    margin: 0;
    font-weight: var(--font-semibold);
  }
  .hint,
  .message,
  .foot {
    margin: 0;
    font-size: var(--text-sm);
  }
  .hint {
    color: var(--color-gray-500);
  }
  .message {
    min-height: 1.4em;
    color: var(--color-error-600);
  }
  .relations {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  kbd {
    font-family: var(--font-family-base);
    font-size: var(--text-xs);
    padding: 0 var(--space-1);
    border: var(--border-thin) solid var(--color-border);
    border-radius: var(--radius-sm);
  }
</style>
