"""Tests for extraction profile resolution and overlays."""
from copy import deepcopy

import pytest

from _profiles import resolve_profiles, select_profile


def test_builtin_ids_fields_and_templates(sample_config):
    profiles = resolve_profiles(sample_config)
    assert list(profiles) == ["business", "academic"]
    assert list(profiles["business"]["fields"]) == [
        "document_date", "company_name", "document_type", "description",
    ]
    assert list(profiles["academic"]["fields"]) == [
        "document_date", "first_author_surname", "journal_name", "title",
    ]
    assert profiles["business"]["template"] == (
        "{document_date} {company_name} {document_type} {description}"
    )
    assert profiles["academic"]["template"] == (
        "{document_date} {first_author_surname} {journal_name} {title}"
    )
    assert profiles["business"]["truncate_field"] == "description"
    assert profiles["business"]["harmonize_field"] == "company_name"
    assert profiles["academic"]["truncate_field"] == "title"
    assert profiles["academic"]["harmonize_field"] is None


def test_overlay_before_inheritance_replaces_in_place_and_deletes(sample_config):
    sample_config["profiles"] = {
        "receipts": {
            "extends": "business",
            "fields": {
                "document_type": None, "description": None,
                "short_title": {"description": "Printed receipt title."},
            },
            "template": "{document_date}_{company_name}_{city}_{short_title}",
            "truncate_field": "short_title",
            "harmonize_field": None,
        },
        "business": {"fields": {
            "company_name": {"description": "Issuer exactly as printed."},
            "city": {"description": "Printed city."},
        }},
        "child": {"extends": "receipts", "intro": "Child intro."},
    }
    before = deepcopy(sample_config)
    profiles = resolve_profiles(sample_config)
    assert list(profiles["receipts"]["fields"]) == [
        "document_date", "company_name", "city", "short_title",
    ]
    assert profiles["receipts"]["fields"]["company_name"] == {
        "description": "Issuer exactly as printed.",
    }
    assert profiles["receipts"]["harmonize_field"] is None
    assert profiles["child"]["fields"] == profiles["receipts"]["fields"]
    assert profiles["child"]["intro"] == "Child intro."
    assert sample_config == before
    profiles["child"]["fields"]["city"]["description"] = "Changed locally."
    assert resolve_profiles(sample_config)["receipts"]["fields"]["city"] == {
        "description": "Printed city.",
    }


def test_standalone_nine_fields_no_cap_and_selection_no_leak(sample_config):
    fields = {"document_date": {"description": "Printed date."}}
    fields.update({f"part_{n}": {"description": f"Printed part {n}."} for n in range(8)})
    sample_config.update(profile="nine", profiles={"nine": {
        "fields": fields, "template": "{part_0}", "truncate_field": "part_0",
    }})
    selected, profile = select_profile(sample_config)
    assert selected == "nine"
    assert len(profile["fields"]) == 9
    assert profile["intro"] == ""
    assert profile["harmonize_field"] is None
    selected, academic = select_profile(sample_config, "academic")
    assert selected == "academic"
    assert academic["template"] == "{document_date} {first_author_surname} {journal_name} {title}"
    assert sample_config["profile"] == "nine"


def test_deleting_company_with_repaired_references_does_not_recreate_it(sample_config):
    sample_config["profiles"] = {"business": {
        "fields": {"company_name": None}, "harmonize_field": None,
        "template": "{document_date} {document_type} {description}",
    }}
    profile = select_profile(sample_config)[1]
    assert list(profile["fields"]) == ["document_date", "document_type", "description"]
