# README and example configs

Date: 2026-09-10

Status: approved for implementation (invoice-first; root example + `examples/`)

## Product locks

- Copied `config.yaml.example` stays invoice-first: `profile: business`, `incoming_invoice: AP`, `outgoing_invoice: AR`.
- Academic is a first-class shipped recipe, not the silent default. Switch with `profile: academic` or `rename --profile academic`.
- Runtime defaults in `_config_loader.DEFAULTS` do not change.
- Do not commit `config.yaml` or `harmonized-company-names.yaml`.
- Do not recapture README screenshots in this spec (separate playbook). Keep existing `screenshot/` paths.
- Portable ZIP stays flat: still ships `config.yaml.example`, not the `examples/` folder. Recipes live in the GitHub repo.

## Layout (GitHub convention)

| File | Role |
|------|------|
| `config.yaml.example` | One-stop copy-me file. Every supported key present. Concise comments so an LLM that has never seen the repo can configure it. Commented one-line switches for academic / German ER/AR. Pointers to `examples/` for full recipes. |
| `examples/*.yaml` | Complete, valid configs (not diffs). Copy over `config.yaml`. |
| `examples/README.md` | Index of recipes with example filenames. |
| `README.md` | SEO landing page: short prose, filename table, screenshots, quick start, then links into examples and the one-stop YAML. |

## Root example contract

Comments must document, without requiring the README:

- Copy to `config.yaml` next to the EXE/CLI.
- Business filename shape: `YYYYMMDD COMPANY AP 12,13.pdf` (amount omitted if none printed).
- Required: `ai.provider`, `ai.model`, `ai.api_key` (empty only for `ollama`), `company.name`.
- Providers: `openai`, `anthropic`, `gemini`, `xai`, `ollama` and current default/budget models.
- `${VAR}` interpolation and `.env` beside the config.
- `pdf.ocr` / `pdf.vision`: `false` / `true` / `"auto"`; pdfplumber always runs.
- PaddleOCR language/device notes.
- `profile` vs `rename --profile`; built-ins `business` and `academic`.
- `profiles: {}` overlay rules in one short comment block; do not paste receipts/notes novels here.
- `prompt_extension` is appended verbatim; do not re-append amounts.

Placeholder `your-api-key-here` and `Your Company Name` remain warnings, not errors.

## `examples/` files

| File | Active difference | Example filename |
|------|-------------------|------------------|
| `academic.yaml` | `profile: academic` | `20260101 Smith Nature Attention Is All You Need.pdf` (empty venue omitted) |
| `er-ar.yaml` | `incoming_invoice: ER` (Eingangsrechnung; not a DATEV filename standard) | `20260906 ACME ER 12,13.pdf` |
| `ollama-offline.yaml` | `provider: ollama`, empty key, `ocr: true` | same business shape, local models |
| `vision-cloud.yaml` | `vision: true`, `ocr: false`, Gemini budget model | scanned PDFs without PaddleOCR |
| `invoice-id.yaml` | business overlay adding `invoice_id` | `20260906 ACME AP 12,13 12345.pdf` |

Each file is a full v2 config so `config validate --config <file>` returns `valid: true` (warnings allowed).

## README shape

Keep: badges, Windows ZIP path, GUI/CLI screenshots, Explorer notes, Ollama install, macOS/Linux clone, support, MIT.

Cut into examples or the YAML: long profile-merge essays, duplicate API-key methods, duplicate OCR tables, receipts/notes custom-profile walkthroughs.

Target: adequately sized (roughly half the current ~640 lines), example-led, keyword-rich first screen (AI PDF rename, invoices, OCR, Windows GUI, academic papers, Ollama). Do not brand ER/AR as DATEV.

Developer commands stay in a collapsed section; `AGENTS.md` remains the agent source of truth.

## Pointers to update

- `AGENTS.md` sources-of-truth table: add `examples/`.
- `CLAUDE.md`: config still `config.yaml.example`; mention `examples/` for recipes.
- `.claude/skills/build/SKILL.md`: ZIP still does not include `examples/`.

## Verification

- Pytest contract: every shipped `config.yaml.example` and `examples/*.yaml` loads and validates with no errors.
- Live CLI: `config validate --config <path> --output json` for each file.
- Astra logical review of README + examples against schema and CLI (no GUI walk).
