import { rename as fsRename, readTextFile, writeTextFile } from '@tauri-apps/plugin-fs';
import type { FileEntry } from './state';
import type { BatchResult, FileResult } from './sidecar';

const UNDO_LOG_NAME = '.autorename-log.json';

function joinPath(dir: string, name: string): string {
  const sep = dir.includes('\\') ? '\\' : '/';
  return dir + sep + name;
}

/** Generate a batch ID matching the Python format: YYYYMMDDTHHMMSS-<6hex> in UTC. */
export function generateBatchId(): string {
  const now = new Date();
  const pad = (n: number, len = 2) => String(n).padStart(len, '0');
  const ts = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}T${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`;
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(3)))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return `${ts}-${hex}`;
}

interface UndoLogV2 {
  version: 2;
  batches: Array<{
    batch_id: string;
    timestamp: string;
    source: string;
    undone: boolean;
    files: Array<{ old_path: string; new_path: string; timestamp: string }>;
  }>;
}

/** Read existing undo log and migrate v1 (bare array) to v2 if needed. */
async function readUndoLog(logPath: string): Promise<UndoLogV2> {
  try {
    const raw = JSON.parse(await readTextFile(logPath));
    if (Array.isArray(raw)) {
      // v1 migration
      return {
        version: 2,
        batches: raw.length > 0
          ? [{
              batch_id: 'migrated-v1',
              timestamp: raw[0]?.timestamp ?? '',
              source: 'cli',
              undone: false,
              files: raw,
            }]
          : [],
      };
    }
    return raw as UndoLogV2;
  } catch {
    return { version: 2, batches: [] };
  }
}

/**
 * Apply cached dry-run results by renaming files directly via Tauri FS.
 * Writes a CLI-compatible v2 undo log so `undo` works regardless of how
 * the rename was performed (cached or full CLI pipeline).
 */
export async function applyCachedRenames(
  files: FileEntry[],
  baseDir: string,
  onProgress?: (msg: string) => void,
): Promise<BatchResult> {
  const results: FileResult[] = [];
  let renamed = 0;
  let skipped = 0;
  let failed = 0;
  const undoEntries: Array<{ old_path: string; new_path: string; timestamp: string }> = [];

  const batchId = generateBatchId();
  const total = files.length;
  for (let i = 0; i < files.length; i++) {
    const entry = files[i];
    const cached = entry.result;

    // Skip files without a rename target (already named correctly, or no result)
    if (!cached?.new_path || cached.status === 'skipped') {
      skipped++;
      results.push(cached
        ? { ...cached, status: 'skipped' }
        : { file: entry.path, status: 'skipped', new_name: null, new_path: null, error: null, warnings: [], company: null, date: null, doc_type: null, provider: null, model: null },
      );
      continue;
    }

    onProgress?.(`Renaming [${i + 1}/${total}] ${entry.name}`);

    try {
      await fsRename(entry.path, cached.new_path);
      renamed++;
      results.push({ ...cached, status: 'renamed' });
      undoEntries.push({
        old_path: entry.path,
        new_path: cached.new_path,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      failed++;
      results.push({ ...cached, status: 'failed', error: String(err) });
    }
  }

  // Write undo log in v2 batch format (append to existing)
  if (undoEntries.length > 0 && files.length > 0) {
    const logPath = joinPath(baseDir, UNDO_LOG_NAME);
    try {
      const logData = await readUndoLog(logPath);
      logData.batches.push({
        batch_id: batchId,
        timestamp: new Date().toISOString(),
        source: 'gui',
        undone: false,
        files: undoEntries,
      });
      await writeTextFile(logPath, JSON.stringify(logData, null, 2));
    } catch { /* undo log write failure is non-critical */ }
  }

  return { success: failed === 0, total, renamed, skipped, failed, files: results, dry_run: false, batch_id: batchId };
}
