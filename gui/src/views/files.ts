import { getState, subscribe, addFiles, clearFiles, setState, updateFileStatuses } from '../lib/state';
import { setupDragDrop } from '../lib/dnd';
import { pickPdfFiles, pickFolder } from '../lib/filepicker';
import { renamePdfs, undoRename, isErrorResult } from '../lib/sidecar';
import { applyCachedRenames } from '../lib/rename-cache';
import { showToast } from '../lib/toast';
import type { AppState, FileEntry } from '../lib/state';
import type { BatchResult, SidecarResult } from '../lib/sidecar';

let container: HTMLElement;
let cleanupDnd: (() => void) | undefined;
let unsubscribe: (() => void) | undefined;

export function renderFilesView(root: HTMLElement): void {
  container = root;

  cleanupDnd = setupDragDrop(
    (paths) => {
      if (paths.length > 0) addFiles(paths);
      else showToast('No PDF files in drop', 'warning');
    },
    (hovering) => {
      const dropZone = container.querySelector('.drop-zone');
      const fileList = container.querySelector('#file-list-container');
      if (dropZone) {
        dropZone.classList.toggle('drop-zone-active', hovering);
      } else if (fileList) {
        fileList.classList.toggle('drag-hover', hovering);
      }
    },
  );

  unsubscribe = subscribe(render);
  render(getState());
}

export function destroyFilesView(): void {
  unsubscribe?.();
  unsubscribe = undefined;
  cleanupDnd?.();
}

function render(state: AppState): void {
  if (state.view !== 'files') return;

  if (state.files.length === 0) {
    renderEmpty();
  } else {
    renderFileList(state);
  }
}

function renderEmpty(): void {
  container.innerHTML = `
    <div class="flex flex-col items-center justify-center flex-1 p-8">
      <div class="drop-zone flex flex-col items-center justify-center gap-4 p-12 w-full max-w-lg
                  border-2 border-dashed rounded-xl border-[var(--border-secondary)]
                  hover:border-[var(--color-primary)] transition-colors cursor-pointer"
           id="drop-zone-area">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.5" class="text-[var(--text-tertiary)]">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <line x1="9" y1="15" x2="12" y2="12"/>
          <line x1="15" y1="15" x2="12" y2="12"/>
        </svg>
        <p class="text-[var(--text-secondary)] text-center">
          Drop PDF files here<br>
          <span class="text-sm text-[var(--text-tertiary)]">or click to browse</span>
        </p>
        <div class="flex gap-3 mt-2">
          <button class="btn btn-primary btn-sm" id="btn-browse-files">Browse Files</button>
          <button class="btn btn-secondary btn-sm" id="btn-browse-folder">Browse Folder</button>
        </div>
      </div>
    </div>
  `;

  document.getElementById('btn-browse-files')?.addEventListener('click', async () => {
    const files = await pickPdfFiles();
    if (files.length > 0) addFiles(files);
  });

  document.getElementById('btn-browse-folder')?.addEventListener('click', async () => {
    const files = await pickFolder();
    if (files === null) return;
    if (files.length > 0) addFiles(files);
    else showToast('No PDF files found in folder', 'warning');
  });

  document.getElementById('drop-zone-area')?.addEventListener('click', async (e) => {
    if ((e.target as HTMLElement).closest('button')) return;
    const files = await pickPdfFiles();
    if (files.length > 0) addFiles(files);
  });
}

// ---------------------------------------------------------------------------
// File row rendering helpers
// ---------------------------------------------------------------------------

function fileVisualState(f: FileEntry): 'pending' | 'preview' | 'renamed' | 'failed' | 'skipped' {
  if (f.status === 'pending' && f.result?.new_name) return 'preview';
  return f.status;
}

function renderFileRow(f: FileEntry): string {
  const vs = fileVisualState(f);
  const newName = f.result?.new_name;
  const error = f.result?.error;

  const dotClass = `fq-dot fq-dot-${vs}`;
  const badgeClass = `fq-badge fq-badge-${vs}`;
  const badgeLabel = vs === 'preview' ? 'preview' : f.status;

  let detail = '';
  if (newName && (vs === 'preview' || vs === 'renamed')) {
    const nameClass = vs === 'preview' ? 'fq-new-name-preview' : 'fq-new-name-renamed';
    detail = `<span class="fq-preview"><span class="fq-arrow">\u2192</span><span class="fq-new-name ${nameClass}">${newName}</span></span>`;
  }
  if (error && vs === 'failed') {
    detail = `<span class="fq-error">${error}</span>`;
  }

  return `
    <div class="fq-row">
      <span class="${dotClass}"></span>
      <div class="fq-info">
        <span class="fq-name">${f.name}</span>
        ${detail}
      </div>
      <span class="${badgeClass}">${badgeLabel}</span>
    </div>`;
}

// ---------------------------------------------------------------------------
// File list view
// ---------------------------------------------------------------------------

function renderFileList(state: AppState): void {
  const hasResults = state.lastResult !== null;
  const pendingCount = state.files.filter((f) => f.status === 'pending').length;
  const busy = state.processing;

  // Button bar: always visible, disabled during processing
  let actionsHtml: string;
  if (hasResults) {
    actionsHtml = `
      <div class="fq-actions-left">
        <button class="btn btn-secondary btn-sm" id="btn-undo" ${busy ? 'disabled' : ''}>Undo Last</button>
        <button class="btn btn-primary btn-sm" id="btn-add-more" ${busy ? 'disabled' : ''}>Add More Files</button>
      </div>`;
  } else {
    const noFiles = pendingCount === 0;
    actionsHtml = `
      <div class="fq-actions-left">
        <button class="btn btn-secondary btn-sm" id="btn-dry-run" ${busy || noFiles ? 'disabled' : ''}>Dry Run</button>
        <button class="btn btn-primary btn-sm" id="btn-rename" ${busy || noFiles ? 'disabled' : ''}>
          Rename ${pendingCount} File${pendingCount !== 1 ? 's' : ''}
        </button>
      </div>`;
  }

  container.innerHTML = `
    <div class="fq-container" id="file-list-container">
      <div class="fq-header">
        <span class="fq-count">${state.files.length} file${state.files.length !== 1 ? 's' : ''}</span>
        ${busy ? `<span class="fq-progress-text">${state.progress || 'Processing\u2026'}</span>` : ''}
      </div>
      ${busy ? '<div class="fq-progress-bar"></div>' : ''}
      <div class="fq-list">
        ${state.files.map(renderFileRow).join('')}
      </div>
      <div class="fq-actions">
        ${actionsHtml}
        <button class="btn btn-ghost btn-sm" id="btn-clear" ${busy ? 'disabled' : ''}>Clear</button>
      </div>
    </div>
  `;

  // Bind actions
  document.getElementById('btn-dry-run')?.addEventListener('click', () => runRename(true));
  document.getElementById('btn-rename')?.addEventListener('click', () => runRename(false));
  document.getElementById('btn-clear')?.addEventListener('click', () => clearFiles());
  document.getElementById('btn-undo')?.addEventListener('click', handleUndo);
  document.getElementById('btn-add-more')?.addEventListener('click', async () => {
    const files = await pickPdfFiles();
    if (files.length > 0) addFiles(files);
  });
}

// ---------------------------------------------------------------------------
// Rename (with dry-run cache support)
// ---------------------------------------------------------------------------

async function runRename(dryRun: boolean): Promise<void> {
  const state = getState();

  // Cache path: apply dry-run results directly without re-processing
  if (!dryRun && state.dryRunResult) {
    const filesToRename = state.files.filter((f) => f.status === 'pending' || f.status === 'skipped');
    if (filesToRename.length === 0) {
      showToast('No files to process', 'warning');
      return;
    }
    setState({ processing: true, progress: 'Applying cached results\u2026' });
    try {
      const batch = await applyCachedRenames(
        filesToRename,
        (line) => setState({ progress: line }),
      );
      const firstPath = state.files[0]?.path;
      const undoDir = firstPath ? firstPath.replace(/[\\/][^\\/]+$/, '') : null;
      setState({ processing: false, progress: '', statusError: '' });
      updateFileStatuses(batch, false);
      setState({ lastResult: batch, dryRunResult: null, undoDirectory: undoDir, lastBatchId: batch.batch_id ?? null });
      if (batch.failed > 0) {
        showToast(`${batch.renamed} renamed, ${batch.failed} failed`, 'warning');
      } else {
        showToast(`${batch.renamed} files renamed successfully`, 'success');
      }
    } catch (err) {
      setState({ processing: false, progress: '' });
      showToast(`Rename failed: ${err}`, 'danger');
    }
    return;
  }

  // Standard path: call CLI sidecar
  const paths = state.files.filter((f) => f.status === 'pending' || f.status === 'skipped').map((f) => f.path);

  if (paths.length === 0) {
    showToast('No files to process', 'warning');
    return;
  }

  setState({ processing: true, progress: 'Starting...' });

  let result: SidecarResult;
  try {
    result = await renamePdfs(
      paths,
      { dryRun },
      (line) => setState({ progress: line }),
    );
  } catch (err) {
    const errStr = String(err);
    if (errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries')) {
      setState({ processing: false, progress: '', statusError: 'CLI executable not found' });
      showToast('CLI executable not found. Reinstall the app, or run "python build.py --cli-only --nosign" if developing.', 'danger');
    } else {
      setState({ processing: false, progress: '' });
      showToast(`Error: ${errStr}`, 'danger');
    }
    return;
  }

  setState({ processing: false, progress: '', statusError: '' });

  if (isErrorResult(result)) {
    let msg = result.message;
    let statusMsg = '';
    if (result.error_type === 'sidecar_error') {
      msg = 'CLI executable not found. Reinstall the app, or run "python build.py --cli-only --nosign" if developing.';
      statusMsg = 'CLI executable not found';
    } else if (result.error_type === 'config_error') {
      msg = 'config.yaml missing or invalid — copy config.yaml.example and add your API key';
      statusMsg = 'Config error';
    } else if (result.error_type === 'auth_error') {
      msg = 'API key missing or invalid — set ai.api_key in config.yaml';
      statusMsg = 'Auth error';
    }
    if (result.suggestion) msg += `. ${result.suggestion}`;
    if (statusMsg) setState({ statusError: statusMsg });
    showToast(msg, 'danger');
    return;
  }

  const batch = result as BatchResult;
  updateFileStatuses(batch, dryRun);

  if (dryRun) {
    setState({ dryRunResult: batch });
    showToast(`Preview: ${batch.renamed} to rename, ${batch.skipped} to skip`, 'info');
  } else {
    // Derive undo directory from first file's parent path
    const firstPath = state.files[0]?.path;
    const undoDir = firstPath ? firstPath.replace(/[\\/][^\\/]+$/, '') : null;
    setState({ lastResult: batch, undoDirectory: undoDir, lastBatchId: batch.batch_id ?? null });
    if (batch.failed > 0) {
      showToast(`${batch.renamed} renamed, ${batch.failed} failed`, 'warning');
    } else {
      showToast(`${batch.renamed} files renamed successfully`, 'success');
    }
  }
}

async function handleUndo(): Promise<void> {
  const { undoDirectory, lastBatchId } = getState();
  setState({ processing: true, progress: 'Undoing...' });

  try {
    const result = await undoRename(undoDirectory ?? undefined, lastBatchId ?? undefined);
    setState({ processing: false, progress: '' });

    if ('error_type' in result) {
      let msg = result.message;
      if (result.suggestion) msg += `. ${result.suggestion}`;
      showToast(msg, 'danger');
    } else if (result.success) {
      showToast(`${result.restored} files restored`, 'success');
      clearFiles();
    } else {
      showToast(`Undo: ${result.restored} restored, ${result.failed} failed`, 'warning');
    }
  } catch (err) {
    setState({ processing: false, progress: '' });
    showToast(`Undo failed: ${err}`, 'danger');
  }
}
