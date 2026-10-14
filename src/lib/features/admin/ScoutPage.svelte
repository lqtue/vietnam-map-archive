<script lang="ts">
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import ScoutCard, { type ScoutCandidate } from '$lib/features/admin/ScoutCard.svelte';
  import ScoutTable from '$lib/features/admin/ScoutTable.svelte';
  import type { Verdict } from '$lib/features/admin/ScoutDecision.svelte';
  import { readText, writeText } from '$lib/core/utils/persistence/storage';
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

  // Grid to judge a sheet by its picture, table to scan a thousand titles.
  // The choice sticks, because a reviewer works one way for a whole session.
  const VIEW_KEY = 'vma-scout-view-v1';
  let view: 'grid' | 'table' = readText(VIEW_KEY) === 'table' ? 'table' : 'grid';
  function setView(next: 'grid' | 'table') {
    view = next;
    writeText(VIEW_KEY, next);
  }

  // Filters
  let filterStatus = 'pending';
  let filterSource = '';
  let filterCategory = '';
  let filterSearch = '';
  let orderBy = 'year';
  let orderDir: 'asc' | 'desc' = 'asc';
  let page = 0;
  const pageSize = 60;

  async function loadCandidates() {
    loading = true;
    const params = new URLSearchParams({
      status: filterStatus,
      limit: String(pageSize),
      offset: String(page * pageSize),
      order: orderBy,
      dir: orderDir,
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
    filterSearch = '';
    orderBy = 'year';
    orderDir = 'asc';
    page = 0;
    loadCandidates();
  }
  function applyFilters() {
    page = 0;
    loadCandidates();
  }
  /** Same column flips direction; a new column starts ascending. */
  function setSort(key: string) {
    if (orderBy === key) orderDir = orderDir === 'asc' ? 'desc' : 'asc';
    else {
      orderBy = key;
      orderDir = 'asc';
    }
    applyFilters();
  }

  // ── per-row actions ─────────────────────────────────────────────────────
  async function decide(id: string, status: Verdict, note: string | null) {
    try {
      const r = await fetch(`/api/admin/scout/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, review_note: note }),
      });
      if (!r.ok) throw new Error(await r.text());
      // Optimistic: remove from current view if we're filtering by status
      if (filterStatus === 'pending') rows = rows.filter((r) => r.id !== id);
      else rows = rows.map((r) => (r.id === id ? { ...r, status, review_note: note } : r));
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

  // One reason covers the batch — it is one decision, taken once.
  let bulkNote = '';

  async function bulkSetStatus(status: 'approved' | 'rejected') {
    if (!selected.size) return;
    actionMsg = `Updating ${selected.size}...`;
    const ids = [...selected];
    const review_note = bulkNote.trim() || null;
    const failed: string[] = [];
    for (const id of ids) {
      try {
        const r = await fetch(`/api/admin/scout/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status, review_note }),
        });
        if (!r.ok) failed.push(id);
      } catch {
        failed.push(id);
      }
    }
    const ok = ids.length - failed.length;
    actionMsg = failed.length
      ? `Updated ${ok}/${ids.length} to ${status}; ${failed.length} failed`
      : `Updated ${ok}/${ids.length} to ${status}`;
    // Failed rows stay selected (and the note stays) so the same click retries them.
    selected = new Set(failed);
    if (!failed.length) bulkNote = '';
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
  // 1,037 pending candidates will never be reviewed one mouse click at a time.
  // j/k walk the list, a/r decide with no reason, x selects for the bulk
  // buttons, u reverts. A reason needs the buttons — that is the trade for
  // being able to clear a page of obvious rows in a few seconds.
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
        if (c?.status === 'pending') decide(c.id, 'approved', null);
        break;
      case 'r':
        if (c?.status === 'pending') decide(c.id, 'rejected', null);
        break;
      case 'u':
        if (c && c.status !== 'pending') decide(c.id, 'pending', null);
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

<svelte:head><title>Scout · VMA Admin</title></svelte:head>

<div class="scout-page">
  <header class="scout-head">
    <h2 class="section-title-sm">Scout Review</h2>
    <p class="section-desc">
      External map candidates discovered via Gallica, Humazur, Rumsey, LoC and the AGS Library.
      Approve → bulk-ingest as draft maps.
    </p>
    <p class="kbd-hint">
      Keyboard: <kbd>j</kbd>/<kbd>k</kbd> move · <kbd>a</kbd> approve · <kbd>r</kbd> reject ·
      <kbd>x</kbd> select · <kbd>u</kbd> revert
    </p>
  </header>

  {#if !roleChecked}
    <p class="empty-state is-block">Checking access…</p>
  {:else if role !== 'admin' && role !== 'mod'}
    <p class="empty-state is-block">Admin access required.</p>
  {:else}
    <section class="sb-card filters">
      <div class="filter-row">
        <label
          >Status
          <select class="sb-input" bind:value={filterStatus} on:change={applyFilters}>
            <option value="pending">Pending {facets?.status?.pending ?? ''}</option>
            <option value="approved">Approved {facets?.status?.approved ?? ''}</option>
            <option value="rejected">Rejected {facets?.status?.rejected ?? ''}</option>
            <option value="ingested">Ingested {facets?.status?.ingested ?? ''}</option>
            <option value="all">All</option>
          </select>
        </label>
        <label
          >Source
          <select class="sb-input" bind:value={filterSource} on:change={applyFilters}>
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
          <select class="sb-input" bind:value={filterCategory} on:change={applyFilters}>
            <option value="">— all —</option>
            {#if facets?.category}
              {#each Object.entries(facets.category) as [c, n] (c)}
                <option value={c}>{c} ({n})</option>
              {/each}
            {/if}
          </select>
        </label>
        <label
          >Search title
          <input
            class="sb-input"
            type="text"
            bind:value={filterSearch}
            on:change={applyFilters}
            placeholder="Saigon, 1882…"
          />
        </label>
        <button class="btn is-sm" on:click={resetFilters}>Reset</button>
        <span class="spacer"></span>
        <div class="sb-pill-row view-toggle" role="group" aria-label="View">
          <button
            class="sb-pill"
            class:is-on={view === 'grid'}
            aria-pressed={view === 'grid'}
            on:click={() => setView('grid')}>▦ Grid</button
          >
          <button
            class="sb-pill"
            class:is-on={view === 'table'}
            aria-pressed={view === 'table'}
            on:click={() => setView('table')}>☰ Table</button
          >
        </div>
      </div>
      <div class="result-line">
        <strong>{total}</strong> matches · page {page + 1} of {Math.max(
          1,
          Math.ceil(total / pageSize)
        )}
        <button
          class="btn is-xs"
          on:click={() => {
            if (page > 0) {
              page--;
              loadCandidates();
            }
          }}
          disabled={page === 0}>← Prev</button
        >
        <button
          class="btn is-xs"
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

    <section class="sb-card bulk-bar">
      <strong>{selected.size}</strong> selected
      <button class="btn is-xs" on:click={selectAll}>Select page</button>
      <button class="btn is-xs is-ghost" on:click={clearSelection}>Clear</button>
      <input
        class="sb-input bulk-note"
        type="text"
        bind:value={bulkNote}
        placeholder="reason for the batch (optional)…"
        disabled={!selected.size}
      />
      <span class="spacer"></span>
      <button
        class="btn is-sm is-success"
        on:click={() => bulkSetStatus('approved')}
        disabled={!selected.size}>Approve selected</button
      >
      <button
        class="btn is-sm is-danger"
        on:click={() => bulkSetStatus('rejected')}
        disabled={!selected.size}>Reject selected</button
      >
      {#if filterStatus === 'approved'}
        <button class="btn is-sm is-primary" on:click={bulkIngest} disabled={!selected.size}
          >Ingest selected as draft maps</button
        >
      {/if}
      {#if actionMsg}<span class="action-msg">{actionMsg}</span>{/if}
    </section>

    {#if loading}
      <p class="empty-state is-block">Loading…</p>
    {:else if view === 'table'}
      <ScoutTable
        {rows}
        {selected}
        {focusIdx}
        {orderBy}
        {orderDir}
        on:toggle={(e) => toggle(e.detail)}
        on:sort={(e) => setSort(e.detail)}
        on:decide={(e) => decide(e.detail.id, e.detail.status, e.detail.note)}
      />
    {:else if !rows.length}
      <p class="empty-state is-block">No candidates match these filters.</p>
    {:else}
      <section class="grid">
        {#each rows as c, i (c.id)}
          <ScoutCard
            candidate={c}
            selected={selected.has(c.id)}
            focused={i === focusIdx}
            on:toggle={(e) => toggle(e.detail)}
            on:decide={(e) => decide(e.detail.id, e.detail.status, e.detail.note)}
          />
        {/each}
      </section>
    {/if}
  {/if}
</div>
