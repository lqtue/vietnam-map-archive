"""Publish L909 city photomaps: draft -> public, only rows that already carry a georeference.

    python3 scripts/l909_publish.py                      # dry run: the table, no write
    python3 scripts/l909_publish.py --skip hai-phong-1968 hon-gay --apply

A row without `annotation_url` or `is_georeferenced` is never published: run
`l909_georef.py annotate ... --apply` first (it uploads the annotation, keeps status draft).
The PATCH filters on status=draft, so a row somebody else already changed is left alone.
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(".env")
URL, KEY = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def main(argv):
    skip = set(argv[argv.index("--skip") + 1:]) - {"--apply"} if "--skip" in argv else set()
    scans = [s for s in json.load(open("work/l909/ingested-scans.json"))["scans"] if s["side"] == "recto"]
    todo = []
    for s in scans:
        r = requests.get(f"{URL}/rest/v1/maps", headers=H, timeout=30, params={
            "id": f"eq.{s['id']}", "select": "status,is_georeferenced,annotation_url"}).json()[0]
        if s["slug"] in skip:
            why = "skipped by you"
        elif r["status"] != "draft":
            why = f"already {r['status']}"
        elif not (r["is_georeferenced"] and r["annotation_url"]):
            why = "NO georeference yet: run annotate --apply first"
        else:
            why, _ = "publish", todo.append(s)
        print(f"{s['slug']:28} {r['status']:7} georef={str(r['is_georeferenced']):5} -> {why}")
    if "--apply" not in argv:
        return print(f"\ndry run: {len(todo)} rows would become public (add --apply)")
    for s in todo:
        r = requests.patch(f"{URL}/rest/v1/maps?id=eq.{s['id']}&status=eq.draft", timeout=30,
                           headers={**H, "Prefer": "return=representation"}, json={"status": "public"})
        r.raise_for_status()
        print(f"public: {s['slug']} ({len(r.json())} row)")


if __name__ == "__main__":
    main(sys.argv)
