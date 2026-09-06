from copy import deepcopy
from unittest.mock import Mock

import pytest

from autorename_pdf_runner import _mod as cli
from _pdf_utils import ExtractionResult
from _profiles import build_metadata_model, select_profile


def run_file(tmp_path, monkeypatch, config, selected, raw, *, mode="dry", filename="source.pdf"):
    profile_id, profile = select_profile(config, selected)
    model = build_metadata_model(profile)
    source = tmp_path / filename
    source.write_bytes(b"source bytes")
    content = ExtractionResult(text="Printed content", quality_score=1, page_count=1, sources=["text"])
    if mode == "no-content":
        content = ExtractionResult(text="", quality_score=0, page_count=1, sources=["text"])
    monkeypatch.setattr(cli, "extract_content", Mock(return_value=content))
    extract = Mock(return_value=None if mode == "no-metadata" else model.model_validate(raw))
    if mode == "provider-error":
        extract.side_effect = RuntimeError("provider failed")
    monkeypatch.setattr(cli, "extract_metadata", extract)
    if mode == "rename-error":
        monkeypatch.setattr(cli, "rename_document", Mock(side_effect=PermissionError("locked")))
    return cli.process_pdf(
        str(source), config, str(tmp_path / "aliases.yaml"), str(tmp_path / "undo.json"),
        dry_run=True, profile_id=profile_id, profile=profile, metadata_model=model,
    ).to_dict()


def test_business_raw_survives_aliases_unicode_and_truncation(sample_config, tmp_path, monkeypatch):
    import _document_processing as documents
    (tmp_path / "aliases.yaml").write_text('Canonical: ["Café"]\n', encoding="utf-8")
    raw = {
        "document_date": "06.09.2026", "company_name": "Cafe\u0301",
        "document_type": "ER", "description": "A" * 400,
    }
    before = deepcopy(raw)
    result = run_file(tmp_path, monkeypatch, sample_config, "business", raw)
    assert result["profile"] == "business"
    assert result["fields"] == before
    assert raw == before
    assert result["company"] == "Canonical"
    assert result["date"] == "2026-09-06"
    assert result["doc_type"] == "ER"
    assert result["status"] == "renamed"
    assert result["new_name"] == "20260906 Canonical ER " + "A" * 222 + ".pdf"
    assert documents.parse_document_date(result["fields"]["document_date"]).isoformat() == result["date"]


def test_academic_bypasses_alias_loading_and_keeps_legacy_date(sample_config, tmp_path, monkeypatch):
    import _document_processing as documents
    forbidden = Mock(side_effect=AssertionError("academic must not access company aliases"))
    monkeypatch.setattr(cli, "harmonize_company_name", forbidden)
    monkeypatch.setattr(documents, "load_company_names", forbidden)
    result = run_file(tmp_path, monkeypatch, sample_config, "academic", {
        "document_date": "01.01.2026", "first_author_surname": "Smith",
        "journal_name": "", "title": "Original title",
    })
    assert result["profile"] == "academic"
    assert result["company"] is None
    assert result["doc_type"] is None
    assert result["date"] == "2026-01-01"
    assert result["new_name"] == "20260101 Smith Original title.pdf"
    forbidden.assert_not_called()


def test_different_harmonize_field_does_not_masquerade_as_company(sample_config, tmp_path, monkeypatch):
    sample_config["profiles"] = {"issuer": {
        "extends": "business", "harmonize_field": "provider",
        "fields": {"provider": {"description": "Printed issuer."}},
        "template": "{document_date} {provider} {description}",
    }}
    harmonize = Mock(return_value="Canonical Issuer")
    monkeypatch.setattr(cli, "harmonize_company_name", harmonize)
    raw = {
        "document_date": "bad date", "company_name": "Raw company",
        "document_type": "", "description": "12,13", "provider": "Raw issuer",
    }
    result = run_file(tmp_path, monkeypatch, sample_config, "issuer", raw)
    assert result["company"] == "Raw company"
    assert result["doc_type"] == ""
    assert result["date"] is None
    assert result["fields"] == raw
    assert result["new_name"] == "00000000 Canonical Issuer 12,13.pdf"
    assert harmonize.call_args.args[0] == "Raw issuer"
    harmonize.assert_called_once()


def test_academic_added_legacy_names_map_by_presence(sample_config, tmp_path, monkeypatch):
    sample_config["profiles"] = {"academic": {"fields": {
        "company_name": {"description": "Printed company."},
        "document_type": {"description": "Printed category."},
    }}}
    result = run_file(tmp_path, monkeypatch, sample_config, "academic", {
        "document_date": "06.09.2026", "first_author_surname": "Smith",
        "journal_name": "", "title": "A Study", "company_name": "<>Raw", "document_type": "",
    })
    assert result["company"] == "<>Raw"
    assert result["doc_type"] == ""
    assert result["date"] == "2026-09-06"


@pytest.mark.parametrize("mode,filename,status,has_fields", [
    ("no-content", "source.pdf", "failed", False),
    ("no-metadata", "source.pdf", "failed", False),
    ("provider-error", "source.pdf", "failed", False),
    ("rename-error", "source.pdf", "failed", True),
    ("dry", "20260906 ACME ER 12,13.pdf", "skipped", True),
])
def test_failure_and_skip_keep_selected_profile_and_available_raw_fields(
    sample_config, tmp_path, monkeypatch, mode, filename, status, has_fields,
):
    monkeypatch.setattr(cli, "harmonize_company_name", lambda value, path, config: value)
    raw = {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "ER", "description": "12,13"}
    result = run_file(tmp_path, monkeypatch, sample_config, "business", raw, mode=mode, filename=filename)
    assert result["profile"] == "business"
    assert result["fields"] == (raw if has_fields else {})
    assert result["status"] == status
    assert result["new_name"] is None
    assert result["new_path"] is None
    assert (result["company"], result["date"], result["doc_type"]) == (
        ("ACME", "2026-09-06", "ER") if has_fields else (None, None, None)
    )


def test_result_fields_have_independent_empty_dicts():
    first = cli.FileResult(file="first.pdf", status="failed", profile="academic")
    second = cli.FileResult(file="second.pdf", status="failed", profile="business")
    first.fields["title"] = "A Study"
    assert second.to_dict()["fields"] == {}
