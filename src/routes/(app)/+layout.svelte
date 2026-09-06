<!--
  Tools: darkroom surface, tool sheet.

  Historical scans are light. A light interface around a light scan gives the
  eye nothing to separate them by, which is why every serious map tool puts a
  dark ground around imagery. The surface is chosen by the route, never by the
  visitor — there is no theme toggle.

  variant="tool" hands the whole field to the map and collapses the margin to
  the two annotation strips. The mode strip goes in the margin: this layout
  owns the margin, and a switcher floated over the field intercepts clicks
  meant for the panels beneath it.
-->
<script lang="ts">
  import { page } from '$app/stores';
  import Sheet from '$lib/ui/Sheet.svelte';
  import NavBar from '$lib/ui/NavBar.svelte';
  import ModeSwitch from '$lib/ui/ModeSwitch.svelte';

  /* Two tool sheets, each with its own modes. /explore is the MapShell surface
     and /scan the ImageShell one, which is the real line between them — the
     map stays warm across a mode change, and the two shells never share a
     mount. `/trip/[id]` has no modes: it is one printed QR code deep. */
  const MODES: Record<string, { label: string; modes: { id: string; label: string }[] }> = {
    '/explore': {
      label: 'Map mode',
      modes: [
        { id: 'browse', label: 'Browse' },
        { id: 'annotate', label: 'Annotate' },
        { id: 'story', label: 'Story' },
      ],
    },
    '/scan': {
      label: 'Scan mode',
      modes: [
        { id: 'inspect', label: 'Inspect' },
        { id: 'triage', label: 'Triage' },
        { id: 'trace', label: 'Trace' },
        { id: 'review', label: 'Review' },
      ],
    },
  };

  $: base = $page.url.pathname;
  $: config = MODES[base] ?? null;
  $: current = $page.url.searchParams.get('mode') ?? config?.modes[0]?.id ?? '';
</script>

<div class="surface-darkroom">
  <Sheet variant="tool">
    <svelte:fragment slot="cartouche">
      <NavBar session={$page.data.session} />
    </svelte:fragment>

    <svelte:fragment slot="margin-top-right">
      {#if config}
        <ModeSwitch
          {base}
          {current}
          label={config.label}
          modes={config.modes}
          carry={$page.url.searchParams}
        />
      {/if}
    </svelte:fragment>

    <slot />
  </Sheet>
</div>
