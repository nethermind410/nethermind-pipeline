#!/bin/bash
# build.sh — one command, one finished video.
#
#   ./build.sh <id>            fetch → generate → render (main + tiktok) → QA → thumbnail
#   ./build.sh <id> --no-fetch skip fetch_real / gen_visuals (assets already in place)
#
# <id> is the cfg/<id>.json name. The TikTok config is (re)generated from the main one
# every run, so edit only cfg/<id>.json. Stops at the first failing step.
set -euo pipefail
cd "$(dirname "$0")"

ID="${1:-}"
if [[ -z "$ID" || ! "$ID" =~ ^[a-z0-9_]+$ || ! -f "cfg/$ID.json" ]]; then
  echo "usage: ./build.sh <id>   (cfg/<id>.json must exist)"; exit 1
fi
PY="${PY:-.venv/bin/python}"   # CI sets PY=python3
command -v "$PY" >/dev/null || { echo "missing $PY — see README (.venv)"; exit 1; }
step() { echo; echo "=== $1  $(date +%T)"; }

if [[ "${2:-}" != "--no-fetch" ]]; then
  step "real photos (fetch_real)";   $PY fetch_real.py "cfg/$ID.json"
  step "generated art (gen_visuals)"; $PY gen_visuals.py "cfg/$ID.json"
fi

step "tiktok config"
$PY - "$ID" <<'EOF'
import json, sys
vid = sys.argv[1]
c = json.load(open(f"cfg/{vid}.json"))
c["id"] = c["file"] = f"{vid}_tiktok"
lines = c.get("end", {}).get("lines", [])
if lines and lines[0].upper().startswith("SUBSCRIBE"):
    lines[0] = "FOLLOW FOR MORE"
with open(f"cfg/{vid}_tiktok.json", "w") as f:
    json.dump(c, f, indent=1, ensure_ascii=False); f.write("\n")
print(f"  wrote cfg/{vid}_tiktok.json")
EOF

for C in "$ID" "${ID}_tiktok"; do
  step "render $C";  $PY make_short.py "cfg/$C.json" | tail -2
  step "QA $C";      $PY qa_render.py "cfg/$C.json" | tail -3
done

if [[ -f "packaging/$ID.json" ]] && grep -q '"thumbnail"' "packaging/$ID.json"; then
  step "thumbnail"; $PY make_thumb.py "packaging/$ID.json"
else
  echo; echo "!! no packaging/$ID.json with a \"thumbnail\" block — thumbnail skipped"
fi

if [[ -z "${CI:-}" ]]; then
  step "asset bundle (for the GitHub render workflow)"
  $PY bundle_assets.py "$ID" || echo "!! bundle upload failed — local build is still fine"
fi

echo; echo "DONE $ID — look at out/${ID}_qa_contact.jpg before posting."
