<script lang="ts">
  import '../styles/global.css';
  import favicon from '$lib/assets/favicon.svg';
  import { afterNavigate, invalidate } from '$app/navigation';
  import { env } from '$env/dynamic/public';
  import { onMount } from 'svelte';
  import { createSupabaseBrowserClient } from '$lib/data/supabase/client';
  import { setSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import {
    getMeasurementConsent,
    initializeMeasurement,
    MEASUREMENT_CONSENT_KEY,
    setMeasurementActor,
    setMeasurementConsent,
    teardownMeasurement,
    trackMeasurementPage,
  } from '$lib/data/measurement';
  import CommandPalette from '$lib/features/shared/CommandPalette.svelte';
  import MeasurementConsent from '$lib/features/shared/MeasurementConsent.svelte';
  import { resolveMeasurementActor } from '$lib/features/shared/measurementLifecycle';
  import { openPalette, isPaletteShortcut, isTypingTarget } from '$lib/core/utils/commandPalette';
  import { page } from '$app/stores';
  import { locale, isLocalizedPath, stripLocale, withLocale } from '$lib/core/i18n';
  import { CANONICAL_HOST, SITE_ORIGIN } from '$lib/core/site';

  export let data;

  // Synchronous, at init: the SSR render reads the store on the very next
  // line of the same tick, so there is no window for a concurrent request to
  // set it to something else. Reactive so a client-side nav keeps it current.
  $: locale.set(data.locale);

  /**
   * Canonical and hreflang for every page in both route groups, computed once
   * here rather than re-typed into sixteen `<svelte:head>` blocks. Only `/`
   * had a canonical before this, so every other URL was its own duplicate
   * across `?tab=`, `?map=` and whatever tracking parameters a share added.
   *
   * The origin is pinned rather than taken from the request: a preview deploy
   * would otherwise declare itself canonical for production's content.
   */
  $: path = stripLocale($page.url.pathname);
  $: localized = isLocalizedPath(path);
  // A translated page's canonical is its own locale's address. On a page with
  // no `/vi` twin the English URL is the only address there is, so a reader
  // who set the cookie still gets Vietnamese chrome at the canonical URL.
  $: canonical = SITE_ORIGIN + (localized && $locale === 'vi' ? withLocale(path) : path);

  const supabase = createSupabaseBrowserClient();
  const measurementId = env.PUBLIC_GA_MEASUREMENT_ID?.trim() ?? '';

  let currentSession = data.session;
  let authReady = false;
  let consentedToMeasurement = false;
  let privacySignal = false;
  let hasNavigated = false;
  let measurementConfigured = false;

  // The palette gates its staff rows on this; null until it resolves, which is
  // the safe direction — a row appears late rather than early. Keyed on the
  // user id so a token refresh does not re-query profiles.
  let role: string | null = null;
  let roleFor: string | null = null;
  $: signedIn = !!currentSession?.user;
  $: loadRole(currentSession?.user?.id ?? null);
  $: roleIsCurrent = !signedIn || roleFor === currentSession?.user?.id;
  $: measurementActor = resolveMeasurementActor(
    authReady && roleIsCurrent,
    signedIn,
    roleIsCurrent ? role : null
  );
  $: measurementAvailable =
    !!measurementId &&
    $page.url.hostname === CANONICAL_HOST &&
    !privacySignal &&
    (measurementActor === 'guest' || measurementActor === 'reader');

  function currentMeasurementActor() {
    const signedInNow = !!currentSession?.user;
    const roleReady = !signedInNow || roleFor === currentSession?.user?.id;
    return resolveMeasurementActor(authReady && roleReady, signedInNow, roleReady ? role : null);
  }

  function syncMeasurement(sendPageView = false) {
    const actor = currentMeasurementActor();
    const host = $page.url.hostname;
    const eligible =
      !!measurementId &&
      host === CANONICAL_HOST &&
      !privacySignal &&
      (actor === 'guest' || actor === 'reader');

    if (!eligible) {
      if (measurementConfigured) setMeasurementActor('unknown');
      return;
    }

    if (!measurementConfigured) {
      // Register no audience class until the safe route context has been set;
      // the service keeps this route in memory while consent is still off.
      initializeMeasurement({ measurementId, actor: 'unknown', hostname: host });
      measurementConfigured = true;
    }

    if (hasNavigated && sendPageView) {
      const path = $page.url.pathname;
      const mode = ['/explore', '/vi/explore', '/scan', '/vi/scan'].includes(path)
        ? ($page.url.searchParams.get('mode') ?? undefined)
        : undefined;
      trackMeasurementPage(path, mode);
    }
    // The route has been registered with actor=unknown first, so a grant or a
    // role resolution can only start the adapter with the actual current page.
    setMeasurementActor(actor);
  }

  function onMeasurementChoice(event: CustomEvent<{ consented: boolean }>) {
    consentedToMeasurement = event.detail.consented;
    setMeasurementConsent(consentedToMeasurement);
    syncMeasurement(true);
  }

  // Only SvelteKit page navigations count. Camera, hash, and selected-map URL
  // changes do not become separate pages; the measurement seam strips unsafe
  // query values and permits only known mode values.
  afterNavigate(() => {
    hasNavigated = true;
    syncMeasurement(true);
  });

  function loadRole(id: string | null) {
    if (id === roleFor) return;
    roleFor = id;
    role = null;
    if (!id) return;
    fetchUserRole(supabase, id)
      .then((r) => {
        if (roleFor === id) {
          role = r;
          syncMeasurement(true);
        }
      })
      .catch(() => {
        // A role lookup failure remains unknown and blocks audience tracking.
      });
  }

  /** ⌘K / Ctrl+K anywhere; "/" only when the visitor is not already typing. */
  function onWindowKeydown(e: KeyboardEvent) {
    if (isPaletteShortcut(e)) {
      e.preventDefault();
      openPalette();
    } else if (e.key === '/' && !isTypingTarget(e.target)) {
      e.preventDefault();
      openPalette();
    }
  }

  // Pass initial session value to context; auth changes trigger full page invalidation
  setSupabaseContext({ supabase, session: data.session });

  onMount(() => {
    // Hydration flag. Every (editorial) page server-renders, so the nav and
    // the hero field are on screen and *look* clickable before any handler is
    // attached — a click in that window is silently dropped. There is nothing
    // to do about that for a reader beyond keeping the bundle small, but a
    // test that clicks at machine speed hits it every time under load, so the
    // smoke suite waits on this rather than on a timeout.
    document.documentElement.dataset.hydrated = 'true';
    consentedToMeasurement = getMeasurementConsent();
    privacySignal =
      navigator.doNotTrack === '1' ||
      (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl === true;

    // Client-side identity is for chrome only — which nav links show, whether
    // the palette offers staff rows. Every actual gate is server-side through
    // requireRole, which reads the getUser()-validated user. So a session off
    // the browser's own cookie is fine here; there is nobody to impersonate.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      const previousExpiry = currentSession?.expires_at;
      const previousUserId = currentSession?.user?.id ?? null;
      const nextUserId = newSession?.user?.id ?? null;
      const identityChanged = previousUserId !== nextUserId;
      const firstAuthResolution = !authReady;
      if (identityChanged) {
        // Revoke the prior actor before replacing the session. A new role must
        // resolve before a signed-in reader can be classified.
        setMeasurementActor('unknown');
        role = null;
        roleFor = null;
      }
      currentSession = newSession;
      authReady = true;
      loadRole(newSession?.user?.id ?? null);
      if (newSession?.expires_at !== previousExpiry) {
        invalidate('supabase:auth');
      }
      syncMeasurement(identityChanged || firstAuthResolution);
    });

    const onMeasurementStorage = (event: StorageEvent) => {
      if (event.key !== MEASUREMENT_CONSENT_KEY) return;
      consentedToMeasurement = event.newValue === 'granted';
      setMeasurementConsent(consentedToMeasurement);
      syncMeasurement(false);
    };
    window.addEventListener('storage', onMeasurementStorage);

    // Service worker, for offline caching. Fire and forget: a registration
    // failure is a console line, never a broken page.
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker
        .register('/sw.js')
        .catch((e) => console.error('Service worker registration failed:', e));
    }

    return () => {
      subscription.unsubscribe();
      window.removeEventListener('storage', onMeasurementStorage);
      teardownMeasurement();
    };
  });
</script>

<svelte:window on:keydown={onWindowKeydown} />

<svelte:head>
  <link rel="icon" href={favicon} />
  <link rel="canonical" href={canonical} />
  {#if localized}
    <link rel="alternate" hreflang="en" href={SITE_ORIGIN + path} />
    <link rel="alternate" hreflang="vi" href={SITE_ORIGIN + withLocale(path)} />
    <link rel="alternate" hreflang="x-default" href={SITE_ORIGIN + path} />
  {/if}
</svelte:head>

<slot />

<MeasurementConsent
  enabled={measurementAvailable}
  locale={$locale}
  on:choice={onMeasurementChoice}
/>

<CommandPalette {role} {signedIn} />
