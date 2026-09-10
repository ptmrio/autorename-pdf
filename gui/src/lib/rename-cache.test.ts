import { beforeEach, describe, expect, it, vi } from 'vitest';

const { fsRename, readTextFile, writeTextFile } = vi.hoisted(() => ({
  fsRename: vi.fn(),
  readTextFile: vi.fn(),
  writeTextFile: vi.fn(),
}));

vi.mock('@tauri-apps/plugin-fs', () => ({
  rename: fsRename,
  readTextFile,
  writeTextFile,
}));

import { applyCachedRenames } from './rename-cache';
import type { FileEntry } from './state';

function pending(path: string, newPath: string): FileEntry {
  return {
    path,
    name: path.split(/[\\/]/).pop() || path,
    status: 'pending',
    result: {
      file: path,
      status: 'renamed',
      new_name: '20260907 ACME AP.pdf',
      new_path: newPath,
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

describe('applyCachedRenames', () => {
  beforeEach(() => {
    fsRename.mockReset();
    readTextFile.mockReset();
    writeTextFile.mockReset();
    readTextFile.mockRejectedValue(new Error('missing log'));
  });

  it('omits batch_id and skip undo log when no file was renamed', async () => {
    fsRename.mockRejectedValue(new Error('access denied'));
    const batch = await applyCachedRenames(
      [pending('D:\\a.pdf', 'D:\\20260907 ACME AP.pdf')],
      'D:\\runtime',
    );
    expect(batch.renamed).toBe(0);
    expect(batch.failed).toBe(1);
    expect(batch.batch_id).toBeNull();
    expect(writeTextFile).not.toHaveBeenCalled();
  });

  it('omits batch_id when files renamed but undo log cannot be written', async () => {
    fsRename.mockResolvedValue(undefined);
    writeTextFile.mockRejectedValue(new Error('access denied'));
    const batch = await applyCachedRenames(
      [pending('D:\\a.pdf', 'D:\\20260907 ACME AP.pdf')],
      'D:\\runtime',
    );
    expect(batch.renamed).toBe(1);
    expect(batch.batch_id).toBeNull();
  });

  it('does not overwrite a malformed undo log', async () => {
    fsRename.mockResolvedValue(undefined);
    readTextFile.mockResolvedValue('{not-json');
    writeTextFile.mockResolvedValue(undefined);
    const batch = await applyCachedRenames(
      [pending('D:\\a.pdf', 'D:\\20260907 ACME AP.pdf')],
      'D:\\runtime',
    );
    expect(batch.renamed).toBe(1);
    expect(batch.batch_id).toBeNull();
    expect(writeTextFile).not.toHaveBeenCalled();
  });
});
