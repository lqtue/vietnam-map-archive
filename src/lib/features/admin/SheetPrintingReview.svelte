<script lang="ts">
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';

  export let seriesId: string;
  export let sheetNumber: string;

  type Printing = {
    id: string;
    printed_title: string | null;
    edition_statement: string | null;
    edition_label: string | null;
    issuing_agency: string | null;
    content_year: number | null;
    edition_year: number | null;
    printing_year: number | null;
    printing_month: number | null;
    printer: string | null;
    printing_statement: string | null;
    part: string | null;
    evidence: Record<string, unknown>;
    review_status: 'unreviewed' | 'verified' | 'uncertain';
  };
  type SourceItem = {
    id: string;
    institution: string;
    title: string | null;
    source_ref: string | null;
    url: string | null;
    year: number | null;
    edition: string | null;
    printing_id: string | null;
  };

  const dispatch = createEventDispatcher<{ changed: void; selected: string }>();
  let rows: Printing[] = [];
  let items: SourceItem[] = [];
  let selectedId = '';
  let draft: Partial<Printing> = {};
  let busy = false;
  let message = '';
  let evidenceSourceUrl = '';
  let reviewNote = '';

  function readEvidence() {
    const evidence = draft.evidence ?? {};
    evidenceSourceUrl = typeof evidence.source_url === 'string' ? evidence.source_url : '';
    reviewNote = typeof evidence.review_note === 'string' ? evidence.review_note : '';
  }

  async function load() {
    if (!seriesId || !sheetNumber) return;
    const query = new URLSearchParams({ series_id: seriesId, sheet_number: sheetNumber });
    const response = await fetch(`/api/admin/sheet-printings?${query}`);
    if (!response.ok) throw new Error('Could not load printing records');
    const result = await response.json();
    rows = result.printings ?? [];
    items = result.items ?? [];
    if (!rows.some((row) => row.id === selectedId)) selectedId = rows[0]?.id ?? '';
    draft = rows.find((row) => row.id === selectedId) ?? {};
    readEvidence();
  }

  async function assignItem(item: SourceItem, printingId: string) {
    busy = true;
    message = '';
    try {
      const response = await fetch(`/api/admin/cell-printings/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ printing_id: printingId || null }),
      });
      if (!response.ok)
        throw new Error(
          (await response.json().catch(() => ({}))).message ?? 'Could not link source item'
        );
      await load();
      dispatch('changed');
      message = 'Source item link saved';
    } catch (e) {
      message = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  function selectPrinting(id: string) {
    selectedId = id;
    draft = rows.find((row) => row.id === id) ?? {};
    readEvidence();
  }
  onMount(() => {
    load().catch((e) => (message = e.message));
  });

  function startNew() {
    selectedId = '';
    draft = { review_status: 'unreviewed', evidence: {} };
    evidenceSourceUrl = '';
    reviewNote = '';
  }

  async function save() {
    busy = true;
    message = '';
    try {
      const body: Record<string, unknown> = { ...draft };
      for (const field of ['content_year', 'edition_year', 'printing_year', 'printing_month']) {
        if (body[field] === undefined || body[field] === '') body[field] = null;
      }
      const evidence = { ...(draft.evidence ?? {}) };
      if (evidenceSourceUrl.trim()) evidence.source_url = evidenceSourceUrl.trim();
      else delete evidence.source_url;
      if (reviewNote.trim()) evidence.review_note = reviewNote.trim();
      else delete evidence.review_note;
      body.evidence = evidence;
      delete body.id;
      delete body.cell_id;
      const isNew = !selectedId;
      const url = isNew ? '/api/admin/sheet-printings' : `/api/admin/sheet-printings/${selectedId}`;
      const response = await fetch(url, {
        method: isNew ? 'POST' : 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          isNew ? { ...body, series_id: seriesId, sheet_number: sheetNumber } : body
        ),
      });
      if (!response.ok)
        throw new Error((await response.json().catch(() => ({}))).message ?? 'Save failed');
      const saved = (await response.json()) as Printing;
      await load();
      selectedId = saved.id;
      draft = saved;
      readEvidence();
      dispatch('changed');
      message = 'Printing saved';
    } catch (e) {
      message = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  function useForThisScan() {
    const selected = rows.find((row) => row.id === selectedId);
    if (selected?.review_status !== 'verified') return;
    dispatch('selected', selected.id);
  }
</script>

<section class="printing-review">
  <div class="head">
    <strong>Printing records for {sheetNumber}</strong>
    <button type="button" class="btn is-xs" on:click={startNew}>New printing</button>
  </div>
  {#if rows.length}
    <label class="form-label">
      <span>Existing printing</span>
      <select value={selectedId} on:change={(e) => selectPrinting(e.currentTarget.value)}>
        {#each rows as row (row.id)}
          <option value={row.id}
            >{row.edition_label ?? row.edition_statement ?? row.printed_title ?? row.id} · {row.review_status}</option
          >
        {/each}
      </select>
    </label>
  {/if}
  {#if items.length}
    <div class="source-items">
      <strong>Institution items</strong>
      {#each items as item (item.id)}
        <label class="form-label source-item">
          <span
            >{item.institution}: {item.title ??
              item.source_ref ??
              item.url ??
              'Untitled item'}{item.year ? ` · ${item.year}` : ''}</span
          >
          <select
            value={item.printing_id ?? ''}
            disabled={busy}
            on:change={(e) => assignItem(item, e.currentTarget.value)}
          >
            <option value="">Unresolved</option>
            {#each rows.filter((row) => row.review_status === 'verified') as row (row.id)}
              <option value={row.id}
                >{row.edition_label ?? row.edition_statement ?? row.printed_title ?? row.id}</option
              >
            {/each}
          </select>
        </label>
      {/each}
    </div>
  {/if}
  <div class="grid">
    <label class="form-label"
      ><span>Printed title</span><input
        class="form-input"
        bind:value={draft.printed_title}
      /></label
    >
    <label class="form-label"
      ><span>Edition label</span><input
        class="form-input"
        bind:value={draft.edition_label}
      /></label
    >
    <label class="form-label"
      ><span>Edition statement</span><input
        class="form-input"
        bind:value={draft.edition_statement}
      /></label
    >
    <label class="form-label"
      ><span>Issuing agency</span><input
        class="form-input"
        bind:value={draft.issuing_agency}
      /></label
    >
    <label class="form-label"
      ><span>Content year</span><input
        class="form-input"
        type="number"
        bind:value={draft.content_year}
      /></label
    >
    <label class="form-label"
      ><span>Edition year</span><input
        class="form-input"
        type="number"
        bind:value={draft.edition_year}
      /></label
    >
    <label class="form-label"
      ><span>Printing year</span><input
        class="form-input"
        type="number"
        bind:value={draft.printing_year}
      /></label
    >
    <label class="form-label"
      ><span>Printing month</span><input
        class="form-input"
        type="number"
        min="1"
        max="12"
        bind:value={draft.printing_month}
      /></label
    >
    <label class="form-label"
      ><span>Printer</span><input class="form-input" bind:value={draft.printer} /></label
    >
    <label class="form-label"
      ><span>Part</span><select bind:value={draft.part}
        ><option value="">Unknown</option><option value="whole">Whole</option><option value="W"
          >West</option
        ><option value="E">East</option><option value="assemblage">Assemblage</option></select
      ></label
    >
    <label class="form-label"
      ><span>Review</span><select bind:value={draft.review_status}
        ><option value="unreviewed">Unreviewed</option><option value="uncertain">Uncertain</option
        ><option value="verified">Verified</option></select
      ></label
    >
    <label class="form-label full"
      ><span>Verbatim printing statement</span><textarea
        class="form-input"
        rows="2"
        bind:value={draft.printing_statement}></textarea></label
    >
    <label class="form-label full"
      ><span>Evidence source URL</span><input
        class="form-input"
        type="url"
        bind:value={evidenceSourceUrl}
        placeholder="https://…"
      /></label
    >
    <label class="form-label full"
      ><span>Review note</span><textarea class="form-input" rows="2" bind:value={reviewNote}
      ></textarea></label
    >
  </div>
  <div class="actions">
    <button type="button" class="btn is-primary is-sm" on:click={save} disabled={busy}
      >{busy ? 'Saving…' : 'Save printing'}</button
    >{#if message}<span>{message}</span>{/if}
  </div>
  {#if rows.find((row) => row.id === selectedId)?.review_status === 'verified'}
    <button type="button" class="btn is-sm" on:click={useForThisScan}
      >Use this printing for this scan</button
    >
  {/if}
</section>

<style>
  .printing-review {
    margin-top: 1rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--color-border);
  }
  .head,
  .actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    margin-bottom: 0.6rem;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.65rem;
  }
  .full {
    grid-column: 1 / -1;
  }
  .source-items {
    display: grid;
    gap: 0.5rem;
    margin: 0.75rem 0;
  }
  .source-item {
    display: grid;
    grid-template-columns: 1fr minmax(12rem, 1fr);
    align-items: center;
    gap: 0.5rem;
  }
  .actions {
    justify-content: flex-start;
    margin-top: 0.6rem;
  }
</style>
