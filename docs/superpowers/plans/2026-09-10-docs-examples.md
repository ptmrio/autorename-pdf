# README and example configs Implementation Plan

> **For agentic workers:** Inline execution in the originating session. Do not commit unless the user asks.

**Goal:** Invoice-first one-stop `config.yaml.example`, GitHub `examples/` recipes, and a shorter example-led README that an unfamiliar LLM can configure from.

**Architecture:** Root copy-me YAML documents every key. `examples/*.yaml` are complete valid configs. README points at those files instead of restating overlay essays. A pytest contract loads and validates every shipped example.

**Tech Stack:** YAML v2 config, pytest, existing `_validate_config` / `load_yaml_config`.

## Global Constraints

- `profile: business` and AP/AR remain the copied defaults.
- Do not change `_config_loader.DEFAULTS`.
- Never commit `config.yaml` or `harmonized-company-names.yaml`.
- Portable ZIP stays flat; do not add `examples/` to `BUNDLE_FILES`.
- No GUI/phase-2 work. No screenshot recapture in this plan.

---

### Task 1: Shipped-example validation contract

**Files:**
- Create: `tests/test_example_configs.py`

- [ ] **Step 1: Write the failing test** that loads `config.yaml.example` and every `examples/*.yaml`, asserts `valid is True` with no error-level issues, invoice-first root defaults, academic selection, DATEV `ER`, and ollama empty-key success.

- [ ] **Step 2: Run it to confirm examples/ is missing**

Run: `venv\Scripts\python.exe -m pytest tests/test_example_configs.py -v`

- [ ] **Step 3: Add YAML recipes + rewrite root example and README**

- [ ] **Step 4: Re-run pytest and `config validate --output json` on each file**

- [ ] **Step 5: Update AGENTS.md, CLAUDE.md, build skill pointers**

Do not commit.
