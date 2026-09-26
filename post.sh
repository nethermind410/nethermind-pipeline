#!/bin/bash
# post.sh — queue a built video on Buffer for YouTube + Instagram + TikTok.
#
#   ./post.sh <id>          DRY RUN: prints exactly what would post, touches nothing
#   ./post.sh <id> --live   uploads to R2 and adds the posts to Buffer's queue
#
# YouTube gets the title + full description; Buffer's API has no tags field, so
# paste youtube_tags into YouTube Studio after it goes live (and the pinned comment).
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
cd "${NETHER_DATA:-$SRC}"   # the data folder (cfg/, out/, …); the code folder unless NETHER_DATA is set

ID="${1:-}"
if [[ -z "$ID" || ! "$ID" =~ ^[a-z0-9_]+$ ]]; then echo "usage: ./post.sh <id> [--live]"; exit 1; fi
PY="$SRC/.venv/bin/python"; [[ -x "$PY" ]] || PY="$(command -v python3)"
FILE=$($PY -c "import json;print(json.load(open('cfg/$ID.json')).get('file','$ID'))")
LAND=$($PY -c "import json;print(json.load(open('cfg/$ID.json')).get('format','') == 'landscape')")
if [[ "$LAND" == "True" ]]; then          # long-form (16:9): YouTube only, no TikTok cut
  NEED=("out/$FILE.mp4" "packaging/$ID.json")
  ARGS=(--video "out/$FILE.mp4" --packaging "packaging/$ID.json" --platforms "youtube")
else
  NEED=("out/$FILE.mp4" "out/${ID}_tiktok.mp4" "packaging/$ID.json")
  ARGS=(--video "out/$FILE.mp4" --tiktok-video "out/${ID}_tiktok.mp4"
        --packaging "packaging/$ID.json" --platforms "youtube,instagram,tiktok")
fi
for f in "${NEED[@]}"; do
  [[ -f "$f" ]] || { echo "missing $f — build it and write the packaging first"; exit 1; }
done

if [[ "${2:-}" == "--live" ]]; then
  # --record makes this safe to re-run: platforms that already succeeded are skipped
  $PY "$SRC/buffer_post.py" "${ARGS[@]}" --record "$ID"
  echo; echo "Still to do by hand once live: YouTube tags + pinned comment (see packaging/$ID.json)."
else
  $PY "$SRC/buffer_post.py" "${ARGS[@]}" --dry-run
  echo; echo "That was a dry run. To post for real:  ./post.sh $ID --live"
fi
