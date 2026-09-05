"""Tests for _ai_processing.py."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _ai_processing import (
    DocumentMetadata,
    build_system_prompt,
    pil_to_base64_data_uri,
    get_instructor_client,
    extract_metadata,
    _build_combined_text,
)
from _pdf_utils import ExtractionResult


class TestDocumentMetadata:
    def test_valid_metadata(self):
        m = DocumentMetadata(
            company_name="ACME",
            document_date="15.03.2024",
            document_type="ER"
        )
        assert m.company_name == "ACME"
        assert m.document_date == "15.03.2024"
        assert m.document_type == "ER"

    def test_empty_values(self):
        m = DocumentMetadata(
            company_name="",
            document_date="",
            document_type=""
        )
        assert m.company_name == ""


class TestBuildSystemPrompt:
    def test_contains_company_name(self, sample_config):
        prompt = build_system_prompt(sample_config)
        assert "Test Company" in prompt

    def test_contains_invoice_codes(self, sample_config):
        prompt = build_system_prompt(sample_config)
        assert "ER" in prompt
        assert "AR" in prompt

    def test_contains_language(self, sample_config):
        prompt = build_system_prompt(sample_config)
        assert "English" in prompt

    def test_custom_invoice_codes(self, sample_config):
        sample_config["pdf"]["incoming_invoice"] = "EIN"
        sample_config["pdf"]["outgoing_invoice"] = "AUS"
        prompt = build_system_prompt(sample_config)
        assert "EIN" in prompt
        assert "AUS" in prompt

    def test_prompt_extension(self, sample_config):
        sample_config["prompt_extension"] = "Also check for VAT numbers."
        prompt = build_system_prompt(sample_config)
        assert "Also check for VAT numbers." in prompt

    def test_no_company_name(self, sample_config):
        sample_config["company"]["name"] = ""
        prompt = build_system_prompt(sample_config)
        assert "main company" in prompt


class TestPilToBase64DataUri:
    def test_png_format(self, sample_pil_image):
        uri = pil_to_base64_data_uri(sample_pil_image, fmt="PNG")
        assert uri.startswith("data:image/png;base64,")

    def test_jpeg_format(self, sample_pil_image):
        uri = pil_to_base64_data_uri(sample_pil_image, fmt="JPEG")
        assert uri.startswith("data:image/jpeg;base64,")

    def test_non_empty_base64(self, sample_pil_image):
        uri = pil_to_base64_data_uri(sample_pil_image)
        base64_part = uri.split(",")[1]
        assert len(base64_part) > 0


class TestGetInstructorClient:
    def test_unknown_provider_raises(self, sample_config):
        sample_config["ai"]["provider"] = "unknown_provider"
        with pytest.raises(ValueError, match="Unknown provider"):
            get_instructor_client(sample_config)

    def test_missing_api_key_raises(self, sample_config):
        sample_config["ai"]["provider"] = "gemini"
        sample_config["ai"]["api_key"] = ""
        with pytest.raises(ValueError, match="API key required"):
            get_instructor_client(sample_config)

    def test_ollama_no_api_key_ok(self, sample_config):
        sample_config["ai"]["provider"] = "ollama"
        sample_config["ai"]["api_key"] = ""
        # Should not raise — ollama doesn't need an API key
        client = get_instructor_client(sample_config)
        assert client is not None

    def test_openai_client(self, sample_config):
        sample_config["ai"]["provider"] = "openai"
        with pytest.raises(ValueError, match="Unknown provider"):
            get_instructor_client(sample_config)

    def test_anthropic_client_raises(self, sample_config):
        sample_config["ai"]["provider"] = "anthropic"
        with pytest.raises(ValueError, match="Unknown provider"):
            get_instructor_client(sample_config)

    @patch("_ai_processing.OpenAI")
    @patch("_ai_processing.instructor")
    def test_ollama_uses_json_mode(self, mock_instructor, mock_openai, sample_config):
        """Ollama must use JSON mode for broadest model compatibility."""
        mock_instructor.from_openai.return_value = MagicMock()
        mock_instructor.Mode.JSON = "JSON"
        sample_config["ai"]["provider"] = "ollama"
        sample_config["ai"]["api_key"] = ""
        get_instructor_client(sample_config)
        mock_instructor.from_openai.assert_called_once_with(mock_openai.return_value, mode="JSON")

    @patch("_ai_processing.OpenAI")
    @patch("_ai_processing.instructor")
    def test_gemini_client_uses_base_url(self, mock_instructor, mock_openai, sample_config):
        mock_instructor.from_openai.return_value = MagicMock()
        sample_config["ai"]["provider"] = "gemini"
        get_instructor_client(sample_config)
        call_args = mock_openai.call_args
        assert "generativelanguage.googleapis.com" in call_args.kwargs["base_url"]


class TestExtractMetadataProviderKwargs:
    """Instructor-shaped kwargs for compat providers (gemini/xai/ollama)."""

    @patch("_ai_processing.get_instructor_client")
    @patch("_ai_processing.build_system_prompt", return_value="test prompt")
    def test_compat_provider_includes_temperature(self, mock_prompt, mock_client, sample_config):
        """Gemini/xAI/Ollama instructor calls keep temperature and omit native kwargs."""
        sample_config["ai"]["provider"] = "gemini"
        mock_completions = MagicMock()
        mock_completions.create.return_value = DocumentMetadata(
            company_name="Test", document_date="01.01.2024", document_type="ER"
        )
        mock_client.return_value = MagicMock(chat=MagicMock(completions=mock_completions))

        from _ai_processing import extract_metadata_from_text
        extract_metadata_from_text("test text", sample_config)

        call_kwargs = mock_completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.0
        assert "max_tokens" not in call_kwargs
        assert "reasoning" not in call_kwargs

    @patch("_ai_processing.get_instructor_client")
    @patch("_ai_processing.build_system_prompt", return_value="test prompt")
    def test_vision_extraction_kwargs(self, mock_prompt, mock_client, sample_config):
        """Vision extraction sends image_url content blocks for compat providers."""
        from PIL import Image
        sample_config["ai"]["provider"] = "gemini"
        mock_completions = MagicMock()
        mock_completions.create.return_value = DocumentMetadata(
            company_name="Test", document_date="01.01.2024", document_type="ER"
        )
        mock_client.return_value = MagicMock(chat=MagicMock(completions=mock_completions))

        from _ai_processing import extract_metadata_from_images
        images = [Image.new("RGB", (100, 100))]
        extract_metadata_from_images(images, sample_config)

        call_kwargs = mock_completions.create.call_args[1]
        messages = call_kwargs["messages"]
        user_msg = messages[1]
        assert user_msg["role"] == "user"
        # Content should be a list with text + image_url blocks
        assert isinstance(user_msg["content"], list)
        image_blocks = [c for c in user_msg["content"] if c.get("type") == "image_url"]
        assert len(image_blocks) == 1


class TestBuildCombinedText:
    def test_text_only(self):
        extraction = ExtractionResult(text="Hello", ocr_text="", sources=["text"])
        assert _build_combined_text(extraction) == "Hello"

    def test_ocr_only(self):
        extraction = ExtractionResult(text="", ocr_text="OCR text", sources=["text", "ocr"])
        assert "OCR text" in _build_combined_text(extraction)

    def test_text_and_ocr(self):
        extraction = ExtractionResult(text="Text", ocr_text="OCR", sources=["text", "ocr"])
        combined = _build_combined_text(extraction)
        assert "Text" in combined
        assert "OCR" in combined
        assert "--- OCR Text ---" in combined

    def test_both_empty(self):
        extraction = ExtractionResult(text="", ocr_text="", sources=["text"])
        assert _build_combined_text(extraction) == ""


class TestExtractMetadata:
    def test_no_content_returns_none(self, sample_config):
        extraction = ExtractionResult(text="", images=[], quality_score=0.0, page_count=0, sources=["text"])
        result = extract_metadata(extraction, sample_config)
        assert result is None

    @patch("_ai_processing.extract_metadata_from_text")
    def test_text_extraction(self, mock_extract, sample_config):
        mock_extract.return_value = DocumentMetadata(
            company_name="ACME", document_date="15.03.2024", document_type="ER"
        )
        extraction = ExtractionResult(
            text="Invoice from ACME", images=[], quality_score=0.8,
            page_count=1, sources=["text"]
        )
        result = extract_metadata(extraction, sample_config)
        assert result.company_name == "ACME"
        mock_extract.assert_called_once()

    @patch("_ai_processing.extract_metadata_from_images")
    def test_vision_extraction(self, mock_extract, sample_config):
        mock_extract.return_value = DocumentMetadata(
            company_name="Globex", document_date="01.01.2024", document_type="AR"
        )
        img = Image.new("RGB", (100, 100))
        extraction = ExtractionResult(
            text="", images=[img], quality_score=0.0,
            page_count=1, sources=["text", "vision"]
        )
        result = extract_metadata(extraction, sample_config)
        assert result.company_name == "Globex"
        mock_extract.assert_called_once()

    @patch("_ai_processing.extract_metadata_from_text_and_images")
    def test_mixed_text_and_images(self, mock_extract, sample_config):
        mock_extract.return_value = DocumentMetadata(
            company_name="Mixed", document_date="01.01.2024", document_type="ER"
        )
        img = Image.new("RGB", (100, 100))
        extraction = ExtractionResult(
            text="Some text", images=[img], quality_score=0.5,
            page_count=1, sources=["text", "vision"]
        )
        result = extract_metadata(extraction, sample_config)
        assert result.company_name == "Mixed"
        mock_extract.assert_called_once()


from _ai_processing import build_provider_create_kwargs


class TestBuildProviderCreateKwargs:
    def test_anthropic_omits_temperature_and_sets_max_tokens(self, sample_config):
        sample_config["ai"]["provider"] = "anthropic"
        sample_config["ai"]["temperature"] = 0.0
        kwargs = build_provider_create_kwargs("anthropic", sample_config)
        assert "temperature" not in kwargs
        assert kwargs["max_tokens"] == 1024

    def test_openai_sets_reasoning_none_and_omits_temperature(self, sample_config):
        sample_config["ai"]["provider"] = "openai"
        sample_config["ai"]["model"] = "gpt-5.6-luna"
        kwargs = build_provider_create_kwargs("openai", sample_config)
        assert kwargs["reasoning"] == {"effort": "none"}
        assert "temperature" not in kwargs

    def test_compat_provider_keeps_temperature(self, sample_config):
        sample_config["ai"]["provider"] = "ollama"
        sample_config["ai"]["temperature"] = 0.2
        kwargs = build_provider_create_kwargs("ollama", sample_config)
        assert kwargs["temperature"] == 0.2
        assert "max_tokens" not in kwargs
        assert "reasoning" not in kwargs


class TestNativeStructuredExtract:
    def test_openai_text_uses_responses_parse(self, sample_config):
        sample_config["ai"]["provider"] = "openai"
        sample_config["ai"]["model"] = "gpt-5.6-luna"
        parsed = DocumentMetadata(company_name="ACME", document_date="15.03.2024", document_type="ER")
        mock_resp = MagicMock(output_parsed=parsed)
        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_resp
        with patch("_ai_processing._get_openai_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_text
            result = extract_metadata_from_text("invoice text", sample_config)
        assert result.company_name == "ACME"
        kwargs = mock_client.responses.parse.call_args.kwargs
        assert kwargs["text_format"] is DocumentMetadata
        assert kwargs["store"] is False
        assert kwargs["reasoning"] == {"effort": "none"}
        assert "temperature" not in kwargs
        mock_client.chat.completions.create.assert_not_called()

    def test_anthropic_text_uses_messages_parse(self, sample_config):
        sample_config["ai"]["provider"] = "anthropic"
        parsed = DocumentMetadata(company_name="GmbH", document_date="01.01.2024", document_type="ER")
        mock_resp = MagicMock(parsed_output=parsed)
        mock_client = MagicMock()
        mock_client.messages.parse.return_value = mock_resp
        with patch("_ai_processing._get_anthropic_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_text
            result = extract_metadata_from_text("rechnung", sample_config)
        assert result.company_name == "GmbH"
        kwargs = mock_client.messages.parse.call_args.kwargs
        assert kwargs["output_format"] is DocumentMetadata
        assert kwargs["max_tokens"] == 1024
        assert "temperature" not in kwargs

    def test_openai_vision_puts_images_in_input(self, sample_config, sample_pil_image):
        sample_config["ai"]["provider"] = "openai"
        sample_config["ai"]["model"] = "gpt-5.6-luna"
        parsed = DocumentMetadata(company_name="ACME", document_date="15.03.2024", document_type="ER")
        mock_resp = MagicMock(output_parsed=parsed)
        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_resp
        with patch("_ai_processing._get_openai_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_images
            result = extract_metadata_from_images([sample_pil_image], sample_config)
        assert result.company_name == "ACME"
        kwargs = mock_client.responses.parse.call_args.kwargs
        assert "input" in kwargs
        assert "messages" not in kwargs
        contents = []
        for item in kwargs["input"]:
            contents.extend(item.get("content", []) if isinstance(item.get("content"), list) else [])
        assert any(c.get("type") == "input_image" for c in contents)
        assert not any(c.get("type") == "image_url" for c in contents)
        mock_client.chat.completions.create.assert_not_called()

    def test_anthropic_vision_keeps_image_blocks_in_messages(self, sample_config, sample_pil_image):
        sample_config["ai"]["provider"] = "anthropic"
        parsed = DocumentMetadata(company_name="GmbH", document_date="01.01.2024", document_type="ER")
        mock_resp = MagicMock(parsed_output=parsed)
        mock_client = MagicMock()
        mock_client.messages.parse.return_value = mock_resp
        with patch("_ai_processing._get_anthropic_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_images
            result = extract_metadata_from_images([sample_pil_image], sample_config)
        assert result.company_name == "GmbH"
        kwargs = mock_client.messages.parse.call_args.kwargs
        assert kwargs["output_format"] is DocumentMetadata
        user_content = kwargs["messages"][0]["content"]
        assert isinstance(user_content, list)
        image_blocks = [c for c in user_content if c.get("type") == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0]["source"]["type"] == "base64"
        mock_client.chat.completions.create.assert_not_called()

    def test_openai_text_and_images_uses_responses_parse(self, sample_config, sample_pil_image):
        sample_config["ai"]["provider"] = "openai"
        parsed = DocumentMetadata(company_name="ACME", document_date="15.03.2024", document_type="ER")
        mock_resp = MagicMock(output_parsed=parsed)
        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_resp
        with patch("_ai_processing._get_openai_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_text_and_images
            result = extract_metadata_from_text_and_images("invoice text", [sample_pil_image], sample_config)
        assert result.company_name == "ACME"
        kwargs = mock_client.responses.parse.call_args.kwargs
        assert kwargs["text_format"] is DocumentMetadata
        assert "input" in kwargs
        mock_client.chat.completions.create.assert_not_called()

    def test_anthropic_text_and_images_uses_messages_parse(self, sample_config, sample_pil_image):
        sample_config["ai"]["provider"] = "anthropic"
        parsed = DocumentMetadata(company_name="GmbH", document_date="01.01.2024", document_type="ER")
        mock_resp = MagicMock(parsed_output=parsed)
        mock_client = MagicMock()
        mock_client.messages.parse.return_value = mock_resp
        with patch("_ai_processing._get_anthropic_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_text_and_images
            result = extract_metadata_from_text_and_images("rechnung", [sample_pil_image], sample_config)
        assert result.company_name == "GmbH"
        kwargs = mock_client.messages.parse.call_args.kwargs
        assert kwargs["output_format"] is DocumentMetadata
        user_content = kwargs["messages"][0]["content"]
        assert any(c.get("type") == "image" for c in user_content)
        mock_client.chat.completions.create.assert_not_called()
