"""CLI integration tests for the redesigned subcommand-based CLI."""

import json
import sys
import os
import argparse
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autorename_pdf_runner import (
    build_parser,
    process_pdf,
    FileResult,
    BatchResult,
    ErrorResult,
    UndoFileResult,
    UndoResult,
    ExitCode,
    resolve_output_format,
    error_exit,
    _mod,
)

_preprocess_argv = _mod._preprocess_argv
_redact_config = _mod._redact_config
_validate_config = _mod._validate_config
_handle_config = _mod._handle_config
_handle_rename = _mod._handle_rename
_handle_undo = _mod._handle_undo
_main = _mod.main
get_base_directory = _mod.get_base_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import assert_batch_result_schema, assert_error_result_schema, assert_undo_result_schema, assert_batch_list_schema


# ---------------------------------------------------------------------------
# 1. Subcommand routing
# ---------------------------------------------------------------------------

class TestBuildParser:
    """Test that build_parser() correctly parses subcommands and arguments."""

    def test_rename_with_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "path/to/file.pdf", "--dry-run"])
        assert args.subcommand == "rename"
        assert args.paths == ["path/to/file.pdf"]
        assert args.dry_run is True

    def test_rename_multiple_paths(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "a.pdf", "b.pdf"])
        assert args.subcommand == "rename"
        assert args.paths == ["a.pdf", "b.pdf"]

    def test_rename_recursive(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "folder", "-r"])
        assert args.subcommand == "rename"
        assert args.recursive is True

    def test_undo_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["undo"])
        assert args.subcommand == "undo"

    def test_undo_with_directory(self):
        parser = build_parser()
        args = parser.parse_args(["undo", "/some/dir"])
        assert args.subcommand == "undo"
        assert args.directory == "/some/dir"

    def test_config_show(self):
        parser = build_parser()
        args = parser.parse_args(["config", "show"])
        assert args.subcommand == "config"
        assert args.config_action == "show"

    def test_config_validate(self):
        parser = build_parser()
        args = parser.parse_args(["config", "validate"])
        assert args.subcommand == "config"
        assert args.config_action == "validate"

    def test_global_output_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--output", "json", "rename", "file.pdf"])
        assert args.output == "json"
        assert args.subcommand == "rename"

    def test_global_output_short_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-o", "text", "rename", "file.pdf"])
        assert args.output == "text"

    def test_global_verbose_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--verbose", "rename", "file.pdf"])
        assert args.verbose is True

    def test_global_quiet_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--quiet", "rename", "file.pdf"])
        assert args.quiet is True

    def test_global_config_path(self):
        parser = build_parser()
        args = parser.parse_args(["--config", "/path/to/config.yaml", "rename", "f.pdf"])
        assert args.config_path == "/path/to/config.yaml"

    def test_rename_provider_override(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "f.pdf", "--provider", "anthropic"])
        assert args.provider == "anthropic"

    def test_rename_model_override(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "f.pdf", "--model", "gpt-5.4-mini"])
        assert args.model == "gpt-5.4-mini"

    def test_rename_vision_flag(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "f.pdf", "--vision"])
        assert args.vision is True

    def test_rename_text_only_flag(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "f.pdf", "--text-only"])
        assert args.text_only is True

    def test_rename_ocr_flag(self):
        parser = build_parser()
        args = parser.parse_args(["rename", "f.pdf", "--ocr"])
        assert args.ocr is True

    def test_no_subcommand_gives_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.subcommand is None


# ---------------------------------------------------------------------------
# 2. argv preprocessing
# ---------------------------------------------------------------------------

class TestPreprocessArgv:
    """Test _preprocess_argv injects 'rename' subcommand when needed."""

    def test_bare_file_injects_rename(self):
        result = _preprocess_argv(["file.pdf"])
        assert result == ["rename", "file.pdf"]

    def test_legacy_undo_flag_passthrough(self):
        """--undo is a boolean flag, so no subcommand is injected (all flags)."""
        result = _preprocess_argv(["--undo"])
        assert result == ["--undo"]

    def test_rename_subcommand_unchanged(self):
        result = _preprocess_argv(["rename", "file.pdf", "--dry-run"])
        assert result == ["rename", "file.pdf", "--dry-run"]

    def test_global_flags_preserved_rename_prepended(self):
        result = _preprocess_argv(["--output", "json", "file.pdf"])
        assert result == ["--output", "json", "rename", "file.pdf"]

    def test_config_show_unchanged(self):
        result = _preprocess_argv(["config", "show"])
        assert result == ["config", "show"]

    def test_undo_subcommand_unchanged(self):
        result = _preprocess_argv(["undo"])
        assert result == ["undo"]

    def test_empty_argv(self):
        result = _preprocess_argv([])
        assert result == []

    def test_multiple_files_injects_rename(self):
        result = _preprocess_argv(["a.pdf", "b.pdf"])
        assert result == ["rename", "a.pdf", "b.pdf"]

    def test_verbose_flag_with_file(self):
        result = _preprocess_argv(["--verbose", "file.pdf"])
        assert result == ["--verbose", "rename", "file.pdf"]

    def test_output_json_with_multiple_files(self):
        result = _preprocess_argv(["-o", "json", "a.pdf", "b.pdf"])
        assert result == ["-o", "json", "rename", "a.pdf", "b.pdf"]

    def test_config_path_with_file(self):
        result = _preprocess_argv(["--config", "/path/config.yaml", "file.pdf"])
        assert result == ["--config", "/path/config.yaml", "rename", "file.pdf"]

    def test_help_flag_passthrough(self):
        """--help is a boolean flag, no subcommand injected."""
        result = _preprocess_argv(["--help"])
        assert result == ["--help"]

    def test_only_boolean_flags_passthrough(self):
        result = _preprocess_argv(["--verbose", "--quiet"])
        assert result == ["--verbose", "--quiet"]


# ---------------------------------------------------------------------------
# 3. Output format resolution
# ---------------------------------------------------------------------------

class TestResolveOutputFormat:
    """Test resolve_output_format priority logic."""

    def test_explicit_json(self):
        args = argparse.Namespace(output="json")
        assert resolve_output_format(args) == "json"

    def test_explicit_text(self):
        args = argparse.Namespace(output="text")
        assert resolve_output_format(args) == "text"

    def test_no_flag_tty_returns_text(self):
        args = argparse.Namespace(output=None)
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty = MagicMock(return_value=True)
            with patch.object(sys, "frozen", False, create=True):
                assert resolve_output_format(args) == "text"

    def test_no_flag_non_tty_returns_json(self):
        args = argparse.Namespace(output=None)
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty = MagicMock(return_value=False)
            # Make sure sys.frozen is not set
            frozen_existed = hasattr(sys, "frozen")
            if frozen_existed:
                old_val = sys.frozen
            try:
                if hasattr(sys, "frozen"):
                    delattr(sys, "frozen")
                assert resolve_output_format(args) == "json"
            finally:
                if frozen_existed:
                    sys.frozen = old_val

    def test_no_flag_frozen_returns_text(self):
        args = argparse.Namespace(output=None)
        with patch.object(sys, "frozen", True, create=True):
            assert resolve_output_format(args) == "text"

    def test_explicit_flag_overrides_frozen(self):
        args = argparse.Namespace(output="json")
        with patch.object(sys, "frozen", True, create=True):
            assert resolve_output_format(args) == "json"

    def test_explicit_flag_overrides_non_tty(self):
        args = argparse.Namespace(output="text")
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty = MagicMock(return_value=False)
            assert resolve_output_format(args) == "text"


# ---------------------------------------------------------------------------
# 4. JSON output — dataclasses
# ---------------------------------------------------------------------------

class TestSetupLogging:
    """Logging should not block the CLI when the log file is unavailable."""

    @patch("autorename_pdf.RotatingFileHandler", side_effect=PermissionError("access denied"))
    def test_setup_logging_survives_file_permission_error(self, _mock_handler):
        _mod.setup_logging(verbose=False)


class TestFileResult:
    """Test FileResult dataclass and serialization."""

    def test_to_dict_all_fields(self):
        r = FileResult(
            file="/path/to/invoice.pdf",
            status="renamed",
            new_name="20240315 ACME ER.pdf",
            new_path="/path/to/20240315 ACME ER.pdf",
            company="ACME",
            date="2024-03-15",
            doc_type="ER",
            provider="openai",
            model="gpt-5.4-mini",
        )
        d = r.to_dict()
        assert d["file"] == "/path/to/invoice.pdf"
        assert d["status"] == "renamed"
        assert d["new_name"] == "20240315 ACME ER.pdf"
        assert d["new_path"] == "/path/to/20240315 ACME ER.pdf"
        assert d["company"] == "ACME"
        assert d["date"] == "2024-03-15"
        assert d["doc_type"] == "ER"
        assert d["provider"] == "openai"
        assert d["model"] == "gpt-5.4-mini"
        assert d["error"] is None

    def test_to_dict_failed(self):
        r = FileResult(file="/path/bad.pdf", status="failed", error="No content")
        d = r.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "No content"
        assert d["new_name"] is None

    def test_to_dict_skipped(self):
        r = FileResult(file="/path/ok.pdf", status="skipped")
        d = r.to_dict()
        assert d["status"] == "skipped"


class TestBatchResult:
    """Test BatchResult serialization."""

    def test_to_json_valid(self):
        fr = FileResult(file="a.pdf", status="renamed", new_name="20240101 X ER.pdf")
        batch = BatchResult(
            success=True, total=1, renamed=1, skipped=0, failed=0,
            files=[fr], dry_run=False,
        )
        j = batch.to_json()
        parsed = json.loads(j)
        assert parsed["success"] is True
        assert parsed["total"] == 1
        assert parsed["renamed"] == 1
        assert parsed["skipped"] == 0
        assert parsed["failed"] == 0
        assert parsed["dry_run"] is False
        assert len(parsed["files"]) == 1
        assert parsed["files"][0]["file"] == "a.pdf"

    def test_to_json_empty_batch(self):
        batch = BatchResult(
            success=True, total=0, renamed=0, skipped=0, failed=0,
        )
        parsed = json.loads(batch.to_json())
        assert parsed["files"] == []

    def test_to_json_dry_run(self):
        batch = BatchResult(
            success=True, total=2, renamed=2, skipped=0, failed=0, dry_run=True,
        )
        parsed = json.loads(batch.to_json())
        assert parsed["dry_run"] is True

    def test_to_json_mixed_results(self):
        files = [
            FileResult(file="a.pdf", status="renamed"),
            FileResult(file="b.pdf", status="failed", error="bad"),
            FileResult(file="c.pdf", status="skipped"),
        ]
        batch = BatchResult(
            success=False, total=3, renamed=1, skipped=1, failed=1, files=files,
        )
        parsed = json.loads(batch.to_json())
        assert parsed["success"] is False
        assert parsed["total"] == 3


class TestErrorResult:
    """Test ErrorResult serialization."""

    def test_to_json_valid(self):
        err = ErrorResult(
            error_type="config_error",
            message="Config not found",
            suggestion="Copy config.yaml.example",
        )
        j = err.to_json()
        parsed = json.loads(j)
        assert parsed["success"] is False
        assert parsed["error_type"] == "config_error"
        assert parsed["message"] == "Config not found"
        assert parsed["suggestion"] == "Copy config.yaml.example"

    def test_to_json_no_suggestion(self):
        err = ErrorResult(error_type="general_error", message="Something broke")
        parsed = json.loads(err.to_json())
        assert parsed["suggestion"] is None

    def test_to_json_is_parseable(self):
        err = ErrorResult(
            error_type="auth_error",
            message="Invalid API key: special chars <>&\"'",
        )
        parsed = json.loads(err.to_json())
        assert "<>&" in parsed["message"]

    def test_to_json_ascii_escapes_unicode(self):
        err = ErrorResult(error_type="general_error", message="OTTO RÖHRS")
        payload = err.to_json()
        assert "RÖHRS" not in payload
        assert "\\u00d6" in payload


class TestUndoResult:
    """Test UndoResult and UndoFileResult serialization."""

    def test_undo_file_result_to_dict(self):
        ufr = UndoFileResult(
            old_path="/old/renamed.pdf",
            new_path="/old/original.pdf",
            status="restored",
        )
        d = ufr.to_dict()
        assert d["old_path"] == "/old/renamed.pdf"
        assert d["new_path"] == "/old/original.pdf"
        assert d["status"] == "restored"
        assert d["error"] is None

    def test_undo_result_to_json(self):
        files = [
            UndoFileResult(old_path="a.pdf", new_path="b.pdf", status="restored"),
        ]
        result = UndoResult(success=True, restored=1, failed=0, files=files)
        parsed = json.loads(result.to_json())
        assert parsed["success"] is True
        assert parsed["restored"] == 1
        assert parsed["failed"] == 0
        assert len(parsed["files"]) == 1


class TestStdioConfig:
    """CLI stdio should be forced to UTF-8 when possible."""

    def test_configure_stdio_utf8_reconfigures_streams(self):
        stdout = MagicMock()
        stderr = MagicMock()
        with patch.object(_mod.sys, "stdout", stdout), patch.object(_mod.sys, "stderr", stderr):
            _mod._configure_stdio_utf8()
        stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="backslashreplace")
        stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="backslashreplace")


# ---------------------------------------------------------------------------
# 5. Structured errors
# ---------------------------------------------------------------------------

class TestErrorExit:
    """Test error_exit produces correct output and exits."""

    def test_json_format_outputs_valid_json(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            error_exit(
                "config_error",
                "Config file missing",
                suggestion="Create config.yaml",
                exit_code=ExitCode.CONFIG_ERROR,
                output_format="json",
            )
        assert exc_info.value.code == ExitCode.CONFIG_ERROR
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["success"] is False
        assert parsed["error_type"] == "config_error"
        assert parsed["message"] == "Config file missing"
        assert parsed["suggestion"] == "Create config.yaml"

    def test_text_format_prints_message(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            error_exit(
                "usage_error",
                "No files specified",
                exit_code=ExitCode.USAGE_ERROR,
                output_format="text",
            )
        assert exc_info.value.code == ExitCode.USAGE_ERROR
        # Text output goes through rich console, which writes to stderr or stdout
        # depending on console configuration. Just verify exit code.

    def test_json_format_no_suggestion(self, capsys):
        with pytest.raises(SystemExit):
            error_exit(
                "no_files",
                "No PDFs found",
                exit_code=ExitCode.NO_FILES,
                output_format="json",
            )
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["suggestion"] is None

    def test_default_exit_code(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            error_exit("general_error", "Oops", output_format="json")
        assert exc_info.value.code == ExitCode.GENERAL_ERROR


# ---------------------------------------------------------------------------
# 6. Config subcommands
# ---------------------------------------------------------------------------

class TestRedactConfig:
    """Test API key redaction logic."""

    def test_long_key_redacted(self):
        config = {"ai": {"api_key": "sk-1234567890abcdef"}}
        redacted = _redact_config(config)
        assert redacted["ai"]["api_key"] == "sk-1...cdef"

    def test_short_key_fully_masked(self):
        config = {"ai": {"api_key": "short"}}
        redacted = _redact_config(config)
        assert redacted["ai"]["api_key"] == "***"

    def test_no_key_untouched(self):
        config = {"ai": {"provider": "ollama"}}
        redacted = _redact_config(config)
        assert "api_key" not in redacted["ai"]

    def test_empty_key_untouched(self):
        config = {"ai": {"api_key": ""}}
        redacted = _redact_config(config)
        assert redacted["ai"]["api_key"] == ""

    def test_original_config_not_mutated(self):
        config = {"ai": {"api_key": "sk-1234567890abcdef"}}
        _redact_config(config)
        assert config["ai"]["api_key"] == "sk-1234567890abcdef"


class TestValidateConfig:
    """Test config validation logic."""

    def test_none_config_reports_error(self):
        result = _validate_config(None, "/path/config.yaml")
        assert result["valid"] is False
        assert any(i["field"] == "config_file" for i in result["issues"])

    def test_missing_provider(self):
        config = {"ai": {"provider": "", "api_key": "key", "model": "m"}, "company": {"name": "X"}}
        result = _validate_config(config, "config.yaml")
        assert any(i["field"] == "ai.provider" for i in result["issues"])

    def test_missing_api_key_non_ollama(self):
        config = {"ai": {"provider": "openai", "api_key": "", "model": "m"}, "company": {"name": "X"}}
        result = _validate_config(config, "config.yaml")
        assert any(i["field"] == "ai.api_key" for i in result["issues"])

    def test_ollama_no_key_ok(self):
        config = {"ai": {"provider": "ollama", "api_key": "", "model": "m"}, "company": {"name": "X"}}
        result = _validate_config(config, "config.yaml")
        assert not any(i["field"] == "ai.api_key" for i in result["issues"])

    def test_missing_model_warning(self):
        config = {"ai": {"provider": "openai", "api_key": "key", "model": ""}, "company": {"name": "X"}}
        result = _validate_config(config, "config.yaml")
        issues = [i for i in result["issues"] if i["field"] == "ai.model"]
        assert len(issues) == 1
        assert issues[0]["level"] == "warning"

    def test_default_company_name_warning(self):
        config = {"ai": {"provider": "openai", "api_key": "key", "model": "m"},
                  "company": {"name": "Your Company Name"}}
        result = _validate_config(config, "config.yaml")
        assert any(i["field"] == "company.name" for i in result["issues"])

    def test_valid_config(self):
        config = {"ai": {"provider": "openai", "api_key": "key", "model": "gpt-5.4-mini"},
                  "company": {"name": "Acme Corp"}}
        result = _validate_config(config, "config.yaml")
        assert result["valid"] is True
        assert len(result["issues"]) == 0


class TestHandleConfigShow:
    """Test config show subcommand."""

    @patch("autorename_pdf._redact_config")
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_config_show_json(self, mock_basedir, mock_load, mock_redact, capsys):
        mock_load.return_value = {"ai": {"provider": "openai", "api_key": "sk-test123456"}}
        mock_redact.return_value = {"ai": {"provider": "openai", "api_key": "sk-t...3456"}}

        args = argparse.Namespace(config_path=None, config_action="show", subcommand="config")
        with pytest.raises(SystemExit) as exc_info:
            _handle_config(args, "json")

        assert exc_info.value.code == ExitCode.SUCCESS
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["ai"]["api_key"] == "sk-t...3456"

    @patch("autorename_pdf.load_yaml_config", return_value=None)
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_config_show_missing_file_json(self, mock_basedir, mock_load, capsys):
        args = argparse.Namespace(config_path=None, config_action="show", subcommand="config")
        with pytest.raises(SystemExit) as exc_info:
            _handle_config(args, "json")

        assert exc_info.value.code == ExitCode.CONFIG_ERROR
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["error_type"] == "config_error"


class TestHandleConfigValidate:
    """Test config validate subcommand."""

    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_config_validate_json_valid(self, mock_basedir, mock_load, capsys):
        mock_load.return_value = {
            "ai": {"provider": "openai", "api_key": "key", "model": "gpt-5.4-mini"},
            "company": {"name": "Acme"},
        }
        args = argparse.Namespace(config_path=None, config_action="validate", subcommand="config")
        with pytest.raises(SystemExit) as exc_info:
            _handle_config(args, "json")

        assert exc_info.value.code == ExitCode.SUCCESS
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["valid"] is True

    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_config_validate_json_invalid(self, mock_basedir, mock_load, capsys):
        mock_load.return_value = {
            "ai": {"provider": "", "api_key": "", "model": ""},
            "company": {"name": ""},
        }
        args = argparse.Namespace(config_path=None, config_action="validate", subcommand="config")
        with pytest.raises(SystemExit) as exc_info:
            _handle_config(args, "json")

        assert exc_info.value.code == ExitCode.CONFIG_ERROR
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["valid"] is False
        assert len(parsed["issues"]) > 0


# ---------------------------------------------------------------------------
# 7. Exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:
    """Verify ExitCode constants exist and have expected values."""

    def test_success(self):
        assert ExitCode.SUCCESS == 0

    def test_general_error(self):
        assert ExitCode.GENERAL_ERROR == 1

    def test_usage_error(self):
        assert ExitCode.USAGE_ERROR == 2

    def test_config_error(self):
        assert ExitCode.CONFIG_ERROR == 3

    def test_no_files(self):
        assert ExitCode.NO_FILES == 4

    def test_partial_failure(self):
        assert ExitCode.PARTIAL_FAILURE == 5

    def test_provider_error(self):
        assert ExitCode.PROVIDER_ERROR == 10

    def test_auth_error(self):
        assert ExitCode.AUTH_ERROR == 11

    def test_error_exit_uses_correct_exit_code(self):
        with pytest.raises(SystemExit) as exc_info:
            error_exit("no_files", "None found", exit_code=ExitCode.NO_FILES, output_format="json")
        assert exc_info.value.code == ExitCode.NO_FILES

    def test_error_exit_default_code(self):
        with pytest.raises(SystemExit) as exc_info:
            error_exit("general_error", "Broken", output_format="json")
        assert exc_info.value.code == ExitCode.GENERAL_ERROR


# ---------------------------------------------------------------------------
# 8. Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Test that legacy CLI patterns still work."""

    def test_bare_file_defaults_to_rename(self):
        """Bare file paths should be preprocessed into rename subcommand."""
        argv = _preprocess_argv(["invoice.pdf"])
        parser = build_parser()
        args = parser.parse_args(argv)
        assert args.subcommand == "rename"
        assert args.paths == ["invoice.pdf"]

    def test_bare_folder_defaults_to_rename(self):
        argv = _preprocess_argv(["./invoices"])
        parser = build_parser()
        args = parser.parse_args(argv)
        assert args.subcommand == "rename"
        assert args.paths == ["./invoices"]

    def test_legacy_undo_flag_detected(self):
        """--undo flag is parsed at the top level (deprecated but functional)."""
        parser = build_parser()
        args = parser.parse_args(["--undo"])
        assert args.undo is True

    def test_bare_paths_with_global_flags(self):
        argv = _preprocess_argv(["-o", "json", "file.pdf"])
        parser = build_parser()
        args = parser.parse_args(argv)
        assert args.subcommand == "rename"
        assert args.output == "json"
        assert args.paths == ["file.pdf"]

    def test_dry_run_with_bare_path(self):
        """Dry run flag after file: preprocessing should handle correctly."""
        argv = _preprocess_argv(["file.pdf", "--dry-run"])
        parser = build_parser()
        args = parser.parse_args(argv)
        assert args.subcommand == "rename"
        assert args.dry_run is True

    def test_multiple_bare_paths(self):
        argv = _preprocess_argv(["a.pdf", "b.pdf", "c.pdf"])
        parser = build_parser()
        args = parser.parse_args(argv)
        assert args.subcommand == "rename"
        assert args.paths == ["a.pdf", "b.pdf", "c.pdf"]


# ---------------------------------------------------------------------------
# 9. Handler-level tests
# ---------------------------------------------------------------------------

class TestHandleRename:
    """Test _handle_rename JSON output contract and exit codes."""

    @patch("autorename_pdf.process_pdf")
    @patch("autorename_pdf.collect_pdf_files", return_value=["/tmp/test.pdf"])
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_json_success(self, mock_bd, mock_load, mock_collect, mock_proc, capsys, sample_config):
        mock_load.return_value = sample_config
        mock_proc.return_value = FileResult(
            file="/tmp/test.pdf", status="renamed",
            new_name="20240315 ACME ER.pdf",
            new_path="/tmp/20240315 ACME ER.pdf",
            company="ACME", date="2024-03-15", doc_type="ER",
            provider="openai", model="gpt-5.4",
        )

        args = argparse.Namespace(
            config_path=None, paths=["/tmp/test.pdf"], dry_run=False,
            recursive=False, quiet=False, provider=None, model=None,
            vision=False, text_only=False, ocr=False, output="json",
        )
        with pytest.raises(SystemExit) as exc_info:
            _handle_rename(args, "json")

        assert exc_info.value.code == ExitCode.SUCCESS
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert_batch_result_schema(data)
        assert data["success"] is True
        assert data["total"] == 1
        assert data["renamed"] == 1
        assert data["files"][0]["company"] == "ACME"

    @patch("autorename_pdf.load_yaml_config", return_value=None)
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_json_no_config(self, mock_bd, mock_load, capsys):
        args = argparse.Namespace(config_path=None, paths=["f.pdf"], dry_run=False,
                                  recursive=False, quiet=False, provider=None, model=None,
                                  vision=False, text_only=False, ocr=False, output="json")
        with pytest.raises(SystemExit) as exc_info:
            _handle_rename(args, "json")

        assert exc_info.value.code == ExitCode.CONFIG_ERROR
        data = json.loads(capsys.readouterr().out)
        assert_error_result_schema(data)
        assert data["error_type"] == "config_error"

    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_json_no_paths(self, mock_bd, mock_load, capsys, sample_config):
        mock_load.return_value = sample_config
        args = argparse.Namespace(config_path=None, paths=[], dry_run=False,
                                  recursive=False, quiet=False, provider=None, model=None,
                                  vision=False, text_only=False, ocr=False, output="json")
        with pytest.raises(SystemExit) as exc_info:
            _handle_rename(args, "json")

        assert exc_info.value.code == ExitCode.USAGE_ERROR
        data = json.loads(capsys.readouterr().out)
        assert_error_result_schema(data)

    @patch("autorename_pdf.collect_pdf_files", return_value=[])
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_json_no_pdfs_found(self, mock_bd, mock_load, mock_collect, capsys, sample_config):
        mock_load.return_value = sample_config
        args = argparse.Namespace(config_path=None, paths=["/empty/dir"], dry_run=False,
                                  recursive=False, quiet=False, provider=None, model=None,
                                  vision=False, text_only=False, ocr=False, output="json")
        with pytest.raises(SystemExit) as exc_info:
            _handle_rename(args, "json")

        assert exc_info.value.code == ExitCode.NO_FILES
        data = json.loads(capsys.readouterr().out)
        assert_error_result_schema(data)

    @patch("autorename_pdf.process_pdf")
    @patch("autorename_pdf.collect_pdf_files", return_value=["/tmp/a.pdf", "/tmp/b.pdf"])
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_json_partial_failure(self, mock_bd, mock_load, mock_collect, mock_proc, capsys, sample_config):
        mock_load.return_value = sample_config
        mock_proc.side_effect = [
            FileResult(file="/tmp/a.pdf", status="renamed", new_name="20240315 ACME ER.pdf",
                       new_path="/tmp/20240315 ACME ER.pdf", company="ACME", date="2024-03-15",
                       doc_type="ER", provider="openai", model="gpt-5.4"),
            FileResult(file="/tmp/b.pdf", status="failed", error="No content",
                       provider="openai", model="gpt-5.4"),
        ]

        args = argparse.Namespace(config_path=None, paths=["/tmp/a.pdf", "/tmp/b.pdf"],
                                  dry_run=False, recursive=False, quiet=False,
                                  provider=None, model=None, vision=False,
                                  text_only=False, ocr=False, output="json")
        with pytest.raises(SystemExit) as exc_info:
            _handle_rename(args, "json")

        assert exc_info.value.code == ExitCode.PARTIAL_FAILURE
        data = json.loads(capsys.readouterr().out)
        assert_batch_result_schema(data)
        assert data["renamed"] == 1
        assert data["failed"] == 1

    @patch("autorename_pdf.process_pdf")
    @patch("autorename_pdf.collect_pdf_files", return_value=["/tmp/a.pdf"])
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_json_all_fail(self, mock_bd, mock_load, mock_collect, mock_proc, capsys, sample_config):
        mock_load.return_value = sample_config
        mock_proc.return_value = FileResult(
            file="/tmp/a.pdf", status="failed", error="No content",
            provider="openai", model="gpt-5.4",
        )

        args = argparse.Namespace(config_path=None, paths=["/tmp/a.pdf"], dry_run=False,
                                  recursive=False, quiet=False, provider=None, model=None,
                                  vision=False, text_only=False, ocr=False, output="json")
        with pytest.raises(SystemExit) as exc_info:
            _handle_rename(args, "json")

        assert exc_info.value.code == ExitCode.GENERAL_ERROR

    @patch("autorename_pdf.process_pdf")
    @patch("autorename_pdf.collect_pdf_files", return_value=["/tmp/test.pdf"])
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_dry_run_json(self, mock_bd, mock_load, mock_collect, mock_proc, capsys, sample_config):
        mock_load.return_value = sample_config
        mock_proc.return_value = FileResult(
            file="/tmp/test.pdf", status="renamed",
            new_name="20240315 ACME ER.pdf", new_path="/tmp/20240315 ACME ER.pdf",
            company="ACME", date="2024-03-15", doc_type="ER",
            provider="openai", model="gpt-5.4",
        )

        args = argparse.Namespace(config_path=None, paths=["/tmp/test.pdf"], dry_run=True,
                                  recursive=False, quiet=False, provider=None, model=None,
                                  vision=False, text_only=False, ocr=False, output="json")
        with pytest.raises(SystemExit) as exc_info:
            _handle_rename(args, "json")

        assert exc_info.value.code == ExitCode.SUCCESS
        data = json.loads(capsys.readouterr().out)
        assert data["dry_run"] is True
        assert data["batch_id"] is None

    @patch("autorename_pdf.process_pdf")
    @patch("autorename_pdf.collect_pdf_files", return_value=["/tmp/test.pdf"])
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_cli_overrides_applied(self, mock_bd, mock_load, mock_collect, mock_proc, capsys, sample_config):
        mock_load.return_value = sample_config
        mock_proc.return_value = FileResult(
            file="/tmp/test.pdf", status="renamed",
            new_name="test.pdf", new_path="/tmp/test.pdf",
            company="X", date="2024-01-01", doc_type="ER",
            provider="anthropic", model="claude-sonnet-4-6",
        )

        args = argparse.Namespace(
            config_path=None, paths=["/tmp/test.pdf"], dry_run=False,
            recursive=False, quiet=False, output="json",
            provider="anthropic", model="claude-sonnet-4-6",
            vision=True, text_only=False, ocr=True,
        )
        with pytest.raises(SystemExit):
            _handle_rename(args, "json")

        # Check that config was mutated before process_pdf was called
        call_args = mock_proc.call_args
        config_used = call_args[0][1]  # second positional arg
        assert config_used["ai"]["provider"] == "anthropic"
        assert config_used["ai"]["model"] == "claude-sonnet-4-6"
        assert config_used["pdf"]["vision"] is True
        assert config_used["pdf"]["ocr"] is True


class TestHandleUndo:
    """Test _handle_undo JSON output contract and exit codes."""

    def test_json_no_log(self, tmp_path, capsys):
        args = argparse.Namespace(directory=str(tmp_path), list_batches=False,
                                  batch=None, undo_all=False)
        with pytest.raises(SystemExit) as exc_info:
            _handle_undo(args, "json")

        assert exc_info.value.code == ExitCode.NO_FILES
        data = json.loads(capsys.readouterr().out)
        assert_error_result_schema(data)

    def test_json_success(self, tmp_path, capsys):
        # Create a renamed file and undo log
        renamed = tmp_path / "20240315 ACME ER.pdf"
        renamed.write_bytes(b"%PDF-1.4 test")
        original = str(tmp_path / "original.pdf")

        undo_log = tmp_path / ".autorename-log.json"
        undo_log.write_text(json.dumps({
            "version": 2,
            "batches": [{
                "batch_id": "20240315T120000-abc123",
                "timestamp": "2024-03-15T12:00:00",
                "undone": False,
                "files": [{
                    "old_path": original,
                    "new_path": str(renamed),
                    "timestamp": "2024-03-15T12:00:00",
                }]
            }]
        }))

        args = argparse.Namespace(directory=str(tmp_path), list_batches=False,
                                  batch=None, undo_all=False)
        with pytest.raises(SystemExit) as exc_info:
            _handle_undo(args, "json")

        assert exc_info.value.code == ExitCode.SUCCESS
        data = json.loads(capsys.readouterr().out)
        assert_undo_result_schema(data)
        assert data["restored"] >= 1

    def test_list_json(self, tmp_path, capsys):
        undo_log = tmp_path / ".autorename-log.json"
        undo_log.write_text(json.dumps({
            "version": 2,
            "batches": [{
                "batch_id": "20240315T120000-abc123",
                "timestamp": "2024-03-15T12:00:00",
                "undone": False,
                "files": [{"old_path": "a.pdf", "new_path": "b.pdf", "timestamp": "2024-03-15T12:00:00"}]
            }]
        }))

        args = argparse.Namespace(directory=str(tmp_path), list_batches=True,
                                  batch=None, undo_all=False)
        with pytest.raises(SystemExit) as exc_info:
            _handle_undo(args, "json")

        assert exc_info.value.code == ExitCode.SUCCESS
        data = json.loads(capsys.readouterr().out)
        assert_batch_list_schema(data)
        assert len(data["batches"]) == 1

    def test_undo_all(self, tmp_path, capsys):
        f1 = tmp_path / "20240315 ACME ER.pdf"
        f1.write_bytes(b"%PDF-1.4 test")
        f2 = tmp_path / "20240316 Globex AR.pdf"
        f2.write_bytes(b"%PDF-1.4 test")

        undo_log = tmp_path / ".autorename-log.json"
        undo_log.write_text(json.dumps({
            "version": 2,
            "batches": [
                {"batch_id": "20240315T120000-aaa111", "timestamp": "2024-03-15T12:00:00",
                 "undone": False, "files": [{"old_path": str(tmp_path / "orig1.pdf"),
                 "new_path": str(f1), "timestamp": "2024-03-15T12:00:00"}]},
                {"batch_id": "20240316T120000-bbb222", "timestamp": "2024-03-16T12:00:00",
                 "undone": False, "files": [{"old_path": str(tmp_path / "orig2.pdf"),
                 "new_path": str(f2), "timestamp": "2024-03-16T12:00:00"}]},
            ]
        }))

        args = argparse.Namespace(directory=str(tmp_path), list_batches=False,
                                  batch=None, undo_all=True)
        with pytest.raises(SystemExit) as exc_info:
            _handle_undo(args, "json")

        assert exc_info.value.code == ExitCode.SUCCESS
        data = json.loads(capsys.readouterr().out)
        assert_undo_result_schema(data)
        assert data["restored"] == 2


class TestMain:
    """Test main() entry point routing."""

    @patch("autorename_pdf._handle_rename")
    @patch("autorename_pdf.setup_logging")
    def test_routes_rename(self, mock_log, mock_handler):
        mock_handler.side_effect = SystemExit(0)
        with patch("sys.argv", ["prog", "rename", "file.pdf"]):
            with pytest.raises(SystemExit):
                _main()
        mock_handler.assert_called_once()

    @patch("autorename_pdf._handle_undo")
    @patch("autorename_pdf.setup_logging")
    def test_routes_undo(self, mock_log, mock_handler):
        mock_handler.side_effect = SystemExit(0)
        with patch("sys.argv", ["prog", "undo"]):
            with pytest.raises(SystemExit):
                _main()
        mock_handler.assert_called_once()

    @patch("autorename_pdf._handle_config")
    @patch("autorename_pdf.setup_logging")
    def test_routes_config(self, mock_log, mock_handler):
        mock_handler.side_effect = SystemExit(0)
        with patch("sys.argv", ["prog", "config", "show"]):
            with pytest.raises(SystemExit):
                _main()
        mock_handler.assert_called_once()

    @patch("autorename_pdf.setup_logging")
    def test_no_args_shows_help(self, mock_log, capsys):
        with patch("sys.argv", ["prog"]):
            with pytest.raises(SystemExit) as exc_info:
                _main()
        assert exc_info.value.code == ExitCode.USAGE_ERROR

    @patch("autorename_pdf._handle_undo")
    @patch("autorename_pdf.setup_logging")
    def test_legacy_undo_flag(self, mock_log, mock_handler):
        mock_handler.side_effect = SystemExit(0)
        with patch("sys.argv", ["prog", "--undo"]):
            with pytest.raises(SystemExit):
                _main()
        mock_handler.assert_called_once()


class TestGetBaseDirectory:
    """Test get_base_directory resolution."""

    def test_with_config_path(self):
        result = get_base_directory("/some/dir/config.yaml")
        assert result == os.path.dirname(os.path.abspath("/some/dir/config.yaml"))

    def test_dev_mode(self):
        result = get_base_directory(None)
        # In dev mode, returns directory of the script file
        assert os.path.isdir(result)

    def test_frozen_mode(self):
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", "/path/to/autorename-pdf.exe"):
                result = get_base_directory(None)
        assert result == "/path/to"
