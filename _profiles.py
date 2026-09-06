"""Extraction profile built-ins, overlay resolution, and selection. Functions only."""
from __future__ import annotations

from copy import deepcopy

_PROFILE_SCALARS = ("intro", "template", "truncate_field", "harmonize_field")
_BUILTIN_IDS = ("business", "academic")


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


def _apply_overlay(base: dict, overlay: dict) -> dict:
    result = deepcopy(base)
    for key in _PROFILE_SCALARS:
        if key in overlay:
            result[key] = overlay[key]
    if "intro" not in result:
        result["intro"] = ""
    if "harmonize_field" not in result:
        result["harmonize_field"] = None
    fields_overlay = overlay.get("fields")
    if fields_overlay is None:
        return result
    fields = result.setdefault("fields", {})
    for field_id, spec in fields_overlay.items():
        if spec is None:
            fields.pop(field_id, None)
        elif field_id in fields:
            fields[field_id] = deepcopy(spec)
        else:
            fields[field_id] = deepcopy(spec)
    return result


def _standalone_defaults(definition: dict) -> dict:
    result = deepcopy(definition)
    result.setdefault("intro", "")
    result.setdefault("harmonize_field", None)
    result.setdefault("fields", {})
    return result


def resolve_profiles(config: dict) -> dict[str, dict]:
    """Fresh, fully merged profiles: built-ins, then custom declaration order."""
    resolved = builtin_profiles(config)
    declarations = config.get("profiles") or {}
    if not isinstance(declarations, dict):
        raise ValueError("profiles must be a mapping")

    for profile_id, overlay in declarations.items():
        if profile_id in _BUILTIN_IDS:
            if overlay is None:
                raise ValueError(f"profile {profile_id!r} is null")
            resolved[profile_id] = _apply_overlay(resolved[profile_id], overlay)

    for profile_id, definition in declarations.items():
        if profile_id in _BUILTIN_IDS:
            continue
        if definition is None:
            raise ValueError(f"profile {profile_id!r} is null")
        parent_id = definition.get("extends")
        if parent_id:
            if parent_id not in resolved:
                raise ValueError(f"unknown parent {parent_id!r} for profile {profile_id!r}")
            parent = resolved[parent_id]
            resolved[profile_id] = _apply_overlay(parent, definition)
        else:
            resolved[profile_id] = _standalone_defaults(definition)
        resolved[profile_id].pop("extends", None)
    return resolved


def select_profile(config: dict, profile_id: str | None = None) -> tuple[str, dict]:
    """Select a resolved profile. Does not mutate config."""
    profiles = resolve_profiles(config)
    selected = profile_id if profile_id is not None else config.get("profile", "business")
    if selected not in profiles:
        raise ValueError(f"unknown profile {selected!r}")
    return selected, deepcopy(profiles[selected])
