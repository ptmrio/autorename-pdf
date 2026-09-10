import { getState, setState } from '../lib/state';
import { getConfigPath, inspectConfig } from '../lib/sidecar';
import { showToast } from '../lib/toast';
import { revealItemInDir } from '@tauri-apps/plugin-opener';
import { applyTheme, getThemePreference, type ThemePreference } from '../lib/theme';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let configPath: string | null = null;
let settingsRoot: HTMLElement | null = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function muted(text: string): string {
  return `<span style="color:var(--text-muted);font-style:italic;font-size:0.8125rem">${escapeHtml(text)}</span>`;
}

// ---------------------------------------------------------------------------
// Field types & section metadata
// ---------------------------------------------------------------------------

type FieldType = 'string' | 'number' | 'boolean' | 'auto-or-bool' | 'secret' | 'enum' | 'array' | 'path';

interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  hint?: string;
  enumValues?: string[];
}

interface SectionDef {
  configKey: string;
  title: string;
  fields: FieldDef[];
}

export const SECTIONS: SectionDef[] = [
  {
    configKey: 'ai',
    title: 'AI connection',
    fields: [
      { key: 'provider', label: 'Provider', type: 'enum', enumValues: ['openai', 'anthropic', 'gemini', 'xai', 'ollama'] },
      { key: 'model', label: 'Model', type: 'string' },
      { key: 'api_key', label: 'API Key', type: 'secret' },
      { key: 'base_url', label: 'Base URL', type: 'string', hint: 'Only needed for proxies or custom endpoints' },
      { key: 'temperature', label: 'Temperature', type: 'number' },
      { key: 'max_retries', label: 'Max Retries', type: 'number' },
    ],
  },
  {
    configKey: 'pdf',
    title: 'PDF',
    fields: [
      { key: 'max_pages', label: 'Max Pages', type: 'number', hint: 'First N pages to process' },
      { key: 'ocr', label: 'OCR', type: 'auto-or-bool', hint: 'PaddleOCR fallback' },
      { key: 'vision', label: 'Vision', type: 'auto-or-bool', hint: 'Send page images to LLM' },
      { key: 'text_quality_threshold', label: 'Text Quality Threshold', type: 'number', hint: '0.0–1.0, triggers auto OCR/vision below this' },
      { key: 'outgoing_invoice', label: 'Outgoing Invoice Code', type: 'string' },
      { key: 'incoming_invoice', label: 'Incoming Invoice Code', type: 'string' },
    ],
  },
  {
    configKey: 'paddleocr',
    title: 'PaddleOCR',
    fields: [
      { key: 'venv_path', label: 'Venv Path', type: 'path', hint: 'Auto-detected if empty' },
      { key: 'language', label: 'Language', type: 'string',
        hint: 'e.g. "en" (English), "de"/"fr" (Latin-script), "ch" (Chinese). Recognition default: PP-OCRv6_small_rec' },
      { key: 'device', label: 'Device', type: 'enum', enumValues: ['auto', 'cpu', 'gpu'], hint: 'auto = GPU if available, else CPU' },
      { key: 'detection_model', label: 'Detection Model', type: 'string',
        hint: 'Leave empty for default PP-OCRv6_small_det. Use PP-OCRv5_server_det for higher accuracy (more RAM)' },
      { key: 'det_limit_side_len', label: 'Detection Limit (px)', type: 'number',
        hint: 'Max image side for detection. Lower = less RAM (default: 736)' },
      { key: 'cpu_threads', label: 'CPU Threads', type: 'number',
        hint: 'Threads for OCR inference (default: 4)' },
    ],
  },
  {
    configKey: 'company',
    title: 'Company',
    fields: [
      { key: 'name', label: 'Company Name', type: 'string', hint: 'Used to distinguish incoming vs outgoing docs' },
    ],
  },
  {
    configKey: 'output',
    title: 'Output',
    fields: [
      { key: 'language', label: 'Language', type: 'string', hint: 'Language for AI-generated doc type labels' },
      { key: 'date_format', label: 'Date Format', type: 'string', hint: 'strftime format for filename date' },
    ],
  },
];

// ---------------------------------------------------------------------------
// Type-specific value renderers
// ---------------------------------------------------------------------------

function renderAutoOrBool(value: unknown): string {
  const label = value === 'auto' ? 'auto' : Boolean(value) ? 'on' : 'off';
  return `<span style="font-family:var(--font-mono,monospace);font-size:0.8125rem;color:var(--text-muted);font-style:italic">${label}</span>`;
}

function renderValue(value: unknown, def: FieldDef): string {
  switch (def.type) {
    case 'boolean':
      return renderToggle(value as boolean);
    case 'auto-or-bool':
      return renderAutoOrBool(value);
    case 'secret':
      return renderSecret(value);
    case 'enum':
      return `<span style="font-family:var(--font-mono,monospace);font-size:0.8125rem;color:var(--text-primary)">${escapeHtml(String(value ?? ''))}</span>`;
    case 'number':
      return `<span style="font-family:var(--font-mono,monospace);font-size:0.8125rem;color:var(--text-primary)">${escapeHtml(String(value ?? ''))}</span>`;
    case 'array':
      return renderArray(value);
    case 'path':
      return renderPath(value);
    case 'string':
    default:
      return renderString(value);
  }
}

function renderToggle(checked: boolean): string {
  return `<span style="font-family:var(--font-mono,monospace);font-size:0.8125rem;color:var(--text-muted);font-style:italic">${checked ? 'on' : 'off'}</span>`;
}

function renderSecret(value: unknown): string {
  const str = String(value ?? '');
  if (!str) return muted('not set');
  const last4 = str.length > 4 ? str.slice(-4) : '';
  return `<span style="font-family:var(--font-mono,monospace);font-size:0.8125rem;color:var(--text-primary);letter-spacing:0.05em">${'••••••••'}${escapeHtml(last4)}</span>`;
}

function renderArray(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return muted('none');
  return `<span style="font-family:var(--font-mono,monospace);font-size:0.8125rem;color:var(--text-primary)">${value.map((v) => escapeHtml(String(v))).join(', ')}</span>`;
}

function renderPath(value: unknown): string {
  const str = String(value ?? '');
  if (!str) return muted('auto-detected');
  return `<span style="font-family:var(--font-mono,monospace);font-size:0.8125rem;color:var(--text-primary);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:middle" title="${escapeHtml(str)}">${escapeHtml(str)}</span>`;
}

function renderString(value: unknown): string {
  const str = String(value ?? '');
  if (!str) return muted('not set');
  return `<span style="font-size:0.8125rem;color:var(--text-primary)">${escapeHtml(str)}</span>`;
}

// ---------------------------------------------------------------------------
// Field & section renderers
// ---------------------------------------------------------------------------

function renderField(value: unknown, def: FieldDef): string {
  const hintHtml = def.hint
    ? `<div class="settings-hint" style="margin-top:0.125rem">${escapeHtml(def.hint)}</div>`
    : '';

  // Booleans: label left, toggle right (single row)
  if (def.type === 'boolean') {
    return `
      <div class="settings-toggle" style="padding:0.375rem 0">
        <span class="settings-toggle-label">${escapeHtml(def.label)}</span>
        ${renderToggle(Boolean(value))}
      </div>
      ${hintHtml}`;
  }

  // auto-or-bool: label left, tri-state right (single row)
  if (def.type === 'auto-or-bool') {
    return `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:0.375rem 0;gap:0.75rem">
        <span class="settings-label" style="margin-bottom:0;flex-shrink:0">${escapeHtml(def.label)}</span>
        ${renderAutoOrBool(value)}
      </div>
      ${hintHtml}`;
  }

  // All other fields: stacked layout (label on top, value below)
  return `
    <div class="settings-field" style="margin-bottom:0;padding:0.375rem 0">
      <span class="settings-label" style="margin-bottom:0.25rem">${escapeHtml(def.label)}</span>
      <div style="min-width:0;overflow:hidden;text-overflow:ellipsis">${renderValue(value, def)}</div>
    </div>
    ${hintHtml}`;
}

function renderSection(sectionDef: SectionDef, config: Record<string, unknown>): string {
  const sectionData = config[sectionDef.configKey] as Record<string, unknown> | undefined;
  if (!sectionData) return '';

  const fieldsHtml = sectionDef.fields
    .map((f) => renderField(sectionData[f.key], f))
    .join('');

  return `
    <div class="settings-section">
      <h3>${escapeHtml(sectionDef.title)}</h3>
      <div class="card card-bordered" style="padding:1rem;min-width:0;overflow:hidden">
        ${fieldsHtml}
      </div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Appearance (app chrome, stored in localStorage.theme — not config.yaml)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export async function refreshSettingsIfOpen(): Promise<void> {
  if (!settingsRoot || getState().view !== 'settings') return;
  await renderSettingsView(settingsRoot);
}

export async function renderSettingsView(root: HTMLElement): Promise<void> {
  settingsRoot = root;
  root.innerHTML = `
    <div class="flex flex-col flex-1 min-h-0 p-6 pt-8">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-lg font-semibold">Settings</h2>
        <div class="settings-header-right">
          <div id="settings-appearance" class="settings-appearance" role="radiogroup" aria-label="Appearance">
            <button type="button" class="settings-appearance-btn" role="radio" data-theme="system">System</button>
            <button type="button" class="settings-appearance-btn" role="radio" data-theme="light">Light</button>
            <button type="button" class="settings-appearance-btn" role="radio" data-theme="dark">Dark</button>
          </div>
          <button class="btn btn-secondary btn-sm" id="btn-back-from-settings">
          <svg class="w-3.5 h-3.5 inline-block mr-1 -mt-px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>Back
          </button>
        </div>
      </div>
      <div id="settings-content" class="flex-1 overflow-y-auto" style="overflow-x:hidden;padding-right:0.5rem">
        <p class="text-sm text-[var(--text-tertiary)]">Loading configuration...</p>
      </div>
      <div class="flex items-center justify-center gap-2 mt-4" id="settings-footer">
        <button class="btn btn-secondary btn-sm" id="btn-validate-config">Validate Config</button>
        <button class="btn btn-secondary btn-sm" id="btn-open-config">Open Config Location</button>
      </div>
    </div>
  `;

  bindAppearance(root);

  document.getElementById('btn-back-from-settings')?.addEventListener('click', () => {
    setState({ view: 'files' });
  });

  document.getElementById('btn-validate-config')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-validate-config') as HTMLButtonElement | null;
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Validating...';
    }
    try {
      const snapshot = await inspectConfig({ force: true });
      const errors = snapshot.issues.filter((i) => i.level === 'error');
      const warnings = snapshot.issues.filter((i) => i.level === 'warning');
      if (errors.length === 0 && warnings.length === 0) {
        showToast('Configuration is valid', 'success');
      } else if (errors.length === 0) {
        showToast(`Configuration is valid (${warnings.length} warning${warnings.length !== 1 ? 's' : ''})`, 'success');
      } else {
        const parts: string[] = [];
        parts.push(`${errors.length} error${errors.length !== 1 ? 's' : ''}`);
        if (warnings.length > 0) {
          parts.push(`${warnings.length} warning${warnings.length !== 1 ? 's' : ''}`);
        }
        showToast(`${parts.join(', ')} found`, 'danger');
      }
      if (errors.length > 0) {
        const first = errors[0];
        setState({ statusError: `${first.field}: ${first.message}`, statusErrorAlert: true });
      } else if (getState().statusError !== 'CLI executable not found') {
        setState({ statusError: '', statusErrorAlert: false });
      }
    } catch (err) {
      showToast(`Validation failed: ${err}`, 'danger');
      const errStr = String(err);
      if (errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries') || errStr.includes('invoke')) {
        setState({ statusError: 'CLI executable not found', statusErrorAlert: true });
      } else {
        setState({ statusError: 'Config error', statusErrorAlert: true });
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Validate Config';
      }
    }
  });

  document.getElementById('btn-open-config')?.addEventListener('click', async () => {
    const path = configPath || await getConfigPath();
    if (path) configPath = path;
    if (!path) {
      showToast('Config path not available', 'danger');
      return;
    }
    try {
      await revealItemInDir(path);
    } catch (err) {
      showToast(`Could not open config location: ${err}`, 'danger');
    }
  });

  // Load config
  try {
    configPath = await getConfigPath();
    const snapshot = await inspectConfig();
    if (snapshot.config == null) {
      throw new Error(`Config file not found: ${snapshot.config_path}`);
    }
    const config = snapshot.config;
    if (snapshot.valid) {
      setState({ statusError: '', statusErrorAlert: false });
    } else if (snapshot.issues.some((i) => i.level === 'error')) {
      setState({ statusError: 'Config error', statusErrorAlert: false });
    }
    const contentEl = document.getElementById('settings-content');
    if (contentEl) {
      const byKey = Object.fromEntries(SECTIONS.map((s) => [s.configKey, s]));
      const aiHtml = renderSection(byKey.ai, config);
      const docsHtml = ['pdf', 'company', 'output'].map((k) => renderSection(byKey[k], config)).join('');
      const paddleHtml = renderSection({ ...byKey.paddleocr, title: 'PaddleOCR' }, config);
      const promptExt = String(config['prompt_extension'] ?? '');
      const promptHtml = promptExt
        ? `<div class="card card-bordered" style="padding:1rem;min-width:0;overflow:hidden">
              <div class="settings-field" style="margin-bottom:0;padding:0.375rem 0">
                <span class="settings-label" style="margin-bottom:0.25rem">Prompt Extension</span>
                <div style="font-size:0.8125rem;color:var(--text-primary);min-width:0;overflow:hidden;text-overflow:ellipsis">${escapeHtml(promptExt)}</div>
              </div>
            </div>`
        : '';
      const configVersion = String(config['config_version'] ?? '');

      contentEl.innerHTML = `
        <div id="settings-readonly-banner" class="settings-readonly-banner">
          <p class="settings-readonly-title">Configuration — read only</p>
          <p>Edit config.yaml next to the app to change these values.</p>
        </div>
        <div class="space-y-4">
          ${aiHtml}
          <div class="settings-section">
            <h3>Documents and naming</h3>
            ${docsHtml}
          </div>
          <div class="settings-section">
            <details class="settings-advanced">
              <summary>Advanced</summary>
              ${paddleHtml}
              ${promptHtml}
            </details>
          </div>
        </div>
        <div class="settings-footer">
          <p class="settings-version">
            Edit <strong>config.yaml</strong> directly to change settings.
            ${configVersion ? `&nbsp;&middot;&nbsp;Config version <span style="font-family:var(--font-mono,monospace);font-size:0.75rem;color:var(--text-muted)">v${escapeHtml(configVersion)}</span>` : ''}
          </p>
        </div>
      `;
    }
  } catch (err) {
    const contentEl = document.getElementById('settings-content');
    if (contentEl) {
      const errStr = String(err);
      const isConfigError = errStr.toLowerCase().includes('config') || errStr.toLowerCase().includes('yaml');
      const isSidecarError = errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries') || errStr.includes('invoke');
      console.error('[settings] config load error:', err);
      let message: string;
      let hint: string;

      // Check config errors first — "Config file not found" contains "not found"
      // but is a config issue, not a missing sidecar.
      if (isConfigError) {
        message = 'config.yaml missing or invalid';
        hint = `Create a <code>config.yaml</code> next to the executable.<br>
          Copy <code>config.yaml.example</code> and fill in your AI provider API key.`;
        setState({ statusError: 'Config error', statusErrorAlert: false });
      } else if (isSidecarError) {
        message = 'CLI executable not found';
        hint = `The GUI needs <code>autorename-pdf-cli.exe</code> to work.<br><br>
          <strong>Portable app?</strong> Re-extract the ZIP — <code>autorename-pdf-cli.exe</code> must be next to the GUI.<br>
          <strong>Developing?</strong> Run <code class="selectable">python build.py --cli-only --nosign</code> — it builds the EXE and stages it for Tauri automatically.`;
        setState({ statusError: 'CLI executable not found', statusErrorAlert: false });
      } else {
        message = 'Could not load configuration';
        hint = String(err);
        setState({ statusError: message, statusErrorAlert: false });
      }

      const validateBtn = document.getElementById('btn-validate-config');
      if (validateBtn && isSidecarError && !isConfigError) validateBtn.remove();
      contentEl.innerHTML = `
        <div class="flex flex-col items-center justify-center flex-1 gap-4 py-8 text-center">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <p class="text-sm font-medium settings-recovery-title">${message}</p>
          <p class="text-xs text-[var(--text-secondary)] max-w-sm leading-relaxed">${hint}</p>
        </div>`;
    }
  }
}
