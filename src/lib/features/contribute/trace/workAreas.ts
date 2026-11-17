/**
 * Work areas drawn on a sheet in the Shapes tool, so a person tracing for a
 * model test can see where to trace and where not to.
 *
 * 1882 Saigon cadastral plan: the ten squares in
 * work/MapSAM2/tiles_1882/tiles.json (8 train, 2 check) and the areas kept
 * back for the final test (reserved_test R1, R2, and the river held-out
 * windows of work/image-processing/experiments/river-reference). Keep this in
 * step with those two files. Boxes are source pixels [x, y, w, h].
 */
export type WorkAreaRole = 'train' | 'check' | 'keep-out';

export interface WorkArea {
  id: string;
  role: WorkAreaRole;
  box: [number, number, number, number];
}

const SAIGON_1882 = '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b';

const RIVER_HELDOUT: [number, number, number, number][] = [
  [2200, 4800, 1000, 1000],
  [3500, 2600, 1000, 1000],
  [8400, 6800, 1000, 1000],
  [3700, 5000, 1000, 1000],
  [10200, 3000, 1000, 1000],
  [4800, 5500, 1000, 1000],
  [2200, 2400, 1000, 1000],
  [7400, 2300, 1000, 1000],
  [5300, 3200, 1000, 1000],
  [10300, 4200, 1000, 1000],
];

export const WORK_AREAS: Record<string, WorkArea[]> = {
  [SAIGON_1882]: [
    { id: 't01', role: 'check', box: [6300, 2610, 1024, 1024] },
    { id: 't02', role: 'train', box: [6420, 3776, 1024, 1024] },
    { id: 't03', role: 'train', box: [8728, 4720, 1024, 1024] },
    { id: 't04', role: 'train', box: [7512, 3312, 1024, 1024] },
    { id: 't05', role: 'train', box: [5000, 2000, 1024, 1024] },
    { id: 't06', role: 'check', box: [2520, 3760, 1024, 1024] },
    { id: 't07', role: 'train', box: [1176, 2864, 1024, 1024] },
    { id: 't08', role: 'train', box: [3864, 1520, 1024, 1024] },
    { id: 't09', role: 'train', box: [7448, 5552, 1024, 1024] },
    { id: 't10', role: 'train', box: [6424, 5168, 1024, 1024] },
    { id: 'R1', role: 'keep-out', box: [4760, 4790, 600, 600] },
    { id: 'R2', role: 'keep-out', box: [8500, 2590, 600, 600] },
    ...RIVER_HELDOUT.map((box, i) => ({ id: `W${i + 1}`, role: 'keep-out' as const, box })),
  ],
};
