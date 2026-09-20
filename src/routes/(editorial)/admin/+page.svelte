<script lang="ts">
  /*
    /admin — one console, tab chosen by `?tab=`.

    Bulk upload, Scout and System status were three sibling routes with nothing
    linking them and no /admin index, so /admin itself was a 404. They are one
    page now. Each tab component keeps its own role gate (bulk is admin-only,
    the others allow mod), so the gate stays where the data is rather than
    being re-implemented here.

    Stories joined them in Sept 2026, from `/scan?mode=review&kind=stories`. A
    story has no sheet and no canvas, so it had been riding inside a
    pixel-coordinate tool it shared nothing with; /admin is where the queues are.
  */
  import { page } from '$app/stores';
  import { ADMIN_TABS, resolveAdminTab, type AdminTab } from '$lib/core/routeModes';
  import PageHero from '$lib/ui/PageHero.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import BulkUploadPage from '$lib/features/admin/BulkUploadPage.svelte';
  import ScoutPage from '$lib/features/admin/ScoutPage.svelte';
  import StatusPage from '$lib/features/admin/StatusPage.svelte';
  import StoryReviewPanel from '$lib/features/admin/StoryReviewPanel.svelte';

  const TAB_LABELS: Record<AdminTab, string> = {
    bulk: 'Bulk upload',
    scout: 'Scout',
    status: 'Status',
    stories: 'Stories',
  };
  const TABS = ADMIN_TABS.map((key) => ({
    key,
    label: TAB_LABELS[key],
  }));

  $: tab = resolveAdminTab($page.url.searchParams.get('tab'));
  $: tabLabel = TAB_LABELS[tab];
</script>

<svelte:head>
  <title>Admin — Vietnam Map Archive</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="page admin-page">
  <PageHero eyebrow={tabLabel} title="Admin" />

  <!-- Scout's queue and Bulk's upload grid are tables, not prose, and both ran
       wider than the 1100px measure before they moved inside this wrapper. -->
  <main class="editorial-main" class:is-wide={tab !== 'status' && tab !== 'stories'}>
    <Tabs
      label="Admin sections"
      tabs={TABS.map((t) => ({ ...t, href: `/admin?tab=${t.key}` }))}
      active={tab}
    />

    {#if tab === 'scout'}
      <ScoutPage />
    {:else if tab === 'status'}
      <StatusPage />
    {:else if tab === 'stories'}
      <StoryReviewPanel />
    {:else}
      <BulkUploadPage />
    {/if}
  </main>
</div>
