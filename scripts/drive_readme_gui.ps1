# Drive the native AutoRename-PDF window for README capture.
# WebView2 does not expose HTML buttons to UIA — use the Python driver.
# Usage: powershell -File scripts/drive_readme_gui.ps1
$root = Split-Path -Parent $PSScriptRoot
& "$root\venv\Scripts\python.exe" "$root\scripts\drive_readme_gui.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
