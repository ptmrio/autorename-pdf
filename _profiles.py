"""Extraction profile built-ins, overlay resolution, and selection. Functions only."""
from __future__ import annotations

import keyword
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field, create_model

_PROFILE_KEYS = {"intro", "fields", "template", "truncate_field", "harmonize_field", "extends"}
_PROFILE_SCALARS = ("intro", "template", "truncate_field", "harmonize_field")
_FIELD_SPEC_KEYS = {"description"}
_BUILTIN_IDS = ("business", "academic")
_PROMPT_PLACEHOLDERS = ("company", "language", "incoming_invoice", "outgoing_invoice")


def _company_name_description(config: dict) -> str:
    company = (config.get("company") or {}).get("name") or ""
    if company:
        return (
            'Find the counterparty company. My company name is "{company}"; '
            "exclude my own company. Strip the legal form, such as e.U., SARL, "
            "GmbH, AG, Ltd, or Limited. Empty if no company is found."
        )
    return (
        "Find the main company in the document. Strip the legal form, such as "
        "e.U., SARL, GmbH, AG, Ltd, or Limited. Empty if no company is found."
    )


def builtin_profiles(config: dict) -> dict[str, dict]:
    """Fresh built-in profile dicts. Company instruction depends on config."""
    business = {
        "intro": (
            "Extract metadata for naming a business document. Separate the document "
            "category from its printed amount or subject. Never invent missing values."
        ),
        "fields": {
            "document_date": {
                "description": (
                    "Find the most relevant document date, such as the invoice date or "
                    "letter date, rather than a payment due date. Interpret the printed "
                    "date according to the document's language and location. Return "
                    "dd.mm.YYYY. Empty if no date is found."
                ),
            },
            "company_name": {"description": _company_name_description(config)},
            "document_type": {
                "description": (
                    'For incoming invoices, use only "{incoming_invoice}". For outgoing '
                    'invoices, use only "{outgoing_invoice}". Do not append an amount, '
                    "invoice number, or the words Invoice or Rechnung to either code. "
                    "For other documents, return a short category in {language}, such as "
                    "Letter or Contract, not a generated subject summary. Empty if unknown."
                ),
            },
            "description": {
                "description": (
                    "For an incoming or outgoing invoice whose document_type is "
                    '"{incoming_invoice}" or "{outgoing_invoice}", copy the printed final '
                    "invoice total amount as-is. Prefer the explicitly labelled final "
                    "total including tax over subtotals, tax-only amounts, or line items. "
                    "Preserve printed decimal and grouping punctuation, for example 12,13 "
                    "or 1.234,56. Preserve currency text or symbols only when printed as "
                    "part of that amount; never add currency words or convert currencies. "
                    "Do not calculate a missing total. Do not include Invoice, Rechnung, "
                    "an invoice number, or a total-label word. Empty if no total is printed. "
                    "For non-invoices, copy the document's own explicit subject or title "
                    "verbatim in its original language. Do not summarize, translate, or "
                    "invent a subject, or fall back to a generic document category or "
                    "identifying number. Empty if no subject or title is present."
                ),
            },
        },
        "template": "{document_date} {company_name} {document_type} {description}",
        "truncate_field": "description",
        "harmonize_field": "company_name",
    }
    academic = {
        "intro": "You are naming an academic paper, preprint, or thesis.",
        "fields": {
            "document_date": {
                "description": (
                    "Publication date in dd.mm.YYYY. Prefer publication over submission "
                    "or revision. If only a year is printed, use 01.01 of that year. "
                    "Empty if no date or year is found."
                ),
            },
            "first_author_surname": {
                "description": (
                    "First author's surname only; no initials, given names, or et al. "
                    "Empty if absent."
                ),
            },
            "journal_name": {
                "description": (
                    "Journal or conference venue as printed, including its printed "
                    "abbreviation. Empty when no venue is given."
                ),
            },
            "title": {
                "description": "Paper title as printed, in its original language. Empty if absent.",
            },
        },
        "template": "{document_date} {first_author_surname} {journal_name} {title}",
        "truncate_field": "title",
        "harmonize_field": None,
    }
    return {"business": business, "academic": academic}


def _check_declared_id(profile_id) -> str:
    if not isinstance(profile_id, str) or not profile_id or profile_id != profile_id.strip():
        raise ValueError(f"invalid profile id {profile_id!r}")
    return profile_id


def _check_selected_id(profile_id) -> str:
    if not isinstance(profile_id, str) or not profile_id or profile_id != profile_id.strip():
        raise ValueError(f"invalid profile id {profile_id!r}")
    return profile_id


def _valid_field_id(field_id) -> bool:
    if not isinstance(field_id, str) or not field_id:
        return False
    if not field_id.isidentifier() or keyword.iskeyword(field_id):
        return False
    if field_id.startswith("_") or field_id.startswith("model_"):
        return False
    if hasattr(BaseModel, field_id):
        return False
    return True


def _parse_placeholders(text: str) -> list[str]:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    names: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "{":
            if i + 1 < n and text[i + 1] == "{":
                i += 2
                continue
            close = text.find("}", i + 1)
            if close < 0:
                raise ValueError("unclosed brace")
            name = text[i + 1:close]
            if not name.isidentifier():
                raise ValueError(f"invalid placeholder {{{name}}}")
            names.append(name)
            i = close + 1
            continue
        if ch == "}":
            if i + 1 < n and text[i + 1] == "}":
                i += 2
                continue
            raise ValueError("unmatched brace")
        i += 1
    return names


def interpolate_profile_text(text: str, config: dict) -> str:
    """Expand the four allowed prompt placeholders. Substituted braces stay literal."""
    values = {
        "company": str((config.get("company") or {}).get("name") or ""),
        "language": str((config.get("output") or {}).get("language") or ""),
        "incoming_invoice": str((config.get("pdf") or {}).get("incoming_invoice") or ""),
        "outgoing_invoice": str((config.get("pdf") or {}).get("outgoing_invoice") or ""),
    }
    names = _parse_placeholders(text)
    for name in names:
        if name not in values:
            raise ValueError(f"unknown prompt placeholder {name!r}")
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "{":
            if i + 1 < n and text[i + 1] == "{":
                out.append("{")
                i += 2
                continue
            close = text.find("}", i + 1)
            name = text[i + 1:close]
            out.append(values[name])
            i = close + 1
            continue
        if ch == "}":
            out.append("}")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def iter_template_tokens(template: str):
    """Yield ('lit', text) or ('field', name) pairs from a validated template."""
    tokens: list[tuple[str, str]] = []
    lit: list[str] = []
    i = 0
    n = len(template)
    while i < n:
        ch = template[i]
        if ch == "{":
            if i + 1 < n and template[i + 1] == "{":
                lit.append("{")
                i += 2
                continue
            close = template.find("}", i + 1)
            if lit:
                tokens.append(("lit", "".join(lit)))
                lit = []
            tokens.append(("field", template[i + 1:close]))
            i = close + 1
            continue
        if ch == "}":
            lit.append("}")
            i += 2
            continue
        lit.append(ch)
        i += 1
    if lit:
        tokens.append(("lit", "".join(lit)))
    return tokens


def _validate_overlay_shape(profile_id: str, overlay, *, allow_extends: bool) -> None:
    if overlay is None:
        raise ValueError(f"profile {profile_id!r} is null")
    if not isinstance(overlay, dict):
        raise ValueError(f"profile {profile_id!r} must be a mapping")
    extra = set(overlay) - _PROFILE_KEYS
    if extra:
        raise ValueError(f"unknown keys on profile {profile_id!r}: {sorted(extra)}")
    if "extends" in overlay:
        if not allow_extends:
            raise ValueError(f"built-in profile {profile_id!r} cannot set extends")
        parent = overlay["extends"]
        if not isinstance(parent, str) or not parent or parent != parent.strip():
            raise ValueError(f"profile {profile_id!r} extends must be a single id")
        _check_selected_id(parent)
    if "intro" in overlay and overlay["intro"] is not None and not isinstance(overlay["intro"], str):
        raise ValueError(f"profile {profile_id!r} intro must be a string")
    if overlay.get("intro") is None and "intro" in overlay:
        raise ValueError(f"profile {profile_id!r} intro is null")
    if "template" in overlay:
        template = overlay["template"]
        if not isinstance(template, str) or not template:
            raise ValueError(f"profile {profile_id!r} template is empty")
    if "fields" in overlay:
        fields = overlay["fields"]
        if not isinstance(fields, dict):
            raise ValueError(f"profile {profile_id!r} fields must be a mapping")
        for field_id, spec in fields.items():
            if spec is None:
                continue
            if not _valid_field_id(field_id):
                raise ValueError(f"invalid field id {field_id!r}")
            if not isinstance(spec, dict):
                raise ValueError(f"field {field_id!r} must be a mapping")
            if set(spec) - _FIELD_SPEC_KEYS:
                raise ValueError(f"unknown keys on field {field_id!r}")
            description = spec.get("description")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"field {field_id!r} description is empty")


def _apply_overlay(base: dict, overlay: dict) -> dict:
    result = deepcopy(base)
    for key in _PROFILE_SCALARS:
        if key in overlay:
            result[key] = overlay[key]
    result.setdefault("intro", "")
    result.setdefault("harmonize_field", None)
    fields_overlay = overlay.get("fields")
    if fields_overlay is None:
        result.pop("extends", None)
        return result
    fields = result.setdefault("fields", {})
    for field_id, spec in fields_overlay.items():
        if spec is None:
            if field_id not in fields:
                raise ValueError(f"cannot delete missing field {field_id!r}")
            if field_id == "document_date":
                raise ValueError("document_date cannot be deleted")
            del fields[field_id]
        else:
            if not _valid_field_id(field_id):
                raise ValueError(f"invalid field id {field_id!r}")
            if field_id in fields:
                fields[field_id] = deepcopy(spec)
            else:
                fields[field_id] = deepcopy(spec)
    result.pop("extends", None)
    return result


def _standalone_defaults(definition: dict) -> dict:
    result = deepcopy(definition)
    result.pop("extends", None)
    result.setdefault("intro", "")
    result.setdefault("harmonize_field", None)
    fields = result.get("fields")
    if fields is None:
        result["fields"] = {}
    elif not isinstance(fields, dict):
        raise ValueError("fields must be a mapping")
    else:
        cleaned = {}
        for field_id, spec in fields.items():
            if spec is None:
                raise ValueError(f"cannot delete missing field {field_id!r}")
            cleaned[field_id] = deepcopy(spec)
        result["fields"] = cleaned
    return result


def _template_placeholders(template: str) -> list[str]:
    if "/" in template or "\\" in template:
        raise ValueError("template cannot contain path separators")
    if template.lower().endswith(".pdf"):
        raise ValueError("template must not include .pdf")
    return _parse_placeholders(template)


def _validate_resolved(profile_id: str, profile: dict) -> None:
    fields = profile.get("fields")
    if not isinstance(fields, dict) or "document_date" not in fields:
        raise ValueError(f"profile {profile_id!r} must include document_date")
    date_spec = fields.get("document_date")
    if not isinstance(date_spec, dict) or not isinstance(date_spec.get("description"), str):
        raise ValueError(f"profile {profile_id!r} document_date is invalid")
    for field_id, spec in fields.items():
        if spec is None or not isinstance(spec, dict):
            raise ValueError(f"field {field_id!r} must be a mapping")
    template = profile.get("template")
    if not isinstance(template, str) or not template:
        raise ValueError(f"profile {profile_id!r} is missing template")
    names = _template_placeholders(template)
    field_ids = set(fields)
    for name in names:
        if name not in field_ids:
            raise ValueError(f"template placeholder {name!r} is not a field")
    truncate = profile.get("truncate_field")
    if not isinstance(truncate, str) or truncate == "document_date" or truncate not in field_ids or f"{{{truncate}}}" not in template:
        raise ValueError(f"invalid truncate_field {truncate!r}")
    if truncate not in names:
        raise ValueError(f"truncate_field {truncate!r} is not in the template")
    harmonize = profile.get("harmonize_field", None)
    if harmonize is not None:
        if not isinstance(harmonize, str) or harmonize == "document_date" or harmonize not in field_ids:
            raise ValueError(f"invalid harmonize_field {harmonize!r}")
    intro = profile.get("intro", "")
    if not isinstance(intro, str):
        raise ValueError(f"profile {profile_id!r} intro must be a string")


def _interpolate_profile(profile: dict, config: dict) -> dict:
    result = deepcopy(profile)
    result["intro"] = interpolate_profile_text(result.get("intro") or "", config)
    for spec in result["fields"].values():
        spec["description"] = interpolate_profile_text(spec["description"], config)
    return result


def resolve_profiles(config: dict) -> dict[str, dict]:
    """Fresh, fully merged and interpolated profiles."""
    resolved = builtin_profiles(config)
    declarations = config["profiles"] if "profiles" in config else {}
    if not isinstance(declarations, dict):
        raise ValueError("profiles must be a mapping")
    for profile_id in declarations:
        _check_declared_id(profile_id)

    for profile_id, overlay in declarations.items():
        if profile_id not in _BUILTIN_IDS:
            continue
        _validate_overlay_shape(profile_id, overlay, allow_extends=False)
        resolved[profile_id] = _apply_overlay(resolved[profile_id], overlay)

    for profile_id, definition in declarations.items():
        if profile_id in _BUILTIN_IDS:
            continue
        _validate_overlay_shape(profile_id, definition, allow_extends=True)
        has_extends = isinstance(definition, dict) and "extends" in definition
        parent_id = definition.get("extends") if has_extends else None
        if has_extends:
            if parent_id not in resolved:
                raise ValueError(f"unknown parent {parent_id!r} for profile {profile_id!r}")
            resolved[profile_id] = _apply_overlay(resolved[parent_id], definition)
        else:
            if not isinstance(definition, dict):
                raise ValueError(f"profile {profile_id!r} must be a mapping")
            if "template" not in definition or "truncate_field" not in definition:
                raise ValueError(f"standalone profile {profile_id!r} is missing settings")
            resolved[profile_id] = _standalone_defaults(definition)

    for profile_id, profile in resolved.items():
        _validate_resolved(profile_id, profile)
        resolved[profile_id] = _interpolate_profile(profile, config)
    return resolved


def select_profile(config: dict, profile_id: str | None = None) -> tuple[str, dict]:
    """Select a resolved profile. Does not mutate config."""
    profiles = resolve_profiles(config)
    selected = config.get("profile", "business") if profile_id is None else profile_id
    selected = _check_selected_id(selected)
    if selected not in profiles:
        raise ValueError(f"unknown profile {selected!r}")
    return selected, deepcopy(profiles[selected])


def build_metadata_model(profile: dict):
    """Concrete required-string model for the resolved profile. No custom base class."""
    fields = {
        name: (str, Field(..., description=spec["description"]))
        for name, spec in profile["fields"].items()
    }
    return create_model(
        "DocumentMetadata",
        __config__=ConfigDict(extra="forbid", strict=True),
        **fields,
    )
