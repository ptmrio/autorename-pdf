"""
Live integration tests that call real AI endpoints.

These tests are SKIPPED by default. Run them explicitly with:
    pytest tests/test_live_integration.py -v --run-live

They require a valid config.yaml (or config.test.yaml) with a real API key.
"""

import os
import sys
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _config_loader import load_yaml_config
from _pdf_utils import extract_content
from _ai_processing import extract_metadata

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_test_config():
    """Load config.test.yaml if it exists, otherwise config.yaml."""
    test_config = os.path.join(PROJECT_DIR, "config.test.yaml")
    prod_config = os.path.join(PROJECT_DIR, "config.yaml")

    path = test_config if os.path.exists(test_config) else prod_config
    config = load_yaml_config(path)
    if not config:
        pytest.skip(f"No config found at {test_config} or {prod_config}")
    return config


@pytest.fixture
def live_config():
    return _load_test_config()


@pytest.mark.live
class TestLiveTextExtraction:
    """Test full pipeline with real AI: text extraction + LLM."""

    def test_english_invoice(self, live_config, tmp_path):
        pdf = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        extraction = extract_content(pdf, live_config)
        assert extraction.method == "text"

        metadata = extract_metadata(extraction, live_config)
        assert metadata is not None
        print(f"\n  Company: {metadata.company_name}")
        print(f"  Date:    {metadata.document_date}")
        print(f"  Type:    {metadata.document_type}")

        assert "ACME" in metadata.company_name.upper()
        assert "2024" in metadata.document_date
        assert metadata.document_type in ["ER", "er"]

    def test_german_invoice(self, live_config, tmp_path):
        pdf = os.path.join(FIXTURES_DIR, "text_rechnung_mustermann.pdf")
        extraction = extract_content(pdf, live_config)
        metadata = extract_metadata(extraction, live_config)

        assert metadata is not None
        print(f"\n  Company: {metadata.company_name}")
        print(f"  Date:    {metadata.document_date}")
        print(f"  Type:    {metadata.document_type}")

        assert "Mustermann" in metadata.company_name
        assert "2025" in metadata.document_date

    def test_outgoing_invoice_classified_as_ar(self, live_config, tmp_path):
        pdf = os.path.join(FIXTURES_DIR, "text_outgoing_invoice_wayne.pdf")
        live_config["company"]["name"] = "Petermeir Digital Solutions"

        extraction = extract_content(pdf, live_config)
        metadata = extract_metadata(extraction, live_config)

        assert metadata is not None
        print(f"\n  Company: {metadata.company_name}")
        print(f"  Date:    {metadata.document_date}")
        print(f"  Type:    {metadata.document_type}")

        assert "Wayne" in metadata.company_name
        assert metadata.document_type in ["AR", "ar"]

    def test_letter_not_classified_as_invoice(self, live_config, tmp_path):
        pdf = os.path.join(FIXTURES_DIR, "text_letter_globex.pdf")
        extraction = extract_content(pdf, live_config)
        metadata = extract_metadata(extraction, live_config)

        assert metadata is not None
        print(f"\n  Company: {metadata.company_name}")
        print(f"  Date:    {metadata.document_date}")
        print(f"  Type:    {metadata.document_type}")

        assert "Globex" in metadata.company_name
        assert metadata.document_type not in ["ER", "AR", "er", "ar"]

    def test_multipage_invoice(self, live_config, tmp_path):
        pdf = os.path.join(FIXTURES_DIR, "multipage_invoice_stark.pdf")
        extraction = extract_content(pdf, live_config)
        metadata = extract_metadata(extraction, live_config)

        assert metadata is not None
        print(f"\n  Company: {metadata.company_name}")
        print(f"  Date:    {metadata.document_date}")
        print(f"  Type:    {metadata.document_type}")

        assert "Stark" in metadata.company_name


@pytest.mark.live
class TestLiveFullRename:
    """Test actual rename with real AI output."""

    def test_rename_real_invoice(self, live_config, tmp_path):
        from autorename_pdf_runner import process_pdf

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "invoice_to_rename.pdf")
        shutil.copy2(src, pdf_copy)

        status = process_pdf(pdf_copy, live_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=False)

        assert status == "renamed"
        assert not os.path.exists(pdf_copy)

        # Check that the renamed file exists and has a sensible name
        renamed_files = [f for f in os.listdir(tmp_path) if f.endswith(".pdf")]
        assert len(renamed_files) == 1
        name = renamed_files[0]
        print(f"\n  Renamed to: {name}")
        assert "ACME" in name.upper() or "Acme" in name
        assert "2024" in name
