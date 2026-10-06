/** One working copy per sheet. Only flush() crosses the write boundary. */
import {
  withEditState,
  patchExtraction,
  createManualBbox,
  groupTextBoxes,
  ungroupTextBoxes,
  batchSetStatus,
  type OcrExtractionPatch,
  type OcrStatus,
} from '../shared/ocrApi';
import type { OcrExtraction, EditableOcrExtraction } from '../shared/types';

export const GEOMETRY_FIELDS = [
  'global_x',
  'global_y',
  'global_w',
  'global_h',
  'rotation_deg',
  'label_w',
  'label_h',
] as const;
const textOf = (r: OcrExtraction) => r._editText ?? r.text_validated ?? r.text;
const catOf = (r: OcrExtraction) => r._editCategory ?? r.category_validated ?? r.category;
const statusOf = (r: OcrExtraction) => r._editStatus ?? r.status;
function signature(r: OcrExtraction): string {
  return JSON.stringify([
    textOf(r),
    catOf(r),
    statusOf(r),
    ...GEOMETRY_FIELDS.map((k) => r[k] ?? null),
    r.text_group_id ?? null,
    r.text_group_order ?? null,
    !!r.is_text_group,
  ]);
}
export type DraftSnapshot = { version: 1; base: OcrExtraction[]; rows: EditableOcrExtraction[] };
export type DraftTransport = {
  patch: typeof patchExtraction;
  create: typeof createManualBbox;
  group: typeof groupTextBoxes;
  ungroup: typeof ungroupTextBoxes;
  verdict: typeof batchSetStatus;
};
const api: DraftTransport = {
  patch: patchExtraction,
  create: createManualBbox,
  group: groupTextBoxes,
  ungroup: ungroupTextBoxes,
  verdict: batchSetStatus,
};

export class OcrDraftSession {
  base: OcrExtraction[] = [];
  rows: EditableOcrExtraction[] = [];
  conflicts: string[] = [];
  private aliases = new Map<string, string>();
  resolveId(id: string): string {
    return this.aliases.has(id) ? this.resolveId(this.aliases.get(id)!) : id;
  }
  private latest: OcrExtraction[] = [];
  constructor(private transport: DraftTransport = api) {}
  dirtyIds(): Set<string> {
    const before = new Map(this.base.map((r) => [r.id, r]));
    const after = new Map(this.rows.map((r) => [r.id, r]));
    return new Set(
      [...new Set([...before.keys(), ...after.keys()])].filter(
        (id) =>
          !before.has(id) ||
          !after.has(id) ||
          signature(before.get(id)!) !== signature(after.get(id)!)
      )
    );
  }
  snapshot(): DraftSnapshot {
    return { version: 1, base: this.base, rows: this.rows };
  }
  restore(value: DraftSnapshot) {
    if (value.version !== 1 || !Array.isArray(value.base) || !Array.isArray(value.rows))
      throw new Error('Invalid OCR draft cache');
    this.base = value.base;
    this.rows = withEditState(value.rows).map((r, i) => ({ ...r, ...value.rows[i] }));
  }
  /** Fresh reads update clean rows, while cached drafts retain their original baseline. */
  load(fresh: OcrExtraction[]) {
    this.latest = fresh;
    const dirty = this.dirtyIds();
    const old = new Map(this.base.map((r) => [r.id, r]));
    const drafts = new Map(this.rows.map((r) => [r.id, r]));
    const incoming = new Map(fresh.map((r) => [r.id, r]));
    this.conflicts = [...dirty].filter(
      (id) =>
        old.has(id) &&
        (!incoming.has(id) || signature(old.get(id)!) !== signature(incoming.get(id)!))
    );
    this.base = [
      ...fresh.filter((r) => !dirty.has(r.id)),
      ...this.base.filter((r) => dirty.has(r.id)),
    ];
    this.rows = [
      ...withEditState(fresh).filter((r) => !dirty.has(r.id)),
      ...this.rows.filter((r) => dirty.has(r.id)),
    ];
    // Locally deleted parents must stay deleted on reload.
    this.rows = this.rows.filter((r) => !dirty.has(r.id) || drafts.has(r.id));
  }
  stage(id: string, patch: Partial<EditableOcrExtraction>) {
    this.rows = this.rows.map((r) => (r.id === id ? { ...r, ...patch } : r));
  }
  add(row: OcrExtraction) {
    this.rows = [...this.rows, ...withEditState([row])];
  }
  group(ids: string[], text: string, category: string): string {
    const parts = ids.map((id) => this.rows.find((r) => r.id === id));
    if (
      new Set(ids).size !== ids.length ||
      parts.length < 2 ||
      parts.length > 100 ||
      parts.some((r) => !r || r.is_text_group || r.text_group_id)
    )
      throw new Error('Choose ungrouped boxes');
    const originals = parts as EditableOcrExtraction[];
    const x = Math.min(...originals.map((r) => r.global_x)),
      y = Math.min(...originals.map((r) => r.global_y));
    const id = crypto.randomUUID();
    this.add({
      id,
      run_id: originals[0].run_id,
      text,
      category,
      text_validated: null,
      category_validated: null,
      status: 'pending',
      confidence: 1,
      is_text_group: true,
      tile_x: Math.round(x),
      tile_y: Math.round(y),
      tile_w: 0,
      tile_h: 0,
      global_x: x,
      global_y: y,
      global_w: Math.max(...originals.map((r) => r.global_x + r.global_w)) - x,
      global_h: Math.max(...originals.map((r) => r.global_y + r.global_h)) - y,
    });
    this.rows = this.rows.map((r) =>
      ids.includes(r.id) ? { ...r, text_group_id: id, text_group_order: ids.indexOf(r.id) } : r
    );
    return id;
  }
  ungroup(id: string) {
    this.rows = this.rows
      .filter((r) => r.id !== id)
      .map((r) =>
        r.text_group_id === id ? { ...r, text_group_id: null, text_group_order: null } : r
      );
  }
  discard() {
    if (this.conflicts.length) {
      const ids = new Set(this.conflicts);
      this.base = [
        ...this.base.filter((r) => !ids.has(r.id)),
        ...this.latest.filter((r) => ids.has(r.id)),
      ];
    }
    this.rows = withEditState(this.base);
    this.conflicts = [];
  }
  /** Acknowledge each successful write before the next. Failed work remains retryable. */
  private acknowledge(row: EditableOcrExtraction) {
    const clean = {
      ...row,
      text_validated: textOf(row),
      category_validated: catOf(row),
      status: statusOf(row),
    };
    this.base = [
      ...this.base.filter((r) => r.id !== row.id),
      { ...clean, _editText: undefined, _editCategory: undefined, _editStatus: undefined },
    ];
    this.rows = this.rows.map((r) => (r.id === row.id ? clean : r));
  }
  private replaceId(oldId: string, newId: string) {
    this.aliases.set(oldId, newId);
    this.rows = this.rows.map((r) => ({
      ...r,
      id: r.id === oldId ? newId : r.id,
      text_group_id: r.text_group_id === oldId ? newId : r.text_group_id,
    }));
  }
  async flush(mapId: string, progress: () => void): Promise<number> {
    if (this.conflicts.length)
      throw new Error(
        'Saved labels changed since this draft. Discard the draft or reload after resolving the conflict.'
      );
    let saved = 0;
    // Ungroup existing parents before editing the restored originals.
    for (const parent of this.base.filter(
      (r) => r.is_text_group && !this.rows.some((v) => v.id === r.id)
    )) {
      await this.transport.ungroup(mapId, parent.id);
      this.base = this.base
        .filter((r) => r.id !== parent.id)
        .map((r) =>
          r.text_group_id === parent.id ? { ...r, text_group_id: null, text_group_order: null } : r
        );
      saved++;
      progress();
    }
    const existing = new Set(this.base.map((r) => r.id));
    for (const row of this.rows.filter((r) => !r.is_text_group && !existing.has(r.id))) {
      const id = await this.transport.create(mapId, {
        run_id: row.run_id || 'manual',
        ...(Object.fromEntries(GEOMETRY_FIELDS.map((k) => [k, row[k]])) as Pick<
          OcrExtraction,
          'global_x' | 'global_y' | 'global_w' | 'global_h'
        >),
        text: textOf(row),
        category: catOf(row),
      });
      this.replaceId(row.id, id);
      // Creation is pending and ungrouped; a later verdict/group is still a draft.
      const created = this.rows.find((r) => r.id === id)!;
      this.base = [
        ...this.base,
        {
          ...created,
          text_group_id: null,
          text_group_order: null,
          status: 'pending',
          _editStatus: 'pending',
        },
      ];
      saved++;
      progress();
    }
    const byId = new Map(this.base.map((r) => [r.id, r]));
    const verdicts: Record<OcrStatus, EditableOcrExtraction[]> = {
      pending: [],
      validated: [],
      rejected: [],
    };
    for (const row of this.rows) {
      const before = byId.get(row.id);
      if (!before) continue;
      // Persist edits to originals before making a new group. Existing members stay immutable.
      if (before.text_group_id) continue;
      const patch: OcrExtractionPatch = { id: row.id };
      if (textOf(row) !== textOf(before)) patch.text = textOf(row);
      if (catOf(row) !== catOf(before)) patch.category = catOf(row);
      for (const k of GEOMETRY_FIELDS)
        if ((row[k] ?? null) !== (before[k] ?? null)) Object.assign(patch, { [k]: row[k] });
      if (Object.keys(patch).length > 1) {
        if (statusOf(row) !== statusOf(before)) patch.status = statusOf(row);
        await this.transport.patch(mapId, patch);
        // Membership is only acknowledged by the group RPC below.
        this.acknowledge({
          ...row,
          text_group_id: before.text_group_id,
          text_group_order: before.text_group_order,
        });
        this.stage(row.id, {
          text_group_id: row.text_group_id,
          text_group_order: row.text_group_order,
        });
        saved++;
        progress();
      } else if (statusOf(row) !== statusOf(before)) verdicts[statusOf(row)].push(row);
    }
    for (const status of ['pending', 'validated', 'rejected'] as OcrStatus[]) {
      const rows = verdicts[status];
      if (!rows.length) continue;
      await this.transport.verdict(
        mapId,
        rows.map((r) => r.id),
        status
      );
      for (const row of rows) {
        const before = byId.get(row.id)!;
        this.acknowledge({
          ...row,
          text_group_id: before.text_group_id,
          text_group_order: before.text_group_order,
        });
        this.stage(row.id, {
          text_group_id: row.text_group_id,
          text_group_order: row.text_group_order,
        });
      }
      saved += rows.length;
      progress();
    }
    for (const group of this.rows.filter(
      (r) => r.is_text_group && !this.base.some((b) => b.id === r.id)
    )) {
      const parts = this.rows
        .filter((r) => r.text_group_id === group.id)
        .sort((a, b) => (a.text_group_order ?? 0) - (b.text_group_order ?? 0));
      const id = await this.transport.group(
        mapId,
        parts.map((r) => r.id),
        textOf(group),
        catOf(group)
      );
      this.replaceId(group.id, id);
      const parent = this.rows.find((r) => r.id === id)!;
      // Group RPC creates a pending parent.
      this.base = [...this.base, { ...parent, status: 'pending', _editStatus: 'pending' }];
      this.base = this.base.map((r) =>
        parts.some((p) => p.id === r.id)
          ? { ...r, text_group_id: id, text_group_order: parts.findIndex((p) => p.id === r.id) }
          : r
      );
      saved++;
      progress();
      if (statusOf(parent) !== 'pending') {
        await this.transport.verdict(mapId, [id], statusOf(parent));
      }
      this.acknowledge(parent);
      progress();
    }
    return saved;
  }
}
