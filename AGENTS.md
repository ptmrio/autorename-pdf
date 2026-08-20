# Agent notes

See `CLAUDE.md` and `README.md` for architecture, providers, and standard commands.

## Cursor Cloud specific instructions

### Scope on Linux cloud VMs

- Primary product for cloud agents: **Python CLI** (`autorename-pdf.py`).
- **GUI / Tauri** (`gui/`) and Windows context-menu EXE are Windows-only; do not expect them to run in Linux cloud VMs.
- Always use the project venv: `source venv/bin/activate` (or `./venv/bin/python ...`).

### Dependencies & fixtures

- Install refresh is handled by the environment update/install script (venv + `requirements.txt` / `requirements-dev.txt`).
- PDF fixtures under `tests/fixtures/` are gitignored; regenerate with `python tests/generate_test_pdfs.py` before pytest if missing.
- Copy configs locally (never commit): `cp config.yaml.example config.yaml` and optionally `cp harmonized-company-names.yaml.example harmonized-company-names.yaml`.

### Lint / test / run

- Tests: `pytest tests/ -v --cov` (see `.claude/skills/test/SKILL.md`).
- Expected on Linux: `test_paddleocr_path_autodetect` fails — it patches Windows `LOCALAPPDATA`; Linux uses `~/.local/share` (see `_config_loader.py`). Treat as platform-specific, not a broken env.
- Live provider tests need `--run-live` plus API keys in `.env` or Ollama; unit/mocked suite does not.
- CLI: `python autorename-pdf.py rename <path> --dry-run --output json` then rename without `--dry-run`.
- Offline end-to-end without cloud API keys: install/start Ollama separately (`ollama serve` in tmux if systemd is unavailable), pull a small model (e.g. `llama3.2:3b`), set `ai.provider: ollama` in `config.yaml`. Ollama is optional — not part of the default install script.

### Secrets

- Optional for unit tests. Required for live cloud providers: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. (see `.env.example`). Never commit `config.yaml` or `.env`.
