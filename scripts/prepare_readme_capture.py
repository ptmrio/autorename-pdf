"""Prepare a throwaway capture config and fixture folder. Does not print secrets."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TAURI_CONFIG = ROOT / "gui" / "src-tauri" / "config.yaml"
BACKUP = ROOT / "gui" / "src-tauri" / "config.yaml.readme-shot.bak"
RESOURCE_BACKUP = ROOT / "gui" / "src-tauri" / "config.yaml.readme-shot.resource.bak"
RAW = ROOT / "screenshot" / "_raw"
FIXTURES = RAW / "fixtures"
VERSION_FILE = ROOT / "_version.py"


def project_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("VERSION"):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("VERSION missing")


def load_personal_config() -> dict:
    for path in (TAURI_CONFIG, ROOT / "config.yaml"):
        if path.is_file():
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if (data.get("ai") or {}).get("api_key"):
                return data
    raise SystemExit("no personal config.yaml with ai.api_key found")


def resource_config_paths() -> list[Path]:
    """`tauri dev` reads resourceDir()/config.yaml, not gui/src-tauri/config.yaml."""
    hits: list[Path] = []
    temp = Path(os.environ.get("TEMP", ""))
    if temp.is_dir():
        hits.extend(temp.glob("cursor-sandbox-cache/**/debug/config.yaml"))
    local_target = ROOT / "gui" / "src-tauri" / "target" / "debug" / "config.yaml"
    hits.append(local_target)
    # Dedup while keeping order
    seen: set[Path] = set()
    out: list[Path] = []
    for path in hits:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(path)
    return out


def write_capture_config() -> None:
    personal = load_personal_config()
    if TAURI_CONFIG.is_file() and not BACKUP.is_file():
        shutil.copy2(TAURI_CONFIG, BACKUP)
    capture = {
        "config_version": 2,
        "ai": {
            "provider": "openai",
            "model": "gpt-5.6-luna",
            "api_key": personal["ai"]["api_key"],
            "base_url": personal.get("ai", {}).get("base_url") or "",
            "temperature": 0.0,
            "max_retries": 2,
        },
        "pdf": {
            "max_pages": 3,
            "ocr": False,
            "vision": False,
            "text_quality_threshold": 0.3,
            "incoming_invoice": "AP",
            "outgoing_invoice": "AR",
        },
        "paddleocr": {
            "venv_path": "",
            "language": "en",
            "device": "auto",
        },
        "company": {
            "name": (personal.get("company") or {}).get("name") or "Petermeir Web Solutions",
        },
        "output": {"language": "English", "date_format": "%Y%m%d"},
        "profile": "business",
        "profiles": {},
        "prompt_extension": "",
    }
    TAURI_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with TAURI_CONFIG.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(capture, fh, default_flow_style=False, allow_unicode=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tests" / "fixtures" / "text_invoice_acme.pdf", FIXTURES / "invoice.pdf")
    shutil.copy2(ROOT / "tests" / "fixtures" / "text_outgoing_invoice_wayne.pdf", FIXTURES / "SCAN001.pdf")
    version = project_version()
    portable = RAW / f"AutoRename-PDF-Portable-{version}"
    portable.mkdir(parents=True, exist_ok=True)
    sidecar = ROOT / "gui" / "src-tauri" / "autorename-pdf-cli-x86_64-pc-windows-msvc.exe"
    if not sidecar.is_file():
        raise SystemExit("sidecar missing; run python build.py --cli-only --nosign")
    shutil.copy2(sidecar, portable / "autorename-pdf-cli.exe")
    shutil.copy2(TAURI_CONFIG, portable / "config.yaml")
    shutil.copy2(FIXTURES / "SCAN001.pdf", portable / "SCAN001.pdf")
    for resource in resource_config_paths():
        if resource.is_file() and not RESOURCE_BACKUP.is_file():
            shutil.copy2(resource, RESOURCE_BACKUP)
        if resource.parent.is_dir():
            shutil.copy2(TAURI_CONFIG, resource)
            print(f"resource_config={resource}")
    print("capture config written (key redacted)")
    print(f"fixtures={FIXTURES}")
    print(f"portable={portable}")


def restore() -> None:
    if BACKUP.is_file():
        shutil.move(str(BACKUP), TAURI_CONFIG)
        print("restored gui/src-tauri/config.yaml")
    else:
        print("no gui/src-tauri backup to restore")
    if RESOURCE_BACKUP.is_file():
        restored_any = False
        for resource in resource_config_paths():
            if resource.parent.is_dir():
                shutil.copy2(RESOURCE_BACKUP, resource)
                restored_any = True
                print(f"restored {resource}")
        RESOURCE_BACKUP.unlink()
        if not restored_any:
            print("resource backup kept nowhere (debug dir missing)")
    else:
        print("no resourceDir backup to restore")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore()
    else:
        write_capture_config()
