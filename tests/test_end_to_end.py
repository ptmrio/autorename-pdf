"""End-to-end tests for the full rename pipeline (with mocked AI)."""

import os
import sys
import shutil
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _ai_processing import DocumentMetadata
from autorename_pdf_runner import process_pdf, collect_pdf_files

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _mock_metadata(company, date, doc_type):
    """Create a mock that replaces extract_metadata to return fixed values."""
    return DocumentMetadata(
        company_name=company,
        document_date=date,
        document_type=doc_type,
    )


class TestFullPipelineDryRun:
    """Test the full pipeline in dry-run mode (no files renamed)."""

    @patch("autorename_pdf.extract_metadata")
    def test_text_invoice_dry_run(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("ACME", "15.03.2024", "ER")

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "text_invoice_acme.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=True)

        assert result.status == "renamed"
        # Original file should still exist (dry run)
        assert os.path.exists(pdf_copy)
        # No new file should be created
        assert not os.path.exists(str(tmp_path / "20240315 ACME ER.pdf"))

    @patch("autorename_pdf.extract_metadata")
    def test_german_invoice_dry_run(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("Mustermann Consulting", "08.02.2025", "ER")

        src = os.path.join(FIXTURES_DIR, "text_rechnung_mustermann.pdf")
        pdf_copy = str(tmp_path / "rechnung.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=True)
        assert result.status == "renamed"
        assert os.path.exists(pdf_copy)

    @patch("autorename_pdf.extract_metadata")
    def test_outgoing_invoice_ar(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("Wayne Enterprises", "10.03.2025", "AR")

        src = os.path.join(FIXTURES_DIR, "text_outgoing_invoice_wayne.pdf")
        pdf_copy = str(tmp_path / "outgoing.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=True)
        assert result.status == "renamed"

    @patch("autorename_pdf.extract_metadata")
    def test_letter_non_invoice(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("Globex", "22.01.2025", "Partnership Agreement")

        src = os.path.join(FIXTURES_DIR, "text_letter_globex.pdf")
        pdf_copy = str(tmp_path / "letter.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=True)
        assert result.status == "renamed"


class TestFullPipelineRealRename:
    """Test actual file renaming (not dry run)."""

    @patch("autorename_pdf.extract_metadata")
    def test_rename_produces_correct_filename(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("ACME", "15.03.2024", "ER")

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "original.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=False)

        assert result.status == "renamed"
        assert not os.path.exists(pdf_copy)
        expected = str(tmp_path / "20240315 ACME ER.pdf")
        assert os.path.exists(expected)

    @patch("autorename_pdf.extract_metadata")
    def test_rename_with_harmonization(self, mock_ai, tmp_path, sample_config, harmonized_names_file):
        mock_ai.return_value = _mock_metadata("ACME Corporation", "15.03.2024", "ER")

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "invoice.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, sample_config, harmonized_names_file,
                             str(tmp_path / ".autorename-log.json"), dry_run=False)

        assert result.status == "renamed"
        expected = str(tmp_path / "20240315 ACME ER.pdf")
        assert os.path.exists(expected)

    @patch("autorename_pdf.extract_metadata")
    def test_undo_log_written(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("ACME", "15.03.2024", "ER")

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "original.pdf")
        shutil.copy2(src, pdf_copy)
        log_path = str(tmp_path / ".autorename-log.json")

        process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                    log_path, dry_run=False)

        import json
        assert os.path.exists(log_path)
        with open(log_path) as f:
            data = json.load(f)
        assert data["version"] == 2
        assert len(data["batches"]) >= 1
        files = data["batches"][-1]["files"]
        assert len(files) == 1
        assert files[0]["old_path"] == pdf_copy
        assert "20240315 ACME ER.pdf" in files[0]["new_path"]

    @patch("autorename_pdf.extract_metadata")
    def test_undo_restores_original(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("ACME", "15.03.2024", "ER")

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "original.pdf")
        shutil.copy2(src, pdf_copy)
        log_path = str(tmp_path / ".autorename-log.json")

        process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                    log_path, dry_run=False)

        from _document_processing import undo_renames
        success, fail, _results = undo_renames(log_path)
        assert success == 1
        assert fail == 0
        assert os.path.exists(pdf_copy)

    @patch("autorename_pdf.extract_metadata")
    def test_custom_date_format(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("ACME", "15.03.2024", "ER")
        sample_config["output"]["date_format"] = "%Y-%m-%d"

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "invoice.pdf")
        shutil.copy2(src, pdf_copy)

        process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                    str(tmp_path / ".autorename-log.json"), dry_run=False)

        expected = str(tmp_path / "2024-03-15 ACME ER.pdf")
        assert os.path.exists(expected)

    @patch("autorename_pdf.extract_metadata")
    def test_duplicate_filename_increments(self, mock_ai, tmp_path, sample_config):
        mock_ai.return_value = _mock_metadata("ACME", "15.03.2024", "ER")

        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        # Create the target filename first to force a collision
        existing = str(tmp_path / "20240315 ACME ER.pdf")
        with open(existing, 'w') as f:
            f.write("already here")

        pdf_copy = str(tmp_path / "invoice.pdf")
        shutil.copy2(src, pdf_copy)

        process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                    str(tmp_path / ".autorename-log.json"), dry_run=False)

        expected = str(tmp_path / "20240315 ACME ER_(1).pdf")
        assert os.path.exists(expected)


class TestFullPipelineFailures:
    """Test graceful failure handling."""

    def test_empty_pdf_fails(self, tmp_path, sample_config):
        src = os.path.join(FIXTURES_DIR, "empty.pdf")
        pdf_copy = str(tmp_path / "empty.pdf")
        shutil.copy2(src, pdf_copy)
        sample_config["pdf"]["ocr"] = False
        sample_config["pdf"]["vision"] = False

        result = process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=False)
        assert result.status == "failed"
        # Original should still exist
        assert os.path.exists(pdf_copy)

    @patch("autorename_pdf.extract_metadata", return_value=None)
    def test_ai_returns_none(self, mock_ai, tmp_path, sample_config):
        src = os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")
        pdf_copy = str(tmp_path / "invoice.pdf")
        shutil.copy2(src, pdf_copy)

        result = process_pdf(pdf_copy, sample_config, str(tmp_path / "names.yaml"),
                             str(tmp_path / ".autorename-log.json"), dry_run=False)
        assert result.status == "failed"
        assert os.path.exists(pdf_copy)


class TestCollectPdfFiles:
    """Test file collection from paths."""

    def test_collect_from_folder(self, tmp_path):
        (tmp_path / "a.pdf").write_text("fake")
        (tmp_path / "b.pdf").write_text("fake")
        (tmp_path / "c.txt").write_text("not a pdf")

        files = collect_pdf_files([str(tmp_path)])
        assert len(files) == 2

    def test_collect_single_file(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_text("fake")
        files = collect_pdf_files([str(pdf)])
        assert len(files) == 1

    def test_collect_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.pdf").write_text("fake")
        (sub / "b.pdf").write_text("fake")

        files_flat = collect_pdf_files([str(tmp_path)], recursive=False)
        files_recursive = collect_pdf_files([str(tmp_path)], recursive=True)
        assert len(files_flat) == 1
        assert len(files_recursive) == 2

    def test_trailing_backslash_path(self, tmp_path):
        (tmp_path / "a.pdf").write_text("fake")
        mangled = str(tmp_path) + '\\"'
        files = collect_pdf_files([mangled])
        assert len(files) == 1
