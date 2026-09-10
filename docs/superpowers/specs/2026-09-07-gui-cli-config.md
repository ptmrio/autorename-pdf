# GUI ↔ CLI config

Date: 2026-09-07

Status: locked for implementation

This is the binding product specification for how the Tauri GUI talks to the Python CLI about configuration. It retains the Astra research dated 2026-09-07 (packaged `config show` ~4.4 s; in-process YAML load ~2.7 ms) and the owner’s synthesis: Python stays authoritative; do not start with a persistent stdio sidecar.

## Scope and defaults

This delivery (phase 1) makes config **load and validate** cheap enough that opening Settings and starting the app do not each pay a full PyInstaller import bill, and makes rename progress events actually arrive.

Phase 2 (specified here, **not** in the accompanying phase-1 plan) is a safe YAML writer so the GUI can edit settings later. It is locked so phase 1 does not paint us into a corner. It is not implemented in this loop.

Non-goals for both phases: persistent `serve --stdio` sidecar, embedding CPython in Rust, a second GUI JSON settings store, reimplementing YAML/profile semantics in TypeScript or Rust, dumping `config show` JSON back to disk, PyInstaller one-folder packaging, committing `config.yaml`.

Python remains functional (no new core classes). GUI and Explorer EXE remain Windows-only. CLI remains cross-platform. Sidecar name stays `autorename-pdf-cli`. Config path stays the existing portable path: `resourceDir()/config.yaml` passed as `--config`.

## Why it is slow today

`gui/src/lib/sidecar.ts` caches only the config **path**. `getConfig()` runs `config show`; `validateConfig()` runs `config validate`; startup and Settings each spawn a fresh process. `autorename-pdf.py` imports `_ai_processing`, `_pdf_utils`, and `_document_processing` before argparse, so a config-only command still loads instructor/OpenAI/Pillow/dateparser. YAML parse time is not the bottleneck.

`renamePdfs` attaches `stderr.on('data')` then calls `.execute()`. Tauri shell delivers those events on `.spawn()`, not `.execute()`. Live progress is currently a no-op.

## Phase 1 — inspect, cache, lazy imports, live progress

### Lazy imports

Top-level imports in `autorename-pdf.py` that are required for config and CLI plumbing stay eager: `_config_loader`, `_profiles`, `_utils`, `_version`, stdlib, rich.

These imports move into the rename/undo/content paths that need them (function-local, not a new class):

- `_ai_processing.extract_metadata`
- `_pdf_utils.extract_content`
- `_document_processing` (harmonize, parse date, render, rename, undo, batch ids)

A fresh process running `config inspect` / `show` / `validate` must not import `instructor`, `openai`, `anthropic`, `pdfplumber`, `pypdfium2`, or `dateparser`.

### Combined inspect

Add `config inspect --output json` (text mode optional, same fields). It performs one load and returns **one** JSON object:

```json
{
  "config_path": "C:\\...\\config.yaml",
  "valid": true,
  "issues": [
    {"field": "ai.provider", "level": "error", "message": "..."}
  ],
  "profile": "business",
  "resolved_profile": {},
  "config": {}
}
```

Rules:

- `config` is the existing `config show` projection: defaults merged, env expanded, `ai.api_key` redacted, **no** `config_path` / `resolved_profile` stuffed inside `config` (those stay siblings). `config_version` remains inside `config` if present.
- Missing file: `valid` false, `config` null, issue on `config_file`, exit `3`.
- Existing `config show` and `config validate` remain. They share the same load/validate helpers. GUI must call **inspect only**, not show+validate.
- Exit codes unchanged: inspect exits `0` if the file was read (even with warnings); exits `3` if missing/unreadable or any issue has `level: error`. Same as validate today when invalid.

### Validator tightening (read path)

`_validate_config` today does not reject an unknown provider, `pdf.ocr: banana`, or negative `pdf.max_pages`. Before the GUI treats inspect as readiness, those become errors:

| Field | Rule |
|---|---|
| `ai.provider` | Required; must be one of `openai`, `anthropic`, `gemini`, `xai`, `ollama`. |
| `ai.api_key` | Required unless provider is `ollama`. Unexpanded `${VAR}` (string still contains `${` after load) is an error for non-ollama. Placeholder example keys such as `your-api-key-here` remain **valid** (warning only) so `config.yaml.example` copies still open. |
| `pdf.ocr`, `pdf.vision` | If present: `true`, `false`, or `"auto"` only. |
| `pdf.max_pages` | If present: integer `>= 1`. |

Do not add a second schema language in phase 1. Do not invent keys. Profile resolution errors stay as today.

### GUI snapshot cache

Replace the dual show/validate calls with one `inspectConfig()` in `sidecar.ts`.

Cache both the **in-flight promise** and the **last successful-or-invalid snapshot**, keyed by the canonical config path. Concurrent callers share the same promise. A rejected promise is discarded so Retry works.

Invalidate the cache on:

- explicit Validate / Refresh in Settings
- window focus (Tauri `onFocusChanged` when focused)
- process of the sidecar returning a new snapshot after a future save (phase 2)

Do **not** spawn a watcher process. Do **not** respawn just to check mtime on every Settings rerender.

`getConfig()` and `validateConfig()` may remain as thin wrappers over the cached inspect for existing tests, or tests update to `inspectConfig`. Callers in `main.ts` and `settings.ts` use inspect.

Startup: one inspect. Settings open: use cache if present; if startup inspect is still in flight, await it. Do not overlap a second process.

### Rename progress

`renamePdfs` (and only rename) must `spawn()` the sidecar, append stdout, forward stderr lines to `onProgress`, and resolve with parsed JSON when the child exits. Undo stays `execute()` (no progress hook). Config inspect stays `execute()`.

## Phase 2 — GUI writes (locked, not this plan)

Python owns a functional apply path. GUI sends a **patch**, never the resolved/redacted show JSON.

Required before any Settings control becomes writable:

1. Round-trip YAML via ruamel (`typ='rt'`), edit named nodes, keep comments and `${VAR}` literals.
2. Secret fields: omit from patch if unchanged; explicit replace; distinct clear. Never save a mask (`sk-a...xyz`) as the key.
3. Atomic replace (`os.replace`) of a temp file in the same directory.
4. Revision / content hash so a stale Settings draft cannot clobber an external edit.
5. Revalidate the serialized candidate with the same loader+validator as inspect.
6. `.env` resolution must not leak across loads in a future long-lived process (`dotenv_values` per load, OS env wins). Phase 1 one-shot processes are unaffected.

No `config set` argv secrets. Preferred CLI: `config apply --stdin` JSON patch once phase 2 is implemented. Settings remains read-only until that CLI exists.

PhraseVault patterns to copy: committed vs draft vs opening baseline; acknowledged save; request correlation. Patterns to skip: `clearInvalidConfig`, fire-and-forget save, class-based `JsonStore`, Electron preload.

## Testing

Phase 1:

- Unit: `config inspect` JSON shape; missing file; validator rejects unknown provider / bad ocr / `max_pages: 0`.
- Unit: importing / running inspect does not import `_ai_processing`.
- GUI: `inspectConfig` shares one sidecar call across concurrent `getConfig`+`validateConfig`; failed promise is not reused; Validate forces a new call.
- GUI: `renamePdfs` uses `spawn` (mock) and still parses stdout JSON.

Do not add live provider tests. Do not require measuring 4 s EXE times in CI.
