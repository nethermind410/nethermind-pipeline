#!/bin/bash
# make_app.sh — (re)build /Applications/Nethermind.app. Safe to re-run (e.g. after a
# Homebrew Python update). The app is a thin shell: all code stays in this folder.
#
# Why a copied python binary: macOS names the Dock icon after the bundle that holds the
# running executable. Running the venv's python directly would show "Python"; a copy
# inside Nethermind.app/Contents/MacOS shows "Nethermind" with our icon. A pyvenv.cfg in
# Contents/ plus a lib/ symlink point that copy at this folder's .venv packages.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="/Applications/Nethermind.app"
PYREAL="$(dirname "$(readlink -f "$HERE/.venv/bin/python")")/../Resources/Python.app/Contents/MacOS/Python"  # the real interpreter; bin/python3.12 re-execs into Python.app, which would name us "Python"
HOMEBIN="$(grep '^home' "$HERE/.venv/pyvenv.cfg" | cut -d= -f2 | xargs)"
VERSION="$(grep '^version' "$HERE/.venv/pyvenv.cfg" | cut -d= -f2 | xargs)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$PYREAL" "$APP/Contents/MacOS/Nethermind"   # the process name macOS shows
ln -s "$HERE/.venv/lib" "$APP/Contents/lib"
cat > "$APP/Contents/pyvenv.cfg" <<EOF
home = $HOMEBIN
include-system-site-packages = false
version = $VERSION
EOF
cp "$HERE/studio/Nethermind.icns" "$APP/Contents/Resources/Nethermind.icns"

cat > "$APP/Contents/MacOS/launch" <<EOF
#!/bin/bash
# Finder gives apps a bare PATH; the pipeline needs Homebrew (ffmpeg) and ~/.local/bin (claude).
export PATH="/opt/homebrew/bin:/usr/local/bin:\$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
exec "\$(dirname "\$0")/Nethermind" "$HERE/app.py"
EOF
chmod +x "$APP/Contents/MacOS/launch"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Nethermind</string>
  <key>CFBundleDisplayName</key><string>Nethermind</string>
  <key>CFBundleIdentifier</key><string>com.nethermind.studio</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>Nethermind</string>
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
