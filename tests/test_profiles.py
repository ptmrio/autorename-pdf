"""Tests for extraction profile resolution and overlays."""
from copy import deepcopy

import pytest

from _profiles import interpolate_profile_text, resolve_profiles, select_profile


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


@pytest.mark.parametrize("definitions", [
    pytest.param({"business": None}, id="null-profile"),
    pytest.param({"business": {"extra_fields": {}}}, id="unknown-profile-key"),
    pytest.param({"business": {"extends": "academic"}}, id="builtin-extends"),
    pytest.param({"x": {"extends": "missing"}}, id="unknown-parent"),
    pytest.param({"x": {"extends": "y"}, "y": {"extends": "business"}}, id="forward-parent"),
    pytest.param({"x": {"extends": "x"}}, id="self-parent"),
    pytest.param({"x": {"extends": "y"}, "y": {"extends": "x"}}, id="cycle"),
    pytest.param({"x": {"extends": ["business"]}}, id="multiple-parents"),
    pytest.param({"x": {"fields": {}}}, id="standalone-missing-settings"),
    pytest.param({"business": {"fields": []}}, id="field-list"),
    pytest.param({"business": {"fields": {"description": "text"}}}, id="scalar-field"),
    pytest.param({"business": {"fields": {"description": {"description": ""}}}}, id="empty-description"),
    pytest.param({"business": {"fields": {"description": {"description": "  "}}}}, id="blank-description"),
    pytest.param({"business": {"fields": {"description": {"description": 3}}}}, id="nonstring-description"),
    pytest.param({"business": {"fields": {"description": {"description": "x", "type": "str"}}}}, id="unknown-field-key"),
    pytest.param({"business": {"fields": {"absent": None}}}, id="delete-missing"),
    pytest.param({"business": {"fields": {"document_date": None}}}, id="delete-date"),
    pytest.param({"x": {"fields": {"title": {"description": "Title."}}, "template": "{title}", "truncate_field": "title"}}, id="missing-date"),
    pytest.param({"business": {"fields": {"company_name": None}}}, id="dangling-company"),
    pytest.param({"business": {"truncate_field": "document_date"}}, id="truncate-date"),
    pytest.param({"business": {"truncate_field": "absent"}}, id="truncate-missing"),
    pytest.param({"business": {"template": "{document_date}"}}, id="truncate-not-in-template"),
    pytest.param({"business": {"harmonize_field": "document_date"}}, id="harmonize-date"),
    pytest.param({"business": {"harmonize_field": "absent"}}, id="harmonize-missing"),
    pytest.param({"business": {"intro": None}}, id="null-intro"),
    pytest.param({"business": {"template": ""}}, id="empty-template"),
    pytest.param({"business": {"template": "{description}.pdf"}}, id="extension-in-template"),
    pytest.param({"business": {"template": "folder/{description}"}}, id="literal-slash"),
    pytest.param({"business": {"template": "folder\\{description}"}}, id="literal-backslash"),
    pytest.param({"business": {"template": "{description} {company}"}}, id="wrong-namespace"),
], ids=None)
def test_invalid_profile_definitions(sample_config, definitions):
    sample_config["profiles"] = definitions
    with pytest.raises(ValueError):
        resolve_profiles(sample_config)


@pytest.mark.parametrize("field_id", [
    "class", "_private", "bad-name", "9field", "model_dump", "schema",
    "model_config", "model_validate", "model_dump_extra", "", 7,
])
def test_invalid_pydantic_field_ids(sample_config, field_id):
    sample_config["profiles"] = {"business": {
        "fields": {field_id: {"description": "Value."}},
    }}
    with pytest.raises(ValueError):
        resolve_profiles(sample_config)


@pytest.mark.parametrize("profile_id", ["", " business", "business ", "Business", "missing", None, 7, False])
def test_invalid_selected_ids(sample_config, profile_id):
    sample_config["profile"] = profile_id
    with pytest.raises(ValueError):
        select_profile(sample_config)


@pytest.mark.parametrize("profile_id", ["", " x", "x ", None, 7, False])
def test_invalid_declared_ids(sample_config, profile_id):
    sample_config["profiles"] = {profile_id: {"extends": "business"}}
    with pytest.raises(ValueError):
        resolve_profiles(sample_config)


@pytest.mark.parametrize("text", [
    "{unknown}", "{company.name}", "{company[0]}", "{company!r}",
    "{company:>10}", "{company:}", "{", "}", "{}",
])
def test_reject_prompt_placeholder_syntax(sample_config, text):
    with pytest.raises(ValueError):
        interpolate_profile_text(text, sample_config)


@pytest.mark.parametrize("template", [
    "{description} {absent}", "{description.upper}", "{description[0]}",
    "{description!r}", "{description:>10}", "{description:}", "{", "}", "{}",
])
def test_reject_filename_placeholder_syntax(sample_config, template):
    sample_config["profiles"] = {"business": {"template": template}}
    with pytest.raises(ValueError):
        resolve_profiles(sample_config)


def test_interpolation_is_single_pass_and_user_company_override_wins(sample_config):
    sample_config["company"]["name"] = "Own {literal}"
    sample_config["output"]["language"] = "German"
    sample_config["pdf"].update(incoming_invoice="IN", outgoing_invoice="OUT")
    assert interpolate_profile_text(
        "{{tag}} {company}|{language}|{incoming_invoice}|{outgoing_invoice}", sample_config,
    ) == "{tag} Own {literal}|German|IN|OUT"
    sample_config["profiles"] = {"business": {"fields": {
        "company_name": {"description": "CUSTOM {company}"},
    }}}
    assert select_profile(sample_config)[1]["fields"]["company_name"]["description"] == "CUSTOM Own {literal}"
    sample_config["company"]["name"] = ""
    assert select_profile(sample_config)[1]["fields"]["company_name"]["description"] == "CUSTOM "


def test_inherited_interpolation_happens_once_after_resolution(sample_config):
    sample_config["company"]["name"] = "Own {literal}"
    sample_config["profiles"] = {
        "business": {"fields": {"company_name": {"description": "Issuer {company} {{tag}}"}}},
        "child": {"extends": "business"},
        "grandchild": {"extends": "child"},
    }
    profiles = resolve_profiles(sample_config)
    assert profiles["grandchild"]["fields"]["company_name"]["description"] == "Issuer Own {literal} {tag}"
