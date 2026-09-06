"""Tests for v2 profile config loading."""
from _config_loader import load_yaml_config
from _profiles import select_profile

import pytest


@pytest.mark.parametrize("source", [
    pytest.param("config_version: 2\nprofile: business\nprofile: academic\n", id="top-level"),
    pytest.param("config_version: 2\nprofiles:\n  business: {}\n  business: {}\n", id="profile-id"),
    pytest.param("config_version: 2\nprofiles:\n  business:\n    fields:\n      description: {description: first}\n      description: {description: second}\n", id="field-id"),
    pytest.param("config_version: 2\nprofiles:\n  business:\n    fields:\n      description: {description: first, description: second}\n", id="field-spec"),
    pytest.param("config_version: 2\nai: {model: one, model: two}\n", id="existing-setting"),
])
def test_duplicate_yaml_keys_rejected(tmp_path, source):
    path = tmp_path / "test-config.yaml"
    path.write_text(source, encoding="utf-8")
    assert load_yaml_config(str(path)) is None
    assert path.read_text(encoding="utf-8") == source


def test_v2_defaults_and_env_before_profile_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_CITY", "Wien")
    path = tmp_path / "test-config.yaml"
    source = (
        "config_version: 2\ncompany: {name: ACME}\nprofiles:\n"
        "  business:\n    fields:\n"
        "      description: {description: '${PROFILE_CITY} {company}'}\n"
    )
    path.write_text(source, encoding="utf-8")
    config = load_yaml_config(str(path))
    assert config["config_version"] == 2
    assert config["profile"] == "business"
    assert select_profile(config)[1]["fields"]["description"]["description"] == "Wien ACME"
    assert path.read_text(encoding="utf-8") == source
    path.write_text("config_version: 2\n", encoding="utf-8")
    assert load_yaml_config(str(path))["profiles"] == {}
