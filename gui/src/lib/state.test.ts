import { describe, it, expect, beforeEach } from 'vitest';
import { getState, setState, addFiles, clearFiles, updateFileStatuses, subscribe } from './state';
import type { BatchResult } from './sidecar';

// Reset state before each test
beforeEach(() => {
  setState({
    view: 'files',
    files: [],
    processing: false,
    progress: '',
    lastResult: null,
    dryRunResult: null,
    statusError: '',
    undoDirectory: null,
    lastBatchId: null,
  });
});

// ---------------------------------------------------------------------------
// Helper to build a BatchResult matching CLI output format
// ---------------------------------------------------------------------------
function makeBatchResult(
  files: Array<{ file: string; status: 'renamed' | 'skipped' | 'failed'; new_name?: string }>,
  dryRun = false,
): BatchResult {
  return {
    success: files.every((f) => f.status !== 'failed'),
    total: files.length,
    renamed: files.filter((f) => f.status === 'renamed').length,
    skipped: files.filter((f) => f.status === 'skipped').length,
    failed: files.filter((f) => f.status === 'failed').length,
    dry_run: dryRun,
    files: files.map((f) => ({
      file: f.file,
      status: f.status,
      new_name: f.new_name ?? null,
      new_path: null,
      error: null,
      company: null,
      date: null,
      doc_type: null,
      provider: null,
      model: null,
    })),
  };
}

// ---------------------------------------------------------------------------
// BUG: Path separator mismatch (Windows backslash vs CLI forward slash)
// ---------------------------------------------------------------------------
describe('updateFileStatuses — path matching', () => {
  it('matches when paths are identical (Linux/macOS)', () => {
    addFiles(['/home/user/invoice.pdf']);
    const batch = makeBatchResult([
      { file: '/home/user/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
    ]);

    updateFileStatuses(batch, false);

    const state = getState();
    expect(state.files[0].status).toBe('renamed');
    expect(state.files[0].result?.new_name).toBe('20250101 ACME Invoice.pdf');
  });

  it('BUG: fails when Tauri gives backslashes but CLI returns forward slashes', () => {
    // Tauri on Windows returns backslash paths
    addFiles(['D:\\Documents\\invoice.pdf']);

    // Python CLI normalizes to forward slashes: os.path.abspath().replace("\\", "/")
    const batch = makeBatchResult([
      { file: 'D:/Documents/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
    ]);

    updateFileStatuses(batch, false);

    const state = getState();
    // This FAILS with the current code — file stays 'pending'
    expect(state.files[0].status).toBe('renamed');
  });

  it('handles mixed-case drive letters', () => {
    addFiles(['d:\\Documents\\invoice.pdf']);
    const batch = makeBatchResult([
      { file: 'D:/Documents/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
    ]);

    updateFileStatuses(batch, false);

    expect(getState().files[0].status).toBe('renamed');
  });
});

// ---------------------------------------------------------------------------
// Dry-run vs real rename
// ---------------------------------------------------------------------------
describe('updateFileStatuses — dry run flag', () => {
  it('keeps status as pending during dry run but stores result', () => {
    addFiles(['/home/user/invoice.pdf']);
    const batch = makeBatchResult([
      { file: '/home/user/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
    ], true);

    updateFileStatuses(batch, true);

    const file = getState().files[0];
    expect(file.status).toBe('pending');
    expect(file.result?.new_name).toBe('20250101 ACME Invoice.pdf');
  });

  it('updates status to renamed for real rename', () => {
    addFiles(['/home/user/invoice.pdf']);
    const batch = makeBatchResult([
      { file: '/home/user/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
    ]);

    updateFileStatuses(batch, false);

    expect(getState().files[0].status).toBe('renamed');
  });

  it('dry run followed by real rename updates status correctly', () => {
    addFiles(['/home/user/invoice.pdf']);

    // Step 1: dry run
    const dryBatch = makeBatchResult([
      { file: '/home/user/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
    ], true);
    updateFileStatuses(dryBatch, true);
    expect(getState().files[0].status).toBe('pending');

    // Step 2: real rename
    const realBatch = makeBatchResult([
      { file: '/home/user/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
    ]);
    updateFileStatuses(realBatch, false);
    expect(getState().files[0].status).toBe('renamed');
  });
});

// ---------------------------------------------------------------------------
// Subscription leak
// ---------------------------------------------------------------------------
describe('subscribe', () => {
  it('returns an unsubscribe function that removes the listener', () => {
    let callCount = 0;
    const unsub = subscribe(() => { callCount++; });

    setState({ progress: 'a' });
    expect(callCount).toBe(1);

    unsub();
    setState({ progress: 'b' });
    expect(callCount).toBe(1); // should not increment after unsub
  });
});

// ---------------------------------------------------------------------------
// addFiles / clearFiles
// ---------------------------------------------------------------------------
describe('addFiles', () => {
  it('deduplicates by path', () => {
    addFiles(['/a.pdf', '/b.pdf']);
    addFiles(['/b.pdf', '/c.pdf']);
    expect(getState().files.map((f) => f.path)).toEqual(['/a.pdf', '/b.pdf', '/c.pdf']);
  });

  it('resets dryRunResult and lastResult', () => {
    setState({ dryRunResult: makeBatchResult([]), lastResult: makeBatchResult([]) });
    addFiles(['/new.pdf']);
    expect(getState().dryRunResult).toBeNull();
    expect(getState().lastResult).toBeNull();
  });
});

describe('clearFiles', () => {
  it('resets files, results, and progress', () => {
    addFiles(['/a.pdf']);
    setState({ progress: 'Processing...', dryRunResult: makeBatchResult([]) });
    clearFiles();
    const s = getState();
    expect(s.files).toEqual([]);
    expect(s.dryRunResult).toBeNull();
    expect(s.lastResult).toBeNull();
    expect(s.progress).toBe('');
  });

  it('resets statusError (BUG-6)', () => {
    setState({ statusError: 'Config error' });
    clearFiles();
    expect(getState().statusError).toBe('');
  });

  it('resets lastBatchId', () => {
    setState({ lastBatchId: '20260319T120000-abc123' });
    clearFiles();
    expect(getState().lastBatchId).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Dry-run skipped/failed status (BUG-8)
// ---------------------------------------------------------------------------
describe('updateFileStatuses — dry run terminal states', () => {
  it('skipped files show skipped status during dry run', () => {
    addFiles(['/home/user/already-named.pdf']);
    const batch = makeBatchResult([
      { file: '/home/user/already-named.pdf', status: 'skipped' },
    ], true);

    updateFileStatuses(batch, true);

    expect(getState().files[0].status).toBe('skipped');
  });

  it('failed files show failed status during dry run', () => {
    addFiles(['/home/user/broken.pdf']);
    const batch = makeBatchResult([
      { file: '/home/user/broken.pdf', status: 'failed' },
    ], true);

    updateFileStatuses(batch, true);

    expect(getState().files[0].status).toBe('failed');
  });

  it('mixed batch: renamed stays pending, skipped becomes skipped during dry run', () => {
    addFiles(['/home/user/invoice.pdf', '/home/user/already-named.pdf']);
    const batch = makeBatchResult([
      { file: '/home/user/invoice.pdf', status: 'renamed', new_name: '20250101 ACME Invoice.pdf' },
      { file: '/home/user/already-named.pdf', status: 'skipped' },
    ], true);

    updateFileStatuses(batch, true);

    const files = getState().files;
    expect(files[0].status).toBe('pending'); // renamed stays pending in dry run
    expect(files[1].status).toBe('skipped'); // skipped becomes skipped immediately
  });
});
