"""The georeference annotation every series pipeline writes, built once.

Tonkin, Indochine 100k, L7014 (scan and PDF) and L909 each carried their own copy
of this, identical in shape and drifting in detail (pixel rounding, mask source).
Build it here; store it with `scripts/georef_write.mjs`, never by hand.

Two choices every caller has relied on. The default transformation is a
first-order polynomial, not a projective: four corners fit a projective
*exactly*, so a pixel of detection error is reproduced as perspective instead of
averaged away, and these sheets were measured as having none to recover. And the
mask is the neatline (or rim) quad, which stops the paper margin, the title block
and the legend from being painted over the neighbouring sheets.
"""


def polynomial(order):
    return {"type": "polynomial", "options": {"order": order}}


def annotation(iiif, w, h, gcps, mask, transformation=None, ndigits=0):
    """`gcps` is [((x, y), (lon, lat)), ...] in the pixel grid of the `w`x`h` scan
    at `iiif`; `mask` is [(x, y), ...]. `transformation` is an Allmaps dict
    (`polynomial(2)`, `{"type": "thinPlateSpline"}`, `{"type": "helmert"}`); None
    is a first-order polynomial. Pixels round to `ndigits` (0 = integers)."""
    px = (lambda v: round(float(v))) if ndigits == 0 else (lambda v: round(float(v), ndigits))
    poly = " ".join(f"{px(x)},{px(y)}" for x, y in mask)
    return {
        "type": "AnnotationPage",
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "items": [{
            "id": f"{iiif}/annotation",
            "type": "Annotation",
            "@context": ["http://iiif.io/api/extension/georef/1/context.json",
                         "http://iiif.io/api/presentation/3/context.json"],
            "motivation": "georeferencing",
            "target": {
                "type": "SpecificResource",
                "source": {"id": iiif, "type": "ImageService3", "width": w, "height": h},
                "selector": {"type": "SvgSelector",
                             "value": f'<svg width="{w}" height="{h}"><polygon points="{poly}" /></svg>'},
            },
            "body": {
                "type": "FeatureCollection",
                "transformation": transformation or polynomial(1),
                "features": [
                    {"type": "Feature",
                     "properties": {"resourceCoords": [px(x), px(y)]},
                     "geometry": {"type": "Point",
                                  "coordinates": [round(float(lon), 7), round(float(lat), 7)]}}
                    for (x, y), (lon, lat) in gcps
                ],
            },
        }],
    }


def store(files, apply=False, replace_public=False, origin="script"):
    """Hand annotation files (each `<map-uuid>.json`) to georef_write.mjs. Dry unless `apply`.

    Returns True when every file passed. A refused file (exit 3) is reported, not
    raised: the others were still stored. Anything else the writer exits with is."""
    import subprocess
    if not files:
        return True
    cmd = ["node", "--env-file=.env", "scripts/georef_write.mjs", "--origin", origin]
    cmd += (["--apply"] if apply else []) + (["--replace-public"] if replace_public else [])
    code = subprocess.run(cmd + [str(f) for f in files]).returncode
    if code not in (0, 3):
        raise SystemExit(f"georef_write.mjs failed (exit {code})")
    return code == 0


if __name__ == "__main__":
    a = annotation("https://iiif.example/x", 100, 80,
                   [((0, 0), (106.1, 10.9)), ((99.6, 0), (106.2, 10.9)), ((99, 79), (106.2, 10.8))],
                   [(0, 0), (99.6, 0), (99, 79)])
    item = a["items"][0]
    assert item["body"]["features"][1]["properties"]["resourceCoords"] == [100, 0]
    assert 'points="0,0 100,0 99,79"' in item["target"]["selector"]["value"]
    assert annotation("u", 1, 1, [((1.26, 2), (0, 0))], [(1.26, 2)], ndigits=1)[
        "items"][0]["body"]["features"][0]["properties"]["resourceCoords"] == [1.3, 2.0]
    assert item["body"]["transformation"] == {"type": "polynomial", "options": {"order": 1}}
    tps = {"type": "thinPlateSpline"}
    assert annotation("u", 1, 1, [], [], tps)["items"][0]["body"]["transformation"] == tps
    assert annotation("u", 1, 1, [], [], polynomial(2))["items"][0]["body"]["transformation"][
        "options"]["order"] == 2
    print("ok")
