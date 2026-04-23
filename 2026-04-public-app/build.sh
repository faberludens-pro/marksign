#!/bin/bash
# MarkSign — build .app + .pkg
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
echo "── Creating PKG ──"
PKG_NAME="MarkSign-0.1.1.pkg"
rm -f "dist/$PKG_NAME"

pkgbuild \
    --component "dist/MarkSign.app" \
    --install-location /Applications \
    --identifier pro.faberludens.marksign \
    --version 0.1.1 \
    "dist/$PKG_NAME"

echo ""
echo "✓  Done: dist/$PKG_NAME"
du -sh "dist/$PKG_NAME"
