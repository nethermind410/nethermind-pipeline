#!/bin/bash
# post.sh — queue a built video on Buffer for YouTube + Instagram + TikTok.
#
#   ./post.sh <id>          DRY RUN: prints exactly what would post, touches nothing
#   ./post.sh <id> --live   uploads to R2 and adds the posts to Buffer's queue
#
# YouTube gets the title + full description; Buffer's API has no tags field, so
# paste youtube_tags into YouTube Studio after it goes live (and the pinned comment).
set -euo pipefail
cd "$(dirname "$0")"

ID="${1:-}"
if [[ -z "$ID" || ! "$ID" =~ ^[a-z0-9_]+$ ]]; then echo "usage: ./post.sh <id> [--live]"; exit 1; fi
PY=.venv/bin/python
FILE=$($PY -c "import json;print(json.load(open('cfg/$ID.json')).get('file','$ID'))")
for f in "out/$FILE.mp4" "out/${ID}_tiktok.mp4" "packaging/$ID.json"; do
  [[ -f "$f" ]] || { echo "missing $f — run ./build.sh $ID and write the packaging first"; exit 1; }
done

ARGS=(--video "out/$FILE.mp4" --tiktok-video "out/${ID}_tiktok.mp4"
      --packaging "packaging/$ID.json" --platforms "youtube,instagram,tiktok")

if [[ "${2:-}" == "--live" ]]; then
  # --record makes this safe to re-run: platforms that already succeeded are skipped
  $PY buffer_post.py "${ARGS[@]}" --record "$ID"
  echo; echo "Still to do by hand once live: YouTube tags + pinned comment (see packaging/$ID.json)."
else
  $PY buffer_post.py "${ARGS[@]}" --dry-run
  echo; echo "That was a dry run. To post for real:  ./post.sh $ID --live"
fi
