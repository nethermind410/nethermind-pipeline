#!/bin/bash
# make_app.sh — (re)build /Applications/<app_name>.app for THIS folder (a dev install; app_name from channel.py —
# "Nethermind" on the original install). For a clean app to give or sell, use package.sh. Safe to re-run (e.g. after a
# Homebrew Python update). The app is a thin shell: all code stays in this folder.
#
# Why a copied python binary: macOS names the Dock icon after the bundle that holds the
# running executable. Running the venv's python directly would show "Python"; a copy
# inside Nethermind.app/Contents/MacOS shows "Nethermind" with our icon. A pyvenv.cfg in
# Contents/ plus a lib/ symlink point that copy at this folder's .venv packages.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="$(cd "$HERE" && .venv/bin/python -c 'import channel; print(channel.get("app_name"))' 2>/dev/null || echo Nethermind)"
BUNDLE_ID="com.$(echo "$NAME" | tr -cd '[:alnum:]' | tr '[:upper:]' '[:lower:]').studio"   # com.nethermind.studio on the original install
APP="/Applications/$NAME.app"
PYREAL="$(dirname "$(readlink -f "$HERE/.venv/bin/python")")/../Resources/Python.app/Contents/MacOS/Python"  # the real interpreter; bin/python3.12 re-execs into Python.app, which would name us "Python"
HOMEBIN="$(grep '^home' "$HERE/.venv/pyvenv.cfg" | cut -d= -f2 | xargs)"
VERSION="$(grep '^version' "$HERE/.venv/pyvenv.cfg" | cut -d= -f2 | xargs)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$PYREAL" "$APP/Contents/MacOS/$NAME"   # the process name macOS shows
ln -s "$HERE/.venv/lib" "$APP/Contents/lib"
cat > "$APP/Contents/pyvenv.cfg" <<EOF
home = $HOMEBIN
include-system-site-packages = false
version = $VERSION
EOF
cp "$HERE/studio/Nethermind.icns" "$APP/Contents/Resources/$NAME.icns"

cat > "$APP/Contents/MacOS/launch" <<EOF
#!/bin/bash
# Finder gives apps a bare PATH; the pipeline needs Homebrew (ffmpeg) and ~/.local/bin (claude).
export PATH="/opt/homebrew/bin:/usr/local/bin:\$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
exec "\$(dirname "\$0")/$NAME" "$HERE/app.py"
EOF
chmod +x "$APP/Contents/MacOS/launch"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$NAME</string>
  <key>CFBundleDisplayName</key><string>$NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>$NAME</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.video</string>
</dict></plist>
EOF
touch "$APP"
echo "Built $APP"
