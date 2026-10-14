<!--
  +error.svelte — every error the site can raise, in one place.

  It sits at the root, so it renders inside the root layout only; the editorial
  layout's nav and footer are not part of it, and the page brings its own. That
  also covers a URL no route matches, which belongs to no group at all.

  A 5xx never shows the thrown message: it can carry database text. A 4xx shows
  the message the route chose, unless it is SvelteKit's bare default.
-->
<script lang="ts">
  import { page } from '$app/stores';
  import { t } from '$lib/core/i18n';
  import NavBar from '$lib/ui/NavBar.svelte';
  import EditorialFooter from '$lib/ui/EditorialFooter.svelte';
  import PageHero from '$lib/ui/PageHero.svelte';

  $: status = $page.status;
  $: notFound = status === 404;
  $: custom = $page.error?.message;
  $: title = notFound ? $t('Page not found') : $t('Something went wrong');
  $: message =
    status < 500 && custom && custom !== 'Not Found'
      ? custom
      : notFound
        ? $t('There is no page at this address. It may have moved, or the link may be wrong.')
        : $t('The archive hit a problem on our side. Try again in a moment.');
</script>

<svelte:head>
  <title>{status} — {title} — Vietnam Map Archive</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<NavBar session={$page.data.session ?? null} />

<div class="page">
  <PageHero eyebrow={String(status)} {title} sub={message} />
  <main class="editorial-main">
    <div class="error-links">
      <a class="btn" href="/">{$t('Home')}</a>
      <a class="btn" href="/catalog">{$t('Catalog')}</a>
    </div>
  </main>
</div>

<EditorialFooter />

<style>
  .error-links {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
  }
</style>
