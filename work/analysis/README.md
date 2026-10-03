# Studies and placement analysis

Study-level measurements and placement diagnostics. [Work guide](../README.md) · [System model](../../docs/model-layout.md).

| Location                                    | Purpose                                                   |
| ------------------------------------------- | --------------------------------------------------------- |
| [District 4](district4/README.md)           | Morphology series and per-sheet georeference diagnostics  |
| [Georeference coverage](georef_coverage.md) | Dated corpus measurements using the District 4 error tool |
| [Saigon controls](saigon6/)                 | Six-sheet control-point picker                            |

River pilots, visual reference crops and segmentation review packs now physically live in
[image-processing/experiments](../image-processing/experiments/README.md). The older `1882/`,
`river_pair/` and `seg-260919/` paths remain compatibility symlinks. River reference tools and
modern overlays use their physical paths in `image-processing/experiments/`; their old
`river_ref/` and `modern_overlay/` links were removed during branch integration.

A measurement describes the images and annotations used at its run date. Recheck those inputs
before treating a recorded result as current. Study assertions must cite the particular run,
image and placement version rather than a folder's newest file.
