<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { page } from '$app/stores';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { signInWithGoogle } from '$lib/core/utils/signIn';

  const { supabase, session } = getSupabaseContext();

  let error = '';
  let loading = false;

  async function loginWithGoogle() {
    error = '';
    loading = true;

    const { error: authError } = await signInWithGoogle(
      supabase,
      $page.url.searchParams.get('next')
    );

    if (authError) {
      error = authError.message;
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Sign in — Vietnam Map Archive</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="page auth-page">
  <!-- The card is the whole page, so it is the main landmark. There is no
       PageHero here on purpose: a sign-in card wants no masthead above it. -->
  <main class="auth-card">
    <h1 class="auth-title">{$t('Sign in')}</h1>

    {#if error}
      <div class="auth-error">{error}</div>
    {/if}

    <div class="auth-options">
      <button class="btn is-lg auth-btn" on:click={loginWithGoogle} disabled={loading}>
        <svg viewBox="0 0 24 24" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            fill="#4285F4"
          />
          <path
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            fill="#34A853"
          />
          <path
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
            fill="#FBBC05"
          />
          <path
            d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            fill="#EA4335"
          />
        </svg>
        <span>{$t('Continue with Google')}</span>
      </button>
    </div>

    <p class="auth-notice">
      {$t(
        'Signing in lets you save favorites and contribute to the archive. Everything you add is released as open data under CC-BY.'
      )}
    </p>
  </main>
</div>

<style>
  /* `.page` (editorial.css) supplies the height and the mount fade; the card
     is deliberately chromeless, so there is no PageHero above it. */
  .auth-page {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    background-color: var(--color-bg);
    background-image: radial-gradient(var(--color-border) 1px, transparent 1px);
    background-size: 32px 32px;
  }

  .auth-card {
    width: 100%;
    max-width: 400px;
    padding: 2.5rem;
    background: var(--color-white);
    border: var(--border-thick);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-solid);
  }

  .auth-title {
    font-family: var(--font-family-display);
    font-size: 2.25rem;
    font-weight: 800;
    color: var(--color-text);
    margin: 0 0 2rem;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: -0.02em;
  }

  /* Tinted from the error ink rather than given its own three literals. */
  .auth-error {
    padding: var(--space-3) var(--space-4);
    background: color-mix(in srgb, var(--color-error-600) 15%, var(--color-white));
    border: 2px solid var(--color-error-600);
    border-radius: var(--radius-md);
    color: var(--color-text);
    font-size: var(--text-sm);
    font-weight: var(--font-semibold);
    margin-bottom: var(--space-6);
    box-shadow: var(--shadow-solid-sm);
  }

  .auth-options {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  /* `.btn.is-lg` (buttons.css) is already the page-CTA size. Only the
     layout it cannot know about is local: this one fills the card. */
  .auth-btn {
    width: 100%;
    justify-content: center;
    text-transform: uppercase;
  }

  .auth-notice {
    text-align: center;
    margin: 2rem 0 0;
    font-family: var(--font-family-base);
    font-size: 0.75rem;
    font-weight: 500;
    line-height: 1.4;
    color: var(--color-text);
    opacity: 0.6;
  }
</style>
