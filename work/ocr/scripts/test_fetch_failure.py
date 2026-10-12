#!/usr/bin/env python3
"""A refused IIIF request must fail the job, not read as "nothing there".

Gallica answers 403 (a Cloudflare challenge) or 429 to a client it has decided
to stop serving. If that came back from fetch_crop / get_image_info as an empty
image, or if ocr.py carried on after losing tiles, the run would finish with 0
labels and `ocr_done` - the same row a blank sheet produces. docs/lessons.md:
"A refused probe reads exactly like a probe that was answered 'no'."

No network, no API calls, no Supabase.

    python test_fetch_failure.py
"""
import tempfile
from pathlib import Path

import iiif_tiles
import ocr


class _Refused:
    def __init__(self, status):
        self.status_code = status
        self.ok = False
        self.content = b"<html>challenge</html>"

    def raise_for_status(self):
        import requests
        raise requests.HTTPError(f"{self.status_code} Client Error")

    def json(self):
        raise ValueError("not json")


def _raises(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except Exception as e:  # SystemExit is not an Exception subclass; handled below
        return e
    return None


iiif_tiles.CACHE_DIR = Path(tempfile.mkdtemp())
iiif_tiles.time.sleep = lambda s: None
BASE = "https://gallica.example/iiif/ark:/12148/btv1bTEST/f1"

for status in (403, 429, 500):
    iiif_tiles.requests.get = lambda *a, _s=status, **k: _Refused(_s)
    iiif_tiles._INFO_CACHE.clear()
    assert _raises(iiif_tiles.get_image_info, BASE) is not None, f"info.json {status} must raise"
    err = _raises(iiif_tiles.fetch_crop, BASE, 0, 0, 100, 100, size=64)
    assert err is not None, f"fetch_crop {status} must raise, not return an image"

# Lost tiles end the run before anything is written.
ocr._fail_on_tile_errors([], 4)  # a clean run passes
try:
    ocr._fail_on_tile_errors([("0_0_100_100", "403")], 4)
except SystemExit as e:
    assert "1 of 4" in str(e)
else:
    raise AssertionError("tile errors must exit non-zero")

print("test_fetch_failure.py ok")
