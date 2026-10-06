import {
  canonicalMeasurementPath,
  MEASUREMENT_EVENTS,
  sanitizeMeasurementMode,
  sanitizeMeasurementParams,
  type MeasurementActor,
  type MeasurementEvent,
} from '$lib/core/measurement';

export type { MeasurementActor, MeasurementEvent } from '$lib/core/measurement';

export const MEASUREMENT_CONSENT_KEY = 'vma-measurement-consent-v1';

export interface MeasurementAdapter {
  load(measurementId: string, initialPage: MeasurementPage): void;
  emit(event: string, params: Record<string, string | number | boolean>): void;
  teardown(): void;
  clearCookies?(measurementId: string): void;
}

export interface MeasurementPage {
  page_path: string;
  page_title: string;
  page_location: string;
  page_referrer: '';
}

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface MeasurementOptions {
  measurementId?: string | null;
  actor: MeasurementActor;
  hostname?: string;
  /** Test seam; the production adapter is used when omitted. */
  adapter?: MeasurementAdapter;
  /** Test seam for explicit consent and privacy-signal cases. */
  storage?: StorageLike;
  privacySignals?: { doNotTrack?: string | null; globalPrivacyControl?: boolean };
}

const CANONICAL_HOST = 'maparchive.vn';
const ROUTE_TITLES: Record<string, string> = {
  '/': 'Vietnam Map Archive',
  '/explore': 'Explore maps',
  '/catalog': 'Map catalogue',
  '/catalog/:slug': 'Historical map',
  '/catalog/series': 'Map series',
  '/catalog/place/:slug': 'Place maps',
  '/directory': 'Directory',
  '/about': 'About Vietnam Map Archive',
  '/contribute': 'Contribute',
  '/support': 'Support Vietnam Map Archive',
  '/walk': 'Walk',
  '/stories': 'Map stories',
  '/blog/:slug': 'Vietnam Map Archive article',
};

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
    [key: `ga-disable-${string}`]: boolean | undefined;
  }
}

let measurementId: string | null = null;
let actor: MeasurementActor = 'unknown';
let hostname = '';
let adapter: MeasurementAdapter | null = null;
let storageOverride: StorageLike | undefined;
let privacyOverride: MeasurementOptions['privacySignals'];
let sessionDenial = false;
let running = false;
let lastPageKey: string | null = null;
let lastRouteIdentity: string | null = null;
let currentPage: MeasurementPage | null = null;

function browserStorage(): StorageLike | undefined {
  if (storageOverride) return storageOverride;
  try {
    return typeof localStorage === 'undefined' ? undefined : localStorage;
  } catch {
    return undefined;
  }
}

function hasPrivacyOptOut(): boolean {
  try {
    const signals =
      privacyOverride ??
      (typeof navigator === 'undefined'
        ? {}
        : (navigator as Navigator & { globalPrivacyControl?: boolean }));
    return (
      signals.doNotTrack === '1' ||
      ('globalPrivacyControl' in signals && signals.globalPrivacyControl === true)
    );
  } catch {
    return true;
  }
}

export function getMeasurementConsent(): boolean {
  if (sessionDenial) return false;
  try {
    return browserStorage()?.getItem(MEASUREMENT_CONSENT_KEY) === 'granted';
  } catch {
    return false;
  }
}

export function getMeasurementConsentChoice(): 'unknown' | 'granted' | 'denied' {
  if (sessionDenial) return 'denied';
  try {
    const value = browserStorage()?.getItem(MEASUREMENT_CONSENT_KEY);
    return value === 'granted' || value === 'denied' ? value : 'unknown';
  } catch {
    return 'unknown';
  }
}

export function setMeasurementConsent(consented: boolean): void {
  const storage = browserStorage();
  let stored = false;
  try {
    if (storage) {
      storage.setItem(MEASUREMENT_CONSENT_KEY, consented ? 'granted' : 'denied');
      stored = true;
    }
  } catch {
    // A storage failure keeps new grants off; denials remain authoritative in memory.
  }
  if (!consented) {
    sessionDenial = true;
    stopAdapter();
    if (measurementId) {
      try {
        (adapter ?? gtagAdapter()).clearCookies?.(measurementId);
      } catch {
        /* Consent withdrawal remains effective even if cookie cleanup fails. */
      }
    }
    return;
  }
  sessionDenial = false;
  if (!stored) return;
  reconcileAdapter();
}

function routeTitle(pagePath: string): string {
  return ROUTE_TITLES[pagePath] ?? 'Vietnam Map Archive';
}

function makePage(pathname: string, mode?: string): MeasurementPage | null {
  const pagePath = canonicalMeasurementPath(pathname);
  if (!pagePath) return null;
  const cleanMode = ['/explore', '/scan'].includes(pagePath)
    ? sanitizeMeasurementMode(mode)
    : undefined;
  const normalizedMode = pagePath === '/explore' && !cleanMode ? 'browse' : cleanMode;
  const query = normalizedMode ? `?mode=${normalizedMode}` : '';
  return {
    page_path: `${pagePath}${query}`,
    page_title: routeTitle(pagePath),
    page_location: `https://${CANONICAL_HOST}${pagePath}${query}`,
    page_referrer: '',
  };
}

function gtagAdapter(): MeasurementAdapter {
  let activeId: string | null = null;
  return {
    load(id, page) {
      if (typeof document === 'undefined' || typeof window === 'undefined') return;
      activeId = id;
      window[`ga-disable-${id}`] = false;
      const script = document.createElement('script');
      script.async = true;
      script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
      script.dataset.vmaMeasurement = 'true';
      document.head.appendChild(script);
      window.dataLayer = window.dataLayer ?? [];
      window.gtag = function () {
        // Use the Google tag command format (Arguments), matching its loader.
        // eslint-disable-next-line prefer-rest-params
        window.dataLayer?.push(arguments);
      };
      window.gtag('js', new Date());
      window.gtag('config', id, {
        send_page_view: false,
        allow_google_signals: false,
        allow_ad_personalization_signals: false,
        page_location: page?.page_location ?? `https://${CANONICAL_HOST}/`,
        page_referrer: '',
        page_title: page?.page_title ?? ROUTE_TITLES['/'],
        send_to: id,
      });
      if (page) window.gtag('event', 'page_view', { ...page, send_to: id });
    },
    emit(event, params) {
      try {
        if (typeof window !== 'undefined' && typeof window.gtag === 'function') {
          window.gtag('event', event, { ...params, send_to: activeId });
        }
      } catch {
        // Analytics is best effort and never blocks a product action.
      }
    },
    teardown() {
      const id = activeId;
      activeId = null;
      if (typeof document !== 'undefined') {
        document
          .querySelectorAll('script[data-vma-measurement="true"]')
          .forEach((script) => script.remove());
      }
      if (typeof window !== 'undefined') {
        if (id) window[`ga-disable-${id}`] = true;
        window.gtag = undefined;
        window.dataLayer = [];
      }
    },
    clearCookies(id) {
      if (typeof document === 'undefined') return;
      const propertyCookie = `_ga_${id.replace(/^G-/, '').replace(/[^A-Z0-9]/gi, '')}`;
      for (const cookie of ['_ga', propertyCookie]) {
        for (const domain of ['', '; domain=maparchive.vn', '; domain=.maparchive.vn']) {
          document.cookie = `${cookie}=; Max-Age=0; path=/; SameSite=Lax; Secure${domain}`;
        }
      }
    },
  };
}

function measurementEnabled(): boolean {
  const hostAllowed = hostname === CANONICAL_HOST;
  return (
    !!measurementId &&
    hostAllowed &&
    actor !== 'unknown' &&
    actor !== 'staff' &&
    getMeasurementConsent() &&
    !hasPrivacyOptOut()
  );
}

function canRun(): boolean {
  return measurementEnabled() && !!currentPage;
}

function stopAdapter(): void {
  if (running) {
    try {
      adapter?.teardown();
    } catch {
      /* best effort */
    }
  }
  running = false;
  lastPageKey = null;
}

function reconcileAdapter(): void {
  if (!measurementEnabled()) {
    stopAdapter();
    return;
  }
  if (running) return;
  if (!currentPage) return;
  adapter ??= gtagAdapter();
  try {
    const page = currentPage;
    if (!page) return;
    adapter.load(measurementId!, page);
    running = true;
    lastPageKey = `${page.page_path}|${page.page_title}`;
  } catch {
    try {
      adapter.teardown();
    } catch {
      /* best effort */
    }
    running = false;
    return;
  }
}

export function initializeMeasurement(options: MeasurementOptions): void {
  stopAdapter();
  measurementId = options.measurementId?.trim() || null;
  if (measurementId && !/^G-[A-Z0-9]+$/i.test(measurementId)) measurementId = null;
  actor = options.actor;
  hostname = options.hostname ?? (typeof location === 'undefined' ? '' : location.hostname);
  adapter = options.adapter ?? null;
  storageOverride = options.storage;
  privacyOverride = options.privacySignals;
  sessionDenial = false;
  currentPage = null;
  lastPageKey = null;
  lastRouteIdentity = null;
  reconcileAdapter();
}

export function setMeasurementActor(nextActor: MeasurementActor): void {
  actor = nextActor;
  reconcileAdapter();
}

export function trackMeasurement(
  event: MeasurementEvent | 'donation_completed',
  params?: Record<string, unknown>
): boolean {
  if (
    event === 'donation_completed' ||
    !running ||
    !canRun() ||
    !MEASUREMENT_EVENTS.includes(event as MeasurementEvent)
  )
    return false;
  const clean = sanitizeMeasurementParams(params);
  clean.actor = actor;
  Object.assign(clean, currentPage);
  try {
    adapter?.emit(event, clean);
  } catch {
    /* best effort; tracking must not block saves */
  }
  return true;
}

export function trackMeasurementPage(pathname: string, mode?: string): boolean {
  const page = makePage(pathname, mode);
  if (!page) {
    currentPage = null;
    lastPageKey = null;
    lastRouteIdentity = null;
    stopAdapter();
    return false;
  }
  const routeOnly = pathname.split(/[?#]/, 1)[0];
  const routeIdentity = `${routeOnly}|${page.page_path}`;
  currentPage = page;
  const sameRoute = routeIdentity === lastRouteIdentity;
  lastRouteIdentity = routeIdentity;
  if (!canRun()) return false;
  const key = `${page.page_path}|${page.page_title}`;
  if (sameRoute && key === lastPageKey) return false;
  if (!running) {
    reconcileAdapter();
    return running;
  }
  try {
    adapter?.emit('page_view', { ...page });
  } catch {
    /* best effort */
  }
  lastPageKey = key;
  return true;
}

export function teardownMeasurement(): void {
  stopAdapter();
  measurementId = null;
  actor = 'unknown';
  hostname = '';
  adapter = null;
  storageOverride = undefined;
  privacyOverride = undefined;
  sessionDenial = false;
  currentPage = null;
  lastRouteIdentity = null;
}
