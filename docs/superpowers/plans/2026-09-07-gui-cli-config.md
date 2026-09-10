# GUI ↔ CLI Config Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GUI config load/validate a single cached `config inspect` call that does not import AI/PDF stacks, and make rename progress events work via `spawn()`.

**Architecture:** Keep Python authoritative. Lazy-import rename-only modules in `autorename-pdf.py`. Add `config inspect` that returns show projection plus validation in one JSON. GUI `inspectConfig()` shares one in-flight sidecar process and caches the snapshot. `renamePdfs` switches from `execute()` to `spawn()` so stderr progress fires.

**Tech Stack:** Python 3.11+ CLI, pytest, Tauri 2 plugin-shell, vanilla TypeScript, Vitest.

## Global Constraints

- Never commit `config.yaml` or `harmonized-company-names.yaml`.
- No new Python core classes; functional modules only.
- GUI talks to Python only via sidecar `autorename-pdf-cli` (`gui/src/lib/sidecar.ts`).
- Package manager is pnpm (`pnpm -C gui …`). Ignore `gui/package-lock.json`.
- Do not implement phase 2 (YAML apply, ruamel, GUI writes, persistent sidecar, PyInstaller onedir).
- Existing `config show` and `config validate` remain working.
- Default OpenAI model stays `gpt-5.6-luna`. Do not invent config keys.
- Inspect JSON `config` sibling keys: `config_path`, `valid`, `issues`, `profile`, `resolved_profile`. Do not stuff `config_path` inside `config`.
- Exit codes: inspect exits `0` when the file was read and there are no error-level issues; `3` if missing/unreadable or any issue has `level: error`.
- Tests mock AI. Do not add `--run-live` tests.
- Use project venv for pytest (`venv\Scripts\python.exe -m pytest`).

## Improver revisions (applied 2026-09-07)

Codex improve: ship with revisions; +0 tasks. Binding deltas:

- Cache inspect by canonical path plus a generation counter so stale responses cannot repopulate after force/focus/path change.
- Settings/startup tests must assert one `inspectConfig` (Validate uses `{ force: true }`); focus invalidates only when `payload === true` and does not refetch. Handle `onFocusChanged` with `.catch`.
- Validator: `max_pages: true` is an error; `pdf.ocr`/`vision` accept only `bool` or `"auto"` (not `0`/`1`).
- Rename spawn: assert `onProgress` from stderr; keep accumulated stderr in the result used for diagnostics.
- Inspect is JSON-only; do not call `resolve_profiles` separately (`select_profile` already does). Add unreadable-file + show/inspect projection parity tests.
- Lazy-import subprocess must run `config inspect|show|validate` and forbid `_ai_processing`, `_pdf_utils`, `_document_processing`, `instructor`, `openai`, `anthropic`, `pdfplumber`, `pypdfium2`, `dateparser`.

---

### Task 1: Lazy-import rename/undo stacks

**Files:**
- Modify: `autorename-pdf.py:20-37` (top-level imports) and call sites in `process_pdf` / `_handle_undo`
- Test: `tests/test_cli.py` (new class at end of config section)

**Interfaces:**
- Consumes: existing `process_pdf`, `_handle_undo`
- Produces: `autorename-pdf.py` no longer imports `_ai_processing`, `_pdf_utils`, or `_document_processing` at module load. Those symbols are imported inside `process_pdf` and `_handle_undo` only.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestLazyConfigImports:
    def test_loading_cli_module_does_not_import_ai_stack(self):
        """Fresh interpreter: importing autorename-pdf.py must not load instructor."""
        import subprocess
        import sys
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = (
            "import importlib.util, os, sys\n"
            f"root = {root!r}\n"
            "sys.path.insert(0, root)\n"
            "spec = importlib.util.spec_from_file_location("
            "'autorename_pdf', os.path.join(root, 'autorename-pdf.py'))\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "assert '_ai_processing' not in sys.modules, sorted(sys.modules)\n"
            "assert 'instructor' not in sys.modules\n"
            "assert 'dateparser' not in sys.modules\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_cli.py::TestLazyConfigImports::test_loading_cli_module_does_not_import_ai_stack -v`

Expected: FAIL — `_ai_processing` is in `sys.modules`.

- [ ] **Step 3: Write minimal implementation**

In `autorename-pdf.py`, remove these top-level imports:

```python
from _ai_processing import extract_metadata
from _pdf_utils import extract_content
from _document_processing import (
    harmonize_company_name,
    parse_document_date,
    render_filename,
    rename_document,
    undo_renames,
    generate_batch_id,
    list_undo_batches,
    write_empty_batch,
)
```

Keep `_config_loader`, `_profiles`, `_utils`, `_version`, stdlib, rich.

At the start of `process_pdf`, add:

```python
    from _ai_processing import extract_metadata
    from _pdf_utils import extract_content
    from _document_processing import (
        harmonize_company_name,
        parse_document_date,
        render_filename,
        rename_document,
        generate_batch_id,
        write_empty_batch,
    )
```

At the start of `_handle_undo`, add:

```python
    from _document_processing import undo_renames, list_undo_batches
```

If `_handle_rename` calls `generate_batch_id` / `write_empty_batch` directly, import those at the start of `_handle_rename` instead of (or in addition to) `process_pdf`. Grep the file; every remaining name from the removed import list must have a local import at its first use. Do not add a new module or class.

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_cli.py::TestLazyConfigImports tests/test_cli.py::TestHandleConfigShow tests/test_cli.py::TestHandleConfigValidate tests/test_cli.py::TestHandleUndo -q --cov-fail-under=0`

Expected: PASS (do not require full-suite coverage floor on this single file run). If `TestHandleUndo` does not exist, run `tests/test_cli.py -k "config or undo" -q`.

Then: `venv\Scripts\python.exe -m pytest tests/test_cli.py tests/test_end_to_end.py -q --cov-fail-under=0` if end-to-end is mock-only; skip `--run-live`.

- [ ] **Step 5: Commit**

```bash
git add autorename-pdf.py tests/test_cli.py
git commit -m "perf: lazy-import AI and PDF stacks so config CLI starts without instructor"
```

---

### Task 2: Tighten `_validate_config`

**Files:**
- Modify: `autorename-pdf.py` `_validate_config` (~663–727)
- Test: `tests/test_cli.py` (existing `TestValidateConfig` / new cases next to it)

**Interfaces:**
- Consumes: `_validate_config(config: dict | None, config_path: str, profile_id: str | None = None) -> dict`
- Produces: same return shape `{valid, issues}`. New error cases: unknown `ai.provider`; `pdf.ocr` / `pdf.vision` not in `{True, False, "auto"}`; `pdf.max_pages` present but not `int >= 1`; non-ollama `api_key` still containing `${` after load. Placeholder `your-api-key-here` is a **warning**, not an error.

Allowed providers (tuple constant next to `_validate_config`, not a class):

```python
_ALLOWED_PROVIDERS = ("openai", "anthropic", "gemini", "xai", "ollama")
```

- [ ] **Step 1: Write the failing tests**

Find the existing class that calls `_validate_config` in `tests/test_cli.py` (near `assert result["valid"] is True`). Add:

```python
    def test_rejects_unknown_provider(self):
        config = {"ai": {"provider": "not-a-vendor", "api_key": "key", "model": "x"},
                  "company": {"name": "Acme"}}
        result = _validate_config(config, "config.yaml")
        assert result["valid"] is False
        assert any(i["field"] == "ai.provider" and i["level"] == "error" for i in result["issues"])

    def test_rejects_invalid_ocr_flag(self):
        config = {
            "ai": {"provider": "openai", "api_key": "key", "model": "x"},
            "company": {"name": "Acme"},
            "pdf": {"ocr": "banana"},
        }
        result = _validate_config(config, "config.yaml")
        assert result["valid"] is False
        assert any(i["field"] == "pdf.ocr" for i in result["issues"])

    def test_rejects_non_positive_max_pages(self):
        config = {
            "ai": {"provider": "openai", "api_key": "key", "model": "x"},
            "company": {"name": "Acme"},
            "pdf": {"max_pages": 0},
        }
        result = _validate_config(config, "config.yaml")
        assert result["valid"] is False
        assert any(i["field"] == "pdf.max_pages" for i in result["issues"])

    def test_unexpanded_env_ref_is_error_for_cloud_provider(self):
        config = {
            "ai": {"provider": "openai", "api_key": "${MISSING_KEY}", "model": "x"},
            "company": {"name": "Acme"},
        }
        result = _validate_config(config, "config.yaml")
        assert result["valid"] is False
        assert any(i["field"] == "ai.api_key" and i["level"] == "error" for i in result["issues"])

    def test_placeholder_api_key_is_warning_only(self):
        config = {
            "ai": {"provider": "openai", "api_key": "your-api-key-here", "model": "x"},
            "company": {"name": "Acme"},
        }
        result = _validate_config(config, "config.yaml")
        assert result["valid"] is True
        assert any(i["field"] == "ai.api_key" and i["level"] == "warning" for i in result["issues"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_cli.py::TestValidateConfig -v` (use the actual class name if different; `pytest tests/test_cli.py -k "unknown_provider or invalid_ocr or max_pages or unexpanded or placeholder" -v`)

Expected: FAIL — unknown provider currently valid.

- [ ] **Step 3: Write minimal implementation**

Inside `_validate_config`, after the existing empty-provider check:

```python
    _ALLOWED_PROVIDERS = ("openai", "anthropic", "gemini", "xai", "ollama")
    if provider and provider not in _ALLOWED_PROVIDERS:
        issues.append({
            "field": "ai.provider",
            "level": "error",
            "message": f"Unknown AI provider {provider!r}. Expected one of: {', '.join(_ALLOWED_PROVIDERS)}",
        })

    if provider and provider != "ollama" and isinstance(api_key, str) and "${" in api_key:
        issues.append({
            "field": "ai.api_key",
            "level": "error",
            "message": "API key still contains an unexpanded ${VAR} reference",
        })

    if isinstance(api_key, str) and api_key.strip().lower() in {"your-api-key-here", "your-api-key"}:
        issues.append({
            "field": "ai.api_key",
            "level": "warning",
            "message": "Placeholder API key; replace before calling a cloud provider",
        })

    pdf = config.get("pdf") or {}
    for flag in ("ocr", "vision"):
        if flag in pdf:
            val = pdf[flag]
            if val not in (True, False, "auto"):
                issues.append({
                    "field": f"pdf.{flag}",
                    "level": "error",
                    "message": f"pdf.{flag} must be true, false, or \"auto\"",
                })
    if "max_pages" in pdf:
        pages = pdf["max_pages"]
        if not isinstance(pages, int) or isinstance(pages, bool) or pages < 1:
            issues.append({
                "field": "pdf.max_pages",
                "level": "error",
                "message": "pdf.max_pages must be an integer >= 1",
            })
```

Keep existing api_key-required-for-non-ollama check. `bool` is a subclass of `int` in Python — the `isinstance(pages, bool)` guard is required.

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_cli.py -k "validate or Validate" -v --cov-fail-under=0`

Expected: PASS, including the older valid/invalid JSON CLI tests.

- [ ] **Step 5: Commit**

```bash
git add autorename-pdf.py tests/test_cli.py
git commit -m "fix: reject unknown providers and invalid pdf.ocr/vision/max_pages in config validate"
```

---

### Task 3: Add `config inspect`

**Files:**
- Modify: `autorename-pdf.py` `build_parser` config subparsers; `_handle_config`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `_redact_config`, `_validate_config`, `load_yaml_config`, `select_profile`, `resolve_profiles`
- Produces: `config inspect --output json` prints:

```python
{
    "config_path": os.path.abspath(config_path),
    "valid": bool,
    "issues": list,
    "profile": profile_id or None,
    "resolved_profile": resolved or None,
    "config": redacted_dict_or_None,
}
```

`config` must **not** contain keys `config_path` or `resolved_profile`. Missing file: `config` is JSON `null`, `valid` false, issue field `config_file`, exit `3`.

- [ ] **Step 1: Write the failing tests**

```python
class TestHandleConfigInspect:
    @patch("autorename_pdf.select_profile", return_value=("business", {"template": "x"}))
    @patch("autorename_pdf.resolve_profiles")
    @patch("autorename_pdf._validate_config")
    @patch("autorename_pdf._redact_config")
    @patch("autorename_pdf.load_yaml_config")
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_inspect_json_combines_show_and_validate(
        self, mock_basedir, mock_load, mock_redact, mock_validate, mock_resolve, mock_select, capsys
    ):
        mock_load.return_value = {"ai": {"provider": "openai", "api_key": "sk-test123456"}}
        mock_redact.return_value = {"ai": {"provider": "openai", "api_key": "sk-t...3456"}}
        mock_validate.return_value = {"valid": True, "issues": []}
        args = argparse.Namespace(config_path=None, config_action="inspect", subcommand="config")
        with pytest.raises(SystemExit) as exc_info:
            _handle_config(args, "json")
        assert exc_info.value.code == ExitCode.SUCCESS
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["valid"] is True
        assert parsed["config"]["ai"]["api_key"] == "sk-t...3456"
        assert "config_path" not in parsed["config"]
        assert "config_path" in parsed
        assert parsed["profile"] == "business"

    @patch("autorename_pdf.load_yaml_config", return_value=None)
    @patch("autorename_pdf.get_base_directory", return_value="/fake")
    def test_inspect_missing_file_json(self, mock_basedir, mock_load, capsys):
        args = argparse.Namespace(config_path=None, config_action="inspect", subcommand="config")
        with pytest.raises(SystemExit) as exc_info:
            _handle_config(args, "json")
        assert exc_info.value.code == ExitCode.CONFIG_ERROR
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["valid"] is False
        assert parsed["config"] is None

    def test_parser_accepts_inspect(self):
        parser = build_parser()
        ns = parser.parse_args(["config", "inspect", "--output", "json"])
        assert ns.config_action == "inspect"
```

If `@patch("autorename_pdf.select_profile")` fails because those names live only as `from _profiles import …` in the CLI module, patch `autorename_pdf.select_profile` still — `autorename_pdf_runner` registers `sys.modules["autorename_pdf"]`. If a test errors on patch target, patch `autorename_pdf.select_profile` vs `_profiles.select_profile` according to how `_handle_config` calls it (unqualified `select_profile` → patch `autorename_pdf.select_profile`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_cli.py::TestHandleConfigInspect -v`

Expected: FAIL — unknown config action / parser missing inspect.

- [ ] **Step 3: Write minimal implementation**

Add parser:

```python
    config_sub.add_parser(
        "inspect",
        parents=[_shared],
        help="Show configuration and validation issues together (JSON)",
    )
```

In `_handle_config`, handle `action == "inspect"` **before** show/validate. Implementation:

```python
    if action == "inspect":
        if config is None:
            payload = {
                "config_path": os.path.abspath(config_path),
                "valid": False,
                "issues": [{
                    "field": "config_file",
                    "level": "error",
                    "message": f"Config file not found: {config_path}",
                }],
                "profile": None,
                "resolved_profile": None,
                "config": None,
            }
            if output_format == "json":
                print(json.dumps(payload, indent=2, ensure_ascii=True))
            else:
                console.print("[red]Configuration file not found.[/red]")
            sys.exit(ExitCode.CONFIG_ERROR)

        validation = _validate_config(config, config_path)
        redacted = _redact_config(config)
        redacted.pop("config_path", None)
        redacted.pop("resolved_profile", None)
        profile_id = None
        resolved = None
        try:
            profile_id, resolved = select_profile(config)
            resolve_profiles(config)
        except ValueError as exc:
            validation["issues"].append({
                "field": "profile",
                "level": "error",
                "message": str(exc),
            })
            validation["valid"] = False

        payload = {
            "config_path": os.path.abspath(config_path),
            "valid": validation["valid"],
            "issues": validation["issues"],
            "profile": profile_id,
            "resolved_profile": resolved,
            "config": redacted,
        }
        if output_format == "json":
            print(json.dumps(payload, indent=2, ensure_ascii=True))
        else:
            console.print("valid" if payload["valid"] else "invalid")
        sys.exit(ExitCode.SUCCESS if payload["valid"] else ExitCode.CONFIG_ERROR)
```

Update the usage error string to mention `inspect`. Update `--help` description on the parent config parser to "Show, validate, or inspect configuration".

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_cli.py::TestHandleConfigInspect tests/test_cli.py::TestHandleConfigShow tests/test_cli.py::TestHandleConfigValidate -v --cov-fail-under=0`

Expected: PASS. Show still redacts keys; validate still `{valid, issues}` only.

- [ ] **Step 5: Commit**

```bash
git add autorename-pdf.py tests/test_cli.py
git commit -m "feat: add config inspect JSON combining show projection and validation"
```

---

### Task 4: GUI `inspectConfig` cache

**Files:**
- Modify: `gui/src/lib/sidecar.ts`
- Test: `gui/src/lib/sidecar.test.ts`

**Interfaces:**
- Consumes: existing `Command.sidecar`, `withConfigArg`
- Produces:

```typescript
export interface ConfigIssue {
  field: string;
  level: string;
  message: string;
}

export interface ConfigSnapshot {
  config_path: string;
  valid: boolean;
  issues: ConfigIssue[];
  profile: string | null;
  resolved_profile: unknown;
  config: Record<string, unknown> | null;
}

export function invalidateConfigSnapshot(): void;
export function inspectConfig(options?: { force?: boolean }): Promise<ConfigSnapshot>;
```

`getConfig()` returns `snapshot.config` (throw if `config` is null after a thrown sidecar failure; if inspect returns JSON with `config: null`, reject with `Error` containing `Config file not found` so existing settings tests still match). `validateConfig()` returns `{ valid, issues }` from the same snapshot. Both share one in-flight promise. `force: true` drops cache first.

- [ ] **Step 1: Write the failing tests**

Replace/extend `gui/src/lib/sidecar.test.ts`. Keep path-resolution tests. Add:

```typescript
  it('inspectConfig, getConfig, and validateConfig share one sidecar process', async () => {
    sidecarSpy.mockReturnValue({
      stderr: { on: vi.fn() },
      execute: vi.fn(async () => ({
        code: 0,
        stdout: JSON.stringify({
          config_path: 'D:\\runtime\\config.yaml',
          valid: true,
          issues: [],
          profile: 'business',
          resolved_profile: {},
          config: { ai: { provider: 'openai' } },
        }),
        stderr: '',
      })),
    });
    const sidecar = await import('./sidecar');
    sidecar.invalidateConfigSnapshot();
    const [inspect, cfg, val] = await Promise.all([
      sidecar.inspectConfig(),
      sidecar.getConfig(),
      sidecar.validateConfig(),
    ]);
    expect(sidecarSpy).toHaveBeenCalledTimes(1);
    expect(sidecarSpy.mock.calls[0][1]).toEqual([
      'config', 'inspect', '--output', 'json', '--config', 'D:\\runtime\\config.yaml',
    ]);
    expect(inspect.valid).toBe(true);
    expect(cfg.ai).toEqual({ provider: 'openai' });
    expect(val.valid).toBe(true);
  });

  it('does not reuse a rejected inspect promise', async () => {
    const execute = vi.fn()
      .mockRejectedValueOnce(new Error('sidecar binaries missing'))
      .mockResolvedValueOnce({
        code: 0,
        stdout: JSON.stringify({
          config_path: 'D:\\runtime\\config.yaml',
          valid: true,
          issues: [],
          profile: 'business',
          resolved_profile: {},
          config: { ai: {} },
        }),
        stderr: '',
      });
    sidecarSpy.mockReturnValue({ stderr: { on: vi.fn() }, execute });
    const sidecar = await import('./sidecar');
    sidecar.invalidateConfigSnapshot();
    await expect(sidecar.inspectConfig()).rejects.toThrow(/sidecar/);
    await expect(sidecar.inspectConfig()).resolves.toMatchObject({ valid: true });
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it('force: true bypasses a completed snapshot', async () => {
    const execute = vi.fn(async () => ({
      code: 0,
      stdout: JSON.stringify({
        config_path: 'D:\\runtime\\config.yaml',
        valid: true,
        issues: [],
        profile: 'business',
        resolved_profile: {},
        config: { n: execute.mock.calls.length },
      }),
      stderr: '',
    }));
    sidecarSpy.mockReturnValue({ stderr: { on: vi.fn() }, execute });
    const sidecar = await import('./sidecar');
    sidecar.invalidateConfigSnapshot();
    await sidecar.inspectConfig();
    await sidecar.inspectConfig({ force: true });
    expect(execute).toHaveBeenCalledTimes(2);
  });
```

Vitest may cache `./sidecar` module state. Call `invalidateConfigSnapshot()` in `beforeEach` and use `vi.resetModules()` + dynamic import if the first test leaks. Prefer exporting `invalidateConfigSnapshot` so resetModules is unnecessary.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm -C gui test:run src/lib/sidecar.test.ts`

Expected: FAIL — `inspectConfig` is not exported.

- [ ] **Step 3: Write minimal implementation**

In `sidecar.ts`:

```typescript
export interface ConfigIssue {
  field: string;
  level: string;
  message: string;
}

export interface ConfigSnapshot {
  config_path: string;
  valid: boolean;
  issues: ConfigIssue[];
  profile: string | null;
  resolved_profile: unknown;
  config: Record<string, unknown> | null;
}

let inspectInflight: Promise<ConfigSnapshot> | null = null;
let inspectCache: ConfigSnapshot | null = null;

export function invalidateConfigSnapshot(): void {
  inspectInflight = null;
  inspectCache = null;
}

export async function inspectConfig(options: { force?: boolean } = {}): Promise<ConfigSnapshot> {
  if (options.force) invalidateConfigSnapshot();
  if (inspectCache && !options.force) return inspectCache;
  if (inspectInflight) return inspectInflight;

  inspectInflight = (async () => {
    const command = Command.sidecar('autorename-pdf-cli', await withConfigArg([
      'config', 'inspect', '--output', 'json',
    ]), SIDECAR_OPTIONS);
    const output = await command.execute();
    if (!output.stdout.trim()) {
      throw new Error(output.stderr || `Process exited with code ${output.code}`);
    }
    const snapshot = JSON.parse(output.stdout) as ConfigSnapshot;
    inspectCache = snapshot;
    return snapshot;
  })();

  try {
    return await inspectInflight;
  } catch (err) {
    inspectInflight = null;
    throw err;
  }
}

export async function getConfig(): Promise<Record<string, unknown>> {
  const snapshot = await inspectConfig();
  if (snapshot.config == null) {
    throw new Error(`Config file not found: ${snapshot.config_path}`);
  }
  return snapshot.config;
}

export async function validateConfig(): Promise<ConfigValidation> {
  const snapshot = await inspectConfig();
  return { valid: snapshot.valid, issues: snapshot.issues };
}
```

Keep `ConfigValidation` type. Keep `getConfigPath` / `getUndoLogDir` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm -C gui test:run src/lib/sidecar.test.ts src/views/settings.test.ts`

Expected: PASS. Settings tests still mock `getConfig`/`validateConfig`.

- [ ] **Step 5: Commit**

```bash
git add gui/src/lib/sidecar.ts gui/src/lib/sidecar.test.ts
git commit -m "perf: cache GUI config inspect so show and validate share one sidecar spawn"
```

---

### Task 5: Wire startup and Settings to inspect cache; invalidate on focus

**Files:**
- Modify: `gui/src/main.ts`, `gui/src/views/settings.ts`
- Test: `gui/src/views/settings.test.ts`

**Interfaces:**
- Consumes: `inspectConfig`, `invalidateConfigSnapshot`
- Produces: startup calls `inspectConfig()` once. Settings Validate calls `inspectConfig({ force: true })`. Window focus (when focused) calls `invalidateConfigSnapshot()` then does not automatically refetch unless Settings is visible — **lock:** on focus, only `invalidateConfigSnapshot()`. Next Settings render or startup-equivalent read fetches fresh. Settings open uses cache if present.

Also: if Settings currently calls both `getConfig` and `validateConfig` sequentially, change it to one `inspectConfig()` and derive both.

- [ ] **Step 1: Write the failing test**

In `settings.test.ts`, mock `inspectConfig` if Settings is switched to it; if Settings still uses `getConfig`+`validateConfig`, add:

```typescript
  it('Validate forces a new inspect rather than the cached snapshot', async () => {
    getConfig.mockResolvedValue({ ai: { provider: 'openai' } });
    validateConfig.mockResolvedValue({ valid: true, issues: [] });
    await renderSettingsView(document.getElementById('root')!);
    getConfig.mockClear();
    validateConfig.mockClear();
    document.getElementById('btn-validate-config')!.click();
    await vi.waitFor(() => {
      expect(getConfig).toHaveBeenCalled();
    });
  });
```

After implementation, if Validate uses `inspectConfig({ force: true })`, mock that instead and assert `force: true`. Prefer exporting inspect from the same sidecar mock:

```typescript
const { getConfig, getConfigPath, validateConfig, inspectConfig, showToast, revealItemInDir } = vi.hoisted(() => ({
  getConfig: vi.fn(),
  getConfigPath: vi.fn(),
  validateConfig: vi.fn(),
  inspectConfig: vi.fn(),
  showToast: vi.fn(),
  revealItemInDir: vi.fn(),
}));
```

If Settings does not use `inspectConfig` directly, do not add a dead mock. The required behavior is: clicking Validate results in a sidecar inspect with cache bypass. Implement via `inspectConfig({ force: true })` **or** `invalidateConfigSnapshot()` + `getConfig()`/`validateConfig()`. One inspect total.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/views/settings.test.ts`

Expected: FAIL or missing assertion until Validate is wired.

- [ ] **Step 3: Write minimal implementation**

`main.ts` startup:

```typescript
  inspectConfig().then((snapshot) => {
    if (!snapshot.valid) {
      const errors = snapshot.issues.filter((i) => i.level === 'error');
      if (errors.length > 0) setState({ statusError: 'Config error' });
      else setState({ statusError: '' });
    } else {
      setState({ statusError: '' });
    }
  }).catch((err) => {
    // same sidecar vs config branching as today
  });
```

Import `inspectConfig` from `./lib/sidecar`.

Settings: replace the dual fetch with:

```typescript
    const snapshot = await inspectConfig();
    // use snapshot.config and snapshot.issues / snapshot.valid
```

Validate button:

```typescript
    const snapshot = await inspectConfig({ force: true });
```

In `main.ts` after `initTitlebar`, register focus invalidation:

```typescript
import { getCurrentWindow } from '@tauri-apps/api/window';
import { invalidateConfigSnapshot } from './lib/sidecar';

  void getCurrentWindow().onFocusChanged((event) => {
    if (event.payload) invalidateConfigSnapshot();
  });
```

If `getCurrentWindow` throws outside Tauri (tests), wrap in try/catch and ignore.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run && pnpm -C gui typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/main.ts gui/src/views/settings.ts gui/src/views/settings.test.ts
git commit -m "fix: load GUI config via inspect once and drop the cache when the window refocuses"
```

---

### Task 6: `renamePdfs` uses `spawn()` for stderr progress

**Files:**
- Modify: `gui/src/lib/sidecar.ts` `renamePdfs`
- Test: `gui/src/lib/sidecar.test.ts`

**Interfaces:**
- Consumes: `Command.sidecar(...).spawn()`, `command.stdout` / `stderr` `data`, `command` `close` event `{ code }`
- Produces: same `Promise<SidecarResult>` as today. `onProgress` called with each stderr line. Undo stays `execute()`.

- [ ] **Step 1: Write the failing test**

```typescript
  it('renamePdfs listens to stderr via spawn, not execute', async () => {
    const stderrOn = vi.fn();
    const stdoutOn = vi.fn();
    const commandOn = vi.fn();
    sidecarSpy.mockReturnValue({
      stderr: { on: stderrOn },
      stdout: { on: stdoutOn },
      on: commandOn,
      spawn: vi.fn(async () => ({ pid: 1 })),
      execute: vi.fn(),
    });
    const { renamePdfs } = await import('./sidecar');
    const progress = vi.fn();
    const pending = renamePdfs(['D:\\a.pdf'], {}, progress);
    expect(sidecarSpy.mock.results[0].value.execute).not.toHaveBeenCalled();
    expect(sidecarSpy.mock.results[0].value.spawn).toHaveBeenCalled();
    const closeHandler = commandOn.mock.calls.find((c: unknown[]) => c[0] === 'close')?.[1];
    const stdoutHandler = stdoutOn.mock.calls.find((c: unknown[]) => c[0] === 'data')?.[1];
    stdoutHandler?.(JSON.stringify({
      success: true, total: 0, renamed: 0, skipped: 0, failed: 0, files: [], dry_run: false,
    }));
    closeHandler?.({ code: 0, signal: null });
    await expect(pending).resolves.toMatchObject({ success: true });
  });
```

Adjust if the implementation accumulates stdout then parses on `close` only (then call stdoutHandler before closeHandler). If `spawn` is not invoked because `execute` remains, the test fails as required.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/lib/sidecar.test.ts`

Expected: FAIL — `execute` is still used.

- [ ] **Step 3: Write minimal implementation**

Replace the `execute()` body of `renamePdfs` with:

```typescript
  const command = Command.sidecar('autorename-pdf-cli', await withConfigArg(args), SIDECAR_OPTIONS);
  let stdout = '';
  command.stdout.on('data', (chunk) => {
    stdout += chunk;
  });
  command.stderr.on('data', (line) => {
    onProgress?.(String(line).trim());
  });
  const output = await new Promise<{ code: number | null; stdout: string; stderr: string }>((resolve, reject) => {
    command.on('error', (err) => reject(new Error(String(err))));
    command.on('close', (event) => {
      resolve({ code: event.code, stdout, stderr: '' });
    });
    void command.spawn().catch(reject);
  });
```

Then reuse the existing `output.code !== 0 && !output.stdout.trim()` error mapping and `JSON.parse(output.stdout)`.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run && pnpm -C gui typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/lib/sidecar.ts gui/src/lib/sidecar.test.ts
git commit -m "fix: spawn the rename sidecar so stderr progress events actually fire"
```
