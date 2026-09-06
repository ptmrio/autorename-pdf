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


from copy import deepcopy
from unittest.mock import MagicMock

import _ai_processing as ai
from PIL import Image
from _pdf_utils import ExtractionResult


def test_prompt_assembly_uses_resolved_schema_order_and_verbatim_extension(sample_config):
    sample_config["prompt_extension"] = "  EXTRA {untouched}\n "
    profile = {
        "intro": "INTRO",
        "fields": {
            "document_date": {"description": "DATE"},
            "title": {"description": "TITLE"},
        },
        "template": "{title}", "truncate_field": "title", "harmonize_field": None,
    }
    before = deepcopy(profile)
    expected = (
        "Extract the requested fields from the document content. Due to OCR text detection, "
        "the text may be noisy and contain spelling and detection errors. Handle those as well as possible."
        "\n\nINTRO\n\ndocument_date: DATE\n\ntitle: TITLE\n\n"
        "Return every requested field as a string. If a value is not found, return an empty string. "
        "Do not invent missing values or return undeclared fields.\n\n  EXTRA {untouched}\n "
    )
    assert ai.build_system_prompt(sample_config, profile) == expected
    assert profile == before
    assert list(build_metadata_model(profile).model_fields) == ["document_date", "title"]
    profile["intro"] = ""
    assert ai.build_system_prompt(sample_config, profile) == expected.replace("\n\nINTRO", "", 1)


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "xai", "ollama"])
@pytest.mark.parametrize("source", ["text", "images", "combined"])
def test_generated_model_reaches_provider(sample_config, monkeypatch, provider, source):
    sample_config["ai"].update(provider=provider, model="gpt-5.6-luna", temperature=0.7)
    profile = select_profile(sample_config, "academic")[1]
    model = build_metadata_model(profile)
    raw = {
        "document_date": "01.01.2026", "first_author_surname": "Smith",
        "journal_name": "", "title": "A Study",
    }
    parsed = model.model_validate(raw)
    client = MagicMock()
    client.responses.parse.return_value.output_parsed = parsed
    client.messages.parse.return_value.parsed_output = parsed
    client.chat.completions.create.return_value = parsed
    monkeypatch.setattr(ai, "_get_openai_client", lambda config: client)
    monkeypatch.setattr(ai, "_get_anthropic_client", lambda config: client)
    monkeypatch.setattr(ai, "get_instructor_client", lambda config: client)
    extraction = ExtractionResult(
        text="Printed text" if source != "images" else "",
        images=[Image.new("RGB", (2, 2))] if source != "text" else [],
        quality_score=1.0, page_count=1, sources=[source],
    )
    result = ai.extract_metadata(extraction, sample_config, profile=profile, metadata_model=model)
    assert result.model_dump() == raw
    if provider == "openai":
        call = client.responses.parse
        kwargs = call.call_args.kwargs
        assert kwargs["text_format"] is model
        assert kwargs["store"] is False
        assert kwargs["reasoning"] == {"effort": "none"}
        assert "temperature" not in kwargs
        assert "reasoning_effort" not in kwargs
        assert "messages" not in kwargs
        user_blocks = kwargs["input"][1]["content"]
        assert sum(block["type"] == "input_image" for block in user_blocks) == (source != "text")
        assert kwargs["input"][0]["content"][0]["text"] == ai.build_system_prompt(sample_config, profile)
        client.chat.completions.create.assert_not_called()
    elif provider == "anthropic":
        call = client.messages.parse
        kwargs = call.call_args.kwargs
        assert kwargs["output_format"] is model
        assert kwargs["max_tokens"] == 1024
        assert "temperature" not in kwargs
        assert "reasoning" not in kwargs
        assert "reasoning_effort" not in kwargs
        assert kwargs["system"] == ai.build_system_prompt(sample_config, profile)
        if source != "text":
            blocks = kwargs["messages"][0]["content"]
            assert sum(block["type"] == "image" for block in blocks) == 1
        client.chat.completions.create.assert_not_called()
    else:
        call = client.chat.completions.create
        kwargs = call.call_args.kwargs
        assert kwargs["response_model"] is model
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_retries"] == sample_config["ai"]["max_retries"]
        assert kwargs["messages"][0]["content"] == ai.build_system_prompt(sample_config, profile)
        if source != "text":
            blocks = kwargs["messages"][1]["content"]
            assert sum(block["type"] == "image_url" for block in blocks) == 1
        client.responses.parse.assert_not_called()
        client.messages.parse.assert_not_called()
    call.assert_called_once()
