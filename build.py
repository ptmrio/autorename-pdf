"""
Build script for AutoRename-PDF.

Pipeline:
  1. Build CLI EXE        (PyInstaller --onefile)
  2. Sign CLI EXE          (Azure Trusted Signing)
  3. Build Tauri GUI       (pnpm tauri build --no-bundle)
  4. Create staging dir    (portable layout)
  5. Create portable ZIP   (flat ZIP from staging)
  6. Cleanup

Output (in Releases/):
  - AutoRename-PDF-Portable-{version}.zip   (primary distribution)

Usage:
  python build.py                  Build everything, sign all
  python build.py --nosign         Build everything, skip signing
  python build.py --cli-only       Build CLI EXE only (skip GUI + packaging)
"""

import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
GUI_DIR = ROOT / "gui"
GUI_TAURI_DIR = GUI_DIR / "src-tauri"
GUI_ICON = GUI_TAURI_DIR / "icons" / "icon.ico"

PYTHON_SCRIPT = "autorename-pdf.py"
OUTPUT_EXE = "autorename-pdf.exe"
BRIDGE_SCRIPT = "_paddleocr_bridge.py"

SIDECAR_SOURCE = "autorename-pdf-cli-x86_64-pc-windows-msvc.exe"
SIDECAR_RUNTIME = "autorename-pdf-cli.exe"
TAURI_GUI_EXE = "autorename-pdf-gui.exe"

DIST_DIR = ROOT / "dist"
STAGING_DIR = DIST_DIR / "staging"
BUILD_DIR = ROOT / "build"
RELEASES_DIR = ROOT / "Releases"

BUNDLE_FILES = [
    "setup.ps1",
    "config.yaml.example",
    "harmonized-company-names.yaml.example",
    ".env.example",
]

# Azure Trusted Signing
SIGNING_METADATA = ROOT / "metadata.json"
TIMESTAMP_SERVER = "http://timestamp.acs.microsoft.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_step_num = 0


def step(msg):
    global _step_num
    _step_num += 1
    print(f"\n{'='*60}")
    print(f"  Step {_step_num}: {msg}")
    print(f"{'='*60}\n")


def run(command, cwd=None, shell=False):
    """Run a command, printing output on failure."""
    proc = subprocess.run(
        command, capture_output=True, text=True, cwd=cwd, shell=shell,
    )
    if proc.returncode != 0:
        print(f"FAILED: {command}")
        if proc.stdout.strip():
            print(proc.stdout[-2000:])
        if proc.stderr.strip():
            print(proc.stderr[-2000:])
        sys.exit(1)
    return proc.stdout


def get_version():
    """Read version from gui/package.json (single source of truth)."""
    pkg = json.loads((GUI_DIR / "package.json").read_text(encoding="utf-8"))
    return pkg["version"]


def check_prerequisites(flags):
    """Verify all required tools are available before starting."""
    errors = []

    try:
        run([sys.executable, "-m", "PyInstaller", "--version"])
    except SystemExit:
        errors.append("PyInstaller not installed. Run: pip install pyinstaller")

    if not GUI_ICON.is_file():
        errors.append(f"Icon not found: {GUI_ICON}")

    for f in BUNDLE_FILES:
        if not (ROOT / f).is_file():
            errors.append(f"Required file missing: {f}")

    if not flags["cli_only"]:
        if shutil.which("pnpm") is None:
            errors.append("pnpm not found. Install via: npm install -g pnpm")
        if not GUI_DIR.is_dir():
            errors.append(f"GUI directory not found: {GUI_DIR}")

    if errors:
        print("Prerequisite check failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("All prerequisites OK.")


# ---------------------------------------------------------------------------
# Build steps
# ---------------------------------------------------------------------------

def build_cli_exe():
    """Build the standalone CLI EXE with PyInstaller."""
    step("Build CLI EXE (PyInstaller)")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--collect-all", "instructor",
        "--collect-all", "pypdfium2",
        "--collect-all", "pypdfium2_raw",
        "--collect-data", "dateparser",
        "--hidden-import", "anthropic",
        f"--add-data={BRIDGE_SCRIPT};.",
        f"--icon={GUI_ICON}",
        f"--name={OUTPUT_EXE}",
        PYTHON_SCRIPT,
    ]

    run(cmd)

    exe_path = DIST_DIR / OUTPUT_EXE
    if not exe_path.is_file():
        print(f"Build succeeded but EXE not found at {exe_path}")
        sys.exit(1)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"CLI EXE built: {exe_path} ({size_mb:.1f} MB)")
    return exe_path


def sign_file(file_path):
    """Sign a file using Azure Trusted Signing."""
    print(f"  Signing: {file_path}")

    dlib = os.environ.get("AZURE_CODE_SIGNING_DLIB") or str(
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft" / "MicrosoftArtifactSigningClientTools"
        / "Azure.CodeSigning.Dlib.dll"
    )

    if not os.path.isfile(dlib):
        print(f"  ERROR: Azure signing DLib not found: {dlib}")
        print("  Install MicrosoftArtifactSigningClientTools or set AZURE_CODE_SIGNING_DLIB.")
        sys.exit(1)

    if not SIGNING_METADATA.is_file():
        print(f"  ERROR: Signing metadata not found: {SIGNING_METADATA}")
        sys.exit(1)

    run(
        f'signtool sign /v /dlib "{dlib}" /dmdf "{SIGNING_METADATA}" '
        f'/fd sha256 /tr {TIMESTAMP_SERVER} /td sha256 "{file_path}"',
        shell=True,
    )


def sign_cli_artifacts(exe_path, nosign):
    """Sign the CLI EXE and setup.ps1."""
    step("Sign CLI artifacts")

    if nosign:
        print("Skipping (--nosign)")
        return

    sign_file(exe_path)
    sign_file(ROOT / "setup.ps1")
    print("Signing complete.")


def build_tauri_gui(nosign):
    """Compile the Tauri GUI app (no bundle — packaged separately as ZIP)."""
    step("Build Tauri GUI (compile only)")

    # Install frontend deps if needed
    if not (GUI_DIR / "node_modules").is_dir():
        print("Installing frontend dependencies...")
        run(["pnpm", "install", "--frozen-lockfile"], cwd=str(GUI_DIR), shell=True)

    # Stage the CLI EXE as Tauri sidecar (needed for compilation)
    # Tauri expects the source file with target-triple suffix in src-tauri/
    sidecar_dst = GUI_TAURI_DIR / SIDECAR_SOURCE
    cli_src = DIST_DIR / OUTPUT_EXE
    print(f"Staging sidecar: {cli_src} -> {sidecar_dst}")
    shutil.copy2(str(cli_src), str(sidecar_dst))

    # Compile Tauri without creating any installer bundle
    tauri_cmd = ["pnpm", "tauri", "build", "--no-bundle"]
    if nosign:
        tauri_cmd.append("--no-sign")

    print(f"Running: {' '.join(tauri_cmd)}")
    run(tauri_cmd, cwd=str(GUI_DIR), shell=True)

    # Verify the GUI EXE was produced
    gui_exe = GUI_TAURI_DIR / "target" / "release" / TAURI_GUI_EXE
    if not gui_exe.is_file():
        print(f"Tauri build succeeded but GUI EXE not found: {gui_exe}")
        sys.exit(1)

    size_mb = gui_exe.stat().st_size / (1024 * 1024)
    print(f"Tauri GUI built: {gui_exe} ({size_mb:.1f} MB)")
    return gui_exe


def create_staging(cli_exe, gui_exe):
    """Create the portable app layout for ZIP packaging."""
    step("Create staging directory")

    if STAGING_DIR.exists():
        shutil.rmtree(str(STAGING_DIR))
    STAGING_DIR.mkdir(parents=True)

    # GUI EXE
    dst_gui = STAGING_DIR / TAURI_GUI_EXE
    print(f"  + {TAURI_GUI_EXE} (Tauri GUI)")
    shutil.copy2(str(gui_exe), str(dst_gui))

    # CLI EXE — Tauri strips the target-triple at build time, so the runtime
    # binary must be the plain name. Also used by setup.ps1 for context menu.
    dst_sidecar = STAGING_DIR / SIDECAR_RUNTIME
    print(f"  + {SIDECAR_RUNTIME} (CLI sidecar + context menu)")
    shutil.copy2(str(cli_exe), str(dst_sidecar))

    # Bundle files
    for f in BUNDLE_FILES:
        src = ROOT / f
        shutil.copy2(str(src), str(STAGING_DIR / f))
        print(f"  + {f}")

    print(f"\nStaging complete: {STAGING_DIR}")


def create_portable_zip():
    """Create portable ZIP from staging directory."""
    step("Create portable ZIP")

    if RELEASES_DIR.is_dir():
        shutil.rmtree(str(RELEASES_DIR), ignore_errors=True)
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)

    version = get_version()
    zip_name = f"AutoRename-PDF-Portable-{version}.zip"
    zip_path = RELEASES_DIR / zip_name

    import zipfile
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for item in STAGING_DIR.iterdir():
            zf.write(str(item), item.name)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Portable ZIP: {zip_path} ({size_mb:.1f} MB)")


def cleanup():
    """Remove build artifacts (keep Releases/)."""
    step("Cleanup")

    for d in [BUILD_DIR, DIST_DIR]:
        if d.is_dir():
            shutil.rmtree(str(d), ignore_errors=True)
            print(f"  Removed {d}/")

    spec_file = ROOT / f"{OUTPUT_EXE}.spec"
    if spec_file.is_file():
        spec_file.unlink()
        print(f"  Removed {spec_file.name}")

    print("Done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def smoke_test(exe_path):
    """Run post-build smoke tests. Returns True if all pass."""
    step("Post-build smoke tests")

    tests = [
        (["--version"], 0, "prints version"),
        (["--help"], 0, "prints help"),
        (["config", "validate", "--config", "nonexistent.yaml", "-o", "json"], 3, "config error as JSON"),
    ]

    # Add dry-run test if fixture exists
    fixture = ROOT / "tests" / "fixtures" / "text_invoice_acme.pdf"
    if fixture.is_file():
        tests.append((["rename", "--dry-run", "-o", "json", str(fixture)], None, "dry-run single PDF"))

    all_passed = True
    for args, expected_code, desc in tests:
        proc = subprocess.run(
            [str(exe_path)] + args,
            capture_output=True, text=True, timeout=30,
        )
        if expected_code is not None and proc.returncode != expected_code:
            print(f"  FAIL: {desc} — expected exit {expected_code}, got {proc.returncode}")
            if proc.stderr.strip():
                print(f"    stderr: {proc.stderr[:500]}")
            all_passed = False
        else:
            # For JSON output tests, verify parseable JSON
            if "-o" in args and "json" in args and proc.stdout.strip():
                try:
                    json.loads(proc.stdout)
                except json.JSONDecodeError:
                    print(f"  FAIL: {desc} — invalid JSON output")
                    all_passed = False
                    continue
            print(f"  PASS: {desc}")

    if not all_passed:
        print("\nSmoke tests FAILED")
        sys.exit(1)

    print("\nAll smoke tests passed")
    return True


def main():
    flags = {
        "cli_only": "--cli-only" in sys.argv,
        "nosign": "--nosign" in sys.argv or os.environ.get("npm_config_nosign") == "true",
        "smoke_test": "--smoke-test" in sys.argv,
    }

    version = get_version()
    mode = "CLI only" if flags["cli_only"] else "CLI + GUI"
    sign_label = "unsigned" if flags["nosign"] else "signed"
    print(f"AutoRename-PDF Build v{version} ({mode}, {sign_label})")

    check_prerequisites(flags)

    cli_exe = build_cli_exe()
    if flags["smoke_test"]:
        smoke_test(cli_exe)
    sign_cli_artifacts(cli_exe, flags["nosign"])

    # Always stage sidecar so `pnpm tauri dev` works after --cli-only builds
    sidecar_dst = GUI_TAURI_DIR / SIDECAR_SOURCE
    shutil.copy2(str(cli_exe), str(sidecar_dst))
    print(f"Sidecar staged: {sidecar_dst}")

    if not flags["cli_only"]:
        gui_exe = build_tauri_gui(flags["nosign"])
        create_staging(cli_exe, gui_exe)
        create_portable_zip()

    cleanup()
    print(f"\nBuild complete. Output in Releases/")


if __name__ == "__main__":
    main()
