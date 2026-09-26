#!/bin/bash
# package.sh — build a clean, distributable Nether.app + .dmg from the tracked code only.
#
#   ./package.sh                 → dist/Nether.app and dist/Nether-<version>.dmg
#   ./package.sh --no-dmg        → the .app only
#   VERSION=1.1 ./package.sh
#
# What goes in: `git ls-files` (tracked code only) minus everything personal or re-makeable. Never: .env, channel.json,
# channel_nethermind.json, out/, assets/, tts/, cfg/, packaging/, episodes/, inspiration/, music, TOPICS.md,
# LEARNINGS.md, .git, the Kokoro model files, jarvis patches. A check at the end fails the build if any slip through.
#
# The app is NOT self-contained yet: on the buyer's Mac it needs Python 3.12+ with the packages in requirements.txt,
# ffmpeg, and the Kokoro voice files (SETUP.md → "Buyer install"). Its data lives in
# ~/Library/Application Support/Nether (NETHER_DATA), so the bundle itself is never written to.
#
# Signing / notarisation: see docs/PRODUCT.md → "Before selling". Unsigned builds trip Gatekeeper on other Macs.
# If SIGN_ID is set (e.g. "Developer ID Application: Your Name (TEAMID)") the app and dmg are signed with it;
# notarisation is then a manual `xcrun notarytool submit … --wait` + `xcrun stapler staple` (needs your Apple account).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
NAME="Nether"
VERSION="${VERSION:-1.0}"
DIST="$HERE/dist"
APP="$DIST/$NAME.app"
RES="$APP/Contents/Resources/app"

EXCLUDE='^(\.env|channel\.json|channel_nethermind\.json|jarvis_nethermind\.patch|TOPICS\.md|LEARNINGS\.md|ROADMAP\.md|runall\.sh|docs/NETHERMIND\.md|package\.sh|make_app\.sh)$|^(out|assets|tts|cfg|packaging|episodes|inspiration|music|\.github|\.claude)/|\.onnx$|voices-v1\.0\.bin$|^espeak-ng(-data)?/|(^|/)espeak-ng(-data)?$|libespeak-ng\.(dylib|so|a)$'
rm -rf "$APP"; mkdir -p "$RES" "$APP/Contents/MacOS"
git ls-files | grep -Ev "$EXCLUDE" | while IFS= read -r f; do
  mkdir -p "$RES/$(dirname "$f")"; cp -p "$f" "$RES/$f"
done
# the original channel's phone dashboard link lives in app.js; the bundle gets a placeholder ext_setup.js swaps or hides
sed -i '' 's#https://claude.ai/artifact/H7zHPA7sX1urnaWbt9yR7B#\#nx-dashboard#g' "$RES/studio/app.js"
mkdir -p "$RES/music"; cp music/README.txt "$RES/music/" 2>/dev/null || true
cp studio/Nethermind.icns "$APP/Contents/Resources/$NAME.icns"

cat > "$APP/Contents/MacOS/launch" <<'EOF'
#!/bin/bash
# Nether: the code is in Resources/app (read-only); your channel lives in Application Support.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export NETHER_DATA="${NETHER_DATA:-$HOME/Library/Application Support/Nether/Channel}"
mkdir -p "$NETHER_DATA"
unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
APPDIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
PY="$HOME/Library/Application Support/Nether/venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"
exec "$PY" "$APPDIR/app.py" "$@"
EOF
chmod +x "$APP/Contents/MacOS/launch"
cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$NAME</string>
  <key>CFBundleDisplayName</key><string>$NAME</string>
  <key>CFBundleIdentifier</key><string>com.nether.studio</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>$NAME</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.video</string>
  <key>NSHumanReadableCopyright</key><string>See LICENSE</string>
</dict></plist>
EOF

# the guard: nothing personal or secret in the bundle — and no espeak-ng binary/data (GPLv3; must stay a
# separate system install the buyer does themselves, per THIRD_PARTY_NOTICES.md, never shipped inside Nether)
LEAK=$(cd "$RES" && { find . \( -name .env -o -name channel.json -o -name channel_nethermind.json -o -name '*.onnx' -o -path './out/*' \
        -o -path './cfg/*' -o -path './packaging/*' -o -path './assets/*' -o -path './tts/*' -o -name .git \
        -o -name 'espeak-ng*' -o -name 'libespeak-ng*' \) -print; \
        grep -rIl -e 'UCpE0Ce-qXmVWCwwqiW5bvxw' -e '6aaf9711ea19ca0bde942596' -e 'H7zHPA7sX1urnaWbt9yR7B' . || true; })
if [[ -n "$LEAK" ]]; then echo "!! refusing to package — personal files or ids found:"; echo "$LEAK"; rm -rf "$APP"; exit 1; fi
echo "Built $APP ($(du -sh "$APP" | cut -f1)) — $(cd "$RES" && find . -type f | wc -l | xargs) files, nothing personal."

if [[ -n "${SIGN_ID:-}" ]]; then
  codesign --force --deep --options runtime --timestamp --sign "$SIGN_ID" "$APP" && echo "Signed with $SIGN_ID"
fi
[[ "${1:-}" == "--no-dmg" ]] && exit 0
STAGE="$DIST/dmg"; DMG="$DIST/$NAME-$VERSION.dmg"
rm -rf "$STAGE" "$DMG"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"
cp README.md LICENSE "$STAGE/" 2>/dev/null || true
hdiutil create -volname "$NAME $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"
[[ -n "${SIGN_ID:-}" ]] && codesign --force --sign "$SIGN_ID" "$DMG"
echo "Built $DMG ($(du -h "$DMG" | cut -f1)). Unsigned unless SIGN_ID was set — see docs/PRODUCT.md before giving it to anyone."
