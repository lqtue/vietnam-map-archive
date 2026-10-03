# Work directory guide

Working files follow the [system model](../docs/model-layout.md): source evidence feeds holdings,
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
| Outside the model         | [Worker instructions](CLAUDE.md), [pipeline commands](../docs/pipelines.md), local execution logs                                                       |
| Historical material       | [Archive](archive/README.md)                                                                                                                            |

## Image processing is consolidated

[image-processing/](image-processing/README.md) physically holds river and segmentation experiments
in `experiments/`, generated run outputs in `results/`, and execution logs in `logs/`.
Its [local catalog](image-processing/catalog.html) lists saved settings and links to result files.
Regenerate it after new runs:

```sh
python3 work/image-processing/build_catalog.py
```

Code and the Python environment remain in `ocr/` and `MapSAM2/`. Old analysis experiment paths,
`ocr/outputs`, `ocr/logs` and `vectorize` are compatibility symlinks to the consolidated locations.
Use the physical paths for new work; existing pipeline commands continue to use the links.

## Keep evidence and outputs distinct

Gitignored outputs, source scans, caches and environments are local and may be absent in a fresh
checkout. Untracked files may also be new work; check [.gitignore](../.gitignore) before committing.
Keep reproduction scripts, provenance, review decisions and source-pixel definitions with the
experiment. Preserve UUIDs and run IDs used by database rows. Keep finished work in `archive/`.

Declare a new working area in [workspace-model.json](../docs/workspace-model.json), add its purpose
and entry command to a README, and link it from the appropriate guide. Record dated findings in
[journals](../docs/journals/README.md) and tasks in the [roadmap](../docs/ROADMAP.md).
