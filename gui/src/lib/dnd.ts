import { getCurrentWebview } from '@tauri-apps/api/webview';
import { expandFolder } from './filepicker';

export function setupDragDrop(
  onDrop: (paths: string[]) => void,
  onHover: (hovering: boolean) => void,
): () => void {
  let unlisten: (() => void) | undefined;

  getCurrentWebview().onDragDropEvent(async (event) => {
    switch (event.payload.type) {
      case 'over':
        onHover(true);
        break;
      case 'drop': {
        onHover(false);
        try {
          const dropped = event.payload.paths;
          const pdfFiles = dropped.filter((p: string) => p.toLowerCase().endsWith('.pdf'));
          const nonPdf = dropped.filter((p: string) => !p.toLowerCase().endsWith('.pdf'));

          const expanded = await Promise.all(
            nonPdf.map(async (p: string) => {
              try { return await expandFolder(p); }
              catch { return [] as string[]; }
            }),
          );

          onDrop([...pdfFiles, ...expanded.flat()]);
        } catch {
          onDrop([]);
        }
        break;
      }
      case 'leave':
        onHover(false);
        break;
    }
  }).then((fn) => { unlisten = fn; });

  return () => unlisten?.();
}
