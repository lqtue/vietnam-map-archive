# Image processing experiments

Layer 3 readings in the [system model](../../../docs/model-layout.md).
[Image processing workspace](../README.md).

| Experiment                    | Entry point                                             | Contents                                                              |
| ----------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------- |
| 1882 river pilot              | [river-1882](river-1882/README.md)                      | Source-pixel crop definitions, water controls and tracing diagnostics |
| Paired 1882/1898 river study  | [river-1882-1898](river-1882-1898/README.md)            | Scripts, pinned crops and pixel comparisons                           |
| September segmentation review | [segmentation-20260919](segmentation-20260919/INDEX.md) | Review exports, figures and superseded evidence                       |
| Modern overlays               | `modern-overlays/`                                      | Local image overlays under `out/`                                     |
| River reference tools         | [river-reference](river-reference/README.md) | Blind-window registry, point labels, traces and scorer; local images under `crops/` |
| OSM warp evidence | [osm-warp](osm-warp/README.md) | Local retained geometry and figures; follow-up deferred |

Reference tools, point labels and traces are versioned. The images under `crops/`,
modern-overlay outputs under `out/`, OSM-warp outputs and segmentation images are local
and may be absent after a checkout. The September review's `_superseded/` material is retained as historical evidence.
Its old next-step list describes that date; the [roadmap](../../../docs/ROADMAP.md) owns current tasks.
