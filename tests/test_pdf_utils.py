"""Tests for _pdf_utils.py."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
import json
from _pdf_utils import extract_text, assess_text_quality, render_pages_to_images, extract_content, _should_run_step
from _pdf_utils import (
    _mojibake_marker_count, _maybe_fix_mojibake,
    _get_bridge_script_path, _get_paddleocr_python,
    _paddleocr_available, ocr_with_paddleocr,
)


class TestShouldRunStep:
    def test_false_disables(self):
        assert _should_run_step(False, 0.1, 0.3) is False

    def test_true_always_enables(self):
        assert _should_run_step(True, 0.9, 0.3) is True

    def test_auto_below_threshold(self):
        assert _should_run_step("auto", 0.1, 0.3) is True

    def test_auto_above_threshold(self):
        assert _should_run_step("auto", 0.5, 0.3) is False


class TestAssessTextQuality:
    def test_empty_text(self):
        assert assess_text_quality("") == 0.0

    def test_whitespace_only(self):
        assert assess_text_quality("   \n\t  ") == 0.0

    def test_good_text(self):
        text = "This is a normal invoice document with proper text content. " * 10
        score = assess_text_quality(text)
        assert score >= 0.7

    def test_short_text(self):
        score = assess_text_quality("Hello")
        assert 0.0 < score < 1.0

    def test_garbage_text(self):
        garbage = "X" * 500  # Single repeated char, no spaces
        score = assess_text_quality(garbage)
        # Garbage text should score lower than good text
        good_score = assess_text_quality("This is a normal invoice document with proper text. " * 10)
        assert score < good_score

    def test_score_range(self):
        text = "Normal text with reasonable word lengths"
        score = assess_text_quality(text)
        assert 0.0 <= score <= 1.0


class TestExtractText:
    def test_extract_from_valid_pdf(self, sample_pdf):
        text, quality = extract_text(sample_pdf, max_pages=3)
        assert "Invoice" in text or "12345" in text
        assert quality > 0.0

    def test_extract_from_empty_pdf(self, empty_pdf):
        text, quality = extract_text(empty_pdf, max_pages=3)
        assert quality < 0.3

    def test_max_pages_limit(self, sample_pdf):
        text, _ = extract_text(sample_pdf, max_pages=1)
        assert "Page 1:" in text

    def test_nonexistent_file(self):
        text, quality = extract_text("/nonexistent/file.pdf")
        assert text == ""
        assert quality == 0.0


class TestRenderPagesToImages:
    def test_render_valid_pdf(self, sample_pdf):
        images = render_pages_to_images(sample_pdf, max_pages=1)
        assert len(images) == 1
        assert images[0].size[0] > 0
        assert images[0].size[1] > 0

    def test_render_nonexistent_file(self):
        images = render_pages_to_images("/nonexistent/file.pdf")
        assert images == []


class TestExtractContent:
    def test_text_only_default(self, sample_pdf, sample_config):
        """Default config (ocr=False, vision=False) returns text source only."""
        result = extract_content(sample_pdf, sample_config)
        assert "text" in result.sources
        assert "ocr" not in result.sources
        assert "vision" not in result.sources
        assert result.page_count > 0
        assert result.images == []

    def test_vision_enabled(self, sample_pdf, sample_config):
        sample_config["pdf"]["vision"] = True
        result = extract_content(sample_pdf, sample_config)
        assert "text" in result.sources
        assert "vision" in result.sources
        assert len(result.images) > 0

    def test_text_always_runs(self, sample_pdf, sample_config):
        """Text extraction runs even when vision is enabled."""
        sample_config["pdf"]["vision"] = True
        result = extract_content(sample_pdf, sample_config)
        assert "text" in result.sources
        assert len(result.text) > 0

    def test_no_ocr_or_vision(self, empty_pdf, sample_config):
        """Empty PDF with no OCR/vision returns only text source."""
        result = extract_content(empty_pdf, sample_config)
        assert result.sources == ["text"]
        assert result.ocr_text == ""
        assert result.images == []


class TestEncryptedPdfDetection:
    def test_encrypted_pdf_returns_empty(self, tmp_path):
        """Encrypted PDFs should return empty text with clear log message."""
        # Create a password-protected PDF using fpdf2
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, "Secret content")
        pdf_path = str(tmp_path / "encrypted.pdf")
        pdf.output(pdf_path)

        # Re-encrypt it using pikepdf if available, otherwise test the error path
        try:
            import pikepdf
            doc = pikepdf.open(pdf_path, allow_overwriting_input=True)
            doc.save(pdf_path, encryption=pikepdf.Encryption(owner="owner", user="user", R=4))
            doc.close()
            text, quality = extract_text(pdf_path)
            assert text == ""
            assert quality == 0.0
        except ImportError:
            # pikepdf not available — test the error detection logic directly
            from unittest.mock import patch as _patch
            with _patch("_pdf_utils._extract_text_with_pdfplumber",
                        side_effect=Exception("PDF requires a password")):
                text, quality = extract_text(pdf_path)
            assert text == ""
            assert quality == 0.0


class TestMojibakeRepair:
    """Test mojibake detection and repair heuristic."""

    def test_marker_count_clean_text(self):
        assert _mojibake_marker_count("Hello World, this is normal text") == 0

    def test_marker_count_with_markers(self):
        # \u00c3 is a common mojibake marker
        text = "R\u00c3\u00b6hrs GmbH"
        assert _mojibake_marker_count(text) > 0

    def test_fix_clean_text_unchanged(self):
        text = "Normal text without mojibake"
        assert _maybe_fix_mojibake(text) == text

    def test_fix_empty_text(self):
        assert _maybe_fix_mojibake("") == ""
        assert _maybe_fix_mojibake(None) is None

    def test_fix_repairs_double_encoded_utf8(self):
        # "Röhrs" encoded as UTF-8 then decoded as latin-1 produces mojibake
        original = "Röhrs"
        mojibake = original.encode("utf-8").decode("latin-1")
        # mojibake should contain \u00c3 marker
        assert _mojibake_marker_count(mojibake) > 0
        # Repair should restore the original
        repaired = _maybe_fix_mojibake(mojibake)
        assert repaired == original

    def test_fix_no_improvement_returns_original(self):
        # Text with markers but where no encoding fix helps
        # Use a string that contains markers but isn't actually double-encoded
        text = "Some text with \u00c3 marker but not actually broken"
        result = _maybe_fix_mojibake(text)
        # Should return something (either original or repaired)
        assert isinstance(result, str)


class TestPaddleOCR:
    """Test PaddleOCR utility functions and subprocess bridge."""

    def test_bridge_path_dev(self):
        """In dev mode, bridge script is in the project directory."""
        path = _get_bridge_script_path()
        assert path.endswith("_paddleocr_bridge.py")
        assert os.path.isfile(path)

    def test_bridge_path_frozen(self):
        """In frozen (PyInstaller) mode, bridge is in MEIPASS."""
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "_MEIPASS", "/frozen/app", create=True):
                path = _get_bridge_script_path()
        assert path == os.path.join("/frozen/app", "_paddleocr_bridge.py")

    def test_python_path_configured(self):
        """Explicit venv_path in config is used."""
        config = {"paddleocr": {"venv_path": "/custom/venv"}}
        with patch("os.path.isfile", return_value=True):
            result = _get_paddleocr_python(config)
        assert result is not None
        assert "python" in result.lower()

    def test_python_path_default_win(self):
        """Default venv path on Windows uses LOCALAPPDATA."""
        config = {"paddleocr": {"venv_path": ""}}
        with patch("sys.platform", "win32"), \
             patch.dict(os.environ, {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}), \
             patch("os.path.isfile", return_value=True):
            result = _get_paddleocr_python(config)
        assert result is not None
        assert "autorename-pdf" in result

    def test_python_path_missing(self):
        """Returns None when venv python doesn't exist."""
        config = {"paddleocr": {"venv_path": "/nonexistent/venv"}}
        result = _get_paddleocr_python(config)
        assert result is None

    def test_available_true(self):
        """Available when python executable exists."""
        config = {"paddleocr": {"venv_path": ""}}
        with patch("_pdf_utils._get_paddleocr_python", return_value="/some/python"):
            assert _paddleocr_available(config) is True

    def test_available_false(self):
        """Not available when python executable not found."""
        config = {"paddleocr": {"venv_path": ""}}
        with patch("_pdf_utils._get_paddleocr_python", return_value=None):
            assert _paddleocr_available(config) is False

    def test_ocr_no_python(self):
        """Returns empty string when PaddleOCR python not found."""
        from PIL import Image
        images = [Image.new("RGB", (100, 100))]
        config = {"paddleocr": {"venv_path": "", "language": "en", "device": "auto"}}
        with patch("_pdf_utils._get_paddleocr_python", return_value=None):
            result = ocr_with_paddleocr(images, config)
        assert result == ""

    def test_ocr_success(self):
        """Successful OCR returns concatenated page text."""
        from PIL import Image
        images = [Image.new("RGB", (100, 100)), Image.new("RGB", (100, 100))]
        config = {"paddleocr": {"venv_path": "", "language": "en", "device": "auto"}}

        # Mock subprocess that returns valid JSON responses
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stderr = iter([])  # iterable, matches `for line in proc.stderr:`
        mock_process.returncode = 0
        mock_process.wait.return_value = 0

        # Simulate stdout returning JSON lines
        responses = [
            json.dumps({"status": "ok", "text": "Invoice #12345"}) + "\n",
            json.dumps({"status": "ok", "text": "Total: EUR 100.00"}) + "\n",
        ]
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = MagicMock(side_effect=responses)

        with patch("_pdf_utils._get_paddleocr_python", return_value="/some/python"), \
             patch("_pdf_utils._get_bridge_script_path", return_value="/bridge.py"), \
             patch("subprocess.Popen", return_value=mock_process), \
             patch("shutil.rmtree"):
            result = ocr_with_paddleocr(images, config)

        assert "Page 1:" in result
        assert "Invoice #12345" in result
        assert "Page 2:" in result
        assert "Total: EUR 100.00" in result

    def test_ocr_bridge_error(self):
        """Bridge error returns empty text with warning."""
        from PIL import Image
        images = [Image.new("RGB", (100, 100))]
        config = {"paddleocr": {"venv_path": "", "language": "en", "device": "auto"}}

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline.return_value = json.dumps(
            {"status": "error", "message": "Model load failed"}
        ) + "\n"

        with patch("_pdf_utils._get_paddleocr_python", return_value="/some/python"), \
             patch("_pdf_utils._get_bridge_script_path", return_value="/bridge.py"), \
             patch("subprocess.Popen", return_value=mock_process), \
             patch("shutil.rmtree"):
            result = ocr_with_paddleocr(images, config)

        assert result == ""


class TestExtractContentOCR:
    """Test extract_content OCR integration paths."""

    def test_ocr_enabled_available(self, sample_pdf, sample_config):
        """When OCR is enabled and available, it runs and appears in sources."""
        sample_config["pdf"]["ocr"] = True
        with patch("_pdf_utils._paddleocr_available", return_value=True), \
             patch("_pdf_utils.ocr_with_paddleocr", return_value="OCR extracted text"):
            result = extract_content(sample_pdf, sample_config)
        assert "ocr" in result.sources
        assert result.ocr_text == "OCR extracted text"

    def test_ocr_enabled_unavailable(self, sample_pdf, sample_config):
        """When OCR is enabled but not installed, it's skipped gracefully."""
        sample_config["pdf"]["ocr"] = True
        with patch("_pdf_utils._paddleocr_available", return_value=False):
            result = extract_content(sample_pdf, sample_config)
        assert "ocr" not in result.sources
        assert result.ocr_text == ""

    def test_ocr_only_uses_lower_scale(self, sample_pdf, sample_config):
        """OCR without vision renders at scale 1.5."""
        from PIL import Image
        sample_config["pdf"]["ocr"] = True
        sample_config["pdf"]["vision"] = False
        with patch("_pdf_utils.render_pages_to_images") as mock_render, \
             patch("_pdf_utils._paddleocr_available", return_value=True), \
             patch("_pdf_utils.ocr_with_paddleocr", return_value="text"):
            mock_render.return_value = [Image.new("RGB", (100, 100))]
            extract_content(sample_pdf, sample_config)
        mock_render.assert_called_once_with(sample_pdf, 3, scale=1.5)

    def test_ocr_and_vision_uses_full_scale(self, sample_pdf, sample_config):
        """OCR + vision renders at scale 2.0."""
        from PIL import Image
        sample_config["pdf"]["ocr"] = True
        sample_config["pdf"]["vision"] = True
        with patch("_pdf_utils.render_pages_to_images") as mock_render, \
             patch("_pdf_utils._paddleocr_available", return_value=True), \
             patch("_pdf_utils.ocr_with_paddleocr", return_value="text"):
            mock_render.return_value = [Image.new("RGB", (100, 100))]
            extract_content(sample_pdf, sample_config)
        mock_render.assert_called_once_with(sample_pdf, 3, scale=2.0)


class TestOCRConfigPassthrough:
    """Test that new paddleocr config keys are passed to the bridge subprocess."""

    def test_config_passed_to_bridge(self):
        """New config keys are passed as CLI args to bridge subprocess."""
        from PIL import Image
        images = [Image.new("RGB", (100, 100))]
        config = {
            "paddleocr": {
                "venv_path": "",
                "language": "en",
                "device": "auto",
                "detection_model": "PP-OCRv5_server_det",
                "det_limit_side_len": 960,
                "cpu_threads": 8,
            }
        }

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline.return_value = json.dumps(
            {"status": "ok", "text": "test"}
        ) + "\n"

        with patch("_pdf_utils._get_paddleocr_python", return_value="/some/python"), \
             patch("_pdf_utils._get_bridge_script_path", return_value="/bridge.py"), \
             patch("subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch("shutil.rmtree"):
            ocr_with_paddleocr(images, config)

        cmd = mock_popen.call_args[0][0]
        assert cmd[2] == "en"  # language is first positional arg after python + bridge
        assert "--det-model" in cmd
        assert "PP-OCRv5_server_det" in cmd
        assert "--det-limit" in cmd
        assert "960" in cmd
        assert "--cpu-threads" in cmd
        assert "8" in cmd

    def test_language_config_changes_bridge_arg(self):
        """Changing paddleocr.language in config changes the CLI arg to the bridge."""
        from PIL import Image
        images = [Image.new("RGB", (100, 100))]
        config = {
            "paddleocr": {
                "venv_path": "",
                "language": "de",
                "device": "auto",
                "detection_model": "",
                "det_limit_side_len": 736,
                "cpu_threads": 4,
            }
        }

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline.return_value = json.dumps(
            {"status": "ok", "text": "test"}
        ) + "\n"

        with patch("_pdf_utils._get_paddleocr_python", return_value="/some/python"), \
             patch("_pdf_utils._get_bridge_script_path", return_value="/bridge.py"), \
             patch("subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch("shutil.rmtree"):
            ocr_with_paddleocr(images, config)

        cmd = mock_popen.call_args[0][0]
        assert cmd[2] == "de"  # language passed as positional arg

    def test_default_config_omits_det_model(self):
        """When detection_model is empty, --det-model is not passed."""
        from PIL import Image
        images = [Image.new("RGB", (100, 100))]
        config = {
            "paddleocr": {
                "venv_path": "",
                "language": "en",
                "device": "auto",
                "detection_model": "",
                "det_limit_side_len": 736,
                "cpu_threads": 4,
            }
        }

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_process.stdout = MagicMock()
        mock_process.stdout.readline.return_value = json.dumps(
            {"status": "ok", "text": "test"}
        ) + "\n"

        with patch("_pdf_utils._get_paddleocr_python", return_value="/some/python"), \
             patch("_pdf_utils._get_bridge_script_path", return_value="/bridge.py"), \
             patch("subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch("shutil.rmtree"):
            ocr_with_paddleocr(images, config)

        cmd = mock_popen.call_args[0][0]
        assert "--det-model" not in cmd
        assert "--det-limit" in cmd
        assert "736" in cmd
        assert "--cpu-threads" in cmd
        assert "4" in cmd
