import { subscribe, getState, setState } from './lib/state';
import { renderFilesView, destroyFilesView } from './views/files';
import { renderSettingsView } from './views/settings';
import { renderAboutView } from './views/about';
import { toggleTheme } from './lib/theme';
import type { AppState, AppView } from './lib/state';

let currentView: AppView | null = null;

export function initRenderer(appEl: HTMLElement): void {
  subscribe((state: AppState) => {
    if (state.view !== currentView) {
      switchView(appEl, state.view);
    }
  });

  // Initial render
  switchView(appEl, getState().view);
}

function switchView(appEl: HTMLElement, view: AppView): void {
  if (currentView === 'files') {
    destroyFilesView();
  }

  currentView = view;

  switch (view) {
    case 'files':
      renderFilesView(appEl);
      break;
    case 'settings':
      renderSettingsView(appEl);
      break;
    case 'about':
      renderAboutView(appEl);
      break;
  }
}

export function createStatusBar(container: HTMLElement): void {
  const bar = document.createElement('div');
  bar.className = 'status-bar';
  bar.innerHTML = `
    <div class="status-bar-left">
      <button class="status-bar-btn" data-view="settings" title="Settings" aria-label="Settings">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      </button>
      <button id="btn-toggle-theme" class="status-bar-btn" title="Toggle theme">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      </button>
      <button class="status-bar-btn" data-view="about" title="About" aria-label="About">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>
      </button>
    </div>
    <div class="status-bar-right">
      <span id="status-text">Ready</span>
    </div>
  `;

  container.appendChild(bar);

  // View navigation (settings gear toggles between files and settings)
  bar.querySelectorAll('[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = (btn as HTMLElement).dataset.view as AppView;
      const current = getState().view;
      setState({ view: current === target ? 'files' : target });
    });
  });

  // Theme toggle
  document.getElementById('btn-toggle-theme')?.addEventListener('click', toggleTheme);

  // Status text updates
  subscribe((state) => {
    const statusEl = document.getElementById('status-text');
    if (!statusEl) return;

    if (state.processing) {
      statusEl.textContent = state.progress || 'Processing...';
      statusEl.classList.remove('status-error');
    } else if (state.statusError) {
      statusEl.textContent = state.statusError;
      statusEl.classList.add('status-error');
    } else if (state.files.length > 0) {
      const provider = state.lastResult?.files[0]?.provider ?? '';
      const model = state.lastResult?.files[0]?.model ?? '';
      const providerInfo = provider ? ` \u00b7 ${provider}${model ? ` / ${model}` : ''}` : '';
      statusEl.textContent = `${state.files.length} files${providerInfo}`;
      statusEl.classList.remove('status-error');
    } else {
      statusEl.textContent = 'Ready';
      statusEl.classList.remove('status-error');
    }
  });
}
