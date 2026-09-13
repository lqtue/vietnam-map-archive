#!/bin/bash
# Bulk upload local JPEGs → R2 IIIF tiles + insert maps/map_iiif_sources rows.
#
# Usage:
#   ./scripts/bulk_upload_local.sh <file-list.txt> [--collection "Service Géographique de l'Indochine"]
#
# file-list.txt: one absolute path per line. Filename pattern parsed as:
#   "<sheet#> <place> <year>.jpg"  → name="<sheet#> <place>", year=<year>
#
# Requires: .env with PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_KEY,
#           rclone "r2:" remote, vips, jq, uuidgen.

set -euo pipefail

FILE_LIST="${1:?Usage: bulk_upload_local.sh <file-list.txt> [--collection ...]}"
COLLECTION="Service Géographique de l'Indochine"
if [[ "${2:-}" == "--collection" ]]; then COLLECTION="${3:-$COLLECTION}"; fi

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then echo "Error: .env not found"; exit 1; fi
SB_URL=$(grep "^PUBLIC_SUPABASE_URL=" .env | cut -d '=' -f2- | tr -d ' "')
SB_KEY=$(grep "^SUPABASE_SERVICE_KEY=" .env | cut -d '=' -f2- | tr -d ' "')
if [[ -z "$SB_URL" || -z "$SB_KEY" ]]; then
  echo "Error: PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_KEY missing"; exit 1
fi

WORKER_BASE="https://iiif.maparchive.vn/iiif"
LOG="scripts/bulk_upload_$(date +%Y%m%d_%H%M%S).log"
echo "→ Log: $LOG"

parse_meta() {
  # $1 = basename without .jpg → echoes "NAME|YEAR|SHEET"
  # NAME has both trailing year and leading sheet number stripped.
  local base="$1"
  local year sheet name
  year=$(echo "$base" | grep -oE '[0-9]{4}$' || true)
  name="$base"
  if [[ -n "$year" ]]; then
    name=$(echo "$name" | sed -E "s/[[:space:]]*$year$//")
  fi
  # Leading "<number>[b]?" optionally followed by '.' (e.g. "20 ", "05b ", "00.")
  sheet=$(echo "$name" | grep -oE '^[0-9]+[a-z]?\.?' | head -1 | sed 's/\.$//' || true)
  if [[ -n "$sheet" ]]; then
    name=$(echo "$name" | sed -E "s/^[0-9]+[a-z]?\.?[[:space:]]*//")
  fi
  name=$(echo "$name" | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')
  echo "${name}|${year}|${sheet}"
}

total=0; ok=0; fail=0
while IFS= read -r path; do
  [[ -z "$path" ]] && continue
  [[ ! -f "$path" ]] && { echo "SKIP (missing): $path" | tee -a "$LOG"; continue; }
  total=$((total+1))

  base=$(basename "$path" .jpg)
  IFS='|' read -r NAME YEAR SHEET <<< "$(parse_meta "$base")"
  MAP_ID=$(uuidgen | tr 'A-Z' 'a-z')

  echo "" | tee -a "$LOG"
  echo "── [$total] $base ──" | tee -a "$LOG"
  echo "   name=$NAME  year=${YEAR:-?}  sheet=${SHEET:-?}  uuid=$MAP_ID" | tee -a "$LOG"

  # 1) Insert maps row
  extra_json='{}'
  if [[ -n "$SHEET" ]]; then
    extra_json=$(jq -nc --arg s "$SHEET" '{sheet_number: $s}')
  fi
  insert_payload=$(jq -n \
    --arg id "$MAP_ID" --arg name "$NAME" \
    --arg col "$COLLECTION" \
    --argjson year "${YEAR:-null}" \
    --argjson extra "$extra_json" \
    '{
      id: $id,
      name: $name,
      year: $year,
      collection: $col,
      source_type: "self",
      status: "draft",
      map_type: "topographic",
      extra_metadata: $extra
    }')
  resp=$(curl -s -w "\n%{http_code}" -X POST "$SB_URL/rest/v1/maps" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
    -H "Content-Type: application/json" -H "Prefer: return=representation" \
    -d "$insert_payload")
  body=$(echo "$resp" | sed '$d'); code=$(echo "$resp" | tail -1)
  if [[ "$code" != "201" ]]; then
    echo "   ✗ maps insert failed ($code): $body" | tee -a "$LOG"
    fail=$((fail+1)); continue
  fi

  # 2) Tile + upload to R2 (no original-iiif-base; this is the origin)
  if ! ./scripts/tile_map.sh "$MAP_ID" "$path" 2>&1 | tee -a "$LOG"; then
    echo "   ✗ tile_map.sh failed" | tee -a "$LOG"
    fail=$((fail+1)); continue
  fi

  IIIF_URL="$WORKER_BASE/$MAP_ID"

  # 3) Insert map_iiif_sources row (primary, self-hosted)
  src_payload=$(jq -n --arg map_id "$MAP_ID" --arg url "$IIIF_URL" \
    '{ map_id: $map_id, label: "R2 (self-hosted)", source_type: "self",
       iiif_image: $url, is_primary: true, sort_order: 0 }')
  resp=$(curl -s -w "\n%{http_code}" -X POST "$SB_URL/rest/v1/map_iiif_sources" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
    -H "Content-Type: application/json" -H "Prefer: return=representation" \
    -d "$src_payload")
  body=$(echo "$resp" | sed '$d'); code=$(echo "$resp" | tail -1)
  if [[ "$code" != "201" ]]; then
    echo "   ✗ map_iiif_sources insert failed ($code): $body" | tee -a "$LOG"
    fail=$((fail+1)); continue
  fi

  # 4) Thumbnail URL.
  #
  # NOT from info.json's `sizes`. The worker computes that array from the
  # pyramid's scaleFactors, so it advertises sizes as available that no one ever
  # wrote to R2 — `vips dzsave` emits tiles plus two `full/` derivatives and
  # nothing else. Taking the smallest listed size gave every map a thumbnail
  # that 404s, and for a self-hosted map there is no upstream IIIF server behind
  # the miss to proxy to, so `stepDown` in thumbUrl.ts ran out of fallbacks and
  # the row showed no picture at all.
  #
  # 800 is what dzsave actually writes and what every other row in the archive
  # stores, which is also the width thumbUrl.ts treats as the guaranteed one.
  THUMB_URL="${IIIF_URL}/full/800,/0/default.jpg"
  if ! curl -sf -o /dev/null "$THUMB_URL"; then
    echo "   ! thumbnail 404s: $THUMB_URL" | tee -a "$LOG"
    THUMB_URL=""
  fi

  # 5) Derive allmaps_id via @allmaps/id (SHA-1 hex first 16 of canonical IIIF URL).
  ALLMAPS_ID=$(node -e "import('@allmaps/id').then(async m => { const u = process.argv[1].replace(/\/(info\.json)?\$/, '').replace(/\/+\$/, ''); process.stdout.write(await m.generateId(u)); })" "$IIIF_URL" 2>/dev/null || echo "")

  # 6) Update maps.iiif_image (+ thumbnail + allmaps_id). Trigger on map_iiif_sources also syncs iiif_image; redundant but safe.
  patch_payload=$(jq -nc --arg url "$IIIF_URL" --arg thumb "$THUMB_URL" --arg aid "$ALLMAPS_ID" \
    '{iiif_image: $url}
     + (if $thumb == "" then {} else {thumbnail: $thumb} end)
     + (if $aid   == "" then {} else {allmaps_id: $aid}  end)')
  curl -s -X PATCH "$SB_URL/rest/v1/maps?id=eq.$MAP_ID" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
    -H "Content-Type: application/json" \
    -d "$patch_payload" > /dev/null

  echo "   ✓ $IIIF_URL${THUMB_URL:+ (thumb ok)}${ALLMAPS_ID:+ (allmaps=$ALLMAPS_ID)}" | tee -a "$LOG"
  ok=$((ok+1))
done < "$FILE_LIST"

echo "" | tee -a "$LOG"
echo "═══ Done: $ok ok / $fail fail / $total total ═══" | tee -a "$LOG"
