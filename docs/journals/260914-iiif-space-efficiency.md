# 260914 — IIIF costs nothing in bytes; what it costs is compliance

**Date:** 2026-09-14 · **Severity:** medium · **Component:** tiles / R2 worker · **Status:** two fixes in flight, container choice deferred to F1

The question was whether IIIF tile serving can be made as space- and
serving-efficient as PMTiles. Measured today against the live bucket and the
live service, on one real sheet — map `0775a31e-7dd8-470a-8b06-67bb8707275f`,
2652 × 3753, 230 tiles. Every number below came out of a command, not an
estimate; the commands are here so they can be re-run.

Headline: **bytes were never the problem.** The whole bucket costs about
$0.13/month. What the measurement found instead is that the service advertises
a IIIF level it does not implement, and almost everything its own `info.json`
promises returns 404.

## The bucket census

```bash
for p in tiles overlay originals basemap sources; do
  echo -n "$p  "; rclone size "r2:vma-tiles/$p"
done
```

| prefix | what | bytes | objects |
|---|---|---:|---:|
| `tiles/` | IIIF pyramids, 155 maps | 1.600 GiB | 119,616 |
| `overlay/` | L7014 mosaic, PMTiles | 4.568 GiB | 1 |
| `originals/` | source scans | 1.302 GiB | 181 |
| `basemap/` | vector basemap PMTiles | 1.122 GiB | 5 |
| `sources/` | sidecars | 2.4 KiB | 39 |

So the IIIF tiles are **99.8% of every object in the bucket and 19% of the
bytes**. At R2's $0.015/GB-month the entire bucket is ≈ $0.13/month. Storage
is not a cost to optimise. Object count and filename-guessing are.

## PMTiles saves essentially zero space

Built from the sample sheet's own full-res tiles — reassembled, then re-cut —
so the comparison is against bytes we actually store:

- one archive: **3829 KB**, against **3828 KB** of raw tile bytes
- PMTiles directory overhead: **627 bytes total, 2.73 bytes per tile**
- duplicate-tile dedupe savings: **0.0%**

The dedupe is the interesting zero. PMTiles earns its reputation on vector
basemaps full of identical ocean tiles; a scanned sheet has no two identical
tiles anywhere, so that whole mechanism pays nothing here.

What PMTiles does buy is **230 objects → 1**, and arithmetic instead of
filename-probing.

## The z/x/y mapping is clean

The worry was that a IIIF pyramid's levels would not sit on PMTiles' power-of-two
addressing. They do. Index the top level — the one that fits in a single tile —
as z0, and tiles-across at level z is always ≤ 2^z. Verified on the sample:

| dzsave scale factor | z | tiles |
|---|---|---|
| sf16 | 0 | 1 |
| sf8 | 1 | 2 × 2 |
| sf4 | 2 | 3 × 4 |
| sf2 | 3 | 6 × 8 |
| sf1 | 4 | 11 × 15 |

## Codecs, same sheet, same pyramid

| encoding | size | files |
|---|---:|---:|
| JPEG Q85 (current) | 4268 KB | 231 |
| COG, JPEG Q85, one file | 3703 KB (−13%) | 1 |
| WebP Q80 | 3132 KB (−27%) | 231 |
| AVIF Q55 | 2040 KB (−52%) | 231 |

Most of the COG's 13% is per-tile JPEG header overhead, **measured directly at
5.38% of all tile bytes** — a 1025-byte mean header on an 18.6 kB mean tile —
plus what a shared table saves. The COG holds 165 full-res tiles, mean 16.8 KB,
with a single 142-byte shared `JPEGTables`: arbitrary tile random-access by byte
range, out of one object.

**Caveat, recorded honestly:** the WebP and AVIF figures come from re-encoding
tiles that were already JPEG, so they are directional, not what a re-tile from
the master would produce. The ratio between them is still fair, because all four
encodings share the same source.

## Compliance — the part that matters

Probed live against
`https://iiif.maparchive.vn/iiif/0775a31e-7dd8-470a-8b06-67bb8707275f`:

- **`profile` claims `level2`. It is level0.** `src/lib/core/iiif/level0.ts`
  already says so in its header comment: "do not trust that field".
- **`full/max/0/default.jpg` → 404.** That is the one request level0 *requires*,
  so strictly the service does not meet level0 either.
- **The advertised `sizes` array is fiction.** The worker synthesises it from
  `scaleFactors`, and every entry 404s: `full/2652,3753`, `full/1326,1877`,
  `full/663,939`, `full/332,470`. The only `full/` size actually present —
  `full/166,235` — is not advertised.
- **Only three widths resolve**, the ones `scripts/tile_map.sh` hardcodes:

  | request | status |
  |---|---|
  | `full/200,` | 200 |
  | `full/300,` | 404 |
  | `full/400,` | 200 |
  | `full/500,` | 404 |
  | `full/800,` | 200 |
  | `full/1000,` | 404 |

- Arbitrary region, `pct:` size, rotation, `gray` quality and `.png` format all
  404.

This is contained today for exactly one reason: **our own client never reads
`info.json`.** `level0.ts` reconstructs dzsave's naming rules from first
principles and asks only for URLs it knows exist. The moment anything else
consumes the service — Allmaps, Mirador, a researcher citing it as IIIF — it
breaks, and it breaks while claiming level2.

## Serving

- Worker tiles ship `Cache-Control: public, max-age=31536000, immutable`. A
  re-tile therefore **reaches no existing reader for a year**. Any container
  change has to carry a new URL, not new bytes at the old one.
- `tiles.maparchive.vn` is already an R2 custom domain over the whole bucket,
  and the tile keys already mirror the IIIF path shape —
  `https://tiles.maparchive.vn/tiles/<mapId>/0,0,256,256/256,256/0/default.jpg`
  returns 200, worker bypassed. **But** it answers `cf-cache-status: DYNAMIC`
  with no `cache-control`, so that path is not edge-cached today. It is only a
  win after headers are set at upload (`rclone --header-upload`) or a cache rule
  is added.

## Decisions

1. **Fix `info.json` now.** `profile` → level0, `sizes` verified against what is
   actually in R2, plus `maxWidth` and a `full/max` alias. In progress today.
2. **Versioned image service id for re-tiles**: `/iiif/<mapId>/v<N>`. Additive —
   no migration, existing maps untouched, and it is the answer to the immutable
   year-long cache above. In progress today.
3. **Container choice — PMTiles vs COG — DEFERRED to F1.** The deciding question
   is not size, it is whether on-the-fly rendering (a real level 2) is ever
   wanted. If yes, build COGs: a COG serves a byte-range tile server now *and*
   Cantaloupe or a wasm-in-Worker renderer later. If no, PMTiles is simpler,
   because every stored tile is already a complete JPEG that needs no
   reassembly. Choosing PMTiles now and deciding to render later means tiling
   the whole corpus twice.
4. **One archive per map, never per collection.** Each map has its own pixel
   coordinate space, so there is no shared z/x/y to pack several into.
   `overlay/l7014-*.pmtiles` holds 452 sheets in one archive only because they
   are all warped to one Web Mercator grid — which is precisely what makes it a
   mosaic layer and not a IIIF service.
5. **Series sheets link to the mosaic by bbox for navigation only**, never as a
   substitute for the sheet's own raster. The mosaic is clipped to the neatline
   (no collar, legend or title block), is in Mercator rather than source-pixel
   space (so OCR extractions and Allmaps GCPs cannot address it), bleeds
   neighbouring sheets at a bbox edge, and tops out at ~4.2 m/px.
6. **WebP deferred, and independent of all of the above.** Its argument is
   mobile bandwidth, not storage, so it is only worth bundling into whatever
   re-tiling pass a container change already requires.

## One correction to an earlier draft

An earlier options table costed on-the-fly rendering at ~0.5 GiB, on the
assumption of one flat master per map. **That is wrong.** Decoding a flat 80 MP
JPEG exceeds a Worker's 128 MB isolate limit, so any viable on-the-fly design
still needs a pyramidal master — and lands near the same storage as every other
option. On-the-fly rendering buys compliance, not space.

## Lesson

**A cost question can have a wrong denominator.** The investigation started on
storage, where the answer is $0.13/month and nothing is worth doing. The real
finding was sitting next to it: a service that advertises level2, fails the one
request level0 mandates, and 404s every size its own `info.json` promises — held
together only because the single client that uses it ignores what it says.
