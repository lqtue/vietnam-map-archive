<!--
  StoryReviewPanel.svelte — the stories half of the moderation queue.

  Same contract as the footprint queue: list what is waiting, decide, move on.
  Approving is what makes a story publicly visible (mig 059); "send back"
  returns it to the author as a draft.
-->
<script lang="ts">
  import { onMount } from 'svelte';

  type StoryRow = {
    id: string;
    title: string;
    description: string | null;
    mode: string;
    status: string;
    point_count: number;
    updated_at: string;
  };

  let stories: StoryRow[] = [];
  let loading = true;
  let error = '';
  let busyId: string | null = null;

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetch('/api/admin/stories?status=submitted');
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).message ?? res.statusText);
      stories = await res.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function decide(id: string, status: 'approved' | 'rejected' | 'draft') {
    busyId = id;
    try {
      const res = await fetch('/api/admin/stories', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).message ?? res.statusText);
      stories = stories.filter((s) => s.id !== id);
    } catch (e: any) {
      error = e.message;
    } finally {
      busyId = null;
    }
  }

  onMount(load);
</script>

{#if loading}
  <div class="state-msg">Loading stories…</div>
{:else if error}
  <div class="state-msg error">{error}</div>
{:else if stories.length === 0}
  <div class="state-msg">Queue's clear — no stories waiting on review.</div>
{:else}
  <ul class="story-list">
    {#each stories as story (story.id)}
      <li class="story-row">
        <div class="story-meta">
          <a class="story-title" href={`/trip/${story.id}`} target="_blank">{story.title}</a>
          <span class="story-sub">
            {story.point_count} point{story.point_count === 1 ? '' : 's'} · {story.mode} · updated
            {new Date(story.updated_at).toLocaleDateString('en-GB')}
          </span>
          {#if story.description}
            <p class="story-desc">{story.description}</p>
          {/if}
        </div>
        <div class="story-actions">
          <button disabled={busyId === story.id} on:click={() => decide(story.id, 'approved')}>
            Approve
          </button>
          <button disabled={busyId === story.id} on:click={() => decide(story.id, 'draft')}>
            Send back
          </button>
          <button
            class="danger"
            disabled={busyId === story.id}
            on:click={() => decide(story.id, 'rejected')}
          >
            Reject
          </button>
        </div>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .story-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .story-row {
    display: flex;
    gap: var(--s-4);
    align-items: flex-start;
    justify-content: space-between;
    padding: var(--s-4);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
  }

  .story-meta {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
    min-width: 0;
  }

  .story-title {
    font-weight: 700;
    color: var(--ink);
  }

  .story-sub {
    font-size: var(--t-sm);
    color: var(--ink-soft);
  }

  .story-desc {
    margin: var(--s-1) 0 0;
    font-size: var(--t-sm);
    color: var(--ink);
  }

  .story-actions {
    display: flex;
    gap: var(--s-2);
    flex-shrink: 0;
  }

  .story-actions button {
    padding: var(--s-2) var(--s-3);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    background: var(--ground-raised);
    font: inherit;
    cursor: pointer;
  }

  .story-actions button.danger {
    color: var(--accent);
  }

  .story-actions button:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
