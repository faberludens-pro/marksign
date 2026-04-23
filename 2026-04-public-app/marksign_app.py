#!/usr/bin/env python3
"""
MarkSign Converter — macOS menu bar app.

Architecture:
  - pystray  : status bar icon, runs in background thread (run_detached)
  - CTk      : window UI, runs on main thread via mainloop()
  - threading: conversion runs in background, schedules UI updates via root.after()

No Dock icon while idle (LSUIElement = YES in Info.plist for packaged app).

States: EMPTY → LOADED → CONVERTING → DONE

IPC (Finder right-click Automator action):
    curl "http://localhost:57892/open?path=/path/to/file.pdf"
"""

import os
import sys
import queue
import threading
import subprocess
import plistlib
import uuid
import tkinter as _tk
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import customtkinter as ctk

# ── Drag-and-drop support (optional — needs tkinterdnd2) ──────────────────────
try:
    from tkinterdnd2 import TkinterDnD as _TkDnD

    class _DnDCTk(ctk.CTk, _TkDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                import sys, os, platform
                machine = platform.machine()
                plat = "osx-arm64" if machine == "arm64" else "osx-x64"
                # In PyInstaller bundle __file__ may not resolve correctly;
                # manually add tkdnd path from known bundle locations.
                candidates = []
                # 1. sys._MEIPASS (PyInstaller onefile or onedir temp)
                if hasattr(sys, "_MEIPASS"):
                    candidates.append(os.path.join(sys._MEIPASS, "tkinterdnd2", "tkdnd", plat))
                # 2. Contents/Resources/ relative to executable (macOS .app bundle)
                exe_dir = os.path.dirname(sys.executable)
                resources_dir = os.path.normpath(os.path.join(exe_dir, "..", "Resources"))
                candidates.append(os.path.join(resources_dir, "tkinterdnd2", "tkdnd", plat))
                # 3. Fallback: package __file__
                pkg_dir = os.path.dirname(_TkDnD.__file__)
                candidates.append(os.path.join(pkg_dir, "tkdnd", plat))
                for path in candidates:
                    if os.path.isdir(path):
                        self.tk.call("lappend", "auto_path", path)
                        break
                self.TkdndVersion = _TkDnD._require(self)
            except Exception:
                pass  # native tkdnd library unavailable — DnD disabled gracefully

    _CTkRoot = _DnDCTk
except Exception:
    _CTkRoot = ctk.CTk
from AppKit import (
    NSStatusBar, NSVariableStatusItemLength, NSImage,
    NSMenu, NSMenuItem, NSApplication as _NSApp,
    NSWorkspace, NSEvent,
)
from Foundation import NSData, NSObject, NSURL
from PIL import Image, ImageDraw

from marksign_engine import convert_file, docling_available, SUPPORTED_FORMATS_V1

# ── Theme ────────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT       = "#0A84FF"
SYSTEM_RED   = "#FF453A"
SYSTEM_GREEN = "#30D158"
LABEL        = "#D9D9D9"
LABEL_2      = "#7F7F7F"
BG_WINDOW    = "#2A2A2A"
BG_TOOLBAR   = "#383838"
BG_CONTENT   = "#1C1C1C"
BG_STATUSBAR = "#2E2E2E"
BG_ROW       = "#252525"
BG_ROW_ALT   = "#222222"
SEPARATOR    = "#3A3A3A"

FONT_TITLE   = ("SF Pro Text", 14, "bold")
FONT_BODY    = ("SF Pro Text", 13)
FONT_SMALL   = ("SF Pro Text", 12)
FONT_TINY    = ("SF Pro Text", 11)

IPC_PORT     = 57892
WINDOW_W     = 640
_SETUP_FLAG  = Path.home() / ".marksign" / "setup_complete"
WINDOW_H     = 480

_window_ref  = [None]   # global ref for IPC access


# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt_size(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024 ** 2:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_ / 1024**2:.1f} MB"


def short_path(path: Path, levels=3) -> str:
    parts = path.parts
    if len(parts) <= levels:
        return str(path)
    return "…/" + "/".join(parts[-levels:])


def reveal_in_finder(path: Path):
    subprocess.run(["open", "-R", str(path)], check=False)


def _resource(name: str) -> Path:
    """Locate a bundled data file — works frozen (.app) and in dev."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / name  # type: ignore[attr-defined]
    here = Path(__file__).parent
    # logo lives one level up in the dev tree
    if name == "logo-marksign.jpg":
        return here.parent / name
    return here / name


def _companion(name: str) -> list:
    """Return the command list to launch a companion executable.
    Frozen: sibling binary in MacOS/; dev: python + .py script."""
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).parent / name)]
    return [sys.executable, str(Path(__file__).parent / f"{name}.py")]


def _pip_cmd() -> list:
    """pip command suitable for installing packages at runtime.
    Frozen apps can't use sys.executable as Python, so we create
    a dedicated venv at ~/.marksign/venv/ with system python3."""
    if not getattr(sys, "frozen", False):
        return [sys.executable, "-m", "pip"]
    import shutil
    venv_dir = Path.home() / ".marksign" / "venv"
    pip = venv_dir / "bin" / "pip"
    if not pip.exists():
        # Prefer a modern Python (3.10+ required by docling); avoid Apple's 3.9.
        # Frozen .app has a minimal PATH — check known absolute locations first.
        import os
        _candidates = [
            # Homebrew arm64
            "/opt/homebrew/bin/python3.13",
            "/opt/homebrew/bin/python3.12",
            "/opt/homebrew/bin/python3.11",
            "/opt/homebrew/bin/python3.10",
            # Homebrew x86_64
            "/usr/local/bin/python3.13",
            "/usr/local/bin/python3.12",
            "/usr/local/bin/python3.11",
            "/usr/local/bin/python3.10",
            # pyenv
            str(Path.home() / ".pyenv" / "shims" / "python3"),
            # PATH fallback
            shutil.which("python3.13") or "",
            shutil.which("python3.12") or "",
            shutil.which("python3.11") or "",
            shutil.which("python3.10") or "",
            shutil.which("python3") or "/usr/bin/python3",
        ]
        python3 = next((c for c in _candidates if c and os.path.isfile(c)), "/usr/bin/python3")
        subprocess.run([python3, "-m", "venv", str(venv_dir)],
                       check=True, capture_output=True)
    return [str(pip)]


# ── File type icons ──────────────────────────────────────────────────────────

_FILE_ICON_CACHE: dict = {}

_FT_STYLES = {
    ".pdf":  {"bg": "#4A1515", "text": "#FF6B6B", "fold": "#7A2020"},
    ".docx": {"bg": "#132040", "text": "#6B9FFF", "fold": "#1E3570"},
    ".doc":  {"bg": "#132040", "text": "#6B9FFF", "fold": "#1E3570"},
    ".pptx": {"bg": "#132040", "text": "#6B9FFF", "fold": "#1E3570"},
    ".ppt":  {"bg": "#132040", "text": "#6B9FFF", "fold": "#1E3570"},
    ".epub": {"bg": "#3A2010", "text": "#FFB855", "fold": "#6A3820"},
    ".xlsx": {"bg": "#0A2818", "text": "#4ADF88", "fold": "#104228"},
    ".xls":  {"bg": "#0A2818", "text": "#4ADF88", "fold": "#104228"},
    ".txt":  {"bg": "#282828", "text": "#AAAAAA", "fold": "#444444"},
    ".rtf":  {"bg": "#282840", "text": "#9999FF", "fold": "#404060"},
}


def _hex(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (255,)


def _make_file_icon(ext: str) -> "ctk.CTkImage":
    """
    Prototype-style file icon: dark tinted background, vibrant ext text,
    folded top-right corner. Matches the HTML prototype design exactly.
    Cached per extension.
    """
    if ext in _FILE_ICON_CACHE:
        return _FILE_ICON_CACHE[ext]

    # .md / .md-done → document shape with large centred logo
    # .md-done uses a green-tinted body to signal successful conversion
    if ext in (".md", ".md-done"):
        W, H, fold, r = 60, 72, 14, 6
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W, H], radius=r, fill=_hex("#222222"))
        d.polygon([(W - fold, 0), (W, 0), (W, fold)], fill=_hex("#444444"))
        d.line([(r, H - 1), (W - r, H - 1)], fill=(0, 0, 0, 80), width=1)
        # Large logo — fills most of the document face
        try:
            shield_size = 48
            src = Image.open(_LOGO_PATH).resize(
                (shield_size, shield_size), Image.LANCZOS).convert("RGBA")
            ox = (W - shield_size) // 2
            oy = (H - shield_size) // 2
            if ext == ".md-done":
                # Full-colour logo for converted files
                img.paste(src, (ox, oy), src)
            else:
                # B&W (white) logo for neutral .md icon
                bw = Image.new("RGBA", (shield_size, shield_size), (0, 0, 0, 0))
                src_px = src.load()
                bw_px  = bw.load()
                for sy in range(shield_size):
                    for sx in range(shield_size):
                        rr, gg, bb, aa = src_px[sx, sy]
                        lum = int(0.299 * rr + 0.587 * gg + 0.114 * bb)
                        if lum > 50:
                            alpha = min(255, int(aa * (lum - 50) / 205))
                            bw_px[sx, sy] = (255, 255, 255, alpha)
                img.paste(bw, (ox, oy), bw)
        except Exception:
            pass
        icon = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 36))
        _FILE_ICON_CACHE[ext] = icon
        return icon

    style = _FT_STYLES.get(ext, {"bg": "#282828", "text": "#AAAAAA", "fold": "#444444"})
    label = ext.lstrip(".").upper()[:4]

    # 2× resolution: display at 30×36, draw at 60×72
    W, H, fold = 60, 72, 12
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # ── Document body (rounded corners, dark tinted) ──────────────────────
    r = 6
    d.rounded_rectangle([0, 0, W, H], radius=r, fill=_hex(style["bg"]))

    # ── Fold corner — overwrite top-right with a triangle ─────────────────
    # Clear the top-right rounded region, draw fold triangle
    d.polygon([(W - fold, 0), (W, 0), (W, fold)], fill=_hex(style["fold"]))

    # ── Subtle drop shadow sim: 1px dark line at bottom ───────────────────
    d.line([(r, H - 1), (W - r, H - 1)], fill=(0, 0, 0, 80), width=1)

    # ── Extension text: bottom-centred, bold ──────────────────────────────
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15)
    except Exception:
        from PIL import ImageFont
        font = ImageFont.load_default()

    d.text((W // 2, H - 10), label, fill=_hex(style["text"]),
           font=font, anchor="mm")

    icon = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 36))
    _FILE_ICON_CACHE[ext] = icon
    return icon


# ── File entry ───────────────────────────────────────────────────────────────

class FileEntry:
    def __init__(self, path: Path):
        self.path = path
        self.size = path.stat().st_size if path.exists() else 0
        self.dest = path.parent / (path.stem + ".md")
        self.status = "waiting"   # waiting | converting | done | error
        self.error_msg = ""
        self.method = ""


# ── IPC server ────────────────────────────────────────────────────────────────

class _IPCHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        win = _window_ref[0]

        if parsed.path == "/open" and "path" in params:
            file_path = Path(params["path"][0])
            if file_path.exists() and win and win.root:
                win._ui_queue.put(lambda fp=file_path: win.add_files([fp], show=True))

        elif parsed.path == "/show":
            if win and win.root:
                win._ui_queue.put(win.show)

        elif parsed.path == "/about":
            if win and win.root:
                win._ui_queue.put(lambda: _show_about(win.root))

        elif parsed.path == "/help":
            if win and win.root:
                win._ui_queue.put(lambda: _show_help(win.root))

        elif parsed.path == "/quit":
            if win and win.root:
                win._ui_queue.put(lambda: (_release_lock(), os._exit(0)))

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


def _start_ipc_server():
    try:
        HTTPServer(("127.0.0.1", IPC_PORT), _IPCHandler).serve_forever()
    except OSError:
        pass


# ── System tray icon (pystray) ────────────────────────────────────────────────

_LOGO_PATH = _resource("logo-marksign.jpg")


def _make_icon_image() -> Image.Image:
    """
    macOS menu bar template icon: white shield outline + white checkmark,
    transparent background. setTemplate_(True) lets macOS handle dark/light.
    Drawn at 2x (44px) for Retina; macOS scales as needed.
    """
    S = 44
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    W = (255, 255, 255, 255)   # white, fully opaque
    lw = 2                      # stroke width

    # ── Shield outline ────────────────────────────────────────────────────
    # Centred, 28 wide × 32 tall. Points: flat top-left/right,
    # slight inward curve handled via polygon approximation.
    cx = S // 2
    # Shield polygon (classic rounded-bottom shield, approximated with segments)
    sx, sy = cx - 12, 6          # top-left
    ex, ey = cx + 12, 6          # top-right
    # Left side down to bottom point
    shield = [
        (sx,      sy),           # top-left
        (ex,      ey),           # top-right
        (ex,      sy + 16),      # right mid
        (cx + 6,  sy + 22),      # lower-right shoulder
        (cx,      sy + 26),      # bottom tip
        (cx - 6,  sy + 22),      # lower-left shoulder
        (sx,      sy + 16),      # left mid
    ]
    d.polygon(shield, outline=W, fill=(0, 0, 0, 0), width=lw)

    # ── Checkmark ─────────────────────────────────────────────────────────
    # Centred inside the shield
    ck_x, ck_y = cx - 6, sy + 11
    d.line([(ck_x,     ck_y + 5),
            (ck_x + 4, ck_y + 9),
            (ck_x + 10, ck_y + 1)],
           fill=W, width=lw + 1, joint="curve")

    return img


def _pil_to_nsimage(pil_img: Image.Image, template: bool = False) -> NSImage:
    """Convert PIL RGBA image to NSImage."""
    import io
    buf = io.BytesIO()
    pil_img.save(buf, "PNG")
    raw = buf.getvalue()
    data = NSData.dataWithBytes_length_(raw, len(raw))
    ns = NSImage.alloc().initWithData_(data)
    if template:
        ns.setTemplate_(True)
    return ns


def _logo_nsimage(size: int = 128) -> NSImage:
    """Load the MarkSign logo as an NSImage."""
    try:
        pil = Image.open(_LOGO_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
        return _pil_to_nsimage(pil)
    except Exception:
        return NSImage.alloc().init()


class _MenuDelegate(NSObject):
    """ObjC target for NSStatusItem menu actions."""
    window_ = None

    def openWindow_(self, sender):
        if self.window_ and self.window_.root:
            self.window_._ui_queue.put(self.window_.show)

    def showAbout_(self, sender):
        if self.window_ and self.window_.root:
            self.window_._ui_queue.put(lambda: _show_about(self.window_.root))

    def showHelp_(self, sender):
        if self.window_ and self.window_.root:
            self.window_._ui_queue.put(lambda: _show_help(self.window_.root))

    def quitApp_(self, sender):
        if self.window_ and self.window_.root:
            self.window_._ui_queue.put(self.window_.root.destroy)


def _create_tray_icon(window: "MarkSignWindow"):
    """Create an NSStatusItem directly via pyobjc — no separate event loop."""
    ns_icon = _pil_to_nsimage(_make_icon_image(), template=True)

    status_bar = NSStatusBar.systemStatusBar()
    status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)
    btn = status_item.button()
    btn.setImage_(ns_icon)
    btn.setToolTip_("MarkSign")
    btn.setHidden_(False)          # critical: button is hidden by default
    status_item.setVisible_(True)  # macOS 10.12+

    delegate = _MenuDelegate.alloc().init()
    delegate.window_ = window

    menu = NSMenu.alloc().init()
    menu.setAutoenablesItems_(False)

    def _item(title, action):
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
        it.setTarget_(delegate)
        menu.addItem_(it)

    _item("Convert file",    "openWindow:")
    menu.addItem_(NSMenuItem.separatorItem())
    _item("About MarkSign",  "showAbout:")
    _item("Help",            "showHelp:")
    menu.addItem_(NSMenuItem.separatorItem())
    _item("Quit MarkSign",   "quitApp:")

    status_item.setMenu_(menu)
    return status_item, delegate  # keep alive (GC)


# ── Conversion window ─────────────────────────────────────────────────────────

class MarkSignWindow:

    def __init__(self):
        self.root: ctk.CTk | None = None
        self._files: list[FileEntry] = []
        self._state = "empty"
        self._conv_thread = None
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()

    # ── Build ─────────────────────────────────────────────────────────────────

    def build(self):
        self.root = _CTkRoot()
        self.root.title("")
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - WINDOW_W) // 2
        y = (sh - WINDOW_H) // 2
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.minsize(460, 380)
        self.root.configure(fg_color=BG_WINDOW)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Re-open window: Cmd+N, dock icon click, and File > New Window
        self.root.bind_all("<Command-n>", lambda e: self.show())
        self.root.createcommand("::tk::mac::ReopenApplication", self.show)

        self._build_content()
        self._build_statusbar()
        self._show_state("empty")
        self._poll_ui_queue()
        # <MouseWheel> events don't fire in PyInstaller bundles on macOS.
        # Use NSEvent local monitor to intercept trackpad scroll directly.
        self._setup_ns_scroll()

        # Drag-and-drop (optional — needs tkdnd)
        for _dnd_target in (self.root, self._content):
            try:
                _dnd_target.drop_target_register("DND_Files")
                _dnd_target.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def show(self):
        if self.root is None:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        try:
            from AppKit import NSApp
            NSApp.activateIgnoringOtherApps_(True)
        except Exception:
            pass

    def _on_close(self):
        self.root.withdraw()

    def _poll_ui_queue(self):
        """Drain the thread-safe queue on the main thread (every 50 ms).
        All background threads post UI updates here instead of calling
        root.after() directly — avoids Python 3.13 GIL/Tcl AfterProc crash."""
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        if self.root:
            self.root.after(50, self._poll_ui_queue)

    # ── Content ───────────────────────────────────────────────────────────────

    def _build_content(self):
        self._content = ctk.CTkFrame(self.root, fg_color=BG_CONTENT, corner_radius=0)
        self._content.pack(fill="both", expand=True)
        self._build_empty_state()
        self._build_list_state()

    @staticmethod
    def _make_drop_icon() -> "ctk.CTkImage":
        """
        Fancy document-to-markdown icon for the empty state.
        Document shape with folded corner + text lines + accent arrow circle.
        """
        W, H = 128, 148
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # ── Document body (navy, rounded corners) ──────────────────────────────
        r, fold = 12, 26
        navy = (22, 68, 138, 255)
        # Rounded rect via overlapping rects + corner ellipses
        d.rectangle([r, 0, W - r, H], fill=navy)
        d.rectangle([0, r, W, H - r], fill=navy)
        for cx, cy in [(r, r), (W - r, r), (r, H - r), (W - r, H - r)]:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=navy)

        # ── Folded corner (top-right) ───────────────────────────────────────────
        fold_color = (40, 100, 185, 255)
        d.polygon([
            (W - r - fold, 0),
            (W - r, 0),
            (W, r),
            (W, r + fold),
            (W - r - fold, r + fold),
        ], fill=fold_color)

        # ── Simulated text lines ────────────────────────────────────────────────
        line_fill = (255, 255, 255, 45)
        for y_ln, x_end in [(28, W - 22), (40, W - 22), (52, W - 22), (64, W // 2 + 8)]:
            d.rounded_rectangle([18, y_ln, x_end, y_ln + 5], radius=2, fill=line_fill)

        # ── Accent circle with down arrow ───────────────────────────────────────
        cx, cy, cr = W // 2, H - 38, 28
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(10, 132, 255, 255))
        # Arrow stem
        d.line([(cx, cy - 14), (cx, cy + 2)], fill=(255, 255, 255, 255), width=4)
        # Arrow head
        d.polygon([(cx - 11, cy + 0), (cx + 11, cy + 0), (cx, cy + 14)],
                  fill=(255, 255, 255, 255))

        return ctk.CTkImage(light_image=img, dark_image=img, size=(64, 74))

    @staticmethod
    def _make_logo_badge(size: int = 48) -> "ctk.CTkImage":
        """Round-rect logo badge for the empty state header."""
        try:
            src = Image.open(_LOGO_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            src = Image.new("RGBA", (size, size), (40, 40, 40, 255))
        return ctk.CTkImage(light_image=src, dark_image=src, size=(size, size))

    def _build_empty_state(self):
        self._frame_empty = ctk.CTkFrame(self._content, fg_color="transparent")

        # Inner block — vertically centered in the frame via place()
        inner = ctk.CTkFrame(self._frame_empty, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # ── Wordmark: shield + Mark (white) + Sign (orange) ────────────────
        wordmark = ctk.CTkFrame(inner, fg_color="transparent")
        wordmark.pack(pady=(0, 20))
        logo_img = self._make_logo_badge(40)
        ctk.CTkLabel(wordmark, image=logo_img, text="",
                     fg_color="transparent").pack(side="left", padx=(0, 10))
        _wm_font = ctk.CTkFont(family="Iowan Old Style", size=30,
                               weight="bold", slant="italic")
        ctk.CTkLabel(wordmark, text="Mark", font=_wm_font,
                     text_color=LABEL, fg_color="transparent").pack(side="left")
        ctk.CTkLabel(wordmark, text="Sign", font=_wm_font,
                     text_color="#E0601A", fg_color="transparent").pack(side="left")

        # ── Orientation headline ────────────────────────────────────────────
        ctk.CTkLabel(
            inner, text="Convert your documents to Markdown, locally",
            font=("SF Pro Display", 20, "bold"), text_color=LABEL,
            fg_color="transparent"
        ).pack(pady=(0, 24))

        ctk.CTkLabel(
            inner, image=self._make_drop_icon(), text="",
            fg_color="transparent"
        ).pack(pady=(0, 14))

        ctk.CTkLabel(inner, text="Drop files to convert",
                     font=("SF Pro Text", 16, "bold"), text_color=LABEL,
                     fg_color="transparent").pack(pady=(0, 4))

        ctk.CTkLabel(inner, text="or",
                     font=FONT_BODY, text_color=LABEL_2,
                     fg_color="transparent").pack(pady=(0, 10))

        ctk.CTkButton(
            inner, text="Select Files",
            font=FONT_BODY, fg_color=ACCENT, hover_color="#0066CC",
            text_color="white", height=32, width=130, corner_radius=6,
            command=self._pick_files
        ).pack(pady=(0, 18))

        chips_frame = ctk.CTkFrame(inner, fg_color="transparent")
        chips_frame.pack()
        for fmt in ["PDF", "DOC", "DOCX", "PPTX", "EPUB", "XLS", "XLSX", "TXT", "RTF"]:
            ctk.CTkLabel(
                chips_frame, text=fmt, font=FONT_TINY,
                text_color=LABEL_2, fg_color="#2E2E2E",
                corner_radius=4, padx=8, pady=3
            ).pack(side="left", padx=3)

    def _build_list_state(self):
        self._frame_list = ctk.CTkFrame(self._content, fg_color="transparent")

        self._scroll = ctk.CTkScrollableFrame(
            self._frame_list, fg_color=BG_CONTENT,
            scrollbar_button_color=BG_ROW,
            scrollbar_button_hover_color=SEPARATOR
        )
        self._scroll.pack(fill="both", expand=True)

        self._add_strip = ctk.CTkButton(
            self._frame_list, text="+ Add more files…",
            font=FONT_SMALL, text_color=LABEL_2,
            fg_color=BG_ROW, hover_color=BG_ROW_ALT,
            height=40, corner_radius=0, border_width=0,
            command=self._pick_files
        )

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = ctk.CTkFrame(self.root, height=44, fg_color=BG_STATUSBAR, corner_radius=0)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        self._progress = ctk.CTkProgressBar(sb, height=4, fg_color=SEPARATOR,
                                            progress_color=ACCENT, corner_radius=2)
        self._progress.set(0)
        self._progress.place(x=0, y=0, relwidth=1.0)

        self._btn_action = ctk.CTkButton(
            sb, text="Convert",
            font=FONT_BODY, fg_color=ACCENT, hover_color="#0066CC",
            text_color="white", height=30, width=110, corner_radius=6,
            command=self._start_conversion
        )
        self._btn_action.place(relx=1.0, x=-12, rely=0.5, anchor="e")

        self._status_label = ctk.CTkLabel(
            sb, text="", font=FONT_SMALL,
            text_color=LABEL_2, fg_color="transparent"
        )
        self._status_label.place(x=12, rely=0.5, anchor="w")

        ctk.CTkLabel(
            sb, text="MarkSign by Faber-Ludens Pro",
            font=("SF Pro Text", 10), text_color="#555555",
            fg_color="transparent"
        ).place(relx=0.5, rely=0.5, anchor="center")

    # ── State machine ─────────────────────────────────────────────────────────

    def _show_state(self, state: str):
        self._state = state

        self._frame_empty.pack_forget()
        self._frame_list.pack_forget()
        self._add_strip.pack_forget()

        if state == "empty":
            self._frame_empty.pack(fill="both", expand=True)
            self._btn_action.configure(state="disabled", fg_color=SEPARATOR)
            self._progress.set(0)
            self._status_label.configure(text="")

        elif state == "loaded":
            self._frame_list.pack(fill="both", expand=True)
            self._add_strip.pack(fill="x", side="bottom")
            self._btn_action.configure(state="normal", fg_color=ACCENT)
            self._progress.set(0)
            self._status_label.configure(text=f"{len(self._files)} file(s) queued")

        elif state == "converting":
            self._frame_list.pack(fill="both", expand=True)
            self._btn_action.configure(state="disabled", fg_color=SEPARATOR)

        elif state == "done":
            self._frame_list.pack(fill="both", expand=True)
            self._btn_action.configure(
                text="Clear", state="normal",
                fg_color=BG_ROW, hover_color=SEPARATOR,
                text_color=LABEL, command=self._clear
            )

    # ── File management ───────────────────────────────────────────────────────

    def _pick_files(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Select files to convert",
            filetypes=[
                ("Supported formats", "*.pdf *.doc *.docx *.pptx *.epub *.xls *.xlsx *.txt *.rtf"),
                ("All files", "*.*"),
            ]
        )
        if paths:
            self.add_files([Path(p) for p in paths])

    def _on_drop(self, event):
        paths = [Path(p) for p in self.root.tk.splitlist(event.data)]
        self.add_files(paths)

    def add_files(self, paths: list[Path], show: bool = False):
        if show:
            self.show()
        supported = {e.lower() for e in SUPPORTED_FORMATS_V1}
        rejected_exts: set[str] = set()
        for p in paths:
            if p.suffix.lower() in supported:
                if not any(e.path == p for e in self._files):
                    self._files.append(FileEntry(p))
            else:
                rejected_exts.add(p.suffix.lower() or "unknown")

        if self._files:
            self._rebuild_list()
            if self._state in ("empty",):
                self._show_state("loaded")
            else:
                self._status_label.configure(text=f"{len(self._files)} file(s) queued")

        if rejected_exts:
            exts_str = ", ".join(sorted(rejected_exts))
            self._show_unsupported_notice(exts_str)

    def _show_unsupported_notice(self, exts_str: str):
        self._status_label.configure(
            text=f"⚠  {exts_str} not supported — use PDF, DOC, DOCX, PPTX, EPUB, XLS, XLSX, TXT, RTF",
            text_color="#FF9F0A"
        )
        # Clear after 5 s, restoring appropriate text
        def _restore():
            if self._state == "loaded":
                self._status_label.configure(
                    text=f"{len(self._files)} file(s) queued", text_color=LABEL_2)
            elif self._state == "empty":
                self._status_label.configure(text="", text_color=LABEL_2)
        self.root.after(5000, _restore)

    def _clear(self):
        self._files.clear()
        self._clear_list()
        self._show_state("empty")
        self._btn_action.configure(
            text="Convert", command=self._start_conversion,
            fg_color=SEPARATOR, text_color=LABEL_2
        )
        self._progress.set(0)

    def _choose_dest(self, entry: FileEntry):
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            parent=self.root,
            title="Choose destination folder",
            initialdir=str(entry.dest.parent),
        )
        if folder:
            entry.dest = Path(folder) / (entry.path.stem + ".md")
            self._rebuild_list()

    def _preview(self, path: Path):
        """Open MarkSign Preview companion viewer."""
        subprocess.Popen(_companion("marksign_preview") + [str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ── List rendering ────────────────────────────────────────────────────────

    def _clear_list(self):
        for w in self._scroll.winfo_children():
            w.destroy()

    def _rebuild_list(self):
        self._clear_list()
        for i, entry in enumerate(self._files):
            bg = BG_ROW if i % 2 == 0 else BG_ROW_ALT
            self._build_row(entry, bg)
        # Force scrollregion update after geometry settles —
        # CTkScrollableFrame's own Configure bind only fires on outer resize,
        # not when content is added programmatically.
        self.root.after_idle(self._update_scrollregion)

    def _update_scrollregion(self):
        canvas = self._scroll._parent_canvas
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_row(self, entry: FileEntry, bg: str):
        # tk.Canvas: height=56 is absolute — never overridden by children.
        row = _tk.Canvas(self._scroll, bg=bg, height=56,
                         bd=0, highlightthickness=0)
        row.pack(fill="x")

        # ── File type icon — vertically centered at row midpoint ───────────────
        icon_ext = ".md-done" if entry.status == "done" else entry.path.suffix.lower()
        icon_lbl = ctk.CTkLabel(row, image=_make_file_icon(icon_ext),
                                text="", fg_color=bg)
        row.create_window(12, 28, window=icon_lbl, anchor="w")

        # ── Display name / size ────────────────────────────────────────────────
        if entry.status == "done":
            display_name = entry.dest.name
            display_size = entry.dest.stat().st_size if entry.dest.exists() else entry.size
        else:
            display_name = entry.path.name
            display_size = entry.size

        # ── Two-line text block — single Frame centered vertically ─────────────
        # anchor="w" centers the frame at y=28 (midpoint of 56px row).
        text_block = _tk.Frame(row, bg=bg)
        row.create_window(52, 28, window=text_block, anchor="w")

        # Line 1: filename + size [+ Preview for done state]
        # height=18 constrains CTkLabel default (~28px) so lines sit tight
        name_row = _tk.Frame(text_block, bg=bg)
        name_row.pack(anchor="w")

        ctk.CTkLabel(name_row, text=display_name, font=FONT_BODY,
                     text_color=LABEL, fg_color=bg, height=18).pack(side="left")
        ctk.CTkLabel(name_row, text=f"  {fmt_size(display_size)}", font=FONT_TINY,
                     text_color=LABEL_2, fg_color=bg, height=18).pack(side="left")


        # Line 2: sub-row — height=14 keeps it tight to line 1
        sub = _tk.Frame(text_block, bg=bg)
        sub.pack(anchor="w")

        if entry.status == "waiting":
            ctk.CTkLabel(sub, text="Save to: ", font=FONT_TINY,
                         text_color=LABEL_2, fg_color=bg, height=14).pack(side="left")
            lnk = ctk.CTkLabel(
                sub, text=f"{short_path(entry.dest.parent)} ›",
                font=FONT_TINY, text_color=ACCENT, fg_color=bg,
                cursor="pointinghand", height=14
            )
            lnk.pack(side="left")
            lnk.bind("<Button-1>", lambda e, en=entry: self._choose_dest(en))

            def _remove(e=entry):
                self._files.remove(e)
                if not self._files:
                    self._show_state("empty")
                else:
                    self._rebuild_list()
                    self._status_label.configure(
                        text=f"{len(self._files)} file(s) queued")

            btn_remove = ctk.CTkButton(
                row, text="×", width=28, height=28,
                font=("SF Pro Text", 16), fg_color=bg,
                hover_color=BG_CONTENT, text_color=LABEL_2, border_width=0,
                command=_remove
            )
            win_id = row.create_window(row.winfo_width() - 12, 28,
                                       window=btn_remove, anchor="e")
            row.bind("<Configure>",
                     lambda e, c=row, w=win_id: c.coords(w, e.width - 12, 28))
            return

        elif entry.status == "converting":
            ctk.CTkLabel(sub, text="Converting file…", font=FONT_TINY,
                         text_color=ACCENT, fg_color=bg, height=14).pack(side="left")

        elif entry.status == "done":
            ctk.CTkLabel(sub, text="Saved in ", font=FONT_TINY,
                         text_color=LABEL_2, fg_color=bg, height=14).pack(side="left")
            ctk.CTkButton(
                sub, text=f"{short_path(entry.dest.parent)} ›",
                font=FONT_TINY, text_color=ACCENT, fg_color=bg,
                hover_color=BG_CONTENT, border_width=0, height=14,
                command=lambda p=entry.dest: reveal_in_finder(p)
            ).pack(side="left")

        elif entry.status == "error":
            lnk = ctk.CTkLabel(
                sub, text="Open in Finder", font=FONT_TINY,
                text_color=ACCENT, fg_color=bg, cursor="pointinghand", height=14
            )
            lnk.pack(side="left")
            lnk.bind("<Button-1>", lambda e, p=entry.path: reveal_in_finder(p))
            err_row = _tk.Frame(self._scroll, bg="#2A1A1A", height=32)
            err_row.pack(fill="x")
            err_row.pack_propagate(False)
            ctk.CTkLabel(
                err_row, text=f"  ✗  {entry.error_msg[:120]}",
                font=FONT_TINY, text_color=SYSTEM_RED, fg_color="#2A1A1A"
            ).pack(anchor="w", padx=12, pady=6)

        status_color = {"done": SYSTEM_GREEN, "error": SYSTEM_RED}.get(entry.status, LABEL_2)
        status_text  = {"done": "✓", "error": "Error"}.get(entry.status, "")

        if entry.status == "done":
            # Right-side cluster: [Preview] [✓] — placed as one canvas window
            right = _tk.Frame(row, bg=bg)
            ctk.CTkButton(
                right, text="Preview", font=FONT_TINY,
                text_color=ACCENT, fg_color=bg,
                hover_color=BG_CONTENT, border_width=0,
                height=22, width=60,
                command=lambda p=entry.dest: self._preview(p)
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(right, text="✓", font=FONT_SMALL,
                         text_color=SYSTEM_GREEN, fg_color=bg).pack(side="left")
            win_id = row.create_window(row.winfo_width() - 12, 28,
                                       window=right, anchor="e")
            row.bind("<Configure>",
                     lambda e, c=row, w=win_id: c.coords(w, e.width - 12, 28))
        else:
            status_lbl = ctk.CTkLabel(row, text=status_text, font=FONT_SMALL,
                                      text_color=status_color, fg_color=bg)
            win_id = row.create_window(row.winfo_width() - 12, 28,
                                       window=status_lbl, anchor="e")
            row.bind("<Configure>",
                     lambda e, c=row, w=win_id: c.coords(w, e.width - 12, 28))

    # ── Scroll — NSEvent local monitor (macOS PyInstaller fix) ───────────────
    # <MouseWheel> events are not delivered to bundled Tk on macOS.
    # We intercept NSScrollWheel events directly via pyobjc and drive the
    # canvas from the main thread via root.after(0, ...).

    def _setup_ns_scroll(self):
        NSScrollWheel = 1 << 22   # NSEventMaskScrollWheel
        window = self

        def _handler(ns_event):
            dy = ns_event.scrollingDeltaY()
            if dy == 0:
                return ns_event
            # Route through thread-safe queue — AppKit thread must not call
            # root.after() directly (Python 3.13 GIL/Tcl AfterProc SIGABRT).
            direction = -1 if dy > 0 else 1
            window._ui_queue.put(lambda d=direction: window._ns_scroll(d))
            return ns_event

        self._ns_scroll_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSScrollWheel, _handler
        )

    def _ns_scroll(self, direction: int):
        if not self._scroll.winfo_ismapped():
            return
        canvas = self._scroll._parent_canvas
        if canvas.yview() == (0.0, 1.0):
            return
        canvas.yview_scroll(direction * 3, "units")

    # ── Conversion ────────────────────────────────────────────────────────────

    def _start_conversion(self):
        if not self._files or self._conv_thread:
            return
        self._show_state("converting")
        # Global indeterminate bar — honest "working" signal (Jakob H1 + Rams H6)
        self._progress.configure(mode="indeterminate")
        self._progress.start()
        self._conv_thread = threading.Thread(target=self._run_conversion, daemon=True)
        self._conv_thread.start()

    def _run_conversion(self):
        total = len(self._files)
        done_count = 0

        for i, entry in enumerate(self._files):
            entry.status = "converting"
            self._ui_queue.put(self._rebuild_list)
            self._ui_queue.put(lambda i=i, t=total: self._set_progress(i, t))

            result = convert_file(str(entry.path))

            if result["ok"]:
                try:
                    # Auto-increment if destination already exists
                    dest = entry.dest
                    if dest.exists():
                        n = 1
                        while True:
                            candidate = dest.parent / f"{dest.stem}_{n}.md"
                            if not candidate.exists():
                                dest = candidate
                                break
                            n += 1
                        entry.dest = dest
                    entry.dest.write_text(result["markdown"], encoding="utf-8")
                    try:
                        src_stat = entry.path.stat()
                        os.utime(entry.dest, (src_stat.st_atime, src_stat.st_mtime))
                    except OSError:
                        pass
                    entry.status = "done"
                    entry.method = result["method"]
                    done_count += 1
                except Exception as e:
                    entry.status = "error"
                    entry.error_msg = f"Could not write output: {e}"
            else:
                entry.status = "error"
                entry.error_msg = result.get("error", "Unknown error")

            self._ui_queue.put(self._rebuild_list)

        self._ui_queue.put(lambda: self._finish_conversion(done_count, total))

    def _set_progress(self, current_idx: int, total: int):
        # Show macro position without a fabricated percentage (Jakob H1 + Rams H6)
        pct = current_idx / total if total > 0 else 0
        self._progress.set(pct)
        self._status_label.configure(
            text=f"Converting file {current_idx + 1} of {total}…",
            text_color=LABEL_2
        )

    def _finish_conversion(self, done: int, total: int):
        self._conv_thread = None
        self._progress.stop()
        self._progress.configure(mode="determinate")
        self._progress.set(1.0)
        errors = total - done
        if errors == 0:
            self._status_label.configure(
                text=f"✓  {done} file{'s' if done != 1 else ''} converted",
                text_color=SYSTEM_GREEN
            )
        else:
            self._status_label.configure(
                text=f"⚠  {done} converted, {errors} failed — use 'Open in Finder' on error files",
                text_color=SYSTEM_RED
            )
        self._show_state("done")
        self._rebuild_list()


# ── First-run setup ───────────────────────────────────────────────────────────

def _run_setup():
    """Polished first-run setup: install docling + pre-warm AI models."""
    root = ctk.CTk()
    root.title("MarkSign — Setup")
    W, H = 460, 310
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    root.resizable(False, False)
    root.configure(fg_color=BG_WINDOW)
    root.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))

    # Logo
    try:
        pil = Image.open(_LOGO_PATH).convert("RGBA").resize((48, 48), Image.LANCZOS)
        logo_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(48, 48))
        ctk.CTkLabel(root, image=logo_img, text="", fg_color="transparent").pack(pady=(28, 0))
    except Exception:
        pass

    ctk.CTkLabel(root, text="Setting up MarkSign",
                 font=("SF Pro Text", 18, "bold"), text_color=LABEL,
                 fg_color="transparent").pack(pady=(10, 4))

    lbl = ctk.CTkLabel(root, text="Installing conversion engine…",
                       font=FONT_BODY, text_color=LABEL_2, fg_color="transparent")
    lbl.pack(pady=(0, 14))

    bar = ctk.CTkProgressBar(root, width=340, mode="indeterminate",
                             progress_color=ACCENT)
    bar.pack()
    bar.start()

    detail = ctk.CTkLabel(root,
                          text="One-time setup — takes 2–5 minutes on first launch.",
                          font=FONT_TINY, text_color=LABEL_2, fg_color="transparent")
    detail.pack(pady=(10, 0))

    _setup_q: queue.SimpleQueue = queue.SimpleQueue()

    def _poll_setup_queue():
        try:
            while True:
                fn = _setup_q.get_nowait()
                fn()
        except queue.Empty:
            pass
        if root.winfo_exists():
            root.after(50, _poll_setup_queue)

    root.after(50, _poll_setup_queue)

    def install():
        # Phase 1: pip install docling
        try:
            subprocess.run(
                _pip_cmd() + ["install", "docling", "--quiet"],
                check=True, capture_output=True,
            )
        except Exception:
            _setup_q.put(lambda: _setup_done(root, bar, lbl, detail, False))
            return

        # Phase 2: pre-warm AI models (docling downloads ONNX models on first init)
        _setup_q.put(lambda: lbl.configure(text="Downloading AI models…"))
        _setup_q.put(lambda: detail.configure(
            text="Layout + OCR models (~300 MB) — first conversion will be instant."))
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401
            DocumentConverter()
        except Exception:
            pass  # non-fatal — models will download on first conversion

        _setup_q.put(lambda: _setup_done(root, bar, lbl, detail, True))

    threading.Thread(target=install, daemon=True).start()
    root.mainloop()


def _setup_done(root, bar, lbl, detail, ok):
    bar.stop()
    if ok:
        _SETUP_FLAG.touch()   # skip setup on all future launches
        lbl.configure(text="✓  MarkSign is ready", text_color=SYSTEM_GREEN)
        detail.configure(text="")
        root.after(1500, root.destroy)
    else:
        lbl.configure(text="Setup failed — PDF conversion unavailable", text_color=SYSTEM_RED)
        detail.configure(text="You can still convert DOCX, EPUB, PPTX, and XLSX files.",
                         text_color=LABEL_2)
        ctk.CTkButton(root, text="Continue", fg_color=ACCENT, width=120,
                      command=root.destroy).pack(pady=16)


# ── Finder Quick Action (right-click "Convert with MarkSign") ─────────────────

_FINDER_SERVICE_SCRIPT = """\
#!/bin/bash
for f in "$@"
do
    curl -sf -G "http://127.0.0.1:57892/open" --data-urlencode "path=$f" &
done
wait
"""

def _install_finder_service():
    """Write Automator Quick Action to ~/Library/Services/ — idempotent."""
    marker = Path.home() / ".marksign" / "finder_service_installed"
    if marker.exists():
        return

    service_dir = (
        Path.home() / "Library" / "Services"
        / "Convert with MarkSign.workflow" / "Contents"
    )
    service_dir.mkdir(parents=True, exist_ok=True)

    a_uuid = str(uuid.uuid4()).upper()
    i_uuid = str(uuid.uuid4()).upper()
    o_uuid = str(uuid.uuid4()).upper()

    doc = {
        "AMApplicationBuild": "521",
        "AMApplicationVersion": "2.10",
        "AMDocumentSpecificationVersion": "0.9",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": True,
                        "Types": ["com.apple.cocoa.path"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMParameterProperties": {
                        "COMMAND_STRING": {},
                        "inputMethod": {},
                        "shell": {},
                        "source": {},
                    },
                    "AMProvides": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.path"],
                    },
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": _FINDER_SERVICE_SCRIPT,
                        "inputMethod": 1,   # pass as arguments, not stdin
                        "shell": "/bin/bash",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.automator.runshe",
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": True,
                    "Category": ["AMCategoryUtilities"],
                    "Class Name": "RunShellScriptAction",
                    "InputUUID": i_uuid,
                    "Keywords": ["Shell", "Script"],
                    "OutputUUID": o_uuid,
                    "UUID": a_uuid,
                    "UnlocalizedApplications": ["Automator"],
                    "arguments": {},
                    "isViewVisible": True,
                    "location": "309.000000:153.000000",
                    "nibPath": (
                        "/System/Library/Automator/Run Shell Script.action"
                        "/Contents/Resources/en.lproj/main.nib"
                    ),
                },
                "isViewVisible": True,
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }

    with open(service_dir / "document.wflow", "wb") as fh:
        plistlib.dump(doc, fh)

    info = {
        "NSServices": [
            {
                "NSMenuItem": {"default": "Convert with MarkSign"},
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {
                    "NSApplicationIdentifier": "com.apple.finder",
                },
                "NSSendFileTypes": ["public.data"],
            }
        ]
    }
    with open(service_dir / "Info.plist", "wb") as fh:
        plistlib.dump(info, fh)

    # Tell macOS to register the new service immediately
    subprocess.run(
        ["/System/Library/CoreServices/pbs", "-update"],
        capture_output=True, check=False,
    )

    marker.parent.mkdir(exist_ok=True)
    marker.touch()


# ── Reader registration ───────────────────────────────────────────────────────



# ── DMG cleanup offer ────────────────────────────────────────────────────────

def _offer_dmg_cleanup(root: ctk.CTk):
    """If a MarkSign DMG is still mounted, offer to eject it (and trash the file)."""
    import subprocess, plistlib
    volume = Path("/Volumes/MarkSign")
    if not volume.exists():
        return

    # Find the source .dmg path via hdiutil
    dmg_path = None
    try:
        out = subprocess.run(
            ["hdiutil", "info", "-plist"],
            capture_output=True, timeout=10,
        )
        info = plistlib.loads(out.stdout)
        for img in info.get("images", []):
            for entity in img.get("system-entities", []):
                if entity.get("mount-point") == str(volume):
                    dmg_path = img.get("image-path")
                    break
            if dmg_path:
                break
    except Exception:
        pass

    dialog = ctk.CTkToplevel(root)
    dialog.title("Installation Complete")
    dialog.resizable(False, False)
    dialog.configure(fg_color=BG_WINDOW)
    dialog.update_idletasks()
    sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
    dialog.geometry(f"380x160+{(sw - 380) // 2}+{(sh - 160) // 2}")
    dialog.lift()
    dialog.focus_force()
    dialog.grab_set()

    ctk.CTkLabel(dialog,
                 text="MarkSign is installed.\nEject the installer disk image?",
                 font=FONT_BODY, text_color=LABEL, fg_color="transparent").pack(pady=(24, 16))

    btns = ctk.CTkFrame(dialog, fg_color="transparent")
    btns.pack()

    def eject():
        dialog.destroy()
        try:
            subprocess.run(["hdiutil", "detach", str(volume), "-quiet"], timeout=10)
        except Exception:
            pass
        if dmg_path and Path(dmg_path).exists():
            try:
                import AppKit
                ws = AppKit.NSWorkspace.sharedWorkspace()
                ws.recycleURLs_completionHandler_(
                    [AppKit.NSURL.fileURLWithPath_(dmg_path)], None
                )
            except Exception:
                pass

    def skip():
        dialog.destroy()

    ctk.CTkButton(btns, text="Keep", width=100, fg_color=BG_ROW,
                  hover_color=SEPARATOR, text_color=LABEL_2, command=skip).pack(side="left", padx=8)
    eject_btn = ctk.CTkButton(btns, text="Eject", width=100, fg_color=ACCENT,
                              hover_color="#0066CC", command=eject)
    eject_btn.pack(side="left", padx=8)
    dialog.bind("<Return>", lambda e: eject())
    dialog.after(100, eject_btn.focus_set)


# ── About menu interception ───────────────────────────────────────────────────

class _AboutDelegate(NSObject):
    root_ = None
    window_ = None
    def showAboutPanel_(self, sender):
        if self.root_:
            _show_about(self.root_)
    def showWindow_(self, sender):
        if self.window_:
            self.window_.show()


_about_delegate_ref = [None]   # keep alive


def _fix_about_menu(root: ctk.CTk, window=None):
    """Replace the native 'About MarkSign' NSMenuItem with our custom dialog."""
    delegate = _AboutDelegate.alloc().init()
    delegate.root_ = root
    delegate.window_ = window
    _about_delegate_ref[0] = delegate

    app = _NSApp.sharedApplication()
    main_menu = app.mainMenu()
    if not main_menu:
        return
    app_menu_item = main_menu.itemAtIndex_(0)
    if not app_menu_item:
        return
    app_menu = app_menu_item.submenu()
    if not app_menu:
        return
    for i in range(app_menu.numberOfItems()):
        item = app_menu.itemAtIndex_(i)
        title = str(item.title()) if item.title() else ""
        if "About" in title:
            item.setTarget_(delegate)
            item.setAction_("showAboutPanel:")
            break

    # Add "New Window" Cmd+N to the File menu (index 1)
    try:
        file_menu_item = main_menu.itemAtIndex_(1)
        file_menu = file_menu_item.submenu() if file_menu_item else None
        if file_menu:
            new_win = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "New Window", "showAbout:", "n"
            )
            new_win.setTarget_(delegate)
            new_win.setAction_("showWindow:")
            file_menu.insertItem_atIndex_(new_win, 0)
    except Exception:
        pass


# ── About dialog ─────────────────────────────────────────────────────────────

def _show_about(root: ctk.CTk):
    dlg = ctk.CTkToplevel(root)
    dlg.title("About MarkSign")
    dlg.geometry("360x340")
    dlg.resizable(False, False)
    dlg.configure(fg_color=BG_WINDOW)
    dlg.lift(); dlg.focus_force(); dlg.grab_set()

    # Logo
    try:
        logo_pil = Image.open(_LOGO_PATH).convert("RGBA").resize((80, 80), Image.LANCZOS)
        logo_img = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(80, 80))
        ctk.CTkLabel(dlg, image=logo_img, text="", fg_color="transparent").pack(pady=(28, 8))
    except Exception:
        pass

    ctk.CTkLabel(dlg, text="MarkSign", font=("SF Pro Display", 22, "bold"),
                 text_color=LABEL, fg_color="transparent").pack()
    ctk.CTkLabel(dlg, text="Document to Markdown Converter",
                 font=FONT_SMALL, text_color=LABEL_2, fg_color="transparent").pack(pady=(2, 0))
    ctk.CTkLabel(dlg, text="Version 0.1.2",
                 font=FONT_TINY, text_color=LABEL_2, fg_color="transparent").pack(pady=(2, 16))

    ctk.CTkFrame(dlg, height=1, fg_color=SEPARATOR).pack(fill="x", padx=24)

    info = ctk.CTkFrame(dlg, fg_color="transparent")
    info.pack(pady=12)
    ctk.CTkLabel(info, text="Made by Faber-Ludens Pro",
                 font=FONT_SMALL, text_color=LABEL, fg_color="transparent").pack()
    ctk.CTkLabel(info, text="marksign@faberludens.pro",
                 font=FONT_SMALL, text_color=ACCENT, fg_color="transparent",
                 cursor="pointinghand").pack(pady=(2, 0))

    ctk.CTkFrame(dlg, height=1, fg_color=SEPARATOR).pack(fill="x", padx=24)

    ctk.CTkButton(dlg, text="Close", width=100, fg_color=BG_ROW,
                  hover_color=SEPARATOR, text_color=LABEL_2,
                  command=dlg.destroy).pack(pady=16)


# ── Help dialog ───────────────────────────────────────────────────────────────

def _show_help(root: ctk.CTk):
    help_md = _resource("marksign_help.md")
    if help_md.exists():
        subprocess.Popen(_companion("marksign_preview") + [str(help_md)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    # Fallback: inline dialog
    dlg = ctk.CTkToplevel(root)
    dlg.title("MarkSign Help")
    dlg.geometry("400x300")
    dlg.configure(fg_color=BG_WINDOW)
    dlg.lift(); dlg.focus_force()
    ctk.CTkLabel(dlg, text="Help file not found.", font=FONT_BODY,
                 text_color=LABEL_2, fg_color="transparent").pack(expand=True)
    ctk.CTkButton(dlg, text="Close", command=dlg.destroy).pack(pady=16)


# ── Entry point ───────────────────────────────────────────────────────────────

_LOCK_FILE = Path.home() / ".marksign" / "running.lock"


def _acquire_lock() -> bool:
    """Return True if this is the only running instance; False if another is already up."""
    try:
        if _LOCK_FILE.exists():
            pid = int(_LOCK_FILE.read_text().strip())
            try:
                os.kill(pid, 0)   # 0 = check existence only
                # Process is alive — bring its window to front via IPC
                try:
                    import urllib.request
                    urllib.request.urlopen(f"http://127.0.0.1:{IPC_PORT}/show", timeout=1)
                except Exception:
                    pass
                return False
            except (ProcessLookupError, PermissionError):
                pass   # stale lock — process is gone
        _LOCK_FILE.write_text(str(os.getpid()))
        return True
    except Exception:
        return True   # can't determine — allow launch


def _release_lock():
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    # Single-instance guard
    if not _acquire_lock():
        sys.exit(0)

    import atexit
    atexit.register(_release_lock)

    # App name + dock icon (best-effort; definitive fix comes with PyInstaller)
    try:
        from AppKit import NSBundle
        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = "MarkSign"
        info["CFBundleDisplayName"] = "MarkSign"
    except Exception:
        pass

    # First-run setup (runs its own mainloop, blocks until done).
    # Skip if the flag file exists (written on first successful setup).
    if not _SETUP_FLAG.exists() and not docling_available():
        _run_setup()

    # Finder Quick Action — idempotent, runs once
    threading.Thread(target=_install_finder_service, daemon=True).start()

    # Build conversion window
    window = MarkSignWindow()
    _window_ref[0] = window
    window.build()

    # Dock icon + intercept native "About" panel — deferred after CTk starts
    def _setup_native():
        try:
            _NSApp.sharedApplication().setApplicationIconImage_(_logo_nsimage(512))
        except Exception:
            pass
        # Replace the native "About MarkSign" menu item action
        try:
            _fix_about_menu(window.root, window)
        except Exception:
            pass

    window.root.after(500, _setup_native)

    # Menu bar icon — disabled until v1.0 (set True to re-enable during development)
    _ENABLE_MENU_BAR = False
    if _ENABLE_MENU_BAR:
        subprocess.Popen(_companion("marksign_tray"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Start IPC server in background thread
    threading.Thread(target=_start_ipc_server, daemon=True).start()

    # Show window on launch
    window.show()

    # DMG cleanup offer after 3s (only if still mounted)
    window.root.after(3000, lambda: _offer_dmg_cleanup(window.root))

    # Main loop — runs on main thread, handles all CTk events
    window.root.mainloop()


if __name__ == "__main__":
    main()
