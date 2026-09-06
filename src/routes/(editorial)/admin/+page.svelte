<script lang="ts">
  import { page } from '$app/stores';
  import BulkUploadPage from '$lib/features/admin/BulkUploadPage.svelte';
  import ScoutPage from '$lib/features/admin/ScoutPage.svelte';
  import StatusPage from '$lib/features/admin/StatusPage.svelte';

  /*
    One admin route, three tools. The tab is a query param rather than a nested
    route so the three pages share a single mount point — each component keeps
    its own role gate, exactly as it had when it was its own page.
  */

  type Tab = 'bulk' | 'scout' | 'status';

  const TABS: { id: Tab; label: string; title: string }[] = [
    { id: 'bulk', label: 'Bulk upload', title: 'Bulk Upload — Admin' },
    { id: 'scout', label: 'Scout', title: 'Scout · VMA Admin' },
    { id: 'status', label: 'System status', title: 'System status · VMA Admin' },
  ];

  function toTab(raw: string | null): Tab {
    const hit = TABS.find((t) => t.id === raw);
    return hit ? hit.id : 'bulk';
  }

  $: tab = toTab($page.url.searchParams.get('tab'));
  $: title = (TABS.find((t) => t.id === tab) ?? TABS[0]).title;
</script>

<svelte:head>
  <title>{title}</title>
  {#if tab === 'status'}
    <meta name="description" content="What the archive holds and what is blocked." />
  {/if}
</svelte:head>

<nav class="admin-tabs" aria-label="Admin tools">
  {#each TABS as t (t.id)}
    <a class="btn btn--sm" href="/admin?tab={t.id}" aria-current={tab === t.id ? 'page' : undefined}
      >{t.label}</a
    >
  {/each}
</nav>

{#if tab === 'scout'}
  <ScoutPage />
{:else if tab === 'status'}
  <StatusPage />
{:else}
  <BulkUploadPage />
{/if}

<style>
  .admin-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-2);
    padding: var(--s-3) var(--s-4) 0;
  }

  .admin-tabs a {
    text-decoration: none;
  }

  .admin-tabs a[aria-current='page'] {
    color: var(--accent);
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }
</style>
