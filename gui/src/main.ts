import { initTitlebar } from './lib/titlebar';
import { initTheme } from './lib/theme';
import { initRenderer, createStatusBar } from './renderer';
import { setState } from './lib/state';
import { validateConfig } from './lib/sidecar';

document.addEventListener('DOMContentLoaded', () => {
  initTitlebar();
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

  // Startup health check — surface problems in the status bar immediately
  validateConfig().then((validation) => {
    if (!validation.valid) {
      const errors = validation.issues.filter((i) => i.level === 'error');
      if (errors.length > 0) setState({ statusError: 'Config error' });
    }
  }).catch((err) => {
    const errStr = String(err);
    if (errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries')) {
      setState({ statusError: 'CLI executable not found' });
    } else {
      setState({ statusError: 'Config error' });
    }
  });
});
