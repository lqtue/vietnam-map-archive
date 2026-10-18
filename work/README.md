# Work directory guide

Working files follow the layers in the [Atlas](../docs/ATLAS.md): source evidence feeds holdings,
placement, readings, entities and studies; surfaces display them and operations run the pipelines.
For product and engineering guidance use the [docs guide](../docs/README.md).

## Find the work by layer

| Model layer               | Where to look                                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sources and surveys       | [Research sources and rights](research/README.md): CartoMundi and period newspapers                                                                     |
| Holdings and placement    | [Indochine 1:100,000](indochine-100k/), [Tonkin](tonkin/), local `l7014/`, [Saigon control picker](analysis/saigon6/)                                   |
| Readings                  | [Image processing workspace](image-processing/README.md): experiments, results and the catalog; [OCR code](ocr/README.md); [SAM2](MapSAM2/VMA_SETUP.md) |
| Entities and vocabularies | [Doling source and street-name pairs](research/doling/SOURCE.md)                                                                                        |
| Assertions and studies    | [Analysis guide](analysis/README.md), [Zenodo preparation](research/zenodo/README.md), local generated reports                                          |
| Surfaces                  | [Viewer prototypes](proto/), [copy and translations](copy/)                                                                                             |
| Outside the model         | [Worker guide](worker/README.md), [pipeline index](../docs/guides/pipelines.md), local execution logs                                                       |
| Historical material       | [Archive](archive/README.md)                                                                                                                            |

## Image processing is consolidated

[image-processing/](image-processing/README.md) physically holds river and segmentation experiments
in `experiments/`, generated run outputs in `results/`, and execution logs in `logs/`.
Its [local catalog](image-processing/catalog.html) lists saved settings and links to result files.
Regenerate it after new runs:

```sh
python3 work/image-processing/build_catalog.py
```

Image commands live in [image-processing/scripts](image-processing/scripts/README.md).
OCR commands stay in `ocr/scripts/`. The shared IIIF, georeference and database helpers now live
in [core/](core/README.md) (`vma_core`); `ocr/scripts/{iiif_tiles,scale,supabase_client}.py` are
thin shims over it. The Python environment remains at `ocr/.venv`; the segmentation scripts'
extra packages are listed in `seg-requirements-cpu.txt` and `seg-requirements-gpu.txt`. SAM2 retains its own code in `MapSAM2/`.
The older river-pilot and segmentation-review paths, `ocr/outputs`, `ocr/logs` and `vectorize`
remain temporary compatibility symlinks. Use physical paths for new commands. Remove the
remaining links only after the reference audit in the [1882 plan](../docs/plans/image-processing-1882-plan.md).

## Keep evidence and outputs distinct

Gitignored outputs, source scans, caches and environments are local and may be absent in a fresh
checkout. Untracked files may also be new work; check [.gitignore](../.gitignore) before committing.
Keep reproduction scripts, provenance, review decisions and source-pixel definitions with the
experiment. Preserve UUIDs and run IDs used by database rows. Keep finished work in `archive/`.
Name an experiment for its subject and an OCR run for its timestamp and method. A folder may span
layers; its layer never replaces a run's input identity and coordinate frame. Never infer review
approval from a filename.

Declare a new working area in [workspace-model.json](../docs/workspace-model.json), add its purpose
and entry command to a README, and link it from the appropriate guide. Then refresh the Atlas and
check the layout (CI runs the second):

```sh
python3 scripts/check_workspace_layout.py --write-atlas
python3 scripts/check_workspace_layout.py
``` Record dated findings in
[journals](../docs/journals/README.md) and tasks in the [roadmap](../docs/ROADMAP.md).
