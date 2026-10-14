"""Run every offline Python self-check in the repo, and fail if one is not listed.

    python3 -m pip install -r work/seg-requirements-cpu.txt
    python3 scripts/run_selfchecks.py

Each check is an assert-based script that needs no network, no secrets, no GPU and no
data files. CI runs this file as the `python` job. A check that cannot run there goes in
SKIP with its reason, so a new self-check is either run or skipped on purpose.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SC = ["--self-check"]

RUN = {
    "scripts/check_workspace_layout.py": SC,
    "scripts/lib/georef_annotation.py": [],
    "scripts/tonkin/tonkin_georef.py": ["selfcheck"],
    "work/MapSAM2/to_sam2_seeds.py": SC,
    "work/analysis/district4/georef_error.py": SC,
    "work/analysis/district4/metrics.py": SC,
    "work/analysis/district4/river_full_map.py": SC,
    "work/analysis/district4/series.py": ["--demo"],
    "work/analysis/district4/sheet_panels.py": SC,
    "work/core/vma_core/georef.py": [],
    "work/core/vma_core/test_core.py": [],
    "work/image-processing/experiments/place-links/build.py": SC,
    "work/image-processing/experiments/place-links/confirm.py": SC,
    "work/image-processing/experiments/place-links/review_items.py": SC,
    "work/image-processing/experiments/river-reference/qgis.py": ["selfcheck"],
    "work/image-processing/experiments/river-reference/score.py": ["--selfcheck"],
    "work/image-processing/experiments/then-now/review.py": SC,
    "work/image-processing/scripts/clean_blocks.py": SC,
    "work/image-processing/scripts/colour_blocks.py": SC,
    "work/image-processing/scripts/landmarks_1882.py": SC,
    "work/image-processing/scripts/modern_prior.py": SC,
    "work/image-processing/scripts/name_masks.py": SC,
    "work/image-processing/scripts/name_today.py": SC,
    "work/image-processing/scripts/regularize_blocks.py": SC,
    "work/image-processing/scripts/river_pass.py": SC,
    "work/image-processing/scripts/road_pass.py": SC,
    "work/image-processing/scripts/seg_eval.py": SC,
    "work/image-processing/scripts/seg_gemini.py": SC,
    "work/image-processing/scripts/sheet_features.py": SC,
    "work/image-processing/scripts/sheet_register.py": SC,
    "work/image-processing/scripts/then_now_blocks.py": SC,
    "work/ocr/scripts/audit_run.py": SC,
    "work/ocr/scripts/dictionary.py": SC,
    "work/ocr/scripts/eval_metrics.py": [],
    "work/ocr/scripts/iiif_tiles.py": SC,
    "work/ocr/scripts/join_labels.py": SC,
    "work/ocr/scripts/labels.py": [],
    "work/ocr/scripts/oneoff/backfill_full800.py": SC,
    "work/ocr/scripts/oneoff/fix_info_scalefactors.py": SC,
    "work/ocr/scripts/review_patterns.py": SC,
    "work/ocr/scripts/test_dedup_labels.py": [],
    "work/ocr/scripts/test_ensemble.py": [],
    "work/ocr/scripts/test_exclude_printed.py": [],
    "work/ocr/scripts/test_grid_offset.py": [],
    "work/ocr/scripts/test_legend_blocks.py": [],
    "work/ocr/scripts/test_legend_lines.py": [],
    "work/ocr/scripts/test_prompt_plumbing.py": [],
    "work/ocr/scripts/test_review_figs.py": [],
    "work/ocr/scripts/test_tile_cache.py": [],
    "work/review-kit/review_page.py": SC,
    "work/review-kit/review_record.py": [],
    "work/review-kit/review_sync.py": SC,
    "work/worker/vma_worker.py": SC,
}
RUN["work/ocr/scripts/ocr.py"] = ["self-check"]

SKIP = {
    "scripts/l7014/l7014_autoplace.py": "needs GDAL (osgeo), which pip cannot install",
    "scripts/l7014/l7014_hand.py": "needs GDAL (osgeo), which pip cannot install",
    "scripts/l7014/l7014_seams.py": "needs GDAL (osgeo), which pip cannot install",
    "scripts/l7014/paper_fault_injection.py": "needs GDAL (osgeo), which pip cannot install",
    "scripts/l7014/test_l7014_gcp.py": "needs GDAL (osgeo), which pip cannot install",
    "scripts/vn1971/common.py": "needs GDAL (osgeo), which pip cannot install",
    "work/ocr/scripts/local_vision.py": "reads drawn digits with the tesseract binary; its answer changes with the tesseract version",
    "work/MapSAM2/inference_tiles_as_video.py": "needs torch (a GPU stack)",
    "work/core/vma_core/iiif.py": "a package module; its check runs through work/ocr/scripts/iiif_tiles.py",
    "work/analysis/district4/river_align.py": "reads rasters that river_full_map.py writes under /tmp",
}

FOUND = re.compile(r'^\s*def (_?self_?check|_demo)\(|"--self-?check"', re.M)


def discover():
    skip_dirs = {".venv", "node_modules", ".git", ".claude", ".svelte-kit"}
    for p in sorted(ROOT.rglob("*.py")):
        rel = p.relative_to(ROOT)
        if skip_dirs & set(rel.parts) or rel.as_posix() == "scripts/run_selfchecks.py":
            continue
        if p.name.startswith("test_") or FOUND.search(p.read_text(errors="replace")):
            yield rel.as_posix()


def main():
    listed = RUN.keys() | SKIP.keys()
    errors = [f"not listed in RUN or SKIP: {f}" for f in discover() if f not in listed]
    errors += [f"listed but missing: {f}" for f in sorted(listed) if not (ROOT / f).exists()]
    for f, args in RUN.items():
        t = time.time()
        try:
            # The test_*.py files read sibling files by bare name, so they run from their own folder.
            cwd = (ROOT / f).parent if Path(f).name.startswith("test_") else ROOT
            r = subprocess.run([sys.executable, str(ROOT / f), *args], cwd=cwd, capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=300)
            ok, out = r.returncode == 0, r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            ok, out = False, "timed out after 300 s"
        print(f"{'ok  ' if ok else 'FAIL'} {time.time() - t:5.1f}s  {f}", flush=True)
        if not ok:
            print("\n".join("      " + line for line in out.strip().splitlines()[-15:]))
            errors.append(f"failed: {f}")
    print(f"\n{len(RUN) - sum(e.startswith('failed') for e in errors)} of {len(RUN)} ran clean, {len(SKIP)} skipped.")
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
