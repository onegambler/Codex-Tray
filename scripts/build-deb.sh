#!/bin/bash
set -e

VERSION="${1:-0.2.0}"
DIR=$(mktemp -d)
PKG_NAME="ai-usage-tray_${VERSION}_all.deb"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Directory structure
mkdir -p "$DIR/DEBIAN"
mkdir -p "$DIR/usr/share/ai-usage-tray"
mkdir -p "$DIR/usr/bin"
mkdir -p "$DIR/usr/share/applications"
mkdir -p "$DIR/etc/xdg/autostart"

# Copy source package, excluding compiled bytecode
mkdir -p "$DIR/usr/share/ai-usage-tray"
cd "$SCRIPT_DIR"
find ai_usage_tray -type f -name '*.py' -exec cp --parents {} "$DIR/usr/share/ai-usage-tray/" \;

# Create wrapper script
cat > "$DIR/usr/bin/ai-usage-tray" << 'SCRIPT'
#!/bin/bash
cd /usr/share/ai-usage-tray
exec /usr/bin/python3 -m ai_usage_tray "$@"
SCRIPT
chmod 755 "$DIR/usr/bin/ai-usage-tray"

# Copy desktop file
cp "$SCRIPT_DIR/autostart/ai-usage-tray.desktop" "$DIR/usr/share/applications/ai-usage-tray.desktop"

# Create autostart entry
cp "$SCRIPT_DIR/autostart/ai-usage-tray.desktop" "$DIR/etc/xdg/autostart/ai-usage-tray.desktop"

# Generate control file
cat > "$DIR/DEBIAN/control" << CONTROL
Package: ai-usage-tray
Version: ${VERSION}
Architecture: all
Maintainer: ai-usage-tray
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0
Recommends: gir1.2-ayatanaappindicator3-0.1 | gir1.2-appindicator3-0.1
Section: utils
Priority: optional
Homepage: https://github.com/anomalyco/tray-app
Description: Linux system-tray monitor for AI coding assistant usage
 Tracks usage and displays remaining limit windows for multiple AI
 coding assistants in the system tray.
 .
 Supports Codex (OpenAI) and OpenCode Go out of the box; additional
 providers can be added through the settings dialog.
CONTROL

# Build .deb
dpkg-deb --build "$DIR" "$PKG_NAME" > /dev/null

rm -rf "$DIR"
echo "$PKG_NAME"
