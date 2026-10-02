<script lang="ts">
  import { onMount } from 'svelte';
  import { invalidateAll } from '$app/navigation';
  import { getSupabaseContext } from '$lib/data/supabase/context';

  const { supabase } = getSupabaseContext();
  let verifiedFactors: { id: string; friendly_name?: string | null }[] = [];
  let level: string | null = null;
  let pendingFactorId = '';
  let qrCode = '';
  let secret = '';
  let code = '';
  let busy = false;
  let message = '';

  async function refresh() {
    const [factors, assurance] = await Promise.all([
      supabase.auth.mfa.listFactors(),
      supabase.auth.mfa.getAuthenticatorAssuranceLevel(),
    ]);
    if (factors.error || assurance.error) {
      message = factors.error?.message ?? assurance.error?.message ?? 'Could not load MFA status';
      return;
    }
    verifiedFactors = (factors.data.totp ?? []).filter((factor) => factor.status === 'verified');
    level = assurance.data.currentLevel;
  }

  onMount(() => {
    void refresh();
  });

  async function enroll() {
    busy = true;
    message = '';
    const { data, error } = await supabase.auth.mfa.enroll({
      factorType: 'totp',
      friendlyName: 'Vietnam Map Archive staff',
    });
    if (error || !data?.totp) {
      message = error?.message ?? 'Could not start authenticator setup';
    } else {
      pendingFactorId = data.id;
      // supabase-js already returns a `data:image/svg+xml` URI; wrapping it again made the browser
      // parse "data:image/…" as XML ("Start tag expected"). Older responses were bare SVG.
      const svg = data.totp.qr_code;
      qrCode = svg.startsWith('data:')
        ? svg
        : `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
      secret = data.totp.secret;
    }
    busy = false;
  }

  async function verify() {
    const factorId = pendingFactorId || verifiedFactors[0]?.id;
    if (!factorId || !/^\d{6}$/.test(code)) {
      message = 'Enter the six-digit code from your authenticator app.';
      return;
    }
    busy = true;
    message = '';
    const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId, code });
    if (error) {
      message = error.message;
    } else {
      pendingFactorId = '';
      qrCode = '';
      secret = '';
      code = '';
      await refresh();
      await invalidateAll();
      message = 'Authenticator verified. Staff tools are available for this session.';
    }
    busy = false;
  }
</script>

<section class="settings-section">
  <h3 class="section-title">Staff sign-in security</h3>
  {#if level === null}
    <p>Checking authenticator status…</p>
  {:else if level === 'aal2'}
    <p>Your authenticator is verified for this session.</p>
  {:else if verifiedFactors.length || pendingFactorId}
    {#if pendingFactorId}
      <p>Scan this code with an authenticator app, then enter its six-digit code.</p>
      <img class="mfa-qr" src={qrCode} alt="Authenticator setup QR code" />
      <p>Manual setup key: <code>{secret}</code></p>
    {:else}
      <p>Enter a code from your authenticator app to unlock staff tools.</p>
    {/if}
    <form on:submit|preventDefault={verify}>
      <label for="staff-mfa-code">Authenticator code</label>
      <input
        id="staff-mfa-code"
        type="text"
        inputmode="numeric"
        autocomplete="one-time-code"
        pattern={'[0-9]{6}'}
        maxlength="6"
        bind:value={code}
        required
      />
      <button class="btn" type="submit" disabled={busy}>Verify code</button>
    </form>
  {:else}
    <p>Staff tools require an authenticator app. Set one up to continue.</p>
    <button class="btn" type="button" on:click={enroll} disabled={busy}>Set up authenticator</button
    >
  {/if}
  {#if message}<p role="status">{message}</p>{/if}
</section>

<style>
  .mfa-qr {
    display: block;
    max-width: 220px;
    margin-block: 1rem;
  }
  form {
    display: grid;
    gap: 0.75rem;
    max-width: 22rem;
  }
  code {
    overflow-wrap: anywhere;
  }
</style>
