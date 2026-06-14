#!/bin/bash
set -e

VERSION="${1:-0.1.0}"
DIR=$(mktemp -d)
PKG_NAME="codex-tray_${VERSION}_all.deb"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Directory structure
mkdir -p "$DIR/DEBIAN"
mkdir -p "$DIR/usr/share/codex-tray"
mkdir -p "$DIR/usr/bin"
mkdir -p "$DIR/usr/share/applications"
mkdir -p "$DIR/etc/xdg/autostart"

# Copy source files
cp "$SCRIPT_DIR/codex_tray.py" "$DIR/usr/share/codex-tray/"
cp "$SCRIPT_DIR/usage_tracker.py" "$DIR/usr/share/codex-tray/"
cp "$SCRIPT_DIR/icon_renderer.py" "$DIR/usr/share/codex-tray/"
cp "$SCRIPT_DIR/config.py" "$DIR/usr/share/codex-tray/"

# Create wrapper script
cat > "$DIR/usr/bin/codex-tray" << 'SCRIPT'
#!/bin/bash
exec /usr/bin/python3 /usr/share/codex-tray/codex_tray.py "$@"
SCRIPT
chmod 755 "$DIR/usr/bin/codex-tray"

# Copy desktop file
cp "$SCRIPT_DIR/autostart/codex-tray.desktop" "$DIR/usr/share/applications/codex-tray.desktop"

# Create autostart symlink
cp "$SCRIPT_DIR/autostart/codex-tray.desktop" "$DIR/etc/xdg/autostart/codex-tray.desktop"

# Generate control file
cat > "$DIR/DEBIAN/control" << CONTROL
Package: codex-tray
Version: ${VERSION}
Architecture: all
Maintainer: codex-tray
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0
Section: utils
Priority: optional
Homepage: https://github.com/anomalyco/tray-app
Description: Linux system-tray monitor for ChatGPT Codex CLI usage
 Tracks Codex CLI token usage and displays remaining 5-hour and
 7-day rolling limit windows in the system tray.
 .
 Requires Codex CLI to be installed and logged in:
   npm install -g @openai/codex
   codex
CONTROL

# Build .deb
dpkg-deb --build "$DIR" "$PKG_NAME" > /dev/null

rm -rf "$DIR"
echo "$PKG_NAME"
