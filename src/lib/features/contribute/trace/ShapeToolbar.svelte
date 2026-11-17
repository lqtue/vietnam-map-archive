<!--
  ShapeToolbar.svelte — the bar under the Shapes canvas: Polygon · Line · Edit.

  Keys (ignored while a text field has focus): p polygon, l line, e edit.
  None clash with the check list's j/k/v/x.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  type Tool = 'polygon' | 'line' | 'edit';
  export let tool: Tool = 'edit';

  const dispatch = createEventDispatcher<{ change: { tool: Tool } }>();

  const TOOLS: { key: Tool; label: string; shortcut: string; title: string }[] = [
    {
      key: 'polygon',
      label: 'Polygon',
      shortcut: 'p',
      title: 'Polygon — blocks, plots, buildings',
    },
    { key: 'line', label: 'Line', shortcut: 'l', title: 'Line — roads and waterways' },
    { key: 'edit', label: 'Edit', shortcut: 'e', title: 'Select a shape and drag its corners' },
  ];

  function onKeydown(e: KeyboardEvent) {
    if (e.isComposing || e.metaKey || e.ctrlKey || e.altKey) return;
    const target = e.target as HTMLElement | null;
    if (
      target?.tagName === 'INPUT' ||
      target?.tagName === 'TEXTAREA' ||
      target?.tagName === 'SELECT'
    )
      return;
    if (target?.isContentEditable) return;
    const hit = TOOLS.find((t) => t.shortcut === e.key);
    if (hit) dispatch('change', { tool: hit.key });
  }
</script>

<svelte:window on:keydown={onKeydown} />

<footer class="bottom-bar">
  {#each TOOLS as t (t.key)}
    <button
      type="button"
      class="sb-btn is-sm"
      class:is-on={tool === t.key}
      aria-pressed={tool === t.key}
      on:click={() => dispatch('change', { tool: t.key })}
      title="{t.title} ({t.shortcut})"
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        {#if t.key === 'polygon'}
          <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5" />
        {:else if t.key === 'line'}
          <polyline points="4 19 8 10 14 14 20 5" />
        {:else}
          <path d="M17 3a2.83 2.83 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
        {/if}
      </svg>
      <span>{t.label}</span>
      <kbd>{t.shortcut}</kbd>
    </button>
  {/each}
</footer>

<style>
  kbd {
    font-family: monospace;
    font-size: 0.65rem;
    opacity: 0.6;
  }
</style>
