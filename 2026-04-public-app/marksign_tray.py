"""
MarkSign Tray — menu bar icon subprocess.

Runs pystray as a separate process so it can own NSApplication's main thread
without conflicting with the CTk main app.
Communicates with the main app via HTTP IPC on localhost:57892.
"""
import sys
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw
import pystray

# Logo path — works in dev and when frozen
if getattr(sys, "frozen", False):
    _LOGO_PATH = Path(sys._MEIPASS) / "logo-marksign.jpg"  # type: ignore[attr-defined]
else:
    _LOGO_PATH = Path(__file__).parent.parent / "logo-marksign.jpg"

IPC_PORT = 57892


def _ipc(path: str):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{IPC_PORT}{path}", timeout=2)
    except Exception:
        pass


def _make_icon() -> Image.Image:
    """
    Template icon derived from logo-marksign.jpg.
    Bright logo pixels → white with luminance-based alpha → crisp on dark menu bars.
    Falls back to a simple 'M' monogram if the logo file is missing.
    """
    size = 128
    try:
        src = Image.open(_LOGO_PATH).convert("RGB").resize((size, size), Image.LANCZOS)
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        src_px = src.load()
        res_px = result.load()
        for y in range(size):
            for x in range(size):
                r, g, b = src_px[x, y]
                lum = int(0.299 * r + 0.587 * g + 0.114 * b)
                if lum > 50:
                    alpha = min(255, (lum - 50) * 3)
                    res_px[x, y] = (255, 255, 255, alpha)
        return result
    except Exception:
        # Fallback: simple 'M' monogram
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w = size // 10
        d.line([(size//8, size*7//8), (size//8, size//8)],       fill=(255,255,255,255), width=w)
        d.line([(size//8, size//8), (size//2, size//2)],          fill=(255,255,255,255), width=w)
        d.line([(size//2, size//2), (size*7//8, size//8)],        fill=(255,255,255,255), width=w)
        d.line([(size*7//8, size//8), (size*7//8, size*7//8)],    fill=(255,255,255,255), width=w)
        return img


def _setup(icon: pystray.Icon):
    """Called in a background thread after pystray finishes initialising.
    Set visible=True (required). White-outline icon — no template mode needed."""
    icon.visible = True

    # Template mode OFF — icon is white strokes on transparent, visible on dark bars.
    try:
        img = icon._icon_image
        if img:
            img.setTemplate_(False)
            icon._status_item.button().setImage_(img)
    except Exception:
        pass


def main():
    def on_open(icon, item):   _ipc("/show")
    def on_about(icon, item):  _ipc("/about")
    def on_help(icon, item):   _ipc("/help")
    def on_quit(icon, item):
        _ipc("/quit")
        icon.stop()

    icon = pystray.Icon(
        "MarkSign",
        _make_icon(),
        "MarkSign",
        menu=pystray.Menu(
            pystray.MenuItem("Convert file",    on_open,  default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("About MarkSign",  on_about),
            pystray.MenuItem("Help",            on_help),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit MarkSign",   on_quit),
        ),
    )
    icon.run(setup=_setup)   # setup called after NSApp starts


if __name__ == "__main__":
    main()
