# Example configs

Complete AutoRename-PDF v2 files from the GitHub repo (not shipped in the Windows ZIP). Copy one over `config.yaml` (next to the EXE or CLI), then set `ai.api_key` and `company.name`.

The [root `config.yaml.example`](../config.yaml.example) is the invoice-first copy-me file (`profile: business`, AP/AR). Do not invent keys; comments there are the schema.

| File | Use when | Example filename |
|------|----------|------------------|
| [`academic.yaml`](academic.yaml) | Papers, preprints, theses | `20260101 Smith Nature Attention Is All You Need.pdf` |
| [`er-ar.yaml`](er-ar.yaml) | German ER/AR (Eingangsrechnung / Ausgangsrechnung) | `20260906 ACME ER 12,13.pdf` |
| [`ollama-offline.yaml`](ollama-offline.yaml) | Local LLM + PaddleOCR, no API key | `20260906 ACME AP 12,13.pdf` |
| [`vision-cloud.yaml`](vision-cloud.yaml) | Scans via LLM vision, no PaddleOCR | `20260906 ACME AP 12,13.pdf` |
| [`invoice-id.yaml`](invoice-id.yaml) | Keep amount and add the printed invoice number | `20260906 ACME AP 12,13 12345.pdf` |

One-run override without copying a file:

```powershell
.\autorename-pdf-cli.exe rename --profile academic paper.pdf
```

Validate before renaming (from a git clone):

```bash
python autorename-pdf.py config validate --config examples/academic.yaml --output json
```
