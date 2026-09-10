"""Capture and composite README screenshots from native Windows windows.

PrintWindow the real AutoRename-PDF / console hwnd. Do not screenshot Vite/Chromium.
"""
from __future__ import annotations

import argparse
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PW_RENDERFULLCONTENT = 2
PLATE_GUI = (1062, 762)
PLATE_CLI = (1275, 788)
PLATE_TOP = (15, 56, 138, 255)
PLATE_BOTTOM = (114, 155, 237, 255)
# Win11 DWM resize border + BitBlt overlap live on L/R/B. Top is the real titlebar.
CROP_LTRB = (12, 0, 12, 12)

FORBIDDEN_SNIPPETS = (
    " gpt-5.4",
    "gpt-5.4",
    "Portable-3.0.0",
    "CLI executable not found",
    "sk-",
    " ER ",
    " ER\n",
    "Microsoft ER",
    "Hetzner ER",
)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()


def _enum_windows() -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        hits.append((int(hwnd), buf.value))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return hits


def find_hwnd(title_substr: str) -> int:
    title_substr = title_substr.lower()
    matches = [(h, t) for h, t in _enum_windows() if title_substr in t.lower()]
    if not matches:
        raise SystemExit(f"no visible window matching {title_substr!r}")
    matches.sort(key=lambda item: len(item[1]))
    return matches[0][0]


def capture_hwnd(hwnd: int, bitblt: bool = False) -> Image.Image:
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise SystemExit(f"invalid window size {width}x{height}")

    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    gdi32.SelectObject(mem_dc, bmp)
    if bitblt:
        screen_dc = user32.GetDC(0)
        gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, rect.left, rect.top, 0x00CC0020)
        user32.ReleaseDC(0, screen_dc)
        ok = True
    else:
        ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
    if not ok:
        gdi32.BitBlt(mem_dc, 0, 0, width, height, hwnd_dc, 0, 0, 0x00CC0020)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem_dc, bmp, 0, height, buf, ctypes.byref(bmi), 0)
    image = Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1).copy()

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)
    return image


def plate(size: tuple[int, int]) -> Image.Image:
    width, height = size
    img = Image.new("RGBA", size)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(PLATE_TOP[i] + (PLATE_BOTTOM[i] - PLATE_TOP[i]) * t) for i in range(4))
        ImageDraw.Draw(img).line([(0, y), (width, y)], fill=color)
    return img


def round_corners(im: Image.Image, radius: int) -> Image.Image:
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), radius=radius, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0))
    out.putalpha(mask)
    return out


def crop_window(src: Image.Image, ltrb: tuple[int, int, int, int] = CROP_LTRB) -> Image.Image:
    left, top, right, bottom = ltrb
    box = (left, top, src.width - right, src.height - bottom)
    if box[2] <= box[0] or box[3] <= box[1]:
        return src
    return src.crop(box)


def composite(src: Image.Image, plate_size: tuple[int, int]) -> Image.Image:
    src = crop_window(src)
    canvas = plate(plate_size)
    pad = 48
    max_w = plate_size[0] - pad * 2
    max_h = plate_size[1] - pad * 2
    scale = min(max_w / src.width, max_h / src.height, 1.0)
    resized = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.Resampling.LANCZOS)
    window = round_corners(resized, radius=max(12, int(18 * scale)))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    x = (plate_size[0] - window.width) // 2
    y = (plate_size[1] - window.height) // 2
    shadow.paste((0, 0, 0, 70), (x + 8, y + 14, x + window.width + 8, y + window.height + 14))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.paste(window, (x, y), window)
    return canvas


def check_png(path: Path, require: list[str], extra_forbid: list[str]) -> None:
    try:
        import pytesseract  # type: ignore
    except ImportError:
        print(f"WARN: pytesseract not installed; {path} needs a visual fail-check", file=sys.stderr)
        return
    text = pytesseract.image_to_string(Image.open(path))
    lowered = text.replace("\u00b7", " / ")
    for snippet in (*FORBIDDEN_SNIPPETS, *extra_forbid):
        if snippet and snippet in lowered:
            raise SystemExit(f"{path}: forbidden snippet {snippet!r} in OCR text")
    for snippet in require:
        if snippet and snippet not in lowered:
            raise SystemExit(f"{path}: missing required snippet {snippet!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture-window")
    cap.add_argument("--title", required=True)
    cap.add_argument("--out", required=True, type=Path)
    cap.add_argument("--bitblt", action="store_true", help="Copy screen pixels (needed for Windows Terminal)")

    comp = sub.add_parser("composite")
    comp.add_argument("--src", required=True, type=Path)
    comp.add_argument("--out", required=True, type=Path)
    comp.add_argument("--kind", choices=("gui", "cli"), required=True)

    chk = sub.add_parser("check")
    chk.add_argument("--png", required=True, type=Path)
    chk.add_argument("--require", action="append", default=[])
    chk.add_argument("--forbid", action="append", default=[])

    sub.add_parser("list-windows")

    args = parser.parse_args()
    if args.cmd == "list-windows":
        for hwnd, title in _enum_windows():
            if title.strip():
                print(f"{hwnd}\t{title}")
        return
    if args.cmd == "capture-window":
        hwnd = find_hwnd(args.title)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        capture_hwnd(hwnd, bitblt=args.bitblt).save(args.out)
        print(args.out)
        return
    if args.cmd == "composite":
        size = PLATE_GUI if args.kind == "gui" else PLATE_CLI
        args.out.parent.mkdir(parents=True, exist_ok=True)
        composite(Image.open(args.src), size).save(args.out)
        print(args.out)
        return
    check_png(args.png, args.require, args.forbid)


if __name__ == "__main__":
    main()
