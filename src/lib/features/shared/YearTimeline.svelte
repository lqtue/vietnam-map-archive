<!--
  YearTimeline.svelte — the catalog's year filter: a decade histogram you drag across.

  Era bands sit on top of the bars, each labelled with the year it starts, and a click on a band
  takes its whole span. Drag selects any run of years, a click on a bar takes
  that decade, and From/To stay for typing an exact year — they are also the keyboard path, as the
  chart itself is pointer-only. Bars are the caller's counts, already narrowed by every other facet.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { t } from '$lib/core/i18n';

  export let bins: { decade: number; count: number }[];
  export let from = '';
  export let to = '';

  const dispatch = createEventDispatcher<{ change: [string, string] }>();

  // ponytail: hand-listed spans for the Saigon archive; lift to core/ if another page needs them.
  const ERAS: [number, number][] = [
    [0, 1858],
    [1859, 1945],
    [1946, 1954],
    [1955, 1975],
    [1976, 9999],
  ];

  let chart: HTMLElement;
  let draft: [number, number] | null = null;
  let anchor = 0;
  let downX = 0;
  let hover: number | null = null;

  $: start = bins[0].decade;
  $: end = bins[bins.length - 1].decade + 10;
  $: span = end - start;
  $: maxCount = Math.max(1, ...bins.map((b) => b.count));
  $: bands = ERAS.map(([a, b], i) => ({
    a,
    b,
    i,
    left: (Math.max(a, start) - start) / span,
    width: (Math.min(b + 1, end) - Math.max(a, start)) / span,
  })).filter((e) => e.width > 0);

  $: committed = (from || to ? [from ? Number(from) : start, to ? Number(to) : end - 1] : null) as
    [number, number] | null;
  $: sel = draft ?? committed;
  $: selStyle = sel
    ? {
        left: (Math.max(sel[0], start) - start) / span,
        width: Math.max(0, Math.min(sel[1] + 1, end) - Math.max(sel[0], start)) / span,
      }
    : null;
  $: ticks = bins.filter((b, i) => i === 0 || b.decade % 20 === 0);

  const yearAt = (x: number) => {
    const r = chart.getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (x - r.left) / r.width));
    return Math.min(end - 1, start + Math.floor(f * span));
  };
  const commit = (a: number, b: number) =>
    dispatch('change', [String(Math.min(a, b)), String(Math.max(a, b))]);

  function down(e: PointerEvent) {
    chart.setPointerCapture(e.pointerId);
    downX = e.clientX;
    anchor = yearAt(e.clientX);
    draft = [anchor, anchor];
  }
  function move(e: PointerEvent) {
    const y = yearAt(e.clientX);
    hover = y;
    if (draft) draft = [Math.min(anchor, y), Math.max(anchor, y)];
  }
  function up(e: PointerEvent) {
    if (!draft) return;
    if (Math.abs(e.clientX - downX) < 4) {
      // a click, not a drag: take the decade, or let go of it if it is already the selection
      const d = Math.floor(anchor / 10) * 10;
      if (from === String(d) && to === String(d + 9)) dispatch('change', ['', '']);
      else commit(d, d + 9);
    } else commit(draft[0], draft[1]);
    draft = null;
  }

  $: hoverBin =
    hover == null ? null : bins.find((b) => hover! >= b.decade && hover! < b.decade + 10);
</script>

<div class="timeline">
  <p class="readout" aria-live="polite">
    {#if hoverBin && !draft}
      <b>{hoverBin.decade}s</b>
      {hoverBin.count.toLocaleString()}
      {$t('maps')}
    {:else if sel}
      <b>{sel[0] === sel[1] ? sel[0] : `${sel[0]}–${sel[1]}`}</b>
      {#if !draft}<button type="button" class="link" on:click={() => dispatch('change', ['', ''])}
          >{$t('Clear')}</button
        >{/if}
    {:else}
      <span class="hint">{$t('Drag across the timeline to pick a range')}</span>
    {/if}
  </p>

  <!-- Pointer-only on purpose: the era buttons and From/To below do the same job from the keyboard. -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="chart"
    class:has-sel={!!sel}
    bind:this={chart}
    on:pointerdown={down}
    on:pointermove={move}
    on:pointerup={up}
    on:pointercancel={() => (draft = null)}
    on:pointerleave={() => (hover = null)}
  >
    <div class="bands">
      {#each bands as e (e.i)}
        {@const on = from === String(Math.max(e.a, start)) && to === String(Math.min(e.b, end - 1))}
        <button
          type="button"
          class="band"
          class:is-on={on}
          aria-pressed={on}
          on:pointerdown|stopPropagation
          on:pointerup|stopPropagation
          on:click={() =>
            on
              ? dispatch('change', ['', ''])
              : commit(Math.max(e.a, start), Math.min(e.b, end - 1))}
          style:left="{e.left * 100}%"
          style:width="{e.width * 100}%"
          style:--tint="{10 + (e.i % 2) * 14}%"
          title="{e.a > 0 ? e.a : ''}–{e.b < 9999 ? e.b : ''}">{Math.max(e.a, start)}</button
        >
      {/each}
    </div>
    <div class="bars" role="img" aria-label={$t('Maps per decade')}>
      {#each bins as b (b.decade)}
        <span
          class="bar"
          style:height="{b.count ? Math.max(6, Math.sqrt(b.count / maxCount) * 100) : 1}%"
        ></span>
      {/each}
    </div>
    {#if selStyle}
      <span class="sel" style:left="{selStyle.left * 100}%" style:width="{selStyle.width * 100}%"
      ></span>
    {/if}
    <div class="axis" aria-hidden="true">
      {#each ticks as b (b.decade)}
        <span style:left="{((b.decade - start) / span) * 100}%">{b.decade}</span>
      {/each}
    </div>
  </div>

  <div class="controls">
    <div class="span">
      <label
        >{$t('From')}
        <input
          type="number"
          inputmode="numeric"
          placeholder={String(start)}
          value={from}
          on:change={(e) => dispatch('change', [e.currentTarget.value, to])}
        /></label
      >
      <label
        >{$t('To')}
        <input
          type="number"
          inputmode="numeric"
          placeholder={String(end - 1)}
          value={to}
          on:change={(e) => dispatch('change', [from, e.currentTarget.value])}
        /></label
      >
    </div>
  </div>
</div>

<style>
  .timeline {
    padding-top: 0.5rem;
  }
  .readout {
    margin: 0 0 0.3rem;
    min-height: 1.2rem;
    font-size: 0.78rem;
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
  }
  .hint {
    opacity: 0.7;
  }
  .link {
    margin-left: auto;
    padding: 0;
    font: inherit;
    background: none;
    border: none;
    color: var(--sb-accent);
    text-decoration: underline;
    cursor: pointer;
  }
  .chart {
    position: relative;
    padding-bottom: 1.1rem;
    cursor: crosshair;
    touch-action: pan-y;
    user-select: none;
  }
  .bands {
    position: relative;
    height: 1.2rem;
  }
  .band {
    position: absolute;
    top: 0;
    bottom: 0;
    box-sizing: border-box;
    padding: 0 0.3rem;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: 0.66rem;
    line-height: 1.2rem;
    background: color-mix(in srgb, var(--sb-accent) var(--tint), transparent);
    border: none;
    border-left: 1px solid var(--color-bg, transparent);
    color: inherit;
    text-align: left;
    font-family: inherit;
    cursor: pointer;
  }
  .band:hover,
  .band.is-on {
    background: color-mix(in srgb, var(--sb-accent) 45%, transparent);
  }
  .bars {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 2.8rem;
    border-bottom: var(--border-thin);
  }
  .bar {
    flex: 1 1 0;
    min-width: 2px;
    background: var(--sb-accent);
  }
  .has-sel .bar {
    opacity: 0.35;
  }
  /* The selection is a window over the bands and bars: it lifts them back to full strength and
     draws two edges, so the span reads as a thing you could drag again. */
  .sel {
    position: absolute;
    top: 0;
    height: calc(1.2rem + 2.8rem);
    box-sizing: border-box;
    border-left: 2px solid var(--color-text);
    border-right: 2px solid var(--color-text);
    background: color-mix(in srgb, var(--sb-accent) 14%, transparent);
    pointer-events: none;
  }
  .axis {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 1rem;
    font-size: 0.64rem;
    opacity: 0.75;
  }
  .axis span {
    position: absolute;
    top: 0.15rem;
    transform: translateX(-50%);
  }
  .axis span:first-child {
    transform: none;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.4rem 0.75rem;
    padding-top: 0.2rem;
  }
  .span {
    display: flex;
    gap: 0.5rem;
    font-size: 0.78rem;
  }
  .span label {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }
  .span input {
    width: 4.5rem;
    padding: 0.25rem 0.35rem;
    font: inherit;
    background: var(--sb-card-bg);
    border: var(--border-thin);
    border-radius: var(--sb-radius-sm);
  }
</style>
