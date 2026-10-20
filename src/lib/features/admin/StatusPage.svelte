<script lang="ts">
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import '$styles/pages/admin-status.css';

  /*
    The archive's own review queue. /scan?mode=shapes&tab=validate lets a person check what
    the machine did to a map; this page lets a person check what the machine did
    to the archive. Every number here was previously reachable only by running
    SQL by hand.

    All the wording lives in `build()` below — one place to edit a sentence, and
    one place to add a row. The API route next door only counts things.
  */

  type Tone = 'good' | 'warn' | 'bad' | 'idle';
  type Row = { label: string; value: string; detail: string; tone: Tone; next?: string };
  type Section = { title: string; blurb: string; rows: Row[] };

  type Status = {
    checkedAt: string;
    maps: {
      total: number;
      published: number;
      drafts: number;
      georeferenced: number;
      withBbox: number;
      read: number;
      triaged: number;
      proposed: number;
      withLayout: number;
    };
    words: { total: number; placed: number; placeNames: number };
    footprints: { total: number; byMachine: number; approved: number; awaitingReview: number };
    reviews: { tasksOpen: number; items: number; verdicts: number; blind: number };
    jobs: {
      queued: number;
      running: number;
      failed: number;
      failures: { kind: string; map_id: string | null; attempts: number; error: string | null }[];
    };
  };

  // ── access ────────────────────────────────────────────────────────────────
  const { supabase, session } = getSupabaseContext();
  let role: 'user' | 'mod' | 'admin' = 'user';
  let roleChecked = false;

  // ── data ──────────────────────────────────────────────────────────────────
  let data: Status | null = null;
  let loading = false;
  let loadError = '';

  async function load() {
    loading = true;
    loadError = '';
    try {
      const r = await fetch('/api/admin/status');
      if (!r.ok) throw new Error(await r.text());
      data = await r.json();
    } catch (e: unknown) {
      loadError = (e as Error).message.slice(0, 300);
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    if (!session?.user?.id) {
      roleChecked = true;
      return;
    }
    role = (await fetchUserRole(supabase, session.user.id)) ?? 'user';
    roleChecked = true;
    if (role === 'admin' || role === 'mod') load();
  });

  // ── wording ───────────────────────────────────────────────────────────────
  const num = (n: number) => n.toLocaleString('en-US');
  const of = (a: number, b: number) => `${num(a)} of ${num(b)}`;

  function build(d: Status): Section[] {
    const m = d.maps;
    const w = d.words;
    const f = d.footprints;
    const j = d.jobs;
    const r = d.reviews;

    const unread = m.georeferenced - m.read;
    const unplaced = w.total - w.placed;

    return [
      {
        title: 'The archive',
        blurb: 'How many maps you hold, and how many are ready to be worked on.',
        rows: [
          {
            label: 'Maps in the archive',
            value: num(m.total),
            detail: `Every scan in the collection. ${num(m.published)} are visible to the public; ${num(m.drafts)} are still private drafts.`,
            tone: 'idle',
          },
          {
            label: 'Pinned to the real world',
            value: of(m.georeferenced, m.total),
            detail:
              'A pinned map knows where it sits on the globe, so it can be laid over a modern one. Nothing else in the pipeline can run until a map is pinned.',
            tone: m.georeferenced === m.total ? 'good' : 'warn',
            next:
              m.total - m.georeferenced > 0
                ? `${num(m.total - m.georeferenced)} still need a person. Open /contribute/georef.`
                : undefined,
          },
          {
            label: 'Sheet outlines saved',
            value: of(m.withBbox, m.georeferenced),
            detail:
              'The rectangle of ground each map covers. Without it, asking "which maps show this spot?" returns nothing, even though the maps are pinned.',
            tone: m.withBbox === 0 ? 'bad' : m.withBbox < m.georeferenced ? 'warn' : 'good',
            next:
              m.withBbox < m.georeferenced
                ? 'Needs a one-off backfill script, same shape as the warp job.'
                : undefined,
          },
        ],
      },
      {
        title: 'Getting sheets ready to read',
        blurb:
          'The AI now proposes where the map sits on the paper and which squares are blank or water. A person looks at that proposal and accepts it. Nothing is read — and nothing is paid for — until someone has.',
        rows: [
          {
            label: 'Sheets a person has accepted',
            value: of(m.triaged, m.georeferenced),
            detail:
              m.triaged === 0
                ? 'None yet. The queueing script only takes accepted sheets, so running it now would queue nothing and look like it worked.'
                : 'These are the ones the queueing script will take.',
            tone: m.triaged === 0 ? 'bad' : m.triaged < m.georeferenced ? 'warn' : 'good',
            next:
              m.triaged < m.georeferenced
                ? 'Open a proposed sheet at /scan?mode=prepare, check the border it suggests, and press Save triage. That is the acceptance.'
                : undefined,
          },
          {
            label: 'Proposed, waiting to be looked at',
            value: of(m.proposed, m.georeferenced),
            detail:
              'The AI has already worked out the border on these. Each one needs a person to glance at it and accept — that is the whole remaining step.',
            tone: m.proposed > 0 ? 'warn' : 'good',
            next: m.proposed > 0 ? 'Work through them at /scan?mode=prepare.' : undefined,
          },
          {
            label: 'Sheets the AI has mapped out',
            value: of(m.withLayout, m.georeferenced),
            detail:
              'The layout pass guesses what each part of the sheet is — the map itself, the title, the legend, insets — so a person corrects boxes instead of drawing them.',
            tone: m.withLayout === 0 ? 'warn' : 'good',
            next:
              m.withLayout < m.georeferenced
                ? 'Run scripts/queue/enqueue_layout_all.mjs for the whole collection at once, then leave a worker running. It proposes the border too.'
                : undefined,
          },
        ],
      },
      {
        title: 'Words lifted off the maps',
        blurb:
          'The AI reads place names and street names off each scan. This is what it has found.',
        rows: [
          {
            label: 'Maps that have been read',
            value: of(m.read, m.georeferenced),
            detail:
              'Only a map that has been read can be searched by name. The rest are pictures as far as search is concerned.',
            tone: m.read === 0 ? 'bad' : m.read < m.georeferenced ? 'warn' : 'good',
            next:
              unread > 0
                ? `${num(unread)} pinned maps have never been read. Queue them with scripts/queue/enqueue_ocr_all.mjs, then run the worker.`
                : undefined,
          },
          {
            label: 'Words found',
            value: num(w.total),
            detail: 'Every label the reader lifted off a scan, before any checking.',
            tone: 'idle',
          },
          {
            label: 'Words placed on the ground',
            value: of(w.placed, w.total),
            detail:
              unplaced > 0
                ? `These have real coordinates, so a search jumps straight to the spot. The other ${num(unplaced)} were read without a box on the page, so there is no position to work out.`
                : 'Every word has real coordinates, so a search jumps straight to the spot.',
            tone: w.total === 0 ? 'idle' : w.placed === 0 ? 'bad' : 'good',
          },
          {
            label: 'Distinct place names',
            value: num(w.placeNames),
            detail:
              'The gazetteer: every spelling of every place, grouped together, with the years it appears. This is what feeds the newspaper search.',
            tone: 'idle',
          },
        ],
      },
      {
        title: 'Buildings and shapes',
        blurb: 'Traced outlines of buildings, blocks, roads and waterways.',
        rows: [
          {
            label: 'Outlines traced',
            value: num(f.total),
            detail: `${num(f.approved)} approved, ${num(f.awaitingReview)} still waiting for someone to look at them.`,
            tone: 'idle',
          },
          {
            label: 'Drawn by the AI',
            value: of(f.byMachine, f.total),
            detail:
              f.byMachine === 0
                ? 'Everything so far was traced by hand. The AI that draws building outlines has never produced a single shape.'
                : 'Shapes the segmentation model produced, before or after a person corrected them.',
            tone: f.byMachine === 0 ? 'bad' : 'good',
            next:
              f.byMachine === 0
                ? 'Needs a Colab session with a GPU running the worker with --kinds seg.'
                : undefined,
          },
          {
            label: 'Waiting for review',
            value: num(f.awaitingReview),
            detail:
              'Shapes a person needs to approve or reject, in /scan?mode=shapes&tab=validate.',
            tone: f.awaitingReview > 0 ? 'warn' : 'good',
          },
        ],
      },
      {
        title: 'Checking the machine',
        blurb:
          'A check only counts if a person could have disagreed. Here a person judges the machine’s proposal, and on some items the proposal is hidden first.',
        rows: [
          {
            label: 'Check tasks open',
            value: num(r.tasksOpen),
            detail:
              r.tasksOpen > 0
                ? 'Tasks that people can sit and judge.'
                : 'No task is open, so the web review page shows nothing. The offline pages (ports 8792 and 8793) work without one.',
            tone: 'idle',
          },
          {
            label: 'Items on the open tasks',
            value: num(r.items),
            detail:
              'Each item is one question for a person, such as which place a sheet label points to.',
            tone: 'idle',
          },
          {
            label: 'Verdicts recorded',
            value: num(r.verdicts),
            detail:
              r.verdicts === 0
                ? 'None yet. Every error rate and seconds-per-item figure still comes from the offline sittings.'
                : 'Judgements people have given on the web page, after undos.',
            tone: r.verdicts === 0 ? 'warn' : 'good',
          },
          {
            label: 'Judged with the machine’s answer hidden',
            value: of(r.blind, r.verdicts),
            detail:
              'Without these, agreement with the machine can only echo it. About one item in five has the answer hidden.',
            tone: 'idle',
          },
        ],
      },
      {
        title: 'The work queue',
        blurb: 'Jobs handed to a worker machine. If something is stuck, this is where it shows up.',
        rows: [
          {
            label: 'Waiting to start',
            value: num(j.queued),
            detail:
              j.queued > 0
                ? 'Queued and waiting. Nothing happens until a worker is running and claims them.'
                : 'Nothing queued. The pipeline is idle by choice, not by fault.',
            tone: j.queued > 0 ? 'warn' : 'idle',
            next: j.queued > 0 ? 'Start a worker to drain these.' : undefined,
          },
          {
            label: 'Running now',
            value: num(j.running),
            detail:
              j.running > 0
                ? 'A worker has claimed these and is working on them.'
                : 'No worker is currently doing anything.',
            tone: 'idle',
          },
          {
            label: 'Failed',
            value: num(j.failed),
            detail:
              j.failed > 0
                ? 'These gave up after retrying. They will not run again on their own.'
                : 'Nothing has failed.',
            tone: j.failed > 0 ? 'bad' : 'good',
          },
        ],
      },
    ];
  }

  $: sections = data ? build(data) : [];
  // The most urgent thing, chosen the same way a person would: the first
  // blocking row that names its own next step.
  $: headline = sections.flatMap((s) => s.rows).find((r) => r.tone === 'bad' && r.next);
  $: checked = data ? new Date(data.checkedAt).toLocaleString() : '';
</script>

<svelte:head>
  <title>System status · VMA Admin</title>
  <meta name="description" content="What the archive holds and what is blocked." />
</svelte:head>

<div class="status-page">
  <header class="status-head">
    <h2 class="section-title-sm">System status in plain words.</h2>
    <p class="section-desc">
      What the archive actually holds right now, what is stuck, and what would unstick it.
    </p>
  </header>

  {#if !roleChecked}
    <p class="empty-state is-block">Checking access…</p>
  {:else if role !== 'admin' && role !== 'mod'}
    <p class="empty-state is-block">Admin access required.</p>
  {:else}
    <div class="status-bar">
      <button class="chip" on:click={load} disabled={loading}>
        {loading ? 'Checking…' : 'Refresh'}
      </button>
      {#if checked}<span class="status-checked">Last checked {checked}</span>{/if}
    </div>

    {#if loadError}
      <p class="empty-state is-block error">Could not load: {loadError}</p>
    {:else if !data}
      <p class="empty-state is-block">Reading the archive…</p>
    {:else}
      {#if headline}
        <section class="status-headline">
          <div class="status-headline-label">Biggest blocker</div>
          <p class="status-headline-text">{headline.label} — {headline.detail}</p>
          <p class="status-headline-next">{headline.next}</p>
        </section>
      {/if}

      {#each sections as section (section.title)}
        <section class="status-section">
          <h2 class="section-title-sm">{section.title}</h2>
          <p class="section-desc status-blurb">{section.blurb}</p>

          <div class="status-rows">
            {#each section.rows as row (row.label)}
              <article class="status-row tone-{row.tone}">
                <div class="status-row-head">
                  <h3 class="status-row-label">{row.label}</h3>
                  <div class="status-row-value">{row.value}</div>
                </div>
                <p class="status-row-detail">{row.detail}</p>
                {#if row.next}
                  <p class="status-row-next"><span>Next</span> {row.next}</p>
                {/if}
              </article>
            {/each}
          </div>
        </section>
      {/each}

      {#if data.jobs.failures.length}
        <section class="status-section">
          <h2 class="section-title-sm">What failed</h2>
          <p class="section-desc status-blurb">
            The most recent failures, newest first. The message is whatever the worker reported.
          </p>
          <div class="status-rows">
            {#each data.jobs.failures as f, i (i)}
              <article class="status-row tone-bad">
                <div class="status-row-head">
                  <h3 class="status-row-label">{f.kind}</h3>
                  <div class="status-row-value status-row-value-sm">
                    {f.attempts}
                    {f.attempts === 1 ? 'try' : 'tries'}
                  </div>
                </div>
                <p class="status-row-detail">{f.error ?? 'No message was recorded.'}</p>
                {#if f.map_id}
                  <p class="status-row-next">
                    <span>Map</span>
                    <a href="/explore?map={f.map_id}">{f.map_id.slice(0, 8)}</a>
                  </p>
                {/if}
              </article>
            {/each}
          </div>
        </section>
      {/if}
    {/if}
  {/if}
</div>
