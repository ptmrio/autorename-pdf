# GUI Phase 1 Close-Out Implementation Plan

> **Astra improve (2026-09-10):** ship with revisions; 0 tasks. Ownership table below is the execution map. Do not load harness-subagent or re-plan phase 1.

**Goal:** Close GUI phase 1 by shipping the leftover UI (filename copy/tooltip, Settings System appearance, About dark/links, titlebar drag) on top of the already-implemented inspect/cache/spawn/readiness work, then prove it in a real Tauri window.

**Architecture:** Do not reopen config inspect, YAML writes, or a redesign. UI tasks patch vanilla TS + existing CSS tokens. Native proof is a parent gate (`build.py --cli-only --nosign` then `pnpm -C gui tauri dev`), not a Fable job. Phase 2 (`config apply`, writable Settings, persistent sidecar) is out of this plan.

**Tech Stack:** Vanilla TypeScript, Tailwind 4 CLI (`pnpm -C gui build:css`), Vitest/jsdom, Tauri 2, project venv for Python gates.

## Global Constraints

- Specs: `docs/superpowers/specs/2026-09-07-gui-cli-config.md` and `docs/superpowers/specs/2026-09-07-gui-visual-system.md`. Visual spec wins over frontend-design defaults.
- **Do not redesign.** Keep PDF red (`--color-primary-*`), PhraseVault roles (15/13/12 type, 32px titlebar, bottom-right toasts). No orange, Marcellus, Mica, React, new typefaces, or SaaS-card kit.
- frontend-design applies as restraint only: sentence-case copy, one accent (PDF red), contrast on small text, no ALL-CAPS eyebrows beyond existing Settings/About section labels already in the tree.
- Python only via sidecar `autorename-pdf-cli`. No GUI config writes. Settings stays a read-only inspector of `config.yaml`.
- Appearance (System / Light / Dark) is **app chrome** in `localStorage.theme`, not a `config.yaml` field. Do not add it to `SECTIONS`.
- Titlebar theme button stays explicit light↔dark (`toggleTheme`). System is only the Settings row.
- `clearFiles()` must not clear `statusError` or `lastBatchId`. Dry Run label stays **Preview names**. Rename stays primary.
- Package manager is pnpm. After CSS: `pnpm -C gui build:css`. Do not hand-edit `gui/assets/css/output.css`.
- Never commit `config.yaml` or `harmonized-company-names.yaml`. Do not add `gui-*.png` or `.playwright-mcp/` to git.
- **Commit only if the human asks.** Each task ends at GREEN tests, not `git commit`. A parent brief cannot authorize a commit.
- Baseline on `feat/gui-config-and-visual` already contains inspect/cache/spawn/readiness. Do not revert those files except as a task names a surgical patch.
- Windows-only GUI. Use `venv\Scripts\python.exe` for pytest.

## Execution

| Tasks | Worker |
|---|---|
| 1–4 (UI) | Fable (Claude Code) with frontend-design, `implement-ui` |
| 5–6 (sidecar build, Tauri walk, full gates) | Parent session |

Do not start Task 5 until Tasks 1–4 are GREEN. Fable GREEN is not a phase-1 pass. An unavailable Tauri run in Task 5 stays UNVERIFIED.

## File map

| File | Responsibility |
|---|---|
| `gui/src/lib/theme.ts` | Export `getThemePreference()`; `applyTheme` already stores `system\|light\|dark` |
| `gui/src/lib/theme.test.ts` | Preference getter + Settings-driven System restore |
| `gui/src/views/files.ts` | `title` on `.fq-name` / `.fq-new-name` with escaped full string |
| `gui/src/views/files.test.ts` | title attributes on pending-preview and renamed rows, including `&` escape |
| `gui/src/css/components/filelist.css` | Keep ellipsis + `user-select: text`; no pulse on `.fq-progress-text` |
| `gui/src/views/settings.ts` | Always-visible `#settings-appearance` radiogroup |
| `gui/src/views/settings.test.ts` | System/Light/Dark; visible on sidecar-missing recovery |
| `gui/src/css/components/settings.css` | Appearance segment styles using existing tokens |
| `gui/src/views/about.ts` | Keep GitHub / license / PhraseVault `data-href` buttons |
| `gui/src/views/about.test.ts` | New: three links + Back |
| `gui/src/css/components/about.css` | Dark-theme small-text contrast if below 4.5:1 |
| `gui/index.html` | `data-tauri-drag-region` on `.titlebar-left` as well as the outer bar; never on `.titlebar-controls` |

---

### Task 1: Long filename tooltip + copy contract

**Worker:** Fable

**Files:**
- Modify: `gui/src/views/files.ts` (`renderFileRow`)
- Test: `gui/src/views/files.test.ts`

**Interfaces:**
- Consumes: existing `FileEntry.name`, `f.result?.new_name`
- Produces: `.fq-name` and `.fq-new-name` have `title` equal to the untruncated string. CSS already has `overflow: hidden; text-overflow: ellipsis; user-select: text` — do not remove it.

- [ ] **Step 1: Write the failing test**

Add to `gui/src/views/files.test.ts` inside `describe('files readiness')`. `FileEntry.status` is `'pending' | 'renamed' | 'skipped' | 'failed'` — never `'preview'`. Preview is derived: `status === 'pending'` plus `result.new_name`.

```typescript
  function longEntry(
    status: 'pending' | 'renamed',
    name: string,
    newName: string,
  ) {
    return {
      path: `D:\\\\docs\\\\${name}`,
      name,
      status,
      result: {
        file: `D:\\\\docs\\\\${name}`,
        status: 'renamed' as const,
        new_name: newName,
        new_path: `D:\\\\docs\\\\${newName}`,
        error: null,
        warnings: [],
        company: 'ACME',
        date: '2026-09-07',
        doc_type: 'AP',
        provider: 'openai',
        model: 'gpt-5.6-luna',
      },
    };
  }

  it('puts the full original and proposed names on title for preview and renamed rows', () => {
    const ampOrig = 'A & B invoice.pdf';
    const ampNew = '20260907 ACME AP A & B.pdf';
    const longOrig = `${'invoice-scan-'.repeat(8)}.pdf`;
    const longNew = '20260907 ACME AP VERY LONG COUNTERPARTY NAME HERE.pdf';
    setState({
      view: 'files',
      files: [
        longEntry('pending', ampOrig, ampNew),
        longEntry('renamed', longOrig, longNew),
      ],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: '',
      lastBatchId: null,
    });
    renderFilesView(document.getElementById('root')!);
    const names = [...document.querySelectorAll('.fq-name')] as HTMLElement[];
    const proposed = [...document.querySelectorAll('.fq-new-name')] as HTMLElement[];
    expect(names[0].getAttribute('title')).toBe(ampOrig);
    expect(proposed[0].getAttribute('title')).toBe(ampNew);
    expect(names[1].getAttribute('title')).toBe(longOrig);
    expect(proposed[1].getAttribute('title')).toBe(longNew);
    expect(document.querySelectorAll('.fq-new-name-preview').length).toBe(1);
    expect(document.querySelectorAll('.fq-new-name-renamed').length).toBe(1);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/views/files.test.ts`

Expected: FAIL — `.fq-name` has no `title`.

- [ ] **Step 3: Write minimal implementation**

In `gui/src/views/files.ts`, add next to other helpers:

```typescript
function escapeAttr(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;');
}
```

In `renderFileRow`, set titles (keep existing class names and ellipsis CSS):

```typescript
        <span class="fq-name" title="${escapeAttr(f.name)}">${f.name}</span>
```

and for the proposed name span:

```typescript
    detail = `<span class="fq-preview"><span class="fq-arrow">\u2192</span><span class="fq-new-name ${nameClass}" title="${escapeAttr(newName)}">${newName}</span></span>`;
```

Do not switch rows to wrap. Do not add a copy-to-clipboard button. Do not assert `getComputedStyle(...).userSelect`. Keep existing `filelist.css` ellipsis + `user-select: text`.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/views/files.test.ts && pnpm -C gui typecheck`

Expected: PASS.

---

### Task 2: Settings appearance row (System / Light / Dark)

**Worker:** Fable

**Files:**
- Modify: `gui/src/lib/theme.ts`
- Modify: `gui/src/lib/theme.test.ts`
- Modify: `gui/src/views/settings.ts`
- Modify: `gui/src/views/settings.test.ts`
- Modify: `gui/src/css/components/settings.css`
- Then: `pnpm -C gui build:css`

**Interfaces:**
- Consumes: existing `applyTheme(preference: ThemePreference): void`, `toggleTheme()` (unchanged: light↔dark only)
- Produces:

```typescript
export function getThemePreference(): ThemePreference;
```

`#settings-appearance` is a `role="radiogroup"` with three `role="radio"` buttons `data-theme="system|light|dark"`. Clicking calls `applyTheme`. The group is in the Settings **chrome** (header), visible on both successful inspect and sidecar-missing recovery. It is not inside `SECTIONS` and not written to `config.yaml`.

- [ ] **Step 1: Write the failing tests**

Append to `gui/src/lib/theme.test.ts` (same matchMedia stub as existing cases):

```typescript
  it('getThemePreference reads stored system without resolving OS', async () => {
    localStorage.setItem('theme', 'system');
    vi.resetModules();
    const { getThemePreference, initTheme } = await import('./theme');
    initTheme();
    expect(getThemePreference()).toBe('system');
  });
```

In `gui/src/views/settings.test.ts`, stub `matchMedia` like `theme.test.ts` (OS dark by default). Reset `localStorage` and `document.documentElement.classList` in `beforeEach`. Add:

```typescript
  it('restores System from an explicit Light preference', async () => {
    localStorage.setItem('theme', 'light');
    document.documentElement.classList.remove('dark');
    inspectConfig.mockResolvedValue(okSnapshot());
    await renderSettingsView(document.getElementById('root')!);
    const group = document.getElementById('settings-appearance')!;
    expect(group.getAttribute('role')).toBe('radiogroup');
    const labels = [...group.querySelectorAll('[data-theme]')].map((el) => el.textContent?.trim());
    expect(labels).toEqual(['System', 'Light', 'Dark']);
    const systemBtn = group.querySelector('[data-theme="system"]') as HTMLButtonElement;
    const lightBtn = group.querySelector('[data-theme="light"]') as HTMLButtonElement;
    expect(lightBtn.getAttribute('aria-checked')).toBe('true');
    expect(group.querySelectorAll('[aria-checked="true"]')).toHaveLength(1);
    systemBtn.click();
    expect(localStorage.getItem('theme')).toBe('system');
    expect(systemBtn.getAttribute('aria-checked')).toBe('true');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    const change = (window.matchMedia('(prefers-color-scheme: dark)') as unknown as {
      addEventListener: { mock: { calls: unknown[][] } };
    }).addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1] as (e: { matches: boolean }) => void;
    change?.({ matches: false });
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('system');
  });

  it('moves appearance selection with arrow keys', async () => {
    localStorage.setItem('theme', 'light');
    inspectConfig.mockResolvedValue(okSnapshot());
    await renderSettingsView(document.getElementById('root')!);
    const group = document.getElementById('settings-appearance')!;
    const lightBtn = group.querySelector('[data-theme="light"]') as HTMLButtonElement;
    lightBtn.focus();
    lightBtn.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(localStorage.getItem('theme')).toBe('dark');
    expect(group.querySelector('[data-theme="dark"]')!.getAttribute('aria-checked')).toBe('true');
    expect(group.querySelector('[data-theme="dark"]')!.getAttribute('tabindex')).toBe('0');
    expect(lightBtn.getAttribute('tabindex')).toBe('-1');
  });

  it('keeps working appearance controls when the sidecar is missing', async () => {
    localStorage.setItem('theme', 'dark');
    inspectConfig.mockRejectedValue(new Error('sidecar binaries missing'));
    await renderSettingsView(document.getElementById('root')!);
    expect(document.getElementById('btn-open-config')).not.toBeNull();
    const lightBtn = document.querySelector('#settings-appearance [data-theme="light"]') as HTMLButtonElement;
    lightBtn.click();
    expect(localStorage.getItem('theme')).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
```

If Settings tests do not yet stub `matchMedia`, copy the `theme.test.ts` `beforeEach` stub into this file so System can follow OS. `initTheme` must already have run (app boot); if Settings tests do not call it, call `initTheme()` once in the appearance tests after stubbing `matchMedia`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm -C gui test:run src/lib/theme.test.ts src/views/settings.test.ts`

Expected: FAIL — `getThemePreference` is not exported; `#settings-appearance` missing.

- [ ] **Step 3: Write minimal implementation**

`gui/src/lib/theme.ts` — add:

```typescript
export function getThemePreference(): ThemePreference {
  const raw = localStorage.getItem('theme');
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system';
}
```

Do not change `toggleTheme`.

In `settings.ts` header (the `justify-between` row with `h2`), after the title, render:

```html
<div id="settings-appearance" class="settings-appearance" role="radiogroup" aria-label="Appearance">
  <button type="button" class="settings-appearance-btn" role="radio" data-theme="system">System</button>
  <button type="button" class="settings-appearance-btn" role="radio" data-theme="light">Light</button>
  <button type="button" class="settings-appearance-btn" role="radio" data-theme="dark">Dark</button>
</div>
```

Bind after the shell is in the DOM (both success and error paths share this header):

```typescript
import { applyTheme, getThemePreference, type ThemePreference } from '../lib/theme';

function order(): ThemePreference[] {
  return ['system', 'light', 'dark'];
}

function syncAppearanceButtons(root: HTMLElement): void {
  const current = getThemePreference();
  root.querySelectorAll<HTMLElement>('#settings-appearance [data-theme]').forEach((btn) => {
    const value = btn.dataset.theme as ThemePreference;
    const selected = value === current;
    btn.setAttribute('aria-checked', String(selected));
    btn.tabIndex = selected ? 0 : -1;
  });
}

function bindAppearance(root: HTMLElement): void {
  const group = root.querySelector<HTMLElement>('#settings-appearance');
  if (!group) return;
  syncAppearanceButtons(root);
  group.addEventListener('click', (event) => {
    const btn = (event.target as HTMLElement).closest<HTMLElement>('[data-theme]');
    const value = btn?.dataset.theme;
    if (value === 'system' || value === 'light' || value === 'dark') {
      applyTheme(value);
      syncAppearanceButtons(root);
      btn?.focus();
    }
  });
  group.addEventListener('keydown', (event) => {
    const key = (event as KeyboardEvent).key;
    if (key !== 'ArrowRight' && key !== 'ArrowLeft') return;
    event.preventDefault();
    const themes = order();
    const idx = themes.indexOf(getThemePreference());
    const next = themes[(idx + (key === 'ArrowRight' ? 1 : themes.length - 1)) % themes.length];
    applyTheme(next);
    syncAppearanceButtons(root);
    group.querySelector<HTMLElement>(`[data-theme="${next}"]`)?.focus();
  });
}
```

Call `bindAppearance(root)` once after the Settings shell HTML is assigned, before inspect. One tab stop (`tabindex="0"` on the checked radio only). Labels are sentence case: `System`, `Light`, `Dark`. No widget library.

`settings.css`:

```css
.settings-appearance {
  display: inline-flex;
  gap: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}
.settings-appearance-btn {
  font-size: var(--font-size-xs);
  padding: 0.25rem 0.625rem;
  border: none;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  cursor: pointer;
}
.settings-appearance-btn + .settings-appearance-btn {
  border-left: 1px solid var(--border-color);
}
.settings-appearance-btn[aria-checked="true"] {
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.settings-appearance-btn:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: -2px;
  z-index: 1;
}
```

Do not use a native `<select>`. Do not restyle as disabled config fields.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/lib/theme.test.ts src/views/settings.test.ts && pnpm -C gui typecheck && pnpm -C gui build:css`

Expected: PASS.

---

### Task 3: About dark contrast and link tests

**Worker:** Fable

**Files:**
- Create: `gui/src/views/about.test.ts`
- Modify: `gui/src/css/components/about.css` only if a named selector fails contrast vs `--bg-primary` / `--bg-tertiary`
- Modify: `gui/src/views/about.ts` only if a selector/id is required for the tests below
- Then: `pnpm -C gui build:css` if CSS changed

**Interfaces:**
- Consumes: existing `data-href` buttons and `openUrl`
- Produces: tests that GitHub, MIT License, and PhraseVault buttons keep `data-href` and Back returns to files. Do **not** move About under Settings (visual spec P2).

- [ ] **Step 1: Write the failing test**

Create `gui/src/views/about.test.ts`. Do not change production selectors to fit the test. GREEN on the first run is acceptable if wiring already exists.

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { openUrl } = vi.hoisted(() => ({ openUrl: vi.fn() }));
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl }));

import { renderAboutView } from './about';
import { getState, setState } from '../lib/state';

const URLS = [
  'https://github.com/ptmrio/autorename-pdf',
  'https://github.com/ptmrio/autorename-pdf/blob/main/LICENSE',
  'https://phrasevault.app',
];

describe('about view', () => {
  beforeEach(() => {
    openUrl.mockReset();
    document.body.innerHTML = '<div id="root"></div>';
    setState({ view: 'about' });
  });

  it('opens GitHub, license, and PhraseVault via data-href', () => {
    renderAboutView(document.getElementById('root')!);
    const buttons = [...document.querySelectorAll<HTMLElement>('[data-href]')];
    const hrefs = buttons.map((el) => el.dataset.href);
    expect(hrefs).toEqual(expect.arrayContaining(URLS));
    for (const url of URLS) {
      buttons.find((el) => el.dataset.href === url)!.click();
      expect(openUrl).toHaveBeenCalledWith(url);
    }
    expect(openUrl).toHaveBeenCalledTimes(3);
  });

  it('Back returns to files', () => {
    renderAboutView(document.getElementById('root')!);
    document.getElementById('btn-back-from-about')!.click();
    expect(getState().view).toBe('files');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/views/about.test.ts`

Expected: FAIL until the file exists / wiring matches. If it already PASSES because `about.ts` already has the links, that is GREEN for behavior — still keep the test.

- [ ] **Step 3: Contrast evidence gate**

Do not treat token names as contrast. Using the hex fallbacks already written on `.about-tagline`, `.about-section p`, `.about-support-card p`, and `.dark .about-link` versus `--bg-primary` / `--bg-tertiary` fallbacks in `theme-variables.css`, compute relative-luminance contrast (WCAG 2.x). Record each ratio in the GATES section of the worker report. Change a selector only if a ratio is `< 4.5:1`. Keep `.dark .about-link { color: var(--color-primary-400); }`. No new palette.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/views/about.test.ts && pnpm -C gui typecheck`

Expected: PASS. If CSS changed: `pnpm -C gui build:css`.

---

### Task 4: Titlebar left drag region

**Worker:** Fable

**Files:**
- Modify: `gui/index.html`
- Test: `gui/src/lib/titlebar.test.ts` (read `index.html` text, same pattern as other CSS/HTML presence tests)

**Interfaces:**
- Consumes: existing outer `.titlebar` `data-tauri-drag-region`
- Produces: `.titlebar-left` also has `data-tauri-drag-region`. `.titlebar-controls` must not.

- [ ] **Step 1: Write the failing test**

Add to `gui/src/lib/titlebar.test.ts`. Keep the `../../index.html` path (from `gui/src/lib` that is `gui/index.html`). Do not add another `../`.

```typescript
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const html = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '../../index.html'),
  'utf8',
);

it('marks titlebar-left as a drag region and keeps controls out of it', () => {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const bar = doc.querySelector('.titlebar');
  const left = doc.querySelector('.titlebar-left');
  const controls = doc.querySelector('.titlebar-controls');
  expect(bar?.hasAttribute('data-tauri-drag-region')).toBe(true);
  expect(left?.hasAttribute('data-tauri-drag-region')).toBe(true);
  expect(controls?.hasAttribute('data-tauri-drag-region')).toBe(false);
  expect(controls?.querySelector('[data-tauri-drag-region]')).toBeNull();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm -C gui test:run src/lib/titlebar.test.ts`

Expected: FAIL — `.titlebar-left` has no drag attribute.

- [ ] **Step 3: Write minimal implementation**

In `gui/index.html`, change:

```html
    <div data-tauri-drag-region class="titlebar-left">
```

Keep `data-tauri-drag-region` on the outer `.titlebar`. Do not put it on `.titlebar-controls` or the three buttons.

- [ ] **Step 4: Run tests**

Run: `pnpm -C gui test:run src/lib/titlebar.test.ts && pnpm -C gui typecheck`

Expected: PASS.

---

### Task 5: Sidecar build and native walk

**Worker:** Parent (not Fable). Fable must stop after Task 4 and report UNVERIFIED for this task.

**Files:** none in the GUI src tree unless spawn permission is missing.

**Interfaces:**
- Consumes: `python build.py --cli-only --nosign` stages `autorename-pdf-cli-x86_64-pc-windows-msvc.exe` for Tauri
- Produces: evidence notes in the worker report, not new product code

- [ ] **Step 1: Confirm spawn capability**

Read `gui/src-tauri/capabilities/default.json`. It must contain `shell:allow-spawn` for `autorename-pdf-cli` in addition to `shell:allow-execute`. If missing, add the matching allow-spawn entry only — do not broaden shell scope.

- [ ] **Step 2: Build the sidecar**

Run:

```
venv\Scripts\python.exe build.py --cli-only --nosign
```

Expected: CLI exe built and staged for `pnpm -C gui tauri dev`.

- [ ] **Step 3: Tauri smoke (manual, record pass/fail)**

Run: `pnpm -C gui tauri dev`

Use disposable copies of PDFs for Preview/Rename/Undo. Record this walk separately from Fable’s Tasks 1–4 GREEN. If Tauri cannot start, mark Task 5 UNVERIFIED — that is not a phase-1 pass.

Walk:
1. Empty Files both themes (status-bar theme button). Example line `20260907 ACME AP.pdf` visible.
2. Missing-CLI (or forced sidecar failure) readiness banner on **empty** Files and again with files queued; Retry / recovery copy visible.
3. Settings: read-only banner, appearance System/Light/Dark, Open Config Location, Validate.
4. About: GitHub / license / PhraseVault open; dark About readable (supplements Task 3 ratios).
5. Queue long-named PDFs: Preview names secondary, Rename primary; native tooltip shows full original/proposed name; selection/copy of the visible line works; names stay single-line ellipsis. Progress text has `role="status"` and does not pulse.
6. One Preview + one Rename on disposable copies; stderr progress updates the UI; Undo works after `renamed > 0`. Then Clear the queue — Undo remains available and restores that batch.
7. Drag the window from the title text, not from caption buttons. Maximize `aria-label` flips to Restore.

Do not implement Snap flyouts.

---

### Task 6: Full gates

**Worker:** Parent

- [ ] **Step 1: Python**

```
venv\Scripts\python.exe -m pytest tests/ -q --cov
venv\Scripts\python.exe -m ruff check .
```

Expected: pytest pass. Record the coverage report’s business-logic module percentages (harmonization/dates/filenames) rather than treating the aggregate `--cov` figure as proof. If those modules are below 80%, that is a gate fail. Ruff clean. If `ruff` is missing: `venv\Scripts\python.exe -m pip install -r requirements-dev.txt` then rerun. No `--run-live`.

- [ ] **Step 2: GUI**

```
pnpm -C gui test:run
pnpm -C gui typecheck
```

Expected: all Vitest tests pass, typecheck clean.

- [ ] **Step 3: Stop**

Do not push. Do not open a PR. Commit only if the human asks. Screenshots at repo root stay untracked.

---

## Out of scope (do not add tasks)

- Phase 2: ruamel, `config apply --stdin`, writable Settings, secret patch semantics, persistent `serve --stdio`, CPython in Rust, PyInstaller onedir
- Move About under Settings (visual spec P2)
- 44px touch targets, Snap `WM_NCHITTEST`, min window below 700px
- Re-running Astra visual research from 2026-09-07 as a product redesign
