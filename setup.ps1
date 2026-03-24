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
        Start-Process powershell.exe -Verb RunAs -WorkingDirectory $PSScriptRoot -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$PSCommandPath`""
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

# Function to find the CLI executable (returns path or $null)
# Searches multiple locations to support portable (Velopack) and standalone layouts.
function Find-AutoRenamePDF {
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

# Function to add registry entries for AutoRenamePDF
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

# Function to remove registry entries
function Remove-RegistryEntries {
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Recurse -ErrorAction SilentlyContinue
}

# Function to install PaddleOCR in an isolated environment
function Install-PaddleOCR {
    $installDir = Join-Path $env:LOCALAPPDATA "autorename-pdf"
    $venvDir = Join-Path $installDir "paddleocr-venv"
    $pythonZipUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
    $pythonDir = Join-Path $installDir "python-embed"
    $pythonExe = Join-Path $pythonDir "python.exe"

    Write-Host "`nInstalling PaddleOCR for offline OCR of scanned documents..." -ForegroundColor Yellow
    Write-Host "This will download ~500MB of files." -ForegroundColor Yellow

    # Create install directory
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null

    # Step 1: Download embedded Python
    if (-not (Test-Path $pythonExe)) {
        Write-Host "[1/4] Downloading Python 3.12 embeddable package..." -ForegroundColor Yellow
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
        Write-Host "[2/4] Installing pip..." -ForegroundColor Yellow
        $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
        $getPipPath = Join-Path $installDir "get-pip.py"
        Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
        & $pythonExe $getPipPath --no-warn-script-location
        Remove-Item $getPipPath
    }
    else {
        Write-Host "[1/4] Python 3.12 already installed, skipping." -ForegroundColor Gray
        Write-Host "[2/4] pip already installed, skipping." -ForegroundColor Gray
    }

    # Step 2: Create venv-like structure using virtualenv
    if (-not (Test-Path (Join-Path $venvDir "Scripts\python.exe"))) {
        Write-Host "[3/4] Creating PaddleOCR virtual environment..." -ForegroundColor Yellow
        & $pythonExe -m pip install virtualenv --no-warn-script-location
        & $pythonExe -m virtualenv $venvDir
    }
    else {
        Write-Host "[3/4] Virtual environment already exists, skipping." -ForegroundColor Gray
    }

    $venvPython = Join-Path $venvDir "Scripts\python.exe"

    # Step 3: Install PaddleOCR and dependencies + pre-download models
    Write-Host "[4/4] Installing PaddlePaddle and PaddleOCR (this may take a few minutes)..." -ForegroundColor Yellow
    & $venvPython -m pip install paddlepaddle==3.3.0 paddleocr --no-warn-script-location

    Write-Host "       Downloading OCR models (first-time setup)..." -ForegroundColor Yellow
    & $venvPython -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en', show_log=False)"

    Write-Host ""
    Write-Host "PaddleOCR installed successfully!" -ForegroundColor Green
    Write-Host "Location: $venvDir" -ForegroundColor Gray
}

# Main routine
$exePath = Find-AutoRenamePDF
$hasExe = $null -ne $exePath

$choice = Read-Host "Do you want to (I)nstall or (U)ninstall AutoRenamePDF? (I/U)"

if ($choice -eq "I" -or $choice -eq "i") {
    Write-Host ""
    Write-Host "Starting installation..." -ForegroundColor Green

    # Copy config example if config doesn't exist
    $configPath = Join-Path $PSScriptRoot "config.yaml"
    $configExample = Join-Path $PSScriptRoot "config.yaml.example"
    if (-not (Test-Path $configPath) -and (Test-Path $configExample)) {
        Copy-Item $configExample $configPath
        Write-Host "[OK] Created config.yaml from example." -ForegroundColor Green
    }
    else {
        Write-Host "[OK] config.yaml already exists." -ForegroundColor Gray
    }

    # Context menu (requires EXE)
    if ($hasExe) {
        Add-RegistryEntries -exePath $exePath
        Write-Host "[OK] Context menu entries registered." -ForegroundColor Green
    }
    else {
        Write-Host "[--] autorename-pdf-cli.exe not found - skipping context menu registration." -ForegroundColor Yellow
        Write-Host "     You can run the tool via Python: python autorename-pdf.py file.pdf" -ForegroundColor Gray
    }

    # Optional: Install PaddleOCR
    Write-Host ""
    $ocrChoice = Read-Host "Install PaddleOCR for offline OCR of scanned documents? (~500MB) [y/N]"
    if ($ocrChoice -eq "y" -or $ocrChoice -eq "Y") {
        Install-PaddleOCR
    }
    else {
        Write-Host "[--] PaddleOCR skipped. You can install it later by running this script again." -ForegroundColor Gray
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Installation completed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Edit config.yaml with your AI provider API key" -ForegroundColor Yellow
    if ($hasExe) {
        Write-Host "  2. Right-click any PDF or folder to auto-rename" -ForegroundColor Yellow
        Write-Host "     On Windows 11: use 'Show more options' (Shift+F10) in the context menu." -ForegroundColor Gray
    }
    else {
        Write-Host "  2. Run: python autorename-pdf.py file.pdf" -ForegroundColor Yellow
    }
}
elseif ($choice -eq "U" -or $choice -eq "u") {
    Write-Host ""
    Write-Host "Starting uninstallation..." -ForegroundColor Green

    # Remove registry entries
    Remove-RegistryEntries
    Write-Host "[OK] Context menu entries removed." -ForegroundColor Green

    # Optionally remove PaddleOCR
    $venvDir = Join-Path $env:LOCALAPPDATA "autorename-pdf"
    if (Test-Path $venvDir) {
        $removeOcr = Read-Host "Remove PaddleOCR installation at $venvDir? [y/N]"
        if ($removeOcr -eq "y" -or $removeOcr -eq "Y") {
            Remove-Item -Path $venvDir -Recurse -Force
            Write-Host "[OK] PaddleOCR removed." -ForegroundColor Green
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Uninstallation completed." -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}
else {
    Write-Host "Invalid choice. Run the script again and choose I to install or U to uninstall." -ForegroundColor Red
}

# Keep window open so the user can read the output
Write-Host ""
Read-Host "Press Enter to close"
