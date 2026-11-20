/**
 * What a place-link verdict must look like, and what it becomes in `review_events`.
 *
 * Pure: no database. `reviewSession.ts` reads the rows and calls these. The rules are the ones
 * `work/image-processing/experiments/place-links/confirm.py` (`Session.submit`) enforces, so a web
 * verdict and an offline verdict mean the same thing and the export scores the same
 * (docs/plans/review-page-plan.md §2.1–2.6).
 */

import { error } from '@sveltejs/kit';
import { foldForSearch } from '$lib/core/utils/unaccent';
import type { Json } from '$lib/data/supabase/types';
import type { Arm } from './reviewArms';

export const RELATIONS = [
  'same_building',
  'same_site_new_building',
  'moved',
  'gone',
  'none',
  'unsure',
] as const;
export type Relation = (typeof RELATIONS)[number];
/** These three name a place, so they need a pick; the others do not. */
const NEEDS_PICK: readonly Relation[] = ['same_building', 'same_site_new_building', 'moved'];

/**
 * The browser's clock is not the server's. `shown_at` and `decided_at` come from the page, so a
 * laptop a few seconds fast would have every verdict refused if the future were not allowed a
 * little room. Anything past this is a wrong clock or a forged stamp.
 */
export const CLOCK_SLACK_MS = 10_000;
/** A sitting stamp older than this cannot be a human reading one item. */
export const MAX_ITEM_MS = 24 * 3600 * 1000;

export type Place = {
  id: string;
  name: string;
  source: string;
  lon: number;
  lat: number;
  dist_m: number;
  names?: string[];
  osm?: string | null;
  tasco_ids?: number[];
  wikidata?: string | null;
  osm_alts?: string[];
};

export type VerdictBody = {
  item_id: string;
  bound: string;
  relation: Relation;
  pick: number | null;
  search_id: string | null;
  note: string;
  shown_at: number;
  decided_at: number;
  hidden_ms: number;
  client_id: string;
  client: { [key: string]: Json | undefined };
};

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function str(o: Obj, field: string, max: number): string {
  const v = o[field];
  if (typeof v !== 'string' || v.length < 1 || v.length > max)
    throw error(400, `${field} must be a string of 1-${max} characters`);
  return v;
}

function num(o: Obj, field: string): number {
  const v = o[field];
  if (typeof v !== 'number' || !Number.isFinite(v)) throw error(400, `${field} must be a number`);
  return v;
}

/** Shape-check a verdict request. Every failure is a 400 naming the field. */
export function parseVerdictBody(raw: unknown): VerdictBody {
  if (!isObj(raw)) throw error(400, 'Body must be an object');
  const relation = raw.relation;
  if (typeof relation !== 'string' || !RELATIONS.includes(relation as Relation))
    throw error(400, `relation must be one of ${RELATIONS.join(', ')}`);
  const pick = raw.pick ?? null;
  if (pick !== null && (typeof pick !== 'number' || !Number.isInteger(pick) || pick < 1))
    throw error(400, 'pick must be a positive integer or null');
  const searchId = raw.search_id ?? null;
  if (searchId !== null && (typeof searchId !== 'string' || searchId.length > 200))
    throw error(400, 'search_id must be a string or null');
  const note = raw.note ?? '';
  if (typeof note !== 'string' || note.length > 2000)
    throw error(400, 'note must be a string of at most 2000 characters');
  const hidden = raw.hidden_ms ?? 0;
  if (typeof hidden !== 'number' || !Number.isFinite(hidden) || hidden < 0)
    throw error(400, 'hidden_ms must be a non-negative number');
  const clientId = str(raw, 'client_id', 36);
  if (!UUID_RE.test(clientId)) throw error(400, 'client_id must be a uuid');
  const client = raw.client ?? {};
  if (!isObj(client) || JSON.stringify(client).length > 4000)
    throw error(400, 'client must be a small object');
  return {
    item_id: str(raw, 'item_id', 200),
    bound: str(raw, 'bound', 128),
    relation: relation as Relation,
    pick,
    search_id: searchId,
    note: note.trim(),
    shown_at: num(raw, 'shown_at'),
    decided_at: num(raw, 'decided_at'),
    hidden_ms: Math.round(hidden),
    client_id: clientId,
    client: client as VerdictBody['client'],
  };
}

/** Stamps are epoch milliseconds from the page. The database also checks decided >= shown. */
export function checkClock(shownMs: number, decidedMs: number, nowMs: number): void {
  if (decidedMs < shownMs) throw error(400, 'decided_at is before shown_at');
  if (decidedMs > nowMs + CLOCK_SLACK_MS) throw error(400, 'decided_at is in the future');
  if (shownMs > nowMs + CLOCK_SLACK_MS) throw error(400, 'shown_at is in the future');
  if (decidedMs - shownMs > MAX_ITEM_MS)
    throw error(400, 'shown_at is more than a day before decided_at');
}

/** `confirm.py` `Session.target`: the place a verdict points at, in the offline file's shape. */
export function placeTarget(c: Place): Json {
  return {
    source: c.source,
    id: c.osm || (c.tasco_ids?.length ? `tasco:${c.tasco_ids[0]}` : c.id),
    name: c.name,
    lng: c.lon,
    lat: c.lat,
    wikidata: c.wikidata ?? null,
    osm_alts: c.osm_alts ?? [],
    tasco_ids: c.tasco_ids ?? [],
  };
}

/**
 * The `verdicts` object for the event, as `confirm.py` writes it, or a 400. `arm` is the server's
 * own (never the client's): the export needs it to score shown against blind.
 */
export function buildVerdict(
  body: Pick<VerdictBody, 'relation' | 'pick' | 'search_id'>,
  arm: Arm,
  proposal: Place[],
  pool: Place[]
): { verdicts: Json; proposalShown: boolean } {
  let target: Json = null;
  let via: string | null = null;
  let pick: number | null = null;
  if (body.search_id) {
    const hit = pool.find((p) => p.id === body.search_id);
    if (!hit) throw error(400, "That place is not in this item's pool");
    target = placeTarget(hit);
    via = 'search';
  } else if (body.pick) {
    // On the blind and no-candidate arms there was no candidate on screen to pick.
    if (arm !== 'shown') throw error(400, 'No candidates were shown on this item');
    const cand = proposal[body.pick - 1];
    if (!cand) throw error(400, 'pick is not one of the candidates');
    target = placeTarget(cand);
    via = 'candidate';
    pick = body.pick;
  }
  if (body.relation === 'none') {
    target = null;
    via = null;
    pick = null;
  }
  if (NEEDS_PICK.includes(body.relation) && target === null)
    throw error(400, 'Pick a place first (a candidate, or search)');
  return {
    verdicts: { arm, pick, pick_via: via, relation: body.relation, target },
    proposalShown: arm === 'shown' && proposal.length > 0,
  };
}

/** The same fold as `confirm.py`: no accents, lower case, runs of other characters become a space. */
export const fold = (s: string): string =>
  foldForSearch(s ?? '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

/** `Session.search`: the pool within 300 m whose names contain the query, nearest first. */
export function searchPool(pool: Place[], q: string, n = 8) {
  const needle = fold(q);
  return pool
    .filter((p) => !needle || (p.names ?? [p.name]).some((x) => fold(x).includes(needle)))
    .sort((a, b) => a.dist_m - b.dist_m)
    .slice(0, n)
    .map((p) => ({
      id: p.id,
      name: p.name,
      source: p.source,
      dist_m: p.dist_m,
      wikidata: p.wikidata ?? null,
    }));
}
