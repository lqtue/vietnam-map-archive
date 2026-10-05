/**
 * The printed reference grid on a sheet, and how an index entry's grid cell
 * becomes a position.
 *
 * A printed index — "Bệnh Viện Chợ Rẫy ... J 5,6" — is a gazetteer that already
 * knows roughly where everything is. Turning those references into points costs
 * no further model calls, and it covers every entry, which spotting the numerals
 * printed on the map body never will.
 *
 * The trade is accuracy: a cell, not a point. A grid position is honest about
 * being the middle of a square a few hundred metres across, and is meant to be
 * superseded by an observed numeral wherever one is found.
 *
 * Columns and rows are stored as the labels actually printed on the sheet, in
 * order, rather than derived from A-Z: sheets skip `I` to avoid confusion with
 * `1`, start at `0`, or run `AA` past `Z`, and guessing any of that puts every
 * point one cell out.
 */

/** `[x, y, w, h]` in source pixels. */
export type GridBox = [number, number, number, number];

export type MapGrid = {
  /** The gridded area in source pixels — the outer edge of cell (first, first). */
  bbox: GridBox;
  /** Column labels left to right, exactly as printed. */
  columns: string[];
  /** Row labels top to bottom, exactly as printed. */
  rows: string[];
};

/** Normalise a label for comparison: case and spacing vary between the margin
 *  and the index that refers to it. */
const norm = (s: string) => s.trim().toUpperCase().replace(/\s+/g, '');

/**
 * The labels a grid reference names, in printed order.
 *
 * Real references from the 1968 Saigon index:
 *   "J 6"      one cell
 *   "J 5,6"    a run
 *   "G H 10"   a run on the other axis
 *
 * Deliberately does NOT decide which token is a column and which is a row.
 * That convention is not universal: this sheet numbers its columns 1-13 and
 * letters its rows A-O, so "J 6" is row J, column 6 — the opposite way round
 * from the sheets where letters run across the top. Assuming one convention
 * silently resolves every reference to nothing.
 */
export function parseGridRef(ref: string): string[] {
  if (!ref) return [];
  return (ref.replace(/[;/,]/g, ' ').match(/[A-Za-z]+|\d+/g) ?? []).map(norm);
}

/**
 * The pixel rectangle a grid reference covers, or null when the grid does not
 * contain it.
 *
 * Each token is resolved against whichever axis actually carries that label, so
 * the same code reads "J 6" on a sheet that letters its rows and on one that
 * letters its columns. A reference naming several labels on one axis returns
 * the box spanning all of them, which is what the sheet means by "G H 10" — the
 * feature straddles the boundary.
 */
export function cellBox(grid: MapGrid, ref: string): GridBox | null {
  if (!grid.columns.length || !grid.rows.length) return null;
  const cols = grid.columns.map(norm);
  const rows = grid.rows.map(norm);

  const colIdx: number[] = [];
  const rowIdx: number[] = [];
  for (const tok of parseGridRef(ref)) {
    const c = cols.indexOf(tok);
    const r = rows.indexOf(tok);
    // A label carried by exactly one axis is unambiguous. When both carry it —
    // a sheet numbering both axes — prefer the column, and the row lookup below
    // still gets its own token from the rest of the reference.
    if (c >= 0 && (r < 0 || !colIdx.length)) colIdx.push(c);
    else if (r >= 0) rowIdx.push(r);
  }
  if (!colIdx.length || !rowIdx.length) return null;

  const [gx, gy, gw, gh] = grid.bbox;
  const cw = gw / grid.columns.length;
  const ch = gh / grid.rows.length;

  const c0 = Math.min(...colIdx);
  const c1 = Math.max(...colIdx);
  const r0 = Math.min(...rowIdx);
  const r1 = Math.max(...rowIdx);

  return [gx + c0 * cw, gy + r0 * ch, (c1 - c0 + 1) * cw, (r1 - r0 + 1) * ch];
}

/** The centre of what a grid reference names, in source pixels. */
export function cellCentre(grid: MapGrid, ref: string): [number, number] | null {
  const box = cellBox(grid, ref);
  return box ? [box[0] + box[2] / 2, box[1] + box[3] / 2] : null;
}

/**
 * How big one cell is, in source pixels — the honest error bar on a grid
 * position. Callers surface it so a viewer can tell a cell-centre from an
 * observed numeral.
 */
export function cellSize(grid: MapGrid): { w: number; h: number } | null {
  if (!grid.columns.length || !grid.rows.length) return null;
  return { w: grid.bbox[2] / grid.columns.length, h: grid.bbox[3] / grid.rows.length };
}

/**
 * Does a point land where an index entry's grid reference says it should?
 *
 * Tolerance is the stated cell inflated by a full cell on each side: the index
 * cell is itself approximate, and a feature near a boundary is often catalogued
 * one cell over. That still rejects a point kilometres away. `null` means there
 * is nothing to check against (no grid, no reference, or a reference the grid
 * does not contain).
 */
export function cellAgreement(
  grid: MapGrid | null,
  ref: string | null | undefined,
  px: number,
  py: number
): boolean | null {
  if (!grid || !ref) return null;
  const box = cellBox(grid, ref);
  const cell = cellSize(grid);
  if (!box || !cell) return null;
  return (
    px >= box[0] - cell.w &&
    px <= box[0] + box[2] + cell.w &&
    py >= box[1] - cell.h &&
    py <= box[1] + box[3] + cell.h
  );
}

/** Validate a grid off the wire. Returns null rather than throwing, so one bad
 *  answer costs the fallback and not the request. */
export function parseGrid(raw: unknown): MapGrid | null {
  if (!raw || typeof raw !== 'object') return null;
  const g = raw as Record<string, unknown>;
  const bb = g.bbox;
  if (!Array.isArray(bb) || bb.length !== 4) return null;
  const nums = bb.map(Number);
  if (nums.some((n) => !Number.isFinite(n))) return null;
  if (nums[2] < 1 || nums[3] < 1) return null;
  const columns = Array.isArray(g.columns) ? g.columns.map(String).filter(Boolean) : [];
  const rows = Array.isArray(g.rows) ? g.rows.map(String).filter(Boolean) : [];
  if (columns.length < 2 || rows.length < 2) return null;
  return { bbox: [nums[0], nums[1], nums[2], nums[3]], columns, rows };
}
