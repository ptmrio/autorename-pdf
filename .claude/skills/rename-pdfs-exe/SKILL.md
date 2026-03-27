---
name: rename-pdfs-exe
description: "[Production] Rename PDF files using the compiled autorename-pdf-cli.exe. Windows only."
user-invocable: true
argument-hint: "[path_to_pdfs]"
allowed-tools:
  - Bash(autorename-pdf*)
---

# Rename PDFs (Production EXE)

Rename PDF files using the installed `autorename-pdf-cli.exe`. Assumes the EXE is on PATH or in the current directory (installed via `setup.ps1` from the release ZIP).

## Workflow

1. **Always dry-run first** to preview changes:
   ```
   autorename-pdf-cli.exe rename $ARGUMENTS --dry-run --output json
   ```

2. **Review the output** — check that company names, dates, and document types look correct.

3. **If the user confirms**, run without dry-run:
   ```
   autorename-pdf-cli.exe rename $ARGUMENTS --output json
   ```

4. **Report results** — show renamed count, any failures, and new filenames.

## Options

Pass these after the path:
- `--recursive` or `-r` — process subfolders
- `--provider <name>` — override AI provider (openai/anthropic/gemini/xai/ollama)
- `--model <name>` — override AI model
- `--vision` — force vision mode (send page images to LLM)
- `--text-only` — text extraction only, no OCR/vision
- `--ocr` — force PaddleOCR

## Undo

```
autorename-pdf-cli.exe undo --output json
```

## Config

```
autorename-pdf-cli.exe config show --output json
```

## Company Name Harmonization

`harmonized-company-names.yaml` (next to the EXE) maps company name variations to standardized names (e.g., "MSFT", "Microsoft Corp." → "Microsoft"). Uses fuzzy matching (Jaro-Winkler) so OCR typos are handled automatically.

If the dry-run output shows inconsistent or wrong company names, suggest the user add mappings:
```yaml
StandardName:
  - "Variation 1"
  - "Variation 2"
```

## Notes

- Config file: `config.yaml` next to the EXE (set up by `setup.ps1`)
- Company names file: `harmonized-company-names.yaml` next to the EXE (copy from `.example`)
- The GUI app (`autorename-pdf-gui.exe`) is the primary way to use this tool — this skill is for CLI/automation use cases
- Output format: `YYYYMMDD COMPANY DOCTYPE.pdf`
- Windows only
