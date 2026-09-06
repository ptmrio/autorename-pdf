from copy import deepcopy
import json
from unittest.mock import Mock

import pytest
import yaml

from autorename_pdf_runner import _mod as cli
from _pdf_utils import ExtractionResult
from _profiles import build_metadata_model


def call_cli(argv, capsys):
    args = cli.build_parser().parse_args(argv)
    handler = cli._handle_config if args.subcommand == "config" else cli._handle_rename
    with pytest.raises(SystemExit) as stopped:
        handler(args, "json")
    return stopped.value.code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("invalid", [
    pytest.param("profile: missing\n", id="unknown-selected"),
    pytest.param("profile: ' business'\n", id="malformed-selected"),
    pytest.param("profiles: null\n", id="null-container"),
    pytest.param("profiles: []\n", id="list-container"),
    pytest.param("profiles: {unused: {extends: missing}}\n", id="invalid-unselected"),
    pytest.param("profiles: {business: {fields: {document_date: null}}}\n", id="deleted-date"),
    pytest.param("profiles: {business: {template: '{description!r}'}}\n", id="invalid-placeholder"),
    pytest.param("profiles: {business: {intro: '{unknown}'}}\n", id="invalid-prompt-placeholder"),
    pytest.param("profiles: {business: null}\n", id="null-definition"),
    pytest.param("profile: business\nprofile: academic\n", id="duplicate-yaml"),
    pytest.param("filename: '{document_date}'\n", id="unsupported-top-level-filename"),
    pytest.param("profiles: {business: {truncate_field: []}}\n", id="truncate-list"),
    pytest.param("profiles: {notes: {extends: '', fields: {document_date: {description: Date}, title: {description: Title}}, template: '{title}', truncate_field: title}}\n", id="empty-parent"),
])
@pytest.mark.parametrize("command", ["rename", "validate"])
def test_invalid_config_exits_3_before_content_provider_or_mutation(
    tmp_path, monkeypatch, capsys, invalid, command,
):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"keep")
    config = tmp_path / "test-config.yaml"
    contents = "config_version: 2\nai: {provider: ollama, model: test}\n" + invalid
    config.write_text(contents, encoding="utf-8")
    content = Mock(side_effect=AssertionError("content called for invalid config"))
    provider = Mock(side_effect=AssertionError("provider called for invalid config"))
    rename = Mock(side_effect=AssertionError("rename called for invalid config"))
    batch = Mock(side_effect=AssertionError("undo batch created for invalid config"))
    monkeypatch.setattr(cli, "extract_content", content)
    monkeypatch.setattr(cli, "extract_metadata", provider)
    monkeypatch.setattr(cli, "rename_document", rename)
    monkeypatch.setattr(cli, "generate_batch_id", batch)
    argv = ["rename", str(source)] if command == "rename" else ["config", "validate"]
    code, payload = call_cli(argv + ["--config", str(config), "--output", "json"], capsys)
    assert code == 3
    if command == "validate":
        assert payload["valid"] is False
        assert any(issue["level"] == "error" for issue in payload["issues"])
    else:
        assert payload["error_type"] == "config_error"
    for operation in (content, provider, rename, batch):
        operation.assert_not_called()
    assert source.read_bytes() == b"keep"
    assert config.read_text(encoding="utf-8") == contents
    assert not (tmp_path / ".autorename-log.json").exists()


@pytest.mark.parametrize("override,selected,expected", [
    (None, "receipts", "20260906 ACME 12,13.pdf"),
    ("academic", "academic", "20260906 Smith A Study.pdf"),
])
def test_cli_selection_builds_one_model_per_batch_without_config_write(
    sample_config, tmp_path, monkeypatch, capsys, override, selected, expected,
):
    config = deepcopy(sample_config)
    config["profile"] = "receipts"
    config["profiles"] = {"receipts": {
        "extends": "business", "template": "{document_date} {company_name} {description}",
        "harmonize_field": None,
    }}
    path = tmp_path / "test-config.yaml"
    original = yaml.safe_dump(config, sort_keys=False)
    path.write_text(original, encoding="utf-8")
    sources = [tmp_path / "one.pdf", tmp_path / "two.pdf"]
    for source in sources:
        source.write_bytes(b"keep")
    monkeypatch.setattr(cli, "extract_content", Mock(return_value=ExtractionResult(
        text="Printed content", quality_score=1, page_count=1, sources=["text"],
    )))
    models = []
    def extract(extraction, loaded_config, *, profile, metadata_model):
        models.append(metadata_model)
        values = {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "ER", "description": "12,13", "first_author_surname": "Smith", "journal_name": "", "title": "A Study"}
        return metadata_model.model_validate({name: values[name] for name in profile["fields"]})
    monkeypatch.setattr(cli, "extract_metadata", extract)
    factory = Mock(wraps=build_metadata_model)
    monkeypatch.setattr(cli, "build_metadata_model", factory)
    argv = ["rename", *(str(source) for source in sources), "--dry-run", "--config", str(path), "--output", "json"]
    if override is not None:
        argv += ["--profile", override]
    code, payload = call_cli(argv, capsys)
    assert code == 0
    assert (payload["total"], payload["renamed"], payload["skipped"], payload["failed"]) == (2, 2, 0, 0)
    assert payload["dry_run"] is True
    assert [item["profile"] for item in payload["files"]] == [selected, selected]
    assert [item["new_name"] for item in payload["files"]] == [expected, expected]
    assert len(models) == 2 and models[0] is models[1]
    factory.assert_called_once()
    assert path.read_text(encoding="utf-8") == original
    assert all(source.read_bytes() == b"keep" for source in sources)
    assert not (tmp_path / ".autorename-log.json").exists()


def test_unknown_cli_profile_is_config_error(sample_config, tmp_path, capsys, monkeypatch):
    path = tmp_path / "test-config.yaml"
    path.write_text(yaml.safe_dump(sample_config), encoding="utf-8")
    process = Mock(side_effect=AssertionError("must not process"))
    monkeypatch.setattr(cli, "process_pdf", process)
    code, payload = call_cli(["rename", "absent.pdf", "--profile", "Academic", "--config", str(path)], capsys)
    assert code == 3
    assert payload["error_type"] == "config_error"
    process.assert_not_called()


def test_cli_profile_override_ignores_stale_configured_selection(
    sample_config, tmp_path, capsys, monkeypatch,
):
    sample_config["profile"] = "missing"
    path = tmp_path / "test-config.yaml"
    path.write_text(yaml.safe_dump(sample_config), encoding="utf-8")
    process = Mock(side_effect=AssertionError("must not process"))
    monkeypatch.setattr(cli, "process_pdf", process)
    code, payload = call_cli(
        ["rename", "absent.pdf", "--profile", "academic", "--dry-run", "--config", str(path)],
        capsys,
    )
    assert code == 4
    assert payload["error_type"] == "no_files"
    process.assert_not_called()


def test_config_show_includes_resolved_selection_and_keeps_redaction(sample_config, tmp_path, capsys):
    sample_config.update(profile="academic", profiles={"academic": {"intro": "Custom academic intro."}})
    sample_config["ai"]["api_key"] = "secret"
    path = tmp_path / "test-config.yaml"
    original = yaml.safe_dump(sample_config, sort_keys=False)
    path.write_text(original, encoding="utf-8")
    code, payload = call_cli(["config", "show", "--config", str(path)], capsys)
    assert code == 0
    assert payload["profile"] == "academic"
    assert payload["resolved_profile"]["intro"] == "Custom academic intro."
    assert payload["resolved_profile"]["harmonize_field"] is None
    assert list(payload["resolved_profile"]["fields"]) == ["document_date", "first_author_surname", "journal_name", "title"]
    assert payload["ai"]["api_key"] == "***"
    assert payload["profiles"] == sample_config["profiles"]
    assert path.read_text(encoding="utf-8") == original
