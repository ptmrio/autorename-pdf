import { open } from '@tauri-apps/plugin-dialog';
import { readDir } from '@tauri-apps/plugin-fs';

/**
 * Expand a folder path into its contained PDF file paths (non-recursive).
 * Returns full absolute paths for each .pdf file found.
 */
export async function expandFolder(folderPath: string): Promise<string[]> {
  const clean = folderPath.replace(/[\\/]+$/, '');
  const sep = clean.includes('\\') ? '\\' : '/';
  const entries = await readDir(clean);
  return entries
    .filter((e) => e.isFile && e.name.toLowerCase().endsWith('.pdf'))
    .map((e) => clean + sep + e.name);
}

export async function pickPdfFiles(): Promise<string[]> {
  const result = await open({
    multiple: true,
    filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
  });
  if (!result) return [];
  return Array.isArray(result) ? result : [result];
}

/**
 * Open a folder picker and return the PDF files inside it.
 * Returns null if the user cancelled, or an array of PDF paths (possibly empty).
 */
export async function pickFolder(): Promise<string[] | null> {
  const folder = await open({ directory: true, multiple: false }) as string | null;
  if (!folder) return null;
  return expandFolder(folder);
}
