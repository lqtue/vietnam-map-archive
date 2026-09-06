<!--
  GeorefSyncPanel.svelte — "Sync georef status from Allmaps" maintenance action.

  Nothing to do with bulk upload; it only lives on /admin?tab=bulk because that was
  the nearest admin page when it was written. It belongs with the catalog admin
  bar (or a future /admin/maintenance). Styling still comes from the host page's
  stylesheet (`$styles/pages/admin-bulk.css`, scoped under .admin-bulk-page) —
  move those four rules with it when it relocates.
-->
<script lang="ts">
  let syncing = false;
  let syncResult: string | null = null;

  async function syncGeorefFromAllmaps() {
    syncing = true;
    syncResult = null;
    try {
      const res = await fetch('/api/admin/maps/sync-georef', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.message || `HTTP ${res.status}`);
      syncResult = `Checked ${data.checked}, flipped ${data.flipped} to georef_done.`;
    } catch (e: any) {
      syncResult = `Failed: ${e.message}`;
    } finally {
      syncing = false;
    }
  }
</script>

<section class="panel">
  <h2>Sync georef status</h2>
  <p class="hint">
    Probe the Allmaps annotation server for every map with an <code>allmaps_id</code> but
    <code>georef_done = false</code>. Volunteers who finish georef in the Allmaps Editor become
    visible to /scan?mode=triage after this runs. Idempotent.
  </p>
  <div class="script-actions">
    <button class="pill-btn" on:click={syncGeorefFromAllmaps} disabled={syncing}>
      {syncing ? 'Syncing…' : 'Sync georef from Allmaps'}
    </button>
  </div>
  {#if syncResult}<p class="status">{syncResult}</p>{/if}
</section>
