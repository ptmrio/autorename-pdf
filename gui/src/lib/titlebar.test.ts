import { beforeEach, describe, expect, it, vi } from 'vitest';
import { initTitlebar } from './titlebar';
// gui/src/lib -> gui/index.html. Vite's ?raw import is typed by vite/client,
// so this needs no @types/node.
import html from '../../index.html?raw';

describe('titlebar maximize label', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <button id="btn-minimize"></button>
      <button id="btn-maximize" aria-label="Maximize"></button>
      <button id="btn-close"></button>
    `;
  });

  it('sets Restore when the window reports maximized and flips back on resize', async () => {
    let maximized = true;
    const onResized = vi.fn(async (handler: () => void) => {
      onResized.mock.calls;
      (onResized as unknown as { handler?: () => void }).handler = handler;
      return () => {};
    });
    const win = {
      minimize: vi.fn(),
      toggleMaximize: vi.fn(),
      close: vi.fn(),
      isMaximized: vi.fn(async () => maximized),
      onResized,
    };
    initTitlebar(win);
    await vi.waitFor(() => {
      expect(document.getElementById('btn-maximize')!.getAttribute('aria-label')).toBe('Restore');
    });
    maximized = false;
    const handler = onResized.mock.calls[0][0] as () => void;
    handler();
    await vi.waitFor(() => {
      expect(document.getElementById('btn-maximize')!.getAttribute('aria-label')).toBe('Maximize');
    });
  });
});

describe('titlebar drag region', () => {
  it('marks titlebar-left as a drag region and keeps controls out of it', () => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const bar = doc.querySelector('.titlebar');
    const left = doc.querySelector('.titlebar-left');
    const controls = doc.querySelector('.titlebar-controls');
    expect(bar?.hasAttribute('data-tauri-drag-region')).toBe(true);
    expect(left?.hasAttribute('data-tauri-drag-region')).toBe(true);
    expect(controls?.hasAttribute('data-tauri-drag-region')).toBe(false);
    expect(controls?.querySelector('[data-tauri-drag-region]')).toBeNull();
  });
});
