"""
AI content processing with multi-provider support via instructor.
Supports OpenAI, Anthropic (native), Gemini, xAI, and Ollama.
"""
from __future__ import annotations

import base64
import io
import logging

from pydantic import BaseModel, Field
from PIL import Image
import instructor
from openai import OpenAI

from _pdf_utils import ExtractionResult


PROVIDER_BASE_URLS = {
    "openai": None,
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "xai": "https://api.x.ai/v1",
    "ollama": "http://localhost:11434/v1",
}


class DocumentMetadata(BaseModel):
    """Structured output model for document metadata extraction."""
    company_name: str = Field(
        description="Counterparty company name, stripped of legal form (GmbH, AG, Ltd, e.U., SARL, etc.)"
    )
    document_date: str = Field(
        description="Most relevant date (invoice date, letter date) in dd.mm.YYYY format"
    )
    document_type: str = Field(
        description="ER for incoming invoice, AR for outgoing invoice, or short descriptive type"
    )


def get_instructor_client(config: dict):
    """Create an instructor-wrapped client for structured LLM output.

    Most providers route through the OpenAI SDK via compatible endpoints.
    Anthropic uses its native SDK (their OpenAI compat ignores structured output).
    """
    provider = config["ai"]["provider"]
    api_key = config["ai"].get("api_key", "")
    custom_base_url = config["ai"].get("base_url", "")

    supported = list(PROVIDER_BASE_URLS.keys()) + ["anthropic"]
    if provider not in supported:
        raise ValueError(f"Unknown provider: {provider}. Supported: {', '.join(supported)}")
    if provider != "ollama" and not api_key:
        raise ValueError(f"API key required for provider '{provider}'. Set ai.api_key in config.yaml.")

    # Anthropic: use native SDK
    if provider == "anthropic":
        from anthropic import Anthropic
        raw = Anthropic(api_key=api_key)
        return instructor.from_anthropic(raw)

    # All others: OpenAI SDK with provider-specific base_url
    base_url = custom_base_url or PROVIDER_BASE_URLS.get(provider)
    if provider == "ollama":
        api_key = api_key or "ollama"

    raw = OpenAI(api_key=api_key, base_url=base_url)
    # Ollama: use JSON mode for broadest model compatibility (TOOLS requires function calling support)
    mode = instructor.Mode.JSON if provider == "ollama" else instructor.Mode.TOOLS
    return instructor.from_openai(raw, mode=mode)


def build_system_prompt(config: dict) -> str:
    """Build the extraction prompt from config values."""
    company = config.get("company", {}).get("name", "")
    lang = config.get("output", {}).get("language", "English")
    er = config.get("pdf", {}).get("incoming_invoice", "ER")
    ar = config.get("pdf", {}).get("outgoing_invoice", "AR")
    ext = config.get("prompt_extension", "")

    prompt = (
        "You will extract the company name, document date, and document type "
        "from the following document content. "
        "Due to the nature of OCR text detection, the text may be noisy and contain "
        "spelling and detection errors. Handle those as well as possible.\n\n"
        "document_date: Find the most appropriate date (e.g. the invoice date) and "
        "assume the correct date format according to the language and location of the document. "
        "Return format must be: dd.mm.YYYY\n\n"
    )

    if company:
        prompt += (
            f'company_name: Find the name of the company that is the corresponding party '
            f'of the document. My company name is: "{company}", avoid using my company name '
            f'as company_name in the response. For the company_name you always strip the '
            f'legal form (e.U., SARL, GmbH, AG, Ltd, Limited, etc.)\n\n'
        )
    else:
        prompt += (
            "company_name: Find the name of the main company in the document. "
            "Strip the legal form (e.U., SARL, GmbH, AG, Ltd, Limited, etc.)\n\n"
        )

    prompt += (
        f"document_type: Find the best matching type of the document. Valid document types are: "
        f"For incoming invoices (invoices my company receives) use the term '{er}' only, nothing more. "
        f"For outgoing invoices (invoices my company sends) use the term '{ar}', nothing more. "
        f"For all other document types, always find a short descriptive summary/subject in {lang} language.\n\n"
        "If a value is not found, leave it empty."
    )

    if ext:
        prompt += f"\n\n{ext}"

    return prompt.strip()


def pil_to_base64_data_uri(image: Image.Image, fmt: str = "PNG") -> str:
    """Convert a PIL image to a base64 data URI."""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/{fmt.lower()};base64,{b64}"


def extract_metadata_from_text(text: str, config: dict) -> DocumentMetadata:
    """Extract document metadata from text using an LLM."""
    client = get_instructor_client(config)
    provider = config["ai"]["provider"]

    kwargs = {
        "model": config["ai"]["model"],
        "response_model": DocumentMetadata,
        "max_retries": config["ai"].get("max_retries", 2),
        "temperature": config["ai"].get("temperature", 0.0),
        "messages": [
            {"role": "system", "content": build_system_prompt(config)},
            {"role": "user", "content": f"Extract the information from this text:\n\n{text}"}
        ],
    }

    # Anthropic uses max_tokens instead of being optional
    if provider == "anthropic":
        kwargs["max_tokens"] = 1024

    return client.chat.completions.create(**kwargs)


def extract_metadata_from_images(images: list, config: dict) -> DocumentMetadata:
    """Extract document metadata from page images using a vision-capable LLM."""
    client = get_instructor_client(config)
    provider = config["ai"]["provider"]

    image_content = [
        {"type": "image_url", "image_url": {"url": pil_to_base64_data_uri(img)}}
        for img in images
    ]

    kwargs = {
        "model": config["ai"]["model"],
        "response_model": DocumentMetadata,
        "max_retries": config["ai"].get("max_retries", 2),
        "temperature": config["ai"].get("temperature", 0.0),
        "messages": [
            {"role": "system", "content": build_system_prompt(config)},
            {"role": "user", "content": [
                {"type": "text", "text": "Extract document metadata from these page images:"},
                *image_content
            ]}
        ],
    }

    if provider == "anthropic":
        kwargs["max_tokens"] = 1024

    return client.chat.completions.create(**kwargs)


def _build_combined_text(extraction: ExtractionResult) -> str:
    """Merge pdfplumber text and OCR text into a single string for the AI."""
    parts = []
    if extraction.text.strip():
        parts.append(extraction.text)
    if extraction.ocr_text.strip():
        if parts:
            parts.append("\n--- OCR Text ---\n")
        parts.append(extraction.ocr_text)
    return "\n".join(parts)


def extract_metadata_from_text_and_images(
    text: str, images: list, config: dict
) -> DocumentMetadata:
    """Extract metadata from combined text + page images (multimodal)."""
    client = get_instructor_client(config)
    provider = config["ai"]["provider"]

    image_content = [
        {"type": "image_url", "image_url": {"url": pil_to_base64_data_uri(img)}}
        for img in images
    ]

    kwargs = {
        "model": config["ai"]["model"],
        "response_model": DocumentMetadata,
        "max_retries": config["ai"].get("max_retries", 2),
        "temperature": config["ai"].get("temperature", 0.0),
        "messages": [
            {"role": "system", "content": build_system_prompt(config)},
            {"role": "user", "content": [
                {"type": "text", "text": f"Extract document metadata from this text and images:\n\n{text}"},
                *image_content,
            ]},
        ],
    }

    if provider == "anthropic":
        kwargs["max_tokens"] = 1024

    return client.chat.completions.create(**kwargs)


def extract_metadata(extraction: ExtractionResult, config: dict) -> DocumentMetadata | None:
    """Extract metadata from an ExtractionResult using the appropriate method."""
    combined_text = _build_combined_text(extraction)
    has_text = bool(combined_text.strip())
    has_images = bool(extraction.images)

    if has_text and has_images:
        return extract_metadata_from_text_and_images(combined_text, extraction.images, config)
    elif has_images:
        return extract_metadata_from_images(extraction.images, config)
    elif has_text:
        return extract_metadata_from_text(combined_text, config)
    else:
        logging.error("No text or images available for metadata extraction")
        return None
