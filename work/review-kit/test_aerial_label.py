"""Tiny test for the aerial-label scorer, with fake verdicts: python3 work/review-kit/test_aerial_label.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aerial_label import item_id  # noqa: E402
from aerial_label_score import kappa, labels, score  # noqa: E402
from review_record import record  # noqa: E402

pts = [{"point_id": f"p{i}", "x": 1, "y": 1, "stratum": "A" if i < 3 else "B"} for i in range(6)]
pts.append({"point_id": "p0r", "x": 1, "y": 1, "stratum": "repeat"})
pts.append({"point_id": "p1r", "x": 1, "y": 1, "stratum": "repeat"})
assert len({item_id(p["point_id"]) for p in pts}) == len(pts) and not item_id("p0r").endswith("r")


def write(path, vals):
    for pid, v in vals.items():
        record(path, task="aerial-label-1950", item_id=item_id(pid), bound="b", reviewer="x", order_idx=0,
               shown_at=1.0, decided_at=2.0, proposal_shown=False, verdicts={"arm": "nocand", "relation": v})


with tempfile.TemporaryDirectory() as td:
    one, two = Path(td) / "1.jsonl", Path(td) / "2.jsonl"
    write(one, {"p0": "built", "p1": "open", "p2": "unsure", "p3": "built", "p4": "built", "p5": "open",
                "p0r": "built", "p1r": "built"})
    write(two, {"p0": "built", "p1": "open", "p2": "built", "p3": "open", "p4": "built", "p5": "open"})
    r = score(labels(one), pts, labels(two))
    assert r["n"] == 8 and r["repeat"] == (1, 2), r
    assert round(r["unsure_pct"], 1) == 12.5
    assert r["built_by_stratum"] == {"A": (1, 2), "B": (2, 3)}, r["built_by_stratum"]
    # unsure excluded: p0,p1,p3,p4,p5 -> agree on 4 of 5 = 80%
    assert r["second"]["n"] == 5 and r["second"]["agree_pct"] == 80.0
    assert abs(r["second"]["kappa"] - 0.6154) < 1e-3, r["second"]
assert kappa(["built", "open"], ["built", "open"]) == 1.0
print("aerial_label test OK")
