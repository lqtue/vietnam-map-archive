#!/usr/bin/env python3
"""Turn hand-pinned corners into Allmaps georeference annotations.

The nine city sheets are already tiled to R2 and serving IIIF, so the only thing
standing between them and appearing warped on /explore is an annotation. That
annotation is a small JSON document — four control points, a mask and a
transformation — and we have all three from `pin.html`. Writing it directly
skips a pass through the Allmaps Editor that would only re-collect what has
already been collected, and the four corners are the same four either way.

    python3 scripts/l7014_annotate.py            # what it would do
    python3 scripts/l7014_annotate.py --write    # upload and point the rows at it

Needs PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY in .env.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORK = Path("work/l7014")
CITY = {"6330-4", "6330-1", "6330-2", "6330-3", "6329-1",
        "6329-4", "6541-4", "6641-3", "6350-4"}
CORNERS = ("NW", "NE", "SE", "SW")
BUCKET = "annotations"


def env():
    out = {}
    for line in (Path(".env").read_text().splitlines() if Path(".env").exists() else []):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    url = os.environ.get("PUBLIC_SUPABASE_URL") or out.get("PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or out.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_KEY not found")
    return url.rstrip("/"), key


def req(url, key, method="GET", body=None, ctype="application/json", extra=None):
    data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body else None)
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("apikey", key)
    r.add_header("Authorization", f"Bearer {key}")
    if data:
        r.add_header("Content-Type", ctype)
    for k, v in (extra or {}).items():
        r.add_header(k, v)
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read()
    return json.loads(raw) if raw and raw[:1] in b"[{" else raw


def plain(url):
    """A fetch with no Supabase headers on it. Two separate 403s live here: the
    IIIF worker refuses a request carrying someone else's apikey, which is what
    a single shared helper sent, and Cloudflare refuses `Python-urllib` by user
    agent before the worker sees it at all."""
    r = urllib.request.Request(url, headers={
        "User-Agent": "vma-l7014/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as f:
        return json.loads(f.read())


def annotation(map_id, iiif, w, h, pin):
    """One georeference annotation, in the shape the Allmaps renderer reads.

    Two choices worth naming. The transformation is a first-order polynomial,
    not a projective: four corners fit a projective *exactly*, so a pixel of
    pinning error would be reproduced faithfully as perspective instead of being
    averaged away, and the sheets were measured as having no perspective to
    recover (opposite edges agree to 0.25%). And the mask is the neatline quad,
    which is what stops the paper margin, the title block and the legend from
    being painted over the neighbouring sheets.
    """
    poly = " ".join(f"{round(pin['pixels'][c][0])},{round(pin['pixels'][c][1])}"
                    for c in CORNERS)
    return {
        "type": "AnnotationPage",
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "items": [{
            "id": f"{iiif}/annotation",
            "type": "Annotation",
            "@context": [
                "http://iiif.io/api/extension/georef/1/context.json",
                "http://iiif.io/api/presentation/3/context.json",
            ],
            "motivation": "georeferencing",
            "target": {
                "type": "SpecificResource",
                "source": {"id": iiif, "type": "ImageService3", "width": w, "height": h},
                "selector": {
                    "type": "SvgSelector",
                    "value": f'<svg width="{w}" height="{h}"><polygon points="{poly}" /></svg>',
                },
            },
            "body": {
                "type": "FeatureCollection",
                "transformation": {"type": "polynomial", "options": {"order": 1}},
                "features": [
                    {"type": "Feature",
                     "properties": {"resourceCoords": [round(pin["pixels"][c][0]),
                                                       round(pin["pixels"][c][1])]},
                     "geometry": {"type": "Point",
                                  "coordinates": [round(pin["ground"][c][0], 7),
                                                  round(pin["ground"][c][1], 7)]}}
                    for c in CORNERS
                ],
            },
        }],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="upload and update the rows")
    args = ap.parse_args()

    base, key = env()
    pins = json.loads((WORK / "pins.json").read_text())
    rows = req(f"{base}/rest/v1/maps?select=id,name,iiif_image,annotation_url,georef_done"
               f"&collection=eq.Series%20L7014%20(Vietnam%201:50,000)", key)
    # A cell can now carry two rows — PCL's scan and Texas Tech's, which are
    # different editions of the same sheet number. They are told apart by the
    # ", ed." the second one's name carries, and pinned under a "@ttu" key,
    # because the pixel corners belong to the scan and not to the cell.
    by_sheet = {}
    for m in rows:
        name = m["name"] or ""
        for s in CITY:
            if f"L7014 {s}" in name:
                by_sheet[f"{s}@ttu" if ", ed." in name else s] = m

    missing = CITY - {k.split("@")[0] for k in by_sheet}
    if missing:
        print(f"no maps row for: {', '.join(sorted(missing))}")

    done = 0
    for sheet in sorted(by_sheet):
        m = by_sheet[sheet]
        pin = pins.get(sheet)
        if not pin:
            print(f"  {sheet}: not pinned, skipped")
            continue
        info = plain(f"{m['iiif_image']}/info.json")
        ann = annotation(m["id"], m["iiif_image"], info["width"], info["height"], pin)
        out = WORK / "annotations" / f"{m['id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(ann, indent=1))
        note = f"  {sheet}  {info['width']}x{info['height']}  -> {out.name}"
        if not args.write:
            print(note + "   (dry run)")
            continue
        url = f"{base}/storage/v1/object/{BUCKET}/{m['id']}.json"
        try:
            req(url, key, "POST", out.read_bytes(), extra={"x-upsert": "true"})
        except urllib.error.HTTPError as e:
            if e.code != 400:
                raise
            req(url, key, "PUT", out.read_bytes(), extra={"x-upsert": "true"})
        public = f"{base}/storage/v1/object/public/{BUCKET}/{m['id']}.json"
        req(f"{base}/rest/v1/maps?id=eq.{m['id']}", key, "PATCH",
            {"annotation_url": public, "georef_done": True})
        print(note + "   uploaded, row updated")
        done += 1
    print(f"\n{done if args.write else len(by_sheet)} sheets "
          f"{'written' if args.write else 'ready'}")


if __name__ == "__main__":
    main()
