#!/bin/bash
# refresh.sh — pull every true number the app shows: Buffer (TikTok, Instagram, queue) + YouTube (views, subs, comments),
# then run the learning loop. Exits non-zero if any part failed, so the agent that ran it shows amber.
cd "$(dirname "$0")"
set -o pipefail
PY="${PY:-.venv/bin/python}"
fail=0
echo "=== Buffer";   $PY stats.py | tail -4              || { echo "!! Buffer stats failed"; fail=1; }
echo "=== YouTube";  $PY youtube.py --comments           || { echo "!! YouTube refresh failed"; fail=1; }
echo "=== Learning"; $PY learning.py | tail -3           || { echo "!! learning loop failed"; fail=1; }
exit $fail
