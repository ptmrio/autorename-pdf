import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('theme preference', () => {
  let darkMql: {
    matches: boolean;
    addEventListener: ReturnType<typeof vi.fn>;
    removeEventListener: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
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
    const change = darkMql.addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1] as (e: { matches: boolean }) => void;
    change?.({ matches: true });
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('system preference follows OS changes', async () => {
    localStorage.setItem('theme', 'system');
    vi.resetModules();
    const { initTheme } = await import('./theme');
    initTheme();
    const change = darkMql.addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1] as (e: { matches: boolean }) => void;
    change?.({ matches: false });
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('system');
  });

  it('toggleTheme writes explicit light then dark, never system', async () => {
    localStorage.setItem('theme', 'system');
    vi.resetModules();
    const { initTheme, toggleTheme } = await import('./theme');
    initTheme();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    toggleTheme();
    expect(localStorage.getItem('theme')).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    toggleTheme();
    expect(localStorage.getItem('theme')).toBe('dark');
    const change = darkMql.addEventListener.mock.calls.find((c) => c[0] === 'change')?.[1] as (e: { matches: boolean }) => void;
    change?.({ matches: false });
    expect(localStorage.getItem('theme')).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('getThemePreference reads stored system without resolving OS', async () => {
    localStorage.setItem('theme', 'system');
    vi.resetModules();
    const { getThemePreference, initTheme } = await import('./theme');
    initTheme();
    expect(getThemePreference()).toBe('system');
  });
});
