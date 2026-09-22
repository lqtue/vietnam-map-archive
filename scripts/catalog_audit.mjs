/**
 * catalog_audit.mjs — are the rows in `maps` consistent with themselves?
 *
 *     node --env-file=.env scripts/catalog_audit.mjs
 *     node --env-file=.env scripts/catalog_audit.mjs --quiet   (findings only)
 *     node scripts/catalog_audit.mjs --self-check              (no db, no network)
 *
 * Read-only. Exits 1 on any FAIL, so it can gate a deploy.
 *
 * Three checkers divide the archive between them and none of them should grow
 * into another:
 *
 *   geo_audit.mjs           is the paper where the annotation says it is?
 *   check_series_index.mjs  does `series_sheets` still agree with `maps`?
 *   this                    is a row consistent with the rest of its own table?
 *
 * Everything here is answerable from the tables alone — no fetch, no geometry.
 * That is the point: it runs in a second, so it can run after every ingest,
 * and the first audit it was written for (2026-09-15, 274 maps) found four
 * things no existing check looked at.
 *
 * What this deliberately does NOT report: a map carrying `allmaps_id` with
 * `georef_done` false. It reads like a fault — the id is a SHA-1 of the
 * canonical IIIF URL, minted locally by `bulk_upload_local.sh` whether or not a
 * control point exists — and this file called it one, over 21 L7014 drafts,
 * until the code that consumes it turned up.
 *
 * It is a work queue. `POST /api/admin/maps/sync-georef` selects exactly that
 * pair, probes annotations.allmaps.org and flips `georef_done` on a hit; the
 * admin "Sync georef from Allmaps" button is its trigger. The id is how the
 * archive remembers that a sheet is uploaded and waiting for someone to place
 * control points. Clearing it, or not writing it at upload, would empty that
 * queue — a volunteer's georeference would arrive and nothing would notice.
 * Publishing on the strength of it is deliberate too: mig 080 exists precisely
 * because georeferencing usually happens *after* publishing.
 *
 * So the count is printed as status, not as a finding. Whether those
 * annotations actually resolve is a network question, and that is
 * `geo_audit.mjs` — which already reports each one as `annotation HTTP 404`.
 *
 * ponytail: joins in JS over one paged read per table. Same trade as
 * check_series_index, same threshold — write the view when a survey makes this
 * slow, and delete this.
 */
import { createClient } from '@supabase/supabase-js';

/** Generous box around Vietnam, shared with geo_audit for the same reason. */
const VIETNAM = [100, 5, 112, 25];
/** mig 027 + 041. A value outside this reached the column without a migration. */
const SOURCE_TYPES = ['ia', 'bnf', 'efeo', 'gallica', 'rumsey', 'self', 'other', 'r2'];
/** `claim_job` reclaims at 3 h (mig 077), so past that a job is stuck, not slow. */
const STUCK_HOURS = 3;
/**
 * Above this, a shared `source_url` is a series landing page, not a duplicate.
 * Sixty Indochine sheets share one Cartomundi URL and that is correct; the one
 * real duplicate in the archive was a pair. Anything in between wants a person.
 */
const SERIES_URL_MIN = 4;

const published = (m) => m.status === 'public' || m.status === 'featured';

/** True if `year` is named in `label`, either literally or as inside a "YYYY-YYYY" range. */
function yearInLabel(year, label) {
  const range = String(label).match(/^(\d{4})-(\d{4})$/);
  if (range) return year >= Number(range[1]) && year <= Number(range[2]);
  return String(label).includes(String(year));
}

/** Word-order and punctuation-insensitive fold, for spotting one name typed twice. */
const foldName = (s) =>
  String(s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .split(' ')
    .sort()
    .join(' ');

const push = (map, key, value) => {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
};

/**
 * The whole audit, over plain arrays so it can be exercised without a database.
 *
 * @param {{maps: any[], aliases: any[], sources: any[], jobs: any[], now?: number}} input
 * @returns {{level: 'FAIL'|'WARN', check: string, subject: string, detail: string}[]}
 */
export function auditCatalog({ maps, aliases = [], sources = [], jobs = [], now = Date.now() }) {
  const out = [];
  const say = (level, check, subject, detail) => out.push({ level, check, subject, detail });
  const who = (m) => `${m.slug || '(no slug)'} [${m.status}]`;
  const ids = new Set(maps.map((m) => m.id));

  // ── the publish gate, and what it does not prove ──────────────────────────
  for (const m of maps) {
    if (!['draft', 'public', 'featured'].includes(m.status))
      say('FAIL', 'status', who(m), `status '${m.status}' is outside draft/public/featured`);

    if (!published(m)) continue;
    if (!m.annotation_url && !m.allmaps_id)
      say(
        'FAIL',
        'publish',
        who(m),
        'published with neither annotation_url nor allmaps_id (mig 062)'
      );
    if (!m.iiif_image)
      say('FAIL', 'publish', who(m), 'published with no iiif_image — nothing to draw');
    if (!m.bbox)
      say('WARN', 'publish', who(m), 'published with no bbox — invisible to extent queries');
    if (!m.thumbnail) say('WARN', 'publish', who(m), 'published with no thumbnail');
    // Legitimate but worth seeing: the map is live and draws nothing until the
    // georeference lands (mig 080's publish-then-georeference path).
    if (!m.georef_done)
      say('WARN', 'publish', who(m), 'published but not yet georeferenced — it draws nothing yet');
    if (!m.year && !m.year_label)
      say('WARN', 'publish', who(m), 'published with no year and no year_label');
    if (!m.holding_institution) say('WARN', 'provenance', who(m), 'no holding_institution');
    if (!m.source_url)
      say('WARN', 'provenance', who(m), 'no source_url — nothing links back to the holder');
  }

  // ── slugs: a sheet's address (mig 088) ────────────────────────────────────
  const bySlug = new Map();
  for (const m of maps) {
    if (!m.slug) say('FAIL', 'slug', m.id, 'empty slug — the trigger did not mint one');
    else push(bySlug, m.slug, m);
  }
  for (const [slug, ms] of bySlug)
    if (ms.length > 1)
      say('FAIL', 'slug', slug, `${ms.length} maps share it: ${ms.map((m) => m.id).join(', ')}`);
  for (const a of aliases) {
    if (bySlug.has(a.slug)) say('FAIL', 'slug', a.slug, 'is both a canonical slug and an alias');
    if (!ids.has(a.map_id)) say('FAIL', 'slug', a.slug, `alias points at missing map ${a.map_id}`);
  }

  // ── bbox: shape only ──────────────────────────────────────────────────────
  // Deliberately no size heuristic. A sheet-sized box and a regional one differ
  // by three orders of magnitude and both are correct; every threshold tried
  // flagged the three `map_type: regional` sheets and nothing else. Whether a
  // bbox is *right* is geo_audit's question, and it is answered exactly by
  // `backfill_map_bbox.mjs --dry --force` reporting "0 differ".
  for (const m of maps) {
    const b = m.bbox;
    if (b === null || b === undefined) continue;
    if (!Array.isArray(b) || b.length !== 4 || b.some((v) => !Number.isFinite(v))) {
      say('FAIL', 'bbox', who(m), `malformed: ${JSON.stringify(b)}`);
      continue;
    }
    const [w, s, e, n] = b;
    if (w >= e || s >= n) {
      say('FAIL', 'bbox', who(m), `inverted or zero-area: [${b}]`);
      continue;
    }
    if (w < VIETNAM[0] || s < VIETNAM[1] || e > VIETNAM[2] || n > VIETNAM[3])
      say('FAIL', 'bbox', who(m), `outside Vietnam: [${b.map((v) => +v.toFixed(3))}]`);
  }

  // ── the same sheet, filed twice ───────────────────────────────────────────
  const byImage = new Map();
  const byUrl = new Map();
  for (const m of maps) {
    if (m.iiif_image) push(byImage, m.iiif_image, m);
    if (m.source_url) push(byUrl, m.source_url, m);
  }
  for (const [img, ms] of byImage)
    if (ms.length > 1)
      say(
        'FAIL',
        'duplicate',
        ms.map((m) => m.slug).join(' + '),
        `one iiif_image serves ${ms.length} maps: ${img}`
      );
  for (const [url, ms] of byUrl)
    if (ms.length > 1 && ms.length < SERIES_URL_MIN)
      say(
        'WARN',
        'duplicate',
        ms.map((m) => m.slug).join(' + '),
        `${ms.length} maps share one source_url: ${url}`
      );

  // ── metadata that contradicts itself ──────────────────────────────────────
  const byInstitution = new Map();
  for (const m of maps) {
    if (m.source_type && !SOURCE_TYPES.includes(m.source_type))
      say('FAIL', 'metadata', who(m), `source_type '${m.source_type}' is outside mig 027/041`);
    if (m.year != null && (m.year < 1500 || m.year > new Date(now).getUTCFullYear()))
      say('FAIL', 'metadata', who(m), `year ${m.year} is not a year this archive can hold`);
    // A label is free text and may be a range or a printing date, but if it
    // names no year in common with the column, one of the two is wrong. A
    // "YYYY-YYYY" range is checked numerically — a year in the middle of one
    // (1880 in "1876-1883") is not a substring of the label, but is still in it.
    if (m.year != null && m.year_label && !yearInLabel(m.year, m.year_label))
      say(
        'WARN',
        'metadata',
        who(m),
        `year ${m.year} appears nowhere in year_label '${m.year_label}'`
      );
    if (m.holding_institution) {
      const k = foldName(m.holding_institution);
      if (!byInstitution.has(k)) byInstitution.set(k, new Set());
      byInstitution.get(k).add(m.holding_institution);
    }
  }
  // One holder typed two ways splits the facet in two and neither half is wrong
  // enough to notice from inside a page.
  for (const spellings of byInstitution.values())
    if (spellings.size > 1)
      say(
        'WARN',
        'metadata',
        'holding_institution',
        `one holder, ${spellings.size} spellings: ${[...spellings].map((s) => JSON.stringify(s)).join(' vs ')}`
      );

  // ── IIIF sources: the trigger's invariants, checked from outside ──────────
  const srcByMap = new Map();
  for (const s of sources) {
    if (!ids.has(s.map_id))
      say('FAIL', 'iiif', s.id, `map_iiif_sources row points at missing map ${s.map_id}`);
    else push(srcByMap, s.map_id, s);
  }
  for (const m of maps) {
    const ss = srcByMap.get(m.id) ?? [];
    const primary = ss.filter((s) => s.is_primary);
    if (primary.length > 1)
      say(
        'FAIL',
        'iiif',
        who(m),
        `${primary.length} primary sources — the partial unique index should forbid this`
      );
    if (ss.length && !primary.length)
      say('FAIL', 'iiif', who(m), `${ss.length} IIIF sources, none primary`);
    if (
      primary.length === 1 &&
      m.iiif_image &&
      primary[0].iiif_image &&
      primary[0].iiif_image !== m.iiif_image
    )
      say(
        'FAIL',
        'iiif',
        who(m),
        'maps.iiif_image disagrees with its own primary source row — the sync trigger did not fire'
      );
    // Not a fault, but it is why the "Fix georeference in Allmaps" button is
    // missing on a page: the editor needs a non-r2 source and there is none.
    if (
      published(m) &&
      m.iiif_image &&
      !m.iiif_manifest &&
      !ss.some((s) => s.source_type !== 'r2' && s.iiif_image)
    )
      say(
        'WARN',
        'iiif',
        who(m),
        'no original (non-r2) IIIF source, so the Allmaps Editor cannot be opened on it'
      );
  }

  // ── the queue ─────────────────────────────────────────────────────────────
  // A failed job is only worth a line while its failure still stands. All four
  // layout jobs that died on 2026-09-13 were re-queued within the hour and
  // finished; the `failed` rows stay as history, and reporting them forever
  // trains the reader to scroll past the section. So a failure is spent once a
  // later job of the same kind on the same map reached `done`.
  const succeededAfter = new Map();
  for (const j of jobs) {
    if (j.status !== 'done') continue;
    const at = Date.parse(j.finished_at ?? j.updated_at ?? j.created_at);
    const k = `${j.kind}|${j.map_id}`;
    if (!(succeededAfter.get(k) >= at)) succeededAfter.set(k, at);
  }
  const supersededBy = (j) =>
    succeededAfter.get(`${j.kind}|${j.map_id}`) >
    Date.parse(j.finished_at ?? j.updated_at ?? j.created_at);

  for (const j of jobs) {
    if (j.map_id && !ids.has(j.map_id))
      say('FAIL', 'jobs', j.id, `job points at missing map ${j.map_id}`);
    const hours = (now - Date.parse(j.updated_at ?? j.created_at)) / 3.6e6;
    if ((j.status === 'claimed' || j.status === 'running') && hours > STUCK_HOURS)
      say(
        'WARN',
        'jobs',
        `${j.kind} ${j.map_id}`,
        `held in '${j.status}' for ${hours.toFixed(1)} h`
      );
    if (j.status === 'failed' && j.attempts >= j.max_attempts && !supersededBy(j))
      say(
        'WARN',
        'jobs',
        `${j.kind} ${j.map_id}`,
        `failed with no retries left (${j.attempts}/${j.max_attempts})`
      );
  }

  const rank = { FAIL: 0, WARN: 1 };
  return out.sort((a, b) => rank[a.level] - rank[b.level] || a.check.localeCompare(b.check));
}

/**
 * Proof that each check can reject something.
 *
 * A checker that only ever runs against a healthy archive reports the same
 * thing whether it works or not — that is how `check_series_index` reported
 * clean over 79 sheets it could not see. So every rule below is handed input it
 * must refuse, and the healthy row that must pass beside it.
 *
 *     node scripts/catalog_audit.mjs --self-check
 */
function selfCheck() {
  let failed = 0;
  const ok = (cond, what) => {
    console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${what}`);
    if (!cond) failed++;
  };
  const NOW = Date.parse('2026-09-15T00:00:00Z');
  const good = {
    id: 'a',
    slug: 'saigon',
    name: 'Saigon',
    status: 'public',
    year: 1920,
    bbox: [106.6, 10.7, 106.8, 10.9],
    iiif_image: 'https://iiif/a',
    annotation_url: 'https://anno/a',
    allmaps_id: null,
    georef_done: true,
    thumbnail: 'https://t/a',
    source_type: 'r2',
    holding_institution: 'BnF',
    source_url: 'https://bnf/a',
    year_label: '1920',
    iiif_manifest: 'https://m/a',
  };
  const run = (over, extra = {}) =>
    auditCatalog({ maps: [{ ...good, ...over }], now: NOW, ...extra });
  const has = (findings, check, level) =>
    findings.some((f) => f.check === check && f.level === level);

  ok(run({}).length === 0, 'a healthy published map produces nothing');

  // The queue, which must stay silent. A draft with a minted allmaps_id and
  // georef_done false is a sheet waiting for control points, not a fault --
  // /api/admin/maps/sync-georef selects exactly that pair and flips it on a hit.
  ok(
    run({
      status: 'draft',
      annotation_url: null,
      allmaps_id: '9c3624b9f48a27e0',
      georef_done: false,
    }).length === 0,
    'a draft queued for georeferencing produces nothing'
  );
  ok(
    !has(
      run({ annotation_url: null, allmaps_id: '9c3624b9f48a27e0', georef_done: true }),
      'publish',
      'WARN'
    ),
    'a published map on an allmaps_id backed by georef_done produces nothing'
  );
  // mig 080's path: published first, georeferenced later. Allowed, but the map
  // draws nothing meanwhile, so it is worth one line.
  ok(
    has(
      run({ annotation_url: null, allmaps_id: '9c3624b9f48a27e0', georef_done: false }),
      'publish',
      'WARN'
    ),
    'a published map not yet georeferenced is flagged, not failed'
  );

  ok(has(run({ status: 'archived' }), 'status', 'FAIL'), 'a status outside the three is rejected');
  ok(
    has(run({ iiif_image: null }), 'publish', 'FAIL'),
    'a published map with no image is rejected'
  );

  // bbox: shape, not size.
  ok(
    has(run({ bbox: [106.8, 10.7, 106.6, 10.9] }), 'bbox', 'FAIL'),
    'an east-of-west bbox is rejected'
  );
  ok(
    has(run({ bbox: [-0.2, 5.5, 0.2, 5.9] }), 'bbox', 'FAIL'),
    'a lon/lat swap landing off West Africa is rejected'
  );
  ok(has(run({ bbox: [106.6, 10.7, 106.8] }), 'bbox', 'FAIL'), 'a three-element bbox is rejected');
  ok(
    !has(run({ bbox: [103.9, 7.4, 109.4, 13.2] }), 'bbox', 'FAIL'),
    'a regional sheet spanning 800 km is accepted'
  );

  // Duplicates, and the series page that must not read as one.
  const twin = (n, over) => ({ ...good, id: `d${n}`, slug: `d${n}`, ...over });
  ok(
    has(
      auditCatalog({ maps: [twin(1, {}), twin(2, { iiif_image: 'https://iiif/a' })], now: NOW }),
      'duplicate',
      'FAIL'
    ),
    'two maps sharing one iiif_image are rejected'
  );
  ok(
    has(
      auditCatalog({
        maps: [
          twin(1, { iiif_image: 'https://iiif/1' }),
          twin(2, { iiif_image: 'https://iiif/2' }),
        ],
        now: NOW,
      }),
      'duplicate',
      'WARN'
    ),
    'two maps sharing one source_url are flagged'
  );
  ok(
    !has(
      auditCatalog({
        maps: Array.from({ length: 6 }, (_, i) => twin(i, { iiif_image: `https://iiif/${i}` })),
        now: NOW,
      }),
      'duplicate',
      'WARN'
    ),
    `${SERIES_URL_MIN}+ maps on one source_url read as a series page, not a duplicate`
  );

  // Slugs.
  ok(
    has(
      auditCatalog({ maps: [twin(1, { slug: 'same' }), twin(2, { slug: 'same' })], now: NOW }),
      'slug',
      'FAIL'
    ),
    'two maps on one slug are rejected'
  );
  ok(
    has(
      auditCatalog({ maps: [good], aliases: [{ slug: 'saigon', map_id: 'a' }], now: NOW }),
      'slug',
      'FAIL'
    ),
    'a slug that is both canonical and an alias is rejected'
  );
  ok(
    has(
      auditCatalog({ maps: [good], aliases: [{ slug: 'old', map_id: 'gone' }], now: NOW }),
      'slug',
      'FAIL'
    ),
    'an alias pointing at a deleted map is rejected'
  );

  // Metadata.
  ok(
    has(run({ source_type: 'flickr' }), 'metadata', 'FAIL'),
    'a source_type no migration allows is rejected'
  );
  ok(
    has(run({ year: 1819, year_label: '1931' }), 'metadata', 'WARN'),
    'a year its label never mentions is flagged'
  );
  ok(
    !has(run({ year: 1880, year_label: '1876-1883' }), 'metadata', 'WARN'),
    'a year inside a range label is accepted'
  );
  ok(
    has(run({ year: 1885, year_label: '1876-1883' }), 'metadata', 'WARN'),
    'a year outside a range label is still flagged'
  );
  ok(
    has(
      auditCatalog({
        maps: [
          twin(1, { holding_institution: 'Perry-Castañeda Library, University of Texas' }),
          twin(2, { holding_institution: 'University of Texas, Perry-Castañeda Library' }),
        ],
        now: NOW,
      }),
      'metadata',
      'WARN'
    ),
    'one holder spelled two ways is flagged'
  );

  // IIIF sources.
  ok(
    has(
      auditCatalog({
        maps: [good],
        sources: [
          { id: 's1', map_id: 'a', is_primary: true, iiif_image: 'https://iiif/a' },
          { id: 's2', map_id: 'a', is_primary: true, iiif_image: 'https://iiif/b' },
        ],
        now: NOW,
      }),
      'iiif',
      'FAIL'
    ),
    'two primary IIIF sources are rejected'
  );
  ok(
    has(
      auditCatalog({
        maps: [good],
        sources: [{ id: 's1', map_id: 'a', is_primary: true, iiif_image: 'https://iiif/OTHER' }],
        now: NOW,
      }),
      'iiif',
      'FAIL'
    ),
    'a primary source disagreeing with maps.iiif_image is rejected'
  );
  ok(
    has(
      auditCatalog({
        maps: [good],
        sources: [{ id: 's1', map_id: 'gone', is_primary: true }],
        now: NOW,
      }),
      'iiif',
      'FAIL'
    ),
    'a source row pointing at a deleted map is rejected'
  );
  ok(
    has(run({ iiif_manifest: null }, { sources: [] }), 'iiif', 'WARN'),
    'a published map the Allmaps Editor cannot open is flagged'
  );

  // The queue.
  const job = (over) => ({
    id: 'j',
    map_id: 'a',
    kind: 'layout',
    status: 'done',
    attempts: 1,
    max_attempts: 3,
    created_at: '2026-09-14T00:00:00Z',
    updated_at: '2026-09-14T00:00:00Z',
    ...over,
  });
  ok(
    has(
      auditCatalog({ maps: [good], jobs: [job({ status: 'failed', attempts: 3 })], now: NOW }),
      'jobs',
      'WARN'
    ),
    'a job out of retries is flagged'
  );

  // A failure that a later run of the same kind already put right is history,
  // not a finding. All four layout jobs that died on 2026-09-13 look like this.
  ok(
    !has(
      auditCatalog({
        maps: [good],
        jobs: [
          job({ id: 'j1', status: 'failed', attempts: 3, finished_at: '2026-09-14T10:00:00Z' }),
          job({ id: 'j2', status: 'done', finished_at: '2026-09-14T12:00:00Z' }),
        ],
        now: NOW,
      }),
      'jobs',
      'WARN'
    ),
    'a failure a later run put right is not flagged'
  );
  ok(
    has(
      auditCatalog({
        maps: [good],
        jobs: [
          job({ id: 'j1', status: 'done', finished_at: '2026-09-14T10:00:00Z' }),
          job({ id: 'j2', status: 'failed', attempts: 3, finished_at: '2026-09-14T12:00:00Z' }),
        ],
        now: NOW,
      }),
      'jobs',
      'WARN'
    ),
    'a failure AFTER the last success still stands'
  );
  ok(
    has(
      auditCatalog({
        maps: [good],
        jobs: [
          job({ id: 'j1', status: 'failed', attempts: 3, finished_at: '2026-09-14T10:00:00Z' }),
          job({ id: 'j2', kind: 'ocr', status: 'done', finished_at: '2026-09-14T12:00:00Z' }),
        ],
        now: NOW,
      }),
      'jobs',
      'WARN'
    ),
    'a success of a DIFFERENT kind does not clear it'
  );
  ok(
    has(
      auditCatalog({ maps: [good], jobs: [job({ status: 'running' })], now: NOW }),
      'jobs',
      'WARN'
    ),
    `a job held past ${STUCK_HOURS} h is flagged`
  );
  ok(
    !has(
      auditCatalog({
        maps: [good],
        jobs: [job({ status: 'running', updated_at: '2026-09-14T23:00:00Z' })],
        now: NOW,
      }),
      'jobs',
      'WARN'
    ),
    'a job running an hour is not'
  );
  ok(
    has(auditCatalog({ maps: [good], jobs: [job({ map_id: 'gone' })], now: NOW }), 'jobs', 'FAIL'),
    'a job pointing at a deleted map is rejected'
  );

  console.log(`\nself-check: ${failed ? `${failed} failed` : 'all passed'}`);
  process.exit(failed ? 1 : 0);
}

/**
 * Pages by the count actually returned, not a hardcoded page size — PostgREST
 * applies its own max-rows cap (a dashboard setting on the hosted project,
 * independent of the local stack's `max_rows` in supabase/config.toml), and a
 * page short of what we asked for is not the same as the last page. Orders by
 * the table's own primary key so `.range()` pages over a stable sequence
 * instead of relying on undefined ordering across paginated reads.
 */
async function readAll(db, table, cols, orderBy = 'id') {
  const out = [];
  for (let from = 0, pageSize = 1000; ;) {
    const { data, error } = await db
      .from(table)
      .select(cols)
      .order(orderBy)
      .range(from, from + pageSize - 1);
    if (error) throw new Error(`${table}: ${error.message}`);
    if (!data.length) return out;
    out.push(...data);
    from += data.length;
  }
}

async function main() {
  const quiet = process.argv.includes('--quiet');
  const { PUBLIC_SUPABASE_URL: url, SUPABASE_SERVICE_KEY: key } = process.env;
  if (!url || !key) {
    console.error(
      'Need PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY — run with `node --env-file=.env`.'
    );
    process.exit(2);
  }
  const db = createClient(url, key, { auth: { persistSession: false } });
  const [maps, aliases, sources, jobs] = await Promise.all([
    readAll(
      db,
      'maps',
      'id,slug,name,status,year,year_label,bbox,iiif_image,iiif_manifest,annotation_url,allmaps_id,georef_done,thumbnail,source_type,source_url,holding_institution,collection'
    ),
    readAll(db, 'map_slug_aliases', 'slug,map_id', 'slug'),
    readAll(db, 'map_iiif_sources', 'id,map_id,source_type,is_primary,iiif_image'),
    readAll(
      db,
      'pipeline_jobs',
      'id,map_id,kind,status,attempts,max_attempts,created_at,updated_at,finished_at'
    ),
  ]);

  const findings = auditCatalog({ maps, aliases, sources, jobs });
  const fails = findings.filter((f) => f.level === 'FAIL');

  if (!quiet || fails.length)
    for (const f of findings)
      console.log(
        `  ${f.level}  ${f.check.padEnd(12)} ${f.subject.slice(0, 44).padEnd(44)} ${f.detail}`
      );

  console.log(
    `\ncatalog_audit: ${maps.length} maps (${maps.filter(published).length} published), ` +
      `${aliases.length} aliases, ${sources.length} IIIF sources, ${jobs.length} jobs`
  );
  console.log(`  ${fails.length} fail, ${findings.length - fails.length} warn`);

  // Status, not a finding. See the header: this pair is the georeference queue,
  // and `geo_audit.mjs` is what says whether the annotations resolve.
  const queued = maps.filter((m) => !m.annotation_url && m.allmaps_id && !m.georef_done).length;
  if (queued)
    console.log(
      `  ${queued} maps queued for georeferencing — admin \u2192 "Sync georef from Allmaps" promotes any that landed`
    );
  if (!fails.length)
    console.log(
      '  position is a separate question: scripts/geo_audit.mjs, and backfill_map_bbox.mjs --dry --force'
    );
  process.exit(fails.length ? 1 : 0);
}

if (process.argv.includes('--self-check')) selfCheck();
else await main();
