import { expect, test } from '@playwright/test';
import {
  OcrDraftSession,
  type DraftTransport,
} from '../src/lib/features/contribute/ocr/ocrDraftSession';
import type { OcrExtraction } from '../src/lib/features/contribute/shared/types';
const row = (id: string, extra: Partial<OcrExtraction> = {}): OcrExtraction => ({
  id,
  run_id: 'run',
  text: id,
  category: 'street',
  text_validated: null,
  category_validated: null,
  status: 'pending',
  tile_x: 0,
  tile_y: 0,
  tile_w: 0,
  tile_h: 0,
  global_x: 0,
  global_y: 0,
  global_w: 100,
  global_h: 20,
  confidence: 1,
  ...extra,
});
function harness() {
  const calls: { kind: string; args: unknown[] }[] = [];
  let fail = '';
  let n = 0;
  const call = async (kind: string, args: unknown[]) => {
    calls.push({ kind, args });
    if (fail === kind) throw new Error('offline');
  };
  const transport: DraftTransport = {
    patch: async (...args) => {
      await call('patch', args);
    },
    create: async (...args) => {
      await call('create', args);
      return `created-${++n}`;
    },
    group: async (...args) => {
      await call('group', args);
      return `group-${++n}`;
    },
    ungroup: async (...args) => {
      await call('ungroup', args);
    },
    verdict: async (...args) => {
      await call('verdict', args);
      return args[1].length;
    },
  };
  const session = new OcrDraftSession(transport);
  session.load([row('a'), row('b', { global_x: 200 })]);
  return {
    session,
    calls,
    fail: (kind: string) => {
      fail = kind;
    },
    transport,
  };
}
test('text, verdict, geometry and grouping make no requests before Save', () => {
  const { session, calls } = harness();
  session.stage('a', { _editText: 'Rue', _editStatus: 'validated', rotation_deg: 35 });
  session.group(['a', 'b'], 'Rue aux Fleurs', 'street');
  expect(calls).toEqual([]);
  expect(session.dirtyIds().size).toBe(3);
});
test('coalesces repeated geometry and text edits into one PATCH', async () => {
  const { session, calls } = harness();
  session.stage('a', { global_x: 10 });
  session.stage('a', { global_x: 20, _editText: 'Rue', _editStatus: 'validated' });
  await session.flush('map', () => {});
  expect(calls).toEqual([
    { kind: 'patch', args: ['map', { id: 'a', text: 'Rue', global_x: 20, status: 'validated' }] },
  ]);
  expect(session.dirtyIds().size).toBe(0);
  // Bound input edits after Save cannot mutate the saved baseline.
  session.rows.find((r) => r.id === 'a')!._editText = 'Changed again';
  expect(session.dirtyIds().has('a')).toBe(true);
});
test('groups verdict-only drafts into one request per status', async () => {
  const { session, calls } = harness();
  session.stage('a', { _editStatus: 'validated' });
  session.stage('b', { _editStatus: 'validated' });
  await session.flush('map', () => {});
  expect(calls).toEqual([{ kind: 'verdict', args: ['map', ['a', 'b'], 'validated'] }]);
  expect(session.dirtyIds().size).toBe(0);
});
test('new boxes and original edits are saved before their group, with IDs remapped', async () => {
  const { session, calls } = harness();
  session.add(row('local', { text: 'Fleurs', rotation_deg: 42 }));
  session.stage('a', { _editText: 'R. aux' });
  session.group(['a', 'local'], 'R. aux Fleurs', 'street');
  await session.flush('map', () => {});
  expect(calls.map((c) => c.kind)).toEqual(['create', 'patch', 'group']);
  expect(calls[2].args).toEqual(['map', ['a', 'created-1'], 'R. aux Fleurs', 'street']);
  expect(session.rows.find((r) => r.id === 'created-1')?.rotation_deg).toBe(42);
  expect(session.rows.find((r) => r.id === 'created-1')?.text_group_id).toBe('group-2');
  expect(session.dirtyIds().size).toBe(0);
});
test('group then ungroup before Save cancels the operation entirely', async () => {
  const { session, calls } = harness();
  const id = session.group(['a', 'b'], 'Combined', 'street');
  session.ungroup(id);
  await session.flush('map', () => {});
  expect(calls).toEqual([]);
  expect(session.dirtyIds().size).toBe(0);
});
test('existing ungroup is saved before edits to its originals', async () => {
  const { session, calls } = harness();
  session.load([
    row('g', { is_text_group: true }),
    row('a', { text_group_id: 'g', text_group_order: 0 }),
    row('b', { text_group_id: 'g', text_group_order: 1 }),
  ]);
  session.ungroup('g');
  session.stage('a', { global_x: 5 });
  await session.flush('map', () => {});
  expect(calls.map((c) => c.kind)).toEqual(['ungroup', 'patch']);
  expect(session.dirtyIds().size).toBe(0);
});
test('a failed group retains drafts, and retry does not repeat acknowledged edits', async () => {
  const { session, calls, fail } = harness();
  session.stage('a', { _editText: 'Rue' });
  session.group(['a', 'b'], 'Rue Ollier', 'street');
  fail('group');
  await expect(session.flush('map', () => {})).rejects.toThrow('offline');
  expect(session.dirtyIds().size).toBe(3);
  const recovered = new OcrDraftSession(harness().transport);
  recovered.restore(JSON.parse(JSON.stringify(session.snapshot())));
  expect(recovered.rows.find((r) => r.id === 'a')?._editText).toBe('Rue');
  fail('');
  await session.flush('map', () => {});
  expect(calls.filter((c) => c.kind === 'patch')).toHaveLength(1);
  expect(session.dirtyIds().size).toBe(0);
});
test('a group saved before a failed verdict is not created twice on retry', async () => {
  const { session, calls, fail } = harness();
  const id = session.group(['a', 'b'], 'Rue Ollier', 'street');
  session.stage(id, { _editStatus: 'validated' });
  fail('verdict');
  await expect(session.flush('map', () => {})).rejects.toThrow();
  expect(session.dirtyIds().size).toBe(1);
  fail('');
  await session.flush('map', () => {});
  expect(calls.filter((c) => c.kind === 'group')).toHaveLength(1);
  expect(session.dirtyIds().size).toBe(0);
});
test('cache recovery merges fresh clean rows but keeps draft geometry and membership', () => {
  const { session } = harness();
  session.stage('a', { global_x: 25 });
  const id = session.group(['a', 'b'], 'Combined', 'street');
  const recovered = new OcrDraftSession();
  recovered.restore(JSON.parse(JSON.stringify(session.snapshot())));
  recovered.load([row('a'), row('b', { global_x: 200 }), row('c')]);
  expect(recovered.rows.find((r) => r.id === 'a')?.global_x).toBe(25);
  expect(recovered.rows.find((r) => r.id === 'b')?.text_group_id).toBe(id);
  expect(recovered.rows.some((r) => r.id === 'c')).toBe(true);
  expect(recovered.conflicts).toEqual([]);
});
test('external changes keep the draft but block Save; discard adopts the fresh server row', async () => {
  const { session, calls } = harness();
  session.stage('a', { _editText: 'Local' });
  session.load([row('a', { text_validated: 'External' }), row('b', { global_x: 200 })]);
  expect(session.rows.find((r) => r.id === 'a')?._editText).toBe('Local');
  await expect(session.flush('map', () => {})).rejects.toThrow('changed');
  expect(calls).toEqual([]);
  session.discard();
  expect(session.rows.find((r) => r.id === 'a')?._editText).toBe('External');
  expect(session.dirtyIds().size).toBe(0);
});
