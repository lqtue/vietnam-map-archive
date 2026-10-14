# scripts/

Commands that act on the live system or build its artifacts. Run them from the repo root
(`node scripts/queue/enqueue_seg.mjs`, `python3 scripts/l7014/l7014_mosaic.py --help`).

**Root** holds the commands wired into npm and CI (`check-bundle.mjs`, `seed-test-db.mjs`,
`mint-worker-key.mjs`, `run_selfchecks.py`, `check_workspace_layout.py`) and the cross-cutting
audit and georeference-write tools (`georef_write.mjs`, `allmaps_*.mjs`, `*_audit.mjs`, ...).

| Folder | What is in it |
|--------|---------------|
| `l7014/` | AMS L7014 series pipeline: mosaic, neatline, autoplace, seams, hand fixes, TTU, metadata; the paper's seam and fault-injection checks |
| `l909/` | AMS L909 series: GeoPDF check, georeference, publish |
| `indochine100k/` | Indochine 1:100,000 grid and georeference |
| `tonkin/` | Tonkin sheet georeference and thin-frame corners |
| `scout/` | Finding sources: scout crawlers, scoring, load to `scout_candidates`, NLV press queries, legend timeline, place reports |
| `queue/` | Enqueue worker jobs (OCR, layout, warp, seg) and dedupe OCR rows |
| `gen/` | Generators: i18n, hero media, changelog shots, system graph, paper render, md to PDF |
| `lib/` | Shared modules the scripts import |
| `oneoff/` | Dated fixes and backfills, kept as a record |
| `vn1971/` | 1971 provincial atlas grid georeferences |

Scout runs write their data files (`scout_all_<ts>.json`, `scout_review.csv`) to `scripts/`
itself; they are gitignored.
