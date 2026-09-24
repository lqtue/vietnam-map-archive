#!/bin/bash
# Tile a map image and upload to Cloudflare R2 for IIIF self-hosting.
#
# Usage: ./scripts/tile_map.sh <map-uuid> <source-image-url-or-local-path>
#                              [original-iiif-base] [--new-version | --version N] [--dry-run]
#
# Requirements:
#   - libvips (brew install vips / apt install libvips-tools)
#   - rclone configured with R2 remote named "r2" (see: rclone config)
#   - Optionally: wrangler logged in (wrangler r2 object put as fallback)
#
# FIRST tiling of a map: no flag. Keys land at tiles/<map-uuid>/ and the IIIF
# image service is https://iiif.maparchive.vn/iiif/<map-uuid>.
#
# RE-TILING a map that is already mirrored: pass --new-version.
#   Tiles go out as `Cache-Control: public, max-age=31536000, immutable`, so an
#   object overwritten in place reaches no reader who already has it for a year.
#   And `rclone copy` never deletes, so a rebuild with fewer levels leaves the
#   old deep levels in the bucket, still answering 200 beside the new ones — a
#   map half one render and half the other, with nothing to see it.
#   The version therefore has to live in the image service id, because that is
#   the only place a IIIF client takes tile URLs from: it derives every one of
#   them from info.json's `id`. A query string or a response header does not
#   propagate. Same discipline as basemap/vietnam-20260906.pmtiles.
#   --new-version writes tiles/<map-uuid>/v<N>/ and prints the service id
#   https://iiif.maparchive.vn/iiif/<map-uuid>/v<N> to put in the database.
#
# Versioning is additive: existing maps stay where they are, nothing is renamed
# or re-uploaded, and the unversioned prefix keeps working forever.
#
# This script never writes to Supabase. The database update is yours to run, and
# it is the step that makes a re-tile reach anyone — it is printed at the end.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: tile_map.sh <map-uuid> [source-image-url-or-path] [original-iiif-base]
                   [--new-version | --version N] [--dry-run]

  --new-version  Re-tile a map that is already mirrored, into the next free
                 version. Asks R2 what is there and takes max+1, so the first
                 re-tile is v2. Writes tiles/<map-uuid>/v<N>/ and touches no
                 existing object.
  --version N    The same prefix, named by hand (N >= 2). For resuming a
                 versioned upload that died halfway, where you need to land on
                 the exact same prefix again rather than a fresh one.
  --dry-run      Print the keys and the service id this run would write, then
                 stop. Downloads nothing, tiles nothing, uploads nothing.

With no version flag nothing changes: keys at tiles/<map-uuid>/, service id
https://iiif.maparchive.vn/iiif/<map-uuid>. That is right for a map's first
tiling and wrong for every re-tile after it — see the header comment.
EOF
}

VERSION=""          # empty = unversioned, i.e. exactly what this script always did
VERSION_MODE=""     # "" | auto | explicit
DRY_RUN=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --new-version)
      VERSION_MODE="auto"; shift ;;
    --version)
      if [[ -z "${2:-}" ]]; then
        echo "Error: --version needs a number (2 or higher)." >&2; exit 1
      fi
      VERSION="$2"; VERSION_MODE="explicit"; shift 2 ;;
    --version=*)
      VERSION="${1#*=}"; VERSION_MODE="explicit"; shift ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    --)
      shift; while [[ $# -gt 0 ]]; do POSITIONAL+=("$1"); shift; done ;;
    -*)
      echo "Error: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    *)
      POSITIONAL+=("$1"); shift ;;
  esac
done
# bash 3.2 (macOS) treats "${a[@]}" on an empty array as unset under `set -u`.
set -- ${POSITIONAL[@]+"${POSITIONAL[@]}"}

if [[ "$VERSION_MODE" == "explicit" ]]; then
  if ! [[ "$VERSION" =~ ^[0-9]+$ ]] || (( VERSION < 2 )); then
    echo "Error: --version takes a whole number, 2 or higher." >&2
    echo "       There is no v1 — a map's first tiling is the unversioned" >&2
    echo "       prefix tiles/<map-uuid>/, and it stays that way." >&2
    exit 1
  fi
fi

MAP_ID="${1:?Usage: tile_map.sh <map-uuid> <source-image-url-or-path> [original-iiif-base]}"

BUCKET="vma-tiles"
WORKER_BASE="https://iiif.maparchive.vn/iiif"

# ── Settle the version before anything expensive happens ────────────────────
# A wrong version is only cheap to fix before the download, and it is the one
# thing here that cannot be corrected afterwards by re-running: the tiles are
# immutable once an id is published.
if [[ "$VERSION_MODE" == "auto" ]]; then
  echo "→ Asking R2 which versions of $MAP_ID already exist..."
  EXISTING=$(rclone lsf --dirs-only "r2:$BUCKET/tiles/$MAP_ID/" 2>/dev/null || true)
  if [[ -z "$EXISTING" ]]; then
    echo "Error: nothing is mirrored at tiles/$MAP_ID/ yet." >&2
    echo "       --new-version re-tiles a map that is already live. A first" >&2
    echo "       tiling takes no flag and belongs at the unversioned prefix." >&2
    exit 1
  fi
  # Directory entries come back with a trailing slash: "v2/", "full/", "0,0,…/".
  LAST=$(printf '%s\n' "$EXISTING" | sed -n 's#^v\([0-9][0-9]*\)/$#\1#p' | sort -n | tail -1)
  VERSION=$(( ${LAST:-1} + 1 ))
  echo "→ Next free version: v$VERSION"
fi

if [[ -n "$VERSION" ]]; then
  DEST_PREFIX="tiles/$MAP_ID/v$VERSION"
  SERVICE_URL="$WORKER_BASE/$MAP_ID/v$VERSION"
else
  DEST_PREFIX="tiles/$MAP_ID"
  SERVICE_URL="$WORKER_BASE/$MAP_ID"
fi

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
  # We fetch from the map_images to find the non-R2 primary source
  DB_RES=$(curl -s "$SB_URL/rest/v1/map_images?map_id=eq.$MAP_ID&is_primary=eq.true" \
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

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "→ Map ID: $MAP_ID"
echo "→ Source: $SOURCE"
if [[ -n "$ORIGINAL_IIIF" ]]; then echo "→ Proxy Target: $ORIGINAL_IIIF"; fi
if [[ -n "$VERSION" ]]; then echo "→ Version: v$VERSION"; fi

if (( DRY_RUN )); then
  echo ""
  echo "── dry run — nothing downloaded, tiled or uploaded ──"
  echo "   R2 prefix:    r2:$BUCKET/$DEST_PREFIX/"
  echo "   info.json:    $DEST_PREFIX/info.json"
  echo "   tile:         $DEST_PREFIX/0,0,1024,1024/256,/0/default.jpg"
  echo "   thumbnails:   $DEST_PREFIX/full/200,/0/default.jpg  (and 400, 800)"
  if [[ -n "$ORIGINAL_IIIF" ]]; then
    echo "   proxy source: sources/$MAP_ID  (one per map, never versioned)"
  fi
  echo "   service id:   $SERVICE_URL"
  exit 0
fi

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
#    `immutable` for a year — so a correction here reaches the edge only under a
#    service id nobody has cached yet. That used to mean a new map id; it now
#    means `--new-version`, which is why a re-tile of a live sheet takes it.
for w in 200 400 800; do
  echo "→ Rendering full/$w, derivative..."
  mkdir -p "$MAP_DIR/full/$w,/0"
  vips thumbnail "$TMPDIR/source.jpg" "$MAP_DIR/full/$w,/0/default.jpg[Q=88]" \
    "$w" --height 1000000 --size down
done

echo "→ Uploading to R2 bucket: $BUCKET/$DEST_PREFIX ..."
rclone copy "$OUTPUT_DIR/$MAP_ID" "r2:$BUCKET/$DEST_PREFIX" \
  --progress \
  --transfers 8 \
  --checkers 16 \
  --s3-chunk-size 32M

# Write original IIIF source URL so the Worker can proxy on cache miss.
# Deliberately unversioned: the upstream library a miss falls back to is a
# property of the map, not of a render, and every version wants the same one.
if [[ -n "$ORIGINAL_IIIF" ]]; then
  echo "→ Writing proxy source URL to R2..."
  echo -n "${ORIGINAL_IIIF%/}" > "$TMPDIR/source_url.txt"
  rclone copyto "$TMPDIR/source_url.txt" "r2:$BUCKET/sources/$MAP_ID" --s3-no-check-bucket
fi

echo ""
if [[ -z "$VERSION" ]]; then
  echo "✓ Done. IIIF base URL:"
  echo "   $WORKER_BASE/$MAP_ID"
  echo ""
  echo "Database was updated automatically during mirroring."
  echo "If this was a manual rerun, verify maps.iiif_image = '$WORKER_BASE/$MAP_ID'"
else
  echo "✓ Tiles written to r2:$BUCKET/$DEST_PREFIX/"
  echo ""
  echo "   NEW IIIF IMAGE SERVICE ID"
  echo "   $SERVICE_URL"
  echo ""
  echo "⚠ Nobody is looking at these tiles, and nobody will until you move the"
  echo "  database row. The old objects under tiles/$MAP_ID/ are untouched and go"
  echo "  out immutable for a year, so every reader still gets the old render; a"
  echo "  IIIF client only ever learns tile URLs from info.json's id, so changing"
  echo "  which id the row names IS the re-render. Until then this upload is inert."
  echo ""
  echo "  Run this yourself against production — this script does not write to"
  echo "  Supabase, on purpose:"
  echo ""
  echo "    update maps"
  echo "       set iiif_image = '$SERVICE_URL',"
  echo "           thumbnail  = '$SERVICE_URL/full/800,/0/default.jpg'"
  echo "     where id = '$MAP_ID';"
  echo ""
  echo "    update map_images"
  echo "       set iiif_image = '$SERVICE_URL'"
  echo "     where map_id = '$MAP_ID'"
  echo "       and iiif_image like '%maparchive.vn%';"
  echo ""
  echo "  Then the georeference: the annotation JSON at maps.annotation_url names"
  echo "  the old service id as its source, so a warped view keeps drawing the old"
  echo "  pixels until that copy is re-pointed at $SERVICE_URL too."
  echo "  Do NOT reach for Mirror to R2 to do it — it rebuilds the base as"
  echo "  $WORKER_BASE/$MAP_ID and would quietly undo both updates above."
  echo "  docs/admin-tooling.md → 'Re-tiling a mirrored map'."
fi
