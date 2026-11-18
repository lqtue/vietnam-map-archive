<!--
  AerialLabelOverlay.svelte — what the page draws over a plain aerial crop: a ring at the point
  (the crop is centred on it) and a faint 100 m scale bar. The crop itself carries nothing.
  Units are the image's own pixels (`viewBox="0 0 out out"`).
-->
<script lang="ts">
  import type { AerialLabelPayload, CropView, PlaceLinkPayload } from '../types';

  export let view: CropView;
  export let payload: PlaceLinkPayload | AerialLabelPayload;

  $: mPerPx = 'm_per_px' in payload ? payload.m_per_px : 1;
  $: centre = view.out / 2;
  $: barLen = (view.bar_m / mPerPx) * (view.out / view.side);
</script>

<svg viewBox="0 0 {view.out} {view.out}" aria-hidden="true" focusable="false">
  <circle class="ring-halo" cx={centre} cy={centre} r="11" />
  <circle class="ring" cx={centre} cy={centre} r="11" />
  <g class="bar">
    <line class="halo" x1="18" y1={view.out - 22} x2={18 + barLen} y2={view.out - 22} />
    <line class="stroke" x1="18" y1={view.out - 22} x2={18 + barLen} y2={view.out - 22} />
    <text x="18" y={view.out - 28}>{view.bar_m} m</text>
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
  .ring,
  .ring-halo {
    fill: none;
  }
  .ring-halo {
    stroke: var(--light-ink);
    stroke-width: 5;
  }
  .ring {
    stroke: var(--color-yellow);
    stroke-width: 2;
  }
  .bar {
    opacity: 0.6;
  }
  .halo {
    stroke: var(--light-ink);
    stroke-width: 5;
  }
  .stroke {
    stroke: var(--light-paper);
    stroke-width: 2;
  }
  .bar text {
    fill: var(--light-paper);
    font-size: 14px;
    paint-order: stroke;
    stroke: var(--light-ink);
    stroke-width: 3;
  }
</style>
