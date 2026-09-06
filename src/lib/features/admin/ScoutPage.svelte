<script lang="ts">
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import ScoutCard, { type ScoutCandidate } from '$lib/features/admin/ScoutCard.svelte';
  import '$styles/pages/admin-scout.css';

  // ── session / role guard ────────────────────────────────────────────────
  const { supabase, session } = getSupabaseContext();
  let role: 'user' | 'mod' | 'admin' = 'user';
  let roleChecked = false;

  async function checkRole() {
    if (!session?.user?.id) {
      role = 'user';
      roleChecked = true;
      return;
    }
    role = (await fetchUserRole(supabase, session.user.id)) ?? 'user';
    roleChecked = true;
    if (role === 'admin' || role === 'mod') loadCandidates();
  }

  // ── data ────────────────────────────────────────────────────────────────
  let rows: ScoutCandidate[] = [];
  let total = 0;
  let loading = false;
  let facets: Record<string, Record<string, number>> | null = null;
  let selected: Set<string> = new Set();
  let actionMsg = '';

  // Filters
  let filterStatus = 'pending';
  let filterSource = '';
  let filterCategory = '';
  let filterMinScore = 40;
  let filterSearch = '';
  let page = 0;
  const pageSize = 60;

  async function loadCandidates() {
    loading = true;
    const params = new URLSearchParams({
      status: filterStatus,
      minScore: String(filterMinScore),
      limit: String(pageSize),
      offset: String(page * pageSize),
    });
    if (filterSource) params.set('source', filterSource);
    if (filterCategory) params.set('category', filterCategory);
    if (filterSearch) params.set('q', filterSearch);
    try {
      const r = await fetch(`/api/admin/scout?${params}`);
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      rows = data.rows;
      total = data.total;
      if (data.facets) facets = data.facets;
    } catch (e: unknown) {
      actionMsg = `Load failed: ${(e as Error).message.slice(0, 200)}`;
    } finally {
      loading = false;
    }
  }

  function resetFilters() {
    filterStatus = 'pending';
    filterSource = '';
    filterCategory = '';
    filterMinScore = 40;
    filterSearch = '';
    page = 0;
    loadCandidates();
  }
  function applyFilters() {
    page = 0;
    loadCandidates();
  }

  // ── per-row actions ─────────────────────────────────────────────────────
  async function setStatus(id: string, status: 'approved' | 'rejected' | 'pending') {
    try {
      const r = await fetch(`/api/admin/scout/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      if (!r.ok) throw new Error(await r.text());
      // Optimistic: remove from current view if we're filtering by status
      if (filterStatus === 'pending') rows = rows.filter((r) => r.id !== id);
      else rows = rows.map((r) => (r.id === id ? { ...r, status } : r));
      selected.delete(id);
      selected = selected;
    } catch (e: unknown) {
      actionMsg = `Update failed: ${(e as Error).message.slice(0, 200)}`;
    }
  }

  function toggle(id: string) {
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    selected = selected;
  }
  function selectAll() {
    rows.forEach((r) => selected.add(r.id));
    selected = selected;
  }
  function clearSelection() {
    selected = new Set();
  }

  async function bulkSetStatus(status: 'approved' | 'rejected') {
    if (!selected.size) return;
    actionMsg = `Updating ${selected.size}...`;
    const ids = [...selected];
    let ok = 0;
    for (const id of ids) {
      try {
        await fetch(`/api/admin/scout/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status }),
        });
        ok++;
      } catch {
        /* per-row error swallowed */
      }
    }
    actionMsg = `Updated ${ok}/${ids.length} to ${status}`;
    selected = new Set();
    loadCandidates();
  }

  async function bulkIngest() {
    if (!selected.size) return;
    if (!confirm(`Ingest ${selected.size} approved candidates as draft maps?`)) return;
    actionMsg = `Ingesting ${selected.size}...`;
    try {
      const r = await fetch('/api/admin/scout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: [...selected] }),
      });
      const data = await r.json();
      actionMsg = `Ingested ${data.ok} ok, ${data.failed} failed`;
      selected = new Set();
      loadCandidates();
    } catch (e: unknown) {
      actionMsg = `Ingest failed: ${(e as Error).message.slice(0, 200)}`;
    }
  }

  // ── keyboard review ─────────────────────────────────────────────────────
  // 3,369 pending candidates will never be reviewed one mouse click at a time.
  // j/k walk the grid, a/r decide, x selects for the bulk buttons, u reverts.
  let focusIdx = -1;

  function onKey(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement | null)?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.metaKey || e.ctrlKey) return;
    if (!rows.length) return;
    const c = rows[focusIdx];
    switch (e.key) {
      case 'j':
      case 'ArrowDown':
        focusIdx = Math.min(focusIdx + 1, rows.length - 1);
        break;
      case 'k':
      case 'ArrowUp':
        focusIdx = Math.max(focusIdx - 1, 0);
        break;
      case 'a':
        if (c?.status === 'pending') setStatus(c.id, 'approved');
        break;
      case 'r':
        if (c?.status === 'pending') setStatus(c.id, 'rejected');
        break;
      case 'u':
        if (c && c.status !== 'pending') setStatus(c.id, 'pending');
        break;
      case 'x':
        if (c) toggle(c.id);
        break;
      default:
        return;
    }
    e.preventDefault();
    // A decision in the pending view removes the row, so the cursor lands on
    // the next card by itself; only clamp the end.
    if (focusIdx >= rows.length) focusIdx = rows.length - 1;
  }

  onMount(checkRole);
</script>

<svelte:window on:keydown={onKey} />

<main class="scout-page">
  <header class="page-header">
    <h1>Scout Review</h1>
    <p>
      External map candidates discovered via Gallica, Humazur, Rumsey, LoC. Approve → bulk-ingest as
      draft maps.
    </p>
    <p class="kbd-hint">
      Keyboard: <kbd>j</kbd>/<kbd>k</kbd> move · <kbd>a</kbd> approve · <kbd>r</kbd> reject ·
      <kbd>x</kbd> select · <kbd>u</kbd> revert
    </p>
  </header>

  {#if !roleChecked}
    <p>Checking access…</p>
  {:else if role !== 'admin' && role !== 'mod'}
    <p>Admin access required.</p>
  {:else}
    <section class="filters">
      <div class="filter-row">
        <label
          >Status
          <select bind:value={filterStatus} on:change={applyFilters}>
            <option value="pending">Pending {facets?.status?.pending ?? ''}</option>
            <option value="approved">Approved {facets?.status?.approved ?? ''}</option>
            <option value="rejected">Rejected {facets?.status?.rejected ?? ''}</option>
            <option value="ingested">Ingested {facets?.status?.ingested ?? ''}</option>
            <option value="all">All</option>
          </select>
        </label>
        <label
          >Source
          <select bind:value={filterSource} on:change={applyFilters}>
            <option value="">— all —</option>
            {#if facets?.source}
              {#each Object.entries(facets.source) as [s, n] (s)}
                <option value={s}>{s} ({n})</option>
              {/each}
            {/if}
          </select>
        </label>
        <label
          >Category
          <select bind:value={filterCategory} on:change={applyFilters}>
            <option value="">— all —</option>
            {#if facets?.category}
              {#each Object.entries(facets.category) as [c, n] (c)}
                <option value={c}>{c} ({n})</option>
              {/each}
            {/if}
          </select>
        </label>
        <label
          >Min score
          <input
            type="number"
            bind:value={filterMinScore}
            on:change={applyFilters}
            step="5"
            style="width:5em"
          />
        </label>
        <label
          >Search title
          <input
            type="text"
            bind:value={filterSearch}
            on:change={applyFilters}
            placeholder="Saigon, 1882…"
          />
        </label>
        <button on:click={resetFilters}>Reset</button>
      </div>
      <div class="result-line">
        <strong>{total}</strong> matches · page {page + 1} of {Math.max(
          1,
          Math.ceil(total / pageSize)
        )}
        <button
          on:click={() => {
            if (page > 0) {
              page--;
              loadCandidates();
            }
          }}
          disabled={page === 0}>← Prev</button
        >
        <button
          on:click={() => {
            if ((page + 1) * pageSize < total) {
              page++;
              loadCandidates();
            }
          }}
          disabled={(page + 1) * pageSize >= total}>Next →</button
        >
      </div>
    </section>

    <section class="bulk-bar">
      <strong>{selected.size}</strong> selected
      <button on:click={selectAll}>Select page</button>
      <button on:click={clearSelection}>Clear</button>
      <span class="spacer"></span>
      <button class="btn-good" on:click={() => bulkSetStatus('approved')} disabled={!selected.size}
        >Approve selected</button
      >
      <button class="btn-bad" on:click={() => bulkSetStatus('rejected')} disabled={!selected.size}
        >Reject selected</button
      >
      {#if filterStatus === 'approved'}
        <button class="btn-primary" on:click={bulkIngest} disabled={!selected.size}
          >Ingest selected as draft maps</button
        >
      {/if}
      {#if actionMsg}<span class="action-msg">{actionMsg}</span>{/if}
    </section>

    {#if loading}
      <p>Loading…</p>
    {:else if !rows.length}
      <p>No candidates match these filters.</p>
    {:else}
      <section class="grid">
        {#each rows as c, i (c.id)}
          <ScoutCard
            candidate={c}
            selected={selected.has(c.id)}
            focused={i === focusIdx}
            on:toggle={(e) => toggle(e.detail)}
            on:status={(e) => setStatus(e.detail.id, e.detail.status)}
          />
        {/each}
      </section>
    {/if}
  {/if}
</main>
