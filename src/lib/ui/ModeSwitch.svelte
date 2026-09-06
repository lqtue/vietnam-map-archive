<!--
  ModeSwitch.svelte — the mode strip for a tool sheet.

  It renders into the sheet's MARGIN, not over the field. The first version of
  this floated at top-centre above the map and swallowed clicks meant for the
  panels underneath it — which is exactly the failure the margin exists to
  prevent. Chrome annotates the field from outside it.

  Links, not buttons: a mode is a URL, so it is shareable, bookmarkable and
  reachable with a middle click.
-->
<script lang="ts">
  export let modes: { id: string; label: string }[] = [];
  export let current = '';
  /** Route path the modes hang off, e.g. '/explore'. */
  export let base = '';
  /** Params to carry across a mode switch — `?map=` above all. */
  export let carry: URLSearchParams | null = null;
  export let label = 'Mode';

  function href(id: string): string {
    const q = new URLSearchParams();
    q.set('mode', id);
    const map = carry?.get('map');
    if (map) q.set('map', map);
    return `${base}?${q}`;
  }
</script>

<nav class="modes" aria-label={label}>
  {#each modes as mode (mode.id)}
    <a
      href={href(mode.id)}
      class="btn btn--xs"
      aria-current={mode.id === current ? 'page' : undefined}
    >
      {mode.label}
    </a>
  {/each}
</nav>

<style>
  .modes {
    display: flex;
    gap: var(--s-1);
  }

  .modes a {
    text-decoration: none;
  }

  .modes a[aria-current='page'] {
    color: var(--accent);
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }
</style>
