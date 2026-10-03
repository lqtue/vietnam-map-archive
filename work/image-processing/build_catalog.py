"""Build a local browsing view of existing image processing evidence. No pipeline runs."""

import csv
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
OUTPUTS = HERE / "results"
VIEW = HERE / ".browse"
NAMES = {
    "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b": "Saigon 1882 — cadastral plan",
    "20ec4f9a-16bd-4895-a593-40c6ed9c9555": "Saigon 1898 — Bertaux plan",
    "eca788e5-6780-4dca-bf23-7651a1c48aba": "Saigon 1959",
}


def read_object(path, warnings):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
        if isinstance(value, dict):
            return value
        warnings.append(f"{path.relative_to(WORK)}: expected a JSON object")
    except (OSError, ValueError) as exc:
        warnings.append(f"{path.relative_to(WORK)}: {exc}")
    return {}


def shortcut(name, target):
    dest = VIEW / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = os.path.relpath(target, dest.parent)
    if dest.is_symlink() and os.readlink(dest) == expected:
        return
    if dest.is_symlink():
        dest.unlink()
    elif dest.exists():
        raise RuntimeError(f"Refusing to overwrite {dest}")
    dest.symlink_to(expected, target_is_directory=target.is_dir())


def link(path, label):
    url = quote(os.path.relpath(path, HERE), safe="/")
    return f'<a href="{url}">{html.escape(label)}</a>'


def main():
    VIEW.mkdir(exist_ok=True)
    warnings, rows = [], []
    groups = {
        "experiments/1882-river": WORK / "image-processing/experiments/river-1882",
        "experiments/1882-1898-river-comparison": WORK / "image-processing/experiments/river-1882-1898",
        "experiments/segmentation-review-2026-09-19": WORK / "image-processing/experiments/segmentation-20260919",
        "experiments/modern-map-overlays": WORK / "image-processing/experiments/modern-overlays",
        "experiments/river-reference-crops": WORK / "image-processing/experiments/river-reference",
        "experiments/district4-morphology": WORK / "analysis/district4",
        "pipelines/text-recognition-and-colour-segmentation": WORK / "ocr",
        "pipelines/sam2-segmentation": WORK / "MapSAM2",
        "historical/vectorize-previews": WORK / "archive/vectorize",
    }
    for name, target in groups.items():
        if target.exists():
            shortcut(name, target)
    for sheet in sorted(OUTPUTS.iterdir()) if OUTPUTS.exists() else []:
        if not sheet.is_dir() or sheet.name.startswith((".", "_")):
            continue
        is_sheet = bool(re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", sheet.name)) or sheet.name == "unknown"
        if not is_sheet:
            shortcut("shared/" + sheet.name, sheet)
            continue
        name = NAMES.get(sheet.name, "Unidentified sheet — " + sheet.name)
        shortcut("maps/" + name, sheet)
        candidates = list((sheet / "runs").iterdir()) if (sheet / "runs").exists() else []
        candidates += [p for p in sheet.iterdir() if p.is_dir() and p.name != "runs"]
        for run in sorted(candidates):
            if not run.is_dir():
                continue
            config = read_object(run / "run_config.json", warnings)
            result = read_object(run / "all_extractions.json", warnings)
            scout = read_object(run / "scout.json", warnings)
            files = sorted(p.name for p in run.iterdir() if p.is_file())
            polygons = any(p.endswith(".geojson") for p in files) or "segmentation.json" in files
            kind = "OCR" if result else "Polygons" if polygons else "Layout" if scout else "Diagnostic / other"
            count = result.get("n_deduped", len(result["extractions"]) if isinstance(result.get("extractions"), list) else "")
            available = "Merged OCR output present" if result else "Layout output present" if scout else "Polygon files present" if polygons else "No recognized result summary"
            if config.get("n_errors"):
                available += f'; {config["n_errors"]} recorded errors'
            rows.append({
                "sheet": name, "map_id": sheet.name, "kind": kind,
                "run": run.name, "recorded_time": config.get("timestamp", ""),
                "model": config.get("model", result.get("model", "")),
                "prompt": config.get("prompt", result.get("prompt", "")),
                "tile_px": config.get("tile_size", ""), "render_px": config.get("render_size", scout.get("render_size", "")),
                "labels": count, "availability": available,
                "path": str(run.relative_to(WORK)), "files": ", ".join(files),
            })
    fields = ["sheet", "map_id", "kind", "run", "recorded_time", "model", "prompt", "tile_px", "render_px", "labels", "availability", "path", "files"]
    with (VIEW / "runs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    table = []
    for row in rows:
        cells = [html.escape(str(row[k])) for k in fields[:11]]
        run = WORK / row["path"]
        cells[3] = link(run, row["run"])
        artifacts = [link(run / f, f) for f in row["files"].split(", ") if f and not re.match(r"^[\d.]+_[\d.]+_", f)]
        cells.append("<details><summary>Result files</summary>" + "<br>".join(artifacts) + "</details>")
        table.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    nav = " · ".join(link(VIEW / p, p) for p in ["maps", "experiments", "pipelines", "shared", "historical"] if (VIEW / p).exists())
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VMA image processing results</title><style>
body{font:16px system-ui;margin:2rem;color:#222;background:#faf8f3}input{font:inherit;padding:.6rem;width:min(90%,40rem)}
table{border-collapse:collapse;margin-top:1rem;font-size:14px}th,td{padding:.5rem;border:1px solid #ccc;text-align:left;vertical-align:top}
th{background:#e9e4da}a{color:#174f70}summary{cursor:pointer}td:nth-child(2){font-size:11px}tr[hidden]{display:none}
</style><h1>Image processing results</h1>
<p>Search a sheet, method, run name, model or prompt. Saved configurations supply settings; blank cells mean unknown.
Folder names are preserved as evidence. Output availability does not establish completion, quality, approval or database import.</p>
<p>Recorded timestamps may disagree with run names; both are shown. Unidentified sheets retain their full ID.</p>
'''
    page += f'<p>{nav} · {link(VIEW / "runs.csv", "Download run table")}</p>'
    page += '<label for="search">Filter results</label> <input id="search" type="search" placeholder="Try 1882, colour, layout, baseline or seq-v1"><p id="count" role="status"></p>'
    page += '<table><thead><tr>' + ''.join(f'<th scope="col">{html.escape(k.replace("_", " "))}</th>' for k in fields[:11] + ["results"]) + '</tr></thead><tbody>' + ''.join(table) + '</tbody></table>'
    page += '''<script>const rows=[...document.querySelectorAll('tbody tr')];const search=document.querySelector('#search');function filter(){const q=search.value.toLowerCase();let n=0;for(const row of rows){row.hidden=!row.textContent.toLowerCase().includes(q);if(!row.hidden)n++}document.querySelector('#count').textContent=n+' of '+rows.length+' runs'}search.addEventListener('input',filter);filter();</script></html>'''
    (HERE / "catalog.html").write_text(page)
    (VIEW / "warnings.txt").write_text("\n".join(warnings))
    print(f"Indexed {len(rows)} run folders; {len(warnings)} metadata warnings. Open {HERE / 'catalog.html'}")


if __name__ == "__main__":
    main()
