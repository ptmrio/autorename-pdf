import { getState, subscribe, addFiles, clearFiles, setState, updateFileStatuses } from '../lib/state';
import { setupDragDrop } from '../lib/dnd';
import { pickPdfFiles, pickFolder } from '../lib/filepicker';
import { renamePdfs, undoRename, isErrorResult, getUndoLogDir, inspectConfig } from '../lib/sidecar';
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
    renderEmpty(state);
  } else {
    renderFileList(state);
  }
}

function renderReadyBanner(state: AppState): string {
  if (!state.statusError) return '';
  const hint = state.statusError.includes('CLI')
    ? 'Re-extract the portable ZIP, or run python build.py --cli-only --nosign if developing.'
    : 'Create config.yaml next to the executable from config.yaml.example.';
  return `
    <div id="ready-banner" class="ready-banner" role="${state.statusErrorAlert ? 'alert' : 'status'}">
      <p>${state.statusError}</p>
      <p class="ready-banner-hint">${hint}</p>
      <button type="button" class="btn btn-secondary btn-sm" id="btn-retry-ready">Retry</button>
    </div>`;
}

async function retryReadiness(): Promise<void> {
  try {
    const snapshot = await inspectConfig({ force: true });
    if (snapshot.valid) {
      setState({ statusError: '', statusErrorAlert: false });
    } else if (snapshot.issues.some((i) => i.level === 'error')) {
      setState({ statusError: 'Config error', statusErrorAlert: true });
    } else {
      setState({ statusError: '', statusErrorAlert: false });
    }
  } catch (err) {
    const errStr = String(err);
    if (errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries') || errStr.includes('invoke')) {
      setState({ statusError: 'CLI executable not found', statusErrorAlert: true });
    } else {
      setState({ statusError: 'Config error', statusErrorAlert: true });
    }
  }
}

function bindReadyBanner(): void {
  document.getElementById('btn-retry-ready')?.addEventListener('click', () => {
    void retryReadiness();
  });
}

function renderEmpty(state: AppState): void {
  const canUndo = Boolean(state.lastBatchId) && !state.processing;
  container.innerHTML = `
    ${renderReadyBanner(state)}
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
          <span class="text-sm text-[var(--text-muted)]">or click to browse</span><br>
          <span class="text-sm text-[var(--text-muted)]">Example: 20260907 ACME AP.pdf</span>
        </p>
        <div class="flex gap-3 mt-2">
          <button class="btn btn-primary btn-sm" id="btn-browse-files">Browse Files</button>
          <button class="btn btn-secondary btn-sm" id="btn-browse-folder">Browse Folder</button>
          ${canUndo ? '<button class="btn btn-secondary btn-sm" id="btn-undo">Undo Last</button>' : ''}
        </div>
      </div>
    </div>
  `;

  bindReadyBanner();
  document.getElementById('btn-undo')?.addEventListener('click', () => { void handleUndo(); });

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

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;');
}

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
    detail = `<span class="fq-preview"><span class="fq-arrow">\u2192</span><span class="fq-new-name ${nameClass}" title="${escapeHtml(newName)}">${escapeHtml(newName)}</span></span>`;
  }
  if (error && vs === 'failed') {
    detail = `<span class="fq-error">${error}</span>`;
  }
  const warnings = f.result?.warnings ?? [];
  if (warnings.length > 0 && vs !== 'failed') {
    detail += `<span class="fq-warning">\u26a0 ${warnings.join('; ')}</span>`;
  }

  return `
    <div class="fq-row">
      <span class="${dotClass}"></span>
      <div class="fq-info">
        <span class="fq-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
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
  const canUndo = Boolean(state.lastBatchId) && !busy;
  const noFiles = pendingCount === 0;
  const blocked = busy || noFiles || !!state.statusError;
  const showProcess = pendingCount > 0;
  const showPostJob = (hasResults || canUndo) && !showProcess;

  const processHtml = showProcess ? `
        <button class="btn btn-secondary btn-sm" id="btn-dry-run" ${blocked ? 'disabled' : ''}>Preview names</button>
        <button class="btn btn-primary btn-sm" id="btn-rename" ${blocked ? 'disabled' : ''}>
          Rename ${pendingCount} File${pendingCount !== 1 ? 's' : ''}
        </button>` : '';
  const undoHtml = canUndo || showPostJob ? `
        <button class="btn btn-secondary btn-sm" id="btn-undo" ${!canUndo ? 'disabled' : ''}>Undo Last</button>` : '';
  const addMoreHtml = showPostJob || (canUndo && showProcess) ? `
        <button class="btn ${showProcess ? 'btn-secondary' : 'btn-primary'} btn-sm" id="btn-add-more" ${busy ? 'disabled' : ''}>Add More Files</button>` : '';

  const actionsHtml = `
      <div class="fq-actions-left">
        ${processHtml}
        ${undoHtml}
        ${addMoreHtml}
      </div>`;

  container.innerHTML = `
    <div class="fq-container" id="file-list-container">
      ${renderReadyBanner(state)}
      <div class="fq-header">
        <span class="fq-count">${state.files.length} file${state.files.length !== 1 ? 's' : ''}</span>
        ${busy ? `<span class="fq-progress-text" role="status">${state.progress || 'Processing\u2026'}</span>` : ''}
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

  bindReadyBanner();
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
      const undoLogDir = await getUndoLogDir();
      const batch = await applyCachedRenames(
        filesToRename,
        undoLogDir,
        (line) => setState({ progress: line }),
      );
      setState({ processing: false, progress: '', statusError: '', statusErrorAlert: false });
      updateFileStatuses(batch, false);
      const prevUndo = getState().lastBatchId;
      setState({
        lastResult: batch,
        dryRunResult: null,
        lastBatchId: batch.renamed > 0 ? (batch.batch_id ?? null) : prevUndo,
      });
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
    if (errStr.includes('sidecar') || errStr.includes('not found') || errStr.includes('binaries') || errStr.includes('invoke')) {
      setState({ processing: false, progress: '', statusError: 'CLI executable not found', statusErrorAlert: true });
      showToast('CLI executable not found. Re-extract the portable ZIP, or run "python build.py --cli-only --nosign" if developing.', 'danger');
    } else {
      setState({ processing: false, progress: '' });
      showToast(`Error: ${errStr}`, 'danger');
    }
    return;
  }

  setState({ processing: false, progress: '', statusError: '', statusErrorAlert: false });

  if (isErrorResult(result)) {
    let msg = result.message;
    let statusMsg = '';
    if (result.error_type === 'sidecar_error') {
      msg = 'CLI executable not found. Re-extract the portable ZIP, or run "python build.py --cli-only --nosign" if developing.';
      statusMsg = 'CLI executable not found';
    } else if (result.error_type === 'config_error') {
      msg = 'config.yaml missing or invalid — copy config.yaml.example and add your API key';
      statusMsg = 'Config error';
    } else if (result.error_type === 'auth_error') {
      msg = 'API key missing or invalid — set ai.api_key in config.yaml';
      statusMsg = 'Auth error';
    }
    if (result.suggestion) msg += `. ${result.suggestion}`;
    if (statusMsg) setState({ statusError: statusMsg, statusErrorAlert: true });
    showToast(msg, 'danger');
    return;
  }

  const batch = result as BatchResult;
  updateFileStatuses(batch, dryRun);

  if (dryRun) {
    setState({ dryRunResult: batch });
    if (batch.renamed === 0 && batch.skipped > 0) {
      showToast('Preview: all files already correctly named', 'info');
    } else {
      showToast(`Preview: ${batch.renamed} to rename, ${batch.skipped} to skip`, 'info');
    }
  } else {
    // Only enable undo when files were actually renamed
    if (batch.renamed > 0) {
      setState({ lastResult: batch, lastBatchId: batch.batch_id ?? null });
    } else {
      setState({ lastResult: batch });
    }
    if (batch.failed > 0) {
      showToast(`${batch.renamed} renamed, ${batch.failed} failed`, 'warning');
    } else if (batch.renamed === 0 && batch.skipped > 0) {
      showToast('All files already correctly named', 'info');
    } else {
      showToast(`${batch.renamed} files renamed successfully`, 'success');
    }
    // Surface per-file warnings (e.g. PaddleOCR failures)
    const allWarnings = batch.files.flatMap((f) => f.warnings ?? []);
    const unique = [...new Set(allWarnings)];
    for (const w of unique) {
      showToast(w, 'warning');
    }
  }
}

async function handleUndo(): Promise<void> {
  const { lastBatchId } = getState();
  if (!lastBatchId) {
    showToast('Nothing to undo', 'info');
    return;
  }
  setState({ processing: true, progress: 'Undoing...' });

  try {
    const result = await undoRename(lastBatchId ?? undefined);
    setState({ processing: false, progress: '' });

    if ('error_type' in result) {
      let msg = result.message;
      if (result.suggestion) msg += `. ${result.suggestion}`;
      showToast(msg, 'danger');
    } else if (result.success) {
      showToast(`${result.restored} files restored`, 'success');
      clearFiles();
      setState({ lastBatchId: null });
    } else {
      showToast(`Undo: ${result.restored} restored, ${result.failed} failed`, 'warning');
    }
  } catch (err) {
    setState({ processing: false, progress: '' });
    showToast(`Undo failed: ${err}`, 'danger');
  }
}
