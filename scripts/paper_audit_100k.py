#!/usr/bin/env python3
"""Human audit of the Indochine 1:100,000 clear set (paper section 9, roadmap item `paper-audit-100k`).

HOW THE OWNER RUNS A SITTING  (about 40 sheets, about 2 hours, stop and resume at will)
----------------------------------------------------------------------------------------
    work/ocr/.venv/bin/python scripts/paper_audit_100k.py serve      # then open http://127.0.0.1:8794
Run it from anywhere; it moves to the repo root. Close the tab or press Ctrl-C when you want a
break. Run `serve` again and it resumes at the first sheet without a verdict. Every verdict is one
line in work/indochine-100k/paper-audit/verdicts.jsonl; nothing is rewritten.

Each sheet has two screens, in this order.
  1. V-frame. Eight crops (four corners, four mid-edges) with the placed boundary drawn as a thin
     magenta line. Question: does that line lie on the sheet's printed edge (the neatline)?
         y  on the edge      n  off the edge      p  partly (some crops yes, some no)
         ?  cannot tell      b  hold to see the crops without the line (toggle)
  2. V-place. Question: is the sheet in the right place on the earth? You answer from the
     sheet's own graticule ticks, which carry a printed label in grades, for example 118g30.
     The page shows strips along the four edges (keys 1 top, 2 bottom, 3 left, 4 right; Tab cycles).
     For each tick you can see: CLICK the tick, TYPE its printed label (118g30, 118.30 and 118,3 all
     work), press Enter. Read at least two ticks, at least 400 px apart, on one side for longitude
     (top or bottom) and one side for latitude (left or right). A second side is welcome; it is
     the check on your own reading. The page never shows the machine's label, the catalogue values
     or the stored lon/lat. If you cannot find the label, do not guess.
         Enter  done with this sheet        0  no ticks are visible       ?  cannot tell
Both screens: u undo the last verdict (it goes back one step), t type a note (Enter leaves it).

When you are done:  python3 scripts/paper_audit_100k.py score   -> paper-audit/paper_audit_100k.json.

COMMANDS
--------
    --self-check   no network, no data files: asserts the scoring maths and the draw
    freeze         read the DB, write paper-audit/population.json (the frame to sample from)
    draw           pick the sample; refuses unless this file is committed and unchanged
    serve          the review page on port 8794 (--sample PATH, --out DIR for a trial run)
    score          verdicts -> paper-audit/paper_audit_100k.json

PRE-REGISTRATION  (written before any draw; commit this file, then `draw`; the draw refuses otherwise)
--------------------------------------------------------------------------------------------------
Question. Of the Indochine 1:100,000 sheets that the gates cleared and that are public, how many
carry a placement error that the gates cannot see, because the gates' committed input is the
catalogue (paper B0151, B0152)? Tri Binh was about 509 m off and passed every gate.

Population. Every row of `maps` in collection "Indochine 1:100,000 - 2nd edition SGI" with
status = public, that also has a saved placement work/indochine-100k/<uuid>.json holding `lines`,
`corners` and `wgs84` and an empty `verdict`. `freeze` writes it, with each sheet's corner hash
(sha1 of json.dumps(wgs84, sort_keys=True)) and its detector_version. The paper's figure is 314
public sheets "at the recorded state". The frame is whatever is public on the day of `freeze`;
`freeze` prints any gap against 314 and does not force it. The sample is a sample of that frame,
not of the 314 of the paper.

Sample. Simple random sample without replacement, n = 40, from the frame sorted by id, using
random.Random(SEED) with SEED written below. The sample order is the sitting order. Calibration
sheets (ids in calibration-fit.json `observations`) stay in the sample if drawn, flagged, and are
reported apart: their placement was tuned against printed ticks, so they are not blind.

Why n = 40. It is what two hours buy (about 3 minutes a sheet), not a power calculation. The
Wilson 95% interval it gives for the V-place failure rate:
    0 of 40 fail:  0.0% [0-9]       2 of 40 fail:  5.0% [1-17]       5 of 40 fail: 12.5% [5-26]
That is wide. It can show a rate is under about 10% or over about 5%; it cannot tell 5% from 10%.
The paper must say so. A larger n needs a second sitting, drawn the same way, not a re-draw.

Threshold. A sheet FAILS V-place if any corner-axis is off by more than 150 m: placed minus
printed, in metres, at each corner, from lines the reviewer fitted through the ticks clicked. It
is the same number as AUDIT_THRESHOLD_M in the machine audit (scripts/indochine100k_georef.py), so the two
are comparable. Fixed before any data. Do not tune it. Edges follow the machine audit: west is
the NW and SW longitude, east is NE and SE, north is NW and NE latitude, south is SW and SE.
Grades convert to degrees by 0.9; longitudes add the Paris meridian, 2.337229166666667 deg.

Unreadable. V-place is unreadable, and scored apart, when the reviewer pressed 0 or ?, or when after
the reading fewer than all four edges have a printed value (no side with two or more ticks 400 px
or more apart on an axis), and no read edge already fails. A read edge that fails makes the sheet
a fail whatever else is missing. V-frame is unreadable when the reviewer pressed ?. The error rates
use readable sheets as the denominator; the worst case (unreadable counted as failed) is reported
beside them. A verdict whose bound hash no longer matches the placement is stale and is dropped
and counted.

V-frame fails on n or p (the boundary is not on the printed edge in at least one crop).

Failures flagged for a second look. A failing sheet is flagged when a side's fitted line leaves a
tick by more than 150 m, or when the two sides of one edge disagree by more than 150 m. These are
more likely a mistyped label than a bad placement. They stay counted as failures in the headline;
the output lists them so the owner can re-read them, and also gives the count without them.

PREDICTIONS (written before the draw; report every one that disagrees)
    V-frame failures:  1 of 40 (range 0 to 3). The frame comes from image lines with small
        residuals, and its gates passed; Tri Binh's frame was right and its place was wrong.
    V-place failures:  5 of 40 (range 2 to 10). The placement is the catalogue box plus a
        latitude-linear offset fitted on six sheets; those six leave residuals of 11 to 188 m
        (mean 76 m), and two of six are over 140 m. A shift of that spread puts roughly one
        sheet in eight over 150 m on some corner.
    Unreadable V-place: 2 of 40. Some sheets carry labels worn or cut by the scan edge.
    Median seconds per sheet:  about 15 s for V-frame, 110 s for V-place, 125 s together
        (so 40 sheets is about 85 minutes of pure reading, about 2 hours with breaks).
        Reading and typing four to six labels dominates.
    The first ten sheets take longer than the last ten (learning curve), by about a third.

This tool does not decide which evidence is better. V-frame sees the machine's proposal, because
the boundary is the thing judged. V-place never sees it, so a person who trusts the drawn line
cannot pass a sheet whose line is off on the earth.

Never edited by this file: indochine100k_georef.py, any placement json, printed-audit.json (read
only, for the agreement table). Local data goes in work/indochine-100k/paper-audit/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

THIS = Path(__file__).resolve()
ROOT = THIS.parent.parent
sys.path.insert(0, str(ROOT / "work" / "review-kit"))
from review_record import bound as bound_hash, load, record, sittings, wilson  # noqa: E402

WORK = ROOT / "work" / "indochine-100k"
PA = WORK / "paper-audit"
TASK = "paper-audit-100k"
COLLECTION = "Indochine 1:100,000 — 2nd édition SGI (1947–1959)"  # same string as indochine100k_georef.COLLECTION

N_SAMPLE = 40
SEED = 20261013  # arbitrary; fixed before any draw, derived from nothing in the data
THRESHOLD_M = 150.0  # = AUDIT_THRESHOLD_M in the machine audit; fixed before any data, do not tune
PAPER_PUBLIC = 314
GRADE, PARIS = 0.9, 2.337229166666667  # same values as indochine100k_georef.GRADE, PARIS
CORNERS = ("NW", "NE", "SE", "SW")
PORT = 8794

TICKS_PER_SIDE = 3
MIN_SEP_PX = 400  # two ticks closer than this do not fix a line
ALONG, OUT, IN = 500, 230, 90  # place panel: 2 x 250 px along the edge; 230 px outside the rim, 90 inside
FRAME_S, FRAME_ZOOM = 320, 1.5  # frame crop: native px square, enlarged
SIDES = {  # side -> (axis, index of the along coordinate in an (x, y) pair, the two corners it reaches)
    "T": ("lon", 0, ("NW", "NE")),
    "B": ("lon", 0, ("SW", "SE")),
    "L": ("lat", 1, ("NW", "SW")),
    "R": ("lat", 1, ("NE", "SE")),
}
EDGES = {  # edge -> (side, corner) pairs that each give one estimate
    "west": (("T", "NW"), ("B", "SW")),
    "east": (("T", "NE"), ("B", "SE")),
    "north": (("L", "NW"), ("R", "NE")),
    "south": (("L", "SW"), ("R", "SE")),
}
GRADE_RANGE = {"lon": (100.0, 130.0), "lat": (3.0, 35.0)}  # typo guard only; Indochine is ~111-120 and ~9-25


# --------------------------------------------------------------------------- the maths

def metres_per_degree(lat):
    """Parallel and meridian scale on WGS 84 (same formula as indochine100k_georef.metres_per_degree)."""
    a, e2 = 6378137.0, 1 - (6356752.314245 / 6378137.0) ** 2
    p = math.radians(lat)
    q = 1 - e2 * math.sin(p) ** 2
    return math.pi / 180 * a * math.cos(p) / math.sqrt(q), math.pi / 180 * a * (1 - e2) / q ** 1.5


def north_metres(lat0, lat1):
    """Meridian arc by Simpson's rule."""
    mid = (lat0 + lat1) / 2
    return abs(lat1 - lat0) * (metres_per_degree(lat0)[1] + 4 * metres_per_degree(mid)[1] + metres_per_degree(lat1)[1]) / 6


def parse_grades(text: str, axis: str | None = None) -> float:
    """'118g30', '118ᵍ30', '118.30', '118,3', '118' -> 118.3. Raises ValueError on anything else."""
    import re

    s = (text or "").strip().replace("'", "").replace("’", "")
    m = re.fullmatch(r"(\d{1,3})\s*(?:[gGᵍᴳ°º]|\^g)?\s*[,.]?\s*(\d{0,4})", s)
    if not m or not s:
        raise ValueError(f"cannot read {text!r} as grades (type like 118g30 or 118.3)")
    v = float(f"{m[1]}.{m[2] or '0'}")
    if axis:
        lo, hi = GRADE_RANGE[axis]
        if not lo <= v <= hi:
            raise ValueError(f"{v} g is outside the {axis} range {lo}-{hi} g; check the label")
    return v


def side_fit(ticks):
    """Least-squares line grades = a + b * along through [(along_px, grades)]; None if it cannot fix a line."""
    if len(ticks) < 2:
        return None
    xs, ys = [t[0] for t in ticks], [t[1] for t in ticks]
    if max(xs) - min(xs) < MIN_SEP_PX:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    return a, b, max(abs(y - (a + b * x)) for x, y in zip(xs, ys))


def score_place(placement: dict, ticks_by_side: dict) -> dict:
    """Placed minus printed, in metres, from the ticks a person clicked and read.

    ticks_by_side: {"T": [(x_px, grades), ...], "B": ..., "L": [(y_px, grades), ...], "R": ...}.
    Nothing here reads the catalogue: the printed value comes from the clicks alone.
    Returns outcome pass | fail | unreadable, the per-corner deltas, the edge deltas (mean of the
    estimates) and flags that mark readings worth a second look.
    """
    corners, wgs = placement["corners"], placement["wgs84"]
    deltas: dict[str, dict[str, float]] = {}
    flags, unusable = [], []
    for side, (axis, idx, pair) in SIDES.items():
        ticks = ticks_by_side.get(side) or []
        fit = side_fit(ticks)
        if fit is None:
            if ticks:
                unusable.append(f"{side}: {len(ticks)} tick(s), no line (need 2 at least {MIN_SEP_PX} px apart)")
            continue
        a, b, resid_g = fit
        lat_ref = (wgs["NW"][1] + wgs["SW"][1]) / 2
        per_deg = metres_per_degree(lat_ref)[0 if axis == "lon" else 1]
        if resid_g * GRADE * per_deg > THRESHOLD_M:
            flags.append(f"{side}: the line leaves a tick by {resid_g * GRADE * per_deg:.0f} m")
        deltas[side] = {}
        for c in pair:
            g = a + b * corners[c][idx]
            if axis == "lon":
                printed = g * GRADE + PARIS
                deltas[side][c] = (wgs[c][0] - printed) * metres_per_degree(wgs[c][1])[0]
            else:
                printed = g * GRADE
                d = wgs[c][1] - printed
                deltas[side][c] = (1 if d >= 0 else -1) * north_metres(wgs[c][1], printed)
    edges, spread, missing = {}, {}, []
    for edge, members in EDGES.items():
        vals = [deltas[s][c] for s, c in members if s in deltas]
        if not vals:
            missing.append(edge)
            continue
        edges[edge] = sum(vals) / len(vals)
        if len(vals) > 1:
            spread[edge] = max(vals) - min(vals)
            if spread[edge] > THRESHOLD_M:
                flags.append(f"{edge}: the two sides differ by {spread[edge]:.0f} m")
    worst = max((abs(v) for per in deltas.values() for v in per.values()), default=None)
    if worst is not None and worst > THRESHOLD_M:
        outcome = "fail"
    elif missing:
        outcome = "unreadable"
    else:
        outcome = "pass"
    return {"outcome": outcome, "edges_m": {k: round(v, 1) for k, v in edges.items()},
            "deltas_m": {s: {c: round(v, 1) for c, v in per.items()} for s, per in deltas.items()},
            "worst_m": None if worst is None else round(worst, 1), "missing_edges": missing,
            "unusable": unusable, "flags": flags}


# --------------------------------------------------------------------------- population, sample, pre-registration gate

def corner_hash(wgs84) -> str:
    return hashlib.sha1(json.dumps(wgs84, sort_keys=True).encode()).hexdigest()


def clear_placement(d: dict) -> bool:
    return all(k in d for k in ("lines", "corners", "wgs84")) and not d.get("verdict") and not d.get("placement_error")


def calibration_ids() -> set[str]:
    f = WORK / "calibration-fit.json"
    return {o["id"] for o in json.loads(f.read_text())["observations"]} if f.exists() else set()


def population_sha1(sheets: list[dict]) -> str:
    return hashlib.sha1(json.dumps(sorted(sheets, key=lambda s: s["id"]), sort_keys=True).encode()).hexdigest()


def georef():
    """The committed names of the georef script, imported late so --self-check never touches it."""
    import os

    os.chdir(ROOT)  # the script's WORK, .env and cache paths are relative to the repo root
    sys.path.insert(0, str(ROOT / "scripts"))
    import indochine100k_georef as g

    assert (g.GRADE, g.PARIS, tuple(g.CORNERS)) == (GRADE, PARIS, CORNERS), "constants drifted from the georef script"
    return g


def freeze(out: Path = PA) -> int:
    g = georef()
    cal = calibration_ids()
    rows = g.rows()
    sheets, left_out = [], []
    for r in sorted(rows, key=lambda r: r["id"]):
        if r["status"] != "public":
            continue
        p = WORK / f"{r['id']}.json"
        d = json.loads(p.read_text()) if p.exists() else {}
        if not clear_placement(d):
            left_out.append(r["name"])
            continue
        sheets.append({"id": r["id"], "name": r["name"], "hash": corner_hash(d["wgs84"]),
                       "detector_version": d.get("detector_version"), "calibration": r["id"] in cal,
                       "printed_quad": bool(d.get("printed_quad_review")),
                       "iiif_base": r.get("iiif_image") or f"https://iiif.maparchive.vn/iiif/{r['id']}"})
    doc = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "collection": COLLECTION, "paper_public_count": PAPER_PUBLIC,
           "db_public": sum(r["status"] == "public" for r in rows), "n": len(sheets),
           "public_without_clear_placement": left_out, "sha1": population_sha1(sheets),
           "calibration_in_population": [s["name"] for s in sheets if s["calibration"]], "sheets": sheets}
    out.mkdir(parents=True, exist_ok=True)
    (out / "population.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    from collections import Counter

    print(f"population: {len(sheets)} public sheets with a clear saved placement ({doc['db_public']} public in the DB)")
    print(f"paper says {PAPER_PUBLIC} 'at the recorded state': gap {len(sheets) - PAPER_PUBLIC:+d} (reported, not forced)")
    print(f"calibration sheets in it: {len(doc['calibration_in_population'])}: {', '.join(doc['calibration_in_population'])}")
    print("detector versions:", dict(Counter(s["detector_version"] for s in sheets)),
          "| printed-quad (skewed) sheets:", sum(s["printed_quad"] for s in sheets))
    if left_out:
        print("public but no clear placement:", left_out)
    print(f"wrote {out / 'population.json'}")
    return 0


def draw_ids(ids: list[str], n: int = N_SAMPLE, seed: int = SEED) -> list[str]:
    return random.Random(seed).sample(sorted(ids), n)


def preregistered(path: Path = THIS, cwd: Path = ROOT):
    """(commit, commit_time, None) if the file is committed and unchanged, else (None, None, reason)."""
    rel = str(Path(path).resolve().relative_to(Path(cwd).resolve()))

    def git(*a):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)

    log = git("log", "-1", "--format=%H %cI", "--", rel)
    if log.returncode != 0 or not log.stdout.strip():
        return None, None, f"{rel} has no commit yet (git log -1 -- {rel} is empty): commit it first"
    if git("diff", "--quiet", "HEAD", "--", rel).returncode != 0:
        return None, None, f"{rel} differs from HEAD: commit or revert the change first"
    commit, when = log.stdout.split()
    return commit, when, None


def draw(pop_path: Path = PA / "population.json", out: Path = PA / "sample.json") -> int:
    commit, when, why = preregistered()
    if why:
        print(f"REFUSED: the draw must come after the committed script (pre-registration). {why}", file=sys.stderr)
        return 2
    if out.exists():
        print(f"REFUSED: {out} already exists. A sample is drawn once; delete it by hand to start over.", file=sys.stderr)
        return 2
    if not pop_path.exists():
        print(f"REFUSED: {pop_path} missing; run freeze first.", file=sys.stderr)
        return 2
    pop = json.loads(pop_path.read_text())
    if population_sha1(pop["sheets"]) != pop["sha1"]:
        print("REFUSED: population.json does not match its own hash", file=sys.stderr)
        return 2
    by_id = {s["id"]: s for s in pop["sheets"]}
    picked = draw_ids(list(by_id))
    doc = {"drawn_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seed": SEED, "n": N_SAMPLE, "population_n": pop["n"],
           "population_sha1": pop["sha1"], "script_commit": commit, "script_commit_time": when,
           "items": [by_id[i] for i in picked]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    cal = [s["name"] for s in doc["items"] if s["calibration"]]
    print(f"drew {N_SAMPLE} of {pop['n']} with seed {SEED}, script commit {commit[:10]}; wrote {out}")
    print(f"calibration sheets in the sample (kept, flagged, reported apart): {len(cal)} {cal}")
    return 0


# --------------------------------------------------------------------------- geometry of the crops

def edge_point(c: dict, side: str, f: float):
    """The point a fraction f along a side, between its two corners (px)."""
    (x0, y0), (x1, y1) = (c[k] for k in SIDES[side][2])
    return x0 + f * (x1 - x0), y0 + f * (y1 - y0)


def expected_fractions(wgs: dict, side: str) -> list[float]:
    """Where, along a side, the printed ticks should be (every 0.1 g), as fractions 0..1. At most 3,
    spread out. Used only to centre the crops: the labels they imply are never sent to the page."""
    axis, _, (a, b) = SIDES[side]
    k = 0 if axis == "lon" else 1
    ga, gb = ((wgs[c][0] - PARIS) / GRADE if axis == "lon" else wgs[c][1] / GRADE for c in (a, b))
    lo, hi = sorted((ga, gb))
    vals = [i / 10 for i in range(math.ceil(lo * 10), math.floor(hi * 10) + 1)]
    fr = [f for f in ((v - ga) / (gb - ga) for v in vals) if 0.1 <= f <= 0.9]
    fr.sort()
    if len(fr) > TICKS_PER_SIDE:
        fr = [fr[0], fr[len(fr) // 2], fr[-1]]
    return fr


def clip_box(x0, y0, w, h, W, H):
    x0, y0 = max(0, min(round(x0), W - 1)), max(0, min(round(y0), H - 1))
    return x0, y0, min(w, W - x0), min(h, H - y0)


def place_panels(placement: dict, W: int, H: int) -> list[dict]:
    """The strips shown on screen 2: up to 3 per side, each ALONG px along the edge, centred where a tick should be."""
    c, wgs = placement["corners"], placement["wgs84"]
    out = []
    for side in SIDES:
        for k, f in enumerate(expected_fractions(wgs, side)):
            x, y = edge_point(c, side, f)
            if side == "T":
                box = (x - ALONG / 2, y - OUT, ALONG, OUT + IN)
            elif side == "B":
                box = (x - ALONG / 2, y - IN, ALONG, OUT + IN)
            elif side == "L":
                box = (x - OUT, y - ALONG / 2, OUT + IN, ALONG)
            else:
                box = (x - IN, y - ALONG / 2, OUT + IN, ALONG)
            out.append({"side": side, "k": k, "box": clip_box(*box, W, H)})
    return out


def frame_panels(placement: dict, W: int, H: int) -> list[dict]:
    c = placement["corners"]
    pts = [(n, c[n]) for n in CORNERS] + [(s, edge_point(c, s, 0.5)) for s in ("T", "R", "B", "L")]
    out = []
    for name, (x, y) in pts:
        x0 = max(0, min(round(x - FRAME_S / 2), W - FRAME_S))
        y0 = max(0, min(round(y - FRAME_S / 2), H - FRAME_S))
        out.append({"name": name, "box": (x0, y0, min(FRAME_S, W), min(FRAME_S, H))})
    return out


def render_frame(im, panel: dict, corners: dict, raw: bool = False):
    from PIL import Image, ImageDraw

    x0, y0, w, h = panel["box"]
    z = FRAME_ZOOM
    img = im.resize((round(w * z), round(h * z)), Image.LANCZOS).convert("RGB")
    if not raw:
        d = ImageDraw.Draw(img)
        pts = [((corners[n][0] - x0) * z, (corners[n][1] - y0) * z) for n in CORNERS]
        d.line(pts + [pts[0]], fill=(255, 0, 200), width=1)
    return img


def png(img) -> bytes:
    b = BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


# --------------------------------------------------------------------------- scans

class Scans:
    """Where crops come from: the georef script's cached IIIF fetch (R2 first, on disk after)."""

    def __init__(self):
        self.g = georef()
        self.T = self.g.T
        self.sizes: dict[str, tuple[int, int]] = {}

    def size(self, base: str):
        if base not in self.sizes:
            info = self.T.get_image_info(base)
            self.sizes[base] = (info["width"], info["height"])
        return self.sizes[base]

    def crop(self, base: str, x: int, y: int, w: int, h: int):
        return self.g.cached_crop(base, x, y, w, h, w)


# --------------------------------------------------------------------------- the sitting

class Session:
    def __init__(self, sample: dict, out: Path, scans, reviewer: str = "tue"):
        self.sample, self.out, self.scans, self.reviewer = sample, Path(out), scans, reviewer
        self.items = sample["items"]
        self.out.mkdir(parents=True, exist_ok=True)
        self.vf = self.out / "verdicts.jsonl"
        self.lock = threading.Lock()
        self.placements, self.plans, self.warmed = {}, {}, set()
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.cache: OrderedDict = OrderedDict()
        for it in self.items:
            p = json.loads((WORK / f"{it['id']}.json").read_text())
            if corner_hash(p["wgs84"]) != it["hash"]:
                raise SystemExit(f"{it['name']}: the placement changed since the sample was drawn; the draw no longer applies")
            self.placements[it["id"]] = p
        self.ids = [it["id"] for it in self.items]

    # state ---------------------------------------------------------------
    def bound(self, iid: str) -> str:
        p = self.placements[iid]
        return bound_hash(p["wgs84"], f"detector@{p.get('detector_version')}")

    def done(self) -> dict:
        return {k: v for k, v in load(self.vf).items() if not v["verdicts"].get("undone")}

    def plan(self, iid: str):
        if iid not in self.plans:
            it = next(i for i in self.items if i["id"] == iid)
            W, H = self.scans.size(it["iiif_base"])
            p = self.placements[iid]
            self.plans[iid] = {"W": W, "H": H, "frame": frame_panels(p, W, H), "place": place_panels(p, W, H)}
        return self.plans[iid]

    def nxt(self) -> dict:
        done = self.done()
        total = len(self.ids)
        for i, iid in enumerate(self.ids):
            for step in ("frame", "place"):
                if f"{iid}:{step}" in done:
                    continue
                pl = self.plan(iid)
                self.warm(i + 1)
                body = {"id": iid, "i": i, "total": total, "step": step,
                        "done_sheets": sum(f"{x}:place" in done for x in self.ids)}
                if step == "frame":
                    body["panels"] = [{"name": p["name"]} for p in pl["frame"]]
                else:  # image coordinates and counts only: no labels, no lon/lat
                    body["panels"] = [{"side": p["side"], "k": p["k"], "w": p["box"][2], "h": p["box"][3]} for p in pl["place"]]
                return body
        return {"id": None, "total": total, "done_sheets": total}

    # crops ---------------------------------------------------------------
    def image(self, iid: str, kind: str, key: str, raw: bool = False) -> bytes:
        ck = (iid, kind, key, raw)
        with self.lock:
            if ck in self.cache:
                return self.cache[ck]
        pl = self.plan(iid)
        it = next(i for i in self.items if i["id"] == iid)
        if kind == "frame":
            panel = next(p for p in pl["frame"] if p["name"] == key)
            im = self.scans.crop(it["iiif_base"], *panel["box"])
            data = png(render_frame(im, panel, self.placements[iid]["corners"], raw))
        else:
            side, k = key[0], int(key[1:])
            panel = next(p for p in pl["place"] if p["side"] == side and p["k"] == k)
            data = png(self.scans.crop(it["iiif_base"], *panel["box"]).convert("RGB"))  # nothing drawn on it
        with self.lock:
            self.cache[ck] = data
            while len(self.cache) > 300:
                self.cache.popitem(last=False)
        return data

    def warm(self, i: int):
        if i >= len(self.ids) or i in self.warmed:
            return
        self.warmed.add(i)
        iid = self.ids[i]

        def go():
            try:
                pl = self.plan(iid)
                for p in pl["frame"]:
                    self.image(iid, "frame", p["name"])
                for p in pl["place"]:
                    self.image(iid, "place", f"{p['side']}{p['k']}")
            except Exception as e:  # a failed prefetch only costs a wait later
                print(f"prefetch of sheet {i + 1} failed: {e}", file=sys.stderr)

        self.pool.submit(go)

    # verdicts ------------------------------------------------------------
    def submit(self, b: dict) -> dict:
        with self.lock:
            iid, step = b["id"], b["step"]
            if iid not in self.placements or step not in ("frame", "place"):
                raise ValueError("unknown sheet or step")
            order = self.ids.index(iid)
            if f"{iid}:{step}" in self.done():
                raise ValueError("this step already has a verdict (press u to undo it first)")
            t1 = float(b.get("decided_at") or time.time())
            t0 = min(float(b.get("shown_at") or t1), t1)
            note = (b.get("note") or "").strip()
            if step == "frame":
                v = b["verdict"]
                if v not in ("y", "n", "p", "?"):
                    raise ValueError("V-frame keys are y n p ?")
                verdicts, readings, shown = {"frame": v}, {}, True  # the boundary IS the thing judged
            else:
                status = b["status"]
                if status not in ("read", "none", "unsure"):
                    raise ValueError("unknown V-place status")
                if f"{iid}:frame" not in self.done():
                    raise ValueError("V-frame comes first")
                ticks = []
                pl = self.plan(iid)
                for t in b.get("ticks") or []:
                    side, k = t["side"], int(t["k"])
                    panel = next((p for p in pl["place"] if p["side"] == side and p["k"] == k), None)
                    if panel is None:
                        raise ValueError(f"no strip {side}{k}")
                    axis, idx, _ = SIDES[side]
                    x0, y0, w, h = panel["box"]
                    cx, cy = float(t["cx"]), float(t["cy"])
                    if not (0 <= cx <= w and 0 <= cy <= h):
                        raise ValueError("a click lies outside its strip")
                    grades = parse_grades(t["typed"], axis)
                    ticks.append({"side": side, "k": k, "x": round(x0 + cx, 1), "y": round(y0 + cy, 1),
                                  "along": round((x0 + cx) if idx == 0 else (y0 + cy), 1),
                                  "typed": str(t["typed"]).strip(), "grades": grades})
                if status == "read" and not ticks:
                    raise ValueError("no ticks entered: press 0 if none are visible, ? if you cannot tell")
                verdicts, shown = {"place": status}, False  # the machine's line is not on these strips
                readings = {"ticks": ticks if status == "read" else [], "image": [pl["W"], pl["H"]]}
            return record(self.vf, task=TASK, item_id=f"{iid}:{step}", bound=self.bound(iid), reviewer=self.reviewer,
                          order_idx=order, shown_at=t0, decided_at=t1, proposal_shown=shown,
                          verdicts=verdicts, readings=readings, note=note)

    def undo(self, now: float | None = None) -> dict | None:
        with self.lock:
            if not self.vf.exists():
                return None
            lines = [json.loads(x) for x in self.vf.read_text(encoding="utf-8").splitlines() if x.strip()]
            cur = self.done()
            for r in reversed(lines):
                if r["verdicts"].get("undone") or cur.get(r["item_id"], {}).get("written_at") != r["written_at"]:
                    continue
                t = now or time.time()
                return record(self.vf, task=TASK, item_id=r["item_id"], bound=r["bound"], reviewer=self.reviewer,
                              order_idx=r["order_idx"], shown_at=t, decided_at=t, proposal_shown=r["proposal_shown"],
                              verdicts={"undone": True})
            return None


# --------------------------------------------------------------------------- web

PAGE = """<!doctype html><meta charset=utf-8><title>Paper audit 100k</title>
<style>body{font:15px system-ui;margin:10px 14px;background:#222;color:#eee}kbd{background:#444;padding:2px 6px;border-radius:3px}
#st{font-weight:600}#msg{color:#ffb347;min-height:1.3em}.dim{color:#999}
#fr{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}#fr figure{margin:0}#fr img{width:100%;border:1px solid #555;display:block}
#fr figcaption{font-size:12px;color:#999}
#tabs span{display:inline-block;padding:3px 12px;margin-right:6px;background:#333;border-radius:3px}#tabs span.on{background:#2f6fd0}
#pl{display:flex;gap:8px;align-items:flex-start}.pn{position:relative}.pn img{display:block;border:1px solid #555;cursor:crosshair}
.pn.h img{width:calc((100vw - 56px)/3)}.pn .m{position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;border:2px solid #f0f;border-radius:50%;pointer-events:none}
.pn input{width:120px;background:#111;color:#eee;border:1px solid #666;padding:3px;margin-top:3px}#note{width:300px;background:#111;color:#eee;border:1px solid #666;padding:3px}
#sum{margin:6px 0}</style>
<p><span id=st></span> <span id=msg></span></p>
<div id=sf style=display:none><div id=fr></div>
<p class=dim>Is the magenta line on the sheet's printed edge (the neatline)? &nbsp; <kbd>y</kbd> on it &nbsp; <kbd>n</kbd> off &nbsp; <kbd>p</kbd> partly &nbsp; <kbd>?</kbd> cannot tell
&nbsp; <kbd>b</kbd> hold: hide the line &nbsp; <kbd>u</kbd> undo &nbsp; <kbd>t</kbd> note</p></div>
<div id=sp style=display:none><div id=tabs></div><div id=sum></div><div id=pl></div>
<p class=dim>Is the sheet in the right place? Read the printed grades. Click a tick, type its label (118g30 or 118.3), Enter.
Two ticks, 400 px or more apart, on one side for longitude (1 top or 2 bottom) and one for latitude (3 left or 4 right); a second side is a welcome check.<br>
<kbd>1</kbd><kbd>2</kbd><kbd>3</kbd><kbd>4</kbd> / <kbd>Tab</kbd> side &nbsp; <kbd>Enter</kbd> done &nbsp; <kbd>0</kbd> no ticks visible &nbsp; <kbd>?</kbd> cannot tell &nbsp; <kbd>Esc</kbd> in a box: drop the tick &nbsp; <kbd>u</kbd> undo &nbsp; <kbd>t</kbd> note</p></div>
<p><input id=note placeholder="t  note (optional)"></p>
<script>
const $=id=>document.getElementById(id),SIDES=['T','B','L','R'],NAME={T:'top',B:'bottom',L:'left',R:'right'};
let item=null,ticks={},side='T',shownAt=0,loaded=0,need=0,raw=false;
const tkey=(s,k)=>s+k;
function marked(){return item.panels.filter(p=>ticks[tkey(p.side,p.k)])}
function loadOne(){if(++loaded===need&&!shownAt)shownAt=Date.now()/1000}
async function next(){item=await (await fetch('/next')).json();ticks={};side='T';shownAt=0;loaded=0;raw=false;$('msg').textContent='';$('note').value='';
 $('sf').style.display=$('sp').style.display='none';
 if(!item.id){$('st').textContent=`all ${item.total} sheets done - close the tab`;return}
 $('st').textContent=`sheet ${item.i+1} / ${item.total} - ${item.step==='frame'?'V-frame: is the line on the printed edge?':'V-place: read the printed ticks'}`;
 if(item.step==='frame')buildFrame();else buildPlace()}
function buildFrame(){$('sf').style.display='';need=item.panels.length;
 $('fr').innerHTML=item.panels.map(p=>`<figure><img src="/img/${item.id}/frame/${p.name}.png" onload=loadOne()><figcaption>${p.name.length>1?'corner':'mid-edge'} ${p.name}</figcaption></figure>`).join('')}
function buildPlace(){$('sp').style.display='';const first=item.panels.filter(p=>p.side==='T');need=Math.max(1,first.length);
 $('pl').innerHTML=item.panels.map(p=>{const h=p.side==='T'||p.side==='B';return `<div class="pn ${h?'h':''}" data-s=${p.side} data-k=${p.k}>
 <img src="/img/${item.id}/place/${p.side}${p.k}.png" ${p.side==='T'?'onload=loadOne()':''} data-w=${p.w} data-h=${p.h}><div class=m style=display:none></div>
 <input placeholder="label, Enter" style=display:none></div>`}).join('');
 document.querySelectorAll('.pn').forEach(el=>{const img=el.querySelector('img'),inp=el.querySelector('input'),k=tkey(el.dataset.s,el.dataset.k);
  img.onclick=e=>{const r=img.getBoundingClientRect();ticks[k]={cx:(e.clientX-r.left)/r.width*img.dataset.w,cy:(e.clientY-r.top)/r.height*img.dataset.h,typed:(ticks[k]||{}).typed||''};draw();inp.focus();inp.select()};
  inp.oninput=()=>{ticks[k].typed=inp.value;sum()};
  inp.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();inp.blur();sum()}else if(e.key==='Escape'){e.preventDefault();if(!inp.value)delete ticks[k];inp.blur();draw()}e.stopPropagation()}});
 pick('T')}
function pick(s){side=s;draw()}
function draw(){document.querySelectorAll('.pn').forEach(el=>{const s=el.dataset.s,k=tkey(s,el.dataset.k),t=ticks[k],img=el.querySelector('img'),m=el.querySelector('.m'),inp=el.querySelector('input');
  el.style.display=s===side?'':'none';m.style.display=t?'':'none';inp.style.display=t?'':'none';
  if(t){m.style.left=(t.cx/img.dataset.w*100)+'%';m.style.top=(t.cy/img.dataset.h*100)+'%';if(document.activeElement!==inp)inp.value=t.typed}});
 $('tabs').innerHTML=SIDES.map((s,i)=>`<span class="${s===side?'on':''}">${i+1} ${NAME[s]}</span>`).join('');sum()}
function sum(){const c={T:0,B:0,L:0,R:0};for(const k in ticks)if(ticks[k].typed.trim())c[k[0]]++;
 $('sum').textContent='ticks entered - '+SIDES.map(s=>`${NAME[s]} ${c[s]}`).join(' · ')}
async function send(body){const r=await fetch('/verdict',{method:'POST',body:JSON.stringify({id:item.id,step:item.step,shown_at:shownAt||Date.now()/1000,decided_at:Date.now()/1000,note:$('note').value,...body})});
 if(!r.ok){$('msg').textContent=(await r.json()).error;return}next()}
function done(status){const list=[];for(const k in ticks){const t=ticks[k];if(!t.typed.trim()){$('msg').textContent=`type the label of the tick you clicked on ${NAME[k[0]]} strip ${+k.slice(1)+1}, or click in its box and press Esc`;return}
  list.push({side:k[0],k:+k.slice(1),cx:t.cx,cy:t.cy,typed:t.typed})}send({status,ticks:status==='read'?list:[]})}
document.onkeydown=async e=>{
 if(e.target.id==='note'){if(e.key==='Enter'||e.key==='Escape')e.target.blur();return}
 if(e.metaKey||e.ctrlKey||e.altKey||!item||!item.id)return;const k=e.key;
 if(k==='t'){e.preventDefault();$('note').focus();return}
 if(k==='u'){await fetch('/undo',{method:'POST'});return next()}
 if(item.step==='frame'){if('ynp?'.includes(k))send({verdict:k});if(k==='b'&&!e.repeat){raw=!raw;document.querySelectorAll('#fr img').forEach(i=>{i.src=i.src.split('?')[0]+(raw?'?raw=1':'')})}return}
 if('1234'.includes(k)&&k.length===1)pick(SIDES[+k-1]);
 else if(k==='Tab'){e.preventDefault();pick(SIDES[(SIDES.indexOf(side)+1)%4])}
 else if(k==='Enter')done('read');else if(k==='0')done('none');else if(k==='?')done('unsure')};
next();
</script>"""


def make_handler(sess: Session):
    class H(BaseHTTPRequestHandler):
        def send(self, body, ctype="application/json", code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode())

        def do_GET(self):
            u = urlparse(self.path)
            try:
                if u.path == "/":
                    return self.send(PAGE, "text/html; charset=utf-8")
                if u.path == "/next":
                    return self.send(json.dumps(sess.nxt(), ensure_ascii=False))
                if u.path.startswith("/img/"):
                    _, _, iid, kind, name = u.path.split("/")
                    raw = parse_qs(u.query).get("raw") == ["1"]
                    return self.send(sess.image(iid, kind, name.removesuffix(".png"), raw), "image/png")
            except (KeyError, ValueError, IndexError, StopIteration) as e:
                return self.send(json.dumps({"error": str(e)}), code=404)
            self.send("{}", code=404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            try:
                if self.path == "/undo":
                    sess.undo()
                else:
                    sess.submit(body)
            except (KeyError, ValueError, IndexError, TypeError) as e:
                return self.send(json.dumps({"error": str(e)}), code=400)
            self.send("{}")

        def log_message(self, *a):
            pass

    return H


def serve(sample_path: Path, out: Path, port: int, reviewer: str) -> int:
    if not sample_path.exists():
        print(f"{sample_path} missing: run freeze, commit this file, then draw", file=sys.stderr)
        return 2
    sample = json.loads(sample_path.read_text())
    sess = Session(sample, out, Scans(), reviewer)
    sess.warm(0)
    print(f"http://127.0.0.1:{port}  ({len(sess.ids)} sheets, {len(sess.done())} verdicts so far, verdicts to {sess.vf})")
    ThreadingHTTPServer(("127.0.0.1", port), make_handler(sess)).serve_forever()
    return 0


# --------------------------------------------------------------------------- score

def summarize(entries: list[dict]) -> dict:
    def rate(k, n):
        return {"fail": k, "readable": n, "rate": wilson(k, n)}

    fr = [e for e in entries if e["frame"] is not None]
    pl = [e for e in entries if e["place"] is not None]
    f_read = [e for e in fr if e["frame"] != "?"]
    f_fail = sum(e["frame"] in ("n", "p") for e in f_read)
    p_read = [e for e in pl if e["place"] != "unreadable"]
    p_fail = sum(e["place"] == "fail" for e in p_read)
    p_unread = len(pl) - len(p_read)
    flagged = [e["name"] for e in pl if e["place"] == "fail" and e["flags"]]
    return {"sheets": len(entries),
            "v_frame": {**rate(f_fail, len(f_read)), "counts": {k: sum(e["frame"] == k for e in fr) for k in "ynp?"},
                        "unreadable": len(fr) - len(f_read), "fail_n_only": sum(e["frame"] == "n" for e in f_read)},
            "v_place": {**rate(p_fail, len(p_read)), "unreadable": p_unread,
                        "worst_case_unreadable_as_fail": wilson(p_fail + p_unread, len(pl)),
                        "fails_without_flagged_readings": p_fail - len(flagged), "fails_flagged_for_second_look": flagged},
            "either_fails": sum(1 for e in entries if e["frame"] in ("n", "p") or e["place"] == "fail")}


def score(sample_path: Path, out: Path, audit_path: Path = WORK / "printed-audit.json", dest: Path | None = None) -> dict:
    sample = json.loads(sample_path.read_text())
    rows = load(out / "verdicts.jsonl")
    rows = {k: v for k, v in rows.items() if not v["verdicts"].get("undone")}
    entries, stale, fr_rows, pl_rows = [], 0, [], []
    for order, it in enumerate(sample["items"]):
        p = json.loads((WORK / f"{it['id']}.json").read_text())
        want = bound_hash(p["wgs84"], f"detector@{p.get('detector_version')}")
        e = {"id": it["id"], "name": it["name"], "order": order, "calibration": it["calibration"], "frame": None,
             "place": None, "flags": [], "sec_frame": None, "sec_place": None, "detail": None}
        rf, rp = rows.get(f"{it['id']}:frame"), rows.get(f"{it['id']}:place")
        if rf and rf["bound"] != want:
            stale, rf = stale + 1, None
        if rp and rp["bound"] != want:
            stale, rp = stale + 1, None
        if rf:
            e["frame"] = rf["verdicts"]["frame"]
            e["sec_frame"] = rf["decided_at"] - rf["shown_at"]
            fr_rows.append(rf)
        if rp:
            by_side: dict[str, list] = {s: [] for s in SIDES}
            for t in rp["readings"].get("ticks", []):
                by_side[t["side"]].append((t["along"], t["grades"]))
            if rp["verdicts"]["place"] == "read":
                e["detail"] = score_place(p, by_side)
                e["place"], e["flags"] = e["detail"]["outcome"], e["detail"]["flags"]
            else:
                e["place"] = "unreadable"
                e["detail"] = {"outcome": "unreadable", "reason": f"reviewer pressed {'0' if rp['verdicts']['place'] == 'none' else '?'}"}
            e["sec_place"] = rp["decided_at"] - rp["shown_at"]
            pl_rows.append(rp)
        entries.append(e)
    rated = [e for e in entries if e["frame"] is not None or e["place"] is not None]
    cal = [e for e in rated if e["calibration"]]
    blind = [e for e in rated if not e["calibration"]]
    pop_n = sample["population_n"]
    med_f = sittings(fr_rows)
    med_p = sittings(pl_rows)
    per_sheet = [e["sec_frame"] + e["sec_place"] for e in rated if e["sec_frame"] is not None and e["sec_place"] is not None]
    med_total = statistics.median(per_sheet) if per_sheet else None

    def curve(key):
        pts = [(e["order"], round(e[key], 1)) for e in rated if e[key] is not None]
        blocks = {}
        for o, s in pts:
            blocks.setdefault(o // 10, []).append(s)
        return {"by_order": pts, "median_s_per_block_of_10": {f"{10 * b + 1}-{10 * b + 10}": round(statistics.median(v), 1) for b, v in sorted(blocks.items())}}

    result = {
        "task": TASK, "n_sample": len(sample["items"]), "n_with_a_verdict": len(rated), "stale_verdicts_dropped": stale,
        "seed": sample["seed"], "script_commit": sample["script_commit"], "population_n": pop_n, "threshold_m": THRESHOLD_M,
        "all": summarize(rated), "excluding_calibration": summarize(blind),
        "calibration_apart": {"n": len(cal), "sheets": [{"name": e["name"], "v_frame": e["frame"], "v_place": e["place"],
                                                          "edges_m": (e["detail"] or {}).get("edges_m")} for e in cal]},
        "unreadable_apart": [{"name": e["name"], "v_frame": e["frame"], "v_place": e["place"]}
                             for e in rated if e["place"] == "unreadable" or e["frame"] == "?"],
        "seconds_per_sheet": {"v_frame": med_f, "v_place": med_p, "both_median_s": None if med_total is None else round(med_total, 1)},
        "learning_curve": {"v_frame": curve("sec_frame"), "v_place": curve("sec_place")},
        "projection_NOT_MEASURED": {
            "what": "median seconds per sheet (both screens) x the number of sheets, at the same pace, no breaks",
            "hours_whole_frame": None if med_total is None else round(med_total * pop_n / 3600, 1), "frame_n": pop_n,
            "hours_paper_314": None if med_total is None else round(med_total * PAPER_PUBLIC / 3600, 1)},
        "sheets": [{k: e[k] for k in ("name", "order", "calibration", "frame", "place", "sec_frame", "sec_place", "flags", "detail")} for e in rated],
    }
    if audit_path.exists():  # read only
        machine = json.loads(audit_path.read_text()).get("entries", {})
        machine = machine if isinstance(machine, dict) else {m["id"]: m for m in machine}
        cross: dict[str, int] = {}
        agree = n = 0
        for e in rated:
            m, it = machine.get(e["id"]), next(i for i in sample["items"] if i["id"] == e["id"])
            if not m or e["place"] is None or m.get("wgs84_sha1") != it["hash"]:
                continue
            n += 1
            cross[f"human {e['place']} / machine {m['outcome']}"] = cross.get(f"human {e['place']} / machine {m['outcome']}", 0) + 1
            agree += e["place"] == m["outcome"]
        result["agreement_with_machine_audit"] = {
            "overlap_sheets": n, "same_outcome": agree, "table": cross,
            "note": f"printed-audit.json holds {len(machine)} entries; only sampled sheets with the same corner hash count"}
    else:
        result["agreement_with_machine_audit"] = "work/indochine-100k/printed-audit.json not found"
    (dest or out / "paper_audit_100k.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    return result


def print_score(r: dict) -> None:
    for key in ("all", "excluding_calibration"):
        s = r[key]
        print(f"[{key}] sheets {s['sheets']}")
        print(f"  V-frame fail: {s['v_frame']['rate']}  unreadable {s['v_frame']['unreadable']}")
        print(f"  V-place fail: {s['v_place']['rate']}  unreadable {s['v_place']['unreadable']}  "
              f"worst case {s['v_place']['worst_case_unreadable_as_fail']}")
    print(f"calibration sheets apart: {r['calibration_apart']['n']}")
    print(f"seconds per sheet: {r['seconds_per_sheet']}")
    print(f"projection (NOT measured): {r['projection_NOT_MEASURED']}")
    print(f"agreement with machine audit: {r['agreement_with_machine_audit']}")


# --------------------------------------------------------------------------- self-check

def self_check() -> int:
    import tempfile
    import urllib.error
    import urllib.request

    from PIL import Image

    # grades
    assert parse_grades("118g30") == 118.3 and parse_grades("118ᵍ30") == 118.3 and parse_grades("118.30") == 118.3
    assert parse_grades("118,3") == 118.3 and parse_grades("118") == 118.0 and parse_grades("118g03") == 118.03
    for bad in ("", "abc", "118g30g", "9.5"):
        try:
            parse_grades(bad, "lon")
            raise AssertionError(f"accepted {bad!r}")
        except ValueError:
            pass
    assert parse_grades("11g90", "lat") == 11.9

    # a synthetic sheet: 4400 x 5900 px, 8.2 m/px, graticule exactly north-up
    corners = {"NW": [400.0, 700.0], "NE": [4800.0, 700.0], "SE": [4800.0, 6600.0], "SW": [400.0, 6600.0]}
    lon0, lon1, lat0, lat1 = 104.80, 105.15, 13.93, 13.48  # west, east, north, south
    wgs = {"NW": [lon0, lat0], "NE": [lon1, lat0], "SE": [lon1, lat1], "SW": [lon0, lat1]}
    placement = {"corners": corners, "wgs84": wgs, "lines": {}}
    cos = metres_per_degree(13.7)

    def printed_ticks(shift_east_m=0.0, shift_north_m=0.0, jitter=0.0, sides="TBLR", n=3, rng=None):
        """What a careful reader would click if the PRINT lies shift_* metres east/north of the placement."""
        rng = rng or random.Random(1)
        lonp = [lon0 + shift_east_m / cos[0], lon1 + shift_east_m / cos[0]]
        latp = [lat0 + shift_north_m / cos[1], lat1 + shift_north_m / cos[1]]
        out = {}
        for s in sides:
            axis, idx, (a, b) = SIDES[s]
            if axis == "lon":
                ga, gb = ((lonp[0] - PARIS) / GRADE, (lonp[1] - PARIS) / GRADE)
            else:
                ga, gb = latp[0] / GRADE, latp[1] / GRADE
            lo, hi = sorted((ga, gb))
            vals = [i / 10 for i in range(math.ceil(lo * 10), math.floor(hi * 10) + 1)]
            vals = vals if n >= 99 else [vals[0], vals[len(vals) // 2], vals[-1]] if n >= 3 else [vals[0], vals[-1]]
            pa, pb = corners[a][idx], corners[b][idx]
            out[s] = [(pa + (v - ga) / (gb - ga) * (pb - pa) + rng.uniform(-jitter, jitter), round(v, 1)) for v in vals]
        return out

    r0 = score_place(placement, printed_ticks())
    assert r0["outcome"] == "pass" and r0["worst_m"] < 1, r0
    assert score_place(placement, printed_ticks(jitter=4))["outcome"] == "pass", "a 4 px click error is well under 150 m"
    assert score_place(placement, printed_ticks(shift_east_m=100))["outcome"] == "pass", "100 m is under the threshold"
    rw = score_place(placement, printed_ticks(shift_east_m=500))  # print is 500 m east, so the sheet sits 500 m WEST of it
    assert rw["outcome"] == "fail" and abs(rw["edges_m"]["west"] + 500) < 3 and abs(rw["edges_m"]["east"] + 500) < 3, rw
    rs = score_place(placement, printed_ticks(shift_north_m=500))  # sheet 500 m SOUTH of the print
    assert rs["outcome"] == "fail" and abs(rs["edges_m"]["south"] + 500) < 3 and abs(rs["edges_m"]["north"] + 500) < 3, rs
    assert score_place(placement, printed_ticks(shift_east_m=-500))["edges_m"]["west"] > 497, "sign: placed east of the print is +"
    assert score_place(placement, printed_ticks(sides="TL"))["outcome"] == "pass", "one side per axis is enough"
    assert score_place(placement, printed_ticks(sides="TL", n=2))["outcome"] == "pass"
    # unreadable: no latitude side, or ticks too close together, is scored apart, never as a pass
    ru = score_place(placement, printed_ticks(sides="TB"))
    assert ru["outcome"] == "unreadable" and set(ru["missing_edges"]) == {"north", "south"}, ru
    close = printed_ticks()
    close["L"], close["R"] = [(500.0, 12.0), (600.0, 12.1)], []
    assert score_place(placement, close)["outcome"] == "unreadable"
    assert score_place(placement, {})["outcome"] == "unreadable"
    # a failure on a side that was read still counts when the other axis is missing
    only = printed_ticks(shift_east_m=500, sides="TB")
    assert score_place(placement, only)["outcome"] == "fail"
    # a mistyped label is flagged, not hidden
    typo = printed_ticks()
    typo["T"][1] = (typo["T"][1][0], typo["T"][1][1] + 0.1)
    rt = score_place(placement, typo)
    assert rt["outcome"] == "fail" and rt["flags"], rt
    # machine-audit convention: edge deltas of a rectangle equal W=NW lon, N=NW lat
    assert abs(score_place(placement, printed_ticks(shift_east_m=300, shift_north_m=-300))["edges_m"]["north"] - 300) < 3

    # the draw is a function of the seed, and the sample is simple random without replacement
    ids = [f"id{i:03d}" for i in range(337)]
    a = draw_ids(ids)
    assert a == draw_ids(list(reversed(ids))) and len(a) == N_SAMPLE == len(set(a)) and set(a) <= set(ids)
    assert a != draw_ids(ids, seed=SEED + 1)

    # the pre-registration gate, in a throwaway repo
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        sh = lambda *c: subprocess.run(c, cwd=td, capture_output=True, text=True, check=True)
        sh("git", "init", "-q")
        sh("git", "config", "user.email", "t@t")
        sh("git", "config", "user.name", "t")
        f = td / "s.py"
        f.write_text("x = 1\n")
        assert preregistered(f, td)[2] is not None, "an uncommitted file must refuse"
        sh("git", "add", "s.py")
        assert preregistered(f, td)[2] is not None, "a file with no commit must refuse"
        sh("git", "commit", "-qm", "c")
        c, _, why = preregistered(f, td)
        assert why is None and len(c) == 40
        f.write_text("x = 2\n")
        assert preregistered(f, td)[2] is not None, "a changed file must refuse"

    # crops, the server and the verdict log, on a fake scan
    class FakeScans:
        def size(self, base):
            return 5200, 7500

        def crop(self, base, x, y, w, h):
            im = Image.new("RGB", (w, h), (235, 225, 200))
            im.putpixel((w // 2, h // 2), (0, 0, 0))
            return im

    wgs_pl = {**placement, "detector_version": 99}
    it = {"id": "fake-1", "name": "Fake (W)", "hash": corner_hash(wgs), "detector_version": 99, "calibration": False,
          "iiif_base": "x"}
    it2 = {**it, "id": "fake-2", "name": "Fake2 (E)", "calibration": True}
    sample = {"seed": SEED, "n": 2, "population_n": 337, "population_sha1": "x", "script_commit": "0" * 40, "items": [it, it2]}
    pl = place_panels(placement, 5200, 7500)
    assert {p["side"] for p in pl} == set("TBLR") and all(1 <= sum(p["side"] == s for p in pl) <= 3 for s in "TBLR")
    assert all(p["box"][2] <= ALONG + OUT + IN and p["box"][3] <= ALONG + OUT + IN for p in pl)
    t0 = next(p for p in pl if p["side"] == "T")
    assert t0["box"][2:] == (ALONG, OUT + IN) and t0["box"][1] < corners["NW"][1] - 100, "top strips reach 230 px above the rim"
    fp = frame_panels(placement, 5200, 7500)
    assert [p["name"] for p in fp] == list(CORNERS) + ["T", "R", "B", "L"]
    im = FakeScans().crop("x", *fp[0]["box"])
    assert render_frame(im, fp[0], corners).tobytes() != render_frame(im, fp[0], corners, raw=True).tobytes(), "the boundary is drawn"
    assert render_frame(im, fp[0], corners).size == (480, 480)

    real_work = globals()["WORK"]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        globals()["WORK"] = td  # placements are read from WORK
        try:
            for i in (it, it2):
                (td / f"{i['id']}.json").write_text(json.dumps(wgs_pl))
            s = Session(sample, td / "out", FakeScans(), "tester")
            srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(s))
            port = srv.server_address[1]
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"

            def get(path):
                return urllib.request.urlopen(base + path).read()

            def post(path, body):
                req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST")
                try:
                    urllib.request.urlopen(req)
                    return None
                except urllib.error.HTTPError as e:
                    return json.loads(e.read())["error"]

            page = get("/").decode()
            assert "/verdict" in page and "/next" in page
            nx = json.loads(get("/next"))
            assert nx["id"] == "fake-1" and nx["step"] == "frame" and nx["i"] == 0 and len(nx["panels"]) == 8
            # the page data never carries labels, lon/lat, catalogue values or the placement
            for leak in ("wgs84", "lon", "lat", "grades", "113.", "104.8", "105.15", "13.93", "catalogue", "expected"):
                assert leak not in json.dumps(nx), f"/next leaks {leak}"
            assert get("/img/fake-1/frame/NW.png")[:8] == b"\x89PNG\r\n\x1a\n" and get("/img/fake-1/frame/NW.png?raw=1")[:4] == b"\x89PNG"
            assert post("/verdict", {"id": "fake-1", "step": "place", "status": "none"}) == "V-frame comes first"
            assert post("/verdict", {"id": "fake-1", "step": "frame", "verdict": "z"})
            t = 1000.0
            assert post("/verdict", {"id": "fake-1", "step": "frame", "verdict": "y", "shown_at": t, "decided_at": t + 12}) is None
            nx = json.loads(get("/next"))
            assert nx["step"] == "place" and all(set(p) == {"side", "k", "w", "h"} for p in nx["panels"])
            assert get(f"/img/fake-1/place/{nx['panels'][0]['side']}0.png")[:4] == b"\x89PNG"
            assert post("/verdict", {"id": "fake-1", "step": "place", "status": "read", "ticks": []}).startswith("no ticks")
            assert "outside" in post("/verdict", {"id": "fake-1", "step": "place", "status": "read",
                                                  "ticks": [{"side": "T", "k": 0, "cx": 9999, "cy": 5, "typed": "113g3"}]})
            assert "lon range" in post("/verdict", {"id": "fake-1", "step": "place", "status": "read",
                                                    "ticks": [{"side": "T", "k": 0, "cx": 5, "cy": 5, "typed": "5g3"}]})
            # click the true ticks in the T and L strips the server planned (print = placement); one tick per strip
            truth, plan, uniq = printed_ticks(n=99), s.plan("fake-1"), []
            for sd in "TL":
                idx = SIDES[sd][1]
                for q in (q for q in plan["place"] if q["side"] == sd):
                    x0, y0, w, h = q["box"]
                    centre = (x0 + w / 2) if idx == 0 else (y0 + h / 2)
                    along, g = min(truth[sd], key=lambda tg: abs(tg[0] - centre))
                    assert abs(along - centre) < ALONG / 2, "a planned strip holds a tick"
                    uniq.append({"side": sd, "k": q["k"], "cx": (along - x0) if idx == 0 else w / 2,
                                 "cy": h / 2 if idx == 0 else (along - y0), "typed": f"{int(g)}g{round((g % 1) * 100):02d}"})
            assert len(uniq) >= 4
            err = post("/verdict", {"id": "fake-1", "step": "place", "status": "read", "ticks": uniq, "shown_at": t + 12, "decided_at": t + 100})
            assert err is None, (err, uniq)
            assert post("/verdict", {"id": "fake-1", "step": "place", "status": "none"}) is not None, "one verdict per step"
            # undo goes back one step, and the log keeps every line
            assert post("/undo", {}) is None and json.loads(get("/next"))["step"] == "place"
            assert post("/undo", {}) is None and json.loads(get("/next"))["step"] == "frame" and json.loads(get("/next"))["i"] == 0
            assert post("/verdict", {"id": "fake-1", "step": "frame", "verdict": "p", "shown_at": t + 200, "decided_at": t + 210}) is None
            assert post("/verdict", {"id": "fake-1", "step": "place", "status": "unsure", "shown_at": t + 210, "decided_at": t + 230}) is None
            assert post("/verdict", {"id": "fake-2", "step": "frame", "verdict": "?", "shown_at": t + 230, "decided_at": t + 238}) is None
            assert post("/verdict", {"id": "fake-2", "step": "place", "status": "none", "shown_at": t + 238, "decided_at": t + 250}) is None
            assert json.loads(get("/next"))["id"] is None
            lines = [json.loads(x) for x in (td / "out" / "verdicts.jsonl").read_text().splitlines()]
            assert len(lines) == 8 and sum(bool(r["verdicts"].get("undone")) for r in lines) == 2
            frame_line = next(r for r in lines if r["item_id"] == "fake-1:frame")
            assert frame_line["task"] == TASK and frame_line["proposal_shown"] is True and frame_line["bound"] == s.bound("fake-1")
            assert frame_line["bound"] == bound_hash(wgs, "detector@99")
            place_line = next(r for r in lines if r["item_id"] == "fake-1:place")
            assert place_line["proposal_shown"] is False and place_line["readings"]["ticks"], "V-place is blind and keeps the reading"
            assert set(place_line["readings"]["ticks"][0]) == {"side", "k", "x", "y", "along", "typed", "grades"}
            # the first reading (before undo) scored as a pass; recover it to prove clicks -> metres end to end
            first = score_place(placement, {sd: [(t_["along"], t_["grades"]) for t_ in place_line["readings"]["ticks"] if t_["side"] == sd]
                                            for sd in "TBLR"})
            assert first["outcome"] == "pass" and first["worst_m"] < 20, first
            # score from the log (the last lines win: fake-1 frame p, place unsure; fake-2 frame ?, place none)
            sp = td / "sample.json"
            sp.write_text(json.dumps(sample))
            res = score(sp, td / "out", audit_path=td / "none.json", dest=td / "score.json")
            assert res["all"]["v_frame"]["counts"] == {"y": 0, "n": 0, "p": 1, "?": 1}, res["all"]["v_frame"]
            assert res["all"]["v_place"]["unreadable"] == 2 and res["calibration_apart"]["n"] == 1
            assert res["excluding_calibration"]["sheets"] == 1 and res["stale_verdicts_dropped"] == 0
            assert (td / "score.json").exists() and res["projection_NOT_MEASURED"]["hours_paper_314"] is not None
            # a changed placement makes the old verdicts stale, never approved
            (td / "fake-1.json").write_text(json.dumps({**wgs_pl, "detector_version": 100}))
            assert score(sp, td / "out", audit_path=td / "none.json", dest=td / "score.json")["stale_verdicts_dropped"] == 2
            (td / "fake-1.json").write_text(json.dumps(wgs_pl))
            # agreement table against a fake machine audit
            ap_ = td / "pa.json"
            ap_.write_text(json.dumps({"entries": {"fake-2": {"outcome": "pass", "wgs84_sha1": it2["hash"]},
                                                   "fake-1": {"outcome": "pass", "wgs84_sha1": "other"}}}))
            ag = score(sp, td / "out", audit_path=ap_, dest=td / "score.json")["agreement_with_machine_audit"]
            assert ag["overlap_sheets"] == 1 and ag["table"] == {"human unreadable / machine pass": 1} and ag["same_outcome"] == 0, ag
            srv.shutdown()
        finally:
            globals()["WORK"] = real_work
    assert wilson(0, 40).startswith("0.0% [0-9]") and wilson(2, 40).startswith("5.0% [1-17]") and wilson(5, 40).startswith("12.5% [5-26]"), \
        "the docstring's interval widths are stale"
    print("paper_audit_100k self-check OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["freeze", "draw", "serve", "score"])
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--sample", default=str(PA / "sample.json"), help="sample file (serve, score)")
    ap.add_argument("--out", default=str(PA), help="directory for verdicts.jsonl and the score (serve, score)")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--reviewer", default="tue")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    if a.cmd == "freeze":
        return freeze()
    if a.cmd == "draw":
        return draw()
    if a.cmd == "serve":
        return serve(Path(a.sample), Path(a.out), a.port, a.reviewer)
    if a.cmd == "score":
        print_score(score(Path(a.sample), Path(a.out)))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
