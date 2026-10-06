import { expect, test } from '@playwright/test';
import { resolveMeasurementActor } from '../src/lib/features/shared/measurementLifecycle';

import { canonicalMeasurementPath, sanitizeMeasurementParams } from '../src/lib/core/measurement';
import {
  getMeasurementConsent,
  getMeasurementConsentChoice,
  initializeMeasurement,
  MEASUREMENT_CONSENT_KEY,
  setMeasurementActor,
  setMeasurementConsent,
  teardownMeasurement,
  trackMeasurement,
  trackMeasurementPage,
  type MeasurementAdapter,
} from '../src/lib/data/measurement';

class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
  removeItem(key: string): void {
    this.values.delete(key);
  }
}

class CaptureAdapter implements MeasurementAdapter {
  loads: Array<{ id: string; page: unknown }> = [];
  events: Array<{ event: string; params: Record<string, string | number | boolean> }> = [];
  teardowns = 0;
  cookieClears = 0;
  loadThrows = false;
  emitThrows = false;
  load(id: string, page: unknown): void {
    if (this.loadThrows) throw new Error('analytics unavailable');
    this.loads.push({ id, page });
  }
  emit(event: string, params: Record<string, string | number | boolean>): void {
    if (this.emitThrows) throw new Error('analytics unavailable');
    this.events.push({ event, params });
  }
  teardown(): void {
    this.teardowns += 1;
  }
  clearCookies(): void {
    this.cookieClears += 1;
  }
}

const setup = (
  overrides: {
    actor?: 'guest' | 'reader' | 'staff' | 'unknown';
    granted?: boolean;
    adapter?: CaptureAdapter;
    privacySignals?: { doNotTrack?: string | null; globalPrivacyControl?: boolean };
  } = {}
) => {
  const storage = new MemoryStorage();
  if (overrides.granted) storage.setItem(MEASUREMENT_CONSENT_KEY, 'granted');
  const adapter = overrides.adapter ?? new CaptureAdapter();
  initializeMeasurement({
    measurementId: 'G-ABC123',
    actor: overrides.actor ?? 'guest',
    hostname: 'maparchive.vn',
    adapter,
    storage,
    privacySignals: overrides.privacySignals,
  });
  return { storage, adapter };
};

test.afterEach(() => teardownMeasurement());

test('consent is off until explicitly granted and the choice can be shown to the user', () => {
  const { adapter, storage } = setup();
  trackMeasurementPage('/explore');
  expect(getMeasurementConsent()).toBe(false);
  expect(getMeasurementConsentChoice()).toBe('unknown');
  expect(adapter.loads).toHaveLength(0);

  setMeasurementConsent(true);
  expect(getMeasurementConsent()).toBe(true);
  expect(getMeasurementConsentChoice()).toBe('granted');
  expect(adapter.loads).toHaveLength(1);
  setMeasurementConsent(false);
  expect(storage.getItem(MEASUREMENT_CONSENT_KEY)).toBe('denied');
  expect(adapter.teardowns).toBe(1);
});

test('staff and unresolved actors never initialize or emit measurement', () => {
  const { adapter } = setup({ actor: 'unknown', granted: true });
  trackMeasurementPage('/explore');
  expect(adapter.loads).toHaveLength(0);
  expect(trackMeasurement('map_open')).toBe(false);
  setMeasurementActor('staff');
  expect(adapter.loads).toHaveLength(0);
  setMeasurementActor('reader');
  expect(adapter.loads).toHaveLength(1);
});

test('role changes pause measurement without clearing the consenting visitor identity', () => {
  const { adapter } = setup({ granted: true });
  trackMeasurementPage('/explore');
  expect(adapter.loads).toHaveLength(1);

  setMeasurementActor('unknown');
  expect(adapter.teardowns).toBe(1);
  expect(adapter.cookieClears).toBe(0);
  setMeasurementActor('reader');
  expect(adapter.loads).toHaveLength(2);
  expect(adapter.cookieClears).toBe(0);

  setMeasurementConsent(false);
  expect(adapter.cookieClears).toBe(1);
});

test('DNT and GPC suppress collection even after consent', () => {
  for (const privacySignals of [{ doNotTrack: '1' }, { globalPrivacyControl: true }]) {
    const { adapter } = setup({ granted: true, privacySignals });
    trackMeasurementPage('/explore');
    expect(adapter.loads).toHaveLength(0);
    expect(trackMeasurement('map_open')).toBe(false);
    teardownMeasurement();
  }
});

test('only bounded allowlisted values survive the parameter boundary', () => {
  const params = sanitizeMeasurementParams({
    surface: 'explore',
    action: 'open',
    result_count: 4,
    map_id: '123e4567-e89b-42d3-a456-426614174000',
    query: 'Rue Catinat',
    email: 'reader@example.com',
    coordinates: '10.77,106.69',
    url: 'https://maparchive.vn/?q=private',
    result_count_bad: 9,
    workflow: 'free form',
  });
  expect(params).toEqual({
    surface: 'explore',
    action: 'open',
    result_count: 4,
    map_id: '123e4567-e89b-42d3-a456-426614174000',
  });
  expect(sanitizeMeasurementParams({ map_id: 'NguyenVanA' })).toEqual({});
});

test('canonical page events use route templates and omit queries, hashes, and arbitrary routes', () => {
  expect(canonicalMeasurementPath('/catalog/secret-personal-slug?email=x#section')).toBe(
    '/catalog/:slug'
  );
  expect(canonicalMeasurementPath('/catalog/institutions')).toBe('/catalog/institutions');
  expect(canonicalMeasurementPath('/catalog/area/mekong-delta')).toBe('/catalog/area/:slug');
  expect(canonicalMeasurementPath('/admin/users/alice@example.com')).toBeNull();

  const { adapter } = setup({ granted: true });
  expect(trackMeasurementPage('/catalog/secret-personal-slug?email=x#section')).toBe(true);
  expect(trackMeasurementPage('/catalog/secret-personal-slug?other=y')).toBe(false);
  const page = adapter.loads[0].page as Record<string, string>;
  expect(page.page_path).toBe('/catalog/:slug');
  expect(page.page_location).toBe('https://maparchive.vn/catalog/:slug');
  expect(page.page_referrer).toBe('');
  expect(trackMeasurementPage('/admin/users/alice@example.com')).toBe(false);
  expect(trackMeasurement('map_open')).toBe(false);
});

test('events carry the safe page context and revocation stops further emission', () => {
  const { adapter } = setup({ granted: true });
  trackMeasurementPage('/explore?mode=browse');
  expect(
    trackMeasurement('map_open', {
      surface: 'explore',
      map_id: '123e4567-e89b-42d3-a456-426614174000',
    })
  ).toBe(true);
  const params = adapter.events[0].params;
  expect(params.page_location).toBe('https://maparchive.vn/explore?mode=browse');
  expect(params.actor).toBe('guest');
  expect(params.query).toBeUndefined();

  setMeasurementConsent(false);
  expect(trackMeasurement('map_open')).toBe(false);
  expect(adapter.events).toHaveLength(1);
});

test('routes visited before consent are remembered without emission and specific sheets remain distinct', () => {
  const { adapter } = setup();
  expect(trackMeasurementPage('/catalog/old-map-one')).toBe(false);
  expect(adapter.loads).toHaveLength(0);
  setMeasurementConsent(true);
  expect(adapter.loads).toHaveLength(1);
  expect((adapter.loads[0].page as { page_path: string }).page_path).toBe('/catalog/:slug');

  expect(trackMeasurementPage('/catalog/old-map-one?view=detail')).toBe(false);
  expect(trackMeasurementPage('/catalog/old-map-two')).toBe(true);
  expect(adapter.events.at(-1)?.params.page_path).toBe('/catalog/:slug');
  expect(trackMeasurementPage('/explore')).toBe(true);
  expect(adapter.events.at(-1)?.params.page_path).toBe('/explore?mode=browse');
});

test('a storage failure cannot revive tracking after consent withdrawal', () => {
  const adapter = new CaptureAdapter();
  const storage = new MemoryStorage();
  storage.setItem(MEASUREMENT_CONSENT_KEY, 'granted');
  initializeMeasurement({
    measurementId: 'G-ABC123',
    actor: 'guest',
    hostname: 'maparchive.vn',
    adapter,
    storage,
  });
  trackMeasurementPage('/explore');
  expect(adapter.loads).toHaveLength(1);
  storage.setItem = () => {
    throw new Error('storage blocked');
  };
  setMeasurementConsent(false);
  setMeasurementActor('reader');
  expect(getMeasurementConsent()).toBe(false);
  expect(adapter.loads).toHaveLength(1);
  expect(trackMeasurement('map_open')).toBe(false);
});

test('donation completion is reserved for trusted confirmation and adapter failures do not escape', () => {
  const adapter = new CaptureAdapter();
  adapter.emitThrows = true;
  setup({ granted: true, adapter });
  trackMeasurementPage('/contribute');
  expect(trackMeasurement('donation_completed')).toBe(false);
  expect(trackMeasurement('save_success', { surface: 'contribute' })).toBe(true);

  teardownMeasurement();
  const loadFailure = new CaptureAdapter();
  loadFailure.loadThrows = true;
  setup({ granted: true, adapter: loadFailure });
  expect(trackMeasurementPage('/explore')).toBe(false);
  expect(trackMeasurement('map_open')).toBe(false);
});

test('role classification fails closed during auth and distinguishes staff from readers', () => {
  expect(resolveMeasurementActor(false, false, null)).toBe('unknown');
  expect(resolveMeasurementActor(true, false, null)).toBe('guest');
  expect(resolveMeasurementActor(true, true, null)).toBe('unknown');
  expect(resolveMeasurementActor(true, true, 'unexpected-role')).toBe('unknown');
  expect(resolveMeasurementActor(true, true, 'admin')).toBe('staff');
  expect(resolveMeasurementActor(true, true, 'mod')).toBe('staff');
  expect(resolveMeasurementActor(true, true, 'user')).toBe('reader');
});

test('preview hosts and invalid property IDs cannot load the tracker even with consent', () => {
  for (const config of [
    { hostname: 'preview.vmabeta.pages.dev', measurementId: 'G-ABC123' },
    { hostname: 'localhost', measurementId: 'G-ABC123' },
    { hostname: 'maparchive.vn', measurementId: 'https://private.example/reader' },
    { hostname: 'maparchive.vn', measurementId: '' },
  ]) {
    const storage = new MemoryStorage();
    storage.setItem(MEASUREMENT_CONSENT_KEY, 'granted');
    const adapter = new CaptureAdapter();
    initializeMeasurement({ ...config, actor: 'guest', adapter, storage });
    trackMeasurementPage('/catalog');
    expect(adapter.loads).toHaveLength(0);
    expect(trackMeasurement('map_open')).toBe(false);
    teardownMeasurement();
  }
});
