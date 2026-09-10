import { initTitlebar } from './lib/titlebar';
import { initTheme } from './lib/theme';
import { initRenderer, createStatusBar } from './renderer';
import { setState } from './lib/state';
import { inspectConfig, invalidateConfigSnapshot } from './lib/sidecar';
import { refreshSettingsIfOpen } from './views/settings';
import { getCurrentWindow } from '@tauri-apps/api/window';

document.addEventListener('DOMContentLoaded', () => {
  try {
    initTitlebar();
  } catch {
    /* jsdom / Vite without Tauri */
  }
  initTheme();

  const appEl = document.getElementById('app');
  if (!appEl) throw new Error('#app element not found');

  // Content area (flex-1, takes remaining space)
  const content = document.createElement('div');
  content.className = 'flex flex-col flex-1 min-h-0';
  appEl.appendChild(content);

  // Status bar at bottom
  createStatusBar(appEl);

  initRenderer(content);

  try {
    void getCurrentWindow().onFocusChanged((event) => {
      if (event.payload) {
        invalidateConfigSnapshot();
        void refreshSettingsIfOpen();
      }
    }).catch(() => {
      /* non-Tauri / denied */
    });
  } catch {
    /* jsdom */
  }

  inspectConfig().then((snapshot) => {
    if (!snapshot.valid) {
      const errors = snapshot.issues.filter((i) => i.level === 'error');
      if (errors.length > 0) setState({ statusError: 'Config error', statusErrorAlert: false });
      else setState({ statusError: '', statusErrorAlert: false });
    } else {
      setState({ statusError: '', statusErrorAlert: false });
    }
  }).catch((err) => {
    const errStr = String(err);
    if (errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries') || errStr.includes('invoke')) {
      setState({ statusError: 'CLI executable not found', statusErrorAlert: false });
    } else {
      setState({ statusError: 'Config error', statusErrorAlert: false });
    }
  });
});
