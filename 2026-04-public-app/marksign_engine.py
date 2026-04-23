#!/usr/bin/env python3
"""
MarkSign Engine — local document-to-Markdown conversion.

Extracted from biblios_brain.py. All conversion is local — no API calls,
no internet required after first-run docling setup.

Supported formats (v1):
    PDF   — docling → pymupdf → markitdown
    DOCX  — pandoc → markitdown → libreoffice
    DOC   — libreoffice → pandoc → markitdown  (hidden, not shown in UI)
    PPTX  — markitdown
    EPUB  — markitdown → pandoc
    XLSX  — markitdown
    TXT   — direct read
    RTF   — pandoc → markitdown

Usage:
    from marksign_engine import convert_file

    result = convert_file("/path/to/document.pdf")
    if result["ok"]:
        print(result["markdown"])
    else:
        print("Error:", result["error"])

    # CLI smoke test:
    python marksign_engine.py /path/to/document.pdf
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger("marksign_engine")

# When the app is frozen (PyInstaller), docling is installed at runtime into
# ~/.marksign/venv/ — inject that into sys.path so imports succeed.
if getattr(sys, "frozen", False):
    _venv_lib = Path.home() / ".marksign" / "venv" / "lib"
    if _venv_lib.exists():
        for _sp in _venv_lib.glob("python*/site-packages"):
            if str(_sp) not in sys.path:
                sys.path.insert(0, str(_sp))
            break


# ── Converters ──────────────────────────────────────────────────────────────
# All external imports are lazy (inside each function).
# This keeps startup fast and the base DMG small.


def _convert_with_docling(path):
    """Convert PDF using IBM docling.

    When frozen (PyInstaller), docling's import chain pulls in torch/transformers
    which need stdlib modules absent from base_library.zip.  Run docling in the
    venv Python subprocess instead — it has a full stdlib and all packages.
    In dev mode (not frozen), import directly as before.
    """
    if getattr(sys, "frozen", False):
        # ── Subprocess path (frozen app) ────────────────────────────────────
        import subprocess
        venv_python = Path.home() / ".marksign" / "venv" / "bin" / "python3"
        if not venv_python.exists():
            return "", "docling-not-installed"

        _SCRIPT = (
            "import sys;"
            "from docling.document_converter import DocumentConverter;"
            "r=DocumentConverter().convert(sys.argv[1]);"
            "txt=r.document.export_to_markdown();"
            "sys.exit(1) if len(txt.strip())<100 else print(txt,end='')"
        )
        try:
            proc = subprocess.run(
                [str(venv_python), "-c", _SCRIPT, str(path)],
                capture_output=True, text=True, timeout=180,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout, "docling"
            if proc.returncode == 1:
                return "", "docling-no-text"
            # non-zero exit → log stderr for diagnosis
            _log = Path.home() / ".marksign" / "debug.log"
            with open(_log, "a") as f:
                f.write(f"[docling-sub] rc={proc.returncode} {proc.stderr[:800]}\n")
            return "", f"docling-error: {proc.stderr[:120]}"
        except subprocess.TimeoutExpired:
            return "", "docling-timeout"
        except Exception as e:
            return "", f"docling-error: {e}"
    else:
        # ── Direct import path (dev / non-frozen) ──────────────────────────
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(str(path))
            text = result.document.export_to_markdown()
            if len(text.strip()) < 100:
                return "", "docling-no-text"
            return text, "docling"
        except ImportError:
            return "", "docling-not-installed"
        except Exception as e:
            return "", f"docling-error: {e}"


def _convert_with_pymupdf(path):
    """Convert PDF using PyMuPDF with font-size-based heading detection."""
    try:
        import fitz
        from collections import Counter

        doc = fitz.open(str(path))

        # Pass 1: collect all font sizes to identify body text size
        font_sizes = Counter()
        for page in doc:
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for block in blocks:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        size = round(span["size"], 1)
                        text_len = len(span["text"].strip())
                        if text_len > 0:
                            font_sizes[size] += text_len

        if not font_sizes:
            doc.close()
            return "", "pymupdf-no-text"

        body_size = font_sizes.most_common(1)[0][0]

        # Pass 2: extract text with heading markers based on font size
        output_parts = []
        for page in doc:
            page_lines = []
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for block in blocks:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    line_text = ""
                    line_size = 0
                    line_flags = 0
                    for span in line["spans"]:
                        line_text += span["text"]
                        if span["size"] > line_size:
                            line_size = round(span["size"], 1)
                            line_flags = span["flags"]
                    line_text = line_text.strip()
                    if not line_text:
                        continue

                    ratio = line_size / body_size if body_size > 0 else 1.0
                    is_bold = bool(line_flags & 2 ** 4)

                    if ratio >= 1.8 and len(line_text) < 200:
                        page_lines.append(f"## {line_text}")
                    elif ratio >= 1.4 and len(line_text) < 200:
                        page_lines.append(f"### {line_text}")
                    elif (ratio >= 1.15 or is_bold) and len(line_text) < 150 and not line_text.endswith(('.', ',', ';', ':')):
                        page_lines.append(f"#### {line_text}")
                    else:
                        page_lines.append(line_text)

            output_parts.append("\n".join(page_lines))

        doc.close()
        text = "\n\n".join(output_parts)
        return text, "pymupdf"

    except ImportError:
        return "", "pymupdf-not-installed"
    except Exception as e:
        return "", f"pymupdf-error: {e}"


def _convert_with_markitdown(path):
    """Convert using Microsoft MarkItDown. Handles DOCX, PPTX, XLSX, EPUB, and more."""
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(str(path))
        text = result.text_content if hasattr(result, "text_content") else str(result)
        return text, "markitdown"
    except ImportError:
        return "", "markitdown-not-installed"
    except Exception as e:
        return "", f"markitdown-error: {e}"


def _convert_with_libreoffice(path):
    """Convert using LibreOffice headless. Handles .doc and malformed Office files."""
    import subprocess, shutil, tempfile, os
    soffice = shutil.which("soffice")
    if not soffice:
        return "", "libreoffice-not-installed"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "txt:Text", "--outdir", tmpdir, str(path)],
                capture_output=True, text=True, timeout=60,
            )
            stem = Path(path).stem
            txt_path = os.path.join(tmpdir, stem + ".txt")
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read(), "libreoffice"
            return "", f"libreoffice-error: {result.stderr[:200]}"
    except Exception as e:
        return "", f"libreoffice-error: {e}"


def _convert_with_pandoc(path, to_format="markdown"):
    """Convert using pandoc. Best for EPUB, DOCX, RTF — preserves structure."""
    import subprocess, shutil
    if not shutil.which("pandoc"):
        return "", "pandoc-not-installed"
    try:
        result = subprocess.run(
            ["pandoc", "--to", to_format, "--wrap=none", str(path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return "", f"pandoc-error: {result.stderr[:200]}"
        return result.stdout, "pandoc"
    except Exception as e:
        return "", f"pandoc-error: {e}"


# ── Converter chain ──────────────────────────────────────────────────────────
# Priority order per format. First converter that returns >100 chars wins.
# DOC is hidden support (not shown in UI format chips).

CONVERTER_CHAIN = {
    ".pdf":  [_convert_with_docling, _convert_with_pymupdf, _convert_with_markitdown],
    ".docx": [_convert_with_pandoc, _convert_with_markitdown, _convert_with_libreoffice],
    ".doc":  [_convert_with_libreoffice, _convert_with_pandoc, _convert_with_markitdown],
    ".pptx": [_convert_with_markitdown],
    ".epub": [_convert_with_markitdown, _convert_with_pandoc],
    ".xlsx": [_convert_with_markitdown],
    ".xls":  [_convert_with_markitdown],
    ".rtf":  [_convert_with_pandoc, _convert_with_markitdown],
    ".txt":  ["direct"],
    ".md":   ["direct"],
}

# Formats shown in UI (for validation and format chip display)
SUPPORTED_FORMATS_V1 = {".pdf", ".doc", ".docx", ".pptx", ".epub", ".xlsx", ".txt", ".rtf"}


# ── Public API ───────────────────────────────────────────────────────────────

def convert_file(source_path):
    """Convert a document to Markdown.

    Returns a dict:
        {"ok": True,  "markdown": str, "chars": int, "method": str}
        {"ok": False, "error": str, "method": str}
    """
    path = Path(source_path)
    if not path.exists():
        return {"ok": False, "error": f"File not found: {path}", "method": "none"}

    suffix = path.suffix.lower()

    if suffix not in CONVERTER_CHAIN:
        return {"ok": False, "error": f"Unsupported format: {suffix}", "method": "none"}

    chain = CONVERTER_CHAIN[suffix]

    # Direct read for plain text
    if chain == ["direct"]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return {"ok": True, "markdown": text, "chars": len(text), "method": "direct"}

    # Try each converter in order; first one that returns >100 chars wins
    last_method = "none"
    for converter in chain:
        if callable(converter):
            text, last_method = converter(path)
            if text and len(text.strip()) > 100:
                return {"ok": True, "markdown": text, "chars": len(text), "method": last_method}

    return {"ok": False, "error": f"All converters failed for {suffix}", "method": last_method}


def docling_available():
    """Check whether docling is installed (for first-run setup screen)."""
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401
        return True
    except ImportError:
        return False


# ── CLI smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python marksign_engine.py <file>")
        sys.exit(1)

    result = convert_file(sys.argv[1])
    if result["ok"]:
        print(f"✓  Converted via {result['method']} — {result['chars']:,} chars")
        print("─" * 60)
        print(result["markdown"][:2000])
        if result["chars"] > 2000:
            print(f"\n[... {result['chars'] - 2000:,} more chars ...]")
    else:
        print(f"✗  Failed ({result['method']}): {result['error']}")
        sys.exit(1)
