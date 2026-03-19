"""Tests using generated fixture PDFs to validate the extraction pipeline."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _pdf_utils import extract_text, assess_text_quality, render_pages_to_images, extract_content


class TestTextInvoice:
    """Tier 1: clean text PDFs should extract well without OCR."""

    def test_english_invoice_quality(self, fixture_text_invoice, sample_config):
        text, quality = extract_text(fixture_text_invoice)
        assert quality >= 0.5
        assert "ACME" in text
        assert "3038228" in text or "INV-2024" in text
        assert "15.03.2024" in text

    def test_german_invoice_quality(self, fixture_german_invoice, sample_config):
        text, quality = extract_text(fixture_german_invoice)
        assert quality >= 0.5
        assert "Mustermann" in text
        assert "08.02.2025" in text
        assert "Rechnung" in text or "RE-2025" in text

    def test_letter_not_invoice(self, fixture_letter, sample_config):
        text, quality = extract_text(fixture_letter)
        assert quality >= 0.3
        assert "Globex" in text
        assert "22.01.2025" in text

    def test_outgoing_invoice(self, fixture_outgoing, sample_config):
        text, quality = extract_text(fixture_outgoing)
        assert quality >= 0.5
        assert "Wayne" in text
        assert "Petermeir" in text

    def test_extract_content_uses_text_source(self, fixture_text_invoice, sample_config):
        result = extract_content(fixture_text_invoice, sample_config)
        assert "text" in result.sources
        assert result.quality_score >= 0.3
        assert result.images == []
        assert len(result.text) > 0


class TestImageInvoice:
    """Tier 2: image-only PDFs should have low text quality and fall through."""

    def test_no_extractable_text(self, fixture_image_invoice, sample_config):
        text, quality = extract_text(fixture_image_invoice)
        assert quality < 0.3

    def test_renders_to_images(self, fixture_image_invoice):
        images = render_pages_to_images(fixture_image_invoice, max_pages=1)
        assert len(images) == 1
        assert images[0].size[0] > 100
        assert images[0].size[1] > 100

    def test_extract_content_with_vision_enabled(self, fixture_image_invoice, sample_config):
        sample_config["pdf"]["vision"] = True
        result = extract_content(fixture_image_invoice, sample_config)
        assert "vision" in result.sources
        assert len(result.images) > 0


class TestMixedInvoice:
    """Mixed PDFs with text + images should still extract text successfully."""

    def test_text_still_extractable(self, fixture_mixed_invoice, sample_config):
        text, quality = extract_text(fixture_mixed_invoice)
        assert quality >= 0.3
        assert "Initech" in text or "INIT-2024" in text

    def test_extract_content_uses_text(self, fixture_mixed_invoice, sample_config):
        result = extract_content(fixture_mixed_invoice, sample_config)
        assert "text" in result.sources


class TestMultipage:
    """Multi-page PDFs should respect max_pages config."""

    def test_extracts_all_three_pages(self, fixture_multipage, sample_config):
        text, _ = extract_text(fixture_multipage, max_pages=3)
        assert "Page 1:" in text
        assert "Page 2:" in text or "Page 3:" in text
        assert "Stark" in text

    def test_max_pages_limit(self, fixture_multipage, sample_config):
        text, _ = extract_text(fixture_multipage, max_pages=1)
        assert "Page 1:" in text
        assert "Page 2:" not in text

    def test_renders_limited_images(self, fixture_multipage):
        images = render_pages_to_images(fixture_multipage, max_pages=2)
        assert len(images) == 2


class TestEdgeCases:
    """Edge cases: empty, minimal text."""

    def test_empty_pdf_low_quality(self, fixture_empty, sample_config):
        text, quality = extract_text(fixture_empty)
        assert quality == 0.0

    def test_empty_extract_content(self, fixture_empty, sample_config):
        result = extract_content(fixture_empty, sample_config)
        assert result.quality_score < 0.3
        assert result.sources == ["text"]

    def test_minimal_text_low_quality(self, fixture_minimal, sample_config):
        text, quality = extract_text(fixture_minimal)
        # Minimal text should score well below a rich invoice
        good_text_quality = extract_text(fixture_minimal.replace("minimal_text", "text_invoice_acme"))[1]
        assert quality < good_text_quality
        assert "42" in text

    def test_vision_enabled_on_text_pdf(self, fixture_text_invoice, sample_config):
        """Even a good text PDF produces images when vision=True."""
        sample_config["pdf"]["vision"] = True
        result = extract_content(fixture_text_invoice, sample_config)
        assert "vision" in result.sources
        assert len(result.images) > 0
        # Text should still be present
        assert "text" in result.sources
        assert len(result.text) > 0

    def test_unicode_filename_extracts_text_and_images(self, fixture_text_invoice, tmp_path, sample_config):
        """Unicode paths should not depend on downstream library path handling."""
        unicode_pdf = tmp_path / "20260307 OTTO RÖHRS ER 75,33.pdf"
        with open(fixture_text_invoice, "rb") as source:
            unicode_pdf.write_bytes(source.read())

        text, quality = extract_text(str(unicode_pdf))
        images = render_pages_to_images(str(unicode_pdf), max_pages=1)
        result = extract_content(str(unicode_pdf), sample_config)

        assert quality >= 0.5
        assert "ACME" in text
        assert len(images) == 1
        assert result.quality_score >= 0.5
        assert "text" in result.sources
