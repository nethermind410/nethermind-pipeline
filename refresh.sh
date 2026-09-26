#!/bin/bash
# refresh.sh — pull every true number the app shows: Buffer (TikTok, Instagram, queue) + YouTube (views, subs, comments),
# then run the learning loop. Exits non-zero if any part failed, so the agent that ran it shows amber.
SRC="$(cd "$(dirname "$0")" && pwd)"
cd "${NETHER_DATA:-$SRC}"   # the data folder (cfg/, out/, …); the code folder unless NETHER_DATA is set
set -o pipefail
PY="${PY:-$SRC/.venv/bin/python}"; [[ -x "$PY" ]] || command -v "$PY" >/dev/null || PY="$(command -v python3)"
fail=0
echo "=== Buffer";   $PY "$SRC/stats.py" | tail -4              || { echo "!! Buffer stats failed"; fail=1; }
echo "=== YouTube";  $PY "$SRC/youtube.py" --comments           || { echo "!! YouTube refresh failed"; fail=1; }
echo "=== Learning"; $PY "$SRC/learning.py" | tail -3           || { echo "!! learning loop failed"; fail=1; }
exit $fail
