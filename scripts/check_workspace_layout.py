"""Check the declared workspace layout without running pipelines or changing files."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    model = json.loads((ROOT / "docs/workspace-model.json").read_text())
    errors, declared, local = [], set(), set()
    expected = ["sources", "holdings", "placement", "readings", "entities", "studies", "surfaces", "operations"]
    if [layer["key"] for layer in model["layers"]] != expected:
        errors.append("Layer order differs from knowledge-system-plan.md §9")
    for layer in model["layers"]:
        for entry in layer["entries"]:
            path = entry["path"]
            if path in declared:
                errors.append(f"Duplicate primary responsibility: {path}")
            declared.add(path)
            if entry["availability"] == "local":
                local.add(path)
            elif not (ROOT / path).exists():
                errors.append(f"Missing repository entry: {path}")
    for old, target in model["compatibility"].items():
        alias = ROOT / old
        if not alias.is_symlink():
            errors.append(f"Missing compatibility link: {old}")
        elif alias.resolve() != (ROOT / target).resolve():
            errors.append(f"Wrong compatibility target: {old} -> {target}")
        elif target not in local and not alias.exists():
            errors.append(f"Broken compatibility link: {old}")
    for path in model["historical"]:
        if not (ROOT / path).exists():
            errors.append(f"Missing historical store: {path}")
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"Workspace layout verified: {len(declared)} primary entries and {len(model['compatibility'])} compatibility links.")


if __name__ == "__main__":
    main()
