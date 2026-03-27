---
name: rename-pdfs
description: "[Dev] Rename PDF files using AI (Python, requires venv). For development and cross-platform (macOS/Linux) use."
user-invocable: true
argument-hint: "[path_to_pdfs]"
allowed-tools:
  - Bash(python *)
  - Bash(source *)
---

# Rename PDFs (Development / Cross-Platform)

Rename PDF files using autorename-pdf from source. Requires the Python venv to be active.

## Workflow

0. **Activate the venv** before running any commands:
   ```
   source venv/Scripts/activate   # Windows
   source venv/bin/activate       # macOS / Linux
   ```

1. **Always dry-run first** to preview changes:
   ```
   python autorename-pdf.py rename $ARGUMENTS --dry-run --output json
   ```

2. **Review the output** — check that company names, dates, and document types look correct.

3. **If the user confirms**, run without dry-run:
   ```
   python autorename-pdf.py rename $ARGUMENTS --output json
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
python autorename-pdf.py undo --output json
```

## Config

```
python autorename-pdf.py config show --output json
```

## Company Name Harmonization

`harmonized-company-names.yaml` maps company name variations to standardized names (e.g., "MSFT", "Microsoft Corp." → "Microsoft"). Uses fuzzy matching (Jaro-Winkler) so OCR typos are handled automatically.

If the dry-run output shows inconsistent or wrong company names, suggest the user add mappings:
```yaml
StandardName:
  - "Variation 1"
  - "Variation 2"
```

## Notes

- Config file: `config.yaml` in project root (never commit — contains API keys)
- Company names file: `harmonized-company-names.yaml` in project root (copy from `.example`)
- Output format: `YYYYMMDD COMPANY DOCTYPE.pdf`
- Providers: openai, anthropic, gemini, xai, ollama
