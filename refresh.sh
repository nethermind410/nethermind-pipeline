#!/bin/bash
# refresh.sh — pull every true number the app shows: Buffer (TikTok, Instagram, queue) + YouTube (views, subs, comments).
cd "$(dirname "$0")"
PY="${PY:-.venv/bin/python}"
echo "=== Buffer"; $PY stats.py | tail -4
echo "=== YouTube"; $PY youtube.py --comments
echo "=== Learning"; $PY learning.py | tail -3
