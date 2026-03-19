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
        sample_config["ai"]["api_key"] = ""
        with pytest.raises(ValueError, match="API key required"):
            get_instructor_client(sample_config)

    def test_ollama_no_api_key_ok(self, sample_config):
        sample_config["ai"]["provider"] = "ollama"
        sample_config["ai"]["api_key"] = ""
        # Should not raise — ollama doesn't need an API key
        client = get_instructor_client(sample_config)
        assert client is not None

    @patch("_ai_processing.OpenAI")
    @patch("_ai_processing.instructor")
    def test_openai_client(self, mock_instructor, mock_openai, sample_config):
        mock_instructor.from_openai.return_value = MagicMock()
        mock_instructor.Mode.TOOLS = "TOOLS"
        client = get_instructor_client(sample_config)
        mock_openai.assert_called_once_with(api_key="test-key-123", base_url=None)
        mock_instructor.from_openai.assert_called_once_with(mock_openai.return_value, mode="TOOLS")

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
