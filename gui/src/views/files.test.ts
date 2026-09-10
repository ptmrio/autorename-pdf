import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/sidecar', () => ({
  renamePdfs: vi.fn(),
  undoRename: vi.fn(),
  isErrorResult: (r: { success: boolean }) => !r.success,
  getUndoLogDir: vi.fn(async () => 'D:\\runtime'),
  inspectConfig: vi.fn(),
}));

vi.mock('../lib/filepicker', () => ({
  pickPdfFiles: vi.fn(async () => []),
  pickFolder: vi.fn(async () => []),
}));

vi.mock('../lib/dnd', () => ({
  setupDragDrop: vi.fn(() => () => {}),
}));

vi.mock('../lib/toast', () => ({ showToast: vi.fn() }));
vi.mock('../lib/rename-cache', () => ({ applyCachedRenames: vi.fn() }));

import { renderFilesView } from './files';
import { setState } from '../lib/state';
import { inspectConfig } from '../lib/sidecar';

describe('files readiness', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    vi.mocked(inspectConfig).mockReset();
    setState({
      view: 'files',
      files: [],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: 'CLI executable not found',
      lastBatchId: null,
    });
  });

  it('shows a persistent banner on the empty dropzone', () => {
    renderFilesView(document.getElementById('root')!);
    const banner = document.getElementById('ready-banner');
    expect(banner).not.toBeNull();
    expect(banner!.getAttribute('role')).toBe('status');
    expect(banner!.textContent).toMatch(/CLI executable not found/);
    expect(document.getElementById('btn-browse-files')).not.toBeNull();
    expect(document.body.textContent).toMatch(/20260907 ACME AP\.pdf/);
  });

  it('Retry forces a new inspect rather than the cached snapshot', async () => {
    vi.mocked(inspectConfig).mockResolvedValue({
      config_path: 'D:\\runtime\\config.yaml',
      valid: true,
      issues: [],
      profile: 'business',
      resolved_profile: {},
      config: { ai: { provider: 'openai' } },
    });
    renderFilesView(document.getElementById('root')!);
    document.getElementById('btn-retry-ready')!.click();
    await vi.waitFor(() => {
      expect(inspectConfig).toHaveBeenCalledWith({ force: true });
    });
  });

  it('shows the banner when files are queued', () => {
    setState({
      view: 'files',
      files: [{ path: 'D:\\a.pdf', name: 'a.pdf', status: 'pending' }],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: 'Config error',
      lastBatchId: null,
    });
    renderFilesView(document.getElementById('root')!);
    expect(document.getElementById('ready-banner')).not.toBeNull();
  });

  it('relabels dry run to Preview names when files are queued', () => {
    setState({
      view: 'files',
      files: [{ path: 'D:\\a.pdf', name: 'a.pdf', status: 'pending' }],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: '',
      lastBatchId: null,
    });
    renderFilesView(document.getElementById('root')!);
    expect(document.getElementById('btn-dry-run')!.textContent).toMatch(/Preview names/);
    expect(document.getElementById('btn-rename')!.className).toMatch(/btn-primary/);
    expect(document.getElementById('btn-dry-run')!.className).toMatch(/btn-secondary/);
  });

  it('keeps Preview names and Rename when Undo remains after Clear', () => {
    setState({
      view: 'files',
      files: [{ path: 'D:\\next.pdf', name: 'next.pdf', status: 'pending' }],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: '',
      lastBatchId: 'batch-1',
    });
    renderFilesView(document.getElementById('root')!);
    expect(document.getElementById('btn-rename')).not.toBeNull();
    expect(document.getElementById('btn-dry-run')).not.toBeNull();
    expect(document.getElementById('btn-undo')).not.toBeNull();
    expect(document.getElementById('btn-rename')!.className).toMatch(/btn-primary/);
  });

  it('keeps Undo on the empty view when a batch id remains', () => {
    setState({
      view: 'files',
      files: [],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: '',
      lastBatchId: 'batch-1',
    });
    renderFilesView(document.getElementById('root')!);
    expect(document.getElementById('btn-undo')).not.toBeNull();
  });

  function longEntry(
    status: 'pending' | 'renamed',
    name: string,
    newName: string,
  ) {
    return {
      path: `D:\\docs\\${name}`,
      name,
      status,
      result: {
        file: `D:\\docs\\${name}`,
        status: 'renamed' as const,
        new_name: newName,
        new_path: `D:\\docs\\${newName}`,
        error: null,
        warnings: [],
        company: 'ACME',
        date: '2026-09-07',
        doc_type: 'AP',
        provider: 'openai',
        model: 'gpt-5.6-luna',
      },
    };
  }

  it('puts the full original and proposed names on title for preview and renamed rows', () => {
    const ampOrig = 'A & B invoice.pdf';
    const ampNew = '20260907 ACME AP A & B.pdf';
    const longOrig = `${'invoice-scan-'.repeat(8)}.pdf`;
    const longNew = '20260907 ACME AP VERY LONG COUNTERPARTY NAME HERE.pdf';
    setState({
      view: 'files',
      files: [
        longEntry('pending', ampOrig, ampNew),
        longEntry('renamed', longOrig, longNew),
      ],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: '',
      lastBatchId: null,
    });
    renderFilesView(document.getElementById('root')!);
    const names = [...document.querySelectorAll('.fq-name')] as HTMLElement[];
    const proposed = [...document.querySelectorAll('.fq-new-name')] as HTMLElement[];
    expect(names[0].getAttribute('title')).toBe(ampOrig);
    expect(proposed[0].getAttribute('title')).toBe(ampNew);
    expect(names[1].getAttribute('title')).toBe(longOrig);
    expect(proposed[1].getAttribute('title')).toBe(longNew);
    expect(document.querySelectorAll('.fq-new-name-preview').length).toBe(1);
    expect(document.querySelectorAll('.fq-new-name-renamed').length).toBe(1);
  });

  it('renders ampersand-entity filenames as literal text, not HTML entities', () => {
    const orig = 'A &copy; invoice.pdf';
    const proposed = '20260907 ACME AP A &copy; invoice.pdf';
    setState({
      view: 'files',
      files: [longEntry('pending', orig, proposed)],
      processing: false,
      progress: '',
      lastResult: null,
      dryRunResult: null,
      statusError: '',
      lastBatchId: null,
    });
    renderFilesView(document.getElementById('root')!);
    const name = document.querySelector('.fq-name') as HTMLElement;
    const next = document.querySelector('.fq-new-name') as HTMLElement;
    expect(name.textContent).toBe(orig);
    expect(next.textContent).toBe(proposed);
    expect(name.getAttribute('title')).toBe(orig);
    expect(next.getAttribute('title')).toBe(proposed);
  });
});
