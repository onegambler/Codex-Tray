#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing system dependencies..."
if command -v apt &>/dev/null; then
    sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pip
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-gobject python3-gobject-gtk3 python3-pip
elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm python-gobject python-pip gtk3
else
    echo "Unsupported package manager."
    echo "Install python3-gi, python3-gi-cairo, and gir1.2-gtk-3.0 manually, then re-run this script."
    exit 1
fi

echo "==> Installing ai-usage-tray..."
if pip3 install "$DIR" 2>/dev/null; then
    :
else
    echo "(retrying with --break-system-packages for PEP 668 compatibility)"
    pip3 install --break-system-packages "$DIR"
fi

echo "==> Setting up autostart..."
mkdir -p ~/.config/autostart
cp "$DIR/autostart/ai-usage-tray.desktop" ~/.config/autostart/

echo ""
echo "Done! Run 'ai-usage-tray' to start."
echo ""
echo "NOTE: At least one provider must be configured."
echo "      Codex is auto-detected if 'codex' CLI is logged in."
echo "      OpenCode Go requires a workspace ID and auth cookie."
