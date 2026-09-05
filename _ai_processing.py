"""
AI content processing with multi-provider support.
OpenAI and Anthropic use native structured parse; Gemini, xAI, and Ollama use instructor.
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


def build_image_content(images: list, provider: str) -> list[dict]:
    """Build image content blocks in the format expected by the provider."""
    if provider == "anthropic":
        result = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            result.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            })
        return result
    return [
        {"type": "image_url", "image_url": {"url": pil_to_base64_data_uri(img)}}
        for img in images
    ]


def build_provider_create_kwargs(provider: str, config: dict) -> dict:
    ai = config["ai"]
    if provider == "anthropic":
        return {"max_tokens": 1024}
    if provider == "openai":
        return {"reasoning": {"effort": "none"}}
    return {"temperature": ai.get("temperature", 0.0)}


def _get_openai_client(config: dict):
    """Create a native OpenAI client (not wrapped with instructor)."""
    api_key = config["ai"].get("api_key", "")
    if not api_key:
        raise ValueError("API key required for provider 'openai'. Set ai.api_key in config.yaml.")
    custom_base_url = config["ai"].get("base_url", "")
    return OpenAI(api_key=api_key, base_url=custom_base_url or None)


def _get_anthropic_client(config: dict):
    """Create a native Anthropic client (not wrapped with instructor)."""
    from anthropic import Anthropic
    api_key = config["ai"].get("api_key", "")
    if not api_key:
        raise ValueError("API key required for provider 'anthropic'. Set ai.api_key in config.yaml.")
    return Anthropic(api_key=api_key)


def _openai_input_text_block(text: str) -> dict:
    return {"type": "input_text", "text": text}


def _openai_input_image_blocks(images: list) -> list[dict]:
    return [
        {"type": "input_image", "image_url": pil_to_base64_data_uri(img)}
        for img in images
    ]


def _extract_openai_native(config: dict, user_content: list) -> DocumentMetadata:
    client = _get_openai_client(config)
    response = client.responses.parse(
        model=config["ai"]["model"],
        input=[
            {"role": "system", "content": [_openai_input_text_block(build_system_prompt(config))]},
            {"role": "user", "content": user_content},
        ],
        text_format=DocumentMetadata,
        store=False,
        **build_provider_create_kwargs("openai", config),
    )
    return response.output_parsed


def _extract_anthropic_native(config: dict, user_content) -> DocumentMetadata:
    client = _get_anthropic_client(config)
    response = client.messages.parse(
        model=config["ai"]["model"],
        system=build_system_prompt(config),
        messages=[{"role": "user", "content": user_content}],
        output_format=DocumentMetadata,
        **build_provider_create_kwargs("anthropic", config),
    )
    return response.parsed_output


def extract_metadata_from_text(text: str, config: dict) -> DocumentMetadata:
    """Extract document metadata from text using an LLM."""
    provider = config["ai"]["provider"]
    user_text = f"Extract the information from this text:\n\n{text}"
    if provider == "openai":
        return _extract_openai_native(config, [_openai_input_text_block(user_text)])
    if provider == "anthropic":
        return _extract_anthropic_native(config, user_text)

    client = get_instructor_client(config)

    kwargs = build_provider_create_kwargs(provider, config)
    kwargs.update({
        "model": config["ai"]["model"],
        "response_model": DocumentMetadata,
        "max_retries": config["ai"].get("max_retries", 2),
        "messages": [
            {"role": "system", "content": build_system_prompt(config)},
            {"role": "user", "content": user_text}
        ],
    })

    return client.chat.completions.create(**kwargs)


def extract_metadata_from_images(images: list, config: dict) -> DocumentMetadata:
    """Extract document metadata from page images using a vision-capable LLM."""
    provider = config["ai"]["provider"]
    if provider == "openai":
        return _extract_openai_native(config, [
            _openai_input_text_block("Extract document metadata from these page images:"),
            *_openai_input_image_blocks(images),
        ])
    if provider == "anthropic":
        image_content = build_image_content(images, "anthropic")
        return _extract_anthropic_native(config, [
            {"type": "text", "text": "Extract document metadata from these page images:"},
            *image_content,
        ])

    client = get_instructor_client(config)
    image_content = build_image_content(images, provider)

    kwargs = build_provider_create_kwargs(provider, config)
    kwargs.update({
        "model": config["ai"]["model"],
        "response_model": DocumentMetadata,
        "max_retries": config["ai"].get("max_retries", 2),
        "messages": [
            {"role": "system", "content": build_system_prompt(config)},
            {"role": "user", "content": [
                {"type": "text", "text": "Extract document metadata from these page images:"},
                *image_content
            ]}
        ],
    })

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
    provider = config["ai"]["provider"]
    user_text = f"Extract document metadata from this text and images:\n\n{text}"
    if provider == "openai":
        return _extract_openai_native(config, [
            _openai_input_text_block(user_text),
            *_openai_input_image_blocks(images),
        ])
    if provider == "anthropic":
        image_content = build_image_content(images, "anthropic")
        return _extract_anthropic_native(config, [
            {"type": "text", "text": user_text},
            *image_content,
        ])

    client = get_instructor_client(config)
    image_content = build_image_content(images, provider)

    kwargs = build_provider_create_kwargs(provider, config)
    kwargs.update({
        "model": config["ai"]["model"],
        "response_model": DocumentMetadata,
        "max_retries": config["ai"].get("max_retries", 2),
        "messages": [
            {"role": "system", "content": build_system_prompt(config)},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                *image_content,
            ]},
        ],
    })

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
