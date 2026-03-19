"""Bump version across all project files from a single command."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES = {
    "package_json": ROOT / "gui" / "package.json",
    "tauri_conf": ROOT / "gui" / "src-tauri" / "tauri.conf.json",
    "cargo_toml": ROOT / "gui" / "src-tauri" / "Cargo.toml",
    "version_py": ROOT / "_version.py",
}

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_current_version() -> str:
    """Read current version from _version.py."""
    text = FILES["version_py"].read_text(encoding="utf-8")
    m = re.search(r'VERSION\s*=\s*"([^"]+)"', text)
    if not m:
        sys.exit("Cannot read current version from _version.py")
    return m.group(1)


def bump(current: str, part: str) -> str:
    major, minor, patch = (int(x) for x in current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def update_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_cargo_toml(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    # Replace only the first version = "..." (under [package])
    text = re.sub(
        r'^(version\s*=\s*)"[^"]+"',
        rf'\g<1>"{version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    path.write_text(text, encoding="utf-8")


def update_version_py(path: Path, version: str) -> None:
    path.write_text(f'VERSION = "{version}"\n', encoding="utf-8")


def main() -> None:
    args = sys.argv[1:]
    do_commit = "--commit" in args
    args = [a for a in args if a != "--commit"]

    if not args:
        print("Usage: python bump-version.py <VERSION | --major | --minor | --patch> [--commit]")
        sys.exit(2)

    arg = args[0]
    current = read_current_version()

    if arg.startswith("--"):
        part = arg.lstrip("-")
        if part not in ("major", "minor", "patch"):
            sys.exit(f"Unknown flag: {arg}")
        version = bump(current, part)
    else:
        version = arg
        if not VERSION_RE.match(version):
            sys.exit(f"Invalid version format: {version} (expected X.Y.Z)")

    print(f"Bumping version: {current} -> {version}")

    for name, path in FILES.items():
        if not path.exists():
            print(f"  SKIP {path.relative_to(ROOT)} (not found)")
            continue
        if name == "version_py":
            update_version_py(path, version)
        elif name == "cargo_toml":
            update_cargo_toml(path, version)
        else:
            update_json(path, version)
        print(f"  OK   {path.relative_to(ROOT)}")

    if do_commit:
        rel_paths = [str(p.relative_to(ROOT)) for p in FILES.values() if p.exists()]
        subprocess.run(["git", "add"] + rel_paths, cwd=ROOT, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Bump version to {version}"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["git", "tag", f"v{version}"],
            cwd=ROOT,
            check=True,
        )
        print(f"  Committed and tagged v{version}")


if __name__ == "__main__":
    main()
