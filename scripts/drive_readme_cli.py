"""Type the README CLI dry-run into Windows Terminal and BitBlt it."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_readme_screenshots import capture_hwnd, find_hwnd, user32  # noqa: E402
from pywinauto.keyboard import send_keys  # noqa: E402

OUT = ROOT / "screenshot" / "_raw" / "cli.png"


def main() -> None:
    hwnd = find_hwnd("README-CLI-SHOT")
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    user32.MoveWindow(hwnd, 120, 80, 1180, 640, True)
    time.sleep(0.4)
    send_keys("cls{ENTER}", pause=0.02)
    time.sleep(0.3)
    send_keys(
        '.\\autorename-pdf-cli.exe rename --dry-run ".\\SCAN001.pdf"{ENTER}',
        with_spaces=True,
        pause=0.03,
    )
    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(2)
        user32.SetForegroundWindow(hwnd)
        img = capture_hwnd(hwnd, bitblt=True)
        # Done line is enough; keep waiting until it appears in a second capture after a pause
        tmp = ROOT / "screenshot" / "_raw" / "cli-progress.png"
        img.save(tmp)
        try:
            import subprocess
            text = subprocess.run(
                ["tesseract", str(tmp), "stdout"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
        except Exception:
            text = ""
        if "Done" in text and ("luna" in text or "gpt" in text):
            break
        if "1 renamed" in text:
            break
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    capture_hwnd(hwnd, bitblt=True).save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
