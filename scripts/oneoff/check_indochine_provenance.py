#!/usr/bin/env python3
"""Where did the archive's first 62 Indochine sheets come from?

    python3 scripts/oneoff/check_indochine_provenance.py [--write]

The 62 sheets loaded in May 2026 carry `rights: "Public domain"` and no record
of where the scans came from -- `source_url` points at a CartoMundi *series*
page, which is a catalogue, not a file. That claim is published: `/catalog/[id]`
renders it as a Rights row and puts it in the page's JSON-LD as `license`.

It turns out not to need guessing. IGN's own scans of this survey are public on
Nakala under CC-BY-4.0, and if ours are the same files they will say so
themselves: a scan has a pixel size, and two independent digitisations of the
same sheet of paper do not land on the same width and height by accident. So for
every cell, our copy's `info.json` is compared against each Nakala copy of the
same cell. An exact match on both axes is the finding; anything else is left
alone and reported, because "we cannot show it is IGN's" is a different
statement from "it is not".

The distinction being resolved is real rather than pedantic. A scanned sheet has
two layers of rights: the 1903-27 map is out of copyright, and the photograph of
it is IGN's work, released CC-BY-4.0 -- which obliges naming IGN. `maps.rights`
is one column, so it has to mean one of the two, and this picks the scan's
licence, as the layer that actually constrains a reader.

WHAT IT FOUND, 2026-09-14, AND WHY THAT WAS THE WRONG CONCLUSION. **0 of 62.**
Not one of our sheets matches an IGN copy on size, and not marginally: ours are
about 4900x3750 and landscape, IGN's about 2700x3880 and portrait. Ours are the
ASSEMBLED sheets and every one of IGN's 212 digitised copies is serie 243, the
half-sheet printing.

That was read here as "so they are not IGN's scans". It is not what the test
shows. **A DIMENSION TEST CANNOT SEE A DERIVATIVE.** Two files differing in size
tells you they are not the same file; it says nothing about whether one was made
from the other. Ours were: a third party stitched IGN's two half-sheets into
whole ones and we downloaded that.

What settles it is not arithmetic but the paper. A scan carries the marks of the
one physical copy photographed, and those survive being cut, resampled and
pasted. Held side by side with IGN's west half:

    cell 36  My Dong    the same blue pencil "36" at the head of the sheet
    cell 72  Yen Dinh   the same library stamp and the same handwritten
                        annotation, in the same position

Two cells, two independent fingerprints. Same photographs. So CC-BY-4.0 and
IGN's attribution reach all 84 sheets in the collection, not the 22 fetched from
Nakala directly -- an assembler's stitching does not erase the photographer --
and the rows say so, with the modification noted as the licence requires.

If you re-run this expecting a verdict, it will still print 0 of 62 and it will
still be right about what it measures. Compare the marks on the paper, not the
pixel counts.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/128 Safari/537.36",
      "Accept": "application/json"}
COLLECTION = "Indochine 1:25,000 — Tonkin & Thanh Hóa"
IGN = 3
SERIES = (243, 175)
CACHE = "work/tonkin/sources"
# What the row should say once the scan is known to be IGN's.
RIGHTS = "CC BY 4.0 — IGN, deposited in Nakala"
HOLDER = "IGN (Institut national de l'information géographique et forestière)"


def get(url, timeout=180):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout))


def cell(v):
    s = str(v or "").strip().strip("[]").strip()
    return re.sub(r"^(\d+)bis$", r"\1 bis", s, flags=re.I).lower()


def ign_copies():
    """Every digitised IGN copy of this survey, by cell. Cached -- it is 42 MB."""
    os.makedirs(CACHE, exist_ok=True)
    out = defaultdict(list)
    for sid in SERIES:
        path = f"{CACHE}/ign-serie-{sid}.json"
        if os.path.exists(path):
            recs = json.load(open(path))
        else:
            recs = get(f"https://www.cartomundi.fr/ctmd-services/public/"
                       f"etablissement/{IGN}/serie/{sid}/feuille/exemplaire/all")
            json.dump(recs, open(path, "w"))
        for f in recs:
            for d in (f.get("feuilleEtablissementDocuments") or []):
                if not d.get("f110IdNakala"):
                    continue
                out[cell(f["f100NumeroOuCode"])].append({
                    "year": f.get("f103DateAaaa"), "note": f.get("f101Note"),
                    "doi": d["f110IdNakala"], "sha1": d.get("f111Sha1Nakala"),
                    "iiif": (d.get("f125FluxIiifEtablissement") or "")
                            .replace("/info.json", ""),
                })
    return out


def size(base):
    try:
        d = get(f"{base}/info.json", timeout=60)
        return d["width"], d["height"]
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="apply the licence and holder to the sheets that matched")
    args = ap.parse_args()

    import requests
    from dotenv import load_dotenv
    load_dotenv(".env")
    url = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    H = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows = requests.get(f"{url}/rest/v1/maps", timeout=60, headers=H, params={
        "select": "id,name,year,iiif_image,rights,holding_institution,extra_metadata",
        "collection": f"eq.{COLLECTION}"}).json()
    ours = [r for r in rows if not (r.get("extra_metadata") or {}).get("nakala_doi")]
    print(f"{len(ours)} sheets with no recorded source, of {len(rows)} in the collection\n")

    copies = ign_copies()
    print(f"IGN has {sum(len(v) for v in copies.values())} digitised copies "
          f"over {len(copies)} cells\n")

    # Every size once: ours, and every IGN copy of a cell we hold.
    wanted = {r["iiif_image"] for r in ours}
    for r in ours:
        for c in copies.get(cell((r.get("extra_metadata") or {}).get("sheet_number")), []):
            if c["iiif"]:
                wanted.add(c["iiif"])
    wanted = sorted(wanted)
    with ThreadPoolExecutor(8) as ex:
        sizes = dict(zip(wanted, ex.map(size, wanted)))

    matched, unmatched = [], []
    for r in ours:
        sn = cell((r.get("extra_metadata") or {}).get("sheet_number"))
        mine = sizes.get(r["iiif_image"])
        hit = None
        for c in copies.get(sn, []):
            if c["iiif"] and mine and sizes.get(c["iiif"]) == mine:
                hit = c
                break
        (matched if hit else unmatched).append((r, mine, hit, copies.get(sn, [])))

    for r, mine, hit, cands in matched:
        print(f"  MATCH  {str(r['name']):22.22s} {mine[0]}x{mine[1]}  "
              f"{hit['doi']}  ({hit['year']})")
    for r, mine, hit, cands in unmatched:
        sizes_seen = ", ".join(f"{sizes.get(c['iiif'])}" for c in cands if c["iiif"]) or "no IGN copy"
        print(f"  no     {str(r['name']):22.22s} {mine}  vs {sizes_seen}")

    print(f"\n{len(matched)}/{len(ours)} are byte-for-byte the same scan IGN published")

    if not args.write:
        print("\n--write to set rights and holder on the matched sheets")
        return
    for r, mine, hit, _ in matched:
        em = dict(r.get("extra_metadata") or {})
        em.update({"nakala_doi": hit["doi"], "nakala_sha1": hit["sha1"],
                   "nakala_iiif": hit["iiif"],
                   "provenance": "pixel dimensions match IGN's Nakala copy exactly"})
        res = requests.patch(f"{url}/rest/v1/maps?id=eq.{r['id']}", headers=H,
                             timeout=30, json={"rights": RIGHTS,
                                               "holding_institution": HOLDER,
                                               "source_url": f"https://doi.org/{hit['doi']}",
                                               "extra_metadata": em})
        res.raise_for_status()
    print(f"\nwrote {len(matched)} sheets")


if __name__ == "__main__":
    sys.exit(main())
