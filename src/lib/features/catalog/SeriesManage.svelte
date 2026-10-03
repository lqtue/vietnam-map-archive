<!--
  SeriesManage — what is behind each cell of a survey, for the people who run it.

  The public table says what the archive SERVES. This says what it HOLDS: every `maps`
  record of the survey in any status, grouped by stage, with the one click that moves it
  on. Admin/mod only, and fetched in the browser under the reader's own session, so a
  draft's name never reaches the server-rendered HTML a crawler gets (RLS gates `maps`).
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import { readAll } from '$lib/data/supabase/paged';

  export let collection: string;
  export let cellCount: number;

  interface Rec {
    id: string;
    slug: string | null;
    name: string | null;
    year: number | null;
    status: string;
    sheet_number: string;
    is_georeferenced: boolean | null;
    iiif_image: string | null;
    source: string | null;
    edition: string | null;
  }

  const { supabase, session } = getSupabaseContext();

  let allowed = false;
  let recs: Rec[] = [];
  let stage: string | null = 'needs_placement';
  let busy = '';
  let failed = '';

  const isLive = (r: Rec) => r.status === 'public' || r.status === 'featured';
  /** Where a record is on its way to the map. */
  function stageOf(r: Rec): string {
    if (isLive(r)) return 'published';
    if (!r.iiif_image) return 'no_image';
    return r.is_georeferenced ? 'ready' : 'needs_placement';
  }
  const STAGES: Record<string, string> = {
    published: 'Published',
    ready: 'Placed, unpublished',
    needs_placement: 'Needs placement',
    no_image: 'Upload incomplete',
  };

  async function load() {
    const { data } = await readAll<Rec>((from, to) =>
      supabase
        .from('maps')
        .select(
          'id,slug,name,year,status,sheet_number,is_georeferenced,iiif_image,source:extra_metadata->>source_archive,edition:extra_metadata->>edition'
        )
        .eq('collection', collection)
        .not('sheet_number', 'is', null)
        .order('id')
        .range(from, to)
    );
    recs = data as Rec[];
  }

  onMount(async () => {
    const role = await fetchUserRole(supabase, session?.user?.id);
    allowed = role === 'admin' || role === 'mod';
    if (allowed) await load();
  });

  /** One cell is "covered" when any record of it is published. */
  $: live = new Set(recs.filter(isLive).map((r) => r.sheet_number));
  $: cellsHeld = new Set(recs.map((r) => r.sheet_number));
  $: counts = recs.reduce<Record<string, number>>((n, r) => {
    const k = stageOf(r);
    n[k] = (n[k] ?? 0) + 1;
    return n;
  }, {});
  $: bySource = recs.reduce<Record<string, number>>((n, r) => {
    const k = r.source ?? 'PCL';
    n[k] = (n[k] ?? 0) + 1;
    return n;
  }, {});
  $: shown = stage ? recs.filter((r) => stageOf(r) === stage) : recs.filter((r) => !isLive(r));
  $: rows = [...shown].sort((a, b) =>
    a.sheet_number.localeCompare(b.sheet_number, undefined, { numeric: true })
  );

  async function publish(r: Rec) {
    if (busy) return;
    busy = r.id;
    failed = '';
    const res = await fetch(`/api/admin/maps/${r.id}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ status: 'public' }),
    });
    if (res.ok) recs = recs.map((x) => (x.id === r.id ? { ...x, status: 'public' } : x));
    else failed = `${r.slug ?? r.id}: ${res.status}`;
    busy = '';
  }
</script>

{#if allowed}
  <section class="section-card manage">
    <h2>Manage</h2>
    <p class="lead">
      {recs.length} records in {cellsHeld.size} of {cellCount} cells; {live.size} cells are served. By
      source: {Object.entries(bySource)
        .map(([k, n]) => `${k} ${n}`)
        .join(' · ')}.
    </p>
    <div class="facets">
      {#each Object.entries(STAGES) as [key, label] (key)}
        {#if counts[key]}
          <button
            type="button"
            class="badge-chip is-sm {key === 'published'
              ? 'chip-green'
              : key === 'ready'
                ? 'chip-yellow'
                : 'chip-gray'}"
            class:is-off={stage !== null && stage !== key}
            aria-pressed={stage === key}
            on:click={() => (stage = stage === key ? null : key)}
          >
            {label} <span class="facet-n">{counts[key]}</span>
          </button>
        {/if}
      {/each}
    </div>
    {#if failed}<p class="err" role="alert">Could not publish {failed}</p>{/if}
    <table class="data-table is-dense">
      <thead>
        <tr><th>Sheet</th><th>Name</th><th>Source</th><th>Version</th><th>Stage</th><th></th></tr>
      </thead>
      <tbody>
        {#each rows as r (r.id)}
          <tr>
            <td class="num">{r.sheet_number}</td>
            <td><a href="/catalog/{r.slug ?? r.id}">{r.name ?? '—'}</a></td>
            <td>{r.source ?? 'PCL'}</td>
            <td>{[r.year, r.edition && `ed. ${r.edition}`].filter(Boolean).join(' · ') || '—'}</td>
            <td>{STAGES[stageOf(r)]}</td>
            <td>
              {#if stageOf(r) === 'ready'}
                <button class="btn is-sm" disabled={!!busy} on:click={() => publish(r)}>
                  {busy === r.id ? 'Publishing…' : 'Publish'}
                </button>
              {:else if stageOf(r) === 'needs_placement'}
                <a href="/catalog/{r.slug ?? r.id}">Place →</a>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if !rows.length}<p class="found">Nothing in this stage.</p>{/if}
  </section>
{/if}

<style>
  .manage {
    margin-bottom: var(--space-4, 1rem);
  }
  .facets {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.75rem 0;
  }
  .err {
    color: var(--color-danger, #b00020);
  }
</style>
