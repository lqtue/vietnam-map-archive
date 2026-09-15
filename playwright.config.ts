import { defineConfig, devices } from '@playwright/test';

// ponytail: chromium only, no fixtures, no global setup. Add firefox/webkit
// projects when a browser-specific bug actually shows up.

// PURE_ONLY=1 drops the two specs that drive a browser against a live site, and
// with them the dev server they need. Everything else under tests/ is a pure
// check that only rides this runner because it is already installed, so the
// remainder needs no server, no network and no database. CI sets it: there the
// app is built against .env.test, whose Supabase URL is a loopback address with
// nothing behind it, and a browser check pointed at that is not a weaker test
// but a false one.
const pureOnly = process.env.PURE_ONLY === '1';

export default defineConfig({
  testDir: 'tests',
  // write.spec.ts has its own config: it needs a local Supabase and a seeded user.
  testIgnore: pureOnly
    ? ['write.spec.ts', 'smoke.spec.ts', 'catalog-series.spec.ts']
    : 'write.spec.ts',
  timeout: 30_000,
  fullyParallel: true,
  reporter: process.env.CI ? 'list' : [['list'], ['html', { open: 'never' }]],
  use: {
    // SMOKE_BASE_URL points the read-only suite at a deployed preview instead
    // of a local dev server (ROADMAP A1 click-through).
    baseURL: process.env.SMOKE_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer:
    pureOnly || process.env.SMOKE_BASE_URL
      ? undefined
      : {
          command: 'npm run dev',
          url: 'http://localhost:5173',
          reuseExistingServer: true,
          timeout: 120_000,
        },
});
