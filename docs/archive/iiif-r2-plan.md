# IIIF Self-Hosting Plan — Cloudflare R2 + Static Tiles

> **Archived.** This plan shipped; the live reference is `docs/admin-tooling.md` §R2 / IIIF worker.
The host below (`iiif.vmaproject.org`) was never used — production is `iiif.maparchive.vn`.

**Goal:** Eliminate dependency on Internet Archive and BnF Gallica IIIF servers going down.
**Approach:** Pre-tile each map once with vips, store tile trees in Cloudflare R2, serve via a
minimal Worker.
**Cost:** ~$0–1/month. **Time:** ~1 day of work.

---

## Architecture

```
Source image (IA / BnF JPEG, stored in Supabase Storage)
    ↓  vips dzsave  (run once per map — local or EC2)
Static tile tree (JPEG tiles + info.json)
    ↓  rclone / wrangler r2 object upload
Cloudflare R2  →  tiles/{mapId}/...
    ↓  Cloudflare Worker (URL rewrite only, ~30 lines)
IIIF Image API  →  https://iiif.vmaproject.org/iiif/{mapId}/...
    ↓  stored in maps.iiif_image
VMA viewer (Allmaps + OpenLayers)
```

**Key insight:** Historical maps never change — pre-tiling once means zero compute at request time.
No pyramidal TIFF needed; `vips dzsave` accepts any JPEG/PNG/TIFF directly.

---

## Components

### 1. Supabase Storage — source archive
- Store original scan JPEGs (one per map) as the authoritative source
- Used as input to re-tile if needed; NOT used for tile serving (egress too expensive)
- Already exists; no new setup needed

### 2. R2 bucket — tile storage
- Bucket: `vma-tiles`
- Key structure: `tiles/{mapId}/{region}/{size}/{rotation}/{quality}.{format}`
- info.json at: `tiles/{mapId}/info.json`
- Zero egress fees — all tile serving is free

### 3. Cloudflare Worker — IIIF endpoint
- Routes: `iiif.vmaproject.org/iiif/{mapId}/...`
- Rewrites IIIF URL path → R2 object key, streams response
- Sets `Cache-Control: immutable` on tiles (tiles never change)
- Sets `Access-Control-Allow-Origin: *` (required for Allmaps)
- ~30 lines of TypeScript, no dependencies

### 4. Tiling script — `scripts/tile_maps.sh` (or `.py`)
- Input: source JPEG (from Supabase Storage URL or local file)
- Command: `vips dzsave source.jpg output/{mapId} --layout iiif --tile-size 256 --suffix .jpg`
- Upload: `wrangler r2 object put` or `rclone copy` to R2
- Update `maps.iiif_image` in Supabase to new Worker URL

---

## Worker Code

```ts
// wrangler.toml binding: TILES → r2 bucket vma-tiles

export default {
  async fetch(request: Request, env: { TILES: R2Bucket }) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET' }
      });
    }

    // /iiif/{mapId}/info.json  or  /iiif/{mapId}/{region}/{size}/{rotation}/{quality}.{format}
    const key = 'tiles' + url.pathname.replace('/iiif', '');
    const obj = await env.TILES.get(key);
    if (!obj) return new Response('Not found', { status: 404 });

    const isJson = key.endsWith('info.json');
    return new Response(obj.body, {
      headers: {
        'Content-Type': isJson ? 'application/json' : 'image/jpeg',
        'Cache-Control': 'public, max-age=31536000, immutable',
        'Access-Control-Allow-Origin': '*',
      }
    });
  }
}
```

---

## Tiling Script

```bash
#!/bin/bash
# Usage: ./scripts/tile_map.sh <map-id> <source-image-url-or-path>
# Requires: libvips, wrangler (logged in), rclone (optional)

MAP_ID=$1
SOURCE=$2
TMPDIR=$(mktemp -d)
OUTPUT="$TMPDIR/$MAP_ID"

echo "→ Downloading source..."
curl -L "$SOURCE" -o "$TMPDIR/source.jpg"

echo "→ Tiling with vips..."
vips dzsave "$TMPDIR/source.jpg" "$OUTPUT" \
  --layout iiif \
  --tile-size 256 \
  --suffix .jpg[Q=85]

echo "→ Uploading to R2..."
# wrangler doesn't support directory upload — use rclone with R2 config
rclone copy "$OUTPUT" "r2:vma-tiles/tiles/$MAP_ID" --progress

echo "→ Done. Image service URL:"
echo "   https://iiif.vmaproject.org/iiif/$MAP_ID"
```

To update `maps.iiif_image` after tiling, run the backfill script or update via admin panel.

---

## Steps

### Phase 1 — Infrastructure (2–3 hrs)
- [ ] Create R2 bucket `vma-tiles` in Cloudflare dashboard
- [ ] Create Worker project `vma-iiif-worker` (wrangler init)
- [ ] Implement Worker (code above), bind R2 bucket
- [ ] Deploy Worker, assign custom domain `iiif.vmaproject.org` (or use `*.workers.dev`)
- [ ] Test with a manually uploaded tile

### Phase 2 — Tiling pipeline (2–3 hrs)
- [ ] Install libvips locally (`brew install vips` / `apt install libvips-tools`)
- [ ] Configure rclone with R2 credentials (Account ID + API token from Cloudflare)
- [ ] Write `scripts/tile_map.sh` (above)
- [ ] Test on one map end-to-end: tile → upload → view in VMA

### Phase 3 — Migrate existing maps (1–2 hrs)
- [ ] Run tiling script for each of the ~20 existing georeferenced maps
- [ ] Update `maps.iiif_image` to the new Worker URL for each
- [ ] Verify tiles load in `/view` and Allmaps overlays render correctly
- [ ] Keep old `iiif_image` URLs in `extra_metadata.iiif_image_original` as fallback reference

### Phase 4 — Integrate into add-map workflow (1 hr)
- [ ] After adding a new map via IIIF manifest in admin, run tiling script
- [ ] Or: add a "Tile & Mirror" button in `MapEditModal` IIIF tab that triggers a server action

---

## Cost Estimate

| Item | Monthly cost |
|------|-------------|
| R2 storage (20 maps × ~500MB tiles = 10GB) | $0.15 |
| R2 Class B reads (tile requests) | Free (first 10M/month) |
| Workers requests | Free (first 100K req/day) |
| Supabase Storage (source JPEGs ~2GB) | Within free tier |
| **Total** | **~$0.15/month** |

Scale to 200 maps: ~$1.50/month.

---

## Pending: Maps to Tile

### btv1b52508901z (BnF Gallica)
mirror-r2 has been run — DB already points to R2
(`maps.iiif_image = https://iiif.maparchive.vn/iiif/<uuid>`).
Tiles not yet uploaded → worker falls back to Gallica proxy → 500s.

Run once rclone + vips are confirmed:
```bash
./scripts/tile_map.sh <map-uuid> \
  "https://gallica.bnf.fr/iiif/ark:/12148/btv1b52508901z/f1/full/full/0/native.jpg" \
  "https://gallica.bnf.fr/iiif/ark:/12148/btv1b52508901z/f1"
```
(`tile_command` was also returned by POST /api/admin/maps/[id]/mirror-r2 — check admin modal Hosting
tab for exact UUID.)

Prerequisites:
- `rclone listremotes` → must show `r2:`
- `vips --version` → must be installed

---

## Notes

- `vips dzsave` with `--layout iiif` outputs IIIF Image API 2.1-compatible tiles
- Input format: any JPEG, PNG, or TIFF — no pyramidal TIFF needed
- BnF Gallica source images: download the highest-res JPEG from the Gallica viewer (not the IIIF
  manifest, which may be slow)
- IA source images: `https://archive.org/download/{identifier}/{file}.jpg`
- Allmaps requires `Access-Control-Allow-Origin: *` on both `info.json` and tile responses
- Tile size 256px is standard; 512px reduces request count for large maps but increases first-tile
  size
- `Q=85` JPEG quality is a good balance for archival maps (color palette is limited)
