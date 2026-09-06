# Dynamic extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** use subagent-driven-development; the parent implements inline.

**Goal:** Support configurable extraction profiles with required named string fields and safe template filenames, defaulting to `20260906 ACME ER 12,13.pdf`.
**Architecture:** Resolve plain-dict built-ins and v2 config overlays before processing; generate one concrete extraction model for the selected profile per run and pass it through every existing provider route. Keep validated raw fields separate from harmonization and rendering, then reuse the existing rename, collision, retry, and undo operations. Extend sidecar JSON additively.
**Tech Stack:** existing Python CLI, Pydantic create_model, YAML v2 config, Tauri GUI sidecar JSON (additive only)
**Spec:** docs/superpowers/specs/2026-09-06-dynamic-extraction.md

## Constraints and execution policy

- No new Python core classes; `create_model` only for the runtime extraction model. Remove the fixed `DocumentMetadata` declaration; existing unrelated result containers can gain fields without redesign.
- Never push. Never commit `config.yaml` / `harmonized-company-names.yaml`. Stage explicit implementation paths only; leave this planning deliverable uncommitted.
- Use project venv `venv\Scripts\python.exe`; every Python command below uses `.\venv\Scripts\python.exe`. Never install Python dependencies globally.
- GUI typecheck with pnpm; GUI changes, if necessary, also require Vitest. No PowerShell test framework and no Tauri E2E.
- Live tests `--run-live` only, and only after explicit authorization to make live calls. Mock providers throughout RED/GREEN development. An unexecuted live check must be reported as unverified, never as a pass.
- No plugin marketplace/framework, profile YAML files on disk/discovery, journal alias maps, generic field alias infrastructure, GUI profile selector/schema editor, config rewrite, OCR/vision changes, or packaging profile assets.
- Preserve Python 3.11+, existing providers/models/settings and retries, independent OCR/vision selection, and the requirement that pdfplumber always runs.
- Invoice `description` is the printed final total, including printed punctuation/currency only. ER/AR already are types. Never default to invoice title/id or calculate a missing amount. Non-invoice descriptions copy explicit source titles verbatim; do not deduplicate a title overlapping its category.

Behavioral tasks below follow write test → run RED → implement → run GREEN → explicit-path commit. Execute each named test group as a small cycle rather than writing the entire suite before implementation. RED means the named behavior fails, not a bad fixture, an unrelated import error, or missing dependencies. A missing new public function is an acceptable first RED; rerun after introducing it to expose its behavioral assertions. Implementation paragraphs specify algorithms and boundary changes, not a mandatory private helper hierarchy. Code blocks are executable tests or concrete boundary edits; this document does not supply a second implementation to maintain.

Do not add prose/prompt keyword-presence tests, source-code scans as application tests, or assertions with no identifiable production behavior. Synthetic interpolation/prompt assembly and provider payload assertions test actual contracts; mocked extraction does **not** prove model comprehension. Exact built-in instruction wording is reviewed against the locked spec, and quality is checked by the explicitly gated live cases.

## File and contract map

| File | Responsibility/change |
|---|---|
| `_profiles.py` (new) | Module-level plain-dict business/academic built-ins; fresh resolution, overlay/inheritance/deletion, validation, single-pass profile interpolation, `create_model` factory. |
| `_config_loader.py` | Only `profile: business` and `profiles: {}` new config defaults; duplicate-key detection without a new loader class; preserve dotenv/env and existing v2 behavior. |
| `_ai_processing.py` | Replace fixed model, compose profile prompt, thread explicit resolved profile/model through native and instructor calls. |
| `_document_processing.py` | Pure template filename renderer; separate generic filename-based rename from fixed three-field rendering; retain harmonization/date/undo functions. |
| `autorename-pdf.py` | Validate/select once, build model once, CLI override/show/validate, raw and legacy result mapping, additive `FileResult` properties. |
| `tests/test_profiles.py`, `tests/test_profile_config.py`, `tests/test_profile_ai.py`, `tests/test_profile_filenames.py`, `tests/test_profile_pipeline.py`, `tests/test_profile_cli.py` (new) | Focused contract tests specified below; use existing pytest and fixtures. |
| `tests/test_ai_processing.py`, `tests/test_document_processing.py`, `tests/test_end_to_end.py`, `tests/test_live_integration.py` | Adapt existing call sites to generated models/new rendering boundaries; keep unrelated assertions. |
| `tests/test_live_profiles.py` (new) | Explicitly gated empirical profile extraction cases. |
| `README.md`, `config.yaml.example` | Intentional naming change, migration note, examples. No personal config edits. |
| `gui/src/lib/sidecar.ts`, `gui/src/lib/sidecar.test.ts` (conditional only) | Optional additive typing if a real compatibility need appears; existing nullable legacy keys retained. |

Pin these boundaries; private token representation, validators, and local helper names are implementation choices:

```text
resolve_profiles(config: dict) -> dict[str, dict]
    Fresh, fully validated/interpolated profiles, built-ins then custom declaration order.
    Validates all definitions; raises ValueError with a profile/field location.
select_profile(config: dict, profile_id: str | None = None) -> tuple[str, dict]
    Calls resolution, then selects explicit override or config.get('profile', 'business').
    No fallback for malformed/unknown selections; never mutates config.
interpolate_profile_text(text: str, config: dict) -> str
    Only four allowed names, escaped braces, single pass; invalid syntax raises ValueError.
build_metadata_model(profile: dict) -> type[BaseModel]
    create_model('DocumentMetadata', __config__=ConfigDict(extra='forbid', strict=True), ...).
build_system_prompt(config: dict, profile: dict) -> str
    Receives already interpolated definition; never interpolates prompt_extension.
extract_metadata(extraction, config, *, profile, metadata_model) -> BaseModel | None
    The three existing extract_metadata_from_* functions and the two native helpers
    also receive keyword-only profile and metadata_model; forward the identical type.
render_filename(profile_id: str, profile: dict, fields: dict[str, str], config: dict) -> str
    Pure; receives working fields (already harmonized where applicable), returns .pdf name.
rename_document(pdf_path: str, new_name: str, undo_log_path=None,
                batch_id=None, dry_run=False) -> str | None
    Consumes renderer output; preserves existing filesystem behavior, None means skip.
process_pdf(pdf_path, config, yaml_path, undo_log_path, dry_run=False,
            output=None, batch_id=None, *, profile_id, profile, metadata_model) -> FileResult
    Existing positional arguments retained; explicit run context is keyword-only.
```

`config show` will keep its existing top-level object and redaction and add output-only `resolved_profile` containing the selected definition; `profile` contains the selected id. Do not store `resolved_profile`, model types, or token objects in YAML or the loaded config. Keep `profiles` as the user's declarations in this view. Only `profile` and `profiles` are accepted new input settings.

## Preflight (setup, no behavior change)

- [ ] Read the spec fully, then inspect the functions in the file map and `git status --short`. Preserve pre-existing work, including the untracked locked spec. If Git reports this worktree's ownership mismatch, use a per-command `git -c safe.directory=D:/Code/autorename-pdf/.worktrees/dynamic-extraction ...`; do not change global Git config.
- [ ] If the local venv is absent, copy the permitted sibling venv using PowerShell, then install only into the worktree venv. These are setup commands, not a new test harness:

```powershell
if (-not (Test-Path -LiteralPath .\venv\Scripts\python.exe)) {
    Copy-Item -LiteralPath ..\stack-modernization\venv -Destination .\venv -Recurse
}
.\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\venv\Scripts\python.exe -c "import sys; print(sys.executable); assert sys.prefix != sys.base_prefix"
```

The sibling is `D:\Code\autorename-pdf\.worktrees\stack-modernization\venv`. If unavailable, create this worktree's `venv` with an installed Python 3.11+ `venv` bootstrap, then use only the commands above for dependencies/execution. Do not copy over an existing working venv. Expected interpreter: this worktree's `venv\Scripts\python.exe`.

- [ ] Record baseline gates:

```powershell
.\venv\Scripts\python.exe -m ruff check .
.\venv\Scripts\python.exe -m pytest tests/ -v --cov
```

Expected: mocked tests pass, live tests skip. Record any pre-existing failure before edits. Setup gets no artificial RED test or commit because it adds no product behavior.

## Task 1: Resolve built-ins, overlays, inheritance, and deletion

**Files:** create `_profiles.py`, `tests/test_profiles.py`.

- [ ] Add these tests. `sample_config` is the existing fixture from `tests/conftest.py`; do not replace it with a second global config fixture.

```python
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
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profiles.py::test_builtin_ids_fields_and_templates tests/test_profiles.py::test_overlay_before_inheritance_replaces_in_place_and_deletes tests/test_profiles.py::test_standalone_nine_fields_no_cap_and_selection_no_leak tests/test_profiles.py::test_deleting_company_with_repaired_references_does_not_recreate_it -v`.
- [ ] Implement the two built-in plain dicts by copying the normative YAML-equivalent contents from the spec into Python dict literals, preserving all instruction wording. For empty own-company config, materialize the exact alternative company instruction **before** overlays; user descriptions win. Deep-copy nested defaults and parents. Apply all same-name built-in overlays before custom profiles, even when a built-in overlay appears later in YAML. Then resolve custom profiles in declaration order, inheriting the already overlaid parent. Assigning existing dict entries preserves position; deleting removes them; new entries append. Validate final definitions, never half-applied overlays. No file loader or class.
- [ ] GREEN: rerun the exact RED command; expect all four tests to pass. Manually compare the two dicts and empty-company variant against the spec; do not encode prose-keyword assertions.
- [ ] Commit: `git add _profiles.py tests/test_profiles.py` then `git commit -m "feat: resolve extraction profile overlays and inheritance"`.

## Task 2: Reject invalid profiles and placeholder grammars

**Files:** modify `_profiles.py`, `tests/test_profiles.py`.

- [ ] Append these executable negative cases and interpolation contracts:

```python
from _profiles import interpolate_profile_text


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
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profiles.py::test_invalid_profile_definitions tests/test_profiles.py::test_invalid_pydantic_field_ids tests/test_profiles.py::test_invalid_selected_ids tests/test_profiles.py::test_invalid_declared_ids tests/test_profiles.py::test_reject_prompt_placeholder_syntax tests/test_profiles.py::test_reject_filename_placeholder_syntax tests/test_profiles.py::test_interpolation_is_single_pass_and_user_company_override_wins tests/test_profiles.py::test_inherited_interpolation_happens_once_after_resolution -v`.
- [ ] Implement strict mapping/scalar/key validation, required date preservation, and reference validation. Check string identifiers with `str.isidentifier`, `keyword.iskeyword`, leading underscore, BaseModel attributes and the installed Pydantic protected namespaces; reject collisions rather than silently dropping/warning. No arbitrary field-count cap. Reject malformed `profiles` containers and non-string ids before dict lookups. Built-in overlays cannot inherit; earlier-parent-only custom resolution rejects every forward/cyclic case.
- [ ] Implement a shared restricted brace parser usable for the two separate namespaces. Keep original placeholder syntax available to reject even an explicitly empty format specifier (`{description:}`); `Formatter.parse` alone loses that distinction. Accept only bare allowed names and doubled literal braces; forbid attribute/index access, `!`, `:`, anonymous/numeric substitutions, malformed braces, filename literal `/` or `\`, and a `.pdf` template suffix (case-insensitive). Interpolate only intro/descriptions, once, after env substitution and resolution; substituted braces are literal. Do not trim user override text or run `.format` again on parent-resolved text. Resolve inheritance before interpolation to avoid double-interpolating inherited descriptions.
- [ ] GREEN: `.\venv\Scripts\python.exe -m pytest tests/test_profiles.py -v`. Every case must pass, including valid repaired deletion from Task 1.
- [ ] Commit: `git add _profiles.py tests/test_profiles.py` then `git commit -m "feat: validate profile fields and restricted placeholders"`.

## Task 3: Load v2 profile config without losing duplicate keys

**Files:** modify `_config_loader.py`; create `tests/test_profile_config.py`.

- [ ] Add loader behavior tests using temporary files only:

```python
from _config_loader import load_yaml_config
from _profiles import select_profile

import pytest


@pytest.mark.parametrize("source", [
    pytest.param("config_version: 2\nprofile: business\nprofile: academic\n", id="top-level"),
    pytest.param("config_version: 2\nprofiles:\n  business: {}\n  business: {}\n", id="profile-id"),
    pytest.param("config_version: 2\nprofiles:\n  business:\n    fields:\n      description: {description: first}\n      description: {description: second}\n", id="field-id"),
    pytest.param("config_version: 2\nprofiles:\n  business:\n    fields:\n      description: {description: first, description: second}\n", id="field-spec"),
    pytest.param("config_version: 2\nai: {model: one, model: two}\n", id="existing-setting"),
])
def test_duplicate_yaml_keys_rejected(tmp_path, source):
    path = tmp_path / "test-config.yaml"
    path.write_text(source, encoding="utf-8")
    assert load_yaml_config(str(path)) is None
    assert path.read_text(encoding="utf-8") == source


def test_v2_defaults_and_env_before_profile_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_CITY", "Wien")
    path = tmp_path / "test-config.yaml"
    source = (
        "config_version: 2\ncompany: {name: ACME}\nprofiles:\n"
        "  business:\n    fields:\n"
        "      description: {description: '${PROFILE_CITY} {company}'}\n"
    )
    path.write_text(source, encoding="utf-8")
    config = load_yaml_config(str(path))
    assert config["config_version"] == 2
    assert config["profile"] == "business"
    assert select_profile(config)[1]["fields"]["description"]["description"] == "Wien ACME"
    assert path.read_text(encoding="utf-8") == source
    path.write_text("config_version: 2\n", encoding="utf-8")
    assert load_yaml_config(str(path))["profiles"] == {}
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_config.py::test_duplicate_yaml_keys_rejected tests/test_profile_config.py::test_v2_defaults_and_env_before_profile_interpolation -v`.
- [ ] Add just these entries to `DEFAULTS`:

```python
"profile": "business",
"profiles": {},
```

Before constructing the config mapping, detect duplicate mapping keys at **every depth**, with YAML line/location information in the logged error. Use a locally instantiated `yaml.SafeLoader` and a function bound to that instance for mapping construction, or a validated node traversal; do not declare a loader subclass or register a global PyYAML constructor. Preserve safe loading, declaration order, and existing mapping semantics. Dispose local loaders even on errors. Return `None` for YAML errors, matching the existing loader contract; CLI translates that to exit 3. Preserve dotenv lookup and recursive `${VAR}` interpolation before profile resolution. Do not deep-merge profile fields with a generic merge that discards null deletes or declaration order.
- [ ] GREEN: `.\venv\Scripts\python.exe -m pytest tests/test_profile_config.py tests/test_config_loader.py -v`. Expect old v2 configs still to load and remain byte-for-byte untouched on disk.
- [ ] Commit: `git add _config_loader.py tests/test_profile_config.py` then `git commit -m "feat: load profile settings and reject duplicate YAML keys"`.

## Task 4: Generate a strict named model

**Files:** modify `_profiles.py`; create `tests/test_profile_ai.py`.

- [ ] Add these schema tests. Prompt assembly and provider call-site adaptation form one atomic change in Task 5.

```python
import pytest
from pydantic import ValidationError

from _profiles import build_metadata_model, select_profile


def test_generated_model_has_required_named_strings_and_descriptions(sample_config):
    profile = select_profile(sample_config, "academic")[1]
    model = build_metadata_model(profile)
    schema = model.model_json_schema()
    assert list(schema["properties"]) == list(profile["fields"])
    assert schema["required"] == list(profile["fields"])
    assert schema["additionalProperties"] is False
    for name, field in profile["fields"].items():
        assert schema["properties"][name]["type"] == "string"
        assert schema["properties"][name]["description"] == field["description"]
        assert "default" not in schema["properties"][name]
    raw = dict.fromkeys(profile["fields"], "")
    assert model.model_validate(raw).model_dump() == raw


@pytest.mark.parametrize("change", ["missing", "null", "number", "boolean", "list", "bytes", "extra"])
def test_generated_model_rejects_invalid_output(sample_config, change):
    profile = select_profile(sample_config)[1]
    model = build_metadata_model(profile)
    raw = dict.fromkeys(profile["fields"], "")
    if change == "missing":
        del raw["description"]
    elif change == "extra":
        raw["invoice_id"] = "12345"
    else:
        raw["description"] = {
            "null": None, "number": 12, "boolean": True, "list": [], "bytes": b"text",
        }[change]
    with pytest.raises(ValidationError):
        model.model_validate(raw)
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_ai.py::test_generated_model_has_required_named_strings_and_descriptions tests/test_profile_ai.py::test_generated_model_rejects_invalid_output -v`.
- [ ] Implement the factory with the concrete Pydantic boundary below (imports belong in `_profiles.py`). No custom base class, default empty values, generic bag, or module-global selected model:

```python
from pydantic import ConfigDict, Field, create_model


def build_metadata_model(profile: dict):
    fields = {
        name: (str, Field(..., description=spec["description"]))
        for name, spec in profile["fields"].items()
    }
    return create_model(
        "DocumentMetadata", __config__=ConfigDict(extra="forbid", strict=True), **fields,
    )
```

- [ ] GREEN: `.\venv\Scripts\python.exe -m pytest tests/test_profile_ai.py tests/test_profiles.py -v`; expect strict required strings and matching schema descriptions. Removing the fixed model and adapting its callers happens together in Task 5, so this commit leaves the existing extraction path intact.
- [ ] Commit: `git add _profiles.py tests/test_profile_ai.py` then `git commit -m "feat: generate strict profile metadata models"`.

## Task 5: Thread the identical generated type through every provider path

**Files:** modify `_ai_processing.py`, `autorename-pdf.py`, `tests/test_ai_processing.py`, `tests/test_end_to_end.py`, `tests/test_live_integration.py`; append `tests/test_profile_ai.py`. Update imports/fixtures at existing call sites when removing the fixed model; do not retain a compatibility class.

- [ ] Append the synthetic prompt-assembly contract and transport matrix. They test exact assembly/dataflow, not keyword presence in normative prose. The matrix exercises text, images, and combined sources through the real dispatch function:

```python
from copy import deepcopy
from unittest.mock import MagicMock

import _ai_processing as ai
from PIL import Image
from _pdf_utils import ExtractionResult


def test_prompt_assembly_uses_resolved_schema_order_and_verbatim_extension(sample_config):
    sample_config["prompt_extension"] = "  EXTRA {untouched}\n "
    profile = {
        "intro": "INTRO",
        "fields": {
            "document_date": {"description": "DATE"},
            "title": {"description": "TITLE"},
        },
        "template": "{title}", "truncate_field": "title", "harmonize_field": None,
    }
    before = deepcopy(profile)
    expected = (
        "Extract the requested fields from the document content. Due to OCR text detection, "
        "the text may be noisy and contain spelling and detection errors. Handle those as well as possible."
        "\n\nINTRO\n\ndocument_date: DATE\n\ntitle: TITLE\n\n"
        "Return every requested field as a string. If a value is not found, return an empty string. "
        "Do not invent missing values or return undeclared fields.\n\n  EXTRA {untouched}\n "
    )
    assert ai.build_system_prompt(sample_config, profile) == expected
    assert profile == before
    assert list(build_metadata_model(profile).model_fields) == ["document_date", "title"]
    profile["intro"] = ""
    assert ai.build_system_prompt(sample_config, profile) == expected.replace("\n\nINTRO", "", 1)


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "xai", "ollama"])
@pytest.mark.parametrize("source", ["text", "images", "combined"])
def test_generated_model_reaches_provider(sample_config, monkeypatch, provider, source):
    sample_config["ai"].update(provider=provider, model="gpt-5.6-luna", temperature=0.7)
    profile = select_profile(sample_config, "academic")[1]
    model = build_metadata_model(profile)
    raw = {
        "document_date": "01.01.2026", "first_author_surname": "Smith",
        "journal_name": "", "title": "A Study",
    }
    parsed = model.model_validate(raw)
    client = MagicMock()
    client.responses.parse.return_value.output_parsed = parsed
    client.messages.parse.return_value.parsed_output = parsed
    client.chat.completions.create.return_value = parsed
    monkeypatch.setattr(ai, "_get_openai_client", lambda config: client)
    monkeypatch.setattr(ai, "_get_anthropic_client", lambda config: client)
    monkeypatch.setattr(ai, "get_instructor_client", lambda config: client)
    extraction = ExtractionResult(
        text="Printed text" if source != "images" else "",
        images=[Image.new("RGB", (2, 2))] if source != "text" else [],
        quality_score=1.0, page_count=1, sources=[source],
    )
    result = ai.extract_metadata(extraction, sample_config, profile=profile, metadata_model=model)
    assert result.model_dump() == raw
    if provider == "openai":
        call = client.responses.parse
        kwargs = call.call_args.kwargs
        assert kwargs["text_format"] is model
        assert kwargs["store"] is False
        assert kwargs["reasoning"] == {"effort": "none"}
        assert "temperature" not in kwargs
        assert "reasoning_effort" not in kwargs
        assert "messages" not in kwargs
        user_blocks = kwargs["input"][1]["content"]
        assert sum(block["type"] == "input_image" for block in user_blocks) == (source != "text")
        assert kwargs["input"][0]["content"][0]["text"] == ai.build_system_prompt(sample_config, profile)
        client.chat.completions.create.assert_not_called()
    elif provider == "anthropic":
        call = client.messages.parse
        kwargs = call.call_args.kwargs
        assert kwargs["output_format"] is model
        assert kwargs["max_tokens"] == 1024
        assert "temperature" not in kwargs
        assert "reasoning" not in kwargs
        assert "reasoning_effort" not in kwargs
        assert kwargs["system"] == ai.build_system_prompt(sample_config, profile)
        if source != "text":
            blocks = kwargs["messages"][0]["content"]
            assert sum(block["type"] == "image" for block in blocks) == 1
        client.chat.completions.create.assert_not_called()
    else:
        call = client.chat.completions.create
        kwargs = call.call_args.kwargs
        assert kwargs["response_model"] is model
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_retries"] == sample_config["ai"]["max_retries"]
        assert kwargs["messages"][0]["content"] == ai.build_system_prompt(sample_config, profile)
        if source != "text":
            blocks = kwargs["messages"][1]["content"]
            assert sum(block["type"] == "image_url" for block in blocks) == 1
        client.responses.parse.assert_not_called()
        client.messages.parse.assert_not_called()
    call.assert_called_once()
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_ai.py::test_prompt_assembly_uses_resolved_schema_order_and_verbatim_extension tests/test_profile_ai.py::test_generated_model_reaches_provider -v`. Exact example matrix node: `tests/test_profile_ai.py::test_generated_model_reaches_provider[combined-openai]`.
- [ ] Replace `build_system_prompt` with ordered assembly: exact shared preamble, nonempty resolved intro, one ordered `field_id: description` paragraph per field, exact shared string/empty/extra instruction, then a blank line plus nonempty `prompt_extension` verbatim. Join the first four parts and append extension afterward; no final `.strip()` that changes it. Keep interpolation out of this function. Retire existing `TestBuildSystemPrompt` keyword-presence tests in favor of the synthetic assembly contract; do not claim this proves model comprehension.
- [ ] Remove the declared `DocumentMetadata` class. Add required keyword-only `profile, metadata_model` arguments to the five provider entry/helper functions and dispatcher shown in the file map. Pass the **same object** down every branch. Replace only the schema argument and system-prompt call at each transport boundary:

```python
# OpenAI responses.parse keyword arguments:
text_format=metadata_model,
# Anthropic messages.parse keyword arguments:
output_format=metadata_model,
# Instructor kwargs entry:
"response_model": metadata_model,
# Every system prompt call:
build_system_prompt(config, profile)
```

Retain OpenAI Responses content blocks, `store=False`, model-sensitive `reasoning={"effort": "none"}` and omitted temperature/legacy reasoning_effort. Retain Anthropic `max_tokens=1024`, omitted temperature and existing messages/image blocks. Retain instructor TOOLS for Gemini/xAI, JSON for Ollama, temperature and max_retries. No client re-routing or new global model cache.
- [ ] Wire default/config-selected run context now so removing the fixed model is atomic: `_handle_rename` resolves the selected profile and creates its model before the loop, passes `profile_id`, `profile`, and `metadata_model` to `process_pdf`, which forwards `profile` and `metadata_model` to extraction. Task 9 changes field/result handling; Task 10 adds CLI override/error/show behavior. Do not create a temporary per-file model path.
- [ ] Adapt existing tests by constructing metadata with the selected generated model and `description=""` for old three-field fixtures; pass the explicit profile/model to direct extraction and process calls. Keep the six existing native parse tests and all their kwargs/content assertions; only replace `DocumentMetadata` identity with the local generated type. Preserve `TestBuildProviderCreateKwargs`, `TestNativeClientMaxRetries`, and instructor mode assertions unchanged. Do not leave a removed import or uncallable application between commits.
- [ ] GREEN:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_profile_ai.py tests/test_ai_processing.py::TestNativeStructuredExtract tests/test_ai_processing.py::TestBuildProviderCreateKwargs tests/test_ai_processing.py::TestNativeClientMaxRetries tests/test_ai_processing.py::TestGetInstructorClient -v
```

Expected: all 15 transport combinations pass; native kwargs and mode/retry tests remain green. Adapt existing `TestExtractMetadata` mocks to the new keyword args and run all of `tests/test_ai_processing.py` as the final task gate.
- [ ] Commit: `git add _ai_processing.py autorename-pdf.py tests/test_profile_ai.py tests/test_ai_processing.py tests/test_end_to_end.py tests/test_live_integration.py` then `git commit -m "feat: pass generated profile models through all extraction routes"`.

## Task 6: Render every normative filename collapse case

**Files:** modify `_document_processing.py`; create `tests/test_profile_filenames.py`.

- [ ] Add the named 16-row acceptance table below. Helpers are local test data adapters, not application scaffolding. Test functions return the complete `.pdf` name through the real pure renderer.

```python
from copy import deepcopy

import pytest

from _document_processing import render_filename
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
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_filenames.py::test_spec_filename_table -v`. Each normative row has its own stable pytest node, e.g. `tests/test_profile_filenames.py::test_spec_filename_table[mixed-missing-venue-title]`; the 16 ids above are the complete table, not a sampled subset.
- [ ] Implement `render_filename` from parsed template tokens. Make a fresh working-value dictionary. Parse only `document_date` through `parse_document_date` (DMY), format valid dates with `output.date_format`; empty/unparseable dates always become `00000000`. Normalize/sanitize extracted strings separately from template literals. Reject unusable text after sanitization; apply `Unknown` only to present `company_name`/`document_type` for active id exactly `business`, never to its custom descendants. Do not treat a text value as unusable solely because its length exceeds 255: the later truncation stage handles long values.
- [ ] Remove empty substitution tokens, accumulating adjacent separator-only literal segments between surviving content. For each accumulated run choose hyphen over underscore over space; surround the surviving hyphen with one space only if the contributing run contained whitespace. Strip stranded separator-only runs at ends. Preserve nonseparator literal content as explicit anchors, including escaped braces. Never inspect punctuation inside surviving value tokens as separators. Finally sanitize/normalize the whole basename, collapse whitespace without deleting value punctuation, and use whole-name `Unknown` only if nothing remains. Do not use a global hyphen/underscore regex over the interpolated string.
- [ ] GREEN: rerun the exact RED command. Expected: all 16 named cases pass with no raw-field mutation.
- [ ] Commit: `git add _document_processing.py tests/test_profile_filenames.py` then `git commit -m "feat: render profile filenames with token-aware separator cleanup"`.

## Task 7: Preserve literal content and bound explicit-field truncation

**Files:** modify `_document_processing.py`; append `tests/test_profile_filenames.py`.

- [ ] Add these renderer tests:

```python
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
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_filenames.py::test_literal_and_value_safety tests/test_profile_filenames.py::test_truncates_only_explicit_title_and_preserves_raw tests/test_profile_filenames.py::test_repeated_truncate_field_shares_one_shortened_value tests/test_profile_filenames.py::test_exhausted_fallback_is_not_reinserted tests/test_profile_filenames.py::test_hard_cut_after_target_exhaustion_strips_trailing_dot tests/test_profile_filenames.py::test_no_second_truncation_target tests/test_profile_filenames.py::test_date_behavior_is_reserved_and_invalid_ignores_output_format tests/test_profile_filenames.py::test_subject_overlapping_category_is_not_deduplicated tests/test_profile_filenames.py::test_invoice_id_overlay_keeps_amount_and_opt_out_keeps_raw_description -v`.
- [ ] Compute all fallbacks once before length handling. While basename exceeds 244 characters and the rendered `truncate_field` has characters left, shorten that shared value from the right and rerender/clean the original tokens. A repeated placeholder uses the same shortened value everywhere. Exhaustion means empty, even if its starting value was `Unknown`; do not reapply field fallbacks. If still too long, hard-cut basename to 244 and strip trailing invalid dots/spaces. Preserve `.pdf` separately. Do not shorten another field implicitly, alter raw input, or reject long text before truncation. The operation must terminate with at most the original target length worth of shortening (an equivalent bounded search is allowed).
- [ ] GREEN: `.\venv\Scripts\python.exe -m pytest tests/test_profile_filenames.py tests/test_document_processing.py::TestParseDocumentDate tests/test_utils.py -v`. Expect all table/safety/length/date cases to pass.
- [ ] Commit: `git add _document_processing.py tests/test_profile_filenames.py` then `git commit -m "feat: truncate the configured filename field safely"`.

## Task 8: Connect rendered names to existing filesystem operations

**Files:** modify `_document_processing.py`, `tests/test_document_processing.py`; append `tests/test_profile_filenames.py`. Update the current CLI import/call atomically when replacing `rename_invoice` with `rename_document`; Task 9 completes dynamic result mapping.

- [ ] Add a real temporary-filesystem test; provider calls are irrelevant and absent:

```python
from pathlib import Path

from _document_processing import rename_document, undo_renames


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
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_filenames.py::test_profile_names_keep_collision_dry_run_skip_and_cross_profile_undo -v`.
- [ ] Split the existing `rename_invoice` at its filename/filesystem boundary. `render_filename` now owns all name construction. `rename_document` receives the safe complete `.pdf` name, derives `base_name` by removing that extension, then retains path normalization, already-correct comparison **before** collision search, `_(n)` collision suffix, dry-run return before mutation/logging, `_rename_with_retry`, and `_write_undo_log`. Keep the current 244-character reservation; do not add another truncation policy or change undo format.
- [ ] Update old rename tests to call the renderer plus `rename_document`, with empty business `description` where the test exercises unchanged three-component output. Replace the old company-only truncation expectation with explicit `truncate_field: company_name` where that is the behavior under test; the new default target is `description`. Preserve the existing retry and all-skipped undo assertions. No test-only legacy production wrapper.
- [ ] GREEN:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_profile_filenames.py::test_profile_names_keep_collision_dry_run_skip_and_cross_profile_undo tests/test_document_processing.py -v
```

Expected: collision uses the same basename/suffix, retry still retries PermissionError and raises on final failure, undo restores logged paths irrespective of current profile, and all-skipped batches still protect prior runs.
- [ ] Commit: `git add _document_processing.py autorename-pdf.py tests/test_document_processing.py tests/test_profile_filenames.py` then `git commit -m "refactor: rename rendered profile filenames with existing undo semantics"`.

## Task 9: Preserve raw fields and map legacy metadata independently

**Files:** modify `autorename-pdf.py`, `tests/test_end_to_end.py`; create `tests/test_profile_pipeline.py`.

- [ ] Add these real orchestration tests with only content/provider boundaries mocked. The existing `autorename_pdf_runner._mod` is the import bridge; reuse it.

```python
from copy import deepcopy
from unittest.mock import Mock

import pytest

from autorename_pdf_runner import _mod as cli
from _pdf_utils import ExtractionResult
from _profiles import build_metadata_model, select_profile


def run_file(tmp_path, monkeypatch, config, selected, raw, *, mode="dry", filename="source.pdf"):
    profile_id, profile = select_profile(config, selected)
    model = build_metadata_model(profile)
    source = tmp_path / filename
    source.write_bytes(b"source bytes")
    content = ExtractionResult(text="Printed content", quality_score=1, page_count=1, sources=["text"])
    if mode == "no-content":
        content = ExtractionResult(text="", quality_score=0, page_count=1, sources=["text"])
    monkeypatch.setattr(cli, "extract_content", Mock(return_value=content))
    extract = Mock(return_value=None if mode == "no-metadata" else model.model_validate(raw))
    if mode == "provider-error":
        extract.side_effect = RuntimeError("provider failed")
    monkeypatch.setattr(cli, "extract_metadata", extract)
    if mode == "rename-error":
        monkeypatch.setattr(cli, "rename_document", Mock(side_effect=PermissionError("locked")))
    return cli.process_pdf(
        str(source), config, str(tmp_path / "aliases.yaml"), str(tmp_path / "undo.json"),
        dry_run=True, profile_id=profile_id, profile=profile, metadata_model=model,
    ).to_dict()


def test_business_raw_survives_aliases_unicode_and_truncation(sample_config, tmp_path, monkeypatch):
    import _document_processing as documents
    (tmp_path / "aliases.yaml").write_text('Canonical: ["Café"]\n', encoding="utf-8")
    raw = {
        "document_date": "06.09.2026", "company_name": "Cafe\u0301",
        "document_type": "ER", "description": "A" * 400,
    }
    before = deepcopy(raw)
    result = run_file(tmp_path, monkeypatch, sample_config, "business", raw)
    assert result["profile"] == "business"
    assert result["fields"] == before
    assert raw == before
    assert result["company"] == "Canonical"
    assert result["date"] == "2026-09-06"
    assert result["doc_type"] == "ER"
    assert result["status"] == "renamed"
    assert result["new_name"] == "20260906 Canonical ER " + "A" * 222 + ".pdf"
    assert documents.parse_document_date(result["fields"]["document_date"]).isoformat() == result["date"]


def test_academic_bypasses_alias_loading_and_keeps_legacy_date(sample_config, tmp_path, monkeypatch):
    import _document_processing as documents
    forbidden = Mock(side_effect=AssertionError("academic must not access company aliases"))
    monkeypatch.setattr(cli, "harmonize_company_name", forbidden)
    monkeypatch.setattr(documents, "load_company_names", forbidden)
    result = run_file(tmp_path, monkeypatch, sample_config, "academic", {
        "document_date": "01.01.2026", "first_author_surname": "Smith",
        "journal_name": "", "title": "Original title",
    })
    assert result["profile"] == "academic"
    assert result["company"] is None
    assert result["doc_type"] is None
    assert result["date"] == "2026-01-01"
    assert result["new_name"] == "20260101 Smith Original title.pdf"
    forbidden.assert_not_called()


def test_different_harmonize_field_does_not_masquerade_as_company(sample_config, tmp_path, monkeypatch):
    sample_config["profiles"] = {"issuer": {
        "extends": "business", "harmonize_field": "provider",
        "fields": {"provider": {"description": "Printed issuer."}},
        "template": "{document_date} {provider} {description}",
    }}
    harmonize = Mock(return_value="Canonical Issuer")
    monkeypatch.setattr(cli, "harmonize_company_name", harmonize)
    raw = {
        "document_date": "bad date", "company_name": "Raw company",
        "document_type": "", "description": "12,13", "provider": "Raw issuer",
    }
    result = run_file(tmp_path, monkeypatch, sample_config, "issuer", raw)
    assert result["company"] == "Raw company"
    assert result["doc_type"] == ""
    assert result["date"] is None
    assert result["fields"] == raw
    assert result["new_name"] == "00000000 Canonical Issuer 12,13.pdf"
    assert harmonize.call_args.args[0] == "Raw issuer"
    harmonize.assert_called_once()


def test_academic_added_legacy_names_map_by_presence(sample_config, tmp_path, monkeypatch):
    sample_config["profiles"] = {"academic": {"fields": {
        "company_name": {"description": "Printed company."},
        "document_type": {"description": "Printed category."},
    }}}
    result = run_file(tmp_path, monkeypatch, sample_config, "academic", {
        "document_date": "06.09.2026", "first_author_surname": "Smith",
        "journal_name": "", "title": "A Study", "company_name": "<>Raw", "document_type": "",
    })
    assert result["company"] == "<>Raw"
    assert result["doc_type"] == ""
    assert result["date"] == "2026-09-06"


@pytest.mark.parametrize("mode,filename,status,has_fields", [
    ("no-content", "source.pdf", "failed", False),
    ("no-metadata", "source.pdf", "failed", False),
    ("provider-error", "source.pdf", "failed", False),
    ("rename-error", "source.pdf", "failed", True),
    ("dry", "20260906 ACME ER 12,13.pdf", "skipped", True),
])
def test_failure_and_skip_keep_selected_profile_and_available_raw_fields(
    sample_config, tmp_path, monkeypatch, mode, filename, status, has_fields,
):
    monkeypatch.setattr(cli, "harmonize_company_name", lambda value, path, config: value)
    raw = {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "ER", "description": "12,13"}
    result = run_file(tmp_path, monkeypatch, sample_config, "business", raw, mode=mode, filename=filename)
    assert result["profile"] == "business"
    assert result["fields"] == (raw if has_fields else {})
    assert result["status"] == status
    assert result["new_name"] is None
    assert result["new_path"] is None
    assert (result["company"], result["date"], result["doc_type"]) == (
        ("ACME", "2026-09-06", "ER") if has_fields else (None, None, None)
    )


def test_result_fields_have_independent_empty_dicts():
    first = cli.FileResult(file="first.pdf", status="failed", profile="academic")
    second = cli.FileResult(file="second.pdf", status="failed", profile="business")
    first.fields["title"] = "A Study"
    assert second.to_dict()["fields"] == {}
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_pipeline.py -v`. Exact nodes are `::test_business_raw_survives_aliases_unicode_and_truncation`, `::test_academic_bypasses_alias_loading_and_keeps_legacy_date`, `::test_different_harmonize_field_does_not_masquerade_as_company`, `::test_academic_added_legacy_names_map_by_presence`, `::test_failure_and_skip_keep_selected_profile_and_available_raw_fields`, and `::test_result_fields_have_independent_empty_dicts`, each prefixed with `tests/test_profile_pipeline.py`.
- [ ] Add fields to the **existing** result container, not a new class:

```python
profile: Optional[str] = None
fields: dict[str, str] = field(default_factory=dict)
```

Initialize every per-file rename result with `profile=profile_id` before extraction. After successful validated extraction, immediately store `result.fields = metadata.model_dump().copy()` before any later operation can fail. Build a separate working dict. Only call existing company harmonization when `profile['harmonize_field']` is non-null, and apply it to just that working field. Academic must bypass even alias loading/existence requirements. Parse date independently. Set `company` from raw `company_name` when present, except use its harmonized working value when it is the selected harmonization target; absent means null. Set `doc_type` from raw `document_type` by presence, including empty string; set `date` from parsed ISO date, independent of profile. These precede filename cleanup/fallback/truncation. Feed working fields into `render_filename` and its name into `rename_document`. Preserve result statuses and new-name/path nullability on skips/failures.
- [ ] Thread explicit run-context keywords through `process_pdf` and update existing direct calls in `tests/test_end_to_end.py` with generated fixtures. For old mock metadata add `description=""`; do not update old category expectations into a pretend extraction-quality test. Keep real PDF/OCR-selection and error/exit assertions.
- [ ] GREEN: `.\venv\Scripts\python.exe -m pytest tests/test_profile_pipeline.py tests/test_end_to_end.py tests/test_cli.py::TestFileResult tests/test_cli.py::TestBatchResult -v`. Expect raw values unmodified on aliases, NFC, length changes, rename error, and already-correct skip.
- [ ] Commit: `git add autorename-pdf.py tests/test_profile_pipeline.py tests/test_end_to_end.py` then `git commit -m "feat: expose raw profile fields with compatible legacy results"`.

## Task 10: Validate before processing, select once per run, and expose resolved config

**Files:** modify `autorename-pdf.py`; create `tests/test_profile_cli.py`; adapt `tests/test_cli.py` mocks to the new explicit context keywords.

- [ ] Add these CLI-boundary tests; input/output and selected model identity are observable, while private resolution scaffolding is not pinned:

```python
from copy import deepcopy
import json
from unittest.mock import Mock

import pytest
import yaml

from autorename_pdf_runner import _mod as cli
from _pdf_utils import ExtractionResult
from _profiles import build_metadata_model


def call_cli(argv, capsys):
    args = cli.build_parser().parse_args(argv)
    handler = cli._handle_config if args.subcommand == "config" else cli._handle_rename
    with pytest.raises(SystemExit) as stopped:
        handler(args, "json")
    return stopped.value.code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("invalid", [
    pytest.param("profile: missing\n", id="unknown-selected"),
    pytest.param("profile: ' business'\n", id="malformed-selected"),
    pytest.param("profiles: null\n", id="null-container"),
    pytest.param("profiles: []\n", id="list-container"),
    pytest.param("profiles: {unused: {extends: missing}}\n", id="invalid-unselected"),
    pytest.param("profiles: {business: {fields: {document_date: null}}}\n", id="deleted-date"),
    pytest.param("profiles: {business: {template: '{description!r}'}}\n", id="invalid-placeholder"),
    pytest.param("profiles: {business: {intro: '{unknown}'}}\n", id="invalid-prompt-placeholder"),
    pytest.param("profiles: {business: null}\n", id="null-definition"),
    pytest.param("profile: business\nprofile: academic\n", id="duplicate-yaml"),
    pytest.param("filename: '{document_date}'\n", id="unsupported-top-level-filename"),
])
@pytest.mark.parametrize("command", ["rename", "validate"])
def test_invalid_config_exits_3_before_content_provider_or_mutation(
    tmp_path, monkeypatch, capsys, invalid, command,
):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"keep")
    config = tmp_path / "test-config.yaml"
    contents = "config_version: 2\nai: {provider: ollama, model: test}\n" + invalid
    config.write_text(contents, encoding="utf-8")
    content = Mock(side_effect=AssertionError("content called for invalid config"))
    provider = Mock(side_effect=AssertionError("provider called for invalid config"))
    rename = Mock(side_effect=AssertionError("rename called for invalid config"))
    batch = Mock(side_effect=AssertionError("undo batch created for invalid config"))
    monkeypatch.setattr(cli, "extract_content", content)
    monkeypatch.setattr(cli, "extract_metadata", provider)
    monkeypatch.setattr(cli, "rename_document", rename)
    monkeypatch.setattr(cli, "generate_batch_id", batch)
    argv = ["rename", str(source)] if command == "rename" else ["config", "validate"]
    code, payload = call_cli(argv + ["--config", str(config), "--output", "json"], capsys)
    assert code == 3
    if command == "validate":
        assert payload["valid"] is False
        assert any(issue["level"] == "error" for issue in payload["issues"])
    else:
        assert payload["error_type"] == "config_error"
    for operation in (content, provider, rename, batch):
        operation.assert_not_called()
    assert source.read_bytes() == b"keep"
    assert config.read_text(encoding="utf-8") == contents
    assert not (tmp_path / ".autorename-log.json").exists()


@pytest.mark.parametrize("override,selected,expected", [
    (None, "receipts", "20260906 ACME 12,13.pdf"),
    ("academic", "academic", "20260906 Smith A Study.pdf"),
])
def test_cli_selection_builds_one_model_per_batch_without_config_write(
    sample_config, tmp_path, monkeypatch, capsys, override, selected, expected,
):
    config = deepcopy(sample_config)
    config["profile"] = "receipts"
    config["profiles"] = {"receipts": {
        "extends": "business", "template": "{document_date} {company_name} {description}",
        "harmonize_field": None,
    }}
    path = tmp_path / "test-config.yaml"
    original = yaml.safe_dump(config, sort_keys=False)
    path.write_text(original, encoding="utf-8")
    sources = [tmp_path / "one.pdf", tmp_path / "two.pdf"]
    for source in sources:
        source.write_bytes(b"keep")
    monkeypatch.setattr(cli, "extract_content", Mock(return_value=ExtractionResult(
        text="Printed content", quality_score=1, page_count=1, sources=["text"],
    )))
    models = []
    def extract(extraction, loaded_config, *, profile, metadata_model):
        models.append(metadata_model)
        values = {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "ER", "description": "12,13", "first_author_surname": "Smith", "journal_name": "", "title": "A Study"}
        return metadata_model.model_validate({name: values[name] for name in profile["fields"]})
    monkeypatch.setattr(cli, "extract_metadata", extract)
    factory = Mock(wraps=build_metadata_model)
    monkeypatch.setattr(cli, "build_metadata_model", factory)
    argv = ["rename", *(str(source) for source in sources), "--dry-run", "--config", str(path), "--output", "json"]
    if override is not None:
        argv += ["--profile", override]
    code, payload = call_cli(argv, capsys)
    assert code == 0
    assert (payload["total"], payload["renamed"], payload["skipped"], payload["failed"]) == (2, 2, 0, 0)
    assert payload["dry_run"] is True
    assert [item["profile"] for item in payload["files"]] == [selected, selected]
    assert [item["new_name"] for item in payload["files"]] == [expected, expected]
    assert len(models) == 2 and models[0] is models[1]
    factory.assert_called_once()
    assert path.read_text(encoding="utf-8") == original
    assert all(source.read_bytes() == b"keep" for source in sources)
    assert not (tmp_path / ".autorename-log.json").exists()


def test_unknown_cli_profile_is_config_error(sample_config, tmp_path, capsys, monkeypatch):
    path = tmp_path / "test-config.yaml"
    path.write_text(yaml.safe_dump(sample_config), encoding="utf-8")
    process = Mock(side_effect=AssertionError("must not process"))
    monkeypatch.setattr(cli, "process_pdf", process)
    code, payload = call_cli(["rename", "absent.pdf", "--profile", "Academic", "--config", str(path)], capsys)
    assert code == 3
    assert payload["error_type"] == "config_error"
    process.assert_not_called()


def test_config_show_includes_resolved_selection_and_keeps_redaction(sample_config, tmp_path, capsys):
    sample_config.update(profile="academic", profiles={"academic": {"intro": "Custom academic intro."}})
    sample_config["ai"]["api_key"] = "secret"
    path = tmp_path / "test-config.yaml"
    original = yaml.safe_dump(sample_config, sort_keys=False)
    path.write_text(original, encoding="utf-8")
    code, payload = call_cli(["config", "show", "--config", str(path)], capsys)
    assert code == 0
    assert payload["profile"] == "academic"
    assert payload["resolved_profile"]["intro"] == "Custom academic intro."
    assert payload["resolved_profile"]["harmonize_field"] is None
    assert list(payload["resolved_profile"]["fields"]) == ["document_date", "first_author_surname", "journal_name", "title"]
    assert payload["ai"]["api_key"] == "***"
    assert payload["profiles"] == sample_config["profiles"]
    assert path.read_text(encoding="utf-8") == original
```

- [ ] RED: `.\venv\Scripts\python.exe -m pytest tests/test_profile_cli.py::test_invalid_config_exits_3_before_content_provider_or_mutation tests/test_profile_cli.py::test_cli_selection_builds_one_model_per_batch_without_config_write tests/test_profile_cli.py::test_unknown_cli_profile_is_config_error tests/test_profile_cli.py::test_config_show_includes_resolved_selection_and_keeps_redaction -v`.
- [ ] Add `rename_parser.add_argument("--profile", default=None, help="Extraction profile id (overrides config for this run)")`. Apply CLI provider/model/OCR overrides as before, then select with `select_profile(config, getattr(args, "profile", None))` and build its model once, **before** collecting/processing PDFs, generating undo batches, or provider calls. `getattr` preserves existing direct-handler callers that construct argparse namespaces without the new optional property. Pass the resolved id/definition/type as explicit keyword arguments to every `process_pdf`. Do not mutate the loaded profile selection to implement an override and do not build a model inside the file loop.
- [ ] Integrate profile resolution into `_validate_config`, including all unselected declared profiles and configured selection. Retain the existing issue structure `{field, level, message}` and provider checks; append a profile location/error when resolution raises `ValueError`. Reject unsupported top-level `filename` rather than treating it as an active override. Translate malformed loaded config/profile/CLI ids into `config_error`, exit 3. A CLI override is the effective selected id for rename; it must still validate all definitions. Do not classify an unknown selected id as argparse usage error or no-files error.
- [ ] For `config show`, validate/select, deep-copy/redact existing config, set output `profile` and output-only `resolved_profile`; retain `config_path`. For `config validate`, keep `{valid, issues}` and exit 3 when any declared profile is invalid. Ensure errors are handled at the CLI config boundary, not swallowed into per-file failures. No serialization of generated types and no writeback to disk.
- [ ] GREEN: `.\venv\Scripts\python.exe -m pytest tests/test_profile_cli.py tests/test_profile_config.py tests/test_cli.py tests/test_end_to_end.py -v`. Update existing mocks for the explicit run context without removing checks of envelope/status/exit behavior.
- [ ] Commit: `git add autorename-pdf.py tests/test_profile_cli.py tests/test_cli.py tests/test_end_to_end.py` then `git commit -m "feat: select and validate extraction profiles at CLI boundaries"`.

## Task 11: Conditional GUI compatibility typing

**Files:** only if necessary, `gui/src/lib/sidecar.ts`, `gui/src/lib/sidecar.test.ts`.

Current inspected code already renders `f.result?.new_name` in `gui/src/views/files.ts`, casts sidecar JSON without stripping additive properties, allows nullable legacy keys, and spreads cached results in `gui/src/lib/rename-cache.ts`. Therefore the default action is **no GUI diff**. Do not invent a GUI requirement to justify a test. If implementation exposes a real need to type additive properties, execute this conditional type-contract cycle; otherwise record the skip and its evidence in GATES.

- [ ] Verify the above existing consumers still use `new_name`/`new_path` and tolerate older cached results; no schema editor, UI form, or display work.
- [ ] Only on the typing branch, append the following test to `gui/src/lib/sidecar.test.ts`, reusing its existing `sidecarSpy` and module mocks:

```typescript
import type { FileResult } from './sidecar';

it('accepts old cached results and preserves additive profile results', async () => {
  const old: FileResult = {
    file: 'D:/paper.pdf', status: 'renamed',
    new_name: '20260101 Smith A Study.pdf', new_path: 'D:/20260101 Smith A Study.pdf',
    error: null, warnings: [], company: null, date: '2026-01-01', doc_type: null,
    provider: 'ollama', model: 'test',
  };
  const current: FileResult = {
    ...old, profile: 'academic',
    fields: { document_date: '01.01.2026', first_author_surname: 'Smith', journal_name: '', title: 'A Study' },
  };
  const payload = { success: true, total: 2, renamed: 2, skipped: 0, failed: 0,
    dry_run: true, files: [old, current] };
  sidecarSpy.mockReturnValue({
    stderr: { on: vi.fn() },
    execute: vi.fn(async () => ({ code: 0, stdout: JSON.stringify(payload), stderr: '' })),
  });
  const { renamePdfs } = await import('./sidecar');
  await expect(renamePdfs(['D:/paper.pdf'], { dryRun: true })).resolves.toEqual(payload);
});
```

- [ ] RED on this branch: `pnpm -C gui typecheck` must fail for the excess `profile`/`fields` properties before the type change. Do not call an already-passing runtime test RED; the changed contract is compile-time acceptance.
- [ ] Add only these optional properties to the existing `FileResult` interface:

```typescript
profile?: string;
fields?: Record<string, string>;
```

- [ ] GREEN: `pnpm -C gui typecheck` then `pnpm -C gui test:run`. Both must pass; older objects lacking both keys remain accepted, nullable legacy properties remain nullable, previews still use returned names. No Tauri E2E.
- [ ] Conditional commit: `git add gui/src/lib/sidecar.ts gui/src/lib/sidecar.test.ts` then `git commit -m "types: accept additive extraction profile results"`. If skipped, there is no commit.

## Task 12: Document the intentional default and validate examples

**Files:** `README.md`, `config.yaml.example`. This is prose/non-behavioral example work after behavioral config support is green; skip artificial RED tests per the TDD policy. Verification is executing the example config through validation and reviewing the published examples against tested contracts.

- [ ] Add the following user-facing text under a `Dynamic extraction profiles` section in `README.md`; include the first paragraph in an adjacent release/migration note rather than creating release machinery:

```markdown
The default business filename now includes a fourth component:
`20260906 ACME ER 12,13.pdf`. ER (Eingangsrechnung) and AR (Ausgangsrechnung)
already identify invoice types. The description copies the printed final total;
if no total is printed, the filename is `20260906 ACME ER.pdf`. Currency is kept
only when printed with the amount. Non-invoices copy an explicit subject/title
in its original language instead of generating a summary.

Existing v2 configs still load, but generated names and prompts intentionally
change. Remove old prompt extensions that append the amount to document_type
when adopting this default, or an amount may appear twice (`ER 12,13 12,13`).
Your config and prompt_extension are never silently rewritten or filtered.

Set `profile: business` or `profile: academic` in config. A run can override
that selection with `rename <path> --profile academic` without saving config.
Academic filenames use date, first author's surname, venue, and full printed
title with spaces; absent venue disappears. A printed year alone normalizes
to January 1 of that year, not evidence of the publication day.

All extraction fields are required strings; missing values are empty strings.
JSON adds `profile` and raw `fields` to each file result. These values survive
filename sanitization, harmonization, and truncation. Templates contain field
names in braces, omit `.pdf`, and cannot contain paths. Escape literal braces
as `{{` and `}}`. `truncate_field` names the non-date template field shortened
first; `harmonize_field` optionally selects one company/issuer field for the
existing company aliases. Academic does not use company aliases.
```

- [ ] Put these complete, mutually alternative examples in the README. Tell users to merge a chosen overlay into their existing single `profiles` mapping; duplicate YAML keys are errors. The first restores the three-component shape with **both** required settings, but does not restore generated non-invoice summaries:

```yaml
profiles:
  business:
    template: "{document_date} {company_name} {document_type}"
    truncate_field: company_name
```

```yaml
profiles:
  business:
    fields:
      invoice_id:
        description: "Copy the printed invoice number exactly, without an Invoice or Rechnung label. Empty if absent or the document is not an invoice."
    template: "{document_date} {company_name} {document_type} {description} {invoice_id}"
    truncate_field: description
```

Explain that the latter retains the inherited amount in description and produces `20260906 ACME ER 12,13 12345.pdf`. Include these complete receipts inheritance and standalone two-field examples:

```yaml
profile: receipts
profiles:
  business:
    fields:
      city:
        description: "City in the counterparty address, as printed. Empty if absent."
  receipts:
    extends: business
    intro: "You are naming a purchase receipt."
    fields:
      document_type: null
      description: null
      short_title:
        description: "Copy a purchase title explicitly printed on the receipt. Empty if absent."
    template: "{document_date}_{company_name}_{city}_{short_title}"
    truncate_field: short_title
    harmonize_field: company_name
```

```yaml
profile: notes
profiles:
  notes:
    fields:
      document_date:
        description: "Copy the printed date as dd.mm.YYYY. Empty if absent."
      title:
        description: "Copy the explicit title verbatim. Empty if absent."
    template: "{document_date} {title}"
    truncate_field: title
```

State that same-name overlays replace scalar settings, keep the order of existing fields, append new fields, and use `field: null` for deletion; date cannot be deleted and references must be repaired. Custom `extends` can name a built-in or an earlier custom profile and inherits the parent's user overlay. There is no separate profile file directory. `config validate` checks all profiles, `config show` includes resolved selection, and `output.date_format` applies across profiles.

- [ ] Add the following active defaults/comments to `config.yaml.example`, remove its superseded amount-in-type prompt example, and leave `prompt_extension: ""`:

```yaml
# Extraction profile; rename --profile overrides this for one run.
profile: business
# Overlay built-ins or declare custom profiles here; see README examples.
profiles: {}

# Optional global instructions, appended verbatim to the profile prompt.
# Business description already contains a printed invoice total.
# Remove older amount-appending document_type instructions to avoid duplicates.
prompt_extension: ""
```

Do not duplicate its existing prompt_extension key. Update invoice-code comments to the spec's incoming/outgoing meanings and align the README's opening filename example and CLI help prose with the fourth default component. CLI help-only text changes may be included in this task; no prose-presence tests. Include both opt-out settings and the optional invoice-id overlay as comments in the example config or explicit nearby README references, with the behavior and exact outputs shown above.
- [ ] Verify:

```powershell
.\venv\Scripts\python.exe autorename-pdf.py config validate --config config.yaml.example --output json
.\venv\Scripts\python.exe -m pytest tests/test_profile_config.py tests/test_profiles.py tests/test_profile_filenames.py -v
```

Expected exit 0 with `valid: true` (existing placeholder-company warnings are allowed) and green behavior tests. Review all YAML examples for a single profiles mapping, correct truncate references, amount semantics, and no accidental real keys. Do not add grep/string-presence tests on this text. No personal config writes.
- [ ] Commit: `git add README.md config.yaml.example` (plus `autorename-pdf.py` only if its help text changed), then `git commit -m "docs: explain dynamic profiles and printed-amount filenames"`.

## Empirical acceptance protocol (explicit live authorization required)

This protocol checks the extraction instructions already implemented/tested through deterministic contracts. It is not a substitute for RED/GREEN or a reason to change the locked fields/templates. During implementation, add `tests/test_live_profiles.py` below, but collect/run it **without** `--run-live` first and expect skips. These are empirical acceptance tests, not fabricated RED tests. No provider requests are authorized by this plan alone.

```python
import pytest

from _ai_processing import extract_metadata_from_text
from _document_processing import render_filename
from _profiles import build_metadata_model, select_profile


@pytest.mark.live
@pytest.mark.parametrize("config_fixture", [
    pytest.param("openai_config", marks=pytest.mark.openai, id="openai"),
    pytest.param("anthropic_config", marks=pytest.mark.anthropic, id="anthropic"),
    pytest.param("ollama_config", marks=pytest.mark.ollama, id="ollama"),
])
@pytest.mark.parametrize("profile_id,source,expected,filename", [
    pytest.param("business", "INVOICE\nFrom: ACME\nBill to: Owner\nInvoice date: 06.09.2026\nInvoice number: 12345\nSubtotal: 10,00\nTax: 2,13\nFinal total including tax: 12,13\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "IN", "description": "12,13"}, "20260906 ACME IN 12,13.pdf", id="incoming-final-total"),
    pytest.param("business", "INVOICE\nFrom: Owner\nBill to: ACME\nInvoice date: 06.09.2026\nInvoice number: 12345\nFinal total including tax: 1.234,56\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "OUT", "description": "1.234,56"}, "20260906 ACME OUT 1.234,56.pdf", id="outgoing-grouped-total"),
    pytest.param("business", "INVOICE\nFrom: ACME\nBill to: Owner\nInvoice date: 06.09.2026\nInvoice number: 12345\nFinal total including tax: EUR 12,13\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "IN", "description": "EUR 12,13"}, "20260906 ACME IN EUR 12,13.pdf", id="printed-currency"),
    pytest.param("business", "INVOICE\nFrom: ACME\nBill to: Owner\nInvoice date: 06.09.2026\nInvoice number: 12345\nItem: consultation\nQuantity: 2\nUnit price: 6,00\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "IN", "description": ""}, "20260906 ACME IN.pdf", id="no-total-no-calculation-or-id"),
    pytest.param("business", "Letter\nFrom: ACME\nTo: Owner\nDate: 06.09.2026\nSubject: Terminbestätigung\nIhr Termin findet nächste Woche statt.\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "Letter", "description": "Terminbestätigung"}, "20260906 ACME Letter Terminbestätigung.pdf", id="verbatim-original-language-subject"),
    pytest.param("academic", "Untersuchung der Netze - Methoden und Ergebnisse\nAlice Smith, Bob Jones\nPublication year: 2026\nAbstract: We study networks.\n", {"document_date": "01.01.2026", "first_author_surname": "Smith", "journal_name": "", "title": "Untersuchung der Netze - Methoden und Ergebnisse"}, "20260101 Smith Untersuchung der Netze - Methoden und Ergebnisse.pdf", id="academic-year-only-full-title-no-venue"),
])
def test_live_profile_extraction(request, config_fixture, profile_id, source, expected, filename):
    config = request.getfixturevalue(config_fixture)
    config["company"]["name"] = "Owner"
    config["output"]["language"] = "English"
    config["pdf"].update(incoming_invoice="IN", outgoing_invoice="OUT")
    selected, profile = select_profile(config, profile_id)
    model = build_metadata_model(profile)
    metadata = extract_metadata_from_text(source, config, profile=profile, metadata_model=model)
    assert metadata.model_dump() == expected
    assert render_filename(selected, profile, metadata.model_dump(), config) == filename
```

- [ ] Offline gate: `.\venv\Scripts\python.exe -m pytest tests/test_live_profiles.py -v`. Expected: 18 skipped tests, zero provider calls. Commit this test file with `git add tests/test_live_profiles.py` and `git commit -m "test: add gated profile extraction acceptance cases"`.
- [ ] Only after authorization, run each requested provider's matrix:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_live_profiles.py::test_live_profile_extraction --run-live --provider ollama -v
.\venv\Scripts\python.exe -m pytest tests/test_live_profiles.py::test_live_profile_extraction --run-live --provider openai -v
.\venv\Scripts\python.exe -m pytest tests/test_live_profiles.py::test_live_profile_extraction --run-live --provider anthropic -v
```

The existing `ollama_config` uses `OLLAMA_MODEL` or `qwen3:4b`; record the actual model and verify the academic case on an installed small model. Do not pull models or broaden live calls implicitly. Example exact node: `tests/test_live_profiles.py::test_live_profile_extraction[academic-year-only-full-title-no-venue-ollama]`. Native OpenAI/Anthropic tests above exercise real parse acceptance; image-only/combined transport remains covered by the mocked matrix and any already-authorized existing live vision cases. Record actual model, raw results, failures, and skips. A missing provider/model is an empirical gate limitation, not an unresolved product decision.

## Final gates and handoff

- [ ] Run once after the last behavioral change:

```powershell
.\venv\Scripts\python.exe -m ruff check .
.\venv\Scripts\python.exe -m pytest tests/ -v --cov --cov-report=term-missing
```

Expected: lint clean, all mocked tests pass, live tests skip without authorization. Inspect the coverage report: `_document_processing.py` and `_utils.py` must each remain above 80%; verify the new rendering/date/harmonization branches are exercised rather than relying on a whole-repo average. `_profiles.py` must also exceed 80% with the new validation/resolution tests. Add focused behavioral cases only for demonstrated uncovered branches; do not add assertion-free scaffold tests. Avoid running the same test file twice in one gate command if class and file selectors overlap.
- [ ] If GUI typing changed, require both `pnpm -C gui typecheck` and `pnpm -C gui test:run`. Otherwise record: “GUI unchanged: existing preview uses new_name; sidecar JSON and cached spreads tolerate additive properties and nullable legacy metadata.”
- [ ] Review the final diff against the locked spec: exactly four built-in fields each; amount/subject instructions exact; no fixed metadata class or custom BaseModel; generated required strict string schema; no alias access for academic; only company-shaped selected aliases; all 16 named filename cases; selected profile/raw JSON on failures/skips; unmodified config files; no OCR/provider/retry regressions; no new profile data assets or loader. This is manual implementation review, not a new source-scanning test suite.
- [ ] Verify `build.py` needs no profile YAML data entry: the imported `_profiles.py` is ordinary Python code. No distribution rebuild or PowerShell testing infrastructure is required to prove an absent asset change; if packaging imports are changed for a concrete reason, validate that change with the existing project build workflow.
- [ ] Run `git diff --check` and `git status --short`; stage only explicit task files. Never stage private configs, the pre-existing spec, credentials, venv, or generated output. Never push. Report test results and any empirically unverified live checks; do not mark skipped live quality tests as verified.

Coverage map for self-review:

| Binding requirement | Implementation/verification |
|---|---|
| Fresh plain built-ins, configured-company instruction, field ordering, overlays/extends/null-delete, nine fields | Tasks 1–2; built-in wording reviewed against spec |
| Strict config/profile/field grammar, duplicate YAML, env-before-profile interpolation, no writeback | Tasks 2–3, 10 |
| Strict required real string properties, no extras, schema/prompt agreement and unchanged extension | Tasks 4–5 |
| Native OpenAI/Anthropic kwargs and instructor modes for text/image/combined | Task 5 plus retained native/mode/retry suites |
| Printed invoice totals, absent totals, currency, original subject, academic year/title semantics | Task 6 table and gated empirical protocol |
| Every table row, separator precedence, literal/escaped braces, Unicode/value punctuation | Tasks 6–7 |
| Explicit repeated-field truncation, exhausted Unknown, final hard cut, 244-character reservation | Tasks 7–8 |
| Collision, dry-run, skip, retry, all-skipped batch, path-based undo across profiles | Task 8 and existing suites |
| Raw JSON retention and independent nullable legacy mapping; company-shaped harmonization only | Task 9 |
| Effective CLI precedence, all-profile validation before calls/mutation, one model per batch, redacted show | Task 10 |
| Additive GUI compatibility only when required | Task 11 conditional typecheck/Vitest branch |
| Default migration, both opt-out settings, optional invoice id, superseded prompt recommendation | Task 12 and Task 7 renderer tests |
| No profile YAML assets; mocked tests/lint and business coverage; live authorization | Final gates and empirical protocol |

TDD exceptions to report in GATES: setup has no product behavior; documentation/example text gets config validation and manual review, not prose-presence tests; the GUI branch is skipped unless typing is needed (compiler RED when taken); live acceptance tests are gated empirical checks of implemented behavior. No planning decisions remain open.
