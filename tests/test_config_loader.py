"""Tests for _config_loader.py."""

import os
import pytest
import yaml
import sys

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _config_loader import load_yaml_config, load_company_names, _detect_old_schema, _deep_merge, _migrate_extraction_config


class TestDeepMerge:
    def test_simple_merge(self):
        defaults = {"a": 1, "b": 2}
        overrides = {"b": 3, "c": 4}
        result = _deep_merge(defaults, overrides)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        defaults = {"ai": {"provider": "openai", "model": "gpt-4"}}
        overrides = {"ai": {"model": "gpt-5"}}
        result = _deep_merge(defaults, overrides)
        assert result["ai"]["provider"] == "openai"
        assert result["ai"]["model"] == "gpt-5"

    def test_override_non_dict_with_dict(self):
        defaults = {"a": "string"}
        overrides = {"a": {"nested": True}}
        result = _deep_merge(defaults, overrides)
        assert result["a"] == {"nested": True}


class TestDetectOldSchema:
    def test_detects_v1_schema(self):
        old_config = {"openai": {"api_key": "sk-xxx", "model": "gpt-4"}}
        assert _detect_old_schema(old_config) is True

    def test_allows_v2_schema(self):
        new_config = {"config_version": 2, "ai": {"provider": "openai"}}
        assert _detect_old_schema(new_config) is False

    def test_empty_config(self):
        assert _detect_old_schema({}) is False


class TestLoadYamlConfig:
    def test_load_valid_v2_config(self, tmp_path):
        config = {
            "config_version": 2,
            "ai": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "test"},
            "company": {"name": "My Corp"},
        }
        path = str(tmp_path / "config.yaml")
        with open(path, 'w') as f:
            yaml.dump(config, f)

        result = load_yaml_config(path)
        assert result is not None
        assert result["ai"]["provider"] == "anthropic"
        assert result["ai"]["model"] == "claude-sonnet-4-6"
        # Defaults should be applied
        assert result["pdf"]["max_pages"] == 3
        assert result["output"]["language"] == "English"

    def test_missing_file(self):
        result = load_yaml_config("/nonexistent/config.yaml")
        assert result is None

    def test_old_schema_exits(self, tmp_path):
        old_config = {"openai": {"api_key": "sk-xxx", "model": "gpt-4"}}
        path = str(tmp_path / "config.yaml")
        with open(path, 'w') as f:
            yaml.dump(old_config, f)

        with pytest.raises(SystemExit):
            load_yaml_config(path)

    def test_empty_file(self, tmp_path):
        path = str(tmp_path / "config.yaml")
        with open(path, 'w') as f:
            f.write("")

        result = load_yaml_config(path)
        assert result is None

    def test_defaults_applied(self, tmp_path):
        config = {"config_version": 2, "ai": {"provider": "openai", "api_key": "test"}}
        path = str(tmp_path / "config.yaml")
        with open(path, 'w') as f:
            yaml.dump(config, f)

        result = load_yaml_config(path)
        assert result["ai"]["temperature"] == 0.0
        assert result["ai"]["max_retries"] == 2
        assert result["pdf"]["text_quality_threshold"] == 0.3
        assert result["pdf"]["ocr"] is False
        assert result["pdf"]["vision"] is False
        assert result["paddleocr"]["languages"] == ["en"]

    def test_paddleocr_path_autodetect(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        config = {"config_version": 2, "ai": {"provider": "openai", "api_key": "test"}}
        path = str(tmp_path / "config.yaml")
        with open(path, 'w') as f:
            yaml.dump(config, f)

        # Reload module to pick up patched env var
        import importlib
        import _config_loader
        importlib.reload(_config_loader)
        result = _config_loader.load_yaml_config(path)
        expected = os.path.join(str(tmp_path), "autorename-pdf", "paddleocr-venv")
        assert result["paddleocr"]["venv_path"] == expected


class TestMigrateExtractionConfig:
    def test_no_old_keys_unchanged(self):
        config = {"pdf": {"ocr": True, "vision": False}}
        result = _migrate_extraction_config(config)
        assert result["pdf"]["ocr"] is True
        assert result["pdf"]["vision"] is False

    def test_auto_paddleocr(self):
        config = {"pdf": {"extraction_mode": "auto", "ocr_fallback": "paddleocr"}}
        result = _migrate_extraction_config(config)
        assert result["pdf"]["ocr"] == "auto"
        assert result["pdf"]["vision"] is False
        assert "extraction_mode" not in result["pdf"]
        assert "ocr_fallback" not in result["pdf"]

    def test_auto_vision(self):
        config = {"pdf": {"extraction_mode": "auto", "ocr_fallback": "vision"}}
        result = _migrate_extraction_config(config)
        assert result["pdf"]["ocr"] is False
        assert result["pdf"]["vision"] == "auto"

    def test_auto_none(self):
        config = {"pdf": {"extraction_mode": "auto", "ocr_fallback": "none"}}
        result = _migrate_extraction_config(config)
        assert result["pdf"]["ocr"] is False
        assert result["pdf"]["vision"] is False

    def test_text_only(self):
        config = {"pdf": {"extraction_mode": "text_only"}}
        result = _migrate_extraction_config(config)
        assert result["pdf"]["ocr"] is False
        assert result["pdf"]["vision"] is False

    def test_vision_only(self):
        config = {"pdf": {"extraction_mode": "vision_only"}}
        result = _migrate_extraction_config(config)
        assert result["pdf"]["ocr"] is False
        assert result["pdf"]["vision"] is True

    def test_migration_in_load(self, tmp_path):
        """Old config keys are migrated when loading a YAML file."""
        config = {
            "config_version": 2,
            "ai": {"provider": "openai", "api_key": "test"},
            "pdf": {"extraction_mode": "auto", "ocr_fallback": "vision"},
        }
        path = str(tmp_path / "config.yaml")
        with open(path, 'w') as f:
            yaml.dump(config, f)

        result = load_yaml_config(path)
        assert result["pdf"]["vision"] == "auto"
        assert result["pdf"]["ocr"] is False
        assert "extraction_mode" not in result["pdf"]


class TestLoadCompanyNames:
    def test_load_valid_file(self, harmonized_names_file):
        result = load_company_names(harmonized_names_file)
        assert "ACME" in result
        assert "Globex" in result
        assert "ACME Corporation" in result["ACME"]

    def test_missing_file(self):
        result = load_company_names("/nonexistent/names.yaml")
        assert result == {}

    def test_empty_file(self, tmp_path):
        path = str(tmp_path / "names.yaml")
        with open(path, 'w') as f:
            f.write("")
        result = load_company_names(path)
        assert result == {}
