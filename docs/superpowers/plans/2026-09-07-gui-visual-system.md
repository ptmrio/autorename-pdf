# GUI Visual System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix unreadable helper/status colors, stop treating the empty queue as “app is healthy”, and make theme/titlebar/Settings match the PhraseVault token roles without a redesign.

**Architecture:** Keep vanilla TS + Tailwind 4 + existing component CSS. Change semantic tokens in `theme-variables.css`, separate readiness from queue state, and honest read-only Settings chrome. No new framework, no Mica, no writable config form.

**Tech Stack:** Tailwind 4 CLI (`pnpm -C gui build:css`), Vitest, jsdom, Tauri window API.

## Global Constraints

- Vanilla TypeScript. No React/Vue/Svelte.
- Python only via sidecar. This plan does not add config writes.
- pnpm for GUI. After CSS edits run `pnpm -C gui build:css`. Do not hand-edit `gui/assets/css/output.css`.
- Keep PDF red primary ramp. Do not copy PhraseVault orange/Marcellus/modal Settings.
- Dry Run is relabeled **Preview names**. Rename stays the primary button.
- `clearFiles()` must not clear `statusError` or `lastBatchId`.
- `localStorage.theme` stores `system` | `light` | `dark` (preference), never only the resolved OS appearance written on first launch.
- Existing `state.test.ts` cases that expect `clearFiles` to reset `statusError` / `lastBatchId` document a bug; change them to match the spec.
- `pnpm -C gui test:run` and `pnpm -C gui typecheck` after each GUI task.

## Improver revisions (applied 2026-09-07)

Codex improve: ship with revisions; 0 tasks. Binding deltas:

- Retry uses `validateConfig()` until `inspectConfig` exists; do not statically import `inspectConfig` in this plan.
- Task 3 owns Undo-on-empty, `lastBatchId` lifecycle (undo clears, new rename replaces). Task 4 owns readiness/copy/labels only.
- Inject a window handle into `initTitlebar` for tests. Do not move the outer `data-tauri-drag-region` unless a manual drag check fails.
- Do not globally remap `--color-danger`/`success`/`info` in `.dark`; override only small-text selectors. Drop `theme-tokens.test.ts` greps; use `build:css` plus later Astra visual.
- Settings: three groups, static rows not disabled inputs, both `PP-OCRv6_small_det` and `PP-OCRv6_small_rec` in hints, banner before values.
- Toggle: explicit light↔dark only, never writes `system`. Banner `role="alert"` only after a user-triggered failed Retry/Validate.

---

### Task 1: Semantic tokens, `--color-primary`, focus ring

**Files:**
- Modify: `gui/src/css/theme-variables.css`
- Modify: `gui/src/css/platform.css` (`:focus-visible`)
- Modify: `gui/src/css/components/buttons.css` (primary focus)
- Modify: `gui/src/css/components/filelist.css` (status text colors, name size/select)
- Test: `gui/src/css/theme-tokens.test.ts` (new; read file text — CSS has no runtime)

**Interfaces:**
- Consumes: generated `--color-secondary-*`, `--color-primary-*`, `--color-danger-*`, `--color-success-*`, `--color-info-*`
- Produces: mappings listed in spec `docs/superpowers/specs/2026-09-07-gui-visual-system.md` P0 contrast section.

- [ ] **Step 1: Write the failing test**

Create `gui/src/css/theme-tokens.test.ts`:

```typescript
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const dir = dirname(fileURLToPath(import.meta.url));
const theme = readFileSync(join(dir, 'theme-variables.css'), 'utf8');
const platform = readFileSync(join(dir, 'platform.css'), 'utf8');
const buttons = readFileSync(join(dir, 'components/buttons.css'), 'utf8');
const filelist = readFileSync(join(dir, 'components/filelist.css'), 'utf8');

describe('theme tokens', () => {
  it('maps light muted/tertiary to secondary-600', () => {
    const root = theme.split('.dark')[0];
    expect(root).toMatch(/--text-muted:\s*var\(--color-secondary-600\)/);
    expect(root).toMatch(/--text-tertiary:\s*var\(--color-secondary-600\)/);
  });

  it('defines --color-primary as primary-600', () => {
    expect(theme).toMatch(/--color-primary:\s*var\(--color-primary-600\)/);
  });

  it('uses --focus-ring for global focus-visible', () => {
    expect(platform).toMatch(/outline:\s*2px solid var\(--focus-ring\)/);
    expect(platform).not.toMatch(/outline:\s*2px solid var\(--color-primary-500\)/);
  });

  it('gives primary buttons a light inset focus ring', () => {
    expect(buttons).toMatch(/box-shadow:\s*inset 0 0 0 2px #fff/);
  });

  it('uses darker info/success/danger for small light-theme names', () => {
    expect(filelist).toMatch(/--color-info-700/);
    expect(filelist).toMatch(/--color-success-700/);
    expect(filelist).toMatch(/--color-danger-700/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/css/theme-tokens.test.ts`

Expected: FAIL — muted is still secondary-400; `--color-primary` undeclared.

- [ ] **Step 3: Write minimal implementation**

`theme-variables.css` light `:root`:

```css
  --bg-secondary: var(--color-secondary-100, #e4e8ed);
  --bg-elevated: #ffffff;
  --text-tertiary: var(--color-secondary-600, #4f5f74);
  --text-muted: var(--color-secondary-600, #4f5f74);
  --focus-ring: var(--color-primary-500, #d2161c);
  --color-primary: var(--color-primary-600);
```

`.dark`:

```css
  --text-tertiary: var(--color-secondary-300, #acb8ca);
  --text-muted: var(--color-secondary-300, #acb8ca);
  --focus-ring: var(--color-primary-400, #fd574d);
  --color-primary: var(--color-primary-600);
  --color-danger: var(--color-danger-400, #fd574e);
  --color-success: var(--color-success-400, #40b261);
  --color-info: var(--color-info-400, #10a3e8);
```

Keep light `--color-danger` / success / info as the 500 fills in the shared status block; **override file-row text** in `filelist.css`:

```css
.fq-new-name {
  font-size: var(--font-size-sm);
  user-select: text;
}
.fq-name {
  user-select: text;
}
.fq-new-name-preview {
  color: var(--color-info-700, #004d72);
}
.dark .fq-new-name-preview {
  color: var(--color-info-400, #10a3e8);
}
.fq-new-name-renamed {
  color: var(--color-success-700, #035725);
}
.dark .fq-new-name-renamed {
  color: var(--color-success-400, #40b261);
}
.fq-error {
  color: var(--color-danger-700, #89090e);
}
.dark .fq-error {
  color: var(--color-danger-400, #fd574e);
}
```

`platform.css` `:focus-visible`:

```css
:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: -2px;
  position: relative;
  z-index: var(--focus-z, 101);
}
```

`buttons.css` `@utility btn-primary` add:

```css
  &:focus-visible {
    outline: none;
    box-shadow: inset 0 0 0 2px #fff;
  }
```

Run `pnpm -C gui build:css`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm -C gui test:run src/css/theme-tokens.test.ts && pnpm -C gui build:css`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/css/theme-variables.css gui/src/css/platform.css gui/src/css/components/buttons.css gui/src/css/components/filelist.css gui/src/css/theme-tokens.test.ts
git commit -m "fix: raise muted contrast and define --color-primary for progress and drop hover"
```

---

### Task 2: Theme preference `system` | `light` | `dark`

**Files:**
- Modify: `gui/src/lib/theme.ts`
- Test: `gui/src/lib/theme.test.ts` (create)
- Modify: `gui/src/renderer.ts` only if `toggleTheme` signature changes

**Interfaces:**
- Consumes: `localStorage.theme`, `prefers-color-scheme`
- Produces:

```typescript
export type ThemePreference = 'system' | 'light' | 'dark';
export function applyTheme(preference: ThemePreference): void;
export function initTheme(): void;
export function toggleTheme(): void; // light <-> dark explicit
```

Default when key missing: `system`. `initTheme` must **not** write `light`/`dark` on first launch. `toggleTheme` sets explicit `light` or `dark` (does not cycle through `system` in this delivery).

- [ ] **Step 1: Write the failing tests**

`gui/src/lib/theme.test.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('theme preference', () => {
  let darkMql: { matches: boolean; addEventListener: ReturnType<typeof vi.fn>; removeEventListener: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    darkMql = {
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
    vi.stubGlobal('matchMedia', vi.fn((query: string) => {
      if (query.includes('prefers-color-scheme: dark')) return darkMql;
      return { matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() };
    }));
    vi.resetModules();
    await import('./theme');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('defaults to system and does not persist light/dark on first init', async () => {
    vi.resetModules();
    const { initTheme } = await import('./theme');
    initTheme();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem('theme')).toBe('system');
  });

  it('stored light ignores OS dark', async () => {
    localStorage.setItem('theme', 'light');
    vi.resetModules();
    const { initTheme } = await import('./theme');
    initTheme();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    const change = darkMql.addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1];
    change?.({ matches: true });
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('system preference follows OS changes', async () => {
    localStorage.setItem('theme', 'system');
    vi.resetModules();
    const { initTheme } = await import('./theme');
    initTheme();
    const change = darkMql.addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1];
    change?.({ matches: false });
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('system');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/lib/theme.test.ts`

Expected: FAIL — `initTheme` writes `dark` into localStorage.

- [ ] **Step 3: Write minimal implementation**

```typescript
export type ThemePreference = 'system' | 'light' | 'dark';

function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolve(preference: ThemePreference): 'light' | 'dark' {
  return preference === 'system' ? getSystemTheme() : preference;
}

export function applyTheme(preference: ThemePreference): void {
  document.documentElement.classList.toggle('dark', resolve(preference) === 'dark');
  localStorage.setItem('theme', preference);
}

export function initTheme(): void {
  const raw = localStorage.getItem('theme');
  const preference: ThemePreference =
    raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system';
  applyTheme(preference);

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (localStorage.getItem('theme') === 'system') {
      document.documentElement.classList.toggle('dark', e.matches);
    }
  });
}

export function toggleTheme(): void {
  const current = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}
```

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/lib/theme.test.ts && pnpm -C gui typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/lib/theme.ts gui/src/lib/theme.test.ts
git commit -m "fix: store theme preference including system instead of freezing the OS appearance"
```

---

### Task 3: Readiness vs queue in state

**Files:**
- Modify: `gui/src/lib/state.ts` `clearFiles`
- Modify: `gui/src/lib/state.test.ts`
- Modify: `gui/src/views/files.ts` Undo enabled from `lastBatchId`

**Interfaces:**
- Consumes: `AppState`
- Produces: `clearFiles()` sets `files: []`, `dryRunResult: null`, `lastResult: null`, `progress: ''` and leaves `statusError` and `lastBatchId` unchanged.

- [ ] **Step 1: Rewrite the failing (currently inverted) tests**

In `gui/src/lib/state.test.ts` replace the `clearFiles` examples:

```typescript
describe('clearFiles', () => {
  it('resets files, results, and progress', () => {
    addFiles(['/a.pdf']);
    setState({ progress: 'Processing...', dryRunResult: makeBatchResult([]) });
    clearFiles();
    const s = getState();
    expect(s.files).toEqual([]);
    expect(s.dryRunResult).toBeNull();
    expect(s.lastResult).toBeNull();
    expect(s.progress).toBe('');
  });

  it('keeps statusError when the queue is cleared', () => {
    setState({ statusError: 'CLI executable not found' });
    clearFiles();
    expect(getState().statusError).toBe('CLI executable not found');
  });

  it('keeps lastBatchId so Undo survives Clear', () => {
    setState({ lastBatchId: '20260319T120000-abc123' });
    clearFiles();
    expect(getState().lastBatchId).toBe('20260319T120000-abc123');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm -C gui test:run src/lib/state.test.ts`

Expected: FAIL — `statusError` still cleared.

- [ ] **Step 3: Write minimal implementation**

```typescript
export function clearFiles(): void {
  setState({ files: [], dryRunResult: null, lastResult: null, progress: '' });
}
```

In `files.ts` `renderFileList`, Undo visibility:

```typescript
  const canUndo = Boolean(state.lastBatchId) && !busy;
```

Show the Undo button when `canUndo` even if `lastResult` is null (queue cleared). Keep Add More as today when `lastResult` is set **or** when files exist. Minimal: if `canUndo && !hasResults`, still render Undo + Add More + Clear:

```typescript
  if (hasResults || canUndo) {
    actionsHtml = `
      <div class="fq-actions-left">
        <button class="btn btn-secondary btn-sm" id="btn-undo" ${!canUndo || busy ? 'disabled' : ''}>Undo Last</button>
        <button class="btn btn-primary btn-sm" id="btn-add-more" ${busy ? 'disabled' : ''}>Add More Files</button>
      </div>`;
  }
```

When the queue is empty, `renderEmpty` runs — Undo must still be available. Add an Undo control on the empty view when `lastBatchId` is set (Task 4 banner/actions). For this task, export nothing new; Task 4 places Undo on empty+banner. Here only fix `clearFiles` + list-view Undo disable predicate: `${busy || !state.lastBatchId ? 'disabled' : ''}` instead of showing Undo only when `hasResults`.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/lib/state.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/lib/state.ts gui/src/lib/state.test.ts gui/src/views/files.ts
git commit -m "fix: keep CLI errors and undo batch id when the file queue is cleared"
```

---

### Task 4: Files readiness banner, example name, Preview names

**Files:**
- Modify: `gui/src/views/files.ts`
- Modify: `gui/src/css/components/filelist.css` (optional `.ready-banner`)
- Test: `gui/src/views/files.test.ts` (create)

**Interfaces:**
- Consumes: `getState().statusError`, `lastBatchId`
- Produces: empty and queued Files views include a `role="status"` banner `#ready-banner` when `statusError` is nonempty. Empty hint includes `20260907 ACME AP.pdf`. Button `#btn-dry-run` label is `Preview names`. `#btn-retry-ready` calls `inspectConfig({ force: true })` and updates `statusError` like `main.ts`.

- [ ] **Step 1: Write the failing tests**

`gui/src/views/files.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/sidecar', () => ({
  renamePdfs: vi.fn(),
  undoRename: vi.fn(),
  isErrorResult: (r: { success: boolean }) => !r.success,
  getUndoLogDir: vi.fn(async () => 'D:\\runtime'),
  inspectConfig: vi.fn(),
}));

vi.mock('../lib/filepicker', () => ({
  pickPdfFiles: vi.fn(async () => []),
  pickFolder: vi.fn(async () => []),
}));

vi.mock('../lib/dnd', () => ({
  setupDragDrop: vi.fn(() => () => {}),
}));

vi.mock('../lib/toast', () => ({ showToast: vi.fn() }));
vi.mock('../lib/rename-cache', () => ({ applyCachedRenames: vi.fn() }));

import { renderFilesView } from './files';
import { setState } from '../lib/state';

describe('files readiness', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    setState({
      view: 'files',
      files: [],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: 'CLI executable not found',
      lastBatchId: null,
    });
  });

  it('shows a persistent banner on the empty dropzone', () => {
    renderFilesView(document.getElementById('root')!);
    const banner = document.getElementById('ready-banner');
    expect(banner).not.toBeNull();
    expect(banner!.getAttribute('role')).toBe('status');
    expect(banner!.textContent).toMatch(/CLI executable not found/);
    expect(document.getElementById('btn-browse-files')).not.toBeNull();
  });

  it('relabels dry run to Preview names when files are queued', () => {
    setState({
      view: 'files',
      files: [{ path: 'D:\\a.pdf', name: 'a.pdf', status: 'pending' }],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: '',
      lastBatchId: null,
    });
    renderFilesView(document.getElementById('root')!);
    expect(document.getElementById('btn-dry-run')!.textContent).toMatch(/Preview names/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/views/files.test.ts`

Expected: FAIL — no `#ready-banner`.

- [ ] **Step 3: Write minimal implementation**

Helper in `files.ts`:

```typescript
function renderReadyBanner(state: AppState): string {
  if (!state.statusError) return '';
  const hint = state.statusError.includes('CLI')
    ? 'Re-extract the portable ZIP, or run python build.py --cli-only --nosign if developing.'
    : 'Create config.yaml next to the executable from config.yaml.example.';
  return `
    <div id="ready-banner" class="ready-banner" role="status">
      <p>${state.statusError}</p>
      <p class="ready-banner-hint">${hint}</p>
      <button type="button" class="btn btn-secondary btn-sm" id="btn-retry-ready">Retry</button>
    </div>`;
}
```

Insert `renderReadyBanner(getState())` at the top of `renderEmpty` and `renderFileList` containers. Bind `#btn-retry-ready` to:

```typescript
import { inspectConfig, isErrorResult, ... } from '../lib/sidecar';

async function retryReadiness(): Promise<void> {
  try {
    const snapshot = await inspectConfig({ force: true });
    if (!snapshot.valid && snapshot.issues.some((i) => i.level === 'error')) {
      setState({ statusError: 'Config error' });
    } else {
      setState({ statusError: '' });
    }
  } catch (err) {
    const errStr = String(err);
    if (errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries')) {
      setState({ statusError: 'CLI executable not found' });
    } else {
      setState({ statusError: 'Config error' });
    }
  }
}
```

Empty copy: add under the hint span:

```html
<span class="text-sm text-[var(--text-muted)]">Example: 20260907 ACME AP.pdf</span>
```

Change Dry Run button text to `Preview names`.

CSS `.ready-banner` in `filelist.css`:

```css
.ready-banner {
  margin: 0.75rem 1rem 0;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  background: var(--bg-elevated);
  color: var(--text-primary);
  border-radius: 0.5rem;
}
.ready-banner-hint {
  color: var(--text-muted);
  font-size: var(--font-size-sm);
  margin: 0.25rem 0 0.5rem;
}
```

Empty view: if `lastBatchId`, include Undo button next to Browse (same `handleUndo`).

If `inspectConfig` is not yet on sidecar because config plan Task 4 is unfinished, Retry may call `validateConfig()` until inspect lands. Prefer `inspectConfig` when exported; otherwise `validateConfig` then `setState({ statusError: ... })`. Do not block this task on Python inspect if the GUI cache work is not merged — use `validateConfig` as the Retry call in that case and switch to `inspectConfig` in a tiny follow-up in the same commit if the export exists.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/views/files.test.ts && pnpm -C gui typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/views/files.ts gui/src/views/files.test.ts gui/src/css/components/filelist.css
git commit -m "fix: show sidecar and config failures on the Files view instead of only the footer"
```

---

### Task 5: Settings read-only inspector chrome

**Files:**
- Modify: `gui/src/views/settings.ts`
- Test: `gui/src/views/settings.test.ts`

**Interfaces:**
- Consumes: existing SECTIONS
- Produces: on successful load, `#settings-readonly-banner` with text `Configuration — read only`. OCR detection-model hint contains `PP-OCRv6_small_det`. Section titles: `AI connection` (was AI Provider), `Documents and naming` wrapping pdf+company+output (may keep three `SectionDef`s but render a group heading), PaddleOCR stays in the existing advanced block.

- [ ] **Step 1: Write the failing tests**

```typescript
  it('shows a read-only banner above fields when config loads', async () => {
    getConfig.mockResolvedValue({ ai: { provider: 'openai' }, pdf: {}, company: { name: 'A' }, output: {} });
    validateConfig.mockResolvedValue({ valid: true, issues: [] });
    await renderSettingsView(document.getElementById('root')!);
    const banner = document.getElementById('settings-readonly-banner');
    expect(banner).not.toBeNull();
    expect(banner!.textContent).toMatch(/Configuration — read only/);
    expect(banner!.textContent).toMatch(/config\.yaml/);
  });

  it('documents PP-OCRv6 small det as the empty detection-model default', async () => {
    const { SECTIONS } = await import('./settings');
    const det = SECTIONS.flatMap((s) => s.fields).find((f) => f.key === 'detection_model');
    expect(det?.hint).toMatch(/PP-OCRv6_small_det/);
  });
```

`SECTIONS` is currently not exported. Export it as `export const SECTIONS` for the hint test, or query the rendered hint text after load with paddleocr section visible. Prefer exporting `SECTIONS`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm -C gui test:run src/views/settings.test.ts`

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Insert at the start of the successful `contentEl.innerHTML`:

```html
<div id="settings-readonly-banner" class="settings-readonly-banner">
  <p class="settings-readonly-title">Configuration — read only</p>
  <p>Edit config.yaml next to the app to change these values.</p>
</div>
```

Rename section titles: `'AI Provider'` → `'AI connection'`; `'PDF Processing'` → `'Documents and naming'` (keep company/output as subsections or merge titles only). Change detection_model hint to:

`'Leave empty for default PP-OCRv6_small_det. Use PP-OCRv5_server_det for higher accuracy (more RAM)'`

Add a few lines in `settings.css`:

```css
.settings-readonly-banner {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  border-radius: 0.5rem;
}
.settings-readonly-title {
  font-weight: var(--font-weight-medium);
}
```

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/views/settings.test.ts && pnpm -C gui typecheck && pnpm -C gui build:css`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/views/settings.ts gui/src/views/settings.test.ts gui/src/css/components/settings.css
git commit -m "fix: label Settings as a read-only config inspector and correct the OCR default hint"
```

---

### Task 6: Titlebar restore label, drag region, kill progress pulse

**Files:**
- Modify: `gui/src/lib/titlebar.ts`
- Modify: `gui/index.html` (optional `data-tauri-drag-region` on `.titlebar-left`)
- Modify: `gui/src/css/components/filelist.css` `.fq-progress-text`
- Test: `gui/src/lib/titlebar.test.ts` (create)

**Interfaces:**
- Consumes: `getCurrentWindow().isMaximized()`, `onResized`
- Produces: `#btn-maximize` `aria-label` is `Restore` when maximized, `Maximize` otherwise. `.fq-progress-text` has no `animation: pulse`. Processing text has `role="status"`.

- [ ] **Step 1: Write the failing tests**

`gui/src/lib/titlebar.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';

const isMaximized = vi.fn(async () => true);
const onResized = vi.fn(async () => () => {});

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    minimize: vi.fn(),
    toggleMaximize: vi.fn(),
    close: vi.fn(),
    isMaximized,
    onResized,
  }),
}));

import { initTitlebar } from './titlebar';

describe('titlebar maximize label', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <button id="btn-minimize"></button>
      <button id="btn-maximize" aria-label="Maximize"></button>
      <button id="btn-close"></button>
    `;
  });

  it('sets Restore when the window reports maximized', async () => {
    initTitlebar();
    await vi.waitFor(() => {
      expect(document.getElementById('btn-maximize')!.getAttribute('aria-label')).toBe('Restore');
    });
  });
});
```

`gui/src/css/theme-tokens.test.ts` add (or this file reads CSS):

```typescript
  it('does not pulse progress text', () => {
    expect(filelist).not.toMatch(/\.fq-progress-text[\s\S]*animation:\s*pulse/);
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm -C gui test:run src/lib/titlebar.test.ts src/css/theme-tokens.test.ts`

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
import { getCurrentWindow } from '@tauri-apps/api/window';

async function syncMaximizeLabel(): Promise<void> {
  const btn = document.getElementById('btn-maximize');
  if (!btn) return;
  try {
    const max = await getCurrentWindow().isMaximized();
    btn.setAttribute('aria-label', max ? 'Restore' : 'Maximize');
  } catch {
    /* jsdom / non-Tauri */
  }
}

export function initTitlebar(): void {
  const appWindow = getCurrentWindow();
  document.getElementById('btn-minimize')?.addEventListener('click', () => {
    void appWindow.minimize();
  });
  document.getElementById('btn-maximize')?.addEventListener('click', () => {
    void appWindow.toggleMaximize().then(() => syncMaximizeLabel());
  });
  document.getElementById('btn-close')?.addEventListener('click', () => {
    void appWindow.close();
  });
  void syncMaximizeLabel();
  void appWindow.onResized(() => {
    void syncMaximizeLabel();
  });
}
```

`index.html`: move `data-tauri-drag-region` from the outer `.titlebar` onto `.titlebar-left` only (controls must not be in the drag region). If the outer bar loses drag on empty chrome, keep it on `.titlebar` **and** add it to `.titlebar-left`; never on `.titlebar-controls`.

`.fq-progress-text`: delete `animation: pulse …`. In `files.ts` progress span add `role="status"`.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run && pnpm -C gui typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/src/lib/titlebar.ts gui/src/lib/titlebar.test.ts gui/index.html gui/src/css/components/filelist.css gui/src/views/files.ts gui/src/css/theme-tokens.test.ts
git commit -m "fix: expose Restore on the maximize button and stop implying progress with a pulse"
```
