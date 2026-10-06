<!--
  TextReviewedMark.svelte — "this sheet's text has been checked", at any stage.

  Sends `reviewed` through the pipeline route, which only sets `reviewed_at`
  (it never touches seg). There is no Undo on purpose: the only way back is
  `idle`, and `set_review_mark` (mig 056) clears `seg_reviewed_at` and
  `exported_at` with it, so one click would wipe a sheet's shape marks.
-->
<script lang="ts">
  import { advancePipelineStage, fetchPipelineStatus } from '../pipelineApi';

  export let mapId: string;

  let reviewedAt: string | null = null;
  let saving = false;
  let error = '';
  let seq = 0;

  $: void load(mapId);

  async function load(id: string) {
    const mine = ++seq;
    reviewedAt = null;
    error = '';
    try {
      const status = await fetchPipelineStatus(id);
      if (mine === seq) reviewedAt = status.reviewed_at ?? null;
    } catch {
      // No status row yet: nothing marked.
    }
  }

  async function mark() {
    if (saving) return;
    const id = mapId;
    saving = true;
    error = '';
    try {
      const status = await advancePipelineStage(id, 'reviewed');
      if (id === mapId) reviewedAt = status.reviewed_at ?? new Date().toISOString();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Could not mark the text reviewed.';
    } finally {
      saving = false;
    }
  }
</script>

<div class="reviewed-mark">
  {#if reviewedAt}
    <span>Text reviewed · {new Date(reviewedAt).toLocaleDateString()}</span>
  {:else}
    <button type="button" class="sb-btn is-sm" disabled={saving} on:click={mark}>
      {saving ? 'Saving…' : 'Mark text reviewed'}
    </button>
  {/if}
  {#if error}<span role="alert">{error}</span>{/if}
</div>

<style>
  .reviewed-mark {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.75rem;
    font-size: 0.75rem;
    color: var(--sb-text-meta);
    border-top: var(--border-thin);
    flex-shrink: 0;
  }
</style>
