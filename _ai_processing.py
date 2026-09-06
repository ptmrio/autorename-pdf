"""
AI content processing with multi-provider support.
OpenAI and Anthropic use native structured parse; Gemini, xAI, and Ollama use instructor.
"""
from __future__ import annotations

import base64
import io
import logging

from pydantic import BaseModel
from PIL import Image
import instructor
from openai import OpenAI

from _pdf_utils import ExtractionResult


PROVIDER_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "xai": "https://api.x.ai/v1",
    "ollama": "http://localhost:11434/v1",
}


def get_instructor_client(config: dict):
    """Create an instructor-wrapped client for Gemini, xAI, or Ollama."""
    provider = config["ai"]["provider"]
    api_key = config["ai"].get("api_key", "")
    custom_base_url = config["ai"].get("base_url", "")

    supported = list(PROVIDER_BASE_URLS.keys())
    if provider not in supported:
        raise ValueError(f"Unknown provider: {provider}. Supported: {', '.join(supported)}")
    if provider != "ollama" and not api_key:
        raise ValueError(f"API key required for provider '{provider}'. Set ai.api_key in config.yaml.")

    base_url = custom_base_url or PROVIDER_BASE_URLS.get(provider)
    if provider == "ollama":
        api_key = api_key or "ollama"

    raw = OpenAI(api_key=api_key, base_url=base_url)
    # Ollama: use JSON mode for broadest model compatibility (TOOLS requires function calling support)
    mode = instructor.Mode.JSON if provider == "ollama" else instructor.Mode.TOOLS
    return instructor.from_openai(raw, mode=mode)


def build_system_prompt(config: dict, profile: dict) -> str:
    """Assemble the extraction prompt from a resolved profile. Does not interpolate."""
    parts = [
        "Extract the requested fields from the document content. Due to OCR text detection, "
        "the text may be noisy and contain spelling and detection errors. Handle those as well as possible."
    ]
    intro = profile.get("intro") or ""
    if intro:
        parts.append(intro)
    parts.append("\n\n".join(
        f"{name}: {spec['description']}"
        for name, spec in profile["fields"].items()
    ))
    parts.append(
        "Return every requested field as a string. If a value is not found, return an empty string. "
        "Do not invent missing values or return undeclared fields."
    )
    prompt = "\n\n".join(parts)
    ext = config.get("prompt_extension") or ""
    if ext:
        prompt += f"\n\n{ext}"
    return prompt


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


def _openai_supports_reasoning_none(model: str) -> bool:
    name = (model or "").lower()
    return "luna" in name or name.startswith("gpt-5.6")


def build_provider_create_kwargs(provider: str, config: dict) -> dict:
    ai = config["ai"]
    if provider == "anthropic":
        return {"max_tokens": 1024}
    if provider == "openai":
        if _openai_supports_reasoning_none(str(ai.get("model", ""))):
            return {"reasoning": {"effort": "none"}}
        return {}
    return {"temperature": ai.get("temperature", 0.0)}


def _get_openai_client(config: dict):
    """Create a native OpenAI client (not wrapped with instructor)."""
    api_key = config["ai"].get("api_key", "")
    if not api_key:
        raise ValueError("API key required for provider 'openai'. Set ai.api_key in config.yaml.")
    custom_base_url = config["ai"].get("base_url", "")
    return OpenAI(
        api_key=api_key,
        base_url=custom_base_url or None,
        max_retries=config["ai"].get("max_retries", 2),
    )


def _get_anthropic_client(config: dict):
    """Create a native Anthropic client (not wrapped with instructor)."""
    from anthropic import Anthropic
    api_key = config["ai"].get("api_key", "")
    if not api_key:
        raise ValueError("API key required for provider 'anthropic'. Set ai.api_key in config.yaml.")
    return Anthropic(api_key=api_key, max_retries=config["ai"].get("max_retries", 2))


def _openai_input_text_block(text: str) -> dict:
    return {"type": "input_text", "text": text}


def _openai_input_image_blocks(images: list) -> list[dict]:
    return [
        {"type": "input_image", "image_url": pil_to_base64_data_uri(img)}
        for img in images
    ]


def _extract_openai_native(config: dict, user_content: list, *, profile: dict, metadata_model: type[BaseModel]) -> BaseModel:
    client = _get_openai_client(config)
    response = client.responses.parse(
        model=config["ai"]["model"],
        input=[
            {"role": "system", "content": [_openai_input_text_block(build_system_prompt(config, profile))]},
            {"role": "user", "content": user_content},
        ],
        text_format=metadata_model,
        store=False,
        **build_provider_create_kwargs("openai", config),
    )
    return response.output_parsed


def _extract_anthropic_native(config: dict, user_content, *, profile: dict, metadata_model: type[BaseModel]) -> BaseModel:
    client = _get_anthropic_client(config)
    response = client.messages.parse(
        model=config["ai"]["model"],
        system=build_system_prompt(config, profile),
        messages=[{"role": "user", "content": user_content}],
        output_format=metadata_model,
        **build_provider_create_kwargs("anthropic", config),
    )
    return response.parsed_output


def extract_metadata_from_text(text: str, config: dict, *, profile: dict, metadata_model: type[BaseModel]) -> BaseModel:
    """Extract document metadata from text using an LLM."""
    provider = config["ai"]["provider"]
    user_text = f"Extract the information from this text:\n\n{text}"
    if provider == "openai":
        return _extract_openai_native(
            config, [_openai_input_text_block(user_text)],
            profile=profile, metadata_model=metadata_model,
        )
    if provider == "anthropic":
        return _extract_anthropic_native(
            config, user_text, profile=profile, metadata_model=metadata_model,
        )

    client = get_instructor_client(config)

    kwargs = build_provider_create_kwargs(provider, config)
    kwargs.update({
        "model": config["ai"]["model"],
        "response_model": metadata_model,
        "max_retries": config["ai"].get("max_retries", 2),
        "messages": [
            {"role": "system", "content": build_system_prompt(config, profile)},
            {"role": "user", "content": user_text}
        ],
    })

    return client.chat.completions.create(**kwargs)


def extract_metadata_from_images(images: list, config: dict, *, profile: dict, metadata_model: type[BaseModel]) -> BaseModel:
    """Extract document metadata from page images using a vision-capable LLM."""
    provider = config["ai"]["provider"]
    if provider == "openai":
        return _extract_openai_native(config, [
            _openai_input_text_block("Extract document metadata from these page images:"),
            *_openai_input_image_blocks(images),
        ], profile=profile, metadata_model=metadata_model)
    if provider == "anthropic":
        image_content = build_image_content(images, "anthropic")
        return _extract_anthropic_native(config, [
            {"type": "text", "text": "Extract document metadata from these page images:"},
            *image_content,
        ], profile=profile, metadata_model=metadata_model)

    client = get_instructor_client(config)
    image_content = build_image_content(images, provider)

    kwargs = build_provider_create_kwargs(provider, config)
    kwargs.update({
        "model": config["ai"]["model"],
        "response_model": metadata_model,
        "max_retries": config["ai"].get("max_retries", 2),
        "messages": [
            {"role": "system", "content": build_system_prompt(config, profile)},
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
    text: str, images: list, config: dict, *, profile: dict, metadata_model: type[BaseModel],
) -> BaseModel:
    """Extract metadata from combined text + page images (multimodal)."""
    provider = config["ai"]["provider"]
    user_text = f"Extract document metadata from this text and images:\n\n{text}"
    if provider == "openai":
        return _extract_openai_native(config, [
            _openai_input_text_block(user_text),
            *_openai_input_image_blocks(images),
        ], profile=profile, metadata_model=metadata_model)
    if provider == "anthropic":
        image_content = build_image_content(images, "anthropic")
        return _extract_anthropic_native(config, [
            {"type": "text", "text": user_text},
            *image_content,
        ], profile=profile, metadata_model=metadata_model)

    client = get_instructor_client(config)
    image_content = build_image_content(images, provider)

    kwargs = build_provider_create_kwargs(provider, config)
    kwargs.update({
        "model": config["ai"]["model"],
        "response_model": metadata_model,
        "max_retries": config["ai"].get("max_retries", 2),
        "messages": [
            {"role": "system", "content": build_system_prompt(config, profile)},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                *image_content,
            ]},
        ],
    })

    return client.chat.completions.create(**kwargs)


def extract_metadata(
    extraction: ExtractionResult, config: dict, *, profile: dict, metadata_model: type[BaseModel],
) -> BaseModel | None:
    """Extract metadata from an ExtractionResult using the appropriate method."""
    combined_text = _build_combined_text(extraction)
    has_text = bool(combined_text.strip())
    has_images = bool(extraction.images)
    ctx = {"profile": profile, "metadata_model": metadata_model}

    if has_text and has_images:
        return extract_metadata_from_text_and_images(combined_text, extraction.images, config, **ctx)
    elif has_images:
        return extract_metadata_from_images(extraction.images, config, **ctx)
    elif has_text:
        return extract_metadata_from_text(combined_text, config, **ctx)
    else:
        logging.error("No text or images available for metadata extraction")
        return None
