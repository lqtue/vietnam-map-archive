# Image processing workspace

One entry point for text recognition, segmentation, polygon cleanup and image comparisons.
[Work guide](../README.md) · [Pipeline commands](../../docs/pipelines.md).

## Browse the actual results

Run from the repository root:

```sh
python3 work/image-processing/build_catalog.py
```

Open the generated `catalog.html` in a browser. Search by sheet, method, run name, model or prompt.
The table links to result files and reports saved settings, label counts where recorded, and missing
result summaries. `.browse/maps/` gives Finder readable names for the identified Saigon sheets;
other sheets retain their full IDs. `.browse/experiments/` groups the scattered image experiments
under descriptive names. These are relative folder shortcuts, so they use the original files without
copying them. The catalog and shortcuts are local and gitignored; regenerate after new runs.

## Physical layout

| Area                  | Location                                                        | Model responsibility                                                              |
| --------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Experiments           | [experiments](experiments/README.md)                            | Readings: river pilots, paired studies, segmentation reviews and reference images |
| Generated results     | `results/<map-id>/runs/<run-id>/`, `results/<map-id>/colour-*/` | Readings, retaining each run's map and configuration                              |
| Reference inputs      | `results/prior/`, `results/osm/`, `results/annotations/`        | Source and placement inputs used by readings                                      |
| Execution logs        | `logs/`                                                         | Operations                                                                        |
| Catalog and shortcuts | `catalog.html`, `.browse/`                                      | Local navigation, generated from the existing files                               |

Reusable code and environments remain in [OCR](../ocr/README.md) and
[SAM2](../MapSAM2/VMA_SETUP.md). Study-level work remains in
[analysis](../analysis/README.md). Retired vectorize previews live in `../archive/vectorize/`.
The [system model layout](../../docs/model-layout.md) explains the responsibility of each area.

The old `work/analysis` image-experiment paths, `work/ocr/outputs`, `work/ocr/logs`, and
`work/vectorize` are compatibility symlinks to these physical locations. New references should
use the physical paths. Preserve individual runs: methods, source images, coordinate frames and
configurations can differ even on the same sheet.

## Naming new results

Use descriptive run IDs such as `20261002T093000Z-ocr-seq-v1-grid2400-render1024` or
`20261002T093000Z-colour-water-review`. Include a UTC timestamp and the method or question.
Pass the ID through OCR's `--run-id`; choose the same pattern for a segmentation `--out` directory.
Keep exact settings in `run_config.json` or the method's output metadata. Once a run ID has been
used in database rows, preserve it. Record evaluation and approval in the experiment notes rather
than guessing them from `baseline`, `fixed`, `normalized`, or the newest timestamp.

The catalog reads existing local JSON only. It performs no model calls, downloads or database writes.
Metadata failures are listed in `.browse/warnings.txt`; unknown identities and dates remain unknown.
