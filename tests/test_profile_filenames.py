from copy import deepcopy
from pathlib import Path

import pytest

from _document_processing import render_filename, rename_document, undo_renames
from _profiles import select_profile


def rendered(config, selected, values, overlay=None, date_format=None):
    config = deepcopy(config)
    if overlay is not None:
        config["profiles"] = {selected: overlay}
    if date_format is not None:
        config["output"]["date_format"] = date_format
    profile_id, profile = select_profile(config, selected)
    raw = dict.fromkeys(profile["fields"], "")
    raw.update(values)
    before = deepcopy(raw)
    name = render_filename(profile_id, profile, raw, config)
    assert raw == before
    return name


DATE = "06.09.2026"
BUSINESS = "{document_date} {company_name} {document_type} {description}"
MIXED = "{document_date} {first_author_surname} {journal_name} - {title}"


@pytest.mark.parametrize("selected,values,overlay,date_format,expected", [
    pytest.param("business", dict(document_date=DATE, company_name="ACME", document_type="ER", description="12,13"), None, None, "20260906 ACME ER 12,13.pdf", id="business-incoming-printed-total"),
    pytest.param("business", dict(document_date=DATE, company_name="ACME", document_type="AR", description="1.234,56"), None, None, "20260906 ACME AR 1.234,56.pdf", id="business-outgoing-grouped-total"),
    pytest.param("business", dict(document_date=DATE, company_name="ACME", document_type="ER", description="EUR 12,13"), None, None, "20260906 ACME ER EUR 12,13.pdf", id="business-printed-currency"),
    pytest.param("business", dict(document_date=DATE, company_name="ACME", document_type="ER", description="", invoice_id="12345"), {"fields": {"invoice_id": {"description": "Printed invoice id."}}}, None, "20260906 ACME ER.pdf", id="business-no-total-even-with-id"),
    pytest.param("business", dict(document_date=DATE, company_name="ACME", document_type="Letter", description="Terminbestätigung"), None, None, "20260906 ACME Letter Terminbestätigung.pdf", id="business-verbatim-subject"),
    pytest.param("business", dict(document_date=DATE, company_name="<>:", document_type="?*", description=""), None, None, "20260906 Unknown Unknown.pdf", id="business-unusable-company-type"),
    pytest.param("academic", dict(document_date=DATE, first_author_surname="Smith", title="A Study"), None, None, "20260906 Smith A Study.pdf", id="academic-missing-venue"),
    pytest.param("academic", dict(document_date=DATE, first_author_surname="Smith"), {"template": "{document_date}_{first_author_surname}_{journal_name}_{title}"}, None, "20260906_Smith.pdf", id="underscore-missing-venue-title"),
    pytest.param("academic", dict(document_date=DATE, first_author_surname="Smith", title="A Study"), {"template": MIXED}, None, "20260906 Smith - A Study.pdf", id="mixed-missing-venue"),
    pytest.param("academic", dict(document_date=DATE, first_author_surname="Smith"), {"template": MIXED}, None, "20260906 Smith.pdf", id="mixed-missing-venue-title"),
    pytest.param("academic", dict(document_date=DATE, first_author_surname="Smith-Jones", title="A Study"), None, "%Y-%m-%d", "2026-09-06 Smith-Jones A Study.pdf", id="hyphenated-date-and-surname"),
    pytest.param("empty", {}, {"fields": {"document_date": {"description": "Date."}, "city": {"description": "City."}, "description": {"description": "Text."}}, "template": "{city} {description}", "truncate_field": "description"}, None, "Unknown.pdf", id="custom-unused-date-empty-basename"),
    pytest.param("custom", {}, {"extends": "business"}, None, "00000000.pdf", id="custom-business-empty-no-fallbacks"),
    pytest.param("academic", {}, None, None, "00000000.pdf", id="academic-all-empty"),
    pytest.param("business", {}, None, None, "00000000 Unknown Unknown.pdf", id="business-all-empty"),
    pytest.param("business", dict(document_date="not a date", company_name="ACME", document_type="ER", description="12,13"), None, None, "00000000 ACME ER 12,13.pdf", id="business-unparseable-date"),
])
def test_spec_filename_table(sample_config, selected, values, overlay, date_format, expected):
    assert rendered(sample_config, selected, values, overlay, date_format) == expected


@pytest.mark.parametrize("template,values,expected", [
    pytest.param("{{Paper}} {title}", {"title": "A Study"}, "{Paper} A Study.pdf", id="escaped-braces"),
    pytest.param("Prefix {journal_name} - {title}", {"title": "Smith-Jones 1.234,56"}, "Prefix - Smith-Jones 1.234,56.pdf", id="literal-prefix-and-value-punctuation"),
    pytest.param("{title}", {"title": "Cafe\u0301 <>:/\\?*\x00."}, "Café.pdf", id="unicode-and-unsafe-value"),
    pytest.param("{title}", {"title": "A   Study"}, "A Study.pdf", id="whitespace-cleanup"),
    pytest.param("{title}", {"title": "--Smith_Jones--"}, "--Smith_Jones--.pdf", id="value-separators-survive"),
    pytest.param("{first_author_surname}_ -_{journal_name}__{title}", {"first_author_surname": "Smith", "title": "A Study"}, "Smith - A Study.pdf", id="hyphen-precedence"),
    pytest.param("{first_author_surname} _ {journal_name} {title}", {"first_author_surname": "Smith", "title": "A Study"}, "Smith_A Study.pdf", id="underscore-precedence"),
    pytest.param("{first_author_surname}--{journal_name}--{title}", {"first_author_surname": "Smith", "title": "A Study"}, "Smith-A Study.pdf", id="hyphen-without-spaces"),
    pytest.param("_ -{title}- _", {"title": ""}, "Unknown.pdf", id="stranded-end-separators"),
    pytest.param("{first_author_surname}_\u00a0{journal_name}-{title}", {"first_author_surname": "Smith", "title": "Study"}, "Smith - Study.pdf", id="nbsp-separator-run"),
    pytest.param("_\u00a0{title}_\u00a0", {"title": ""}, "Unknown.pdf", id="nbsp-stranded-ends"),
])
def test_literal_and_value_safety(sample_config, template, values, expected):
    assert rendered(sample_config, "academic", values, {"template": template}) == expected


def test_truncates_only_explicit_title_and_preserves_raw(sample_config):
    assert rendered(sample_config, "academic", {
        "document_date": DATE, "first_author_surname": "Smith", "title": "A" * 400,
    }) == "20260906 Smith " + "A" * 229 + ".pdf"


def test_repeated_truncate_field_shares_one_shortened_value(sample_config):
    assert rendered(sample_config, "academic", {"title": "A" * 200}, {
        "template": "{title} - {title}",
    }) == "A" * 120 + " - " + "A" * 120 + ".pdf"


def test_exhausted_fallback_is_not_reinserted(sample_config):
    assert rendered(sample_config, "business", {}, {
        "template": "L" * 250 + " {company_name}", "truncate_field": "company_name",
    }) == "L" * 244 + ".pdf"


def test_hard_cut_after_target_exhaustion_strips_trailing_dot(sample_config):
    assert rendered(sample_config, "academic", {"title": "abc"}, {
        "template": "x" * 243 + ".tail {title}",
    }) == "x" * 243 + ".pdf"


def test_no_second_truncation_target(sample_config):
    expected = ("20260906 " + "C" * 400 + " ER")[:244] + ".pdf"
    assert rendered(sample_config, "business", {
        "document_date": DATE, "company_name": "C" * 400,
        "document_type": "ER", "description": "12,13",
    }) == expected


def test_date_behavior_is_reserved_and_invalid_ignores_output_format(sample_config):
    assert rendered(sample_config, "academic", {
        "document_date": "invalid", "title": "06.09.2026",
    }, date_format="%Y-%m-%d") == "00000000 06.09.2026.pdf"
    assert rendered(sample_config, "academic", {
        "document_date": "01.01.2026", "title": "Full title: subtitle",
    }) == "20260101 Full title subtitle.pdf"


def test_subject_overlapping_category_is_not_deduplicated(sample_config):
    assert rendered(sample_config, "business", {
        "document_date": DATE, "company_name": "ACME",
        "document_type": "Letter", "description": "Letter",
    }) == "20260906 ACME Letter Letter.pdf"


def test_invoice_id_overlay_keeps_amount_and_opt_out_keeps_raw_description(sample_config):
    values = {"document_date": DATE, "company_name": "ACME", "document_type": "ER", "description": "12,13", "invoice_id": "12345"}
    assert rendered(sample_config, "business", values, {
        "fields": {"invoice_id": {"description": "Printed invoice number."}},
        "template": "{document_date} {company_name} {document_type} {description} {invoice_id}",
    }) == "20260906 ACME ER 12,13 12345.pdf"
    del values["invoice_id"]
    assert rendered(sample_config, "business", values, {
        "template": "{document_date} {company_name} {document_type}",
        "truncate_field": "company_name",
    }) == "20260906 ACME ER.pdf"
    assert values["description"] == "12,13"


def test_profile_names_keep_collision_dry_run_skip_and_cross_profile_undo(sample_config, tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"original bytes")
    log = tmp_path / "undo.json"
    target_name = rendered(sample_config, "academic", {
        "document_date": DATE, "first_author_surname": "Smith", "title": "A" * 400,
    })
    existing = tmp_path / target_name
    existing.write_bytes(b"existing bytes")
    expected = tmp_path / (target_name[:-4] + "_(1).pdf")
    preview = rename_document(str(source), target_name, str(log), "preview", dry_run=True)
    assert Path(preview) == expected
    assert source.read_bytes() == b"original bytes"
    assert not expected.exists()
    assert not log.exists()
    actual = rename_document(str(source), target_name, str(log), "academic-batch")
    assert Path(actual) == expected
    assert expected.read_bytes() == b"original bytes"
    assert existing.read_bytes() == b"existing bytes"
    assert len(expected.name) == 252
    assert rename_document(str(existing), target_name, str(log), "skip-batch") is None
    sample_config["profile"] = "business"
    restored, failed, files = undo_renames(str(log), batch_id="academic-batch")
    assert (restored, failed) == (1, 0)
    assert len(files) == 1
    assert source.read_bytes() == b"original bytes"
    assert not expected.exists()
    assert existing.read_bytes() == b"existing bytes"
