#!/bin/bash
# install_daily.sh — run daily.py every day at 7:00 (+ a 20:30 catch-up that only acts if 7:00 failed), via launchd.
#
#   ./install_daily.sh            install (or update) the 7:00 run
#   ./install_daily.sh --remove   stop it
#
# Unlike a scheduled chat, launchd catches up: if the Mac was asleep at 7:00 it runs on wake.
# Output goes to out/daily.log. Replace the Claude app's "Nethermind daily build" task with this,
# or change that task to run `python3 daily.py` — don't run both, or you'll get two videos a day.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
PY="$DIR/.venv/bin/python"; [[ -x "$PY" ]] || PY="$(command -v python3)"
LABEL="$("$PY" -c 'import channel; print(channel.get("launchd_label"))' 2>/dev/null || echo com.nethermind.daily)"   # channel.json
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="${NETHER_DATA:-$DIR}/out"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ "${1:-}" == "--remove" ]]; then rm -f "$PLIST"; echo "Daily run removed."; exit 0; fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/daily.py</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>20</integer><key>Minute</key><integer>30</integer></dict>
  </array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>${NETHER_DATA:+<key>NETHER_DATA</key><string>$NETHER_DATA</string>}</dict>
  <key>StandardOutPath</key><string>$LOGDIR/daily.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/daily.log</string>
</dict></plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Daily run installed: 7:00 every day, 20:30 catch-up if the morning run failed (runs after sleep too). Log: out/daily.log"
echo "Try it now:  $PY daily.py --dry"
