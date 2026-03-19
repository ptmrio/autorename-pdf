import { getCurrentWindow } from '@tauri-apps/api/window';

export function initTitlebar(): void {
  const appWindow = getCurrentWindow();

  document.getElementById('btn-minimize')?.addEventListener('click', () => {
    appWindow.minimize();
  });
  document.getElementById('btn-maximize')?.addEventListener('click', () => {
    appWindow.toggleMaximize();
  });
  document.getElementById('btn-close')?.addEventListener('click', () => {
    appWindow.close();
  });
}
