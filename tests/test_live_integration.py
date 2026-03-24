"""
Live integration tests that call real AI endpoints.

These tests are SKIPPED by default. Run them with:
    pytest tests/test_live_integration.py --run-live -v

Provider selection:
    pytest tests/ --run-live --provider ollama -v     # Free, local
    pytest tests/ --run-live --provider openai -v     # Cloud, ~$0.001/test
    pytest tests/ --run-live --provider anthropic -v  # Cloud, ~$0.001/test
    pytest tests/ --run-live -v                       # All available providers

API keys are loaded from .env file (see .env.example for template).
Ollama tests require Ollama running at localhost:11434.
"""

import os
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
