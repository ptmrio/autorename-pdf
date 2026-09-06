# Profile-based dynamic extraction

Date: 2026-09-06

Status: locked for implementation

This is the binding product specification. It retains the Astra architecture decision dated 2026-09-06 and supersedes that decision's invoice-description semantics with the owner's correction: invoice descriptions contain the printed total amount, not an invoice title or number.

## Scope and defaults

V1 supports selecting and configuring extraction profiles through CLI and the existing v2 `config.yaml`. A profile defines named extraction fields, their instructions, and filename rendering. Built-ins are a module-level plain dict in `_profiles.py`; users overlay or extend them in config. No shipped or user `profiles/*.yaml` discovery and no additional PyInstaller data assets.

The default profile is `business`. Its default filename is intentionally changed from three components to four:

`20260906 ACME ER 12,13.pdf`

ER means Eingangsrechnung (incoming invoice); AR means Ausgangsrechnung (outgoing invoice). They already identify the document type. `ER Invoice 12345` is not the default behavior. If no printed amount exists, the result is `20260906 ACME ER.pdf`.

Non-goals: marketplace, plugin framework, automatic profile detection, per-document profile switching within a run, GUI profile selector or schema editor, mandatory GUI dynamic-fields display, journal alias maps, generic per-field alias framework, new extraction value types, or changes to OCR/vision selection. pdfplumber always runs; OCR and vision remain independent. The Python CLI remains cross-platform; GUI and Explorer integration remain Windows-only.

## Configuration contract

Only two new top-level keys are introduced:

```yaml
profile: business
profiles: {}
```

`rename --profile <id>` overrides `profile` for that run without writing config. An omitted config selection defaults to `business`. Profile ids are nonempty, case-sensitive strings without surrounding whitespace; the selected id must exist. No automatic fallback from an unknown id. Existing v2 config, environment interpolation, provider settings, and output settings remain applicable; no config-version bump.

Each profile accepts only these keys:

| Key | Contract |
|---|---|
| `intro` | String; defaults to empty for a standalone custom profile. |
| `fields` | Ordered mapping `field_id: {description: "..."}`. Each description is a nonempty string. In an overlay, `field_id: null` deletes an inherited field. |
| `template` | Nonempty basename template, without `.pdf`; required after resolution. This is the only filename-template setting. |
| `truncate_field` | Required field id; must reference an existing non-date field appearing in the template. |
| `harmonize_field` | Existing non-date field id representing a company/issuer, or `null`; defaults to `null` for standalone profiles. |
| `extends` | Parent profile id, permitted only on custom profiles. Single inheritance only. |

There are no field lists, `extra_fields`, arbitrary extras bags, positional `field_1` schema design, field type flags, or top-level `filename` override. All extracted values are required strings; an unavailable value is the empty string, not a missing property or null. There is no application-level field-count cap; provider schema limits still apply.

Resolution is deterministic:

1. Materialize fresh copies of both built-in dicts, including the default company instruction conditional described below. Never mutate shared defaults.
2. Apply same-name config overlays to built-ins, regardless of their position in `profiles`.
3. Resolve custom profiles in YAML declaration order. `extends` may name either resolved built-in or an earlier custom profile. Inherit the resolved parent, including its user overlay. Reject unknown parents, custom forward references, self-inheritance, and cycles. Built-in overlays cannot use `extends`.
4. A standalone custom profile supplies `fields`, `template`, and `truncate_field`. Optional keys receive their standalone defaults. Scalar keys replace wholesale; `harmonize_field: null` disables harmonization.
5. An existing field id replaces its description without changing position; new ids append in YAML order. `field: null` deletes; deleting a nonexistent field is an error. Full replacement uses explicit deletions and additions, with no replace-all operator.
6. Validate each final resolved profile, not an incomplete overlay. Deleting a field requires fixing every template, truncation, and harmonization reference to it. `document_date` must exist in every resolved profile and cannot be deleted; its extraction description can be overridden.

Field ids must be public Python identifiers accepted as Pydantic field names: reject Python keywords, leading underscores, and collisions with BaseModel machinery or protected namespaces. Duplicate YAML keys are errors rather than last-value-wins, including duplicate profile and field ids. Unknown profile/field-spec keys, null profile definitions, malformed values, invalid references, and unsupported placeholders are config errors. Validate before provider calls or file mutation and return config exit code `3`. `config validate` checks all declared profiles; `config show` exposes the selected id and its resolved definition alongside existing config, retaining secret redaction. A rename run validates configuration and the CLI-selected id before processing.

## Built-ins: YAML-equivalent content

These blocks define Python-dict content, not files to package. Their field instructions are normative. The business company instruction shown is the variant when `company.name` is nonempty.

```yaml
business:
  intro: >-
    Extract metadata for naming a business document. Separate the document
    category from its printed amount or subject. Never invent missing values.
  fields:
    document_date:
      description: >-
        Find the most relevant document date, such as the invoice date or
        letter date, rather than a payment due date. Interpret the printed
        date according to the document's language and location. Return
        dd.mm.YYYY. Empty if no date is found.
    company_name:
      description: >-
        Find the counterparty company. My company name is "{company}";
        exclude my own company. Strip the legal form, such as e.U., SARL,
        GmbH, AG, Ltd, or Limited. Empty if no company is found.
    document_type:
      description: >-
        For incoming invoices, use only "{incoming_invoice}". For outgoing
        invoices, use only "{outgoing_invoice}". Do not append an amount,
        invoice number, or the words Invoice or Rechnung to either code.
        For other documents, return a short category in {language}, such as
        Letter or Contract, not a generated subject summary. Empty if unknown.
    description:
      description: >-
        For an incoming or outgoing invoice whose document_type is
        "{incoming_invoice}" or "{outgoing_invoice}", copy the printed final
        invoice total amount as-is. Prefer the explicitly labelled final
        total including tax over subtotals, tax-only amounts, or line items.
        Preserve printed decimal and grouping punctuation, for example 12,13
        or 1.234,56. Preserve currency text or symbols only when printed as
        part of that amount; never add currency words or convert currencies.
        Do not calculate a missing total. Do not include Invoice, Rechnung,
        an invoice number, or a total-label word. Empty if no total is printed.
        For non-invoices, copy the document's own explicit subject or title
        verbatim in its original language. Do not summarize, translate, or
        invent a subject, or fall back to a generic document category or
        identifying number. Empty if no subject or title is present.
  template: "{document_date} {company_name} {document_type} {description}"
  truncate_field: description
  harmonize_field: company_name

academic:
  intro: "You are naming an academic paper, preprint, or thesis."
  fields:
    document_date:
      description: >-
        Publication date in dd.mm.YYYY. Prefer publication over submission
        or revision. If only a year is printed, use 01.01 of that year.
        Empty if no date or year is found.
    first_author_surname:
      description: >-
        First author's surname only; no initials, given names, or et al.
        Empty if absent.
    journal_name:
      description: >-
        Journal or conference venue as printed, including its printed
        abbreviation. Empty when no venue is given.
    title:
      description: "Paper title as printed, in its original language. Empty if absent."
  template: "{document_date} {first_author_surname} {journal_name} {title}"
  truncate_field: title
  harmonize_field: null
```

When `company.name` is empty, materialize the default business company instruction as: `Find the main company in the document. Strip the legal form, such as e.U., SARL, GmbH, AG, Ltd, or Limited. Empty if no company is found.` A user override of this description is authoritative and does not receive the conditional text. Invoice direction retains existing business semantics using the configured own company when available; uncertain values remain empty.

Business ships exactly these four fields; invoice number is not a default field. Non-invoice subject/title is copied even if its printed wording overlaps the type; do not paraphrase or deduplicate source text. Academic ships exactly the four ids shown, preserves title and venue language, and has no default dash or company harmonization. Its year-only date convention means January 1 is a normalization convention, not evidence of the actual publication day. Do not ask the model to shorten academic titles or drop subtitles; filename truncation handles length.

## User configuration examples and compatibility

Add an invoice id while retaining the default amount in `{description}`:

```yaml
profiles:
  business:
    fields:
      invoice_id:
        description: >-
          Copy the printed invoice number exactly, without an Invoice or
          Rechnung label. Empty if absent or the document is not an invoice.
    template: "{document_date} {company_name} {document_type} {description} {invoice_id}"
    truncate_field: description
```

With total `12,13` and number `12345`, this yields `20260906 ACME ER 12,13 12345.pdf`. The inherited amount instruction stays intact. Users may instead override descriptions and templates for other preferences.

Opt out of the fourth filename component with both settings:

```yaml
profiles:
  business:
    template: "{document_date} {company_name} {document_type}"
    truncate_field: company_name
```

This restores the three-token filename shape; `description` is still extracted and available in JSON. It does not restore the former generated-summary semantics for non-invoice `document_type`; users seeking that behavior can override that field's description too. Existing configs remain syntactically valid but names and prompts are intentionally not byte-identical. No silent legacy-profile selection or automatic config rewrite.

The current example `prompt_extension` that adds an amount to `document_type` is superseded by the business `description` field. Documentation and the example config must replace that recommendation and tell existing users to remove that amount-appending instruction when adopting the new default, avoiding `ER 12,13 12,13`. Do not silently rewrite or filter users' prompt extensions. Global `prompt_extension` remains supported and appends verbatim; a user-supplied conflicting extension can still change model output.

Inheritance, replacement, and deletion require no Python edits:

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

`receipts` inherits the overlaid business date, company, and city fields, removes type and description, and adds `short_title`. `--profile academic` still selects academic's own template. A standalone profile supplies its own date and text fields with the required settings. `output.date_format: "%Y-%m-%d"` changes filename dates for whichever profile is selected.

## Extraction and prompt contract

Use functions and plain dicts. **No new Python classes or class hierarchy; `pydantic.create_model("DocumentMetadata", ...)` only for the runtime extraction model.** Replace the fixed metadata declaration with one concrete generated type per selected profile per run. Existing unrelated result containers need no class redesign.

Each configured field becomes a real named, required string property with its resolved description, not a default-valued optional property. Reject omitted properties, null/non-string values, and undeclared output properties. Use Pydantic configuration through `create_model` to forbid extras; do not introduce a custom base class. No generic bag or positional field indirection. Retain a separate raw string dictionary from validated extraction before any rendering transformations.

Pass that same concrete type on text, image-only, and combined extraction paths: OpenAI `responses.parse(text_format=...)`; Anthropic `messages.parse(output_format=...)`; instructor `response_model=...` for Gemini and xAI in TOOLS mode and Ollama in JSON mode. Existing client routing, retry behavior, provider settings, and extraction-source selection remain intact.

Prompt order is:

1. Shared preamble: `Extract the requested fields from the document content. Due to OCR text detection, the text may be noisy and contain spelling and detection errors. Handle those as well as possible.`
2. Resolved profile intro, if nonempty.
3. Ordered `field_id: description` instructions, using the same resolved descriptions as the schema.
4. Shared instruction: `Return every requested field as a string. If a value is not found, return an empty string. Do not invent missing values or return undeclared fields.`
5. Existing nonempty global `prompt_extension`, appended verbatim after a blank line.

Only profile intro and field descriptions interpolate `{company}`, `{language}`, `{incoming_invoice}`, and `{outgoing_invoice}`, from existing config settings. Support escaped literal braces; unknown names, access expressions, conversions, format specifiers, and malformed braces are config errors. Interpolation is single-pass: braces in inserted config values are text. Existing `${VAR}` environment resolution precedes profile interpolation; filename placeholders are a separate namespace. `prompt_extension` receives no profile-placeholder interpolation and does not create schema fields or filename placeholders.

## Date and filename contract

`document_date` is the single reserved date id and remains a string in extraction. Parse nonempty values through dateparser with DMY order; format parsed dates using existing `output.date_format` (default `%Y%m%d`). Empty or unparseable dates render as `00000000`, regardless of output format, and have a null legacy JSON date. Do not assign date behavior to other fields by name or inference.

Templates define a basename, without `.pdf`, supporting named `{field_id}` substitutions and literal text; `{{` and `}}` escape literal braces. Reject unknown fields, attribute/index access, conversions, format specifiers, and malformed braces. Template text cannot create a path; reject literal path separators. Sanitize extracted values and the final basename under existing filename-safety rules and Unicode normalization. Whitespace cleanup, sanitization, harmonization, formatted dates, fallbacks, and truncation never modify raw JSON `fields`.

Render from template tokens so cleanup cannot damage punctuation inside a nonempty value. Empty or unusable text values disappear, except that active profile id `business` retains `Unknown` for unusable `company_name` and `document_type` after sanitization. This special fallback does not apply to custom profiles even when they extend business. It only concerns fields that still exist; deleted fields are not recreated.

Collapse whitespace and separator-only literal runs stranded by empty substitutions. For deterministic v1 cleanup, separators are whitespace, underscore, and hyphen in template literal segments, not in extracted values. Between surviving values, collapse runs to one separator: prefer a hyphen if present, otherwise underscore, otherwise one space; a hyphen keeps one surrounding space when the contributing literal run contained whitespace. Strip stranded separator-only runs at either end. Preserve other literal text as explicit template content, subject to filename safety. Literal punctuation inside nonempty values, such as `1.234,56`, `Smith-Jones`, or a hyphenated date, is never treated as a removable separator. Use `Unknown` for the whole basename only when nothing remains after rendering and cleanup.

The table is normative. Dates are 06.09.2026 unless stated otherwise; each output includes `.pdf`.

| Template / extracted situation | Required filename |
|---|---|
| Business default; ACME, ER, printed total `12,13` | `20260906 ACME ER 12,13.pdf` |
| Business default; ACME, AR, printed total `1.234,56` | `20260906 ACME AR 1.234,56.pdf` |
| Business default; ACME, ER, printed amount `EUR 12,13` | `20260906 ACME ER EUR 12,13.pdf` |
| Business default; ACME, ER, no printed total (even if invoice number exists) | `20260906 ACME ER.pdf` |
| Business default; ACME, Letter, printed subject `Terminbestätigung` | `20260906 ACME Letter Terminbestätigung.pdf` |
| Business default; company/type unusable, description absent | `20260906 Unknown Unknown.pdf` |
| Academic default; Smith, no venue, title `A Study` | `20260906 Smith A Study.pdf` |
| `{document_date}_{first_author_surname}_{journal_name}_{title}`; Smith, venue/title absent | `20260906_Smith.pdf` |
| `{document_date} {first_author_surname} {journal_name} - {title}`; Smith, venue absent, title `A Study` | `20260906 Smith - A Study.pdf` |
| Same mixed-separator template; Smith, venue/title absent | `20260906 Smith.pdf` |
| Academic default; date format `%Y-%m-%d`, Smith-Jones, no venue, title `A Study` | `2026-09-06 Smith-Jones A Study.pdf` |
| Custom `{city} {description}`; both absent (date field exists but is not used) | `Unknown.pdf` |
| Custom extending business, default four-token template, all values empty | `00000000.pdf` |
| Academic default; all values empty | `00000000.pdf` |
| Business default; all values empty | `00000000 Unknown Unknown.pdf` |
| Business default; unparseable date, ACME, ER, `12,13` | `00000000 ACME ER 12,13.pdf` |

`truncate_field` explicitly controls length. Shorten that rendered field from the right until the 244-character basename limit is met or its value is exhausted, rerendering and cleaning separators. If a field appears repeatedly, shorten the shared rendered value for all its occurrences. Fallbacks are applied before truncation; do not reinsert an exhausted value or loop on `Unknown`. If still too long, hard-cut the rendered basename to 244 characters and remove invalid trailing punctuation. Do not introduce a second implicit truncation target. Preserve `.pdf`, current `_(n)` collision naming, current length reservation for the suffix, dry-run behavior, rename retries, already-correct skips, and path-based undo across profile changes.

## Harmonization, JSON, and GUI

`harmonize_field` selects at most one company-shaped field for the existing company-name alias file and Jaro-Winkler matching behavior. It is a semantic declaration by the profile author, not a new type system. Business selects `company_name`; a custom profile may select an actual company/issuer field such as `provider`. Academic disables harmonization and must not load or require a company alias file. No journal alias maps.

Keep the existing batch envelope, result keys, statuses, error reporting, and exit codes. Add these keys to each rename `FileResult`:

| Key | Meaning |
|---|---|
| `profile` | Selected resolved profile id, including on per-file failures or skips. |
| `fields` | All validated extracted named strings before harmonization, Unicode normalization, sanitization, date formatting, fallbacks, or truncation. Empty object before successful metadata extraction; retain populated values if a later rename fails or skips. |

Legacy metadata keys map independently from named fields; do not branch all three on profile id:

- `company`: harmonized value when `company_name` exists and is the selected harmonization field; otherwise its extracted value when present, or null when the field is absent. A differently named harmonization field does not masquerade as `company_name`.
- `date`: parsed ISO date from `document_date`, or null when missing/unparseable. Academic therefore retains a legacy date on successful parsing.
- `doc_type`: extracted `document_type` when the field exists, otherwise null. An extracted empty string remains empty.

These legacy values precede filename sanitization, fallback, and truncation. `new_name` and `new_path` retain their existing meanings and nullability. GUI previews must use returned `new_name` rather than reconstructing a name from legacy company/date/type values. The GUI can ignore the additive properties; any necessary compatibility typing must preserve nullable legacy fields and existing older cached results. V1 requires no profile-specific GUI form or display. Config-selected profiles work through the existing sidecar invocation.

For a successful default invoice, the additive payload contains `profile: "business"` and `fields` with `document_date: "06.09.2026"`, `company_name: "ACME"`, `document_type: "ER"`, and `description: "12,13"`. Its `new_name` is `20260906 ACME ER 12,13.pdf`; legacy `date` is `2026-09-06`. For academic, `company` and `doc_type` are null unless those fields were explicitly added, and raw `title` stays complete even if the filename title is truncated.

## Acceptance gates

These gates bind the later implementation. This prose-only specification does not require TDD, prompt string-presence tests, or live provider calls.

- [ ] Built-ins are plain dicts in `_profiles.py`; only `create_model` generates the extraction model; no new declared core classes, profile file loader, or packaging data assets.
- [ ] Default business has exactly date, company, type, and description. Both configured invoice codes extract a printed final total into description, preserve locale punctuation, omit invoice labels/numbers, and leave description empty when total is absent. Non-invoice subjects are verbatim; type is a short category. Demonstrate the amount, empty-total, currency, and subject cases in the table.
- [ ] Academic ids and space-separated template match this spec; first-author surname, absent venue, original-language full title, and year-only January 1 normalization work.
- [ ] Config exercises same-name overrides, field replacement/addition/deletion, standalone custom profiles, inherited user overlays, disabled harmonization, and CLI precedence without cross-profile template leakage. A valid nine-field profile is not rejected solely for field count.
- [ ] Duplicate YAML keys, unknown ids/parents, custom forward references/cycles, malformed values, invalid field ids, deleted or missing date, bad prompt/template placeholders, and dangling references fail with exit `3` before extraction or mutation. Validate resolved profiles and all declared profiles through `config validate`.
- [ ] Schema validation requires all named string properties, rejects null/non-string/extra properties, exposes descriptions, and passes the same concrete type through mocked native OpenAI/Anthropic and instructor Gemini/xAI/Ollama text, image, and combined paths. Prompt extension appends unchanged and never defines schema.
- [ ] Behavioral filename tests cover every table row, literal text/escaped braces, punctuation inside values, Unicode and unsafe values, date formatting, explicit-field truncation, repeated fields, exhausted fallback values, hard-cut fallback, collisions, dry-run, skips, retry behavior, and undo after switching profiles.
- [ ] Company aliases affect only the chosen company-shaped field. Academic bypasses alias loading. JSON raw values survive harmonization and truncation; failed/skipped files use the defined additive contract; legacy keys map independently and academic retains a parsed date. GUI previews use `new_name` and tolerate nullable legacy fields and older cached results.
- [ ] README/release notes and `config.yaml.example` explain the intentional fourth-component default, show both three-token opt-out settings and the optional `invoice_id` overlay, and replace the old amount-in-type prompt recommendation. Existing user configs are not rewritten.
- [ ] Later code changes pass project-venv lint and mocked tests, maintaining business-logic coverage above 80%; GUI compatibility changes pass pnpm typecheck/unit checks. Distribution needs no profile YAML assets. Empirical extraction checks, including an academic sample on a small Ollama model and native parse paths, run only under explicit `--run-live` authorization.

No product decisions remain open. Provider acceptance and extraction quality remain empirical implementation validation, not reasons to defer the locked schema or naming behavior.
