#!/bin/bash
# Tile a map image and upload to Cloudflare R2 for IIIF self-hosting.
# Usage: ./scripts/tile_map.sh <map-uuid> <source-image-url-or-local-path>
#
# Requirements:
#   - libvips (brew install vips / apt install libvips-tools)
#   - rclone configured with R2 remote named "r2" (see: rclone config)
#   - Optionally: wrangler logged in (wrangler r2 object put as fallback)
#
# After upload, update maps.iiif_image in Supabase to:
#   https://iiif.maparchive.vn/iiif/<map-uuid>

set -euo pipefail

MAP_ID="${1:?Usage: tile_map.sh <map-uuid> <source-image-url-or-path> [original-iiif-base]}"

# ── Fetch from Supabase if missing ──────────────────────────────────────────
if [[ -z "${2:-}" ]]; then
  echo "→ No source provided. Fetching from Supabase..."
  if [ ! -f .env ]; then echo "Error: .env not found"; exit 1; fi
  
  SB_URL=$(grep PUBLIC_SUPABASE_URL .env | cut -d '=' -f2 | tr -d ' "')
  SB_KEY=$(grep SUPABASE_SERVICE_KEY .env | cut -d '=' -f2 | tr -d ' "')
  
  if [[ -z "$SB_URL" ]] || [[ -z "$SB_KEY" ]]; then
    echo "Error: Could not find PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_KEY in .env"
    exit 1
  fi

  # 1. Fetch manifest/info to determine original IIIF image
  # We fetch from the map_iiif_sources to find the non-R2 primary source
  DB_RES=$(curl -s "$SB_URL/rest/v1/map_iiif_sources?map_id=eq.$MAP_ID&is_primary=eq.true" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY")
  
  ORIGINAL_IIIF=$(echo "$DB_RES" | jq -r '.[0].iiif_image' | grep -v "null")
  
  if [[ "$ORIGINAL_IIIF" == *"maparchive.vn"* ]] || [[ "$ORIGINAL_IIIF" == "null" ]]; then
     # Try fetching iiif_image from maps table directly if primary source is already R2
     DB_MAP=$(curl -s "$SB_URL/rest/v1/maps?id=eq.$MAP_ID&select=source_url,iiif_image" \
       -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY")
     # This logic is complex, usually we want the "upstream" source. 
     # For now, let's assume we need the user to provide it if the DB is already updated to R2.
     echo "Error: DB already points to R2. Please provide the original source URL manually."
     exit 1
  fi

  # Determine DOWNLOAD_URL
  if [[ "$ORIGINAL_IIIF" == *"gallica.bnf.fr"* ]]; then
      SOURCE="${ORIGINAL_IIIF%/}/full/full/0/native.jpg"
  else
      SOURCE="${ORIGINAL_IIIF%/}/full/max/0/default.jpg"
  fi
else
  SOURCE="$2"
  ORIGINAL_IIIF="${3:-}"
fi

BUCKET="vma-tiles"
WORKER_BASE="https://iiif.maparchive.vn/iiif"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "→ Map ID: $MAP_ID"
echo "→ Source: $SOURCE"
if [[ -n "$ORIGINAL_IIIF" ]]; then echo "→ Proxy Target: $ORIGINAL_IIIF"; fi

# Download if URL, copy if local path
if [[ "$SOURCE" == http* ]]; then
  echo "→ Downloading source image..."
  # --fail so an upstream error page never lands in source.jpg and dies later as
  # a confusing vips error; --retry because both IA and Gallica flake on
  # full-resolution fetches (504s, truncated transfers, momentary DNS misses)
  # and one flake should not cost the whole map.
  curl -L --fail --retry 5 --retry-all-errors --retry-delay 5 --progress-bar "$SOURCE" -o "$TMPDIR/source.jpg"
else
  cp "$SOURCE" "$TMPDIR/source.jpg"
fi

# Check if file is valid
if [ ! -s "$TMPDIR/source.jpg" ]; then
    echo "Error: Downloaded file is empty. Check your SOURCE URL."
    exit 1
fi

OUTPUT_DIR="$TMPDIR/tiles"
mkdir -p "$OUTPUT_DIR"

echo "→ Tiling with vips (IIIF layout, 256px tiles, Q=85)..."
vips dzsave "$TMPDIR/source.jpg" "$OUTPUT_DIR/source" \
  --layout iiif3 \
  --tile-size 256 \
  --suffix ".jpg[Q=85]"

# dzsave with --layout iiif3 creates a subfolder named after the input file (source).
# We must rename it to the Map ID so the worker can find it at tiles/{id}/info.json
mv "$OUTPUT_DIR/source" "$OUTPUT_DIR/$MAP_ID"

# ── Close the two gaps that make the worker proxy upstream ──────────────────
# The worker renders nothing: a IIIF path it has no key for is fetched from the
# originating library instead. So anything we advertise but do not write becomes
# a silent dependency on that library, and breaks when the library does.
#
# 1. dzsave lists one more scaleFactor than it emits — the top level's single
#    tile is never written. Drop any factor whose origin tile is absent.
#
#    A level's origin tile has two possible spellings, because dzsave uses two:
#    a `0,0,w,h` region while the level still takes more than one tile, and
#    `full/{ceil(W/sf)},{ceil(H/sf)}` for the level that fits in one. Testing
#    only the region spelling trims the top level of every map whose last level
#    is a single tile — which is every map — leaving it advertised one level
#    shallower than it is. 21 Indochine sheets shipped that way: they claimed
#    [1,2,4,8] while `full/166,235` sat in the bucket answering 200, so the
#    renderer clamped a level down and pulled a 2x2 grid where one tile would
#    have done. The same check is spelled again in
#    `work/ocr/scripts/fix_info_scalefactors.py`; change either and change both.
#
#    This runs before the full/200, 400, 800 thumbnails below, but it still
#    tests the exact `w,h` name rather than `full/` itself — a re-tile over an
#    existing directory would otherwise find those thumbnails and keep a level
#    dzsave had not written.
MAP_DIR="$OUTPUT_DIR/$MAP_ID"
if [[ -f "$MAP_DIR/info.json" ]]; then
  W=$(jq -r '.width' "$MAP_DIR/info.json")
  H=$(jq -r '.height' "$MAP_DIR/info.json")
  KEPT=$(for sf in $(jq -r '.tiles[0].scaleFactors[]' "$MAP_DIR/info.json"); do
           span=$((256 * sf))
           tw=$(( span < W ? span : W )); th=$(( span < H ? span : H ))
           # Sizes round up, per axis, independently — same rule the worker's
           # `widthOnlySizeToExplicit` has to reproduce.
           cw=$(( (W + sf - 1) / sf )); ch=$(( (H + sf - 1) / sf ))
           # `|| true` because a factor genuinely absent is the normal case here
           # and its failing test is the pipeline's exit status under pipefail:
           # without this the KEPT assignment fails and set -e kills the script
           # right here, silently, on every map.
           { [[ -d "$MAP_DIR/$tw,$th" || -d "$MAP_DIR/0,0,$tw,$th" ]] ||
             { (( span >= W && span >= H )) && [[ -d "$MAP_DIR/full/$cw,$ch" ]]; }
           } && echo "$sf" || true
         done | jq -sc '.')
  if [[ "$KEPT" != "[]" ]]; then
    echo "→ Advertised scale factors trimmed to $KEPT"
    jq --argjson k "$KEPT" '.tiles[0].scaleFactors = $k | del(.sizes)' \
      "$MAP_DIR/info.json" > "$MAP_DIR/info.json.tmp" && mv "$MAP_DIR/info.json.tmp" "$MAP_DIR/info.json"
  fi
fi

# 2. The only full/ derivative dzsave writes is a ~200px thumbnail named for its
#    own `w,h`, but every caller asks by width: the share page's OG image wants
#    full/800,, and `atWidth` in thumbUrl.ts rewrites the stored URL to full/200,
#    or full/400, for the 48px rail cell and the 96px catalog cell. A width we do
#    not write is a hard 404 for a self-hosted map, because there is no upstream
#    library behind the miss to proxy to — which is how 56 published sheets came
#    to draw nothing in /catalog's grid.
#
#    `--height` is the whole trick. `vips thumbnail in out 800` fits 800 into
#    BOTH axes, so a portrait sheet lands at 615x800: a valid JPEG, at a key that
#    promises width 800, silently the wrong size. Every portrait sheet tiled
#    before this line was fixed is in that state.
#
#    Re-tiling an existing map overwrites these keys, and the worker serves them
#    `immutable` for a year — so a correction here reaches the edge only on a new
#    map id, never on a sheet already mirrored.
for w in 200 400 800; do
  echo "→ Rendering full/$w, derivative..."
  mkdir -p "$MAP_DIR/full/$w,/0"
  vips thumbnail "$TMPDIR/source.jpg" "$MAP_DIR/full/$w,/0/default.jpg[Q=88]" \
    "$w" --height 1000000 --size down
done

echo "→ Uploading to R2 bucket: $BUCKET/tiles/$MAP_ID ..."
rclone copy "$OUTPUT_DIR/$MAP_ID" "r2:$BUCKET/tiles/$MAP_ID" \
  --progress \
  --transfers 8 \
  --checkers 16 \
  --s3-chunk-size 32M

# Write original IIIF source URL so the Worker can proxy on cache miss
if [[ -n "$ORIGINAL_IIIF" ]]; then
  echo "→ Writing proxy source URL to R2..."
  echo -n "${ORIGINAL_IIIF%/}" > "$TMPDIR/source_url.txt"
  rclone copyto "$TMPDIR/source_url.txt" "r2:$BUCKET/sources/$MAP_ID" --s3-no-check-bucket
fi

echo ""
echo "✓ Done. IIIF base URL:"
echo "   $WORKER_BASE/$MAP_ID"
echo ""
echo "Database was updated automatically during mirroring."
echo "If this was a manual rerun, verify maps.iiif_image = '$WORKER_BASE/$MAP_ID'"
