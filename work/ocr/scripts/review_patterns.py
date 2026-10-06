#!/usr/bin/env python3
"""What a human reviewer's verdicts on one sheet's OCR say about the next sheet.

    python work/ocr/scripts/review_patterns.py                    # the 1882 sheet
    python work/ocr/scripts/review_patterns.py --map <uuid>       # another sheet
    python work/ocr/scripts/review_patterns.py --self-check       # no DB, asserts only

Reads `ocr_labels` for one map (PostgREST, read-only), prints a report and writes
`work/ocr/outputs/<map>/review_patterns.json`. Sections: (a) verdict mix and whether
confidence predicts rejection, (b) raw-vs-effective text diffs, (c) category
confusion, (d) why rows were rejected, (e) vocabulary the dictionary and
LABEL_PREFIXES lack, (f) the sparse layout of road and river names, (g) self-check.

Three facts about the data shape every number here, and none of them is visible in
the table:

* **A rejection is usually not an error.** Several runs read the same sheet and the
  reviewer validates one reading per label, so most rejected rows are the *other
  run's copy* of a validated label. Section (d) sorts every rejection into dup /
  box-off / part / text-wrong / adjacent / orphan before (a) asks whether
  confidence predicts anything; only the last four are wrong readings.
* **Validated means `review_status='validated'`, never `text_corrected IS NOT NULL`.**
  The effective text is `coalesce(text_corrected, text)`; null means accepted as is.
* **Boxes the reviewer touched are overwritten in place**, so there is no original
  box. `label_w/label_h` (the unrotated text rectangle) exist on a minority of rows,
  almost all of them ones a human drew or edited; every layout figure says how many
  rows it stands on and which of them carry it.

A `manual` row is a box the human added because OCR missed it: its raw `text` is
empty and its `category` is the review UI's default `other`, so it is held out of the
confusion matrix and its category is recovered from its group or its generic word.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_metrics import box_iou, char_sim, has_diacritic  # noqa: E402
from labels import LABEL_PREFIXES, fold, label_core, name_key  # noqa: E402

DEFAULT_MAP = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"  # 1882 Plan Cadastral de Saigon
DEFAULT_MPP = 0.3416  # metres per source pixel, 1882
OUT_ROOT = Path(__file__).resolve().parents[1] / "outputs"

NAME_CATS = ("street", "hydrology")
# The generic word that makes an uncategorised manual box a road or a river.
HYDRO_GENERICS = {"arroyo", "rach", "kinh", "song", "canal", "riviere", "fleuve"}
NOT_ROAD_GENERICS = {"place", "cong truong", "hameau", "ap", "xom", "cour", "cau", "ben", "pont"}
ABBREVIATIONS = {  # printed or typed short forms -> long form, folded
    "r": "rue", "bd": "boulevard", "bld": "boulevard", "boul": "boulevard", "st": "saint",
    "ste": "sainte", "vge": "village", "rte": "route", "av": "avenue", "pl": "place",
    "imp": "impasse", "q": "quai", "ch": "chemin",
}
NUM_RE = re.compile(r"^\s*(n\s*[°º˚o]?\.?|no\.?|num[eé]ro)\s*\d+\w*\s*$", re.I)
NUM_TAIL_RE = re.compile(r"\s+(n\s*[°º˚o]?\.?|no\.?)\s*\d+.*$", re.I)


# --------------------------------------------------------------------- small maths
def pctile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def rnd(x, n=2):
    return None if x is None else round(x, n)


def dist_summary(xs: list[float], n=1) -> dict:
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "min": rnd(min(xs), n), "p10": rnd(pctile(xs, 10), n),
            "p25": rnd(pctile(xs, 25), n), "median": rnd(median(xs), n),
            "p75": rnd(pctile(xs, 75), n), "p90": rnd(pctile(xs, 90), n), "p95": rnd(pctile(xs, 95), n),
            "p99": rnd(pctile(xs, 99), n), "max": rnd(max(xs), n)}


def axial_diff(a: float, b: float) -> float:
    """Smallest difference between two text angles, which repeat every 180 degrees."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


def axial_mean(angles: list[float]) -> float:
    s = sum(math.sin(math.radians(2 * a)) for a in angles)
    c = sum(math.cos(math.radians(2 * a)) for a in angles)
    return math.degrees(math.atan2(s, c)) / 2


def rot_bucket(deg: float | None) -> str:
    if deg is None:
        return "null"
    a = abs(deg)
    if a == 0:
        return "0 exactly"
    return "0-15" if a < 15 else "15-35" if a < 35 else "35-55" if a < 55 else "55-90"


def conf_bucket(c: float | None) -> str:
    if c is None:
        return "null"
    c = round(c, 2)
    return "<0.8" if c < 0.8 else "0.8-0.9" if c < 0.9 else "0.9-0.95" if c < 0.95 else "0.95-<1" if c < 1 else "1.0"


# --------------------------------------------------------------------------- row model
def eff_text(r: dict) -> str:
    t = r.get("text_corrected")
    return (t if t is not None else r.get("text")) or ""


def is_number_only(text: str) -> bool:
    return bool(NUM_RE.match(text or ""))


def strip_number(text: str) -> str:
    return NUM_TAIL_RE.sub("", text or "").strip()


def first_token(text: str) -> str:
    toks = fold(text).replace("'", " ").split()
    return toks[0].strip(".,;:") if toks else ""


def prefix_category(text: str) -> str | None:
    """street / hydrology from the generic word, or None. Used only when a manual
    box arrives with the review UI's default `other` and no group to inherit from."""
    t = first_token(text)
    if t in HYDRO_GENERICS:
        return "hydrology"
    folded = {fold(p) for p in LABEL_PREFIXES} - NOT_ROAD_GENERICS - HYDRO_GENERICS
    if t in folded or t in ("r", "bd", "bld", "av", "rte", "q"):
        return "street"
    return None


class Sheet:
    """Rows of one map with the derived fields every section shares."""

    def __init__(self, rows: list[dict], mpp: float, sheet_w=None, sheet_h=None):
        self.rows, self.mpp = rows, mpp
        self.by_id = {r["id"]: r for r in rows}
        self.groups = [r for r in rows if r.get("is_text_group")]
        self.members: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            gid = r.get("text_group_id")
            if gid and not r.get("is_text_group"):
                self.members[gid].append(r)
        for g in self.members.values():
            g.sort(key=lambda m: (m.get("text_group_order") is None, m.get("text_group_order") or 0))
        self.sheet_w = sheet_w or max((r["tile_x"] + r["tile_w"] for r in rows if r.get("tile_w")), default=None)
        self.sheet_h = sheet_h or max((r["tile_y"] + r["tile_h"] for r in rows if r.get("tile_w")), default=None)
        self.reassigned = Counter()
        for r in rows:
            r["_eff_text"] = eff_text(r)
            r["_eff_cat"] = self._eff_cat(r)
            r["_manual"] = r.get("model") == "manual"
        self.V = [r for r in rows if r["review_status"] == "validated" and not r.get("is_text_group")]
        self.model_rows = [r for r in rows if not r["_manual"] and not r.get("is_text_group")]

    def _eff_cat(self, r: dict) -> str | None:
        c = r.get("category_corrected") or r.get("category")
        if c not in (None, "", "other"):
            return c
        gid = r.get("text_group_id")
        if gid and gid in self.by_id:
            g = self.by_id[gid]
            gc = g.get("category_corrected") or g.get("category")
            if gc not in (None, "", "other"):
                self.reassigned["from group"] += 1
                return gc
        if r.get("model") == "manual":
            pc = prefix_category(eff_text(r))
            if pc:
                self.reassigned["from generic word"] += 1
                return pc
        return c or "other"

    def centre(self, r: dict) -> tuple[float, float]:
        return r["global_x"] + r["global_w"] / 2, r["global_y"] + r["global_h"] / 2

    def box(self, r: dict) -> tuple[float, float, float, float]:
        return r["global_x"], r["global_y"], r["global_w"], r["global_h"]


def oriented_dims(r: dict) -> tuple[float, float, str] | None:
    """(long side, short side, source) of the text rectangle, in source px.

    `label_w/label_h` are the unrotated rectangle and exist only on rows a human
    edited. Otherwise `global_w/h` is the axis-aligned box of the rotated
    rectangle: usable as-is near 0 or 90 degrees and solvable between, except near
    45 degrees where the two equations collapse into one and most streets live.
    """
    lw, lh = r.get("label_w"), r.get("label_h")
    if lw and lh:
        return max(lw, lh), min(lw, lh), "label"
    gw, gh = r.get("global_w"), r.get("global_h")
    if not gw or not gh:
        return None
    th = math.radians(r.get("rotation_deg") or 0)
    c, s = abs(math.cos(th)), abs(math.sin(th))
    if s < 0.1:
        return max(gw, gh), min(gw, gh), "box"
    if c < 0.1:
        return max(gw, gh), min(gw, gh), "box"
    det = c * c - s * s
    if abs(det) > 0.3:
        a, b = (c * gw - s * gh) / det, (c * gh - s * gw) / det
        if a > 0 and b > 0:
            return max(a, b), min(a, b), "solved"
    return None


def nchars(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def spacing(r: dict) -> tuple[float, str] | None:
    """Letter advance in letter heights: long side / characters / short side."""
    d = oriented_dims(r)
    n = nchars(r["_eff_text"])
    if not d or n < 3 or d[1] <= 0 or is_number_only(r["_eff_text"]):
        return None
    return d[0] / n / d[1], d[2]


# ------------------------------------------------------------------------- diff classes
def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold(s))


def _num_norm(s: str) -> str:
    s = fold(s)
    s = re.sub(r"\bn\s*[°º˚o]?\.?\s*(?=\d)", "no ", s)
    s = re.sub(r"\bno\.?\s*(?=\d)", "no ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _expand(s: str) -> str:
    toks = re.sub(r"[^a-z0-9' ]+", " ", fold(s).replace(".", " ")).split()
    return " ".join(ABBREVIATIONS.get(t, t) for t in toks)


def _is_subsequence(small: str, big: str) -> bool:
    """Are all of `small`'s words in `big`, in order? 'Rue Thu duc' in 'Rue de Thu duc No. 11'."""
    s, b = fold(small).split(), iter(fold(big).split())
    return bool(s) and all(w in b for w in s)


def classify_diff(raw: str, eff: str) -> str:
    """One label for how a human changed the model's text. First match wins, so a
    row that changed in two ways is filed under the more mechanical one."""
    raw, eff = (raw or "").strip(), (eff or "").strip()
    if raw == eff:
        return "same"
    if not raw:
        return "typed (model empty)"
    if raw.casefold() == eff.casefold():
        return "case"
    if fold(raw) == fold(eff):
        return "diacritic/accent"
    if _squash(raw) == _squash(eff):
        return "punctuation/spacing"
    if _num_norm(raw) == _num_norm(eff):
        return "numeral (N°/No.)"
    if _expand(raw) == _expand(eff):
        return "abbreviation"
    if label_core(fold(raw)) == label_core(fold(eff)) and first_token(raw) != first_token(eff):
        return "generic word swap"
    if _is_subsequence(raw, eff):
        return "extended (human added words)"
    if _is_subsequence(eff, raw):
        return "truncated (human trimmed words)"
    return "wrong word" if char_sim(fold(raw), fold(eff)) >= 0.6 else "rewrite"


# --------------------------------------------------------------------------- (a)+(d)
SIM_DUP = 0.8


def covered_by(r: dict, v: dict) -> float:
    """Share of r's own box that lies inside v's box. IoU is the wrong test for a
    diagonal label: its axis-aligned box is mostly empty paper, so a fragment that
    sits squarely on the printed name overlaps it by a few percent of the union."""
    x0, y0 = max(r["global_x"], v["global_x"]), max(r["global_y"], v["global_y"])
    x1 = min(r["global_x"] + r["global_w"], v["global_x"] + v["global_w"])
    y1 = min(r["global_y"] + r["global_h"], v["global_y"] + v["global_h"])
    area = r["global_w"] * r["global_h"]
    return max(0.0, x1 - x0) * max(0.0, y1 - y0) / area if area > 0 else 0.0


def fragment_kind(text: str, container_text: str) -> str:
    t = (text or "").strip()
    if is_number_only(t):
        return "house number alone"
    if nchars(t) <= 4:
        return "generic/short piece"
    if _is_subsequence(t, container_text):
        return "words of the validated name"
    return "other"


def reject_reason(sh: Sheet, r: dict) -> tuple[str, float | None]:
    """Why a rejected model row is rejected, and the centre distance to its twin.

    Side effect: sets r["_container"] (id of the validated row it sits inside) and
    r["_sub"] for fragments.

    dup        a validated row sits on it (IoU>=0.3) with the same folded text
    part       IoU>=0.3, one text contains the other: a fragment or a superset
    text-wrong IoU>=0.3, different text
    box-off    the same text validated within 500 px or around it, boxes barely overlapping
    fragment   >=50% of its box lies inside a validated box and the text differs:
               the model cut one printed name into pieces, the human drew it whole
    adjacent   overlaps a validated row a little, text unrelated
    orphan     nothing validated near it
    """
    rt = fold(r["text"] or "")
    best, best_iou = None, 0.0
    for v in sh.V:
        i = box_iou(sh.box(r), sh.box(v))
        if i > best_iou:
            best, best_iou = v, i
    cx, cy = sh.centre(r)

    def cdist(v):
        vx, vy = sh.centre(v)
        return math.hypot(cx - vx, cy - vy)

    if best is not None and best_iou >= 0.3:
        vt = fold(best["_eff_text"])
        if char_sim(rt, vt) >= SIM_DUP:
            return "dup", cdist(best)
        if rt and vt and (_squash(rt) in _squash(vt) or _squash(vt) in _squash(rt)):
            return "part", cdist(best)
        return "text-wrong", cdist(best)
    twins = [v for v in sh.V if (cdist(v) < 500 or covered_by(r, v) >= 0.5)
             and char_sim(rt, fold(v["_eff_text"])) >= SIM_DUP]
    if twins:
        return "box-off", min(cdist(v) for v in twins)
    inside = [(covered_by(r, v), v) for v in sh.V]
    cov, cont = max(inside, key=lambda t: t[0], default=(0.0, None))
    if cont is not None and cov >= 0.5:
        r["_container"], r["_sub"] = cont["id"], fragment_kind(r["text"], cont["_eff_text"])
        return "fragment", cdist(cont)
    if best is not None and best_iou > 0:
        return "adjacent", cdist(best)
    return "orphan", None


def tile_edge(sh: Sheet, r: dict, margin=40) -> bool | None:
    """Does the box touch an internal tile edge? None where the run stored no tile."""
    if not r.get("tile_w"):
        return None
    x0, y0, x1, y1 = r["global_x"], r["global_y"], r["global_x"] + r["global_w"], r["global_y"] + r["global_h"]
    tx0, ty0, tx1, ty1 = r["tile_x"], r["tile_y"], r["tile_x"] + r["tile_w"], r["tile_y"] + r["tile_h"]
    hit = (tx0 > 0 and x0 <= tx0 + margin) or (ty0 > 0 and y0 <= ty0 + margin)
    hit = hit or (sh.sheet_w and tx1 < sh.sheet_w - 1 and x1 >= tx1 - margin)
    hit = hit or (sh.sheet_h and ty1 < sh.sheet_h - 1 and y1 >= ty1 - margin)
    return bool(hit)


def section_a_d(sh: Sheet) -> tuple[dict, dict]:
    a: dict = {}
    allr = [r for r in sh.rows if not r.get("is_text_group")]
    a["rows_by_status"] = dict(Counter(r["review_status"] for r in sh.rows))
    a["rows_by_status_excl_groups"] = dict(Counter(r["review_status"] for r in allr))
    a["group_rows"] = len(sh.groups)
    a["by_run"] = {k: dict(v) for k, v in _cross(allr, lambda r: r["run_id"]).items()}
    a["by_category_effective"] = {k: dict(v) for k, v in _cross(allr, lambda r: r["_eff_cat"]).items()}
    a["by_confidence_bucket"] = {k: dict(v) for k, v in
                                 _cross([r for r in allr if not r["_manual"]], lambda r: conf_bucket(r.get("confidence"))).items()}

    # why each rejected model row was rejected
    rej, reasons = [r for r in sh.model_rows if r["review_status"] == "rejected"], {}
    for r in rej:
        reasons[r["id"]] = reject_reason(sh, r)
    d: dict = {"n_rejected_model_rows": len(rej)}
    d["reason_counts"] = dict(Counter(v[0] for v in reasons.values()))
    d["reason_by_run"] = {k: dict(v) for k, v in _cross(rej, lambda r: reasons[r["id"]][0], col=lambda r: r["run_id"]).items()}
    d["dup_centre_distance_px"] = dist_summary([v[1] for v in reasons.values() if v[0] == "dup"])
    d["dup_centre_distance_m"] = dist_summary([v[1] * sh.mpp for v in reasons.values() if v[0] == "dup"])

    def prof(rs):
        areas = [r["global_w"] * r["global_h"] for r in rs]
        mins = [min(r["global_w"], r["global_h"]) for r in rs]
        edge = [tile_edge(sh, r) for r in rs]
        known = [e for e in edge if e is not None]
        return {"n": len(rs), "area_median_px2": rnd(median(areas), 0) if areas else None,
                "min_side_median_px": rnd(median(mins), 0) if mins else None,
                "tile_edge_share": rnd(sum(known) / len(known), 3) if known else None, "tile_edge_known": len(known),
                "confidence_median": rnd(median([r["confidence"] for r in rs if r.get("confidence") is not None]), 3) if rs else None,
                "categories": dict(Counter(r["category"] for r in rs)),
                "chars_median": rnd(median([nchars(r["text"]) for r in rs]), 1) if rs else None}

    d["profile"] = {"validated model rows": prof([r for r in sh.model_rows if r["review_status"] == "validated"])}
    for k in sorted(set(v[0] for v in reasons.values())):
        d["profile"][f"rejected: {k}"] = prof([r for r in rej if reasons[r["id"]][0] == k])
    orph = [r for r in rej if reasons[r["id"]][0] == "orphan"]
    texts = [(r["text"] or "").strip() for r in orph]
    d["orphan_text_features"] = {
        "n": len(orph),
        "digits_only": sum(bool(re.fullmatch(r"[\d\W]+", t)) for t in texts),
        "under_4_chars": sum(len(t) < 4 for t in texts),
        "all_caps": sum(t.isupper() for t in texts),
        "empty": sum(not t for t in texts),
        "over_60_chars": sum(len(t) > 60 for t in texts),
        "notes_marked_fragment": sum(bool(re.search(r"fragment|continues|part of|spans", r.get("notes") or "", re.I)) for r in orph),
        "examples": [{"text": r["text"], "cat": r["category"], "conf": r["confidence"], "run": r["run_id"]} for r in
                     sorted(orph, key=lambda r: -(r["global_w"] * r["global_h"]))[:25]],
    }
    frag = [r for r in rej if reasons[r["id"]][0] == "fragment"]
    d["fragment_kinds"] = dict(Counter(r["_sub"] for r in frag))
    d["fragment_examples"] = [{"fragment": r["text"], "inside": sh.by_id[r["_container"]]["_eff_text"], "kind": r["_sub"]}
                              for r in frag[:20]]
    per_container = Counter(r["_container"] for r in frag)
    d["fragments_per_validated_box"] = dict(sorted(Counter(per_container.values()).items()))
    d["validated_boxes_with_fragments"] = len(per_container)
    d["part_and_textwrong_examples"] = [
        {"model": r["text"], "validated_twin": _twin_text(sh, r), "reason": reasons[r["id"]][0]}
        for r in rej if reasons[r["id"]][0] in ("part", "text-wrong")][:20]
    for r in rej:
        r["_reason"] = reasons[r["id"]][0]

    # (a) does confidence predict a wrong reading?
    pool = [r for r in sh.model_rows if r["review_status"] in ("validated", "rejected") and r.get("confidence") is not None]
    a["confidence"] = {"pooled": _conf_sweep(pool), "by_run": {}}
    for run in sorted({r["run_id"] for r in pool}):
        sub = [r for r in pool if r["run_id"] == run]
        a["confidence"]["by_run"][run] = _conf_sweep(sub)
    a["confidence_values_by_run"] = {run: dict(Counter(round(r["confidence"], 2) for r in pool if r["run_id"] == run).most_common(8))
                                     for run in sorted({r["run_id"] for r in pool})}
    return a, d


def _twin_text(sh: Sheet, r: dict) -> str:
    v = max(sh.V, key=lambda v: box_iou(sh.box(r), sh.box(v)))
    return v["_eff_text"]


def _cross(rows, key, col=None):
    out: dict = defaultdict(Counter)
    for r in rows:
        out[key(r)][col(r) if col else r["review_status"]] += 1
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def _conf_sweep(rows: list[dict]) -> dict:
    """Flag a row when confidence < t, against three definitions of 'bad':
    a wrong text (text-wrong or part, the only rejections that are a misreading),
    any rejected non-duplicate (adds the fragments and scope rejections), and any
    rejection. Duplicates are good readings that lost to another run's copy, so
    they are left out of the first two populations."""
    def go(bad_fn, pop):
        n_bad = sum(bad_fn(r) for r in pop)
        res = {"n": len(pop), "n_bad": n_bad, "base_rate": rnd(n_bad / len(pop), 3) if pop else None, "cutoffs": []}
        for t in sorted({round(r["confidence"], 2) for r in pop}) + [1.01]:
            fl = [r for r in pop if round(r["confidence"], 2) < t]
            tp = sum(bad_fn(r) for r in fl)
            if not fl:
                continue
            p, rc = tp / len(fl), (tp / n_bad if n_bad else 0)
            res["cutoffs"].append({"flag_below": t, "flagged": len(fl), "precision": rnd(p, 3), "recall": rnd(rc, 3),
                                   "f1": rnd(2 * p * rc / (p + rc), 3) if p + rc else 0})
        best = max(res["cutoffs"], key=lambda c: (c["f1"], -c["flagged"]), default=None)
        res["best_f1"] = best
        # rank statistic: chance that a bad row has lower confidence than a good one
        good = [r["confidence"] for r in pop if not bad_fn(r)]
        bad = [r["confidence"] for r in pop if bad_fn(r)]
        if good and bad:
            wins = sum((b < g) + 0.5 * (b == g) for b in bad for g in good)
            res["auc_low_conf_means_bad"] = rnd(wins / (len(bad) * len(good)), 3)
        return res

    ok = lambda r: r["review_status"] == "validated"  # noqa: E731
    keep = [r for r in rows if ok(r) or r.get("_reason") != "dup"]
    wrong = [r for r in rows if ok(r) or r.get("_reason") in ("text-wrong", "part")]
    isrej = lambda r: r["review_status"] == "rejected"  # noqa: E731
    return {"vs_wrong_text_only": go(isrej, wrong),
            "vs_rejected_non_dup": go(isrej, keep),
            "vs_any_rejection": go(isrej, rows)}


# ------------------------------------------------------------------------------- (b)
def section_b(sh: Sheet) -> dict:
    b: dict = {}
    model_v = [r for r in sh.V if not r["_manual"]]
    ungrouped = [r for r in model_v if not r.get("text_group_id")]
    members = [r for r in model_v if r.get("text_group_id")]
    changed = lambda r: r.get("text_corrected") is not None  # noqa: E731

    def classes(rows):
        c = Counter(classify_diff(r["text"], r["_eff_text"]) for r in rows)
        ex: dict = defaultdict(list)
        for r in rows:
            k = classify_diff(r["text"], r["_eff_text"])
            if k != "same" and len(ex[k]) < 8:
                ex[k].append([r["text"], r["_eff_text"]])
        return {"counts": dict(c.most_common()), "examples": dict(ex)}

    b["validated_model_rows"] = len(model_v)
    b["ungrouped"] = {"n": len(ungrouped), **classes(ungrouped)}
    b["group_members"] = {"n": len(members), **classes(members)}
    b["text_corrected_not_null_among_validated"] = sum(changed(r) for r in model_v)  # not a verdict count
    # char accuracy of the model against the reviewer, per run (ungrouped rows only)
    b["char_sim_raw_vs_effective_by_run"] = {
        run: {"n": len(rs), "mean": rnd(sum(char_sim(r["text"], r["_eff_text"]) for r in rs) / len(rs), 4),
              "exact_share": rnd(sum(r["text"].strip() == r["_eff_text"].strip() for r in rs) / len(rs), 3)}
        for run in sorted({r["run_id"] for r in ungrouped})
        for rs in [[r for r in ungrouped if r["run_id"] == run]]}
    # groups: split / merge
    g_kinds = Counter()
    sizes = Counter()
    joins_match = 0
    gex = []
    for g in sh.groups:
        ms = sh.members.get(g["id"], [])
        sizes[len(ms)] += 1
        kind = group_kind(ms)
        g_kinds[kind] += 1
        joined = " ".join(m["_eff_text"] for m in ms)
        if _squash(joined) == _squash(g["_eff_text"]):
            joins_match += 1
        if len(gex) < 12:
            gex.append({"group": g["_eff_text"], "kind": kind, "members_raw": [m["text"] for m in ms],
                        "members_effective": [m["_eff_text"] for m in ms]})
    b["groups"] = {"n": len(sh.groups), "by_kind": dict(g_kinds), "member_count": dict(sizes),
                   "group_text_equals_joined_members": joins_match, "examples": gex}
    # the model wrote the whole name into one fragment's box: how often?
    b["member_trims"] = sum(classify_diff(m["text"], m["_eff_text"]).startswith("truncated") for m in members)
    # diacritic fix table: raw token -> effective token
    pairs = Counter()
    for r in model_v:
        if classify_diff(r["text"], r["_eff_text"]) in ("diacritic/accent", "wrong word", "case", "abbreviation"):
            for rt, et in _token_pairs(r["text"], r["_eff_text"]):
                pairs[(rt, et)] += 1
    b["token_corrections"] = [{"raw": k[0], "effective": k[1], "n": n} for k, n in pairs.most_common(30)]
    b["diacritic_load"] = {"validated rows with a mark in effective text": sum(has_diacritic(r["_eff_text"]) for r in model_v),
                           "of which raw text had none": sum(has_diacritic(r["_eff_text"]) and not has_diacritic(r["text"]) for r in model_v)}
    return b


def _token_pairs(raw: str, eff: str) -> list[tuple[str, str]]:
    rt, et = raw.split(), eff.split()
    if len(rt) != len(et):
        return []
    return [(a, b) for a, b in zip(rt, et) if a != b]


def group_kind(ms: list[dict]) -> str:
    if any(is_number_only(m["_eff_text"]) for m in ms):
        return "name+number"
    return "name pieces" if len(ms) >= 2 else "single"


# ------------------------------------------------------------------------------- (c)
def section_c(sh: Sheet) -> dict:
    model = [r for r in sh.model_rows if r["review_status"] == "validated"]
    changes = Counter((r["category"], r["category_corrected"]) for r in model
                      if r.get("category_corrected") and r["category_corrected"] != r["category"])
    matrix = Counter((r["category"], r.get("category_corrected") or r["category"]) for r in model)
    manual = [r for r in sh.rows if r["_manual"] and not r.get("is_text_group")]
    return {
        "model_validated_rows": len(model),
        "category_changed": sum(changes.values()),
        "changes": {f"{a} -> {b}": n for (a, b), n in changes.most_common()},
        "matrix_raw_to_effective": {f"{a} -> {b}": n for (a, b), n in sorted(matrix.items())},
        "manual_rows": len(manual),
        "manual_raw_category": dict(Counter(r["category"] for r in manual)),
        "manual_effective_category": dict(Counter(r["_eff_cat"] for r in manual)),
        "reassigned_for_section_f": dict(sh.reassigned),
    }


# ------------------------------------------------------------------------------- (e)
def section_e(sh: Sheet) -> dict:
    known = {fold(p) for p in LABEL_PREFIXES}
    first = defaultdict(Counter)
    toks = Counter()
    for r in sh.V:
        t = r["_eff_text"]
        if r["_eff_cat"] in NAME_CATS + ("place", "institution", "building"):
            ft = first_token(t)
            if ft:
                first[r["_eff_cat"]][ft] += 1
        for w in re.findall(r"[^\W\d_]{3,}", t.lower()):
            toks[w] += 1
    gap = {cat: [(w, n) for w, n in c.most_common() if w not in known and n >= 2][:15] for cat, c in first.items()}
    abbr = Counter(t.strip(",;:") for r in sh.V for t in r["_eff_text"].split() if re.fullmatch(r"[A-Za-zÀ-ỹ]{1,3}\.", t))
    fixed = Counter()
    for r in sh.V:
        if not r["_manual"] and r.get("text_corrected") is not None:
            raw = set(fold(r["text"]).split())
            for w in fold(r["_eff_text"]).split():
                if len(w) >= 3 and w not in raw:
                    fixed[w] += 1
    return {
        "first_word_not_in_LABEL_PREFIXES": {c: [{"word": w, "n": n} for w, n in v] for c, v in gap.items()},
        "printed_abbreviations_in_validated_text": dict(abbr.most_common(15)),
        "words_the_human_had_to_supply": [{"word": w, "n": n} for w, n in fixed.most_common(25) if n >= 2],
        "most_common_validated_words": [{"word": w, "n": n} for w, n in toks.most_common(30)],
    }


# ------------------------------------------------------------------------------- (f)
def name_rows(sh: Sheet) -> list[dict]:
    """Validated road and river name rows, effective category, number-only pieces out."""
    return [r for r in sh.V if r["_eff_cat"] in NAME_CATS and not is_number_only(r["_eff_text"])]


def outcome(sh: Sheet, r: dict) -> str:
    if r["_manual"]:
        return "missed (human-added)"
    gid = r.get("text_group_id")
    if gid and group_kind(sh.members.get(gid, [])) in ("name pieces", "name+number"):
        return "split (grouped)"
    k = classify_diff(r["text"], r["_eff_text"])
    if k == "same":
        return "ok"
    if k in ("case", "diacritic/accent", "punctuation/spacing", "numeral (N°/No.)", "abbreviation"):
        return "minor fix"
    return "misread"


def pair_geometry(a: dict, b: dict) -> dict | None:
    """How two text boxes lie relative to one another along their shared direction.

    a, b: {cx, cy, rot, long, short}. Direction is (cos t, -sin t) in image
    coordinates, because rotation_deg is counter-clockwise on screen and y grows
    downward (checked on the Rue Mac-Mahon pieces, whose centre-to-centre vector
    runs at -23 degrees in image space against rotation_deg +23).
    """
    th = math.radians(axial_mean([a["rot"], b["rot"]]))
    ux, uy = math.cos(th), -math.sin(th)
    dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]
    along, perp = abs(dx * ux + dy * uy), abs(dx * uy - dy * ux)
    out = {"drot": axial_diff(a["rot"], b["rot"]), "along_px": along, "perp_px": perp}
    if a.get("long") and b.get("long") and a.get("short") and b.get("short"):
        h = (a["short"] + b["short"]) / 2
        gap = along - (a["long"] + b["long"]) / 2
        out.update({"h": h, "gap_px": gap, "gap_h": gap / h, "perp_h": perp / h})
    return out


def as_pair_item(sh: Sheet, r: dict) -> dict:
    cx, cy = sh.centre(r)
    d = oriented_dims(r)
    return {"cx": cx, "cy": cy, "rot": r.get("rotation_deg") or 0.0, "long": d[0] if d else None,
            "short": d[1] if d else None, "src": d[2] if d else None, "id": r["id"], "text": r["_eff_text"]}


def links(g: dict, X: float, Y: float, K: float) -> bool:
    """The 'suggest group' heuristic: same direction, same line, close in letter heights."""
    return ("gap_h" in g and g["drot"] <= X and g["perp_h"] <= Y and -0.5 <= g["gap_h"] <= K)


CONNECTIVES = {"de", "du", "des", "d", "la", "le", "les", "l", "aux", "au", "et", "a"}


def incomplete_name(text: str) -> bool:
    """Is this text visibly the start or end of a longer name?  A bare generic
    ('Rue', 'Arroyo'), a trailing connective ('Route Basse de', 'R. aux'), or no
    generic word at all ('Chinois', 'Mac'). French connectives; a Vietnamese sheet
    needs its own list, but a bare 'Đường' or a name with no generic still counts."""
    toks = fold(text).replace("'", " ").split()
    if not toks:
        return False
    generics = {fold(p) for p in LABEL_PREFIXES} | {"r", "arroyo", "bd"}
    first = toks[0].strip(".")
    return label_core(fold(text)) == "" or toks[-1].strip(".") in CONNECTIVES or first not in generics


def suggest_group_eval(sh: Sheet, names: list[dict], pos_ids: set, radius_px: float) -> dict:
    """How well a collinearity rule would have predicted the human's name-piece groups.

    Universe: every pair of road/river name rows within radius_px, plus pending
    members of the human's groups (a grouped piece is evidence even before it is
    validated). Positive: both pieces in one name-pieces group. In-sample, on
    ~a dozen positive pairs: a way to choose thresholds worth testing, not a measurement."""
    ids = {r["id"] for r in names}
    extra = [m for g in sh.groups if g["_eff_cat"] in NAME_CATS for m in sh.members.get(g["id"], [])
             if m["id"] not in ids and not is_number_only(m["_eff_text"])]
    rows = names + extra
    items = [as_pair_item(sh, r) for r in rows]
    uni = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            dist = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
            if dist > radius_px:
                continue
            g = pair_geometry(a, b)
            if "gap_h" not in g:
                continue
            ang = math.degrees(math.atan2(-(b["cy"] - a["cy"]), b["cx"] - a["cx"]))
            g.update({"pos": frozenset((a["id"], b["id"])) in pos_ids, "same_text": fold(a["text"]) == fold(b["text"]),
                      "inc": incomplete_name(a["text"]) or incomplete_name(b["text"]), "ia": i, "ib": j,
                      "dev": max(axial_diff(ang, a["rot"]), axial_diff(ang, b["rot"])), "dist": dist})
            uni.append(g)
    npos = sum(u["pos"] for u in uni)
    out = {"radius_px": radius_px, "pairs": len(uni), "positives": npos, "positives_total": len(pos_ids),
           "pending_group_members_added": len(extra),
           "scope": "in-sample: thresholds fitted on the human groups they are scored against; n positives is small"}
    pos = [u for u in uni if u["pos"]]
    out["positive_pairs"] = {
        "rot_diff_deg": dist_summary([u["drot"] for u in pos], 1),
        "connecting_line_vs_rotation_deg": dist_summary([u["dev"] for u in pos], 1),
        "perp_offset_in_letter_heights": dist_summary([u["perp_h"] for u in pos], 2),
        "gap_in_letter_heights": dist_summary([u["gap_h"] for u in pos], 2),
        "incomplete_flag": sum(u["inc"] for u in pos)}
    out["negative_pairs"] = {"n": len(uni) - npos, "flagged_incomplete": sum(u["inc"] for u in uni if not u["pos"])}
    grid = []
    for X in (5, 10, 15, 20, 30, 45, 90):
        for Y in (0.5, 1, 1.5, 2, 3, 6):
            for K in (5, 10, 20, 30, 60):
                for need_inc in (False, True):
                    L = [u for u in uni if u["drot"] <= X and u["perp_h"] <= Y and -0.5 <= u["gap_h"] <= K
                         and not u["same_text"] and (u["inc"] or not need_inc)]
                    tp = sum(u["pos"] for u in L)
                    fp = len(L) - tp
                    p, rc = (tp / len(L) if L else 0), (tp / npos if npos else 0)
                    grid.append({"max_rot_diff_deg": X, "max_perp_letter_h": Y, "max_gap_letter_h": K, "need_incomplete_piece": need_inc,
                                 "tp": tp, "fp": fp, "precision": rnd(p, 3), "recall": rnd(rc, 3),
                                 "f1": rnd(2 * p * rc / (p + rc), 3) if p + rc else 0})

    def best(sub):
        if not sub:
            return None
        top = max(g["f1"] for g in sub)
        return min([g for g in sub if g["f1"] >= top - 0.02],
                   key=lambda g: (g["fp"], g["max_gap_letter_h"], g["max_perp_letter_h"], g["max_rot_diff_deg"]))
    out["best_with_incomplete_prior"] = best([g for g in grid if g["need_incomplete_piece"]])
    out["best_geometry_only"] = best([g for g in grid if not g["need_incomplete_piece"]])
    out["best_rotation_gate_off"] = best([g for g in grid if g["need_incomplete_piece"] and g["max_rot_diff_deg"] == 90])
    out["best_rotation_gate_5deg"] = best([g for g in grid if g["need_incomplete_piece"] and g["max_rot_diff_deg"] <= 10])
    # top-1: for each incomplete piece that has a human partner, is its best-ranked candidate the partner?
    partner = defaultdict(set)
    for u in pos:
        partner[u["ia"]].add(u["ib"])
        partner[u["ib"]].add(u["ia"])
    hits = tot = 0
    n_cands = []
    for i, partners in partner.items():
        if not incomplete_name(items[i]["text"]):
            continue
        cands = []
        for u in uni:
            if i in (u["ia"], u["ib"]) and -0.5 <= u["gap_h"] <= 30 and not u["same_text"]:
                cands.append((u["perp_h"], u["ib"] if u["ia"] == i else u["ia"]))
        tot += 1
        n_cands.append(len(cands))
        hits += bool(cands) and min(cands)[1] in partners
    out["top1_for_incomplete_pieces"] = {"fragments": tot, "best_ranked_candidate_is_a_human_partner": hits,
                                         "mean_candidates_per_fragment": rnd(sum(n_cands) / len(n_cands), 1) if n_cands else None,
                                         "ranking": "smallest perpendicular offset among candidates with gap <= 30 letter heights"}
    return out


def section_f(sh: Sheet, radius_px=3500) -> dict:
    f: dict = {}
    names = name_rows(sh)
    f["n_name_rows_validated"] = len(names)
    f["by_category"] = dict(Counter(r["_eff_cat"] for r in names))

    # --- letter spacing
    sp = [(r, spacing(r)) for r in names]
    have = [(r, s) for r, s in sp if s]
    f["spacing"] = {"rows_with_geometry": len(have), "of": len(names),
                    "by_source": dict(Counter(s[1] for _, s in have)),
                    "note": "label = unrotated rectangle stored by a human edit; box = axis-aligned box near 0/90 deg; "
                            "solved = inverted from the axis-aligned box (noisy). Rows a human never touched and that "
                            "sit near 45 deg have none."}
    vals = [s[0] for _, s in have]
    f["spacing"]["distribution"] = dist_summary(vals, 2)
    f["spacing"]["histogram"] = dict(sorted(Counter(round(min(v, 3.0) * 4) / 4 for v in vals).items()))
    if vals:
        q1, q3 = pctile(vals, 33), pctile(vals, 67)
        bins = [("tight", lambda v: v < q1), ("mid", lambda v: q1 <= v < q3), ("wide", lambda v: v >= q3)]
        f["spacing"]["tercile_edges"] = [rnd(q1, 2), rnd(q3, 2)]
        f["spacing"]["outcome_by_tercile"] = {
            nm: dict(Counter(outcome(sh, r) for r, s in have if fn(s[0]))) for nm, fn in bins}
        f["spacing"]["outcome_by_tercile_label_source_only"] = {
            nm: dict(Counter(outcome(sh, r) for r, s in have if fn(s[0]) and s[1] == "label")) for nm, fn in bins}
        f["spacing"]["widest"] = [{"text": r["_eff_text"], "spacing": rnd(s[0], 2), "outcome": outcome(sh, r),
                                   "rot": r.get("rotation_deg")} for r, s in sorted(have, key=lambda t: -t[1][0])[:10]]
    f["outcome_all_name_rows"] = dict(Counter(outcome(sh, r) for r in names))
    has_tail = lambda t: bool(NUM_TAIL_RE.search(t or ""))  # noqa: E731
    tailed = [r for r in names if has_tail(r["_eff_text"])]
    f["house_number_tails"] = {
        "name rows whose effective text ends in a house number": len(tailed), "of": len(names),
        "of those, the model's raw text lacked the number": sum(not has_tail(r["text"]) for r in tailed if not r["_manual"]),
        "model-read rows (excl. manual) among them": sum(not r["_manual"] for r in tailed),
        "manual rows with a number tail": sum(r["_manual"] for r in tailed),
        "manual rows without": sum(r["_manual"] for r in names if not has_tail(r["_eff_text"]))}
    if have:
        f["house_number_tails"]["misread_share_by_spacing_tercile_with_tail_vs_without"] = {
            nm: {"with tail": dict(Counter(outcome(sh, r) for r, s in have if fn(s[0]) and has_tail(r["_eff_text"]))),
                 "without tail": dict(Counter(outcome(sh, r) for r, s in have if fn(s[0]) and not has_tail(r["_eff_text"])))}
            for nm, fn in bins}
    nfrag = Counter(r["_container"] for r in sh.rows if r.get("_reason") == "fragment")
    inside = [nfrag.get(r["id"], 0) for r in names if not r["_manual"]]
    f["model_fragments_per_validated_name_box"] = {
        "validated model-read name rows": len(inside), "with >=1 rejected fragment inside": sum(k > 0 for k in inside),
        "histogram": dict(sorted(Counter(inside).items())), "mean": rnd(sum(inside) / len(inside), 2) if inside else None}
    if have and vals:
        f["model_fragments_per_validated_name_box"]["mean_by_spacing_tercile"] = {
            nm: rnd(sum(nfrag.get(r["id"], 0) for r, s in have if fn(s[0]) and not r["_manual"]) /
                    max(1, sum(1 for r, s in have if fn(s[0]) and not r["_manual"])), 2) for nm, fn in bins}

    # --- fragments
    pos_pairs, num_pairs = [], []
    pos_ids = set()
    kinds = Counter()
    for g in sh.groups:
        ms = sh.members.get(g["id"], [])
        if g["_eff_cat"] not in NAME_CATS:
            continue
        kind = group_kind(ms)
        kinds[kind] += 1
        items = [as_pair_item(sh, m) for m in ms]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a_num = is_number_only(items[i]["text"])
                b_num = is_number_only(items[j]["text"])
                geo = pair_geometry(items[i], items[j])
                rec = {"group": g["_eff_text"], "a": items[i]["text"], "b": items[j]["text"], **(geo or {}),
                       "src": (items[i]["src"], items[j]["src"])}
                if a_num or b_num:
                    num_pairs.append(rec)
                else:
                    pos_pairs.append(rec)
                    pos_ids.add(frozenset((items[i]["id"], items[j]["id"])))
    f["groups"] = {"name_groups_by_kind": dict(kinds),
                   "pieces_per_name_group": dict(Counter(len([m for m in sh.members.get(g["id"], [])
                                                              if not is_number_only(m["_eff_text"])])
                                                         for g in sh.groups if g["_eff_cat"] in NAME_CATS)),
                   "name_piece_pairs": len(pos_pairs), "number_attach_pairs": len(num_pairs)}

    def summarise(pairs):
        geo = [p for p in pairs if "gap_h" in p]
        return {"n_pairs": len(pairs), "n_with_geometry": len(geo),
                "rot_spread_deg": dist_summary([p["drot"] for p in pairs], 1),
                "gap_in_letter_heights": dist_summary([p["gap_h"] for p in geo], 2),
                "perp_offset_in_letter_heights": dist_summary([p["perp_h"] for p in geo], 2),
                "gap_px": dist_summary([p["gap_px"] for p in geo], 0),
                "centre_distance_px": dist_summary([p["along_px"] for p in pairs], 0)}

    f["fragments"] = {"name_piece_pairs": summarise(pos_pairs), "number_attach_pairs": summarise(num_pairs),
                      "name_piece_examples": [{k: (rnd(v, 2) if isinstance(v, float) else v) for k, v in p.items()}
                                              for p in pos_pairs[:14]]}

    f["heuristic"] = suggest_group_eval(sh, names, pos_ids, radius_px)

    # --- repeats
    f["repeats"] = repeats(sh)

    # --- orientation
    model_names = [r for r in sh.model_rows if r["_eff_cat"] in NAME_CATS or (r["category"] in NAME_CATS)]
    hist = Counter(int(math.floor(((r.get("rotation_deg") or 0) + 90) / 15)) * 15 - 90 for r in names if r.get("rotation_deg") is not None)
    f["orientation"] = {
        "histogram_15deg_name_rows": dict(sorted(hist.items())),
        "share_rotation_exactly_0": rnd(sum((r.get("rotation_deg") or 0) == 0 for r in names) / max(len(names), 1), 3),
        "by_bucket": {},
    }
    byb: dict = defaultdict(lambda: {"validated": 0, "rejected_non_dup": 0, "rejected_dup": 0, "sims": []})
    for r in model_names:
        if r["review_status"] == "validated":
            e = byb[rot_bucket(r.get("rotation_deg"))]
            e["validated"] += 1
            e["sims"].append(char_sim(r["text"], r["_eff_text"]))
        elif r["review_status"] == "rejected":
            e = byb[rot_bucket(r.get("rotation_deg"))]
            e["rejected_dup" if r.get("_reason") == "dup" else "rejected_non_dup"] += 1
    for k, e in sorted(byb.items()):
        sims = e.pop("sims")
        tot = e["validated"] + e["rejected_non_dup"]
        f["orientation"]["by_bucket"][k] = {**e, "char_sim_mean": rnd(sum(sims) / len(sims), 3) if sims else None,
                                            "validated_share_excl_dup": rnd(e["validated"] / tot, 3) if tot else None}

    # --- misses
    manual = [r for r in names if r["_manual"]]
    found = [r for r in names if not r["_manual"]]
    def dims(rs):
        ds = [oriented_dims(r) for r in rs]
        ds = [d for d in ds if d]
        return {"n": len(rs), "with_dims": len(ds), "long_px": dist_summary([d[0] for d in ds], 0),
                "short_px": dist_summary([d[1] for d in ds], 0)}
    f["misses"] = {
        "manual_name_rows": len(manual), "model_validated_name_rows": len(found),
        "manual_dims": dims(manual), "found_dims": dims(found),
        "manual_spacing": dist_summary([s[0] for r in manual for s in [spacing(r)] if s], 2),
        "found_spacing": dist_summary([s[0] for r in found for s in [spacing(r)] if s], 2),
        "rotation_manual": dict(Counter(rot_bucket(r.get("rotation_deg")) for r in manual)),
        "rotation_found": dict(Counter(rot_bucket(r.get("rotation_deg")) for r in found)),
        "chars_manual": dist_summary([nchars(r["_eff_text"]) for r in manual], 0),
        "chars_found": dist_summary([nchars(r["_eff_text"]) for r in found], 0),
        "rows": [{"text": r["_eff_text"], "cat": r["_eff_cat"], "rot": r.get("rotation_deg"),
                  "long": rnd((oriented_dims(r) or [None])[0], 0), "short": rnd((oriented_dims(r) or [None, None])[1], 0),
                  "spacing": rnd((spacing(r) or [None])[0], 2), "run": r["run_id"], "status": r["review_status"]} for r in manual],
        "all_manual_rows_any_category": len([r for r in sh.rows if r["_manual"] and not r.get("is_text_group")]),
        "rejected_model_fragments_inside_a_manual_box": dict(sorted(Counter(nfrag.get(r["id"], 0) for r in manual).items())),
        "manual_name_rows_with_number_tail": sum(has_tail(r["_eff_text"]) for r in manual),
        "found_name_rows_with_number_tail": sum(has_tail(r["_eff_text"]) for r in found),
    }
    return f


def instances(sh: Sheet) -> list[dict]:
    """One entry per printed name: an ungrouped validated row, or one text group."""
    out = []
    in_group = {m["id"] for ms in sh.members.values() for m in ms}
    for r in name_rows(sh):
        if r["id"] in in_group:
            continue
        cx, cy = sh.centre(r)
        out.append({"text": strip_number(r["_eff_text"]), "cx": cx, "cy": cy, "rot": r.get("rotation_deg") or 0.0, "cat": r["_eff_cat"]})
    for g in sh.groups:
        if g["_eff_cat"] not in NAME_CATS:
            continue
        ms = [m for m in sh.members.get(g["id"], []) if not is_number_only(m["_eff_text"])]
        if not ms:
            continue
        cs = [sh.centre(m) for m in ms]
        out.append({"text": strip_number(g["_eff_text"]), "cx": sum(c[0] for c in cs) / len(cs), "cy": sum(c[1] for c in cs) / len(cs),
                    "rot": axial_mean([m.get("rotation_deg") or 0.0 for m in ms]), "cat": g["_eff_cat"]})
    return out


def repeats(sh: Sheet) -> dict:
    inst = [i for i in instances(sh) if name_key(i["text"])]
    by = defaultdict(list)
    for i in inst:
        by[name_key(i["text"])].append(i)
    counts = Counter({k: len(v) for k, v in by.items()})
    multi = {k: v for k, v in by.items() if len(v) >= 2}
    nn, pair_rows = [], []
    for k, v in multi.items():
        for a_i, a in enumerate(v):
            ds = [(math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"]), b) for b_i, b in enumerate(v) if b_i != a_i]
            d, b = min(ds, key=lambda t: t[0])
            nn.append(d * sh.mpp)
        for a_i in range(len(v)):
            for b_i in range(a_i + 1, len(v)):
                a, b = v[a_i], v[b_i]
                d = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
                ang = math.degrees(math.atan2(-(b["cy"] - a["cy"]), b["cx"] - a["cx"]))
                along = axial_diff(ang, axial_mean([a["rot"], b["rot"]])) <= 15
                pair_rows.append({"name": k, "m": d * sh.mpp, "drot": axial_diff(a["rot"], b["rot"]), "along_line": along})
    along_pairs = [p for p in pair_rows if p["along_line"] and p["drot"] <= 15]
    res = {
        "name_instances": len(inst), "distinct_names": len(by), "names_seen_more_than_once": len(multi),
        "count_per_name_histogram": dict(sorted(Counter(counts.values()).items())),
        "most_repeated": [{"name": k, "n": n} for k, n in counts.most_common(12) if n >= 2],
        "nearest_repeat_m": dist_summary(nn, 0),
        "pair_spacing_m_all": dist_summary([p["m"] for p in pair_rows], 0),
        "pair_spacing_m_along_the_line": dist_summary([p["m"] for p in along_pairs], 0),
        "pairs_total": len(pair_rows), "pairs_along_one_line": len(along_pairs),
        "caveat": "repeats are counted among validated rows only; the reviewer kept one reading per label, "
                  "so a repeat here is a second printed instance, not a second run's copy",
    }
    res["_min_real_repeat_m"] = rnd(min((p["m"] for p in pair_rows), default=None), 0) if pair_rows else None
    return res


# ------------------------------------------------------------------------------ report
def show(obj, indent=2) -> None:
    """Print a nested dict one line per leaf: short values inline, long ones indented."""
    pad = " " * indent
    for k, v in obj.items():
        line = json.dumps(v, ensure_ascii=False, default=str)
        if isinstance(v, dict) and len(line) > 150:
            print(f"{pad}{k}:")
            show(v, indent + 2)
        else:
            print(f"{pad}{k}: {line if len(line) < 900 else line[:900] + ' ...'}")


def report(sh: Sheet, a, b, c, d, e, f) -> None:
    n = len(sh.rows)
    print(f"== OCR review patterns: map {sh.rows[0]['map_id'] if sh.rows else '?'}  ({n} rows, {len(sh.groups)} group rows, "
          f"{sum(r['_manual'] for r in sh.rows)} manual boxes)")
    print("\n[a] verdicts")
    print(f"  rows by status (all): {a['rows_by_status']}   excluding group rows: {a['rows_by_status_excl_groups']}")
    for k in ("by_run", "by_category_effective", "by_confidence_bucket"):
        print(f"  {k}:")
        for key, v in a[k].items():
            print(f"    {str(key):28s} {v}")
    print("  confidence values by run (top 8):", a["confidence_values_by_run"])
    for scope, res in [("pooled", a["confidence"]["pooled"])] + list(a["confidence"]["by_run"].items()):
        for pop in ("vs_wrong_text_only", "vs_rejected_non_dup", "vs_any_rejection"):
            r = res[pop]
            print(f"  cutoff [{scope}] {pop}: n={r['n']} bad={r['n_bad']} base={r['base_rate']} auc={r.get('auc_low_conf_means_bad')} "
                  f"best={r['best_f1']}")
    print("\n[b] text diffs on validated model rows")
    print(f"  ungrouped n={b['ungrouped']['n']}: {b['ungrouped']['counts']}")
    print(f"  group members n={b['group_members']['n']}: {b['group_members']['counts']}")
    print(f"  char_sim raw vs effective by run: {b['char_sim_raw_vs_effective_by_run']}")
    for k, ex in {**b['ungrouped']['examples'], **{'members/' + k: v for k, v in b['group_members']['examples'].items()}}.items():
        print(f"    {k}: {ex[:4]}")
    print(f"  groups: {b['groups']['n']} {b['groups']['by_kind']} sizes={b['groups']['member_count']} "
          f"joined==group text: {b['groups']['group_text_equals_joined_members']}")
    print(f"  member trims (model wrote more than the piece): {b['member_trims']}")
    print(f"  token corrections: {[(x['raw'], x['effective'], x['n']) for x in b['token_corrections'][:15]]}")
    print("\n[c] category")
    for k, v in c.items():
        print(f"  {k}: {v}")
    print("\n[d] rejections")
    print(f"  {d['n_rejected_model_rows']} rejected model rows: {d['reason_counts']}")
    print(f"  reason by run: {d['reason_by_run']}")
    print(f"  dup twin centre distance px: {d['dup_centre_distance_px']}  (m: {d['dup_centre_distance_m']})")
    for k, v in d["profile"].items():
        print(f"  {k}: {v}")
    print(f"  orphan features: { {k: v for k, v in d['orphan_text_features'].items() if k != 'examples'} }")
    for ex in d["orphan_text_features"]["examples"][:12]:
        print(f"    orphan {ex}")
    for ex in d["part_and_textwrong_examples"][:10]:
        print(f"    {ex}")
    print("\n[e] vocabulary")
    show(e)
    print("\n[f] sparse layout of road and river names")
    show(f)


def build(rows: list[dict], mpp: float, sheet_w=None, sheet_h=None) -> dict:
    sh = Sheet(rows, mpp, sheet_w, sheet_h)
    a, d = section_a_d(sh)
    b, c, e = section_b(sh), section_c(sh), section_e(sh)
    f = section_f(sh)
    return {"_sheet": sh, "a": a, "b": b, "c": c, "d": d, "e": e, "f": f}


# ---------------------------------------------------------------------------- (g) main
def fetch(map_id: str) -> list[dict]:
    from eval import _rest_get
    rows = _rest_get("ocr_labels", {"map_id": f"eq.{map_id}", "select": "*", "order": "id"})
    stray = [r for r in rows if r.get("map_id") != map_id]
    assert not stray, f"{len(stray)} rows from another map came back"
    return rows


def _self_check() -> None:
    # diff classes
    assert classify_diff("Rue Catinat", "Rue Catinat") == "same"
    assert classify_diff("Marche Central", "Marché Central") == "diacritic/accent"
    assert classify_diff("MAIRIE", "Mairie") == "case"
    assert classify_diff("Rue Mac Mahon N° 26", "Rue Mac Mahon No. 26") == "numeral (N°/No.)"
    assert classify_diff("R. aux Fleurs", "Rue aux Fleurs") == "abbreviation"
    assert classify_diff("Quai Charner No. 18", "Rue Charner No. 18") == "generic word swap"
    assert classify_diff("Rue Thu duc", "Rue de Thu duc No. 11") == "extended (human added words)"
    assert classify_diff("Arroyo Chinois", "Arroyo") == "truncated (human trimmed words)"
    assert classify_diff("Rue Mac-Mahon", "Rue Mac Mahon") == "punctuation/spacing"
    assert classify_diff("Rạch Cầu Chông", "Rạch Cầu Chống") == "diacritic/accent"
    assert classify_diff("CHASSELOUD", "CHASSELOUP") == "wrong word"
    assert classify_diff("", "Rue") == "typed (model empty)"
    assert is_number_only("N° 5") and is_number_only("No. 26") and not is_number_only("Rue 5")
    assert strip_number("Rue Dayot No. 5") == "Rue Dayot"
    assert prefix_category("Arroyo de l'Avalanche") == "hydrology" and prefix_category("R. aux Fleurs") == "street"
    assert prefix_category("Ancien Palais de Justice") is None
    assert conf_bucket(0.95) == "0.95-<1" and conf_bucket(1.0) == "1.0" and conf_bucket(0.9) == "0.9-0.95"
    # angles
    assert axial_diff(179, 1) == 2 and axial_diff(-45, 45) == 90
    assert abs(axial_mean([89, -89]) - 90) < 1e-6 or abs(abs(axial_mean([89, -89])) - 90) < 1e-6
    # oriented dims: a 1000x50 rectangle at 20 degrees round-trips through its axis-aligned box
    th = math.radians(20)
    W, H = 1000 * math.cos(th) + 50 * math.sin(th), 1000 * math.sin(th) + 50 * math.cos(th)
    lng, sht, src = oriented_dims({"global_w": W, "global_h": H, "rotation_deg": 20})
    assert src == "solved" and abs(lng - 1000) < 1 and abs(sht - 50) < 1
    assert oriented_dims({"global_w": 400, "global_h": 440, "rotation_deg": 45}) is None  # det ~ 0
    assert oriented_dims({"global_w": 300, "global_h": 40, "rotation_deg": 0})[2] == "box"
    # collinearity: two boxes on one horizontal line, 75 px apart (7.5 letter heights), tilted 4 degrees up-right
    A = {"cx": 0, "cy": 0, "rot": 0, "long": 100, "short": 10}
    B = {"cx": 150, "cy": -5, "rot": 4, "long": 50, "short": 10}
    g = pair_geometry(A, B)
    assert abs(g["drot"] - 4) < 1e-9 and abs(g["gap_h"] - 7.5) < 0.2 and g["perp_h"] < 0.6, g
    assert links(g, 5, 1, 8) and not links(g, 3, 1, 8) and not links(g, 5, 1, 6)
    # the same pair shifted a whole line down is a different line, not a fragment
    C = {**B, "cy": 60}
    assert not links(pair_geometry(A, C), 5, 1, 20)
    # a 23-degree line in image space (y down): direction runs up-right when rotation_deg is positive
    t = math.radians(23)
    P = {"cx": 0, "cy": 0, "rot": 23, "long": 100, "short": 10}
    Q = {"cx": 400 * math.cos(t), "cy": -400 * math.sin(t), "rot": 23, "long": 100, "short": 10}
    gq = pair_geometry(P, Q)
    assert gq["perp_px"] < 1e-6 and abs(gq["along_px"] - 400) < 1e-6
    # incomplete pieces and fragments
    assert incomplete_name("Rue") and incomplete_name("Route Basse de") and incomplete_name("Chinois")
    assert incomplete_name("R. aux") and not incomplete_name("Rue Sohier") and not incomplete_name("Rue de Singapore")
    assert covered_by({"global_x": 10, "global_y": 10, "global_w": 20, "global_h": 20},
                      {"global_x": 0, "global_y": 0, "global_w": 100, "global_h": 100}) == 1.0
    assert fragment_kind("N° 8", "Rue de Bang Kok No. 8") == "house number alone"
    assert fragment_kind("Rue", "Rue Thabert") == "generic/short piece"
    # group kinds
    assert group_kind([{"_eff_text": "Rue Dayot"}, {"_eff_text": "No. 5"}]) == "name+number"
    assert group_kind([{"_eff_text": "Rue"}, {"_eff_text": "Mac"}]) == "name pieces"
    # reject_reason on a toy sheet
    def row(i, x, y, w, h, text, status, **kw):
        return {"id": i, "map_id": "m", "global_x": x, "global_y": y, "global_w": w, "global_h": h, "text": text,
                "text_corrected": None, "category": "street", "category_corrected": None, "review_status": status,
                "run_id": "r", "confidence": 0.9, "model": "x", "rotation_deg": 0, "is_text_group": False,
                "text_group_id": None, **kw}
    toy = Sheet([row("v", 0, 0, 100, 20, "Rue Catinat", "validated"),
                 row("d", 2, 1, 100, 20, "Rue Catinat", "rejected"),
                 row("w", 0, 0, 100, 20, "Quai Charner", "rejected"),
                 row("o", 5000, 5000, 80, 20, "XQZ", "rejected")], 0.34)
    assert reject_reason(toy, toy.by_id["d"])[0] == "dup"
    assert reject_reason(toy, toy.by_id["w"])[0] == "text-wrong"
    assert reject_reason(toy, toy.by_id["o"])[0] == "orphan"
    print("[ok] review_patterns self-check passed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--map", default=DEFAULT_MAP, help="map uuid (default: the 1882 Plan Cadastral)")
    ap.add_argument("--mpp", type=float, default=DEFAULT_MPP, help="metres per source pixel (default 0.3416, 1882)")
    ap.add_argument("--sheet-w", type=int, default=None)
    ap.add_argument("--sheet-h", type=int, default=None)
    ap.add_argument("--out", default=None, help="JSON path (default outputs/<map>/review_patterns.json)")
    ap.add_argument("--self-check", action="store_true", help="run the asserts and exit")
    args = ap.parse_args()
    if args.self_check:
        _self_check()
        return
    rows = fetch(args.map)
    if not rows:
        raise SystemExit(f"no ocr_labels rows for {args.map}")
    res = build(rows, args.mpp, args.sheet_w, args.sheet_h)
    sh = res.pop("_sheet")
    report(sh, res["a"], res["b"], res["c"], res["d"], res["e"], res["f"])
    out = Path(args.out) if args.out else OUT_ROOT / args.map / "review_patterns.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"map_id": args.map, "mpp": args.mpp, **res}, ensure_ascii=False, indent=2, default=str))
    print(f"\n[ok] wrote {out}")


if __name__ == "__main__":
    main()
