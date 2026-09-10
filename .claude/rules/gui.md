---
paths:
  - "gui/**"
---

# GUI

- Vanilla TypeScript. No React/Vue/Svelte.
- Python only via sidecar `autorename-pdf-cli` (`gui/src/lib/sidecar.ts`). Do not reimplement rename/undo/config in the frontend.
- Package manager is **pnpm** (`gui/pnpm-lock.yaml`). `build.py` uses `pnpm install --frozen-lockfile`. Ignore `package-lock.json`.
- CSS: Tailwind 4 CLI → `gui/assets/css/output.css` (gitignored). `pnpm -C gui build:css`.
- Tests: Vitest next to the module (`gui/src/**/*.test.ts`). `pnpm -C gui test:run` / `typecheck`.
