"""Shared test fixtures for AutoRename-PDF."""

import copy
import json
import os
import sys
import urllib.request
import pytest
from PIL import Image

# Load .env file if python-dotenv is installed (dev dependency)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from _pdf_utils import _paddleocr_available


# --- Live test prerequisite helpers ---

_paddleocr_cached = None

def _paddleocr_available_for_tests() -> bool:
    """Check if PaddleOCR venv is installed (cached)."""
    global _paddleocr_cached
    if _paddleocr_cached is None:
        _paddleocr_cached = _paddleocr_available({"paddleocr": {"venv_path": ""}})
    return _paddleocr_cached


def _ollama_vision_model() -> str | None:
    """Return name of an installed vision-capable Ollama model, or None."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            for m in data.get("models", []):
                name = m.get("name", "")
                if "-vl" in name or "vl:" in name or "llava" in name:
                    return name
    except Exception:
        pass
    return None


# --- pytest hooks for live integration tests ---

def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="Run live integration tests against real AI endpoints")
    parser.addoption("--provider", action="store", default=None,
                     help="Run live tests for a specific provider: openai, anthropic, ollama")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: mark test as live integration test")
    config.addinivalue_line("markers", "openai: tests specific to OpenAI provider")
    config.addinivalue_line("markers", "anthropic: tests specific to Anthropic provider")
    config.addinivalue_line("markers", "ollama: tests specific to local Ollama provider")
    config.addinivalue_line("markers", "vision: tests requiring vision-capable model")
    config.addinivalue_line("markers", "ocr: tests requiring PaddleOCR installed")


def _ollama_available() -> bool:
    """Check if Ollama is responding at localhost:11434."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    run_live = config.getoption("--run-live")
    provider_filter = config.getoption("--provider")

    for item in items:
        # Skip all live tests unless --run-live
        if "live" in item.keywords and not run_live:
            item.add_marker(pytest.mark.skip(reason="Need --run-live to run"))
            continue

        if not run_live:
            continue

        # Provider-specific skip logic
        if "openai" in item.keywords:
            if provider_filter and provider_filter != "openai":
                item.add_marker(pytest.mark.skip(reason=f"--provider={provider_filter}"))
            elif not os.environ.get("OPENAI_API_KEY"):
                item.add_marker(pytest.mark.skip(reason="OPENAI_API_KEY not set"))

        if "anthropic" in item.keywords:
            if provider_filter and provider_filter != "anthropic":
                item.add_marker(pytest.mark.skip(reason=f"--provider={provider_filter}"))
            elif not os.environ.get("ANTHROPIC_API_KEY"):
                item.add_marker(pytest.mark.skip(reason="ANTHROPIC_API_KEY not set"))

        if "ollama" in item.keywords:
            if provider_filter and provider_filter != "ollama":
                item.add_marker(pytest.mark.skip(reason=f"--provider={provider_filter}"))
            elif not _ollama_available():
                item.add_marker(pytest.mark.skip(reason="Ollama not running at localhost:11434"))
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
            "device": "auto",
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


@pytest.fixture
def real_config():
    """Config matching the actual config.yaml structure (with test API key)."""
    return {
        "config_version": 2,
        "ai": {
            "provider": "openai",
            "model": "gpt-5.4",
            "api_key": "test-key-for-testing-only",
            "base_url": "",
            "temperature": 0.0,
            "max_retries": 2,
        },
        "pdf": {
            "max_pages": 3,
            "ocr": False,
            "vision": True,
            "text_quality_threshold": 0.3,
            "outgoing_invoice": "AR",
            "incoming_invoice": "ER",
        },
        "paddleocr": {
            "venv_path": "",
            "languages": ["en", "de"],
            "device": "auto",
        },
        "company": {
            "name": "Petermeir Web Solutions, Gerhard Petermeir",
        },
        "output": {
            "language": "German",
            "date_format": "%Y%m%d",
        },
        "prompt_extension": 'If it is an incoming or outgoing invoice, add the total amount to the document_type like "AR 12,34" or "ER 56,78".',
    }


# --- JSON contract validators (match TypeScript interfaces in gui/src/lib/sidecar.ts) ---

def assert_batch_result_schema(data: dict):
    """Validate JSON matches the GUI's BatchResult TypeScript interface."""
    assert isinstance(data.get("success"), bool), "success must be bool"
    for key in ("total", "renamed", "skipped", "failed"):
        assert isinstance(data.get(key), int), f"{key} must be int"
    assert isinstance(data.get("dry_run"), bool), "dry_run must be bool"
    assert isinstance(data.get("files"), list), "files must be list"
    for f in data["files"]:
        assert "file" in f and isinstance(f["file"], str)
        assert f["status"] in ("renamed", "skipped", "failed")
        for key in ("new_name", "new_path", "error", "company", "date", "doc_type", "provider", "model"):
            assert key in f, f"FileResult missing key: {key}"


def assert_error_result_schema(data: dict):
    """Validate JSON matches the GUI's ErrorResult TypeScript interface."""
    assert data.get("success") is False
    assert isinstance(data.get("error_type"), str) and data["error_type"]
    assert isinstance(data.get("message"), str) and data["message"]
    assert "suggestion" in data  # can be None


def assert_undo_result_schema(data: dict):
    """Validate JSON matches the GUI's UndoResult TypeScript interface."""
    assert isinstance(data.get("success"), bool)
    assert isinstance(data.get("restored"), int)
    assert isinstance(data.get("failed"), int)
    assert isinstance(data.get("files"), list)
    for f in data["files"]:
        assert "old_path" in f and "new_path" in f and "status" in f
        assert f["status"] in ("restored", "failed")


def assert_batch_list_schema(data: dict):
    """Validate JSON matches the GUI's UndoBatchListResult TypeScript interface."""
    assert isinstance(data.get("batches"), list)
    for b in data["batches"]:
        assert "batch_id" in b and "file_count" in b


# --- Live provider config builders ---

def _base_live_config() -> dict:
    """Base config structure for live tests (matches actual config.yaml)."""
    return {
        "config_version": 2,
        "ai": {
            "provider": "",
            "model": "",
            "api_key": "",
            "base_url": "",
            "temperature": 0.0,
            "max_retries": 3,
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
            "languages": ["en", "de"],
            "device": "auto",
        },
        "company": {
            "name": "Petermeir Web Solutions, Gerhard Petermeir",
        },
        "output": {
            "language": "German",
            "date_format": "%Y%m%d",
        },
        "prompt_extension": "",
    }


@pytest.fixture
def openai_config():
    """Live OpenAI config with real API key from .env."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    config = _base_live_config()
    config["ai"]["provider"] = "openai"
    config["ai"]["model"] = "gpt-5.4-mini"
    config["ai"]["api_key"] = key
    return config


@pytest.fixture
def anthropic_config():
    """Live Anthropic config with real API key from .env."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    config = _base_live_config()
    config["ai"]["provider"] = "anthropic"
    config["ai"]["model"] = "claude-haiku-4-5-20251001"
    config["ai"]["api_key"] = key
    return config


@pytest.fixture
def ollama_config():
    """Live Ollama config (local, no API key needed)."""
    if not _ollama_available():
        pytest.skip("Ollama not running at localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
    config = _base_live_config()
    config["ai"]["provider"] = "ollama"
    config["ai"]["model"] = model
    config["ai"]["api_key"] = ""
    return config


# --- Vision-enabled config fixtures ---

@pytest.fixture
def openai_vision_config(openai_config):
    """OpenAI config with vision enabled (gpt-5.4-mini supports vision)."""
    config = copy.deepcopy(openai_config)
    config["pdf"]["vision"] = True
    return config


@pytest.fixture
def anthropic_vision_config(anthropic_config):
    """Anthropic config with vision enabled (claude-haiku-4-5 supports vision)."""
    config = copy.deepcopy(anthropic_config)
    config["pdf"]["vision"] = True
    return config


@pytest.fixture
def ollama_vision_config():
    """Ollama config with a vision-capable model (auto-detected)."""
    if not _ollama_available():
        pytest.skip("Ollama not running at localhost:11434")
    model = _ollama_vision_model()
    if not model:
        pytest.skip("No vision-capable Ollama model installed (need *-vl or llava model)")
    config = _base_live_config()
    config["ai"]["provider"] = "ollama"
    config["ai"]["model"] = model
    config["ai"]["api_key"] = ""
    config["pdf"]["vision"] = True
    return config


# --- OCR-enabled config fixtures ---

@pytest.fixture
def openai_ocr_config(openai_config):
    """OpenAI config with PaddleOCR enabled."""
    if not _paddleocr_available_for_tests():
        pytest.skip("PaddleOCR not available")
    config = copy.deepcopy(openai_config)
    config["pdf"]["ocr"] = True
    return config


@pytest.fixture
def anthropic_ocr_config(anthropic_config):
    """Anthropic config with PaddleOCR enabled."""
    if not _paddleocr_available_for_tests():
        pytest.skip("PaddleOCR not available")
    config = copy.deepcopy(anthropic_config)
    config["pdf"]["ocr"] = True
    return config


@pytest.fixture
def ollama_ocr_config(ollama_config):
    """Ollama config with PaddleOCR enabled (Max Privacy scenario)."""
    if not _paddleocr_available_for_tests():
        pytest.skip("PaddleOCR not available")
    config = copy.deepcopy(ollama_config)
    config["pdf"]["ocr"] = True
    return config


# --- Combined / Auto config fixtures ---

@pytest.fixture
def openai_combined_config(openai_config):
    """OpenAI config with both OCR and vision enabled."""
    if not _paddleocr_available_for_tests():
        pytest.skip("PaddleOCR not available")
    config = copy.deepcopy(openai_config)
    config["pdf"]["ocr"] = True
    config["pdf"]["vision"] = True
    return config


@pytest.fixture
def openai_auto_config(openai_config):
    """OpenAI config with auto mode for OCR and vision."""
    config = copy.deepcopy(openai_config)
    config["pdf"]["ocr"] = "auto"
    config["pdf"]["vision"] = "auto"
    return config


# --- Feature config fixtures ---

@pytest.fixture
def openai_prompt_ext_config(openai_config):
    """OpenAI config with prompt_extension for extracting invoice totals."""
    config = copy.deepcopy(openai_config)
    config["prompt_extension"] = (
        'If it is an incoming or outgoing invoice, add the total amount '
        'to the document_type like "AR 12,34" or "ER 56,78".'
    )
    return config


@pytest.fixture
def openai_german_config(openai_config):
    """OpenAI config with German output language."""
    config = copy.deepcopy(openai_config)
    config["output"]["language"] = "German"
    return config


# --- Live data fixtures ---

@pytest.fixture
def live_harmonized_names(tmp_path):
    """Harmonized company names YAML covering all fixture PDF companies."""
    import yaml
    names = {
        "ACME": ["ACME Corporation", "Acme Corp", "ACME Inc", "ACME Corporation GmbH"],
        "Mustermann": ["Max Mustermann", "Mustermann GmbH", "Mustermann Consulting",
                        "Mustermann Handel", "Max Mustermann Consulting"],
        "Springfield Nuclear": ["Springfield Power Co.", "Springfield Nuclear Power",
                                 "Springfield Nuclear Plant"],
        "Initech": ["Initech Solutions", "Initech Solutions AG", "Initech Corp"],
        "Stark Industries": ["Stark Industries", "Stark Inc", "Stark"],
        "Globex": ["Globex Corporation", "Globex Corp"],
        "Wayne Enterprises": ["Wayne Enterprises", "Wayne Industries", "Wayne Corp"],
    }
    path = str(tmp_path / "harmonized-company-names.yaml")
    with open(path, 'w') as f:
        yaml.dump(names, f)
    return path
