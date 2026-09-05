# Stack Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring AutoRename-PDF to 2026-current dependency, SDK, GUI, OCR, and packaging floors, and close the TDD gap on AI request contracts.

**Architecture:** Keep the functional Python CLI, isolated PaddleOCR subprocess, and Tauri sidecar GUI. Split AI extraction: native structured parse for OpenAI and Anthropic; Instructor remains only for Gemini, xAI, and Ollama. Do not rewrite the product, add frameworks, or change the portable-ZIP distribution model.

**Tech Stack:** Python 3.11+ CLI, Instructor (compat providers), OpenAI Responses parse, Anthropic messages.parse, pdfplumber + pypdfium2 + Pillow, PaddleOCR 3.7 / PP-OCRv6_small defaults, Tauri 2 + Vite 8 + Tailwind 4 CLI, PyInstaller 6.22 onefile.

**Spec:** Approved clustered modernization (conversation 2026-09-05): slices 1–6 in full, Astra as final adversarial + visual reviewer. Practices anchors: OpenAI Structured Outputs (2026-09-05), Anthropic Structured Outputs / tool use (2026-09-05).

## Global Constraints

- Documented Python floor stays **3.11**. OCR embed pin becomes **3.13.15**. CLI EXE interpreter is whatever PyInstaller is run with (dev baseline 3.11.9).
- `openai>=2.54.0,<3` (Instructor 1.16 cannot take OpenAI 3.x). `anthropic>=1.4.0,<2`. `instructor>=1.16.0,<2`. `rich>=13.8.0,<15`. `pydantic>=2.8.0,<3`.
- Native parse: OpenAI `client.responses.parse(..., text_format=DocumentMetadata, store=False)`; Anthropic `client.messages.parse(..., output_format=DocumentMetadata)`. Do not pass `temperature` to Anthropic 1.x.
- OpenAI default example model: `gpt-5.6-luna` with reasoning effort **none**.
- OCR defaults: `PP-OCRv6_small_det` + for `en` and latin-script langs `PP-OCRv6_small_rec`. Keep specialized v5 rec models (korean, arabic, cyrillic, etc.). Isolated venv architecture unchanged. `enable_mkldnn=False` in both bridge and setup.ps1 preloader.
- GUI: pnpm only (delete `gui/package-lock.json`). Vite **^8.1.0**. sharp **^0.35.4**. Match each Tauri plugin JS package to its Rust crate. Rust edition stays **2021**. Vanilla TS, no React/Svelte.
- Packaging: PyInstaller **==6.22.2**, hooks-contrib **==2026.7**, portable ZIP + sidecar. Do not introduce MSI/Store. Azure timestamp URL unchanged.
- TDD policy: Required for new/changed behavior. Forbidden: grep/string-presence tests on requirement files or prompts. Optional: pure pin/config/docs (one-line why in GATES).
- Work from: `D:/Code/autorename-pdf/.worktrees/stack-modernization`. Commit after each task. Never push.
- Do not revert unrelated main-worktree WIP (skill ZIP bundling, Authenticode blob). This branch starts from `1465cfc`.
- Tests: `python -m pytest tests/ -q -m "not live"` using the worktree venv once created. Generate fixtures with `python tests/generate_test_pdfs.py` if PDFs are missing (`*.pdf` is gitignored).
- Functional Python (no new classes except existing Pydantic models). Modules stay `_`-prefixed.

---

### Task 1: Python floors + pyproject tool config

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Create: `pyproject.toml`
- Test: existing `tests/test_pdf_utils.py`, `tests/test_extraction_fixtures.py` (no new version-grep tests)

**Interfaces:**
- Consumes: current lower-bound requirements
- Produces: installable floors that pdfplumber 0.11.10 / pypdfium2 5.13 / Pillow 12.3 accept; pytest config in pyproject

TDD skip: non-behavioral dependency floors and tool config. Gate is the existing PDF suite after install.

- [ ] **Step 1: Write requirements.txt**

```
anthropic>=1.4.0,<2
dateparser>=1.2.0
python-dotenv>=1.2.2
instructor>=1.16.0,<2
openai>=2.54.0,<3
pdfplumber>=0.11.10
Pillow>=12.3.0
pydantic>=2.8.0,<3
pypdfium2>=5.13.0
PyYAML>=6.0.3
rapidfuzz>=3.9.0
rich>=13.8.0,<15
```

Keep one package per line, no extras on instructor yet (Task 4). Anthropic 1.x lands here; Task 2/3 must land in the same PR wave before merge — this branch will not be mergeable until those tasks remove `temperature` from Anthropic calls. If Task 1 is committed alone, tests that still pass `temperature` through instructor/anthropic mocks will still pass (they mock the client). Real Anthropic 1.x would break — Task 2 is next immediately.

- [ ] **Step 2: Write requirements-dev.txt**

Keep `-r requirements.txt`. Set:

```
pytest>=9.1.1
pytest-cov>=7.1.0
python-dotenv>=1.2.2
fpdf2>=2.8.0
pyinstaller==6.22.2
pyinstaller-hooks-contrib==2026.7
ruff==0.16.6
```

- [ ] **Step 3: Write pyproject.toml** (tools only, no `[project]` duplication of deps)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
filterwarnings = ["ignore::DeprecationWarning"]

[tool.ruff]
target-version = "py311"
exclude = ["venv", "build", "dist", "gui", ".worktrees", ".superpowers"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F"]

[tool.coverage.run]
source = ["."]
omit = ["tests/*", "venv/*", "build.py", "gui/*"]
```

Do not move pytest markers out of `tests/conftest.py`.

- [ ] **Step 4: Create worktree venv and install**

```
python -m venv venv
venv\Scripts\python.exe -m pip install -U pip
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe tests/generate_test_pdfs.py
```

- [ ] **Step 5: Run PDF/extraction tests**

```
venv\Scripts\python.exe -m pytest tests/test_pdf_utils.py tests/test_extraction_fixtures.py -q -m "not live"
```

Expected: PASS. If pypdfium2 5.x breaks `PdfPage.render` / `to_pil`, stop and report — do not swap PDF libraries.

- [ ] **Step 6: Commit**

```
git add requirements.txt requirements-dev.txt pyproject.toml
git commit -m "Raise Python dependency floors and add pyproject tool config."
```

---

### Task 2: TDD sampling / provider request kwargs

**Files:**
- Create tests in: `tests/test_ai_processing.py`
- Modify: `_ai_processing.py`
- Test: `tests/test_ai_processing.py`

**Interfaces:**
- Consumes: `config["ai"]` with `provider`, `model`, `temperature`
- Produces: `build_provider_create_kwargs(provider: str, config: dict) -> dict` used by all three extract functions

The production change that would fail these tests: sending `temperature` to Anthropic, or omitting `max_tokens` for Anthropic, or sending temperature to OpenAI when reasoning effort is not `none`.

- [ ] **Step 1: Write the failing tests** (append a new class; do not delete existing tests yet)

```python
from _ai_processing import build_provider_create_kwargs

class TestBuildProviderCreateKwargs:
    def test_anthropic_omits_temperature_and_sets_max_tokens(self, sample_config):
        sample_config["ai"]["provider"] = "anthropic"
        sample_config["ai"]["temperature"] = 0.0
        kwargs = build_provider_create_kwargs("anthropic", sample_config)
        assert "temperature" not in kwargs
        assert kwargs["max_tokens"] == 1024

    def test_openai_sets_reasoning_none_and_omits_temperature(self, sample_config):
        sample_config["ai"]["provider"] = "openai"
        sample_config["ai"]["model"] = "gpt-5.6-luna"
        kwargs = build_provider_create_kwargs("openai", sample_config)
        assert kwargs["reasoning"] == {"effort": "none"}
        assert "temperature" not in kwargs

    def test_compat_provider_keeps_temperature(self, sample_config):
        sample_config["ai"]["provider"] = "ollama"
        sample_config["ai"]["temperature"] = 0.2
        kwargs = build_provider_create_kwargs("ollama", sample_config)
        assert kwargs["temperature"] == 0.2
        assert "max_tokens" not in kwargs
        assert "reasoning" not in kwargs
```

- [ ] **Step 2: Run tests to verify they fail**

```
venv\Scripts\python.exe -m pytest tests/test_ai_processing.py::TestBuildProviderCreateKwargs -q
```

Expected: FAIL with `build_provider_create_kwargs` not defined (or ImportError).

- [ ] **Step 3: Implement the helper and wire it into the three extract functions**

```python
def build_provider_create_kwargs(provider: str, config: dict) -> dict:
    ai = config["ai"]
    if provider == "anthropic":
        return {"max_tokens": 1024}
    if provider == "openai":
        return {"reasoning": {"effort": "none"}}
    return {"temperature": ai.get("temperature", 0.0)}
```

In `extract_metadata_from_text`, `extract_metadata_from_images`, and `extract_metadata_from_text_and_images`: start from this dict instead of hardcoding `temperature` and the anthropic `max_tokens` branch. Keep `model`, `response_model`, `max_retries`, `messages` as they are for this task (native parse is Task 3).

- [ ] **Step 4: Run helper tests and full AI tests**

```
venv\Scripts\python.exe -m pytest tests/test_ai_processing.py -q
```

Expected: PASS. Update `TestExtractMetadataProviderKwargs` if they still assert `temperature` in Anthropic instructor calls — Anthropic must not include temperature even on the instructor-shaped kwargs (Task 3 will switch the client).

- [ ] **Step 5: Commit**

```
git add _ai_processing.py tests/test_ai_processing.py
git commit -m "Omit Anthropic temperature and pin OpenAI reasoning effort in request kwargs."
```

---

### Task 3: Native OpenAI Responses + Anthropic parse

**Files:**
- Modify: `_ai_processing.py`
- Modify: `tests/test_ai_processing.py`

**Interfaces:**
- Consumes: `build_provider_create_kwargs`, `DocumentMetadata`, `build_system_prompt`, `build_image_content`
- Produces: `extract_metadata_from_*` returning `DocumentMetadata` via native parse for `openai` and `anthropic`; instructor path unchanged for other providers

Production change that would fail these tests: calling `chat.completions.create` for OpenAI/Anthropic, or not using `text_format`/`output_format`.

- [ ] **Step 1: Write failing tests** using mocks of the real SDKs, not Instructor

```python
class TestNativeStructuredExtract:
    def test_openai_text_uses_responses_parse(self, sample_config):
        sample_config["ai"]["provider"] = "openai"
        sample_config["ai"]["model"] = "gpt-5.6-luna"
        parsed = DocumentMetadata(company_name="ACME", document_date="15.03.2024", document_type="ER")
        mock_resp = MagicMock(output_parsed=parsed)
        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_resp
        with patch("_ai_processing._get_openai_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_text
            result = extract_metadata_from_text("invoice text", sample_config)
        assert result.company_name == "ACME"
        kwargs = mock_client.responses.parse.call_args.kwargs
        assert kwargs["text_format"] is DocumentMetadata
        assert kwargs["store"] is False
        assert kwargs["reasoning"] == {"effort": "none"}
        assert "temperature" not in kwargs
        mock_client.chat.completions.create.assert_not_called()

    def test_anthropic_text_uses_messages_parse(self, sample_config):
        sample_config["ai"]["provider"] = "anthropic"
        parsed = DocumentMetadata(company_name="GmbH", document_date="01.01.2024", document_type="ER")
        mock_resp = MagicMock(parsed_output=parsed)
        mock_client = MagicMock()
        mock_client.messages.parse.return_value = mock_resp
        with patch("_ai_processing._get_anthropic_client", return_value=mock_client):
            from _ai_processing import extract_metadata_from_text
            result = extract_metadata_from_text("rechnung", sample_config)
        assert result.company_name == "GmbH"
        kwargs = mock_client.messages.parse.call_args.kwargs
        assert kwargs["output_format"] is DocumentMetadata
        assert kwargs["max_tokens"] == 1024
        assert "temperature" not in kwargs
```

Add one vision test: OpenAI native path puts image input in `input` (not Chat Completions `image_url` messages). Anthropic vision keeps existing `build_image_content(..., "anthropic")` blocks inside `messages`.

- [ ] **Step 2: Run to verify FAIL** (functions still hit instructor)

```
venv\Scripts\python.exe -m pytest tests/test_ai_processing.py::TestNativeStructuredExtract -q
```

- [ ] **Step 3: Implement `_get_openai_client`, `_get_anthropic_client`, and branch extractors**

Keep `get_instructor_client` for gemini/xai/ollama. For openai/anthropic, do not wrap with instructor.

OpenAI text call shape (adapt if the installed 2.54 SDK uses a slightly different kwarg name — assert in test, then match production):

```python
client.responses.parse(
    model=model,
    input=[
        {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
        {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
    ],
    text_format=DocumentMetadata,
    store=False,
    **build_provider_create_kwargs("openai", config),
)
```

Return `response.output_parsed`.

Anthropic:

```python
client.messages.parse(
    model=model,
    system=system_prompt,
    messages=[{"role": "user", "content": user_content}],
    output_format=DocumentMetadata,
    **build_provider_create_kwargs("anthropic", config),
)
```

Return `response.parsed_output`.

Update existing instructor-based kwargs tests so they only apply to gemini/xai/ollama. Anthropic `max_tokens` test moves to the native class.

- [ ] **Step 4: Run AI tests + full non-live suite**

```
venv\Scripts\python.exe -m pytest tests/test_ai_processing.py tests/test_end_to_end.py -q -m "not live"
```

- [ ] **Step 5: Commit**

```
git add _ai_processing.py tests/test_ai_processing.py
git commit -m "Use native structured parse for OpenAI and Anthropic extraction."
```

---

### Task 4: Instructor compat providers stay on OpenAI 2.x

**Files:**
- Modify: `_ai_processing.py` only if `get_instructor_client` needs Mode unchanged
- Modify: `tests/test_ai_processing.py` (gemini/xai/ollama still instructor)

**Interfaces:**
- Consumes: Task 3 branching
- Produces: gemini/xai/ollama still `instructor.from_openai`; ollama still `Mode.JSON`; others `Mode.TOOLS`

- [ ] **Step 1: Write failing test if missing**

```python
def test_gemini_still_uses_instructor_tools(self, sample_config):
    sample_config["ai"]["provider"] = "gemini"
    with patch("_ai_processing.OpenAI") as mock_openai, patch("_ai_processing.instructor") as mock_instructor:
        mock_instructor.Mode.TOOLS = "TOOLS"
        mock_instructor.from_openai.return_value = MagicMock()
        get_instructor_client(sample_config)
        mock_instructor.from_openai.assert_called_once()
```

xAI same pattern with `api.x.ai`. Keep existing ollama JSON test.

- [ ] **Step 2: Run FAIL/PASS as appropriate** — if already green, do not add ceremony. If Task 3 accidentally routed gemini to native OpenAI parse, this fails; fix routing (`provider == "openai"` only, not all OpenAI-SDK providers).

- [ ] **Step 3: Confirm `extract_metadata_from_text` for gemini still uses instructor client `chat.completions.create`.**

- [ ] **Step 4: Full AI tests**

```
venv\Scripts\python.exe -m pytest tests/test_ai_processing.py -q
```

- [ ] **Step 5: Commit** (skip commit if no file changes; note in report)

```
git add _ai_processing.py tests/test_ai_processing.py
git commit -m "Keep Instructor TOOLS/JSON for Gemini, xAI, and Ollama."
```

---

### Task 5: Default model gpt-5.6-luna

**Files:**
- Modify: `config.yaml.example`
- Modify: `tests/conftest.py` sample configs if they hardcode `gpt-5.4`
- Modify: `README.md` / `CLAUDE.md` / `AGENTS.md` only where they name the example model

TDD skip for example YAML (non-behavioral config). Required: conftest defaults used by tests should not claim gpt-5.4 if production example changed — grep conftest for `gpt-5.4` and update to `gpt-5.6-luna` so tests exercise the real default.

- [ ] **Step 1: Update `config.yaml.example`**

```
  model: "gpt-5.6-luna"
  temperature: 0.0                # Ignored for OpenAI/Anthropic native parse
```

- [ ] **Step 2: Update test configs / docs that copy the example model slug**

- [ ] **Step 3: Run** `venv\Scripts\python.exe -m pytest tests/ -q -m "not live"`

- [ ] **Step 4: Commit**

```
git commit -am "Default the OpenAI example model to gpt-5.6-luna."
```

---

### Task 6: PaddleOCR 3.7 pins + PP-OCRv6_small defaults

**Files:**
- Modify: `_paddleocr_bridge.py`
- Modify: `setup.ps1` pins and preloader
- Modify: `config.yaml.example` comments
- Modify: `tests/test_pdf_utils.py` (constructor kwargs / default model names)

**Interfaces:**
- Consumes: `_LANG_TO_REC_MODEL`, `_init_v3`
- Produces: default det `PP-OCRv6_small_det`; rec for `en` and the current latin group `PP-OCRv6_small_rec`; other groups stay on their v5 rec models; setup.ps1 `PaddlePaddleVersion=3.3.1`, `PaddleOCRVersion=3.7.0`

Production change that would fail tests: defaulting det to `PP-OCRv5_mobile_det` or mapping `en` to `en_PP-OCRv5_mobile_rec`.

- [ ] **Step 1: Write failing tests** (import bridge module; it must stay importable without paddleocr installed)

```python
from _paddleocr_bridge import _LANG_TO_REC_MODEL, _init_v3

def test_en_uses_v6_small_rec():
    assert _LANG_TO_REC_MODEL["en"] == "PP-OCRv6_small_rec"

def test_de_uses_v6_small_rec():
    assert _LANG_TO_REC_MODEL["de"] == "PP-OCRv6_small_rec"

def test_korean_stays_v5():
    assert _LANG_TO_REC_MODEL["korean"] == "korean_PP-OCRv5_mobile_rec"
```

For `_init_v3` default det: patch `paddleocr.PaddleOCR` after injecting a fake module, or extract:

```python
def default_detection_model() -> str:
    return "PP-OCRv6_small_det"
```

and unit-test that. Prefer a tiny helper over mocking imports if `_init_v3` currently imports paddleocr inside the function (it does). Add:

```python
def test_default_detection_model_is_v6_small():
    from _paddleocr_bridge import default_detection_model
    assert default_detection_model() == "PP-OCRv6_small_det"
```

- [ ] **Step 2: Run FAIL**

- [ ] **Step 3: Update map + helper + `_init_v3` else-branch + setup.ps1 preloader string to include `enable_mkldnn=False` and v6 model names**

setup.ps1 pins:

```
$script:PaddlePaddleVersion = "3.3.1"
$script:PaddleOCRVersion    = "3.4.0"  # replace with 3.7.0
```

Preloader Python one-liner must pass the same constructor flags as the bridge (including `enable_mkldnn=False`, v6 names).

Keep cu118 GPU index. Do not switch to cu126.

- [ ] **Step 4: Run** `venv\Scripts\python.exe -m pytest tests/test_pdf_utils.py tests/test_config_loader.py -q`

- [ ] **Step 5: Commit**

```
git commit -am "Default PaddleOCR to PP-OCRv6 small models and pin 3.7.0 / Paddle 3.3.1."
```

---

### Task 7: Embed CPython 3.13.15 + version-aware OCR bootstrap

**Files:**
- Modify: `setup.ps1`

TDD skip: PowerShell bootstrap (no Pester in repo). Gate: script contains version compare + recreate, not only `Test-Path python.exe`.

- [ ] **Step 1: Change pins**

```
$script:VirtualenvVersion   = "21.7.8"
$script:PythonVersion       = "3.13.15"
$script:PythonZipUrl        = "https://www.python.org/ftp/python/$script:PythonVersion/python-$script:PythonVersion-embed-amd64.zip"
```

- [ ] **Step 2: Replace “python.exe exists → skip” with version check**

If `python.exe` exists, run `& $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"` and compare to `$script:PythonVersion`. On mismatch: remove `$pythonDir` and `$venvDir`, then download/recreate. On match: skip download. Always recreate the venv when the base interpreter changes.

Check native command exit codes after get-pip and virtualenv install; fail the OCR install function on non-zero.

Do not replace virtualenv with `python -m venv` (embed has no venv module).

- [ ] **Step 3: Manually read the function for overlay bugs (do not overlay 3.13 onto 3.12 files)**

- [ ] **Step 4: Commit**

```
git add setup.ps1
git commit -m "Recreate the OCR embed on Python version mismatch and pin 3.13.15."
```

---

### Task 8: GUI toolchain — Vite 8, sharp, pnpm lock, Tauri 2.x pairs

**Files:**
- Modify: `gui/package.json`
- Delete: `gui/package-lock.json`
- Modify: `gui/pnpm-lock.yaml` (via pnpm, not hand-edit)
- Modify: `gui/src-tauri/Cargo.toml`
- Modify: `gui/src-tauri/Cargo.lock` (via cargo)
- Modify: `build.py` only if `pnpm install --frozen-lockfile` should always run (Task 9 may own that)

TDD skip: dependency/lock refresh. Gates: typecheck + vitest + CSS build.

- [ ] **Step 1: package.json**

- `build:css`: `tailwindcss -i ./src/css/index.css -o ./assets/css/output.css --minify` (no `npx`)
- `"packageManager": "pnpm@10.0.0"` — set to the pnpm major actually installed (`pnpm -v`); do not invent 10 if the machine is 9.x
- `"engines": { "node": ">=20.19.0" }`
- Dependencies: `@tauri-apps/api` `^2.11.1`; plugins to the pairs in the research note (dialog `^2.7.2`, fs `^2.5.1`, opener `^2.5.4`, shell `^2.3.5`)
- Dev: `@tauri-apps/cli` `^2.11.4`, `vite` `^8.1.0`, `vitest` `^5.0.0` if Vite 8 requires it, else stay on vitest 4 **only if `pnpm test:run` works**. Prefer vitest 5 + coverage-v8 matched. `sharp` `^0.35.4`. `@tailwindcss/cli` `^4.3.3`. Keep `jsdom` `^29.1.1` (jsdom 30 needs a newer Node patch than 24.5).

- [ ] **Step 2: Cargo.toml**

```
tauri-build = { version = "2.6.3", features = [] }
tauri = { version = "2.11.5", features = [] }
tauri-plugin-shell = "2.3.5"
tauri-plugin-dialog = "2.7.2"
tauri-plugin-fs = "2.5.1"
tauri-plugin-opener = "2.5.4"
```

Keep edition 2021. Recheck [Tauri releases](https://v2.tauri.app/release/) at implement time and take later 2.x patches if listed.

- [ ] **Step 3: Delete package-lock.json. Run from `gui/`:**

```
pnpm install
pnpm run typecheck
pnpm run test:run
pnpm run build:css
pnpm run build
```

If Vite 8 needs `vite.config` changes, make the smallest change that restores the existing vanilla TS build. Do not migrate to a frontend framework.

- [ ] **Step 4: `cargo check` in `gui/src-tauri`**

- [ ] **Step 5: Commit**

```
git add gui/package.json gui/pnpm-lock.yaml gui/src-tauri/Cargo.toml gui/src-tauri/Cargo.lock
git rm gui/package-lock.json
git commit -m "Refresh the Tauri GUI to Vite 8 and matched Tauri 2.x plugins."
```

---

### Task 9: PyInstaller pins + always-frozen pnpm install

**Files:**
- Modify: `build.py`
- `requirements-dev.txt` already pinned in Task 1

TDD skip: build orchestration. Gate: read `build.py` — `pnpm install --frozen-lockfile` must run even when `node_modules` exists.

- [ ] **Step 1: Remove the skip-if-node_modules branch around pnpm install. Always frozen-install before `pnpm tauri build`.**

- [ ] **Step 2: Confirm PyInstaller flags in `build.py` still match 6.22 (`--onefile`, `--collect-all instructor`). No spec-file rewrite.**

- [ ] **Step 3: Commit**

```
git add build.py
git commit -m "Always frozen-install GUI deps before the Tauri build."
```

---

### Task 10: Ruff gate + Windows CI + docs

**Files:**
- Create: `.github/workflows/test.yml`
- Modify: `CLAUDE.md`, `README.md`, `AGENTS.md` (Python pins, model default, OCR 3.7/v6, instructor scope)
- Modify: code only if ruff E4/E7/E9/F finds real defects in touched Python files

TDD skip: CI YAML and prose. Gate: ruff + pytest on the worktree.

- [ ] **Step 1: Run ruff**

```
venv\Scripts\python.exe -m ruff check .
```

Fix genuine F/E defects in application Python. Do not enable format. File-level `# noqa: E402` only for conftest path bootstrap if needed.

- [ ] **Step 2: Add `.github/workflows/test.yml`**

```yaml
name: test
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  pytest:
    runs-on: windows-2022
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: |
          python -m venv venv
          .\venv\Scripts\python.exe -m pip install -U pip
          .\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
      - name: Generate fixtures
        run: .\venv\Scripts\python.exe tests/generate_test_pdfs.py
      - name: Ruff
        run: .\venv\Scripts\python.exe -m ruff check .
      - name: Pytest
        run: .\venv\Scripts\python.exe -m pytest tests/ -q --cov -m "not live"
```

No API keys, no setup.ps1, no OCR download, no signing.

- [ ] **Step 3: Update CLAUDE.md / README / AGENTS.md to match shipped behavior** (native parse for OpenAI/Anthropic, instructor for three compat providers, default model, OCR pins). Do not invent APIs.

- [ ] **Step 4: Full verification**

```
venv\Scripts\python.exe -m ruff check .
venv\Scripts\python.exe -m pytest tests/ -q --cov -m "not live"
pnpm -C gui run typecheck
pnpm -C gui run test:run
```

- [ ] **Step 5: Commit**

```
git add .github/workflows/test.yml CLAUDE.md README.md AGENTS.md
git commit -m "Add Windows lint+pytest CI and document the modernized stack."
```

---

## Self-check

- Spec coverage: slices 1–6 mapped to tasks 1–10 (AI native+pins+luna, PDF floors, GUI Vite8/Tauri, packaging/CI/ruff, OCR v6+3.13 embed).
- TDD required on AI kwargs, native parse, OCR default model names. Config/lock/CI skipped with why.
- No placeholder TBD steps.
- Astra adversarial + visual review is the parent’s post-plan Validate stage, not a task in this file.
