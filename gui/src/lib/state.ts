import type { FileResult, BatchResult } from './sidecar';

export type AppView = 'files' | 'settings' | 'about';

export interface FileEntry {
  path: string;
  name: string;
  status: 'pending' | 'renamed' | 'skipped' | 'failed';
  result?: FileResult;
}

export interface AppState {
  view: AppView;
  files: FileEntry[];
  processing: boolean;
  progress: string;
  lastResult: BatchResult | null;
  dryRunResult: BatchResult | null;
  statusError: string;
  undoDirectory: string | null;
  lastBatchId: string | null;
}

type Listener = (state: AppState) => void;

const listeners: Set<Listener> = new Set();

let state: AppState = {
  view: 'files',
  files: [],
  processing: false,
  progress: '',
  lastResult: null,
  dryRunResult: null,
  statusError: '',
  undoDirectory: null,
  lastBatchId: null,
};

export function getState(): Readonly<AppState> {
  return state;
}

export function setState(partial: Partial<AppState>): void {
  state = { ...state, ...partial };
  listeners.forEach((fn) => fn(state));
}

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function addFiles(paths: string[]): void {
  const existing = new Set(state.files.map((f) => f.path));
  const newEntries: FileEntry[] = paths
    .filter((p) => !existing.has(p))
    .map((p) => ({
      path: p,
      name: p.split(/[\\/]/).pop() || p,
      status: 'pending' as const,
    }));
  setState({ files: [...state.files, ...newEntries], dryRunResult: null, lastResult: null });
}

export function clearFiles(): void {
  setState({ files: [], dryRunResult: null, lastResult: null, progress: '', undoDirectory: null, statusError: '', lastBatchId: null });
}

function normalizePath(p: string): string {
  return p.replace(/\\/g, '/').toLowerCase();
}

export function updateFileStatuses(result: BatchResult, isDryRun = false): void {
  const resultMap = new Map(result.files.map((f) => [normalizePath(f.file), f]));
  const updatedFiles = state.files.map((entry) => {
    const fileResult = resultMap.get(normalizePath(entry.path));
    if (fileResult) {
      return {
        ...entry,
        status: isDryRun && fileResult.status === 'renamed'
          ? entry.status
          : (fileResult.status as FileEntry['status']),
        result: fileResult,
      };
    }
    return entry;
  });
  setState({ files: updatedFiles });
}
