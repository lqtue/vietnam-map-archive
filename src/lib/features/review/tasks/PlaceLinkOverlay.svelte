<!--
  PlaceLinkOverlay.svelte — what the page draws over a plain crop of the sheet: the label's box, the
  candidates (shown arm only), the north arrow and the scale bar.

  Everything is in the image's own pixel units (`viewBox="0 0 out out"`), so a marker sits on the
  pixel it names at any display size and no JS measures the DOM. The crop carries nothing the
  machine made: on the blind arm `candidates` is empty and nothing of its answer is drawn.
-->
<script lang="ts">
  import type { Candidate, CropView, PlaceLinkPayload } from '../types';

  export let view: CropView;
  export let payload: PlaceLinkPayload;
  export let candidates: Candidate[] = [];
  /** 1-based index of the picked candidate, or null. */
  export let picked: number | null = null;

  const COLOURS = ['var(--color-primary)', 'var(--color-blue)', 'var(--color-green)'];

  $: z = view.out / view.side;
  const at = (v: CropView, p: [number, number]): [number, number] => [
    ((p[0] - v.x0) * v.out) / v.side,
    ((p[1] - v.y0) * v.out) / v.side,
  ];
  $: box = payload.box
    ? {
        x: at(view, [payload.box[0], payload.box[1]])[0],
        y: at(view, [payload.box[0], payload.box[1]])[1],
        w: payload.box[2] * z,
        h: payload.box[3] * z,
      }
    : null;
  $: dot = payload.pos_from === 'px' ? at(view, payload.px) : null;
  $: [nx, ny] = payload.sheet.north_px;
  // The north arrow sits in the lower right; the bar in the lower left.
  $: ox = view.out - 70;
  $: oy = view.out - 70;
  $: head = [ox + nx * 36, oy + ny * 36];
  $: tail = [ox - nx * 36, oy - ny * 36];
  $: wing = [-ny, nx];
  $: barLen = (view.bar_m / payload.sheet.m_per_px) * z;
  const points = (pts: [number, number][]) => pts.map((p) => at(view, p).join(',')).join(' ');
</script>

<svg viewBox="0 0 {view.out} {view.out}" aria-hidden="true" focusable="false">
  {#if box}
    <rect class="label-box" x={box.x} y={box.y} width={box.w} height={box.h} />
  {/if}
  {#if dot}
    <circle class="label-box" cx={dot[0]} cy={dot[1]} r="7" />
  {/if}
  {#each candidates as cand, k (cand.id)}
    {#if cand.outline_px && cand.outline_px.length > 1}
      <polyline
        class="outline"
        class:picked={picked === k + 1}
        style:stroke={COLOURS[k % 3]}
        points={points([
          ...cand.outline_px,
          ...(cand.outline_px.length > 2 ? [cand.outline_px[0]] : []),
        ])}
      />
    {/if}
    <g class="marker" class:picked={picked === k + 1} style:--marker={COLOURS[k % 3]}>
      <circle cx={at(view, cand.px)[0]} cy={at(view, cand.px)[1]} r="13" />
      <text x={at(view, cand.px)[0]} y={at(view, cand.px)[1]}>{k + 1}</text>
    </g>
  {/each}

  <g class="furniture">
    <circle cx={ox} cy={oy} r="52" class="plate" />
    <line x1={tail[0]} y1={tail[1]} x2={head[0]} y2={head[1]} class="stroke" />
    <polygon
      class="fill"
      points="{head[0]},{head[1]} {head[0] - nx * 16 + wing[0] * 9},{head[1] -
        ny * 16 +
        wing[1] * 9} {head[0] - nx * 16 - wing[0] * 9},{head[1] - ny * 16 - wing[1] * 9}"
    />
    <text class="n" x={head[0] + nx * 14} y={head[1] + ny * 14}>N</text>
    <rect class="plate" x="12" y={view.out - 40} width={barLen + 12} height="28" />
    <line class="stroke" x1="18" y1={view.out - 22} x2={18 + barLen} y2={view.out - 22} />
    <text class="bar-label" x="18" y={view.out - 28}>{view.bar_m} m</text>
  </g>
</svg>

<style>
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }
  .label-box {
    fill: none;
    stroke: var(--color-yellow);
    stroke-width: 3;
  }
  .outline {
    fill: none;
    stroke-width: 2;
  }
  .outline.picked {
    stroke-width: 5;
  }
  .marker circle {
    fill: var(--marker);
    stroke: var(--light-paper);
    stroke-width: 2;
  }
  .marker.picked circle {
    stroke: var(--light-ink);
    stroke-width: 4;
  }
  .marker text {
    fill: var(--light-paper);
    font-size: 22px;
    font-weight: var(--font-bold);
    text-anchor: middle;
    dominant-baseline: central;
  }
  /* Printed furniture: ink on paper whatever the theme, like the scan under it. */
  .plate {
    fill: var(--light-paper);
  }
  .stroke {
    stroke: var(--light-ink);
    stroke-width: 5;
  }
  .fill {
    fill: var(--light-ink);
  }
  .n {
    fill: var(--light-ink);
    font-size: 22px;
    text-anchor: middle;
    dominant-baseline: central;
  }
  .bar-label {
    fill: var(--light-ink);
    font-size: 14px;
  }
</style>
