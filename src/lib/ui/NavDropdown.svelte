<!--
  NavDropdown.svelte — Reusable dropdown panel for NavBar.
  Opens on click, closes on Escape or outside click.

  Props:
    label   — button text (e.g. "Maps")
    active  — whether any child link matches the current route
-->
<script lang="ts">
  import { onMount } from 'svelte';

  export let label: string;
  export let active: boolean = false;

  let open = false;
  let triggerEl: HTMLButtonElement;
  let panelEl: HTMLDivElement;

  function toggle() {
    open = !open;
  }
  function close() {
    open = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }

  function handleOutsideClick(e: MouseEvent) {
    if (
      triggerEl &&
      !triggerEl.contains(e.target as Node) &&
      panelEl &&
      !panelEl.contains(e.target as Node)
    ) {
      close();
    }
  }

  onMount(() => {
    document.addEventListener('keydown', handleKeydown);
    document.addEventListener('click', handleOutsideClick);
    return () => {
      document.removeEventListener('keydown', handleKeydown);
      document.removeEventListener('click', handleOutsideClick);
    };
  });
</script>

<div class="nav-dropdown-wrap">
  <button
    bind:this={triggerEl}
    class="nav-link nav-dropdown-trigger"
    class:active
    class:open
    type="button"
    aria-haspopup="true"
    aria-expanded={open}
    on:click={toggle}
  >
    {label}
    <svg class="chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path
        d="M2 4l4 4 4-4"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </button>

  {#if open}
    <div bind:this={panelEl} class="nav-dropdown-panel" role="menu">
      <slot />
    </div>
  {/if}
</div>

<style>
  .nav-dropdown-wrap {
    position: relative;
  }

  .nav-dropdown-trigger {
    background: none;
    border: 2px solid transparent;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }

  .nav-dropdown-trigger.open,
  .nav-dropdown-trigger.active {
    background: var(--accent);
    border-color: var(--rule);
    color: var(--ink);
  }

  .chevron {
    transition: transform 0.15s;
    flex-shrink: 0;
  }
  .nav-dropdown-trigger.open .chevron {
    transform: rotate(180deg);
  }

  .nav-dropdown-panel {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    background: var(--ground-raised);
    border: var(--rule-thick) solid var(--rule);
    border-radius: var(--radius);
    padding: 0.5rem;
    min-width: 200px;
    z-index: 200;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }
</style>
