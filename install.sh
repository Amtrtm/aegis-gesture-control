#!/usr/bin/env bash
# PROJECT AEGIS — ShobNG Plugin Installer (Linux / macOS / WSL)
#
# Usage:
#   ./install.sh
#   ./install.sh /path/to/ShobNG

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHOBNG_PATH="${1:-$SCRIPT_DIR/../ShobNG}"

# ── Resolve ShobNG path ───────────────────────────────────────────────────────
if [ ! -d "$SHOBNG_PATH/frontend/src/plugins" ]; then
    echo ""
    echo "Could not find ShobNG at: $SHOBNG_PATH"
    printf "Enter the full path to your ShobNG directory: "
    read -r SHOBNG_PATH
fi

SHOBNG_PATH="${SHOBNG_PATH%/}"

if [ ! -d "$SHOBNG_PATH/frontend/src/plugins" ]; then
    echo "ERROR: ShobNG plugin directory not found at $SHOBNG_PATH/frontend/src/plugins"
    exit 1
fi

# ── Copy plugin files ─────────────────────────────────────────────────────────
SRC="$SCRIPT_DIR/shobng-plugin/frontend/src/plugins/gesture-control"
DEST="$SHOBNG_PATH/frontend/src/plugins/gesture-control"

echo ""
echo "PROJECT AEGIS — ShobNG Plugin Installer"
echo "  Source : $SRC"
echo "  Target : $DEST"
echo ""

mkdir -p "$DEST"
cp -rf "$SRC/." "$DEST/"

echo "Plugin files installed successfully."
echo ""
echo "Next steps:"
echo "  1. Start the AEGIS backend:  cd backend && python main.py --source 1"
echo "  2. Start ShobNG:             cd $SHOBNG_PATH && ./start.sh"
echo "  3. Open the Plugins panel in ShobNG and enable 'Gesture Control'."
echo ""
