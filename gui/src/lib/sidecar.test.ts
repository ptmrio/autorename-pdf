import { beforeEach, describe, expect, it, vi } from 'vitest';

const sidecarSpy = vi.fn();

vi.mock('@tauri-apps/api/path', () => ({
  resourceDir: vi.fn(async () => 'D:\\runtime'),
  join: vi.fn(async (...parts: string[]) => parts.join('\\')),
}));

vi.mock('@tauri-apps/plugin-shell', () => ({
  Command: {
    sidecar: (...args: unknown[]) => sidecarSpy(...args),
  },
}));

describe('sidecar config path resolution', () => {
  beforeEach(() => {
    sidecarSpy.mockReset();
    sidecarSpy.mockReturnValue({
      stderr: { on: vi.fn() },
      execute: vi.fn(async () => ({
        code: 0,
        stdout: JSON.stringify({ success: true, issues: [] }),
        stderr: '',
      })),
    });
  });

  it('passes the resolved config path to validation calls', async () => {
    const { validateConfig } = await import('./sidecar');

    await validateConfig();

    expect(sidecarSpy).toHaveBeenCalledWith('autorename-pdf-cli', [
      'config',
      'validate',
      '--output',
      'json',
      '--config',
      'D:\\runtime\\config.yaml',
    ], {
      encoding: 'utf-8',
      env: {
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
      },
    });
  });

  it('returns the resolved config path even before the CLI loads', async () => {
    const { getConfigPath } = await import('./sidecar');

    await expect(getConfigPath()).resolves.toBe('D:\\runtime\\config.yaml');
  });
});
