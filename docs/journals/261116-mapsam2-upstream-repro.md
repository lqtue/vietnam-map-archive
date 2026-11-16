# MapSAM2 upstream repro (step 0) — 2026-11-16

*Draft. The pass bar below was written before the first training run.*

## Pass bar (set before seeing any number)

The paper's Table 1 gives MapSAM2 railway 10-shot IoU 73.0, and Table 2 gives 56.7 without memory
attention. We call the run **reproduces** if our printed `IOU` x 100 is closer to 73.0 than to 56.7,
that is at least 64.9. Below that it **does not reproduce**. This is one run, one seed (upstream
fixes seed 42, but `cudnn.benchmark = True` makes it non-deterministic anyway), so a result
within a few points of the bar is a weak verdict either way.
