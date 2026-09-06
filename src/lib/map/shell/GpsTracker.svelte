<!--
  GpsTracker.svelte — GPS position tracking overlay for /view mode.

  Headless component: creates OL layers for position dot + track line.
  Reads the OL Map from shell context.
-->
<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { get } from 'svelte/store';
  import Feature from 'ol/Feature';
  import LineString from 'ol/geom/LineString';
  import Point from 'ol/geom/Point';
  import VectorSource from 'ol/source/Vector';
  import VectorImageLayer from 'ol/layer/VectorImage';
  import Style from 'ol/style/Style';
  import Stroke from 'ol/style/Stroke';
  import Fill from 'ol/style/Fill';
  import CircleStyle from 'ol/style/Circle';
  import { fromLonLat } from 'ol/proj';
  import type { Coordinate } from 'ol/coordinate';
  import type Map from 'ol/Map';

  import { startTracking, stopTracking, formatError } from '$lib/core/geo/geolocation';
  import type { TrackingState } from '$lib/core/geo/types';
  import { getShellContext } from '$lib/map/shell/context';

  const dispatch = createEventDispatcher<{
    position: { lon: number; lat: number };
    stateChange: { state: TrackingState };
    error: { message: string };
  }>();

  export let active = false;
  export let autoFollow = true;
  export let showTrack = true;

  const { map: mapWritable } = getShellContext();

  let olMap: Map | null = null;
  let trackSource: VectorSource | null = null;
  let trackLayer: VectorImageLayer<VectorSource> | null = null;
  let positionSource: VectorSource | null = null;
  let positionLayer: VectorImageLayer<VectorSource> | null = null;
  let currentTrack: Feature<LineString> | null = null;
  let currentPosition: Feature<Point> | null = null;
  let coordinates: Coordinate[] = [];
  let watchId: number | null = null;
  let trackingState: TrackingState = 'inactive';

  // Literal hex on purpose: OpenLayers style objects are canvas fills, not CSS —
  // they cannot read a custom property.
  function createTrackStyle(): Style {
    return new Style({
      stroke: new Stroke({ color: '#ea580c', width: 4, lineCap: 'round', lineJoin: 'round' }),
    });
  }

  function createPositionStyle(): Style {
    return new Style({
      image: new CircleStyle({
        radius: 8,
        fill: new Fill({ color: '#ffffff' }),
        stroke: new Stroke({ color: '#ea580c', width: 3 }),
      }),
    });
  }

  function handlePositionUpdate(position: GeolocationPosition) {
    const { longitude, latitude } = position.coords;
    const coord = fromLonLat([longitude, latitude]);

    coordinates = [...coordinates, coord];

    if (showTrack && trackSource) {
      if (!currentTrack) {
        currentTrack = new Feature({ geometry: new LineString(coordinates) });
        currentTrack.setId('gps-track');
        trackSource.addFeature(currentTrack);
      } else {
        currentTrack.getGeometry()?.setCoordinates(coordinates);
      }
    }

    if (positionSource) {
      if (!currentPosition) {
        currentPosition = new Feature({ geometry: new Point(coord) });
        currentPosition.setId('gps-position');
        positionSource.addFeature(currentPosition);
      } else {
        currentPosition.getGeometry()?.setCoordinates(coord);
      }
    }

    if (autoFollow && olMap) {
      olMap.getView().animate({ center: coord, duration: 300 });
    }

    dispatch('position', { lon: longitude, lat: latitude });
  }

  function start() {
    if (trackingState !== 'inactive') return;
    coordinates = [];
    currentTrack = null;
    currentPosition = null;
    trackSource?.clear();
    positionSource?.clear();

    watchId = startTracking({
      onPosition: handlePositionUpdate,
      onError: (err) => {
        const message = formatError(err);
        dispatch('error', { message });
        trackingState = 'inactive';
        dispatch('stateChange', { state: 'inactive' });
        if (watchId !== null) {
          stopTracking(watchId);
          watchId = null;
        }
      },
    });

    if (watchId !== null) {
      trackingState = 'active';
      dispatch('stateChange', { state: 'active' });
    }
  }

  function stop() {
    if (watchId !== null) {
      stopTracking(watchId);
      watchId = null;
    }
    trackingState = 'inactive';
    dispatch('stateChange', { state: 'inactive' });
  }

  $: if (active && trackingState === 'inactive') start();
  $: if (!active && trackingState === 'active') stop();

  onMount(() => {
    const unsub = mapWritable.subscribe(($map) => {
      if (!$map || olMap) return;
      olMap = $map;

      trackSource = new VectorSource();
      trackLayer = new VectorImageLayer({
        source: trackSource,
        zIndex: 20,
        style: createTrackStyle,
      });

      positionSource = new VectorSource();
      positionLayer = new VectorImageLayer({
        source: positionSource,
        zIndex: 25,
        style: createPositionStyle,
      });

      olMap.addLayer(trackLayer);
      olMap.addLayer(positionLayer);
    });

    return () => {
      unsub();
    };
  });

  onDestroy(() => {
    stop();
    if (olMap) {
      if (trackLayer) olMap.removeLayer(trackLayer);
      if (positionLayer) olMap.removeLayer(positionLayer);
    }
  });
</script>
