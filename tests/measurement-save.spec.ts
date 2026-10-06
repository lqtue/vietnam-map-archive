import { expect, test } from '@playwright/test';
import { createClient } from '@supabase/supabase-js';
import { updateAnnotationSet } from '../src/lib/data/supabase/annotations';
import type { Database } from '../src/lib/data/supabase/types';

const layerId = '123e4567-e89b-42d3-a456-426614174000';

function clientForResponse(body: unknown, status = 200) {
  return createClient<Database>('https://fixture.example', 'fixture-key', {
    auth: { persistSession: false, autoRefreshToken: false },
    global: {
      fetch: async (input, init) => {
        const url = new URL(String(input));
        expect(url.searchParams.get('select')).toBe('id');
        expect(url.searchParams.get('id')).toBe(`eq.${layerId}`);
        expect(init?.method).toBe('PATCH');
        return new Response(JSON.stringify(body), {
          status,
          headers: { 'content-type': 'application/json' },
        });
      },
    },
  });
}

test('a successful persisted Studio update needs an acknowledged row', async () => {
  const features = {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [106, 10] }, properties: {} },
    ],
  };
  expect(
    await updateAnnotationSet(clientForResponse([{ id: layerId }]), layerId, { features })
  ).toBe(true);
  // PostgREST can return success with zero rows for RLS-hidden or nonexistent IDs.
  expect(await updateAnnotationSet(clientForResponse([]), layerId, { features })).toBe(false);
});
