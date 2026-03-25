"""
Live integration tests that call real AI endpoints.

These tests are SKIPPED by default. Run them with:
    pytest tests/test_live_integration.py --run-live -v

Provider selection:
    pytest tests/ --run-live --provider ollama -v     # Free, local
    pytest tests/ --run-live --provider openai -v     # Cloud, ~$0.001/test
    pytest tests/ --run-live --provider anthropic -v  # Cloud, ~$0.001/test
    pytest tests/ --run-live -v                       # All available providers

Mode selection:
    pytest tests/ --run-live -m vision -v             # Vision tests only
    pytest tests/ --run-live -m ocr -v                # OCR tests only

API keys are loaded from .env file (see .env.example for template).
Ollama tests require Ollama running at localhost:11434.
"""

import os
import re
import sys
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _pdf_utils import extract_content
from _ai_processing import extract_metadata

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _extract(pdf_name: str, config: dict):
    """Helper: extract content from a fixture PDF and run AI metadata extraction."""
    pdf = os.path.join(FIXTURES_DIR, pdf_name)
    extraction = extract_content(pdf, config)
    assert "text" in extraction.sources
    metadata = extract_metadata(extraction, config)
    assert metadata is not None, f"AI returned None for {pdf_name}"
    provider = config["ai"]["provider"]
    model = config["ai"]["model"]
    print(f"\n  [{provider}/{model}] {pdf_name}")
    print(f"    Company: {metadata.company_name}")
    print(f"    Date:    {metadata.document_date}")
    print(f"    Type:    {metadata.document_type}")
    return metadata


def _extract_full(pdf_name: str, config: dict):
    """Helper: extract + AI metadata, returning (metadata, sources, quality_score)."""
    pdf = os.path.join(FIXTURES_DIR, pdf_name)
    extraction = extract_content(pdf, config)
    metadata = extract_metadata(extraction, config)
    assert metadata is not None, f"AI returned None for {pdf_name}"
    provider = config["ai"]["provider"]
    model = config["ai"]["model"]
    print(f"\n  [{provider}/{model}] {pdf_name}")
    print(f"    Sources: {extraction.sources} | Quality: {extraction.quality_score:.2f}")
    print(f"    Company: {metadata.company_name}")
    print(f"    Date:    {metadata.document_date}")
    print(f"    Type:    {metadata.document_type}")
    return metadata, extraction.sources, extraction.quality_score


# ---------------------------------------------------------------------------
# Per-provider extraction tests
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.openai
class TestOpenAI:
    """Live extraction with OpenAI (gpt-5-mini)."""

    def test_english_invoice(self, openai_config):
        md = _extract("text_invoice_acme.pdf", openai_config)
        assert "ACME" in md.company_name.upper()
        assert "2024" in md.document_date

    def test_german_invoice(self, openai_config):
        md = _extract("text_rechnung_mustermann.pdf", openai_config)
        assert "MUSTERMANN" in md.company_name.upper()

    def test_outgoing_invoice(self, openai_config):
        md = _extract("text_outgoing_invoice_wayne.pdf", openai_config)
        assert "WAYNE" in md.company_name.upper()
        assert md.document_type.upper() in ["AR", "AR 1"]  # may include amount

    def test_letter_not_invoice(self, openai_config):
        md = _extract("text_letter_globex.pdf", openai_config)
        assert "GLOBEX" in md.company_name.upper()
        assert md.document_type.upper() not in ["ER", "AR"]

    def test_multipage_invoice(self, openai_config):
        md = _extract("multipage_invoice_stark.pdf", openai_config)
        assert "STARK" in md.company_name.upper()


@pytest.mark.live
@pytest.mark.anthropic
class TestAnthropic:
    """Live extraction with Anthropic (claude-haiku)."""

    def test_english_invoice(self, anthropic_config):
        md = _extract("text_invoice_acme.pdf", anthropic_config)
        assert "ACME" in md.company_name.upper()
        assert "2024" in md.document_date

    def test_german_invoice(self, anthropic_config):
        md = _extract("text_rechnung_mustermann.pdf", anthropic_config)
        assert "MUSTERMANN" in md.company_name.upper()

    def test_outgoing_invoice(self, anthropic_config):
        md = _extract("text_outgoing_invoice_wayne.pdf", anthropic_config)
        assert "WAYNE" in md.company_name.upper()
        assert md.document_type.upper() in ["AR", "AR 1"]

    def test_letter_not_invoice(self, anthropic_config):
        md = _extract("text_letter_globex.pdf", anthropic_config)
        assert "GLOBEX" in md.company_name.upper()
        assert md.document_type.upper() not in ["ER", "AR"]

    def test_multipage_invoice(self, anthropic_config):
        md = _extract("multipage_invoice_stark.pdf", anthropic_config)
        assert "STARK" in md.company_name.upper()


@pytest.mark.live
@pytest.mark.ollama
class TestOllama:
    """Live extraction with Ollama (local model).

    Small local models (qwen3:4b) are less accurate than cloud models.
    These tests validate the pipeline works (structured output returned,
    fields populated) without asserting specific content accuracy.
    """

    def test_english_invoice(self, ollama_config):
        md = _extract("text_invoice_acme.pdf", ollama_config)
        assert md.company_name.strip(), "company_name should not be empty"
        assert md.document_date.strip(), "document_date should not be empty"
        assert md.document_type.strip(), "document_type should not be empty"

    def test_german_invoice(self, ollama_config):
        md = _extract("text_rechnung_mustermann.pdf", ollama_config)
        assert md.company_name.strip()
        assert md.document_date.strip()

    def test_outgoing_invoice(self, ollama_config):
        md = _extract("text_outgoing_invoice_wayne.pdf", ollama_config)
        assert md.company_name.strip()
        assert md.document_type.strip()

    def test_letter_not_invoice(self, ollama_config):
        md = _extract("text_letter_globex.pdf", ollama_config)
        assert md.company_name.strip()
        assert md.document_type.strip()


# ---------------------------------------------------------------------------
# Full rename round-trip (uses whatever provider is available)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveFullRename:
    """End-to-end rename with real AI, then undo."""

    @pytest.mark.openai
    def test_rename_and_undo_openai(self, openai_config, tmp_path):
        self._rename_and_undo(openai_config, tmp_path)

    @pytest.mark.anthropic
    def test_rename_and_undo_anthropic(self, anthropic_config, tmp_path):
        self._rename_and_undo(anthropic_config, tmp_path)

    @pytest.mark.ollama
    def test_rename_and_undo_ollama(self, ollama_config, tmp_path):
        self._rename_and_undo(ollama_config, tmp_path)

    def _rename_and_undo(self, config, tmp_path):
        from autorename_pdf_runner import process_pdf
        from _document_processing import undo_renames

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "invoice_to_rename.pdf")
        shutil.copy2(src, pdf_copy)

        undo_log = str(tmp_path / ".autorename-log.json")
        result = process_pdf(pdf_copy, config, str(tmp_path / "names.yaml"),
                             undo_log, dry_run=False, batch_id="test-batch-001")

        provider = config["ai"]["provider"]
        print(f"\n  [{provider}] status={result.status} new_name={result.new_name}")
        assert result.status == "renamed", f"Expected renamed, got {result.status}: {result.error}"
        assert not os.path.exists(pdf_copy), "Original file should be gone"
        assert result.new_name is not None
        assert result.new_name.endswith(".pdf")
        # Verify date was extracted (should contain 2024 from the ACME invoice)
        assert "2024" in result.new_name or result.company is not None

        # Undo
        restored, failed, _ = undo_renames(undo_log, undo_all=True)
        assert restored >= 1
        assert failed == 0
        assert os.path.exists(pdf_copy), "Original file should be restored"


# ---------------------------------------------------------------------------
# README Scenario 2: Cloud AI + Vision (ocr=false, vision=true)
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.vision
class TestVisionExtraction:
    """Vision-enabled extraction: send page images to LLM."""

    @pytest.mark.openai
    def test_image_pdf_openai(self, openai_vision_config):
        """Image-only PDF extracted via vision with OpenAI."""
        md, sources, quality = _extract_full("image_invoice_springfield.pdf", openai_vision_config)
        assert "vision" in sources
        assert quality < 0.3, "Image-only PDF should have low text quality"
        assert md.company_name.strip(), "company_name should not be empty"
        assert md.document_date.strip(), "document_date should not be empty"

    @pytest.mark.anthropic
    def test_image_pdf_anthropic(self, anthropic_vision_config):
        """Image-only PDF extracted via vision with Anthropic."""
        md, sources, quality = _extract_full("image_invoice_springfield.pdf", anthropic_vision_config)
        assert "vision" in sources
        assert quality < 0.3
        assert md.company_name.strip()
        assert md.document_date.strip()

    @pytest.mark.openai
    def test_mixed_pdf_openai(self, openai_vision_config):
        """Mixed PDF (text + logo image) with vision enabled."""
        md, sources, _ = _extract_full("mixed_invoice_initech.pdf", openai_vision_config)
        assert "text" in sources
        assert "vision" in sources
        assert "INITECH" in md.company_name.upper()

    @pytest.mark.openai
    def test_text_pdf_with_vision_openai(self, openai_vision_config):
        """Good text PDF with vision — vision supplements, doesn't break."""
        md, sources, _ = _extract_full("text_invoice_acme.pdf", openai_vision_config)
        assert "text" in sources
        assert "vision" in sources
        assert "ACME" in md.company_name.upper()


# ---------------------------------------------------------------------------
# README Scenario 1: Cloud AI + PaddleOCR (ocr=true, vision=false)
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.ocr
class TestOCRExtraction:
    """OCR-enabled extraction: PaddleOCR enhances scanned PDFs."""

    @pytest.mark.openai
    def test_image_pdf_ocr_openai(self, openai_ocr_config):
        """Image-only PDF with OCR providing text to OpenAI."""
        md, sources, _ = _extract_full("image_invoice_springfield.pdf", openai_ocr_config)
        assert "ocr" in sources
        assert md.company_name.strip(), "OCR + AI should extract a company name"
        assert md.document_date.strip()

    @pytest.mark.anthropic
    def test_image_pdf_ocr_anthropic(self, anthropic_ocr_config):
        """Image-only PDF with OCR providing text to Anthropic."""
        md, sources, _ = _extract_full("image_invoice_springfield.pdf", anthropic_ocr_config)
        assert "ocr" in sources
        assert md.company_name.strip()

    @pytest.mark.openai
    def test_text_pdf_with_ocr(self, openai_ocr_config):
        """Good text PDF with OCR — OCR supplements, doesn't break."""
        md, sources, _ = _extract_full("text_invoice_acme.pdf", openai_ocr_config)
        assert "ocr" in sources
        assert "ACME" in md.company_name.upper()


# ---------------------------------------------------------------------------
# README Scenario 3: Max Privacy — Ollama + PaddleOCR (fully local)
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.ollama
@pytest.mark.ocr
class TestOllamaLocal:
    """Fully local pipeline: Ollama + PaddleOCR, no cloud, no API keys."""

    def test_text_invoice(self, ollama_ocr_config):
        """Text invoice through fully local pipeline."""
        md, sources, _ = _extract_full("text_invoice_acme.pdf", ollama_ocr_config)
        assert "ocr" in sources
        assert md.company_name.strip()
        assert md.document_date.strip()
        assert md.document_type.strip()

    def test_image_invoice_with_ocr(self, ollama_ocr_config):
        """Image-only invoice — OCR provides text, Ollama extracts metadata."""
        md, sources, quality = _extract_full("image_invoice_springfield.pdf", ollama_ocr_config)
        assert "ocr" in sources
        assert quality < 0.3, "Image-only PDF should have low text quality"
        assert md.company_name.strip()
        assert md.document_type.strip()


# ---------------------------------------------------------------------------
# Both OCR + Vision together (--ocr --vision)
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.ocr
@pytest.mark.vision
class TestCombinedOCRVision:
    """Maximum accuracy: both OCR and vision enabled simultaneously."""

    @pytest.mark.openai
    def test_image_pdf_both_openai(self, openai_combined_config):
        """Image-only PDF with all three extraction sources."""
        md, sources, _ = _extract_full("image_invoice_springfield.pdf", openai_combined_config)
        assert "ocr" in sources, "OCR should have run"
        assert "vision" in sources, "Vision should have run"
        assert md.company_name.strip()

    @pytest.mark.openai
    def test_mixed_pdf_both_openai(self, openai_combined_config):
        """Mixed PDF with OCR + vision — all sources combined."""
        md, sources, _ = _extract_full("mixed_invoice_initech.pdf", openai_combined_config)
        assert "text" in sources
        assert "vision" in sources
        assert "INITECH" in md.company_name.upper()


# ---------------------------------------------------------------------------
# Auto mode (ocr: "auto", vision: "auto") with quality threshold
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.openai
class TestAutoMode:
    """Auto mode: OCR/vision trigger only when text quality is below threshold."""

    def test_auto_skips_on_good_text(self, openai_auto_config):
        """Good text PDF — auto should NOT trigger OCR/vision."""
        md, sources, quality = _extract_full("text_invoice_acme.pdf", openai_auto_config)
        assert quality > 0.3, "Good text PDF should score above threshold"
        assert sources == ["text"], f"Auto should skip OCR/vision, got sources={sources}"
        assert "ACME" in md.company_name.upper()

    def test_auto_triggers_on_image_pdf(self, openai_auto_config):
        """Image-only PDF — auto SHOULD trigger vision (quality below threshold)."""
        md, sources, quality = _extract_full("image_invoice_springfield.pdf", openai_auto_config)
        assert quality < 0.3, "Image-only PDF should score below threshold"
        assert "vision" in sources, "Auto should trigger vision for low-quality text"
        assert md.company_name.strip()

    def test_auto_triggers_on_minimal_text(self, openai_auto_config):
        """Minimal text PDF — auto behavior depends on text quality score.

        minimal_text.pdf may score above or below the 0.3 threshold depending
        on content. We verify auto mode's decision is consistent with quality.
        """
        md, sources, quality = _extract_full("minimal_text.pdf", openai_auto_config)
        if quality < 0.3:
            assert len(sources) > 1, f"Auto should trigger fallback for quality {quality}"
        else:
            assert sources == ["text"], f"Auto should skip for quality {quality}"


# ---------------------------------------------------------------------------
# P1: Prompt extension — invoice totals
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.openai
class TestPromptExtension:
    """Prompt extension: AI adds invoice totals to document_type."""

    def test_invoice_total_extracted(self, openai_prompt_ext_config):
        """Invoice doc_type should include a monetary amount."""
        md = _extract("text_invoice_acme.pdf", openai_prompt_ext_config)
        assert re.search(r'\d', md.document_type), \
            f"Expected digits in doc_type with prompt_extension, got: {md.document_type}"

    def test_outgoing_ar_with_amount(self, openai_prompt_ext_config):
        """Outgoing invoice should have invoice code + amount."""
        md = _extract("text_outgoing_invoice_wayne.pdf", openai_prompt_ext_config)
        # AI may classify as AR (outgoing) or ER (incoming) depending on perspective
        assert re.search(r'[EA]R', md.document_type.upper()), \
            f"Expected ER or AR in doc_type, got: {md.document_type}"
        assert re.search(r'\d', md.document_type), \
            f"Expected digits in doc_type with prompt_extension, got: {md.document_type}"

    def test_letter_no_amount(self, openai_prompt_ext_config):
        """Non-invoice should NOT get ER/AR classification."""
        md = _extract("text_letter_globex.pdf", openai_prompt_ext_config)
        assert md.document_type.upper() not in ["ER", "AR"]


# ---------------------------------------------------------------------------
# P1: Company name harmonization through live pipeline
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.openai
class TestLiveHarmonization:
    """Company harmonization via process_pdf with real AI + harmonized names YAML."""

    def test_harmonizes_acme(self, openai_config, live_harmonized_names, tmp_path):
        """AI extracts 'ACME Corporation GmbH', harmonized to 'ACME'."""
        from autorename_pdf_runner import process_pdf

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "acme_invoice.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, openai_config, live_harmonized_names,
                             str(tmp_path / ".autorename-log.json"),
                             dry_run=True, batch_id="test-harmonize")

        print(f"\n  Harmonization: raw company → {result.company}")
        assert result.status == "renamed"
        assert result.company == "ACME", \
            f"Expected 'ACME' after harmonization, got: {result.company}"

    def test_harmonizes_mustermann(self, openai_config, live_harmonized_names, tmp_path):
        """AI extracts Mustermann variant, harmonized to 'Mustermann'."""
        from autorename_pdf_runner import process_pdf

        src = os.path.join(FIXTURES_DIR, "text_rechnung_mustermann.pdf")
        pdf_copy = str(tmp_path / "mustermann_rechnung.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, openai_config, live_harmonized_names,
                             str(tmp_path / ".autorename-log.json"),
                             dry_run=True, batch_id="test-harmonize")

        print(f"\n  Harmonization: raw company → {result.company}")
        assert result.status == "renamed"
        assert result.company == "Mustermann", \
            f"Expected 'Mustermann' after harmonization, got: {result.company}"
