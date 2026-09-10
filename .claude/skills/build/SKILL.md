---
name: build
description: Build the EXE and distribution package. Use when the user wants to create a release build.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Glob
---

# Build Distribution Package

Build the PyInstaller EXE and create the distribution ZIP.

## Steps

1. Activate the venv:

```bash
source venv/Scripts/activate
```

2. Ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

3. Run the build script:

```bash
python build.py
```

4. Verify the output:
   - Check `dist/autorename-pdf.exe` exists
   - Check the ZIP file was created with today's date
   - Report the file sizes

5. Refresh README screenshots when GUI chrome, invoice codes, default model, CLI prompt, or version changes. Follow **README screenshot playbook** below. Playwright against Vite is not the product window.

6. If build fails:
   - Check for import errors or missing modules
   - Verify PyInstaller is installed
   - Check `build.py` for hardcoded paths that may need updating

## Notes

- Build includes code signing (requires certificate — will skip gracefully if unavailable)
- The ZIP includes: EXE, setup.ps1, config.yaml.example, harmonized-company-names.yaml.example, .env.example. Recipe configs stay in the GitHub `examples/` folder (not in the flat portable ZIP).
- Do NOT include config.yaml (contains API keys) in any build output

## README screenshot playbook

Target files: `screenshot/autorename-pdf-gui.png`, `screenshot/autorename-pdf-cli.png`.

Helpers (do not commit `_raw/` or the throwaway capture config):

- `scripts/prepare_readme_capture.py` — backup `gui/src-tauri/config.yaml`, write AP/`gpt-5.6-luna` capture config, copy fixtures + portable folder
- `scripts/prepare_readme_capture.py restore` — put the developer config back (always, even if capture fails)
- `scripts/drive_readme_gui.py` — native window: Browse Files → Preview names → Rename
- `scripts/capture_readme_screenshots.py` — PrintWindow / `--bitblt` + blue-plate composite. Crops 12px from left/right/bottom (keeps the titlebar) so Win11 DWM/BitBlt bleed does not show on the plate.

**Product shown (must match shipped defaults, not the developer’s personal `config.yaml`):**

- Invoice codes **AP/AR** (not ER)
- Model **gpt-5.6-luna** (or whatever `_version.py` / `config.yaml.example` currently ship)
- Portable folder name `AutoRename-PDF-Portable-{version}` from `_version.py` (today: 3.2.0)
- Light GUI theme
- Files view after a real **Preview names** then **Rename** (two disposable text PDFs)
- CLI: PowerShell in that portable folder with `.\autorename-pdf-cli.exe rename --dry-run …` (flags **after** `rename`)
- Extraction for the shot: `ocr: false`, `vision: false` (pdfplumber only) so the CLI does not show a Vision line

**Never:**

- Screenshot Vite/Chromium (`localhost:5173`), missing-CLI banners, or `gui-*.png` / `vite-*.png`
- Show API keys (`sk-`)
- Leave the developer’s ER/`gpt-5.4`/amount-in-`document_type` config in `gui/src-tauri/config.yaml` for the shot
- Commit `gui/src-tauri/config.yaml`, `config.yaml.readme-shot.bak`, or `screenshot/_raw/`

**GUI**

1. `python build.py --cli-only --nosign` if `gui/src-tauri/autorename-pdf-cli-x86_64-pc-windows-msvc.exe` is missing or Pillow/`_imaging` versions drifted.
2. `venv\Scripts\python.exe scripts/prepare_readme_capture.py` (also overwrites `tauri dev` `resourceDir()/config.yaml` in cargo-target — that is the file the GUI sidecar actually loads)
3. `$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9222'; pnpm -C gui tauri dev`. Wait for the native `AutoRename-PDF` window (custom titlebar, not a browser tab). Confirm light theme (status-bar sun/moon toggle).
4. WebView2 does **not** expose HTML buttons to UIA, and synthetic mouse clicks often hit the Tauri drag-resize overlay. Launch with `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222` and run `venv\Scripts\python.exe scripts/drive_readme_gui.py` (CDP click + native **Öffnen** filename box). Or click **Browse Files** yourself, paste two quoted PDF paths, then **Preview names** → **Rename**. Capture only after **RENAMED** badges.
5. `venv\Scripts\python.exe scripts/capture_readme_screenshots.py capture-window --title AutoRename-PDF --out screenshot/_raw/gui.png`
6. `venv\Scripts\python.exe scripts/capture_readme_screenshots.py composite --kind gui --src screenshot/_raw/gui.png --out screenshot/autorename-pdf-gui.png`

**CLI**

Windows Terminal’s GPU surface is black under PrintWindow. Use `--bitblt` (window must be fully on-screen, unobscured), or `cmd.exe`/`conhost` if BitBlt is dirty.

1. `prepare_readme_capture.py` already copies the sidecar + capture `config.yaml` into `screenshot/_raw/AutoRename-PDF-Portable-{version}\` (no key visible in the console).
2. Open a **new** Windows Terminal tab titled `README-CLI-SHOT` **in that folder**. Close leftover 16-bit / old shot windows first. Run:

```powershell
.\autorename-pdf-cli.exe rename --dry-run ".\SCAN001.pdf"
```

3. Foreground that hwnd (window must be fully on-screen). Prefer `venv\Scripts\python.exe scripts/drive_readme_cli.py` after `wt.exe -w new --title README-CLI-SHOT -d <portable> -- powershell -NoExit -NoLogo`. Then:

```powershell
venv\Scripts\python.exe scripts/capture_readme_screenshots.py capture-window --title README-CLI-SHOT --bitblt --out screenshot/_raw/cli.png
venv\Scripts\python.exe scripts/capture_readme_screenshots.py composite --kind cli --src screenshot/_raw/cli.png --out screenshot/autorename-pdf-cli.png
```

Copy `harmonized-company-names.yaml.example` into the portable folder as `harmonized-company-names.yaml` so the shot does not wrap a missing-file warning. Size the Terminal window (~1080×620) and keep it unobscured (BitBlt copies overlapping pixels). A subst drive (`subst Q: screenshot\_raw` then `cd Q:\AutoRename-PDF-Portable-{version}`) keeps `Portable-{version}` in the prompt while leaving the command on one line. `pip install pywinauto` in the venv is only needed for the drive scripts.

**Fail the recapture** if either composite still contains:

- ` ER ` / `Microsoft ER` / `Hetzner ER` as an invoice code
- `gpt-5.4`
- `Portable-3.0.0` or any version other than current `_version.py`
- `CLI executable not found`
- `sk-`

Require **AP** (or AR) in the GUI names, **gpt-5.6-luna** in the status/CLI AI line, **Undo Last** chrome on the GUI after rename, and `.\autorename-pdf-cli.exe` plus `Portable-{version}` on the CLI.

`venv\Scripts\python.exe scripts/prepare_readme_capture.py restore` when finished. Delete `screenshot/_raw/` if it contains secrets or live paths you do not want locally.
