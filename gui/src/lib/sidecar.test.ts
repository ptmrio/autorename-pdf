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

function inspectStdout(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    config_path: 'D:\\runtime\\config.yaml',
    valid: true,
    issues: [],
    profile: 'business',
    resolved_profile: {},
    config: { ai: { provider: 'openai' } },
    ...overrides,
  });
}

describe('sidecar config path resolution', () => {
  beforeEach(async () => {
    sidecarSpy.mockReset();
    sidecarSpy.mockReturnValue({
      stderr: { on: vi.fn() },
      stdout: { on: vi.fn() },
      on: vi.fn(),
      spawn: vi.fn(),
      execute: vi.fn(async () => ({
        code: 0,
        stdout: inspectStdout(),
        stderr: '',
      })),
    });
    const { invalidateConfigSnapshot } = await import('./sidecar');
    invalidateConfigSnapshot();
  });

  it('passes the resolved config path to inspect calls', async () => {
    const { validateConfig } = await import('./sidecar');

    await validateConfig();

    expect(sidecarSpy).toHaveBeenCalledWith('autorename-pdf-cli', [
      'config',
      'inspect',
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

  it('returns the resource directory for undo log', async () => {
    const { getUndoLogDir } = await import('./sidecar');

    await expect(getUndoLogDir()).resolves.toBe('D:\\runtime');
  });

  it('inspectConfig, getConfig, and validateConfig share one sidecar process', async () => {
    const sidecar = await import('./sidecar');
    sidecar.invalidateConfigSnapshot();
    const [inspect, cfg, val] = await Promise.all([
      sidecar.inspectConfig(),
      sidecar.getConfig(),
      sidecar.validateConfig(),
    ]);
    expect(sidecarSpy).toHaveBeenCalledTimes(1);
    expect(inspect.valid).toBe(true);
    expect(cfg.ai).toEqual({ provider: 'openai' });
    expect(val.valid).toBe(true);
  });

  it('does not reuse a rejected inspect promise', async () => {
    const execute = vi.fn()
      .mockRejectedValueOnce(new Error('sidecar binaries missing'))
      .mockResolvedValueOnce({
        code: 0,
        stdout: inspectStdout(),
        stderr: '',
      });
    sidecarSpy.mockReturnValue({
      stderr: { on: vi.fn() },
      stdout: { on: vi.fn() },
      on: vi.fn(),
      spawn: vi.fn(),
      execute,
    });
    const sidecar = await import('./sidecar');
    sidecar.invalidateConfigSnapshot();
    await expect(sidecar.inspectConfig()).rejects.toThrow(/sidecar/);
    await expect(sidecar.inspectConfig()).resolves.toMatchObject({ valid: true });
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it('force: true bypasses a completed snapshot', async () => {
    const execute = vi.fn(async () => ({
      code: 0,
      stdout: inspectStdout(),
      stderr: '',
    }));
    sidecarSpy.mockReturnValue({
      stderr: { on: vi.fn() },
      stdout: { on: vi.fn() },
      on: vi.fn(),
      spawn: vi.fn(),
      execute,
    });
    const sidecar = await import('./sidecar');
    sidecar.invalidateConfigSnapshot();
    await sidecar.inspectConfig();
    await sidecar.inspectConfig({ force: true });
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it('stale inspect after force does not repopulate the cache', async () => {
    let resolveFirst: (value: { code: number; stdout: string; stderr: string }) => void = () => {};
    const first = new Promise<{ code: number; stdout: string; stderr: string }>((resolve) => {
      resolveFirst = resolve;
    });
    const execute = vi.fn()
      .mockImplementationOnce(() => first)
      .mockResolvedValueOnce({
        code: 0,
        stdout: inspectStdout({ config: { ai: { provider: 'anthropic' } } }),
        stderr: '',
      });
    sidecarSpy.mockReturnValue({
      stderr: { on: vi.fn() },
      stdout: { on: vi.fn() },
      on: vi.fn(),
      spawn: vi.fn(),
      execute,
    });
    const sidecar = await import('./sidecar');
    sidecar.invalidateConfigSnapshot();
    const stale = sidecar.inspectConfig();
    const fresh = sidecar.inspectConfig({ force: true });
    const freshResult = await fresh;
    resolveFirst({
      code: 0,
      stdout: inspectStdout({ config: { ai: { provider: 'stale' } } }),
      stderr: '',
    });
    const staleResult = await stale;
    const cached = await sidecar.inspectConfig();
    expect(freshResult.config).toEqual({ ai: { provider: 'anthropic' } });
    expect(staleResult.config).toEqual({ ai: { provider: 'anthropic' } });
    expect(cached.config).toEqual({ ai: { provider: 'anthropic' } });
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it('renamePdfs listens to stderr via spawn, not execute', async () => {
    const stderrOn = vi.fn();
    const stdoutOn = vi.fn();
    const commandOn = vi.fn();
    const spawn = vi.fn(async () => ({ pid: 1 }));
    const execute = vi.fn();
    sidecarSpy.mockReturnValue({
      stderr: { on: stderrOn },
      stdout: { on: stdoutOn },
      on: commandOn,
      spawn,
      execute,
    });
    const { renamePdfs } = await import('./sidecar');
    const progress = vi.fn();
    const pending = renamePdfs(['D:\\a.pdf'], {}, progress);
    await vi.waitFor(() => expect(spawn).toHaveBeenCalled());
    expect(execute).not.toHaveBeenCalled();
    const closeHandler = commandOn.mock.calls.find((c) => c[0] === 'close')?.[1] as (e: { code: number; signal: null }) => void;
    const stdoutHandler = stdoutOn.mock.calls.find((c) => c[0] === 'data')?.[1] as (chunk: string) => void;
    const stderrHandler = stderrOn.mock.calls.find((c) => c[0] === 'data')?.[1] as (chunk: string) => void;
    expect(stderrHandler).toEqual(expect.any(Function));
    stderrHandler('Processing [1/1] a.pdf');
    expect(progress).toHaveBeenCalledWith('Processing [1/1] a.pdf');
    stdoutHandler(JSON.stringify({
      success: true, total: 0, renamed: 0, skipped: 0, failed: 0, files: [], dry_run: false,
    }));
    closeHandler({ code: 0, signal: null });
    await expect(pending).resolves.toMatchObject({ success: true });
  });

  it('renamePdfs surfaces stderr when spawn exits without stdout', async () => {
    const stderrOn = vi.fn();
    const stdoutOn = vi.fn();
    const commandOn = vi.fn();
    const spawn = vi.fn(async () => ({ pid: 1 }));
    sidecarSpy.mockReturnValue({
      stderr: { on: stderrOn },
      stdout: { on: stdoutOn },
      on: commandOn,
      spawn,
      execute: vi.fn(),
    });
    const { renamePdfs } = await import('./sidecar');
    const pending = renamePdfs(['D:\\a.pdf']);
    await vi.waitFor(() => expect(spawn).toHaveBeenCalled());
    const closeHandler = commandOn.mock.calls.find((c) => c[0] === 'close')?.[1] as (e: { code: number; signal: null }) => void;
    const stderrHandler = stderrOn.mock.calls.find((c) => c[0] === 'data')?.[1] as (chunk: string) => void;
    stderrHandler('config.yaml missing');
    closeHandler({ code: 3, signal: null });
    await expect(pending).resolves.toMatchObject({
      success: false,
      error_type: 'config_error',
    });
  });
});
