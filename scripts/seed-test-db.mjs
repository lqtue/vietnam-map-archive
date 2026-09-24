/**
 * Seed a NON-PRODUCTION Supabase with the fixtures the write-path smokes need
 * (tests/write.spec.ts): one staff user and one public map.
 *
 * Usage: node --env-file=.env.test scripts/seed-test-db.mjs
 *
 * Idempotent — re-running updates in place. Refuses to touch anything that
 * isn't a loopback URL unless VMA_ALLOW_REMOTE_SEED=1 is set, so a stray
 * `.env` can't point it at production.
 */
import { createClient } from '@supabase/supabase-js';
import { createHash } from 'node:crypto';

export const TEST_EMAIL = 'write-smoke@vma.test';
export const TEST_PASSWORD = 'write-smoke-password';
export const TEST_MAP_ALLMAPS_ID = 'f0f0f0f0f0f0f0f0';
// Fixed so tests/write.spec.ts can present it; only ever exists in a local stack.
export const TEST_WORKER_TOKEN = 'write-smoke-worker-token';

const url = process.env.PUBLIC_SUPABASE_URL;
const serviceKey = process.env.SUPABASE_SERVICE_KEY;

if (!url || !serviceKey) {
  throw new Error(
    'PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (use --env-file=.env.test)'
  );
}

const isLoopback = /^https?:\/\/(127\.0\.0\.1|localhost)(:|\/|$)/.test(url);
if (!isLoopback && process.env.VMA_ALLOW_REMOTE_SEED !== '1') {
  throw new Error(
    `Refusing to seed a non-loopback Supabase (${url}). Set VMA_ALLOW_REMOTE_SEED=1 if you really mean it.`
  );
}

const db = createClient(url, serviceKey, { auth: { persistSession: false } });

// 1. Staff user. createUser 422s when the address is taken, so fall back to a lookup.
let userId;
const created = await db.auth.admin.createUser({
  email: TEST_EMAIL,
  password: TEST_PASSWORD,
  email_confirm: true,
});
if (created.data?.user) {
  userId = created.data.user.id;
} else {
  const { data, error } = await db.auth.admin.listUsers({ perPage: 1000 });
  if (error) throw error;
  const existing = data.users.find((u) => u.email === TEST_EMAIL);
  if (!existing) throw created.error ?? new Error(`Could not create or find ${TEST_EMAIL}`);
  userId = existing.id;
  const { error: pwErr } = await db.auth.admin.updateUserById(userId, { password: TEST_PASSWORD });
  if (pwErr) throw pwErr;
}

// handle_new_user() inserts the profile row; we only raise the role.
const { error: roleErr } = await db.from('profiles').update({ role: 'admin' }).eq('id', userId);
if (roleErr) throw roleErr;

// 2. A public, georeferenced map to hang extractions and footprints off.
const { data: map, error: mapErr } = await db
  .from('maps')
  .upsert(
    {
      allmaps_id: TEST_MAP_ALLMAPS_ID,
      name: 'Write-smoke fixture map',
      status: 'public',
      is_georeferenced: true,
      year: 1900,
      iiif_image: 'https://example.invalid/iiif/write-smoke',
    },
    { onConflict: 'allmaps_id' }
  )
  .select('id')
  .single();
if (mapErr) throw mapErr;

// 3. A worker key, so the pipeline endpoints have something to authenticate.
const { error: keyErr } = await db.from('worker_keys').upsert(
  {
    name: 'write-smoke-worker',
    kinds: [],
    token_hash: createHash('sha256').update(TEST_WORKER_TOKEN).digest('hex'),
    revoked_at: null,
  },
  { onConflict: 'token_hash' }
);
if (keyErr) throw keyErr;

console.log(JSON.stringify({ url, userId, mapId: map.id, email: TEST_EMAIL }, null, 2));
