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

5. If build fails:
   - Check for import errors or missing modules
   - Verify PyInstaller is installed
   - Check `build.py` for hardcoded paths that may need updating

## Notes

- Build includes code signing (requires certificate — will skip gracefully if unavailable)
- The ZIP includes: EXE, setup.ps1, config.yaml.example, harmonized-company-names.yaml.example
- Do NOT include config.yaml (contains API keys) in any build output
