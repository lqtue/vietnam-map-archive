# VMA L7014 verification artifacts — local staging package

This is a local, unpublished staging package for the L7014 verification results. It
contains derived geometry, source inventory, seam and datum tables, regeneration logs,
and cached georeference inputs. It contains no source scans, COGs, tiles, DOI, or Zenodo
deposition metadata.

The run provenance and exact commands are in `regen/REGEN.md`; the package was assembled
from the ignored `work/l7014/` outputs described there. Verify every file with:

```text
shasum -a 256 -c SHA256SUMS
```

The recorded run used commit `7ee5d947303bdc9183ae8fffc2290bd88ea861ec` plus the source
changes identified in `regen/REGEN.md`. This package is not itself a publication record.
