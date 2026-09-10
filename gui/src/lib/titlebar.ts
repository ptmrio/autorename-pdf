import { getCurrentWindow } from '@tauri-apps/api/window';

export interface TitlebarWindow {
  minimize: () => void | Promise<void>;
  toggleMaximize: () => void | Promise<void>;
  close: () => void | Promise<void>;
  isMaximized: () => Promise<boolean>;
  onResized: (handler: () => void) => Promise<unknown>;
}

async function syncMaximizeLabel(win: TitlebarWindow): Promise<void> {
  const btn = document.getElementById('btn-maximize');
  if (!btn) return;
  try {
    const max = await win.isMaximized();
    btn.setAttribute('aria-label', max ? 'Restore' : 'Maximize');
  } catch {
    /* jsdom / non-Tauri */
  }
}

export function initTitlebar(win: TitlebarWindow = getCurrentWindow() as unknown as TitlebarWindow): void {
  document.getElementById('btn-minimize')?.addEventListener('click', () => {
    void win.minimize();
  });
  document.getElementById('btn-maximize')?.addEventListener('click', () => {
    void Promise.resolve(win.toggleMaximize()).then(() => syncMaximizeLabel(win));
  });
  document.getElementById('btn-close')?.addEventListener('click', () => {
    void win.close();
  });
  void syncMaximizeLabel(win);
  void win.onResized(() => {
    void syncMaximizeLabel(win);
  }).catch(() => {
    /* non-Tauri */
  });
}
