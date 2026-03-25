import { Command } from '@tauri-apps/plugin-shell';
import { join, resourceDir } from '@tauri-apps/api/path';

export interface FileResult {
  file: string;
  status: 'renamed' | 'skipped' | 'failed';
  new_name: string | null;
  new_path: string | null;
  error: string | null;
  warnings: string[];
  company: string | null;
  date: string | null;
  doc_type: string | null;
  provider: string | null;
  model: string | null;
}

export interface BatchResult {
  success: boolean;
  total: number;
  renamed: number;
  skipped: number;
  failed: number;
  files: FileResult[];
  dry_run: boolean;
  batch_id?: string;
}

export interface ErrorResult {
  success: false;
  error_type: string;
  message: string;
  suggestion: string;
}

export type SidecarResult = BatchResult | ErrorResult;

export interface UndoFileResult {
  old_path: string;
  new_path: string;
  status: 'restored' | 'failed';
  error?: string;
}

export interface UndoResult {
  success: boolean;
  restored: number;
  failed: number;
  files: UndoFileResult[];
  batch_id?: string;
}

export interface ConfigValidation {
  valid: boolean;
  issues: Array<{ field: string; level: string; message: string }>;
}

let resolvedConfigPathPromise: Promise<string> | null = null;
const SIDECAR_OPTIONS = {
  encoding: 'utf-8',
  env: {
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
  },
} as const;

async function getResolvedConfigPath(): Promise<string> {
  if (!resolvedConfigPathPromise) {
    resolvedConfigPathPromise = resourceDir().then((dir) => join(dir, 'config.yaml'));
  }
  return resolvedConfigPathPromise;
}

async function withConfigArg(args: string[]): Promise<string[]> {
  return [...args, '--config', await getResolvedConfigPath()];
}

export function isErrorResult(result: SidecarResult): result is ErrorResult {
  return !result.success && 'error_type' in result;
}

export async function renamePdfs(
  paths: string[],
  options: {
    dryRun?: boolean;
    recursive?: boolean;
    provider?: string;
    model?: string;
    vision?: boolean;
    textOnly?: boolean;
    ocr?: boolean;
  } = {},
  onProgress?: (line: string) => void,
): Promise<SidecarResult> {
  const args = ['rename', ...paths, '--output', 'json'];
  if (options.dryRun) args.push('--dry-run');
  if (options.recursive) args.push('--recursive');
  if (options.provider) args.push('--provider', options.provider);
  if (options.model) args.push('--model', options.model);
  if (options.vision) args.push('--vision');
  if (options.textOnly) args.push('--text-only');
  if (options.ocr) args.push('--ocr');

  const command = Command.sidecar('autorename-pdf-cli', await withConfigArg(args), SIDECAR_OPTIONS);

  command.stderr.on('data', (line) => {
    onProgress?.(line.trim());
  });

  const output = await command.execute();

  if (output.code !== 0 && !output.stdout.trim()) {
    const stderr = output.stderr || '';
    let errorType = 'sidecar_error';
    let message = stderr || `Process exited with code ${output.code}`;
    let suggestion = '';

    if (output.code === 3 || stderr.toLowerCase().includes('config')) {
      errorType = 'config_error';
      message = 'config.yaml missing or invalid.';
      suggestion = 'Create config.yaml next to the executable (see config.yaml.example).';
    } else if (output.code === 11 || stderr.toLowerCase().includes('api key') || stderr.toLowerCase().includes('auth')) {
      errorType = 'auth_error';
      message = 'API key missing or invalid.';
      suggestion = 'Set your AI provider API key in config.yaml under ai.api_key.';
    } else if (!stderr) {
      message = 'CLI executable not found or failed to start.';
      suggestion = 'Re-extract the portable ZIP, or run "python build.py --cli-only --nosign" if developing.';
    }

    return { success: false, error_type: errorType, message, suggestion } as ErrorResult;
  }

  return JSON.parse(output.stdout) as SidecarResult;
}

export async function undoRename(batchId?: string): Promise<UndoResult | ErrorResult> {
  const args = ['undo', '--output', 'json'];
  if (batchId) args.push('--batch', batchId);
  const command = Command.sidecar('autorename-pdf-cli', await withConfigArg(args), SIDECAR_OPTIONS);
  const output = await command.execute();
  if (output.code !== 0 && !output.stdout.trim()) {
    throw new Error(output.stderr || `Undo failed with exit code ${output.code}`);
  }
  return JSON.parse(output.stdout) as UndoResult | ErrorResult;
}

export async function getConfig(): Promise<Record<string, unknown>> {
  const command = Command.sidecar('autorename-pdf-cli', await withConfigArg([
    'config', 'show', '--output', 'json',
  ]), SIDECAR_OPTIONS);
  const output = await command.execute();
  return JSON.parse(output.stdout);
}

export async function getConfigPath(): Promise<string | null> {
  return getResolvedConfigPath();
}

export async function getUndoLogDir(): Promise<string> {
  return resourceDir();
}

export async function validateConfig(): Promise<ConfigValidation> {
  const command = Command.sidecar('autorename-pdf-cli', await withConfigArg([
    'config', 'validate', '--output', 'json',
  ]), SIDECAR_OPTIONS);
  const output = await command.execute();
  return JSON.parse(output.stdout);
}
