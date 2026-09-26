#!/bin/bash
# build.sh — one command, one finished video.
#
#   ./build.sh <id>            fetch → generate → render (main + tiktok) → QA → thumbnail
#   ./build.sh <id> --no-fetch skip fetch_real / gen_visuals (assets already in place)
#
# <id> is the cfg/<id>.json name. The TikTok cut is (re)generated from the main one by
# retention.py every run, so edit only cfg/<id>.json. Stops at the first failing step.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
cd "${NETHER_DATA:-$SRC}"   # the data folder (cfg/, out/, …); the code folder unless NETHER_DATA is set

ID="${1:-}"
if [[ -z "$ID" || ! "$ID" =~ ^[a-z0-9_]+$ || ! -f "cfg/$ID.json" ]]; then
  echo "usage: ./build.sh <id>   (cfg/<id>.json must exist)"; exit 1
fi
PY="${PY:-$SRC/.venv/bin/python}"; [[ -x "$PY" ]] || command -v "$PY" >/dev/null || PY="$(command -v python3)"   # CI sets PY=python3
command -v "$PY" >/dev/null || { echo "missing $PY — see README (.venv)"; exit 1; }
EP=$($PY -c "import json;c=json.load(open('cfg/$ID.json'));print(c.get('episode','') if c.get('format')=='landscape' else '')")
if [[ -n "$EP" ]]; then                    # a long-form video is rebuilt from its episode by make_long.py
  exec $PY "$SRC/make_long.py" "episodes/$EP.json"
fi
# report to NETHER (orchestrator.py): one Production task per build, one step per stage,
# so a failure shows which stage broke and its last lines. Reporting never stops a build.
mkdir -p out/logs; LOG="out/logs/build_$ID.log"; : > "$LOG"
exec > >(tee -a "$LOG") 2>&1
RETRY=$([[ "${2:-}" == "--no-fetch" ]] && echo build_nofetch || echo build)
TASK=$($PY "$SRC/orchestrator.py" begin production "Build $ID" --video "$ID" --retry "{\"action\":\"$RETRY\",\"id\":\"$ID\"}" 2>/dev/null || true)
finish() { code=$?; [[ -n "$TASK" ]] && $PY "$SRC/orchestrator.py" end "$TASK" "$code" "$LOG" 2>/dev/null || true; exit $code; }
trap finish EXIT
step() { echo; echo "=== $1  $(date +%T)"; [[ -n "$TASK" ]] && $PY "$SRC/orchestrator.py" step "$TASK" "$1" 2>/dev/null || true; }

if [[ "${2:-}" != "--no-fetch" ]]; then
  step "real photos (fetch_real)";   $PY "$SRC/fetch_real.py" "cfg/$ID.json"
  step "generated art (gen_visuals)"; $PY "$SRC/gen_visuals.py" "cfg/$ID.json"
fi

step "tiktok config (retention cut)"
# retention.py: number on frame 0, punch-in, tight gaps, no still held over ~6s,
# follow end card. Tag beats "in": ["short"] in cfg/<id>.json to leave them out.
$PY "$SRC/retention.py" tiktok "cfg/$ID.json" --max 35 | sed -n '/_tiktok.json  —/,$p;/^!/,/re-run/p'

step "narration (your voice where recorded)"
$PY "$SRC/voice.py" apply "cfg/$ID.json"
$PY "$SRC/voice.py" apply "cfg/${ID}_tiktok.json"

for C in "$ID" "${ID}_tiktok"; do
  if [[ "$C" == *_tiktok ]]; then
    # reuse the main narration: only beats the cut splits get re-narrated
    mkdir -p "tts/$C" && cp -n tts/"$ID"/* "tts/$C/" 2>/dev/null || true
  fi
  step "render $C";  $PY "$SRC/make_short.py" "cfg/$C.json" | tail -2
  step "QA $C";      $PY "$SRC/qa_render.py" "cfg/$C.json" | tail -3
done

if [[ -f "packaging/$ID.json" ]] && grep -q '"thumbnail"' "packaging/$ID.json"; then
  step "thumbnail"; $PY "$SRC/make_thumb.py" "packaging/$ID.json"
else
  echo; echo "!! no packaging/$ID.json with a \"thumbnail\" block — thumbnail skipped"
fi

if [[ -z "${CI:-}" ]]; then
  step "asset bundle (for the GitHub render workflow)"
  $PY "$SRC/bundle_assets.py" "$ID" || echo "!! bundle upload failed — local build is still fine"
fi

echo; echo "DONE $ID — look at out/${ID}_qa_contact.jpg before posting."
