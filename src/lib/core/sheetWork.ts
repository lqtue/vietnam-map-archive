/**
 * What has been done to a sheet — the one place the status vocabulary lives.
 *
 * A sheet's work is a set of independent tracks, not one stage: a legend can be
 * read on a sheet whose body never was, and `map_pipeline_status` (one linear
 * stage) cannot say so. Facts come from `/api/admin/maps/work-state`; nothing
 * here is stored, so it cannot disagree with the data. Georeferenced or not is
 * the Map/Image badge and is not repeated.
 */
import type { TriageState } from '$lib/data/maps/triageTypes';

export type WorkFacts = {
  /**
   * Regions the layout pass found. `legend` counts only a region a person confirmed: the layout
   * model labels a legend on ~90% of sheets, including topographic sheets that have none, so its
   * guess is not a fact about the sheet.
   */
  found: { title: boolean; legend: boolean; index: boolean };
  /** Categories with at least one non-rejected label. */
  read: { title: boolean; legend: boolean; body: boolean };
  triage: TriageState;
  /** A person marked the sheet "prints no legend" (`triage.legend`). Legend entries outrank it. */
  noLegend?: boolean;
  /** `map_pipeline_status`: an OCR job finished / a person marked the text reviewed. */
  ocrRan: boolean;
  textReviewed: boolean;
  /** A segmentation job ran / a person marked the shapes reviewed. */
  segRan: boolean;
  shapesReviewed: boolean;
};
export type WorkFactsById = Record<string, WorkFacts>;

export type TrackState = 'done' | 'doing' | 'todo';
export type Track = { key: string; label: string; state: TrackState; hint: string };

/** The sheet with nothing done — what a map with no row is. */
export const NO_WORK: WorkFacts = {
  found: { title: false, legend: false, index: false },
  read: { title: false, legend: false, body: false },
  triage: 'needs_layout',
  ocrRan: false,
  textReviewed: false,
  segRan: false,
  shapesReviewed: false,
};

const pick = (done: boolean, doing: boolean): TrackState =>
  done ? 'done' : doing ? 'doing' : 'todo';

/** One row per track, in the order the work is done. */
export function sheetTracks(f: WorkFacts | undefined): Track[] {
  const w = f ?? NO_WORK;
  return [
    {
      key: 'triage',
      label: 'Triage',
      state: pick(w.triage === 'ready', w.triage !== 'needs_layout'),
      hint: 'Layout checked and a crop accepted',
    },
    {
      key: 'title',
      label: 'Title',
      state: pick(w.read.title, w.found.title),
      hint: 'Title read (yellow: found, not read)',
    },
    {
      key: 'legend',
      label: 'Legend',
      state: w.read.legend || w.noLegend ? 'done' : pick(false, w.found.legend),
      hint:
        w.noLegend && !w.read.legend
          ? 'No legend printed'
          : 'Legend read (yellow: a person marked the region, not read yet)',
    },
    {
      key: 'body',
      label: 'Body',
      state: pick(w.read.body || w.ocrRan, false),
      hint: 'Place names read off the map',
    },
    {
      key: 'text',
      label: 'Text',
      state: pick(w.textReviewed, false),
      hint: 'Place names checked by a person',
    },
    {
      key: 'shapes',
      label: 'Shapes',
      state: pick(w.shapesReviewed, w.segRan),
      hint: 'Shapes checked (yellow: drawn, not checked)',
    },
  ];
}

export const STATE_LABEL: Record<TrackState, string> = {
  done: 'Done',
  doing: 'In progress',
  todo: 'Not yet',
};

/** One word for the whole sheet: every track done, any started, or none. */
export function overallState(f: WorkFacts | undefined): TrackState {
  const states = sheetTracks(f).map((t) => t.state);
  return states.every((s) => s === 'done')
    ? 'done'
    : states.some((s) => s !== 'todo')
      ? 'doing'
      : 'todo';
}

const stateOf = (f: WorkFacts | undefined, key: string): TrackState =>
  sheetTracks(f).find((t) => t.key === key)!.state;

/** The "Work" filter: what a person scanning the catalog is hunting for. */
export const WORK_FILTERS = [
  { key: '', label: 'Work: any', test: () => true },
  { key: 'triage', label: 'Needs triage', test: (f) => stateOf(f, 'triage') !== 'done' },
  { key: 'legend', label: 'Legend found, not read', test: (f) => stateOf(f, 'legend') === 'doing' },
  {
    key: 'text',
    label: 'Text not checked',
    test: (f) => stateOf(f, 'body') === 'done' && stateOf(f, 'text') !== 'done',
  },
  { key: 'shapes', label: 'Shapes not checked', test: (f) => stateOf(f, 'shapes') !== 'done' },
  { key: 'done', label: 'All done', test: (f) => overallState(f) === 'done' },
] as const satisfies readonly {
  key: string;
  label: string;
  test: (f: WorkFacts | undefined) => boolean;
}[];

export const matchesWork = (key: string, f: WorkFacts | undefined): boolean =>
  (WORK_FILTERS.find((w) => w.key === key) ?? WORK_FILTERS[0]).test(f);

/** Where a sheet stands for legend work. `ready` = legend region found, not yet read. */
export type LegendReadiness = 'read' | 'none' | 'ready' | 'unlocated';

export function legendReadiness(s: WorkFacts | undefined): LegendReadiness {
  if (s?.read.legend) return 'read';
  if (s?.noLegend) return 'none';
  return s?.found.legend ? 'ready' : 'unlocated';
}

/** The legend picker's chip text for a sheet whose legend has no entries yet. */
export function readSummary(s: WorkFacts | undefined): string | undefined {
  if (!s) return undefined;
  if (s.noLegend) return 'no legend printed';
  const parts = [
    s.found.legend && 'legend found',
    s.read.title && 'title read',
    s.read.body && 'body read',
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : undefined;
}
