"""Score an `aerial-label-1950` sitting from the exported verdicts (review_sync.py pull) and the points CSV.

    python3 aerial_label_score.py verdicts.jsonl label_points_0028.csv [--second other_verdicts.jsonl]

Prints: n labelled, % unsure, agreement on the repeats (the same point shown twice, same label), per stratum the
share labelled built, and with --second the percent agreement and Cohen's kappa between the two reviewers
(unsure excluded). The strata come only from the points CSV; they never reach the page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from aerial_label import item_id, read_points  # noqa: E402
from review_record import load  # noqa: E402

LABELS = ("built", "open", "unsure")


def labels(path) -> dict[str, str]:
    """item_id -> label, the last line per item, undone ones dropped (load() keeps the last line)."""
    return {i: r["verdicts"]["relation"] for i, r in load(path).items()
            if not r["verdicts"].get("undone") and r["verdicts"].get("relation") in LABELS}


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in ("built", "open"))
    return None if pe == 1 else (po - pe) / (1 - pe)


def score(lab: dict[str, str], points: list[dict], second: dict[str, str] | None = None) -> dict:
    ids = {p["point_id"]: item_id(p["point_id"]) for p in points}
    out: dict = {"n": len(lab), "unsure_pct": None, "repeat": None, "built_by_stratum": {}, "second": None}
    if lab:
        out["unsure_pct"] = 100 * sum(v == "unsure" for v in lab.values()) / len(lab)
    pairs = [(lab[ids[p["point_id"][:-1]]], lab[ids[p["point_id"]]]) for p in points
             if p["stratum"] == "repeat" and ids[p["point_id"]] in lab and ids.get(p["point_id"][:-1]) in lab]
    if pairs:
        out["repeat"] = (sum(a == b for a, b in pairs), len(pairs))
    by: dict[str, list[str]] = {}
    for p in points:
        if p["stratum"] != "repeat" and ids[p["point_id"]] in lab and lab[ids[p["point_id"]]] != "unsure":
            by.setdefault(p["stratum"], []).append(lab[ids[p["point_id"]]])
    out["built_by_stratum"] = {s: (v.count("built"), len(v)) for s, v in sorted(by.items())}
    if second is not None:
        both = [(lab[i], second[i]) for i in lab if i in second and "unsure" not in (lab[i], second[i])]
        a, b = [x for x, _ in both], [y for _, y in both]
        out["second"] = {"n": len(both), "agree_pct": 100 * sum(x == y for x, y in both) / len(both) if both else None,
                         "kappa": kappa(a, b)}
    return out


def show(r: dict) -> None:
    print(f"n labelled: {r['n']}")
    if r["unsure_pct"] is not None:
        print(f"unsure: {r['unsure_pct']:.1f}%")
    if r["repeat"]:
        k, n = r["repeat"]
        print(f"repeat agreement: {k}/{n} = {100 * k / n:.0f}%")
    for s, (b, n) in r["built_by_stratum"].items():
        print(f"built share, {s}: {b}/{n} = {100 * b / n:.0f}%")
    if r["second"]:
        s = r["second"]
        kap = "n/a" if s["kappa"] is None else f"{s['kappa']:.2f}"
        agree = "n/a" if s["agree_pct"] is None else f"{s['agree_pct']:.0f}%"
        print(f"two reviewers (unsure excluded): n={s['n']} agreement {agree} kappa {kap}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("verdicts")
    ap.add_argument("points")
    ap.add_argument("--second")
    a = ap.parse_args()
    show(score(labels(a.verdicts), read_points(a.points), labels(a.second) if a.second else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
