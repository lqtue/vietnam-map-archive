<!--
  ExplorePrivacyNotice.svelte — welcome chooser shown on first arrival to
  /explore. Offers two paths:

    • Use my location → triggers the browser GPS prompt and centres on
      the user.
    • Show all maps  → skips GPS, frames the default view (Saigon
      centre) and opens Browse so the user can pick any map across the
      archive (VMA covers Saigon AND other regions).

  Includes the privacy explainer for the location path. Ack persists in
  localStorage under `vma-explore-welcome-ack-v1` so returning users skip
  straight to their previously chosen mode.
-->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { readText, writeText } from '$lib/core/utils/persistence/storage';

  const STORAGE_KEY = 'vma-explore-welcome-ack-v1';
  type Choice = 'location' | 'all';
  const dispatch = createEventDispatcher<{ allow: void; skip: void }>();

  let visible = false;
  let dontShowAgain = true;

  onMount(() => {
    if (!browser) return;
    const prev = readText(STORAGE_KEY) as Choice | null;
    if (prev === 'location') {
      dispatch('allow');
      return;
    }
    if (prev === 'all') {
      dispatch('skip');
      return;
    }
    visible = true;
  });

  function persist(choice: Choice) {
    if (!browser || !dontShowAgain) return;
    writeText(STORAGE_KEY, choice);
  }

  function chooseLocation() {
    persist('location');
    visible = false;
    dispatch('allow');
  }
  function chooseAll() {
    persist('all');
    visible = false;
    dispatch('skip');
  }
</script>

{#if visible}
  <div class="backdrop" role="presentation"></div>
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="welcome-title">
    <h2 id="welcome-title">Explore the archive</h2>
    <p class="lede">
      Browse VMA's historical maps of Vietnam — Saigon, Hanoi, Huế, Cambodia and beyond. Pick how
      you want to start.
    </p>

    <div class="choices">
      <button type="button" class="choice primary" on:click={chooseLocation}>
        <span class="choice-icon" aria-hidden="true">📍</span>
        <span class="choice-body">
          <strong>Use my location</strong>
          <span>Centre on where I'm standing and surface the maps that cover it.</span>
        </span>
      </button>

      <button type="button" class="choice" on:click={chooseAll}>
        <span class="choice-icon" aria-hidden="true">🗂️</span>
        <span class="choice-body">
          <strong>Show all maps</strong>
          <span>Skip GPS — browse the whole archive and pick anywhere on Earth.</span>
        </span>
      </button>
    </div>

    <details class="privacy">
      <summary>What happens when I share my location?</summary>
      <ul>
        <li><strong>What:</strong> approximate device location, only while this tab is open.</li>
        <li><strong>Where:</strong> stays on your device — never sent to a server.</li>
        <li><strong>Stop anytime:</strong> tap 📍 at the top right, or revoke in your browser.</li>
      </ul>
    </details>

    <label class="ack-row">
      <input type="checkbox" bind:checked={dontShowAgain} />
      <span>Remember my choice on this device</span>
    </label>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: var(--scrim);
    z-index: 200;
  }
  .modal {
    position: fixed;
    left: 50%;
    bottom: 0;
    transform: translateX(-50%);
    width: min(460px, 100vw);
    background: var(--sb-card-bg);
    color: var(--sb-text);
    border: var(--rule-hair) solid var(--rule);
    border-bottom: none;
    border-top-left-radius: var(--radius);
    border-top-right-radius: var(--radius);
    box-shadow: 0 -6px 0 var(--rule);
    padding: 1.05rem 1.1rem 1.25rem;
    z-index: 201;
    max-height: 90vh;
    overflow-y: auto;
  }
  @media (min-width: 600px) {
    .modal {
      bottom: 50%;
      transform: translate(-50%, 50%);
      border: var(--rule-hair) solid var(--rule);
      border-radius: var(--radius);
    }
  }

  h2 {
    margin: 0 0 0.4rem;
    font-family: var(--sb-font-display);
    font-size: var(--t-lg);
    font-weight: var(--w-semi);
  }
  .lede {
    margin: 0 0 0.85rem;
    font-size: 0.92rem;
    color: var(--sb-text-meta);
    line-height: 1.4;
  }

  .choices {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    margin-bottom: 0.85rem;
  }
  .choice {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    width: 100%;
    text-align: left;
    padding: 0.8rem 0.85rem;
    background: var(--sb-card-bg);
    border: var(--rule-hair) solid var(--rule);
    border-radius: var(--radius);
    font-family: inherit;
    cursor: pointer;
    color: var(--sb-text);
  }
  .choice.primary {
    background: var(--sb-accent-warm);
    color: var(--ground-raised);
  }
  .choice:active {
    transform: translate(2px, 2px);
  }
  .choice-icon {
    font-size: 1.55rem;
    line-height: 1;
    flex-shrink: 0;
  }
  .choice-body {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }
  .choice-body strong {
    font-size: 0.98rem;
    font-weight: var(--w-semi);
  }
  .choice-body span {
    font-size: 0.82rem;
    opacity: 0.85;
    line-height: 1.35;
  }

  .privacy {
    margin-bottom: 0.75rem;
    font-size: var(--t-sm);
  }
  .privacy summary {
    cursor: pointer;
    font-weight: var(--w-semi);
    color: var(--sb-accent);
    padding: 0.3rem 0;
  }
  .privacy ul {
    list-style: none;
    padding: 0.4rem 0 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    line-height: 1.4;
  }
  .privacy li {
    padding-left: 0.7rem;
    border-left: 2.5px solid var(--sb-accent-warm);
  }

  .ack-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.84rem;
    cursor: pointer;
    user-select: none;
  }
  .ack-row input {
    width: 16px;
    height: 16px;
    accent-color: var(--sb-accent-warm);
  }
</style>
