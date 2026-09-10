"""Shipped example configs must load and validate with no errors."""
from pathlib import Path

import pytest

from _config_loader import load_yaml_config
from _document_processing import render_filename
from _profiles import select_profile
from autorename_pdf_runner import _mod as cli

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = [
    ROOT / "config.yaml.example",
    ROOT / "examples" / "academic.yaml",
    ROOT / "examples" / "er-ar.yaml",
    ROOT / "examples" / "ollama-offline.yaml",
    ROOT / "examples" / "vision-cloud.yaml",
    ROOT / "examples" / "invoice-id.yaml",
]


@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_shipped_example_config_validates(path):
    assert path.is_file(), f"missing shipped example: {path}"
    config = load_yaml_config(str(path))
    assert config is not None
    result = cli._validate_config(config, str(path))
    errors = [i for i in result["issues"] if i["level"] == "error"]
    assert errors == []
    assert result["valid"] is True


def test_root_example_is_invoice_first():
    config = load_yaml_config(str(ROOT / "config.yaml.example"))
    result = cli._validate_config(config, "config.yaml.example")
    assert config["profile"] == "business"
    assert config["pdf"]["incoming_invoice"] == "AP"
    assert config["pdf"]["outgoing_invoice"] == "AR"
    assert result["profile"] == "business"
    assert "description" in result["resolved_profile"]["fields"]


def test_academic_example_selects_academic_builtin():
    config = load_yaml_config(str(ROOT / "examples" / "academic.yaml"))
    result = cli._validate_config(config, "examples/academic.yaml")
    assert config["profile"] == "academic"
    assert result["profile"] == "academic"
    assert "first_author_surname" in result["resolved_profile"]["fields"]
    assert result["resolved_profile"]["harmonize_field"] is None


def test_er_ar_example_uses_eingangs_ausgangs_codes():
    config = load_yaml_config(str(ROOT / "examples" / "er-ar.yaml"))
    assert config["pdf"]["incoming_invoice"] == "ER"
    assert config["pdf"]["outgoing_invoice"] == "AR"
    result = cli._validate_config(config, "examples/er-ar.yaml")
    assert result["valid"] is True


def test_ollama_example_allows_empty_api_key():
    config = load_yaml_config(str(ROOT / "examples" / "ollama-offline.yaml"))
    assert config["ai"]["provider"] == "ollama"
    assert config["ai"]["api_key"] == ""
    assert config["pdf"]["ocr"] is True
    result = cli._validate_config(config, "examples/ollama-offline.yaml")
    assert result["valid"] is True
    assert not any(i["field"] == "ai.api_key" and i["level"] == "error" for i in result["issues"])


def test_invoice_id_example_keeps_amount_and_adds_id():
    config = load_yaml_config(str(ROOT / "examples" / "invoice-id.yaml"))
    result = cli._validate_config(config, "examples/invoice-id.yaml")
    template = result["resolved_profile"]["template"]
    assert template == "{document_date} {company_name} {document_type} {description} {invoice_id}"
    assert result["resolved_profile"]["truncate_field"] == "description"
    pid, profile = select_profile(config)
    name = render_filename(pid, profile, {
        "document_date": "06.09.2026", "company_name": "ACME",
        "document_type": "AP", "description": "12,13", "invoice_id": "12345",
    }, config)
    assert name == "20260906 ACME AP 12,13 12345.pdf"


def test_vision_cloud_example_enables_vision_without_ocr():
    config = load_yaml_config(str(ROOT / "examples" / "vision-cloud.yaml"))
    assert config["ai"]["provider"] == "gemini"
    assert config["pdf"]["vision"] is True
    assert config["pdf"]["ocr"] is False
    result = cli._validate_config(config, "examples/vision-cloud.yaml")
    assert result["valid"] is True


def test_documented_example_filenames():
    cases = [
        (
            ROOT / "config.yaml.example",
            {"document_date": "06.09.2026", "company_name": "ACME",
             "document_type": "AP", "description": "12,13"},
            "20260906 ACME AP 12,13.pdf",
        ),
        (
            ROOT / "examples" / "er-ar.yaml",
            {"document_date": "06.09.2026", "company_name": "ACME",
             "document_type": "ER", "description": "12,13"},
            "20260906 ACME ER 12,13.pdf",
        ),
        (
            ROOT / "examples" / "academic.yaml",
            {"document_date": "01.01.2026", "first_author_surname": "Smith",
             "journal_name": "Nature", "title": "Attention Is All You Need"},
            "20260101 Smith Nature Attention Is All You Need.pdf",
        ),
        (
            ROOT / "examples" / "academic.yaml",
            {"document_date": "01.01.2026", "first_author_surname": "Smith",
             "journal_name": "", "title": "Original title"},
            "20260101 Smith Original title.pdf",
        ),
    ]
    for path, fields, expected in cases:
        config = load_yaml_config(str(path))
        pid, profile = select_profile(config)
        assert render_filename(pid, profile, fields, config) == expected