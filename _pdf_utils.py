"""
PDF processing utilities for text extraction, image rendering, and OCR.
Uses pdfplumber for text, pypdfium2 for page images, PaddleOCR via subprocess.
"""
from __future__ import annotations

import os
import json
import logging
import subprocess
import sys
import tempfile
import shutil
import threading
from dataclasses import dataclass, field

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image


@dataclass
class ExtractionResult:
    """Result of PDF content extraction."""
    text: str = ""                                  # pdfplumber text (always)
    ocr_text: str = ""                              # PaddleOCR text (if run)
    images: list = field(default_factory=list)      # page images (if vision)
    quality_score: float = 0.0
    page_count: int = 0
    sources: list = field(default_factory=list)     # e.g. ["text"], ["text","ocr"], ["text","vision"]
    warnings: list = field(default_factory=list)    # non-fatal issues (OCR failures, etc.)


_MOJIBAKE_MARKERS = (
    "\u00c3",
    "\u00c2",
    "\u00e2\u201a",
    "\u00e2\u20ac\u0153",
    "\u00e2\u20ac",
    "\u00e2\u20ac\u201c",
    "\u00e2\u20ac\u201d",
)


def _open_pdf_stream(pdf_path: str):
    """Open a PDF as a binary stream for libraries that mishandle some paths."""
    return open(os.fspath(pdf_path), "rb")


def _mojibake_marker_count(text: str) -> int:
    return sum(text.count(marker) for marker in _MOJIBAKE_MARKERS)


def _maybe_fix_mojibake(text: str) -> str:
    """Repair common UTF-8/legacy-codepage mojibake when it is clearly better."""
    if not text or _mojibake_marker_count(text) == 0:
        return text

    original_markers = _mojibake_marker_count(text)
    for legacy_encoding in ("cp1252", "latin-1"):
        try:
            repaired = text.encode(legacy_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired and _mojibake_marker_count(repaired) < original_markers:
            logging.info("Applied mojibake repair heuristic to extracted PDF text")
            return repaired
    return text


def _extract_text_with_pdfplumber(pdf_path: str, max_pages: int, repair: bool = False) -> str:
    """Extract text while isolating per-page parser failures."""
    all_text = []
    with _open_pdf_stream(pdf_path) as stream:
        with pdfplumber.open(
            stream,
            unicode_norm="NFC",
            raise_unicode_errors=False,
            repair=repair,
        ) as pdf:
            pages_to_read = min(max_pages, len(pdf.pages))
            for i in range(pages_to_read):
                try:
                    page = pdf.pages[i]
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        all_text.append(f"Page {i + 1}:\n{page_text}")
                except Exception as e:
                    logging.warning(f"Error extracting text from page {i + 1} of {pdf_path}: {e}")
    return "\n\n".join(all_text)


def extract_text(pdf_path: str, max_pages: int = 3) -> tuple:
    """Extract text using pdfplumber. Returns (text, quality_score)."""
    try:
        text = _extract_text_with_pdfplumber(pdf_path, max_pages, repair=False)
    except Exception as e:
        logging.warning(f"Primary text extraction failed for {pdf_path}: {e}")
        try:
            text = _extract_text_with_pdfplumber(pdf_path, max_pages, repair=True)
            logging.info(f"Recovered text extraction via pdfplumber repair mode: {pdf_path}")
        except Exception as repair_error:
            logging.error(f"Error extracting text from {pdf_path}: {repair_error}")
            return "", 0.0

    text = _maybe_fix_mojibake(text)
    quality = assess_text_quality(text)
    logging.info(f"Extracted text quality: {quality:.2f}, length: {len(text)} chars")
    logging.debug(f"Full extracted text ({len(text)} chars):\n{text}")
    return text, quality


def assess_text_quality(text: str) -> float:
    """Score 0.0-1.0 based on text characteristics.

    Heuristics: character count, alphanumeric ratio, average word length.
    """
    if not text or not text.strip():
        return 0.0

    # Character count score (0-0.4)
    char_count = len(text.strip())
    char_score = min(char_count / 500, 1.0) * 0.4

    # Alphanumeric ratio (0-0.3)
    alnum_count = sum(1 for c in text if c.isalnum())
    total_non_space = sum(1 for c in text if not c.isspace())
    alnum_ratio = alnum_count / total_non_space if total_non_space > 0 else 0
    alnum_score = alnum_ratio * 0.3

    # Average word length (0-0.3) — very short or very long words indicate garbage
    words = text.split()
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        # Ideal average word length is 3-8 characters
        if 3 <= avg_word_len <= 8:
            word_score = 0.3
        elif 2 <= avg_word_len <= 12:
            word_score = 0.15
        else:
            word_score = 0.05
    else:
        word_score = 0.0

    return min(char_score + alnum_score + word_score, 1.0)


def render_pages_to_images(pdf_path: str, max_pages: int = 3, scale: float = 2.0) -> list[Image.Image]:
    """Render PDF pages to PIL images using pypdfium2 v5."""
    images = []
    pdf = None
    stream = None
    try:
        stream = _open_pdf_stream(pdf_path)
        pdf = pdfium.PdfDocument(stream, autoclose=False)
        pages_to_render = min(max_pages, len(pdf))
        if pages_to_render == 0:
            logging.warning(f"PDF has 0 pages: {pdf_path}")
            return images

        for i in range(pages_to_render):
            page = None
            bitmap = None
            try:
                page = pdf[i]
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                images.append(pil_image)
            except Exception as page_error:
                logging.warning(f"Error rendering page {i + 1} from {pdf_path}: {page_error}")
            finally:
                if bitmap is not None and hasattr(bitmap, "close"):
                    bitmap.close()
                if page is not None:
                    page.close()
    except Exception as e:
        logging.error(f"Error rendering pages from {pdf_path}: {e}")
    finally:
        if pdf is not None:
            pdf.close()
        if stream is not None:
            stream.close()
    return images


def _get_bridge_script_path() -> str:
    """Get path to the PaddleOCR bridge script, handling PyInstaller."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "_paddleocr_bridge.py")


def _get_paddleocr_python(config: dict) -> str | None:
    """Get path to python executable inside PaddleOCR venv."""
    venv = config.get("paddleocr", {}).get("venv_path", "")
    if not venv:
        # Platform-specific default venv location
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA", "")
        else:
            base = os.path.join(os.path.expanduser("~"), ".local", "share")
        if base:
            venv = os.path.join(base, "autorename-pdf", "paddleocr-venv")

    if not venv:
        return None

    # Platform-specific venv layout: Scripts/python.exe (Win) vs bin/python (Unix)
    if sys.platform == "win32":
        python = os.path.join(venv, "Scripts", "python.exe")
    else:
        python = os.path.join(venv, "bin", "python")
    return python if os.path.isfile(python) else None


def _paddleocr_available(config: dict) -> bool:
    """Check if PaddleOCR venv exists and is functional."""
    return _get_paddleocr_python(config) is not None


def ocr_with_paddleocr(images: list[Image.Image], config: dict) -> str:
    """Save images as temp files, pipe paths to bridge script, collect OCR text."""
    python = _get_paddleocr_python(config)
    if not python:
        logging.error("PaddleOCR python not found")
        return ""

    bridge_src = _get_bridge_script_path()
    paddleocr_cfg = config.get("paddleocr", {})
    lang = paddleocr_cfg.get("language", "en")
    device = paddleocr_cfg.get("device", "auto")
    det_model = paddleocr_cfg.get("detection_model", "")
    det_limit = paddleocr_cfg.get("det_limit_side_len", 736)
    cpu_threads = paddleocr_cfg.get("cpu_threads", 4)

    tmp_dir = tempfile.mkdtemp(prefix="autorename_ocr_")
    try:
        # PyInstaller isolation: when frozen, the bridge script lives in _MEIPASS.
        # Python adds the script's directory to sys.path[0], so _MEIPASS becomes
        # sys.path[0] in the child process. The bundled socket.py/_socket.pyd then
        # shadow the venv's stdlib, causing "python311.dll conflicts" on import.
        # Fix: copy the bridge script to a clean temp dir so sys.path[0] is clean.
        # Also reset SetDllDirectoryW (PyInstaller bootloader sets it to _MEIPASS,
        # which is inherited by child processes).
        # See: https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
        # See: https://github.com/pyinstaller/pyinstaller/issues/3795
        meipass = getattr(sys, '_MEIPASS', None)
        env = os.environ.copy()
        if meipass:
            # Copy bridge script out of _MEIPASS to avoid polluting child sys.path
            bridge = os.path.join(tmp_dir, os.path.basename(bridge_src))
            shutil.copy2(bridge_src, bridge)

            # Reset DLL search order (defense-in-depth)
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.kernel32.SetDllDirectoryW(None)

            # Clean PATH and PyInstaller env vars
            meipass_norm = os.path.normpath(meipass)
            path_dirs = env.get("PATH", "").split(os.pathsep)
            path_dirs = [d for d in path_dirs if os.path.normpath(d) != meipass_norm]
            env["PATH"] = os.pathsep.join(path_dirs)
            for var in ("_MEIPASS2", "PYTHONPATH", "PYTHONHOME"):
                env.pop(var, None)
        else:
            bridge = bridge_src

        cmd = [python, bridge, lang, "--device", device,
               "--det-limit", str(det_limit),
               "--cpu-threads", str(cpu_threads)]
        if det_model:
            cmd.extend(["--det-model", det_model])

        logging.info(f"Starting PaddleOCR (lang={lang}, device={device})")

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            env=env,
        )

        # Stream stderr in background so model-download progress is visible.
        # Lines about active model downloads are logged at WARNING level
        # (always visible) so users see first-time model download progress.
        def _drain_stderr():
            for line in proc.stderr:
                line = line.rstrip()
                if not line:
                    continue
                low = line.lower()
                if ("downloading" in low or "fetching" in low
                        or "download complete" in low):
                    logging.warning(f"PaddleOCR: {line}")
                else:
                    logging.info(f"PaddleOCR: {line}")
        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        all_text = []
        for i, img in enumerate(images):
            tmp_path = os.path.join(tmp_dir, f"page_{i}.png")
            img.save(tmp_path)
            try:
                proc.stdin.write(tmp_path + "\n")
                proc.stdin.flush()
                line = proc.stdout.readline()
                if not line:
                    logging.warning(f"PaddleOCR bridge returned empty line for page {i + 1}")
                    continue
                result = json.loads(line)
                if result["status"] == "ok":
                    all_text.append(f"Page {i + 1}:\n{result['text']}")
                else:
                    logging.warning(f"PaddleOCR error on page {i + 1}: {result.get('message', 'unknown')}")
            except (json.JSONDecodeError, BrokenPipeError, OSError) as e:
                logging.warning(f"PaddleOCR bridge communication error on page {i + 1}: {e}")
                break  # Bridge is dead, no point sending more pages

        try:
            proc.stdin.close()
            proc.wait(timeout=30)
        except Exception as e:
            logging.warning(f"PaddleOCR process cleanup: {e}")
            proc.kill()
            proc.wait(timeout=5)

        stderr_thread.join(timeout=5)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return "\n\n".join(all_text)


def _should_run_step(setting, quality: float, threshold: float) -> bool:
    """Determine if an optional extraction step (OCR/vision) should run.

    setting: False (disabled), True (always), or "auto" (run when quality < threshold).
    """
    if setting is True or setting == "true":
        return True
    if setting is False or setting == "false" or not setting:
        return False
    # "auto" — run only when text quality is below threshold
    return quality < threshold


def extract_content(pdf_path: str, config: dict) -> ExtractionResult:
    """Main extraction entry point. Text always runs; OCR and vision are independent add-ons."""
    pdf_cfg = config.get("pdf", {})
    max_pages = pdf_cfg.get("max_pages", 3)
    threshold = pdf_cfg.get("text_quality_threshold", 0.3)
    ocr_setting = pdf_cfg.get("ocr", False)
    vision_setting = pdf_cfg.get("vision", False)

    sources = []
    warnings = []

    # Step 1: Always run pdfplumber text extraction
    text, quality = extract_text(pdf_path, max_pages)
    sources.append("text")

    # Step 2: Determine if OCR / vision should run
    run_ocr = _should_run_step(ocr_setting, quality, threshold)
    run_vision = _should_run_step(vision_setting, quality, threshold)

    ocr_text = ""
    images = []

    # Step 3: Render images if needed for OCR or vision
    # Use lower scale for OCR-only (detection model resizes internally anyway)
    if run_ocr or run_vision:
        ocr_scale = 1.5 if (run_ocr and not run_vision) else 2.0
        images = render_pages_to_images(pdf_path, max_pages, scale=ocr_scale)
        if not images:
            logging.warning(f"No images rendered from {pdf_path}")
            warnings.append("Could not render page images")
            run_ocr = False
            run_vision = False

    # Step 4: PaddleOCR
    if run_ocr:
        if _paddleocr_available(config):
            try:
                ocr_text = ocr_with_paddleocr(images, config)
            except Exception as e:
                logging.warning(f"PaddleOCR failed, continuing without OCR: {e}")
                warnings.append(f"PaddleOCR failed: {e}")
                ocr_text = ""
            if ocr_text.strip():
                sources.append("ocr")
            else:
                if not warnings:  # Don't duplicate if we already logged a failure
                    logging.warning("PaddleOCR returned empty text")
                    warnings.append("PaddleOCR returned no text")
        else:
            logging.warning("PaddleOCR requested but not available")
            warnings.append("PaddleOCR not installed — run setup.ps1 to install")

    # Step 5: Vision — keep images in result
    if run_vision:
        sources.append("vision")
    else:
        images = []  # Don't pass images if vision not requested

    return ExtractionResult(
        text=text,
        ocr_text=ocr_text,
        images=images,
        quality_score=quality,
        page_count=max_pages,
        sources=sources,
        warnings=warnings,
    )
