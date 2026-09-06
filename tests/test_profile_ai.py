"""Tests for generated extraction models."""
import pytest
from pydantic import ValidationError

from _profiles import build_metadata_model, select_profile


def test_generated_model_has_required_named_strings_and_descriptions(sample_config):
    profile = select_profile(sample_config, "academic")[1]
    model = build_metadata_model(profile)
    schema = model.model_json_schema()
    assert list(schema["properties"]) == list(profile["fields"])
    assert schema["required"] == list(profile["fields"])
    assert schema["additionalProperties"] is False
    for name, field in profile["fields"].items():
        assert schema["properties"][name]["type"] == "string"
        assert schema["properties"][name]["description"] == field["description"]
        assert "default" not in schema["properties"][name]
    raw = dict.fromkeys(profile["fields"], "")
    assert model.model_validate(raw).model_dump() == raw


@pytest.mark.parametrize("change", ["missing", "null", "number", "boolean", "list", "bytes", "extra"])
def test_generated_model_rejects_invalid_output(sample_config, change):
    profile = select_profile(sample_config)[1]
    model = build_metadata_model(profile)
    raw = dict.fromkeys(profile["fields"], "")
    if change == "missing":
        del raw["description"]
    elif change == "extra":
        raw["invoice_id"] = "12345"
    else:
        raw["description"] = {
            "null": None, "number": 12, "boolean": True, "list": [], "bytes": b"text",
        }[change]
    with pytest.raises(ValidationError):
        model.model_validate(raw)
