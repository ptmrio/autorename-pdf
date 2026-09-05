# AutoRename-PDF

PDF auto-renamer using AI + OCR. Output: `YYYYMMDD COMPANY DOCTYPE.pdf`.

Be concise. Smallest correct diff. Always use the project venv — never install Python deps globally.

## Sources of truth

Do not copy these into this file.

| Need | Where |
|------|--------|
| Provider / OCR / vision knobs | `config.yaml.example` |
| Human install and usage | `README.md` |
| Company-name aliases | `harmonized-company-names.yaml.example` |

## Commands

Activate `venv` first (`venv\Scripts\activate` on Windows).

| Task | Command |
|------|---------|
| Install | `pip install -r requirements.txt` and `requirements-dev.txt` |
| CLI | `python autorename-pdf.py rename <path>` |
| Dry-run | `python autorename-pdf.py rename <path> --dry-run` |
| Undo | `python autorename-pdf.py undo` |
| Config | `python autorename-pdf.py config show` / `config validate` |
| Lint | `python -m ruff check .` |
| Test | `pytest tests/ -v --cov` |
| Live test | `pytest tests/ --run-live --provider ollama -v` |
| EXE + GUI zip | `python build.py` |
| GUI typecheck | `pnpm -C gui typecheck` |
| GUI unit tests | `pnpm -C gui test:run` |
| GUI dev | `pnpm -C gui tauri dev` |

JSON mode: `--output json`. Exit codes: `0` ok, `1` error, `2` usage, `3` config, `4` no files, `5` partial, `10` provider, `11` auth.

## Architecture

Functional Python (no classes). `_*.py` modules are internal.

| Module | Role |
|--------|------|
| `autorename-pdf.py` | CLI + orchestration |
| `_ai_processing.py` | Native structured parse for OpenAI (`responses.parse`) and Anthropic (`messages.parse`); instructor for Gemini, xAI, Ollama |
| `_pdf_utils.py` | pdfplumber, pypdfium2, PaddleOCR bridge |
| `_paddleocr_bridge.py` | Isolated PaddleOCR venv subprocess |
| `_document_processing.py` | Harmonize (Jaro-Winkler), rename, undo |
| `_config_loader.py` | YAML v2; `${VAR}` from `.env` beside config |
| `_utils.py` | Filename validation, constants |

GUI lives in `gui/`: Tauri 2 sidecar wrapping the CLI (`autorename-pdf-cli`). Vanilla TypeScript, Tailwind 4, Vitest. Use **pnpm** (`gui/pnpm-lock.yaml`); ignore `gui/package-lock.json`.

## Hard rules

- Never commit `config.yaml` or `harmonized-company-names.yaml`. Examples only.
- Do not add classes to the Python core.
- GUI and Explorer context-menu EXE are Windows-only. The Python CLI is cross-platform.
- Python 3.11+ floor for the CLI. OCR embed is Python 3.13.15.
- Default OpenAI model is `gpt-5.6-luna`.
- OpenAI and Anthropic use native structured parse. Instructor is only for Gemini (TOOLS), xAI (TOOLS), and Ollama (JSON).
- pdfplumber always runs. OCR (`pdf.ocr`) and vision (`pdf.vision`) are independent (`false` / `true` / `auto`).
- OCR pins: PaddlePaddle 3.3.1 / PaddleOCR 3.7.0. Defaults `PP-OCRv6_small_det` + `PP-OCRv6_small_rec` for `en` and latin-script langs.
- Dates: dateparser, DMY locale.
- Business logic (harmonization, dates, filenames) should stay above 80% test coverage. Mock AI in unit tests; live calls are `--run-live` only.
