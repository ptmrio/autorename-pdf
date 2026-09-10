import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { inspectConfig, getConfigPath, showToast, revealItemInDir } = vi.hoisted(() => ({
  inspectConfig: vi.fn(),
  getConfigPath: vi.fn(),
  showToast: vi.fn(),
  revealItemInDir: vi.fn(),
}));

vi.mock('../lib/sidecar', () => ({
  inspectConfig,
  getConfigPath,
}));

vi.mock('../lib/toast', () => ({
  showToast,
}));

vi.mock('@tauri-apps/plugin-opener', () => ({
  revealItemInDir,
}));

import { getState, setState } from '../lib/state';
import { renderSettingsView, refreshSettingsIfOpen, SECTIONS } from './settings';
import { initTheme } from '../lib/theme';

function resetAppState() {
  setState({
    view: 'settings',
    files: [],
    processing: false,
    progress: '',
    lastResult: null,
    dryRunResult: null,
    statusError: '',
    lastBatchId: null,
  });
}

function okSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    config_path: 'D:\\runtime\\config.yaml',
    valid: true,
    issues: [] as Array<{ field: string; level: string; message: string }>,
    profile: 'business',
    resolved_profile: {},
    config: {
      ai: { provider: 'openai', model: 'gpt-5.6-luna' },
      pdf: {},
      company: { name: 'A' },
      output: {},
    },
    ...overrides,
  };
}

describe('settings footer recovery', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    resetAppState();
    inspectConfig.mockReset();
    getConfigPath.mockReset();
    showToast.mockReset();
    revealItemInDir.mockReset();
    getConfigPath.mockResolvedValue('D:\\runtime\\config.yaml');
  });

  it('keeps Open Config Location when config.yaml is missing', async () => {
    inspectConfig.mockResolvedValue(okSnapshot({
      valid: false,
      config: null,
      issues: [{ field: 'config_file', level: 'error', message: 'Config file not found' }],
    }));

    await renderSettingsView(document.getElementById('root')!);

    const footer = document.getElementById('settings-footer');
    expect(footer).not.toBeNull();
    expect(footer!.style.display).not.toBe('none');
    expect(document.getElementById('btn-open-config')).not.toBeNull();
    const validateBtn = document.getElementById('btn-validate-config') as HTMLButtonElement;
    expect(validateBtn.disabled).toBe(false);
  });

  it('hides footer only for sidecar errors that are not config errors', async () => {
    inspectConfig.mockRejectedValue(new Error('sidecar binaries missing'));

    await renderSettingsView(document.getElementById('root')!);

    const footer = document.getElementById('settings-footer');
    expect(footer!.style.display).not.toBe('none');
    expect(document.getElementById('btn-open-config')).not.toBeNull();
    expect(document.getElementById('btn-validate-config')).toBeNull();
  });

  it('treats missing Tauri invoke as a sidecar error', async () => {
    inspectConfig.mockRejectedValue(new TypeError("Cannot read properties of undefined (reading 'invoke')"));

    await renderSettingsView(document.getElementById('root')!);

    expect(document.body.textContent).toMatch(/CLI executable not found/);
    expect(document.getElementById('btn-open-config')).not.toBeNull();
    expect(document.getElementById('btn-validate-config')).toBeNull();
    expect(getState().statusError).toBe('CLI executable not found');
  });

  it('reloads Settings after a focus invalidation when the view is still open', async () => {
    inspectConfig
      .mockRejectedValueOnce(new Error('sidecar binaries missing'))
      .mockResolvedValueOnce(okSnapshot());
    await renderSettingsView(document.getElementById('root')!);
    expect(document.getElementById('settings-readonly-banner')).toBeNull();
    await refreshSettingsIfOpen();
    await vi.waitFor(() => {
      expect(document.getElementById('settings-readonly-banner')).not.toBeNull();
    });
    expect(inspectConfig).toHaveBeenCalledTimes(2);
  });
});

describe('validate config blocks rename', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    resetAppState();
    inspectConfig.mockReset();
    getConfigPath.mockReset();
    showToast.mockReset();
    getConfigPath.mockResolvedValue('D:\\runtime\\config.yaml');
    inspectConfig.mockResolvedValue(okSnapshot());
  });

  it('sets statusError from the first validation error field and message', async () => {
    await renderSettingsView(document.getElementById('root')!);
    inspectConfig.mockResolvedValue(okSnapshot({
      valid: false,
      issues: [
        { field: 'ai.api_key', level: 'error', message: 'API key is required' },
        { field: 'company.name', level: 'warning', message: 'empty' },
      ],
    }));
    document.getElementById('btn-validate-config')!.click();
    await vi.waitFor(() => {
      expect(getState().statusError).toContain('ai.api_key');
    });
    expect(inspectConfig).toHaveBeenLastCalledWith({ force: true });
    expect(getState().statusError).toContain('API key is required');
  });

  it('clears a validation statusError when validate succeeds', async () => {
    await renderSettingsView(document.getElementById('root')!);
    setState({ statusError: 'ai.api_key: API key is required' });
    inspectConfig.mockResolvedValue(okSnapshot());
    document.getElementById('btn-validate-config')!.click();
    await vi.waitFor(() => {
      expect(getState().statusError).toBe('');
    });
  });

  it('sets persistent readiness when Validate throws', async () => {
    await renderSettingsView(document.getElementById('root')!);
    inspectConfig.mockRejectedValue(new Error('sidecar binaries missing'));
    document.getElementById('btn-validate-config')!.click();
    await vi.waitFor(() => {
      expect(getState().statusError).toBe('CLI executable not found');
    });
    expect(getState().statusErrorAlert).toBe(true);
  });

  it('shows a read-only banner above fields when config loads', async () => {
    await renderSettingsView(document.getElementById('root')!);
    const banner = document.getElementById('settings-readonly-banner');
    expect(banner).not.toBeNull();
    expect(banner!.textContent).toMatch(/Configuration — read only/);
    expect(banner!.textContent).toMatch(/config\.yaml/);
    expect(document.querySelector('input')).toBeNull();
    expect(document.querySelector('details.settings-advanced')).not.toBeNull();
    expect(document.querySelector('details.settings-advanced')?.hasAttribute('open')).toBe(false);
  });

  it('documents PP-OCRv6 small det and rec defaults', () => {
    const det = SECTIONS.flatMap((s) => s.fields).find((f) => f.key === 'detection_model');
    const lang = SECTIONS.flatMap((s) => s.fields).find((f) => f.key === 'language');
    expect(det?.hint).toMatch(/PP-OCRv6_small_det/);
    expect(lang?.hint).toMatch(/PP-OCRv6_small_rec/);
  });
});

describe('settings appearance', () => {
  let darkMql: {
    matches: boolean;
    addEventListener: ReturnType<typeof vi.fn>;
    removeEventListener: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    resetAppState();
    inspectConfig.mockReset();
    getConfigPath.mockReset();
    showToast.mockReset();
    revealItemInDir.mockReset();
    getConfigPath.mockResolvedValue('D:\\runtime\\config.yaml');
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
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('restores System from an explicit Light preference', async () => {
    localStorage.setItem('theme', 'light');
    initTheme();
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
    const change = darkMql.addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1] as (e: { matches: boolean }) => void;
    change?.({ matches: false });
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('system');
  });

  it('keeps an explicit Light preference when the OS switches to dark', async () => {
    localStorage.setItem('theme', 'system');
    initTheme();
    inspectConfig.mockResolvedValue(okSnapshot());
    await renderSettingsView(document.getElementById('root')!);
    const group = document.getElementById('settings-appearance')!;
    (group.querySelector('[data-theme="light"]') as HTMLButtonElement).click();
    expect(localStorage.getItem('theme')).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    const change = darkMql.addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1] as (e: { matches: boolean }) => void;
    change?.({ matches: true });
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('light');
  });

  it('moves appearance selection with arrow keys', async () => {
    localStorage.setItem('theme', 'light');
    initTheme();
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
    initTheme();
    inspectConfig.mockRejectedValue(new Error('sidecar binaries missing'));
    await renderSettingsView(document.getElementById('root')!);
    expect(document.getElementById('btn-open-config')).not.toBeNull();
    const lightBtn = document.querySelector('#settings-appearance [data-theme="light"]') as HTMLButtonElement;
    lightBtn.click();
    expect(localStorage.getItem('theme')).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
