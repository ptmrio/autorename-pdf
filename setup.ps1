# AutoRenamePDF Installation/Uninstallation Script
#
# How to run:
#   Right-click this file > "Run with PowerShell"
#   - OR -
#   Open PowerShell and run:  .\setup.ps1
#   The script will auto-elevate to Administrator via UAC prompt.
#
# On Windows 11, context menu entries appear under "Show more options" (Shift+F10).

# Auto-elevate to administrator if not already running as admin
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "AutoRenamePDF Setup requires Administrator privileges." -ForegroundColor Yellow
    Write-Host "Requesting elevation via UAC..." -ForegroundColor Gray
    try {
        Start-Process powershell.exe -Verb RunAs -WorkingDirectory $PSScriptRoot -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    }
    catch {
        Write-Host "UAC prompt was declined or elevation failed." -ForegroundColor Red
        Write-Host "Please right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
        Read-Host "Press Enter to close"
    }
    exit
}

# Set window title for the elevated session
$Host.UI.RawUI.WindowTitle = "AutoRenamePDF Setup"

# Enforce TLS 1.2+ for web downloads (PS 5.1 defaults to TLS 1.0)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Banner
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AutoRenamePDF Setup" -ForegroundColor Cyan
Write-Host "  Running as Administrator" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─── Helper Functions ──────────────────────────────────────────────────────────

function Find-AutoRenamePDF {
    <# Find the CLI executable. Searches multiple locations for portable/standalone layouts. #>
    $candidates = @(
        (Join-Path $PSScriptRoot "autorename-pdf-cli.exe"),
        (Join-Path $PSScriptRoot "autorename-pdf.exe")
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}


function Add-RegistryEntries {
    param($exePath)

    # For PDF files
    New-Item -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Force | Out-Null
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Name "(Default)" -Value "Auto Rename PDF"
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Name "Icon" -Value "shell32.dll,71"
    New-Item -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF\command" -Force | Out-Null
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF\command" -Name "(Default)" -Value "cmd /c `"`"$exePath`" `"%1`" & pause`""

    # For Folders
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Force | Out-Null
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Name "(Default)" -Value "Auto Rename PDFs in Folder"
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Name "Icon" -Value "shell32.dll,71"
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs\command" -Force | Out-Null
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs\command" -Name "(Default)" -Value "cmd /c `"`"$exePath`" `"%1`" & pause`""

    # For Directory Background
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Force | Out-Null
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Name "(Default)" -Value "Auto Rename PDFs in This Folder"
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Name "Icon" -Value "shell32.dll,71"
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs\command" -Force | Out-Null
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs\command" -Name "(Default)" -Value "cmd /c `"`"$exePath`" `"%V`" & pause`""
}


function Remove-RegistryEntries {
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Recurse -ErrorAction SilentlyContinue
}


function Install-PaddlePaddleGPU {
    <# Install PaddlePaddle GPU edition. Returns $true on success, $false on failure. #>
    param([string]$VenvPython)

    # Remove CPU version first (different package name — both can coexist but shouldn't)
    Write-Host "       Removing CPU-only PaddlePaddle (if present)..." -ForegroundColor Gray
    & $VenvPython -m pip uninstall paddlepaddle -y 2>$null | Out-Host

    Write-Host "       Downloading PaddlePaddle GPU from paddlepaddle.org.cn..." -ForegroundColor Yellow
    Write-Host "       This server is located in China and may be slow. Please be patient." -ForegroundColor Gray
    & $VenvPython -m pip install paddlepaddle-gpu==3.3.0 `
        -i "https://www.paddlepaddle.org.cn/packages/stable/cu118/" `
        --default-timeout=300 --no-warn-script-location 2>&1 | Out-Host
    $pipExitCode = $LASTEXITCODE

    if ($pipExitCode -ne 0) {
        Write-Host "       GPU package download failed." -ForegroundColor Red
        return $false
    }

    # Verify CUDA compilation
    Write-Host "       Verifying GPU support..." -ForegroundColor Gray
    $cudaCheck = & $VenvPython -c "import paddle; print(paddle.device.is_compiled_with_cuda())" 2>$null
    if ($cudaCheck -eq "True") {
        return $true
    }
    else {
        Write-Host "       GPU verification failed (CUDA not detected)." -ForegroundColor Red
        return $false
    }
}


function Install-PaddleOCR {
    <# Install PaddleOCR in an isolated Python environment. #>
    param([bool]$UseGPU = $false)

    $installDir = Join-Path $env:LOCALAPPDATA "autorename-pdf"
    $venvDir = Join-Path $installDir "paddleocr-venv"
    $pythonZipUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
    $pythonDir = Join-Path $installDir "python-embed"
    $pythonExe = Join-Path $pythonDir "python.exe"

    $totalSteps = if ($UseGPU) { 5 } else { 4 }

    # Create install directory
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null

    # Step 1: Download embedded Python
    if (-not (Test-Path $pythonExe)) {
        Write-Host "  [1/$totalSteps] Downloading Python 3.12 embeddable package..." -ForegroundColor Yellow
        $zipPath = Join-Path $installDir "python-embed.zip"
        Invoke-WebRequest -Uri $pythonZipUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $pythonDir -Force
        Remove-Item $zipPath

        # Enable import site (required for pip)
        $pthFile = Get-ChildItem -Path $pythonDir -Filter "python*._pth" | Select-Object -First 1
        if ($pthFile) {
            $content = Get-Content $pthFile.FullName
            $content = $content -replace '#import site', 'import site'
            Set-Content $pthFile.FullName $content
        }

        # Install pip
        Write-Host "  [2/$totalSteps] Installing pip..." -ForegroundColor Yellow
        $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
        $getPipPath = Join-Path $installDir "get-pip.py"
        Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
        & $pythonExe $getPipPath --no-warn-script-location | Out-Host
        Remove-Item $getPipPath
    }
    else {
        Write-Host "  [1/$totalSteps] Python 3.12 already installed, skipping." -ForegroundColor Gray
        Write-Host "  [2/$totalSteps] pip already installed, skipping." -ForegroundColor Gray
    }

    # Step 3: Create virtual environment
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Host "  [3/$totalSteps] Creating PaddleOCR virtual environment..." -ForegroundColor Yellow
        & $pythonExe -m pip install virtualenv --no-warn-script-location | Out-Host
        & $pythonExe -m virtualenv $venvDir | Out-Host
    }
    else {
        Write-Host "  [3/$totalSteps] Virtual environment already exists, skipping." -ForegroundColor Gray
    }

    # Step 4: Install PaddlePaddle + PaddleOCR
    $gpuInstalled = $false
    if ($UseGPU) {
        Write-Host "  [4/$totalSteps] Installing PaddlePaddle GPU and PaddleOCR..." -ForegroundColor Yellow
        & $venvPython -m pip install paddleocr --no-warn-script-location | Out-Host
        $gpuInstalled = Install-PaddlePaddleGPU -VenvPython $venvPython

        if (-not $gpuInstalled) {
            Write-Host ""
            Write-Host "  GPU installation failed. Falling back to CPU mode." -ForegroundColor Yellow
            Write-Host "  This is fine — PaddleOCR works well on CPU, just slightly slower." -ForegroundColor Gray
            & $venvPython -m pip uninstall paddlepaddle-gpu -y 2>$null | Out-Host
            & $venvPython -m pip install paddlepaddle==3.3.0 --no-warn-script-location | Out-Host
        }
    }
    else {
        Write-Host "  [4/$totalSteps] Installing PaddlePaddle and PaddleOCR..." -ForegroundColor Yellow
        & $venvPython -m pip install paddlepaddle==3.3.0 paddleocr --no-warn-script-location | Out-Host
    }

    # Final step: Download OCR models
    Write-Host "  Downloading OCR models (first-time setup)..." -ForegroundColor Yellow
    & $venvPython -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en', show_log=False)" | Out-Host

    # Report result
    Write-Host ""
    $mode = if ($gpuInstalled) { "GPU" } else { "CPU" }
    Write-Host "  PaddleOCR installed successfully! ($mode)" -ForegroundColor Green
    Write-Host "  Location: $venvDir" -ForegroundColor Gray

    return $gpuInstalled
}


function Show-Summary {
    <# Display a clean summary of what was installed or removed. #>
    param(
        [string]$Action,
        [hashtable]$Results
    )

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    if ($Action -eq "install") {
        Write-Host "  Installation complete!" -ForegroundColor Green
    }
    else {
        Write-Host "  Uninstallation complete!" -ForegroundColor Green
    }
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""

    if ($Action -eq "install") {
        Write-Host "  What was installed:" -ForegroundColor White
        foreach ($key in @("config", "context_menu", "paddleocr")) {
            $entry = $Results[$key]
            if ($null -eq $entry) { continue }
            if ($entry.Status -eq "ok") {
                Write-Host "    [OK] $($entry.Label)" -ForegroundColor Green
            }
            elseif ($entry.Status -eq "skip") {
                Write-Host "    [--] $($entry.Label)" -ForegroundColor Gray
            }
        }
    }
    else {
        Write-Host "  What was removed:" -ForegroundColor White
        foreach ($key in @("context_menu", "paddleocr")) {
            $entry = $Results[$key]
            if ($null -eq $entry) { continue }
            if ($entry.Status -eq "ok") {
                Write-Host "    [OK] $($entry.Label)" -ForegroundColor Green
            }
            elseif ($entry.Status -eq "skip") {
                Write-Host "    [--] $($entry.Label)" -ForegroundColor Gray
            }
        }
    }
}


# ─── Main Routine ─────────────────────────────────────────────────────────────

$exePath = Find-AutoRenamePDF
$hasExe = $null -ne $exePath

$choice = Read-Host "Do you want to (I)nstall or (U)ninstall AutoRenamePDF? (I/U)"

if ($choice -eq "I" -or $choice -eq "i") {
    Write-Host ""
    Write-Host "Starting installation..." -ForegroundColor Green
    Write-Host ""

    $results = @{}

    # ── 1. Config file ────────────────────────────────────────────────────────
    $configPath = Join-Path $PSScriptRoot "config.yaml"
    $configExample = Join-Path $PSScriptRoot "config.yaml.example"
    if (-not (Test-Path $configPath) -and (Test-Path $configExample)) {
        Copy-Item $configExample $configPath
        $results["config"] = @{ Status = "ok"; Label = "config.yaml created from example" }
    }
    else {
        $results["config"] = @{ Status = "ok"; Label = "config.yaml (already exists)" }
    }
    Write-Host "  $($results['config'].Label)" -ForegroundColor Green

    # ── 2. Context menu (optional) ────────────────────────────────────────────
    Write-Host ""
    if ($hasExe) {
        Write-Host "--- Context Menu ---" -ForegroundColor Cyan
        Write-Host "  Adds right-click options for PDFs and folders in Windows Explorer." -ForegroundColor Gray
        Write-Host "  On Windows 11, these appear under 'Show more options' (Shift+F10)." -ForegroundColor Gray
        $menuChoice = Read-Host "  Install context menu entries? [y/N]"
        if ($menuChoice -eq "y" -or $menuChoice -eq "Y") {
            Add-RegistryEntries -exePath $exePath
            $results["context_menu"] = @{ Status = "ok"; Label = "Context menu entries registered" }
            Write-Host "  [OK] Context menu entries registered." -ForegroundColor Green
        }
        else {
            $results["context_menu"] = @{ Status = "skip"; Label = "Context menu (skipped)" }
            Write-Host "  [--] Skipped. You can add them later by running this script again." -ForegroundColor Gray
        }
    }
    else {
        $results["context_menu"] = @{ Status = "skip"; Label = "Context menu (no EXE found)" }
        Write-Host "  [--] autorename-pdf-cli.exe not found — context menu not available." -ForegroundColor Yellow
        Write-Host "       You can run the tool via: python autorename-pdf.py file.pdf" -ForegroundColor Gray
    }

    # ── 3. PaddleOCR (optional) ───────────────────────────────────────────────
    Write-Host ""
    Write-Host "--- PaddleOCR (Offline OCR) ---" -ForegroundColor Cyan
    Write-Host "  Enables text recognition for scanned/image-based PDFs." -ForegroundColor Gray
    Write-Host "  Downloads ~500 MB (Python runtime, PaddlePaddle, OCR models)." -ForegroundColor Gray
    $ocrChoice = Read-Host "  Install PaddleOCR? [y/N]"
    if ($ocrChoice -eq "y" -or $ocrChoice -eq "Y") {

        # ── 3a. GPU option (only if PaddleOCR chosen) ─────────────────────────
        $useGpu = $false
        Write-Host ""
        Write-Host "  --- GPU Acceleration ---" -ForegroundColor Cyan
        Write-Host "  PaddleOCR can use an NVIDIA GPU for faster text recognition." -ForegroundColor Gray
        Write-Host "  Requirements: NVIDIA GPU with CUDA support (driver 452.39+)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  Note: The GPU package (~500 MB) downloads from PaddlePaddle's" -ForegroundColor Gray
        Write-Host "  servers in China and may be slow depending on your location." -ForegroundColor Gray
        Write-Host "  If the download fails, CPU mode will be used instead." -ForegroundColor Gray
        $gpuChoice = Read-Host "  Install with GPU acceleration? [y/N]"
        if ($gpuChoice -eq "y" -or $gpuChoice -eq "Y") {
            $useGpu = $true
        }

        Write-Host ""
        $gpuInstalled = Install-PaddleOCR -UseGPU $useGpu
        $mode = if ($gpuInstalled) { "GPU" } else { "CPU" }
        $results["paddleocr"] = @{ Status = "ok"; Label = "PaddleOCR ($mode)" }
    }
    else {
        $results["paddleocr"] = @{ Status = "skip"; Label = "PaddleOCR (skipped)" }
        Write-Host "  [--] Skipped. You can install it later by running this script again." -ForegroundColor Gray
    }

    # ── Summary ───────────────────────────────────────────────────────────────
    Show-Summary -Action "install" -Results $results

    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Yellow
    Write-Host "    1. Edit config.yaml with your AI provider API key" -ForegroundColor White
    if ($hasExe -and $results["context_menu"].Status -eq "ok") {
        Write-Host "    2. Right-click any PDF or folder to auto-rename" -ForegroundColor White
    }
    else {
        Write-Host "    2. Run: python autorename-pdf.py <file.pdf>" -ForegroundColor White
    }
}
elseif ($choice -eq "U" -or $choice -eq "u") {
    Write-Host ""
    Write-Host "Starting uninstallation..." -ForegroundColor Green
    Write-Host ""

    $results = @{}

    # ── 1. Context menu ──────────────────────────────────────────────────────
    Write-Host "--- Context Menu ---" -ForegroundColor Cyan
    $menuChoice = Read-Host "  Remove context menu entries? [y/N]"
    if ($menuChoice -eq "y" -or $menuChoice -eq "Y") {
        Remove-RegistryEntries
        $results["context_menu"] = @{ Status = "ok"; Label = "Context menu entries removed" }
        Write-Host "  [OK] Context menu entries removed." -ForegroundColor Green
    }
    else {
        $results["context_menu"] = @{ Status = "skip"; Label = "Context menu (kept)" }
    }

    # ── 2. PaddleOCR ─────────────────────────────────────────────────────────
    $ocrDir = Join-Path $env:LOCALAPPDATA "autorename-pdf"
    if (Test-Path $ocrDir) {
        Write-Host ""
        Write-Host "--- PaddleOCR ---" -ForegroundColor Cyan
        Write-Host "  Location: $ocrDir" -ForegroundColor Gray
        $removeOcr = Read-Host "  Remove PaddleOCR installation? [y/N]"
        if ($removeOcr -eq "y" -or $removeOcr -eq "Y") {
            Remove-Item -Path $ocrDir -Recurse -Force
            $results["paddleocr"] = @{ Status = "ok"; Label = "PaddleOCR removed" }
            Write-Host "  [OK] PaddleOCR removed." -ForegroundColor Green
        }
        else {
            $results["paddleocr"] = @{ Status = "skip"; Label = "PaddleOCR (kept)" }
        }
    }

    Show-Summary -Action "uninstall" -Results $results
}
else {
    Write-Host "Invalid choice. Run the script again and choose I or U." -ForegroundColor Red
}

# Keep window open so the user can read the output, then close on Enter
Write-Host ""
Read-Host "Press Enter to close"
