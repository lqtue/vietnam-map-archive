/**
 * What the review API sends and takes (src/routes/api/review/**). Place links are the only task so
 * far, so the item types are theirs; a second task widens `ReviewItem` (docs/plans/review-page-plan.md §7).
 */

export type Relation =
  'same_building' | 'same_site_new_building' | 'moved' | 'gone' | 'none' | 'unsure';

/** One of the machine's candidates (shown arm only). `px` is the position on the sheet, in source pixels. */
export type Candidate = {
  id: string;
  name: string;
  source: string;
  dist_m: number;
  wikidata?: string | null;
  px: [number, number];
  outline_px?: [number, number][] | null;
};

export type SearchHit = {
  id: string;
  name: string;
  source: string;
  dist_m: number;
  wikidata: string | null;
};

/**
 * A plain crop of the sheet (no overlay), and where it sits. A source point `p` lands at
 * `((p.x - x0) * out / side, (p.y - y0) * out / side)` in the image, which is also the
 * overlay's own SVG coordinate (`viewBox="0 0 out out"`).
 */
export type CropView = {
  url: string;
  x0: number;
  y0: number;
  side: number;
  out: number;
  bar_m: number;
};

export type PlaceLinkPayload = {
  text: string;
  category?: string | null;
  names?: string[] | null;
  /** Where the label sits on the sheet, in source pixels. */
  px: [number, number];
  /** The label's own box: x, y, width, height in source pixels. */
  box?: [number, number, number, number] | null;
  pos_from?: string | null;
  lon: number;
  lat: number;
  sheet: { map_id: string; m_per_px: number; north_px: [number, number] };
  views: { close: CropView; context: CropView };
};

export type ReviewItem = {
  item_id: string;
  bound: string;
  payload: PlaceLinkPayload;
  /** The candidates on this reviewer's shown arm; empty otherwise. Never says which arm. */
  proposal: Candidate[];
};

export type NextReply = {
  task: { key: string; title: string; question: string };
  done: number;
  total: number;
  item: ReviewItem | null;
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
  client: { viewport: string; ua: string };
};

export type TaskSummary = {
  key: string;
  title: string;
  question: string;
  question_vi: string | null;
  total: number;
  done: number;
};

/** What a task's overlay component takes: the view, the item, and what to draw over it. */
export type OverlayProps = {
  view: CropView;
  payload: PlaceLinkPayload;
  candidates?: Candidate[];
  picked?: number | null;
};
