#!/bin/bash
# MarkSign — build .app + .dmg
# Run from 2026-04-public-app/
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "── Installing pyinstaller into venv ──"
.venv/bin/pip install pyinstaller --quiet

echo "── Building .app ──"
.venv/bin/pyinstaller marksign.spec --noconfirm --clean

echo "── Build complete: dist/MarkSign.app ──"
ls -lh dist/MarkSign.app/Contents/MacOS/

echo ""
echo "── Creating DMG ──"
DMG_NAME="MarkSign-0.1.1.dmg"
rm -f "dist/$DMG_NAME"

create-dmg \
    --volname "MarkSign" \
    --window-pos 200 120 \
    --window-size 540 380 \
    --icon-size 128 \
    --icon "MarkSign.app" 160 170 \
    --app-drop-link 380 170 \
    --no-internet-enable \
    "dist/$DMG_NAME" \
    "dist/MarkSign.app"

echo ""
echo "✓  Done: dist/$DMG_NAME"
du -sh "dist/$DMG_NAME"
