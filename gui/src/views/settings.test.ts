import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getConfig, getConfigPath, validateConfig, showToast, revealItemInDir } = vi.hoisted(() => ({
  getConfig: vi.fn(),
  getConfigPath: vi.fn(),
  validateConfig: vi.fn(),
  showToast: vi.fn(),
  revealItemInDir: vi.fn(),
}));

vi.mock('../lib/sidecar', () => ({
  getConfig,
  getConfigPath,
  validateConfig,
}));

vi.mock('../lib/toast', () => ({
  showToast,
}));

vi.mock('@tauri-apps/plugin-opener', () => ({
  revealItemInDir,
}));

import { getState, setState } from '../lib/state';
import { renderSettingsView } from './settings';

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

describe('settings footer recovery', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    resetAppState();
    getConfig.mockReset();
    getConfigPath.mockReset();
    validateConfig.mockReset();
    showToast.mockReset();
    revealItemInDir.mockReset();
    getConfigPath.mockResolvedValue('D:\\runtime\\config.yaml');
  });

  it('keeps Open Config Location when config.yaml is missing', async () => {
    getConfig.mockRejectedValue(new Error('Config file not found'));

    await renderSettingsView(document.getElementById('root')!);

    const footer = document.getElementById('settings-footer');
    expect(footer).not.toBeNull();
    expect(footer!.style.display).not.toBe('none');
    expect(document.getElementById('btn-open-config')).not.toBeNull();
    const validateBtn = document.getElementById('btn-validate-config') as HTMLButtonElement;
    expect(validateBtn.disabled).toBe(true);
  });

  it('hides footer only for sidecar errors that are not config errors', async () => {
    getConfig.mockRejectedValue(new Error('sidecar binaries missing'));

    await renderSettingsView(document.getElementById('root')!);

    const footer = document.getElementById('settings-footer');
    expect(footer!.style.display).toBe('none');
  });
});

describe('validate config blocks rename', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    resetAppState();
    getConfig.mockReset();
    getConfigPath.mockReset();
    validateConfig.mockReset();
    showToast.mockReset();
    getConfigPath.mockResolvedValue('D:\\runtime\\config.yaml');
    getConfig.mockResolvedValue({
      ai: { provider: 'openai', model: 'gpt-5.6-luna' },
    });
  });

  it('sets statusError from the first validation error field and message', async () => {
    validateConfig.mockResolvedValue({
      valid: false,
      issues: [
        { field: 'ai.api_key', level: 'error', message: 'API key is required' },
        { field: 'company.name', level: 'warning', message: 'empty' },
      ],
    });

    await renderSettingsView(document.getElementById('root')!);
    document.getElementById('btn-validate-config')!.click();
    await vi.waitFor(() => {
      expect(getState().statusError).toContain('ai.api_key');
    });
    expect(getState().statusError).toContain('API key is required');
    expect(getState().statusError.length).toBeGreaterThan(0);
  });

  it('clears a validation statusError when validate succeeds', async () => {
    validateConfig.mockResolvedValue({ valid: true, issues: [] });

    await renderSettingsView(document.getElementById('root')!);
    setState({ statusError: 'ai.api_key: API key is required' });
    document.getElementById('btn-validate-config')!.click();
    await vi.waitFor(() => {
      expect(getState().statusError).toBe('');
    });
  });
});
