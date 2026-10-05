<!--
  MapClickCapture.svelte — Headless component that captures map clicks.
  Lives inside MapShell slot to access the shell context.
  Dispatches 'click' events with [lon, lat] coordinates.
-->
<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { toLonLat } from 'ol/proj';
  import type Map from 'ol/Map';
  import type { Unsubscriber } from 'svelte/store';

  import { getShellContext } from '$lib/map/shell/context';

  const dispatch = createEventDispatcher<{
    mapClick: { lon: number; lat: number };
  }>();

  export let enabled = false;

  const { map: mapWritable } = getShellContext();

  let olMap: Map | null = null;
  let unsub: Unsubscriber | null = null;

  function handleClick(event: any) {
    if (!enabled || !olMap || olMap.get('legendPointPicking')) return;
    const coord = event.coordinate;
    const [lon, lat] = toLonLat(coord);
    dispatch('mapClick', { lon, lat });
  }

  onMount(() => {
    unsub = mapWritable.subscribe(($map) => {
      if (!$map || olMap) return;
      olMap = $map;
      olMap.on('click', handleClick);
    });
  });

  onDestroy(() => {
    unsub?.();
    if (olMap) {
      olMap.un('click', handleClick);
    }
  });
</script>
