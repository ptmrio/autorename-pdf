"""Tests for _pdf_utils.py."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _pdf_utils import extract_text, assess_text_quality, render_pages_to_images, extract_content, _should_run_step


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
            from unittest.mock import patch
            with patch("_pdf_utils._extract_text_with_pdfplumber",
                       side_effect=Exception("PDF requires a password")):
                text, quality = extract_text(pdf_path)
            assert text == ""
            assert quality == 0.0
