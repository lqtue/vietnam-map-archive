<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { getMeasurementConsentChoice } from '$lib/data/measurement';

  export let enabled = false;
  export let locale: 'en' | 'vi' = 'en';

  const dispatch = createEventDispatcher<{ choice: { consented: boolean } }>();
  let choice: 'unknown' | 'granted' | 'denied' = 'unknown';
  let open = false;

  onMount(() => {
    choice = getMeasurementConsentChoice();
  });

  function decide(consented: boolean) {
    choice = consented ? 'granted' : 'denied';
    open = false;
    dispatch('choice', { consented });
  }
</script>

{#if enabled}
  <div class="measurement-control" lang={locale}>
    {#if choice !== 'unknown'}
      <button
        class="btn is-xs is-ghost settings-button"
        type="button"
        aria-expanded={open}
        aria-controls="measurement-choices"
        on:click={() => (open = !open)}
      >
        {locale === 'vi' ? 'Tuỳ chọn phân tích' : 'Analytics choices'}
      </button>
    {/if}
    <section
      id="measurement-choices"
      class="measurement-panel"
      aria-label={locale === 'vi' ? 'Tuỳ chọn phân tích' : 'Analytics choices'}
      hidden={choice !== 'unknown' && !open}
    >
      <p>
        {locale === 'vi'
          ? 'Cho phép Google Analytics giúp chúng tôi hiểu mọi người tìm và sử dụng bản đồ như thế nào. Bạn có thể đổi lựa chọn bất cứ lúc nào.'
          : 'Optional Google Analytics helps us understand how people find and use maps. You can change this choice at any time.'}
      </p>
      <div class="measurement-actions">
        <button class="btn is-sm is-primary" type="button" on:click={() => decide(true)}>
          {locale === 'vi' ? 'Cho phép' : 'Allow'}
        </button>
        <button class="btn is-sm is-ghost" type="button" on:click={() => decide(false)}>
          {locale === 'vi' ? 'Không, cảm ơn' : 'Decline'}
        </button>
      </div>
    </section>
  </div>
{/if}

<style>
  .measurement-control {
    position: fixed;
    z-index: 40;
    right: max(1rem, env(safe-area-inset-right));
    bottom: max(4rem, calc(env(safe-area-inset-bottom) + 3rem));
    max-width: min(22rem, calc(100vw - 2rem));
    color: var(--color-text);
  }

  .measurement-panel {
    padding: 0.9rem;
    border: var(--border-thin);
    border-radius: var(--radius-sm);
    background: var(--color-bg);
    box-shadow: var(--shadow-solid-xs);
    font-size: 0.8125rem;
    line-height: 1.45;
  }

  .measurement-panel[hidden] {
    display: none;
  }

  p {
    margin: 0 0 0.75rem;
  }

  .measurement-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .settings-button {
    background: var(--color-white);
    border: var(--border-thin);
    font-size: 0.75rem;
    opacity: 0.78;
  }

  .settings-button:hover,
  .settings-button:focus-visible {
    opacity: 1;
  }

  @media (max-width: 480px) {
    .measurement-control {
      right: max(0.65rem, env(safe-area-inset-right));
      bottom: max(3.75rem, calc(env(safe-area-inset-bottom) + 2.75rem));
      max-width: calc(100vw - 1.3rem);
    }
  }
</style>
