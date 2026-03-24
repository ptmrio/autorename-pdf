# AutoRename-PDF

PDF auto-renamer using AI + OCR. Extracts company name, date, and document type from PDFs, renames to `YYYYMMDD COMPANY DOCTYPE.pdf`.

## Development Setup

**Always use a virtual environment.** Never install dependencies globally.

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for testing
```

## Commands

All commands assume the venv is activated.

- **Run**: `python autorename-pdf.py [options] <files_or_folders>`
- **Dry run**: `python autorename-pdf.py --dry-run <files_or_folders>`
- **Undo**: `python autorename-pdf.py --undo`
- **Test**: `pytest tests/ -v --cov`
- **Build EXE**: `python build.py`
- **Install deps**: `pip install -r requirements.txt`

## AI Tool Integration

- **Skill (dev)**: `/rename-pdfs <path>` — Python source, requires venv. For development and macOS/Linux.
- **Skill (prod)**: `/rename-pdfs-exe <path>` — compiled EXE, Windows only. For production/automation.
- Both skills dry-run first, then ask for confirmation before renaming.
- **CLI JSON mode**: `python autorename-pdf.py rename <path> --output json`
- **Exit codes**: 0=success, 1=error, 2=usage, 3=config, 4=no files, 5=partial, 10=provider, 11=auth
- **Subcommands**: `rename`, `undo`, `config show`, `config validate`
- **Primary usage**: GUI app (Tauri) or Windows context menu via compiled EXE from release ZIP.

## Architecture

Functional Python (no classes). Modules prefixed with `_` are internal:

| Module | Purpose |
|--------|---------|
| `autorename-pdf.py` | Entry point, CLI (argparse), orchestration |
| `_ai_processing.py` | Multi-provider AI via instructor, structured output (Pydantic) |
| `_pdf_utils.py` | Text extraction (pdfplumber), image rendering (pypdfium2), PaddleOCR bridge |
| `_paddleocr_bridge.py` | Subprocess bridge script for PaddleOCR venv |
| `_document_processing.py` | Company harmonization (rapidfuzz), renaming, undo log |
| `_config_loader.py` | YAML v2 config loading, schema validation, defaults |
| `_utils.py` | Filename validation, constants |

## Key Rules

- **NEVER commit `config.yaml`** — contains API keys. Only commit `config.yaml.example`.
- **NEVER commit `harmonized-company-names.yaml`** — user-specific data. Only commit the `.example`.
- Platform: Windows-only (context menu EXE via PyInstaller)
- Config: YAML-based (`config.yaml`), v2 schema — see `config.yaml.example`
- Python 3.11+, type hints encouraged
- Company name matching uses Jaro-Winkler similarity (rapidfuzz library)
- Date parsing uses dateparser with DMY locale
- OCR: PaddleOCR via isolated subprocess venv (optional, installed by setup.ps1)

## AI Providers

Supports 5 providers via `ai.provider` config key:

| Provider | SDK | Notes |
|----------|-----|-------|
| `openai` | openai (native) | Default |
| `anthropic` | anthropic (native) | Uses `instructor.from_anthropic()` |
| `gemini` | openai (base_url) | Google's OpenAI-compatible endpoint |
| `xai` | openai (base_url) | Grok models |
| `ollama` | openai (base_url) | Local models, no API key needed |

All providers use `instructor` for structured Pydantic output. Anthropic uses native SDK because their OpenAI compat layer ignores structured output.

## Three-Tier Extraction

1. **Tier 1**: pdfplumber text extraction (free, instant)
2. **Tier 2a**: PaddleOCR via subprocess (free, ~2-5s/page, if installed)
3. **Tier 2b**: Vision mode — page images sent to LLM (~$0.0001/page)

Controlled by `pdf.ocr` (false/true/"auto") and `pdf.vision` (false/true/"auto").

## Environment Variables

Config values support `${VAR_NAME}` syntax for environment variable references.
A `.env` file next to `config.yaml` is loaded automatically via `python-dotenv`.

## Testing

Tests in `tests/` using pytest. Unit tests mock AI API calls. Live integration tests (`--run-live`) call real providers.
Business logic (harmonization, date parsing, filename generation) should have >80% coverage.

### Live Tests

```bash
pytest tests/ --run-live -v                       # All available providers
pytest tests/ --run-live --provider ollama -v      # Free, local only
pytest tests/ --run-live --provider openai -v      # OpenAI only
pytest tests/ --run-live --provider anthropic -v   # Anthropic only
```

API keys are loaded from `.env` file (see `.env.example`). Ollama tests require Ollama running locally.

## Build & Distribution

`build.py` creates signed EXE via PyInstaller, packages as ZIP with setup.ps1.
`setup.ps1` installs context menu entries and optionally PaddleOCR (~500MB).

**GUI platform support**: Windows only. The Tauri GUI invokes the CLI as a sidecar binary (compiled EXE). Cross-platform would require PyInstaller builds for each target OS — the TypeScript/Rust code is already platform-agnostic.
