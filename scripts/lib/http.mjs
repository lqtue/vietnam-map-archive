/**
 * http.mjs — fetching from someone else's catalogue.
 *
 * Six copies of `sleep`, three different User-Agent strings (one of them a bare
 * `Mozilla/5.0` that identifies nobody), and four hand-rolled retry loops. The
 * UA matters more than it looks: these are small institutional servers, several
 * rate-limit, and one that decides to block us should be able to see who we are
 * and mail the address in the string rather than just start answering 429.
 */

/** Identifies us, and where to complain. Used unless a caller overrides it. */
export const UA = 'Mozilla/5.0 (compatible; vietnam-map-archive/1.0; +https://maparchive.vn)';

/** @param {number} ms */
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * GET JSON, with a timeout, a few retries, and a pause between calls.
 *
 * Retries only what can succeed on a second try — a timeout, a network error, a
 * 429 or a 5xx. A 404 is an answer; retrying it three times only makes the run
 * slower and the log harder to read.
 *
 * @param {string} url
 * @param {{ headers?: Record<string,string>, attempts?: number, timeoutMs?: number, throttleMs?: number }} [opts]
 * @returns {Promise<any>}
 */
export async function fetchJson(url, opts = {}) {
  const { headers = {}, attempts = 3, timeoutMs = 20_000, throttleMs = 0 } = opts;
  let last;
  for (let i = 1; i <= attempts; i++) {
    try {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), timeoutMs);
      try {
        const res = await fetch(url, {
          headers: { 'User-Agent': UA, Accept: 'application/json', ...headers },
          signal: ctl.signal,
        });
        if (res.ok) {
          const json = await res.json();
          if (throttleMs) await sleep(throttleMs);
          return json;
        }
        if (res.status < 500 && res.status !== 429) {
          throw new Error(`HTTP ${res.status} ${url}`);
        }
        last = new Error(`HTTP ${res.status} ${url}`);
      } finally {
        clearTimeout(timer);
      }
    } catch (e) {
      if (e instanceof Error && /^HTTP [34]\d\d/.test(e.message)) throw e;
      last = e;
    }
    if (i < attempts) await sleep(500 * 2 ** (i - 1));
  }
  throw last instanceof Error ? last : new Error(String(last));
}
