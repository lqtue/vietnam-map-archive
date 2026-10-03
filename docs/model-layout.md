# Where files belong in the system model

The layers and object names come from [Knowledge system §9](knowledge-system-plan.md#9-open-work-by-layer).
The [workspace mapping](workspace-model.json) declares the primary responsibility of documentation
and working folders. It records existing storage; it does not create database objects or another task tracker.
Open work stays in [ROADMAP](ROADMAP.md).

| Model layer               | Working material                                                                                                                        | Documentation                                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Sources and surveys       | [Rights and sources](../work/research/README.md)                                                                                        | [Survey note](research/allmaps-series-note.md)                                                                 |
| Holdings                  | Scan and tile datasets beside their series; shared operator code                                                                        | [Sheet preparation](digitalize-guide.md), [catalog operations](admin-tooling.md)                               |
| Placement                 | [Indochine](../work/indochine-100k/), [Tonkin](../work/tonkin/), local L7014 builds, [Saigon controls](../work/analysis/saigon6/)       | [Review procedure](journals/260930-series-georef-review-loop.md)                                               |
| Readings                  | [OCR](../work/ocr/README.md), [SAM2](../work/MapSAM2/VMA_SETUP.md), [image experiments and results](../work/image-processing/README.md) | [Processing record](research/image-processing-record.md), [river research](research/river-reconstruction.md)   |
| Entities and vocabularies | [Doling street-name data](../work/research/doling/SOURCE.md)                                                                            | [Knowledge model](knowledge-system-plan.md)                                                                    |
| Assertions and studies    | [District 4](../work/analysis/district4/README.md), [deposit preparation](../work/research/zenodo/README.md)                            | [Paper](paper/README.md), [research records](research/README.md), [journals](journals/README.md)               |
| Surfaces                  | [Prototypes](../work/proto/), [copy](../work/copy/)                                                                                     | [User guide](user-guide.md), [Search](search-plan.md), [Walk](walk-plan.md), [design system](design-system.md) |
| Outside the model         | [Worker](../work/worker/), catalog builder and execution logs                                                                           | Engineering references in the [docs guide](README.md)                                                          |

A folder may span layers: District 4 includes placement diagnostics, while the image processing
results include modern reference inputs. Keep each run's input identity and coordinate frame;
its folder's primary responsibility does not replace that provenance.

## Storage and compatibility

The physical image-processing workspace contains `experiments/`, local `results/` and local `logs/`.
Reusable OCR code and its environment remain at `work/ocr/`; SAM2 remains at `work/MapSAM2/`.
Studies stay at `work/analysis/`, source-derived material at `work/research/`, and surfaces at
`work/proto/` and `work/copy/`. Finished or obsolete material belongs in `work/archive/`.

Research narratives live at `docs/research/`, dated records at `docs/journals/`, and manuscript
sources at `docs/paper/`. Shared engineering references, model documents, plans and the tracker keep
their established canonical names. `docs/archive/` and `roadmap-record.md` remain frozen.

Older image experiment paths, `work/ocr/outputs`, `work/ocr/logs`, `work/vectorize`, and the five
research record paths at the docs root are relative compatibility symlinks. New references should
use the physical locations. These links preserve existing scripts and historical citations;
they are not duplicate stores. Private files remain gitignored and are never indexed.

## Adding or maintaining material

Choose a primary layer from the table, then put code, inputs, outputs and study narrative in their
appropriate existing homes. Declare a new working area or reference in `workspace-model.json`.
Keep one authoritative copy. Name an experiment for its subject and an OCR run for its timestamp
and method; retain map UUID and run ID as provenance. Never infer review approval from a filename.

Check the layout and refresh the local result catalog from the repository root:

```sh
python3 scripts/check_workspace_layout.py
python3 work/image-processing/build_catalog.py
```

Local artifacts may be missing in a fresh checkout. The layout checker permits their absence but
requires repository entries and compatibility links to resolve appropriately.
