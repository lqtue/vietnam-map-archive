#!/usr/bin/env python3
"""Georeference error per sheet, from the map's own Allmaps annotation.

    python3 work/analysis/district4/georef_error.py --self-check   # no network
    python3 work/analysis/district4/georef_error.py                # the D4 six
    python3 work/analysis/district4/georef_error.py --maps <id> <id> ...

Why this exists: `scale.py` already fetches the annotation and reads the GCPs,
but it only reports metres-per-pixel. It never reports how well the transform
those GCPs imply actually fits them, so every sheet in the archive except 1882
carries a ground resolution and no stated error. `knowledge-alignment.md`'s rule
is that an urban-change claim needs a stated georeference limit; this is what
states it.

The primary figure is **similarity with a y-flip**, because that is the model
Allmaps applies for `helmert`: uniform scale, one rotation, translation, with
image y negated because image y points down. Affine is reported beside it only
to show whether the extra two degrees of freedom buy anything — where they do
not, the scan is undistorted and the survey internally consistent.

Every figure is printed with the scan's pixel dimensions, taken from the same
annotation document the GCPs came from. That is not decoration: the 1959 sheet
has two scans (5000x3790 and 14000x10773) which produced two individually
correct m/px figures that read as a contradiction for weeks. A figure whose
scan is not stated is not checkable.

Self-check at the bottom, no network: `python3 georef_error.py --self-check`.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ocr" / "scripts"))
from scale import (  # noqa: E402
    MIN_GCPS,
    annotation_for_map,
    gcps_from_annotation,
)

MAPS_TXT = Path(__file__).with_name("maps.txt")


@dataclass(frozen=True)
class Fit:
    """One transform fitted to one sheet's GCPs, scored in ground metres."""

    model: str
    rmse_m: float
    worst_m: float
    scale_x: float          # metres per source pixel
    scale_y: float          # equal to scale_x for a similarity
    rotation_deg: float | None   # None for affine: it has no single rotation

    def __str__(self) -> str:
        scale = (f"{self.scale_x:.4f}" if abs(self.scale_x - self.scale_y) < 5e-4
                 else f"{self.scale_x:.4f}/{self.scale_y:.4f}")
        rot = "" if self.rotation_deg is None else f", rot {self.rotation_deg:.2f}deg"
        return (f"{self.model}: {scale} m/px{rot}, "
                f"RMSE {self.rmse_m:.1f} m, worst {self.worst_m:.1f} m")


# WGS84. Used for the radii of curvature below, not for a full projection.
_WGS84_A = 6378137.0
_WGS84_E2 = 2 / 298.257223563 - (1 / 298.257223563) ** 2


def _local_metres(lonlat: np.ndarray) -> np.ndarray:
    """lng/lat -> metres, local tangent plane at the sheet's own latitude.

    Uses the WGS84 **radii of curvature** at that latitude -- meridian `M` for
    the north axis, normal `N * cos(lat)` for the east axis. Verified against
    pyproj UTM 48N on the 1882 sheet: helmert RMSE 12.74 m here against 12.75 m
    there, affine identical to 0.01 m. So this is a real projection's answer
    without the dependency.

    **This is deliberately NOT `scale.metres_per_pixel`'s convention**, and the
    difference is not cosmetic. `scale.py` uses fixed constants (111_132.95 m
    per degree of latitude, 111_320.0 at the equator for longitude) which are
    global means, not local values -- at 10.78 N the true figures are 110_613
    and 109_368. `scale.py` is right to do that: it sizes tiles, needs ~1%, and
    a metre either way is invisible after snapping to a grid. A residual is a
    different job. See the header of `georef_error.md` for what the convention
    was worth: 11.3 m against 12.7 m on the same sheet and the same points.
    """
    phi = math.radians(float(lonlat[:, 1].mean()))
    w = math.sqrt(1 - _WGS84_E2 * math.sin(phi) ** 2)
    m_per_deg_lat = _WGS84_A * (1 - _WGS84_E2) / w ** 3 * math.pi / 180
    m_per_deg_lon = _WGS84_A / w * math.cos(phi) * math.pi / 180
    return lonlat * np.array([m_per_deg_lon, m_per_deg_lat])


def _score(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float]:
    """(RMSE, worst single point), both as 2-D ground distances in metres."""
    d = np.hypot(*(pred - truth).T)
    return float(np.sqrt((d ** 2).mean())), float(d.max())


def fit_similarity(px: np.ndarray, metres: np.ndarray, *, yflip: bool) -> Fit:
    """Uniform scale + rotation + translation, 4 dof, by linear least squares.

    With `yflip`, image y is negated first, which is what Allmaps does and what
    makes the difference between 11 m and 989 m on the 1882 sheet. The model is
    `ground = M @ [x, -y] + t` with `M = [[a, -b], [b, a]]`, which is linear in
    (a, b, tx, ty) -- so this is one lstsq, not an iteration.
    """
    u = px[:, 0]
    v = -px[:, 1] if yflip else px[:, 1]
    n = len(px)

    # Two rows per point: easting then northing.
    design = np.zeros((2 * n, 4))
    design[0::2] = np.column_stack([u, -v, np.ones(n), np.zeros(n)])
    design[1::2] = np.column_stack([v, u, np.zeros(n), np.ones(n)])
    target = metres.reshape(-1)

    (a, b, tx, ty), *_ = np.linalg.lstsq(design, target, rcond=None)
    pred = np.column_stack([a * u - b * v + tx, b * u + a * v + ty])

    rmse, worst = _score(pred, metres)
    scale = float(math.hypot(a, b))
    return Fit(
        model="similarity+yflip" if yflip else "similarity, no yflip",
        rmse_m=rmse,
        worst_m=worst,
        scale_x=scale,
        scale_y=scale,
        rotation_deg=float(math.degrees(math.atan2(b, a))) % 360,
    )


def fit_affine(px: np.ndarray, metres: np.ndarray) -> Fit:
    """Full affine, 6 dof. Reported for comparison only, never as the headline.

    No y-flip argument: an affine absorbs the flip in its own coefficients, so
    fitting it on raw pixels and on flipped pixels gives the same residuals.
    """
    design = np.column_stack([px, np.ones(len(px))])
    coef, *_ = np.linalg.lstsq(design, metres, rcond=None)
    rmse, worst = _score(design @ coef, metres)
    return Fit(
        model="affine 6dof",
        rmse_m=rmse,
        worst_m=worst,
        scale_x=float(np.hypot(coef[0, 0], coef[0, 1])),
        scale_y=float(np.hypot(coef[1, 0], coef[1, 1])),
        rotation_deg=None,
    )


def source_size(ann: dict[str, Any]) -> tuple[int | None, int | None, str]:
    """(width, height, where it came from) for the scan the GCPs were placed on.

    The annotation is asked first and the IIIF `info.json` second, in that order
    and for one reason: the annotation is the document the control points live
    in, so its dimensions are guaranteed to describe the same scan. A size read
    from anywhere else can silently belong to a different scan of the same
    sheet -- which is exactly what happened to the 1959 row for weeks.

    Returns (None, None, reason) rather than guessing. "not established" is a
    real answer here; a made-up one is not.
    """
    target = (ann.get("items") or [{}])[0].get("target") or {}
    for node, label in ((target.get("source") or {}, "annotation target.source"),
                        (target, "annotation target")):
        w, h = node.get("width"), node.get("height")
        if w and h:
            return int(w), int(h), label

    base = (target.get("source") or {}).get("id")
    if not base:
        return None, None, "not established (no target.source.id in annotation)"
    try:
        import requests
        info = requests.get(f"{base.rstrip('/')}/info.json", timeout=20)
        if info.ok:
            d = info.json()
            if d.get("width") and d.get("height"):
                return int(d["width"]), int(d["height"]), "IIIF info.json"
        return None, None, f"not established (info.json HTTP {info.status_code})"
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return None, None, f"not established (info.json failed: {type(exc).__name__})"


def map_rows(map_ids: list[str]) -> dict[str, dict[str, Any]]:
    """year / name / slug per id, so labels never depend on maps.txt order."""
    import requests

    from supabase_client import _headers, _load_config

    url, key = _load_config()
    resp = requests.get(
        f"{url}/rest/v1/maps",
        params={"id": f"in.({','.join(map_ids)})", "select": "id,year,name,slug"},
        headers=_headers(key),
        timeout=20,
    )
    resp.raise_for_status()
    return {r["id"]: r for r in resp.json()}


def measure(map_id: str) -> dict[str, Any]:
    """Every figure for one sheet, or a `skipped` reason. Never raises."""
    ann = annotation_for_map(map_id)
    if not ann:
        return {"id": map_id, "skipped": "no annotation"}

    px, lonlat, declared = gcps_from_annotation(ann)
    if len(px) < MIN_GCPS:
        return {"id": map_id, "skipped": f"only {len(px)} GCPs", "n_gcps": len(px)}

    # Collinear control points fit a line, not a plane. scale.py refuses on this
    # and so do we, but we report the condition number either way so a marginal
    # sheet is visible rather than silently dropped.
    centred = px - px.mean(axis=0)
    sv = np.linalg.svd(centred, compute_uv=False)
    condition = float(sv[-1] / sv[0]) if sv[0] > 0 else 0.0

    metres = _local_metres(lonlat)
    w, h, size_src = source_size(ann)
    return {
        "id": map_id,
        "n_gcps": len(px),
        "declared": declared,
        "condition": condition,
        "width": w,
        "height": h,
        "size_src": size_src,
        "helmert": fit_similarity(px, metres, yflip=True),
        "noflip": fit_similarity(px, metres, yflip=False),
        "affine": fit_affine(px, metres),
    }


# The 1882 sheet. `worked-example-1882.md:40` records RMSE 11.3 m / worst 23.0 m,
# and this script measures 12.7 / 27.7 on the same annotation and the same ten
# points. Neither is a bug: the recorded pair was computed over a SPHERICAL earth
# (R = 6_371_008 m), which reproduces 11.28 / 23.00 here exactly. The figures
# below are the geodetic ones -- WGS84 radii of curvature, cross-checked against
# pyproj UTM 48N to 0.01 m -- and they are the ones to quote.
#
# Note which fit noticed. Affine is 10.58 / 17.41 under EVERY convention tried,
# because six degrees of freedom absorb a wrong lat/lon ratio into the fitted
# coefficients. The similarity has four and cannot, so it is the only one of the
# two that can see an error in the frame it is measured in. That is this
# archive's own thesis turning up inside its own measurement code.
ANCHOR = {
    "id": "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b",
    "m_per_px": 0.3411, "rotation": 89.66, "rmse": 12.74, "worst": 27.72,
    "affine_rmse": 10.59, "affine_worst": 17.42, "noflip_rmse": 985.0,
    "width": 12102, "height": 8982, "n_gcps": 10, "declared": "helmert",
    "superseded": "11.3 / 23.0 in worked-example-1882.md:40, spherical earth",
}


def check_anchor(r: dict[str, Any]) -> list[str]:
    """Differences from the recorded 1882 figures, in plain sentences."""
    if r.get("skipped"):
        return [f"1882 could not be measured: {r['skipped']}"]
    tol = {"m_per_px": 0.002, "rotation": 0.1, "rmse": 0.1, "worst": 0.2,
           "affine_rmse": 0.1, "affine_worst": 0.2, "noflip_rmse": 15.0}
    got = {
        "m_per_px": r["helmert"].scale_x, "rotation": r["helmert"].rotation_deg,
        "rmse": r["helmert"].rmse_m, "worst": r["helmert"].worst_m,
        "affine_rmse": r["affine"].rmse_m, "affine_worst": r["affine"].worst_m,
        "noflip_rmse": r["noflip"].rmse_m,
    }
    out = []
    for k, want in ((k, ANCHOR[k]) for k in tol):
        if abs(got[k] - want) > tol[k]:
            out.append(f"1882 {k}: recorded {want}, measured {got[k]:.4g}")
    for k in ("width", "height", "n_gcps"):
        if r.get(k) != ANCHOR[k]:
            out.append(f"1882 {k}: recorded {ANCHOR[k]}, measured {r.get(k)}")
    return out


def render(results: list[dict[str, Any]], rows: dict[str, dict[str, Any]]) -> str:
    out = ["| year | sheet | GCPs | declared | scan (px) | m/px | rot | "
           "**RMSE** | **worst** | affine RMSE | affine worst |",
           "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        meta = rows.get(r["id"], {})
        year = meta.get("year") or "?"
        name = (meta.get("name") or r["id"])[:38]
        if r.get("skipped"):
            out.append(f"| {year} | {name} | — | — | — | — | — | "
                       f"**{r['skipped']}** | — | — | — |")
            continue
        scan = (f"{r['width']}x{r['height']}" if r["width"]
                else f"*{r['size_src']}*")
        h, a = r["helmert"], r["affine"]
        out.append(
            f"| {year} | {name} | {r['n_gcps']} | {r['declared'] or '—'} | {scan} | "
            f"{h.scale_x:.4f} | {h.rotation_deg:.2f}° | "
            f"**{h.rmse_m:.1f} m** | **{h.worst_m:.1f} m** | "
            f"{a.rmse_m:.1f} m | {a.worst_m:.1f} m |")
    return "\n".join(out)


def _self_check() -> None:
    """Synthetic GCPs with a known transform. No network, no Supabase."""
    rng = np.random.default_rng(0)
    px = rng.uniform(0, 10000, size=(12, 2))

    # Build ground truth from a known similarity WITH the y-flip: 0.5 m/px,
    # rotated 30 degrees, translated. If the fit cannot recover this exactly,
    # nothing downstream means anything.
    s, th = 0.5, math.radians(30.0)
    a, b = s * math.cos(th), s * math.sin(th)
    u, v = px[:, 0], -px[:, 1]
    metres = np.column_stack([a * u - b * v + 1000.0, b * u + a * v - 500.0])

    got = fit_similarity(px, metres, yflip=True)
    assert got.rmse_m < 1e-6, got
    assert got.worst_m < 1e-6, got
    assert abs(got.scale_x - s) < 1e-9, got
    assert abs(got.rotation_deg - 30.0) < 1e-9, got

    # The whole point of the flip: the same data fitted without it is wrong by
    # a lot, and loudly so. This is what a 989 m RMSE on 1882 is telling you.
    blind = fit_similarity(px, metres, yflip=False)
    assert blind.rmse_m > 100.0, blind

    # Affine has 6 dof and absorbs the flip, so it fits this exactly too. It
    # must never look *worse* than the similarity it generalises.
    aff = fit_affine(px, metres)
    assert aff.rmse_m < 1e-6, aff
    assert aff.rmse_m <= got.rmse_m + 1e-9, (aff, got)

    # Noise floor: a known perturbation must come back as roughly itself, not
    # be quietly absorbed. Ten metres of scatter reads as ~10 m RMSE.
    noisy = metres + rng.normal(0, 10.0, size=metres.shape)
    n = fit_similarity(px, noisy, yflip=True)
    assert 5.0 < n.rmse_m < 20.0, n
    assert n.worst_m >= n.rmse_m, n

    # A degenerate case the caller has to see rather than be handed a number
    # for: collinear control points fit a line, and the cross-axis scale they
    # imply is noise. Confirm the condition number collapses so `measure` can
    # flag it.
    line = np.column_stack([np.linspace(0, 9000, 8), np.linspace(0, 9000, 8)])
    sv = np.linalg.svd(line - line.mean(axis=0), compute_uv=False)
    assert sv[-1] / sv[0] < 1e-9, sv

    print("self-check: 6 assertions groups passed, no network used")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true",
                    help="run the synthetic checks and exit; no network")
    ap.add_argument("--maps", nargs="*", default=None,
                    help="map ids (default: work/analysis/district4/maps.txt)")
    # ponytail: archive-wide coverage run (274 maps) needs a durable record per
    # batch rather than only a stdout table, and needs to run in batches rather
    # than one process holding 274 in-flight HTTP calls. --csv appends one row
    # per measured (or skipped) sheet; safe to call once per batch of ids.
    ap.add_argument("--csv", default=None,
                    help="append one row per sheet to this CSV (creates with "
                         "header if absent)")
    args = ap.parse_args()

    if args.self_check:
        _self_check()
        return

    ids = args.maps or [s for s in MAPS_TXT.read_text().strip().split(",") if s]
    results = [measure(i) for i in ids]

    if args.csv:
        import csv as _csv
        path = Path(args.csv)
        is_new = not path.exists()
        try:
            csv_rows = map_rows(ids)
        except Exception:  # noqa: BLE001
            csv_rows = {}
        fields = ["id", "year", "name", "slug", "skipped", "n_gcps", "declared",
                  "condition", "width", "height", "size_src",
                  "helmert_rmse_m", "helmert_worst_m", "helmert_scale_mpp",
                  "helmert_rotation_deg", "noflip_rmse_m",
                  "affine_rmse_m", "affine_worst_m",
                  "affine_scale_x_mpp", "affine_scale_y_mpp"]
        with path.open("a", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=fields)
            if is_new:
                w.writeheader()
            for r in results:
                meta = csv_rows.get(r["id"], {})
                row = {"id": r["id"], "year": meta.get("year"),
                       "name": meta.get("name"), "slug": meta.get("slug"),
                       "skipped": r.get("skipped", "")}
                if not r.get("skipped"):
                    h, a = r["helmert"], r["affine"]
                    row.update({
                        "n_gcps": r["n_gcps"], "declared": r["declared"],
                        "condition": f"{r['condition']:.4f}",
                        "width": r["width"], "height": r["height"],
                        "size_src": r["size_src"],
                        "helmert_rmse_m": f"{h.rmse_m:.2f}",
                        "helmert_worst_m": f"{h.worst_m:.2f}",
                        "helmert_scale_mpp": f"{h.scale_x:.4f}",
                        "helmert_rotation_deg": f"{h.rotation_deg:.2f}",
                        "noflip_rmse_m": f"{r['noflip'].rmse_m:.2f}",
                        "affine_rmse_m": f"{a.rmse_m:.2f}",
                        "affine_worst_m": f"{a.worst_m:.2f}",
                        "affine_scale_x_mpp": f"{a.scale_x:.4f}",
                        "affine_scale_y_mpp": f"{a.scale_y:.4f}",
                    })
                else:
                    row["n_gcps"] = r.get("n_gcps", "")
                w.writerow(row)
    try:
        rows = map_rows(ids)
    except Exception as exc:  # noqa: BLE001
        print(f"(could not read maps.year/name: {type(exc).__name__}: {exc})",
              file=sys.stderr)
        rows = {}

    results.sort(key=lambda r: rows.get(r["id"], {}).get("year") or 9999)
    print(render(results, rows))
    print()

    for r in results:
        if r.get("skipped"):
            continue
        notes = []
        if r["n_gcps"] < 6:
            notes.append(f"only {r['n_gcps']} GCPs")
        if r["condition"] < 0.05:
            notes.append(f"near-collinear GCPs (condition {r['condition']:.3f})")
        if r["declared"] and r["declared"] != "helmert":
            notes.append(f"declared `{r['declared']}`, not helmert — "
                         "a single m/px is an approximation here")
        if not r["width"]:
            notes.append(r["size_src"])
        if notes:
            print(f"- `{r['id'][:8]}`: " + "; ".join(notes))

    anchor = next((r for r in results if r["id"] == ANCHOR["id"]), None)
    if anchor:
        diffs = check_anchor(anchor)
        print()
        if diffs:
            print("**1882 DID NOT REPRODUCE.** Stop and resolve this before "
                  "quoting anything below; either the recorded figure or this "
                  "code is wrong.")
            for d in diffs:
                print(f"  - {d}")
        else:
            print("1882 reproduces the recorded figures "
                  "(docs/worked-example-1882.md:40).")


if __name__ == "__main__":
    main()
