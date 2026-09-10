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

export function getThemePreference(): ThemePreference {
  const raw = localStorage.getItem('theme');
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system';
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
