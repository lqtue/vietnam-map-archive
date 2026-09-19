/**
 * segCommand.ts — builds the MapSAM2 inference command the Segment tab hands to
 * Colab, and remembers the knobs that went into it.
 *
 * localStorage key: `digitalize-seg-<mapId>`. Kept under that name — it is what
 * every operator's browser already holds, and a rename would lose their paths.
 */
import { readJson, writeJson } from '$lib/core/utils/persistence/storage';

export type SegConfig = {
  checkpointPath: string;
  mapsam2Dir: string;
  priorPath: string;
  encoder: 'vit_t' | 'vit_s' | 'vit_b' | 'vit_l';
  useTextMask: boolean;
  useWatershed: boolean;
};

/**
 * Colab defaults, because that is where a GPU is. `checkpointPath` is the LoRA
 * checkpoint the April 2026 run actually wrote — `epoch_010.pth` under the
 * cached dataset, in upstream MapSAM2's `logs/<exp>/Model/epoch_NN.pth` naming.
 * It replaces `MyDrive/mapsam2_checkpoint.pth`, a path no file has ever been at,
 * so the panel printed a command that could only fail on a missing file. A
 * machine with the checkpoint somewhere else sets MAPSAM2_CHECKPOINT and lets
 * the worker's own default fall away.
 */
export const DEFAULT_SEG_CONFIG: SegConfig = {
  checkpointPath: '/content/drive/MyDrive/vma_mapsam2_cache/models/epoch_010.pth',
  mapsam2Dir: '/content/MapSAM2',
  priorPath: '',
  encoder: 'vit_s',
  useTextMask: false,
  useWatershed: true,
};

/**
 * With a validated OCR run or colour-block prior the model runs LoRA-prompted;
 * without either it falls back to automatic mode. The worker builds the same
 * conditional command, so prior-only jobs must remain prompted here too.
 */
export function buildSegCommand(
  mapId: string | null | undefined,
  ocrRunId: string | null | undefined,
  cfg: SegConfig
): string {
  if (!mapId) return '';
  const hasOcr = !!ocrRunId;
  const hasPrior = !!cfg.priorPath;
  const hasPrompts = hasOcr || hasPrior;
  return [
    `python work/MapSAM2/inference_tiles_as_video.py`,
    `  --map-id ${mapId}`,
    `  --checkpoint ${cfg.checkpointPath}`,
    `  --encoder ${cfg.encoder}`,
    hasPrompts ? `  --lora --mapsam2-dir ${cfg.mapsam2Dir}` : null,
    hasPrompts ? `  --mode prompted` : `  --mode automatic`,
    hasOcr ? `  --ocr-run-id ${ocrRunId}` : null,
    hasPrior ? `  --prior ${cfg.priorPath}` : null,
    `  --tile-size 1024 --overlap 128`,
    cfg.useTextMask ? `  --text-mask` : null,
    cfg.useWatershed ? `  --watershed` : null,
    `  --device cuda`,
    `  --out-json footprints.json --preview --write-supabase`,
  ]
    .filter(Boolean)
    .join(' \\\n');
}

const segKey = (mapId: string) => `digitalize-seg-${mapId}`;

/** `base` with any stored MapSAM2 config applied over it. */
export function loadSegConfig(mapId: string, base: SegConfig = DEFAULT_SEG_CONFIG): SegConfig {
  const data = readJson<Partial<SegConfig> | null>(segKey(mapId), null);
  if (!data) return { ...base };
  return {
    ...base,
    ...(data.checkpointPath ? { checkpointPath: data.checkpointPath } : {}),
    ...(data.mapsam2Dir ? { mapsam2Dir: data.mapsam2Dir } : {}),
    ...(typeof data.priorPath === 'string' ? { priorPath: data.priorPath } : {}),
    ...(data.encoder ? { encoder: data.encoder } : {}),
    ...(typeof data.useTextMask === 'boolean' ? { useTextMask: data.useTextMask } : {}),
    ...(typeof data.useWatershed === 'boolean' ? { useWatershed: data.useWatershed } : {}),
  };
}

export function saveSegConfig(mapId: string, cfg: SegConfig): void {
  writeJson(segKey(mapId), cfg);
}
