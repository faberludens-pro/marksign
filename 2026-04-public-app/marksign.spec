# -*- mode: python ; coding: utf-8 -*-
"""
MarkSign — PyInstaller build spec
Produces: dist/MarkSign.app (macOS .app bundle)

Build command (from 2026-04-public-app/):
    .venv/bin/pyinstaller marksign.spec --noconfirm

Three executables share one COLLECT + BUNDLE:
  MarkSign          — main converter window (CTk + pyobjc)
  marksign_preview  — companion MD viewer  (WKWebView + pyobjc)
  marksign_tray     — menu bar icon        (pystray + pyobjc)
"""

import sys
from pathlib import Path

block_cipher = None
here = Path(SPECPATH).resolve()
root = here.parent  # product root — logo-marksign.jpg lives here

# ── Shared hidden imports ────────────────────────────────────────────────────

_HIDDEN = [
    # pyobjc — PyInstaller doesn't auto-detect ObjC bridge imports
    "objc",
    "_objc",
    "AppKit",
    "Foundation",
    "CoreFoundation",
    "CoreGraphics",
    "LaunchServices",
    # watchdog macOS backend
    "watchdog.observers",
    "watchdog.observers.fsevents",
    # CTk
    "customtkinter",
    "customtkinter.windows",
    "customtkinter.windows.widgets",
    "customtkinter.windows.widgets.core_widget_classes",
    # Pillow
    "PIL._tkinter_finder",
    "PIL.Image",
    "PIL.ImageDraw",
    # plistlib / uuid — stdlib, but explicit is safe
    "plistlib",
    "uuid",
    # drag-and-drop (optional — graceful fallback if missing)
    "tkinterdnd2",
    "tkinterdnd2.TkinterDnD",
]

_HIDDEN_PREVIEW = [
    "objc", "_objc",
    "AppKit", "Foundation", "CoreFoundation",
    "WebKit",
    "watchdog.observers",
    "watchdog.observers.fsevents",
    "markdown_it",
    "pygments",
    "pygments.lexers",
    "pygments.formatters",
    "pygments.styles",
]

_HIDDEN_TRAY = [
    "objc", "_objc",
    "AppKit", "Foundation",
    "PIL.Image", "PIL.ImageDraw",
    "PyObjCTools",
    "PyObjCTools.AppHelper",
    "PyObjCTools.MachSignals",
]

# Exclude heavy ML packages — docling is installed at runtime into ~/.marksign/venv/
_EXCLUDES = [
    "docling",
    "torch",
    "torchvision",
    "transformers",
    "huggingface_hub",
    "easyocr",
    "timm",
    "safetensors",
    "onnxruntime",
]

# ── Shared data files ────────────────────────────────────────────────────────

try:
    import customtkinter as _ctk
    _ctk_root = Path(_ctk.__file__).parent
    _ctk_data = [(str(_ctk_root), "customtkinter")]
except ImportError:
    _ctk_data = []

try:
    import tkinterdnd2 as _dnd
    _dnd_root = Path(_dnd.__file__).parent
    _dnd_data = [(str(_dnd_root), "tkinterdnd2")]
    # Native tkdnd library — must be bundled as binary for dlsym to find it
    import platform
    _arch = "arm64" if platform.machine() == "arm64" else "x64"
    _dylib = list((_dnd_root / "tkdnd" / f"osx-{_arch}").glob("*.dylib"))
    _dnd_bins = [(str(d), f"tkinterdnd2/tkdnd/osx-{_arch}") for d in _dylib]
except ImportError:
    _dnd_data = []
    _dnd_bins = []

_DATAS = [
    (str(root / "logo-marksign.jpg"), "."),
    ("marksign_help.md", "."),
] + _ctk_data + _dnd_data


# ══════════════════════════════════════════════════════════════════════════════
# 1. Main app
# ══════════════════════════════════════════════════════════════════════════════

a = Analysis(
    ["marksign_app.py"],
    pathex=[str(here)],
    binaries=_dnd_bins,
    datas=_DATAS,
    hiddenimports=_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MarkSign",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Preview companion
# ══════════════════════════════════════════════════════════════════════════════

a_preview = Analysis(
    ["marksign_preview.py"],
    pathex=[str(here)],
    binaries=[],
    datas=[],          # fonts are base64-embedded in the source file
    hiddenimports=_HIDDEN_PREVIEW,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    cipher=block_cipher,
    noarchive=False,
)

pyz_preview = PYZ(a_preview.pure, a_preview.zipped_data, cipher=block_cipher)

exe_preview = EXE(
    pyz_preview,
    a_preview.scripts,
    [],
    exclude_binaries=True,
    name="marksign_preview",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch=None,
)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Tray icon subprocess
# ══════════════════════════════════════════════════════════════════════════════

a_tray = Analysis(
    ["marksign_tray.py"],
    pathex=[str(here)],
    binaries=[],
    datas=[],
    hiddenimports=_HIDDEN_TRAY,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    cipher=block_cipher,
    noarchive=False,
)

pyz_tray = PYZ(a_tray.pure, a_tray.zipped_data, cipher=block_cipher)

exe_tray = EXE(
    pyz_tray,
    a_tray.scripts,
    [],
    exclude_binaries=True,
    name="marksign_tray",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch=None,
)


# ══════════════════════════════════════════════════════════════════════════════
# 4. COLLECT — merge all three into one dist directory
# ══════════════════════════════════════════════════════════════════════════════

coll = COLLECT(
    exe,         a.binaries,         a.zipfiles,         a.datas,
    exe_preview, a_preview.binaries, a_preview.zipfiles, a_preview.datas,
    exe_tray,    a_tray.binaries,    a_tray.zipfiles,    a_tray.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MarkSign",
)


# ══════════════════════════════════════════════════════════════════════════════
# 5. BUNDLE — wrap as macOS .app
# ══════════════════════════════════════════════════════════════════════════════

app = BUNDLE(
    coll,
    name="MarkSign.app",
    icon="MarkSign.icns",
    bundle_identifier="pro.faberludens.marksign",
    info_plist={
        "CFBundleName": "MarkSign",
        "CFBundleDisplayName": "MarkSign",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,    # respect system dark mode
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHumanReadableCopyright": "© 2026 Faber-Ludens Pro",
        # Show Dock icon while running (set True for menu-bar-only mode later)
        "LSUIElement": False,
        # Register as an alternate handler for .md files
        # (primary handler set via duti / LaunchServices at first run)
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Markdown Document",
                "CFBundleTypeExtensions": ["md", "markdown"],
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
            }
        ],
    },
)
