#!/usr/bin/env python3
"""Serve the painting <-> map page and its local IIIF tiles, port 8794.

    python3 work/image-processing/experiments/panorama-match/serve.py work/image-processing
    open http://localhost:8794/experiments/panorama-match/index.html

Tiles live in the gitignored results/panorama-match/favre1881/ (see index.html for the vips line).
CORS plus Chrome's private-network header, so other https pages can read the tiles too.
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


ThreadingHTTPServer(("127.0.0.1", 8794), partial(H, directory=sys.argv[1])).serve_forever()
