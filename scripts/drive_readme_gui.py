"""Drive the native AutoRename-PDF window for README screenshots.

WebView2 does not expose HTML buttons to UIA. Clicks use PrintWindow + Tesseract
word boxes (and a red-blob fallback for primary buttons). The file picker is the
native German/English common dialog.
"""
from __future__ import annotations

import json
import ctypes
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_readme_screenshots import (  # noqa: E402
    RECT,
    _enum_windows,
    capture_hwnd,
    find_hwnd,
    user32,
)

FIXTURES = ROOT / "screenshot" / "_raw" / "fixtures"
RAW = ROOT / "screenshot" / "_raw"
CDP_EVAL = ROOT / "scripts" / "webview_cdp_eval.mjs"
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def cdp_eval(expression: str) -> dict:
    proc = subprocess.run(
        ["node", str(CDP_EVAL), expression],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"CDP eval failed: {proc.stderr or proc.stdout}")
    line = (proc.stdout or "").strip().splitlines()[-1]
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"type": "string", "value": line}


def page_text() -> str:
    result = cdp_eval("document.body.innerText")
    return str(result.get("value") or "")


def wait_page(snippet: str, timeout: float) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        last = page_text()
        if snippet.lower() in last.lower():
            return
        time.sleep(1.0)
    raise SystemExit(f"timed out waiting for {snippet!r}; last page text:\n{last}")


def wait_cdp(timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        proc = subprocess.run(
            ["node", str(CDP_EVAL), "1"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return
        last = (proc.stderr or proc.stdout).strip()
        time.sleep(0.5)
    raise SystemExit(f"WebView2 CDP not reachable: {last}")


def click_screen(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def foreground(hwnd: int) -> None:
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)


def tesseract_words(image: Image.Image) -> list[tuple[str, int, int, int, int]]:
    tmp = RAW / "_ocr.png"
    RAW.mkdir(parents=True, exist_ok=True)
    image.save(tmp)
    proc = subprocess.run(
        ["tesseract", str(tmp), "stdout", "tsv"],
        capture_output=True,
        text=True,
        check=False,
    )
    words: list[tuple[str, int, int, int, int]] = []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        text = parts[11].strip()
        if not text:
            continue
        left, top, width, height = map(int, parts[6:10])
        words.append((text, left, top, width, height))
    return words


def find_phrase(words: list[tuple[str, int, int, int, int]], phrase: str) -> tuple[int, int] | None:
    needles = phrase.lower().split()
    for i in range(len(words) - len(needles) + 1):
        if [w[0].lower().rstrip(".,:") for w in words[i : i + len(needles)]] == needles:
            left = min(w[1] for w in words[i : i + len(needles)])
            top = min(w[2] for w in words[i : i + len(needles)])
            right = max(w[1] + w[3] for w in words[i : i + len(needles)])
            bottom = max(w[2] + w[4] for w in words[i : i + len(needles)])
            return (left + right) // 2, (top + bottom) // 2
    return None


def red_blob_centers(image: Image.Image) -> list[tuple[int, int, int]]:
    """Return (area, cx, cy) for red primary-button blobs, largest first."""
    pix = image.convert("RGB")
    w, h = pix.size
    visited = bytearray(w * h)
    blobs: list[tuple[int, int, int]] = []

    def is_red(px: tuple[int, int, int]) -> bool:
        r, g, b = px
        return r > 130 and g < 60 and b < 70 and r > g + 70 and r > b + 70

    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if visited[idx]:
                continue
            if not is_red(pix.getpixel((x, y))):
                continue
            stack = [(x, y)]
            visited[idx] = 1
            xs: list[int] = []
            ys: list[int] = []
            while stack:
                cx, cy = stack.pop()
                xs.append(cx)
                ys.append(cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    nidx = ny * w + nx
                    if visited[nidx]:
                        continue
                    if is_red(pix.getpixel((nx, ny))):
                        visited[nidx] = 1
                        stack.append((nx, ny))
            area = len(xs)
            if area < 80:
                continue
            blobs.append((area, sum(xs) // area, sum(ys) // area))
    blobs.sort(reverse=True)
    return blobs


def click_image_point(hwnd: int, ix: int, iy: int) -> None:
    left, top, _, _ = window_rect(hwnd)
    click_screen(left + ix, top + iy)


def snapshot(hwnd: int) -> Image.Image:
    foreground(hwnd)
    return capture_hwnd(hwnd)


def click_text(hwnd: int, phrase: str, image: Image.Image | None = None) -> bool:
    image = image or snapshot(hwnd)
    pos = find_phrase(tesseract_words(image), phrase)
    if not pos:
        return False
    click_image_point(hwnd, pos[0], pos[1])
    return True


def click_primary(hwnd: int, image: Image.Image | None = None) -> bool:
    image = image or snapshot(hwnd)
    blobs = red_blob_centers(image)
    if not blobs:
        return False
    _area, cx, cy = blobs[0]
    click_image_point(hwnd, cx, cy)
    return True


def open_dialog_hwnds() -> list[int]:
    hits = []
    for hwnd, title in _enum_windows():
        folded = title.casefold()
        if folded in {"öffnen", "open"} or folded.endswith("öffnen"):
            hits.append(hwnd)
    return hits


def close_open_dialogs() -> None:
    for hwnd in open_dialog_hwnds():
        user32.PostMessageW(hwnd, 0x0010, 0, 0)
    if open_dialog_hwnds():
        time.sleep(0.4)


def fill_open_dialog(paths: list[Path], timeout: float = 8.0) -> None:
    from pywinauto import Application

    quoted = " ".join(f'"{p.resolve()}"' for p in paths)
    deadline = time.time() + timeout
    hwnd = None
    while time.time() < deadline:
        found = open_dialog_hwnds()
        if found:
            hwnd = found[-1]
            break
        time.sleep(0.2)
    if hwnd is None:
        raise SystemExit("file dialog (Öffnen/Open) did not appear")
    app = Application(backend="uia").connect(handle=hwnd)
    dlg = app.window(handle=hwnd)
    dlg.set_focus()
    time.sleep(0.2)
    edit = dlg.child_window(auto_id="1148", control_type="Edit")
    edit.set_edit_text(quoted)
    time.sleep(0.2)
    dlg.child_window(auto_id="1", control_type="Button").click()
    time.sleep(0.8)


def wait_text(hwnd: int, phrase: str, timeout: float = 90.0) -> Image.Image:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = snapshot(hwnd)
        words = " ".join(w[0] for w in tesseract_words(last))
        if phrase.lower() in words.lower():
            return last
        time.sleep(1.5)
    last.save(RAW / "gui-timeout.png")
    raise SystemExit(f"timed out waiting for {phrase!r}")


def main() -> None:
    user32.SetProcessDPIAware()
    invoice = FIXTURES / "invoice.pdf"
    scan = FIXTURES / "SCAN001.pdf"
    if not invoice.is_file() or not scan.is_file():
        raise SystemExit("fixtures missing; run python scripts/prepare_readme_capture.py")

    hwnd = find_hwnd("AutoRename-PDF")
    foreground(hwnd)
    wait_cdp()
    close_open_dialogs()
    text = page_text()
    already_previewed = "PREVIEW" in text and " AP " in text
    if not already_previewed:
        if cdp_eval("document.getElementById('btn-clear') ? 'yes' : 'no'").get("value") == "yes":
            cdp_eval("document.getElementById('btn-clear').click()")
            time.sleep(0.4)
        empty = snapshot(hwnd)
        empty.save(RAW / "gui-empty.png")
        if "Preview names" not in page_text():
            cdp_eval("document.getElementById('btn-browse-files')?.click()")
            fill_open_dialog([invoice, scan])
            wait_page("Preview names", timeout=20)
        queued = snapshot(hwnd)
        queued.save(RAW / "gui-queued.png")
        cdp_eval("document.getElementById('btn-dry-run')?.click()")
        wait_page("PREVIEW", timeout=120)
    previewed = snapshot(hwnd)
    previewed.save(RAW / "gui-preview.png")

    cdp_eval("document.getElementById('btn-rename')?.click()")
    wait_page("RENAMED", timeout=60)
    renamed = snapshot(hwnd)
    renamed.save(RAW / "gui.png")
    print(RAW / "gui.png")


if __name__ == "__main__":
    main()
