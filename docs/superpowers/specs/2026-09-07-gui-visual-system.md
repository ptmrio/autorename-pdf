# GUI visual system

Date: 2026-09-07

Status: locked for implementation

This is the binding product specification for AutoRename-PDF’s Tauri GUI look and interaction. It retains the Astra visual research dated 2026-09-07 and the owner’s synthesis: keep the PhraseVault-derived vanilla TypeScript + Tailwind 4 system; do not redesign; do not invert Dry Run vs Rename into a new primary action.

## Scope and defaults

This delivery is P0 (contrast, undefined accent, readiness) plus a small P1 set (theme preference, titlebar state, Settings as a honest read-only inspector, filename density, Dry Run label).

Non-goals: React/Vue/Electron, Mica or acrylic, PhraseVault orange/Marcellus/modal settings, writable Settings form (blocked on config phase 2), 44px touch targets, Snap-layout `WM_NCHITTEST`, reducing min window below 700px, dashboard empty state, moving About under Settings (P2), copying `packages/shared` as a runtime dependency.

Stack stays vanilla TS, Tailwind 4 CLI → `gui/assets/css/output.css` via `pnpm -C gui build:css`. Do not hand-edit `output.css`. Python only via sidecar.

## Design kinship

Reuse PhraseVault **roles**, not its brand:

| Keep from shared/PhraseVault | Do not copy |
|---|---|
| 15px body / 13px secondary / 12px caption | Marcellus, orange primary |
| 32px titlebar, 46px caption buttons | Settings-as-modal, tab rail, Save/Cancel draft |
| Accessibility.css reduced-motion / forced-colors | Electron `-webkit-app-region` |
| Bottom-right toasts | Carbon top-right placement |

AutoRename keeps PDF red (`--color-primary-*` ramp already generated).

## P0 — contrast and accents

Lock these token mappings in `gui/src/css/theme-variables.css` (values are AutoRename’s generated ramp, not PhraseVault’s):

**Light (`:root`)**

- `--text-tertiary` and `--text-muted`: `var(--color-secondary-600)` (`#4f5f74`, not secondary-400)
- `--bg-secondary`: `var(--color-secondary-100)`
- `--bg-elevated`: `#ffffff`
- `--bg-primary` / canvas: keep `var(--color-secondary-50)`
- `--focus-ring`: `var(--color-primary-500)`

**Dark (`.dark`)**

- `--text-tertiary` and `--text-muted`: `var(--color-secondary-300)`
- `--color-danger` used as **small text** on `--bg-secondary` / status surface: `var(--color-danger-400)` (keep `--color-danger-500` for fills/dots)
- `--color-success` as small filename text: `var(--color-success-400)`
- `--color-info` as small preview filename text: `var(--color-info-400)`

**Light small status text** (file rows): preview names use `var(--color-info-700)`; renamed names use `var(--color-success-700)`; errors use `var(--color-danger-700)`.

Define `--color-primary: var(--color-primary-600)` in `:root` and `.dark` so `filelist.css` / drop-zone hover / progress bar stop referencing an undefined custom property.

Primary filled buttons: `:focus-visible` uses a **white** (or `currentColor` on the icon) 2px inset ring, not `primary-500` on `primary-600`. Global `:focus-visible` in `platform.css` must consume `var(--focus-ring)`, not a hardcoded `primary-500`.

Dashed drop-zone border may stay decorative; do not spend this delivery on a WCAG campaign against every 1:1 separator. Helper copy on the empty state must use `--text-secondary` / `--text-muted` after the token fix.

Regenerate CSS with `pnpm -C gui build:css` after token edits.

## P0 — readiness vs queue

Separate four facts in `gui/src/lib/state.ts`:

| Field | Meaning | Cleared by |
|---|---|---|
| `statusError` | App not ready (missing CLI, bad config) | Successful inspect with `valid: true`, or Retry that succeeds |
| `files` | Current queue | Clear / new session |
| `lastBatchId` | Undo target | Successful undo of that batch, or a new **successful rename** that replaces it |
| `lastResult` / `dryRunResult` | Display of last job | Clear queue **may** clear display results; must **not** clear `statusError` or `lastBatchId` |

`clearFiles()` today wipes `statusError` and `lastBatchId`. That is a bug: emptying the drop zone does not repair a missing sidecar and must not hide Undo.

Undo in the files view is enabled when `lastBatchId` is nonempty and not `processing`, independent of whether the queue was cleared.

**Files view** must show a persistent, non-toast readiness banner when `statusError` is set: the existing human strings (`CLI executable not found`, `Config error`) plus the existing Settings recovery hint (open/create `config.yaml`, re-extract ZIP). Place it in the Files workspace (empty and queued). Footer status may repeat a short form; it is not sufficient alone.

Retry: the existing startup inspect path; a control on the banner re-runs `inspectConfig({ force: true })` (phase-1 config spec). Do not use a 5-second toast as the only explanation.

Existing `state.test.ts` cases that expect `clearFiles()` to reset `statusError` / `lastBatchId` are documenting the bug; change the tests to match this spec.

## P1 — theme preference

`localStorage` key `theme` stores **preference**: `system` | `light` | `dark`. Never write the resolved OS appearance into that key.

- `applyTheme(preference)` sets `document.documentElement.classList` `.dark` from the resolved appearance, and stores the preference.
- `initTheme()` reads preference (default `system` if missing). The `prefers-color-scheme` listener updates the class **only** when preference is `system`.
- `toggleTheme()` cycles `light` → `dark` → `system` → `light` (or light/dark only if the titlebar control stays a binary toggle: then it sets explicit `light`/`dark` and does not claim to follow the OS). **Lock:** the titlebar/theme button toggles explicit light/dark; a Settings appearance row later can expose System. For this delivery, add `system` as the default when no key exists, and stop `initTheme` from writing `light`/`dark` on first launch.
- `index.html` may keep `class="dark"` as a FOUC fallback; `initTheme` runs on `DOMContentLoaded` and corrects it.

## P1 — workspace copy and density

- Empty dropzone layout stays. Add one example line under the hint: `20260907 ACME AP.pdf`.
- Relabel **Dry Run** → **Preview names**. Keep **Rename N files** as the primary button. Do not demote Rename to a hidden expert path.
- Proposed/renamed filenames: `var(--font-size-sm)` (13px), not 10px badges for the name itself. Badges may stay 10–12px.
- Original and proposed names are `user-select: text` (override the global button `user-select: none` only on `.fq-name` / `.fq-new-name`).

Do not rewrite `files.ts` into a virtual list. Patching full `innerHTML` on every progress tick is accepted for this delivery if the readiness banner still renders; a stable header/list split is allowed if a task stays small.

## P1 — Settings is a read-only inspector

Keep the full-window Settings view. At the **top** of the content column, before fields:

- Title line: `Configuration — read only`
- One sentence: `Edit config.yaml next to the app to change these values.`
- Keep **Open Config Location** and **Validate** in the footer.

Do not style read-only values as disabled form controls if they are not editable. Group existing fields as:

1. AI connection (provider, model, key availability)
2. Documents and naming (company, output, OCR, vision independently)
3. Advanced (the existing collapsed advanced block)

Do not add a profile editor. Do not add writable inputs. OCR model hint text must match `config.yaml.example` (`PP-OCRv6_small_det` / `PP-OCRv6_small_rec`), not a stale v5 string if one is hard-coded.

## P1 — titlebar

Keep custom chrome. `initTitlebar` must:

- Update maximize button `aria-label` to `Restore` when maximized, `Maximize` otherwise (listen to Tauri `onResized` / `isMaximized`).
- Leave window controls **outside** `data-tauri-drag-region` (already true). Verify `.titlebar-left` dragging: if clicks on the title do not drag, add `data-tauri-drag-region` on `.titlebar-left` only, not on the buttons.

Do not implement Snap flyouts. Do not switch to native decorations.

## Accessibility (this delivery only)

- Readiness banner: `role="status"` for non-urgent CLI-missing; `role="alert"` only when a validate action just failed.
- Processing progress text: `role="status"` on `.fq-progress-text`.
- Do not add a live region that dumps every CLI stderr line.
- Keep `accessibility.css`. Remove the pulsating animation on `.fq-progress-text` (text stays; CSS `animation: pulse` goes). Reduced-motion already kills animation globally; still remove the pulse so meaning is not motion-only.

## Testing

- `theme.test.ts`: no stored key → follows OS; stored `light` ignores OS change; stored `system` follows OS change.
- `state.test.ts`: `clearFiles` keeps `statusError` and `lastBatchId`.
- `files` view test: when `statusError` is set and `files` is empty, banner is in the document; Browse still exists.
- Settings: read-only banner present on successful load.
- `pnpm -C gui test:run` and `pnpm -C gui typecheck`.
- After CSS changes: `pnpm -C gui build:css`.

Visual acceptance (Astra, after implementation): empty Files in both themes, missing-CLI banner, Settings read-only header, theme toggle, Preview names label. Do not require a packaged Snap-layout test.
