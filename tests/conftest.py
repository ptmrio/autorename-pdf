"""Shared test fixtures for AutoRename-PDF."""

import os
import pytest
from PIL import Image


# --- pytest hooks for live integration tests ---

def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="Run live integration tests against real AI endpoints")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: mark test as live integration test")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        skip = pytest.mark.skip(reason="Need --run-live to run")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip)
from fpdf import FPDF

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def sample_config():
    """A complete v2 config dict for testing."""
    return {
        "config_version": 2,
        "ai": {
            "provider": "openai",
            "model": "gpt-5.4",
            "api_key": "test-key-123",
            "base_url": "",
            "temperature": 0.0,
            "max_retries": 2,
        },
        "pdf": {
            "max_pages": 3,
            "ocr": False,
            "vision": False,
            "text_quality_threshold": 0.3,
            "outgoing_invoice": "AR",
            "incoming_invoice": "ER",
        },
        "paddleocr": {
            "venv_path": "",
            "languages": ["en"],
            "use_gpu": False,
        },
        "company": {
            "name": "Test Company",
        },
        "output": {
            "language": "English",
            "date_format": "%Y%m%d",
        },
        "prompt_extension": "",
    }


# --- Generated fixture PDFs ---

@pytest.fixture
def sample_pdf(tmp_path):
    """Create a simple PDF with text content for testing."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Invoice #12345", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "Date: 15.03.2024", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "From: ACME Corporation GmbH", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "To: Test Company", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "Amount: EUR 1,234.56", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "Description: Web Development Services", new_x="LMARGIN", new_y="NEXT")
    pdf_path = str(tmp_path / "test_invoice.pdf")
    pdf.output(pdf_path)
    return pdf_path


@pytest.fixture
def empty_pdf(tmp_path):
    """Create an empty PDF (no text content)."""
    pdf = FPDF()
    pdf.add_page()
    pdf_path = str(tmp_path / "empty.pdf")
    pdf.output(pdf_path)
    return pdf_path


@pytest.fixture
def fixture_text_invoice():
    """Clean English text invoice from fixtures."""
    return os.path.join(FIXTURES_DIR, "text_invoice_acme.pdf")


@pytest.fixture
def fixture_german_invoice():
    """German text invoice from fixtures."""
    return os.path.join(FIXTURES_DIR, "text_rechnung_mustermann.pdf")


@pytest.fixture
def fixture_image_invoice():
    """Image-only scanned invoice from fixtures (no extractable text)."""
    return os.path.join(FIXTURES_DIR, "image_invoice_springfield.pdf")


@pytest.fixture
def fixture_mixed_invoice():
    """Text invoice with embedded logo image."""
    return os.path.join(FIXTURES_DIR, "mixed_invoice_initech.pdf")


@pytest.fixture
def fixture_multipage():
    """3-page invoice from fixtures."""
    return os.path.join(FIXTURES_DIR, "multipage_invoice_stark.pdf")


@pytest.fixture
def fixture_letter():
    """Business letter (not an invoice)."""
    return os.path.join(FIXTURES_DIR, "text_letter_globex.pdf")


@pytest.fixture
def fixture_outgoing():
    """Outgoing invoice (AR classification)."""
    return os.path.join(FIXTURES_DIR, "text_outgoing_invoice_wayne.pdf")


@pytest.fixture
def fixture_empty():
    """Empty PDF from fixtures."""
    return os.path.join(FIXTURES_DIR, "empty.pdf")


@pytest.fixture
def fixture_minimal():
    """Minimal text PDF from fixtures."""
    return os.path.join(FIXTURES_DIR, "minimal_text.pdf")


# --- Other fixtures ---

@pytest.fixture
def sample_pil_image():
    """Create a simple PIL image for testing."""
    return Image.new("RGB", (200, 100), color="white")


@pytest.fixture
def harmonized_names_file(tmp_path):
    """Create a test harmonized company names YAML file."""
    import yaml
    names = {
        "ACME": ["ACME Corporation", "Acme Corp", "ACME Inc"],
        "Globex": ["Globex Corporation", "Globex Corp"],
    }
    path = str(tmp_path / "harmonized-company-names.yaml")
    with open(path, 'w') as f:
        yaml.dump(names, f)
    return path
