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

# SIG # Begin signature block
# MII6oQYJKoZIhvcNAQcCoII6kjCCOo4CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCDLL7qPCrcMIIuR
# mtyKvMuxoXecQ7HcZ16xeqL4Q9y6KKCCIsYwggXMMIIDtKADAgECAhBUmNLR1FsZ
# lUgTecgRwIeZMA0GCSqGSIb3DQEBDAUAMHcxCzAJBgNVBAYTAlVTMR4wHAYDVQQK
# ExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xSDBGBgNVBAMTP01pY3Jvc29mdCBJZGVu
# dGl0eSBWZXJpZmljYXRpb24gUm9vdCBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkgMjAy
# MDAeFw0yMDA0MTYxODM2MTZaFw00NTA0MTYxODQ0NDBaMHcxCzAJBgNVBAYTAlVT
# MR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xSDBGBgNVBAMTP01pY3Jv
# c29mdCBJZGVudGl0eSBWZXJpZmljYXRpb24gUm9vdCBDZXJ0aWZpY2F0ZSBBdXRo
# b3JpdHkgMjAyMDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBALORKgeD
# Bmf9np3gx8C3pOZCBH8Ppttf+9Va10Wg+3cL8IDzpm1aTXlT2KCGhFdFIMeiVPvH
# or+Kx24186IVxC9O40qFlkkN/76Z2BT2vCcH7kKbK/ULkgbk/WkTZaiRcvKYhOuD
# PQ7k13ESSCHLDe32R0m3m/nJxxe2hE//uKya13NnSYXjhr03QNAlhtTetcJtYmrV
# qXi8LW9J+eVsFBT9FMfTZRY33stuvF4pjf1imxUs1gXmuYkyM6Nix9fWUmcIxC70
# ViueC4fM7Ke0pqrrBc0ZV6U6CwQnHJFnni1iLS8evtrAIMsEGcoz+4m+mOJyoHI1
# vnnhnINv5G0Xb5DzPQCGdTiO0OBJmrvb0/gwytVXiGhNctO/bX9x2P29Da6SZEi3
# W295JrXNm5UhhNHvDzI9e1eM80UHTHzgXhgONXaLbZ7LNnSrBfjgc10yVpRnlyUK
# xjU9lJfnwUSLgP3B+PR0GeUw9gb7IVc+BhyLaxWGJ0l7gpPKWeh1R+g/OPTHU3mg
# trTiXFHvvV84wRPmeAyVWi7FQFkozA8kwOy6CXcjmTimthzax7ogttc32H83rwjj
# O3HbbnMbfZlysOSGM1l0tRYAe1BtxoYT2v3EOYI9JACaYNq6lMAFUSw0rFCZE4e7
# swWAsk0wAly4JoNdtGNz764jlU9gKL431VulAgMBAAGjVDBSMA4GA1UdDwEB/wQE
# AwIBhjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBTIftJqhSobyhmYBAcnz1AQ
# T2ioojAQBgkrBgEEAYI3FQEEAwIBADANBgkqhkiG9w0BAQwFAAOCAgEAr2rd5hnn
# LZRDGU7L6VCVZKUDkQKL4jaAOxWiUsIWGbZqWl10QzD0m/9gdAmxIR6QFm3FJI9c
# Zohj9E/MffISTEAQiwGf2qnIrvKVG8+dBetJPnSgaFvlVixlHIJ+U9pW2UYXeZJF
# xBA2CFIpF8svpvJ+1Gkkih6PsHMNzBxKq7Kq7aeRYwFkIqgyuH4yKLNncy2RtNwx
# AQv3Rwqm8ddK7VZgxCwIo3tAsLx0J1KH1r6I3TeKiW5niB31yV2g/rarOoDXGpc8
# FzYiQR6sTdWD5jw4vU8w6VSp07YEwzJ2YbuwGMUrGLPAgNW3lbBeUU0i/OxYqujY
# lLSlLu2S3ucYfCFX3VVj979tzR/SpncocMfiWzpbCNJbTsgAlrPhgzavhgplXHT2
# 6ux6anSg8Evu75SjrFDyh+3XOjCDyft9V77l4/hByuVkrrOj7FjshZrM77nq81YY
# uVxzmq/FdxeDWds3GhhyVKVB0rYjdaNDmuV3fJZ5t0GNv+zcgKCf0Xd1WF81E+Al
# GmcLfc4l+gcK5GEh2NQc5QfGNpn0ltDGFf5Ozdeui53bFv0ExpK91IjmqaOqu/dk
# ODtfzAzQNb50GQOmxapMomE2gj4d8yu8l13bS3g7LfU772Aj6PXsCyM2la+YZr9T
# 03u4aUoqlmZpxJTG9F9urJh4iIAGXKKy7aIwggb3MIIE36ADAgECAhMzAAh1y68I
# Xf3T2Wo1AAAACHXLMA0GCSqGSIb3DQEBDAUAMFoxCzAJBgNVBAYTAlVTMR4wHAYD
# VQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xKzApBgNVBAMTIk1pY3Jvc29mdCBJ
# RCBWZXJpZmllZCBDUyBBT0MgQ0EgMDIwHhcNMjYwMzI1MDUwODQ0WhcNMjYwMzI4
# MDUwODQ0WjB1MQswCQYDVQQGEwJBVDETMBEGA1UECBMKU3RlaWVybWFyazEZMBcG
# A1UEBxMQQmFkIEdsZWljaGVuYmVyZzEaMBgGA1UEChMRR2VyaGFyZCBQZXRlcm1l
# aXIxGjAYBgNVBAMTEUdlcmhhcmQgUGV0ZXJtZWlyMIIBojANBgkqhkiG9w0BAQEF
# AAOCAY8AMIIBigKCAYEAj02SMf7i7ccCx/I81rDpMVumAbARdZ6T6yrhIQgECvTJ
# AFtL4AlXzIvS8UIkpA36fkxq3xeVbacEWjeqn8BN67ZA/K5IM+ohOqECc5WxYO7G
# 8Myztj1/TzUmbkhj3vKbQi2i41sFKkTUfkFia7xc+jLO8/W/hmJlN2JYHbXCsvNE
# LUBj3Vy2WH8/rkOnSlaPC79EDEsabeOGi83XXfRAmipy/PCaKYEEayIL2E8DQl46
# d8Hr6+Vfh4SqBiGQuyWEeRD1XRMuIciQbS5amjJF9W9ETdypZZ28pe67sivMsrZS
# ecRcCJ9/XM0sp3qiaa+XH+N5fDwzE7Q/TIgf9Byxzl9T08pYI7OLvmGTvahb85Mj
# FIR0sRFwhy2BFm/bFNraVbnMhF/x6SIlfmeZ/PknR+rBEcX83pB4X0Gg02FQcwCA
# UsdTsw/HhfTsJpbW95ho3G+KtTIQSoGzEEJ/E5mIdY6gMAX02EDH+CocpkNWPuHU
# VIQ3cyNUrtLjkrKbtenxAgMBAAGjggIZMIICFTAMBgNVHRMBAf8EAjAAMA4GA1Ud
# DwEB/wQEAwIHgDA8BgNVHSUENTAzBgorBgEEAYI3YQEABggrBgEFBQcDAwYbKwYB
# BAGCN2Hw79cLgo7y7RCCv/euTYLhx7VLMB0GA1UdDgQWBBREkJrhtibSOSn2Ykia
# SskWAOMZDDAfBgNVHSMEGDAWgBQkRZmhd5AqfMPKg7BuZBaEKvgsZzBnBgNVHR8E
# YDBeMFygWqBYhlZodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9N
# aWNyb3NvZnQlMjBJRCUyMFZlcmlmaWVkJTIwQ1MlMjBBT0MlMjBDQSUyMDAyLmNy
# bDCBpQYIKwYBBQUHAQEEgZgwgZUwZAYIKwYBBQUHMAKGWGh0dHA6Ly93d3cubWlj
# cm9zb2Z0LmNvbS9wa2lvcHMvY2VydHMvTWljcm9zb2Z0JTIwSUQlMjBWZXJpZmll
# ZCUyMENTJTIwQU9DJTIwQ0ElMjAwMi5jcnQwLQYIKwYBBQUHMAGGIWh0dHA6Ly9v
# bmVvY3NwLm1pY3Jvc29mdC5jb20vb2NzcDBmBgNVHSAEXzBdMFEGDCsGAQQBgjdM
# g30BATBBMD8GCCsGAQUFBwIBFjNodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtp
# b3BzL0RvY3MvUmVwb3NpdG9yeS5odG0wCAYGZ4EMAQQBMA0GCSqGSIb3DQEBDAUA
# A4ICAQBUralTW2eSOPGtygeXa4vpR+5KHpFTJvDdz+8CFVHXjTB41xoto4c/hXpF
# 3D7YDw/5hf9ODb0Na6A30Afb4ykdcUWEVTK7ASbwZo73NLKIWAzka52FXeJfW1uK
# /mHsiKuv4tPwy8w23gCn2mBSZGHtATnn/96agGWhqhDwFrw5267wGQ4o1YVf+9YO
# Kg+AvoFXhrSaptVhTMUg4I/gdFdZjxe6lBKc5C8mUzAgNEYsnQOz2To1XsVjRp3x
# xtf/JkdNcY1Tc33Aw2zEOe2yRVYLQSGGqEBCT/aIk1OzxSowQxt7lM6SS78mMVJ/
# N2qG6gClcBYHo0iI+RD4TgSJ7jBhLT68t6g3npCOjGWz+3/VQcNzGLqvL7gRV8RC
# 74Hy86nx8iupNH7pWVIdKxneHxvDh7dg3cdTmvs6vW5Eo0w1IcvTzcAk9g+5Ku8o
# jEbXLLIkL+zwMuUyZhkNZiWQS5+2yeLJPqObxn+1d9IZKRmLOtwhxQQtXqJors5J
# Sou0Wy57mYdVl5j49/qd/I/en8acQonVnxVue4o7dNUGlrKKQoUaD4imwlUhuiw4
# WzB9cMMF+Q5vTkefIVYsPUXIatQN8Zn7igm43NNh0fyVLnZ5AkuYeyUIfeG91q1E
# rxaT1mMgCht8QmOy2c+VRp0+K4tS8QLyqjZhFbIb+ZkbgyuQcTCCBvcwggTfoAMC
# AQICEzMACHXLrwhd/dPZajUAAAAIdcswDQYJKoZIhvcNAQEMBQAwWjELMAkGA1UE
# BhMCVVMxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjErMCkGA1UEAxMi
# TWljcm9zb2Z0IElEIFZlcmlmaWVkIENTIEFPQyBDQSAwMjAeFw0yNjAzMjUwNTA4
# NDRaFw0yNjAzMjgwNTA4NDRaMHUxCzAJBgNVBAYTAkFUMRMwEQYDVQQIEwpTdGVp
# ZXJtYXJrMRkwFwYDVQQHExBCYWQgR2xlaWNoZW5iZXJnMRowGAYDVQQKExFHZXJo
# YXJkIFBldGVybWVpcjEaMBgGA1UEAxMRR2VyaGFyZCBQZXRlcm1laXIwggGiMA0G
# CSqGSIb3DQEBAQUAA4IBjwAwggGKAoIBgQCPTZIx/uLtxwLH8jzWsOkxW6YBsBF1
# npPrKuEhCAQK9MkAW0vgCVfMi9LxQiSkDfp+TGrfF5VtpwRaN6qfwE3rtkD8rkgz
# 6iE6oQJzlbFg7sbwzLO2PX9PNSZuSGPe8ptCLaLjWwUqRNR+QWJrvFz6Ms7z9b+G
# YmU3YlgdtcKy80QtQGPdXLZYfz+uQ6dKVo8Lv0QMSxpt44aLzddd9ECaKnL88Jop
# gQRrIgvYTwNCXjp3wevr5V+HhKoGIZC7JYR5EPVdEy4hyJBtLlqaMkX1b0RN3Kll
# nbyl7ruyK8yytlJ5xFwIn39czSyneqJpr5cf43l8PDMTtD9MiB/0HLHOX1PTylgj
# s4u+YZO9qFvzkyMUhHSxEXCHLYEWb9sU2tpVucyEX/HpIiV+Z5n8+SdH6sERxfze
# kHhfQaDTYVBzAIBSx1OzD8eF9Owmltb3mGjcb4q1MhBKgbMQQn8TmYh1jqAwBfTY
# QMf4KhymQ1Y+4dRUhDdzI1Su0uOSspu16fECAwEAAaOCAhkwggIVMAwGA1UdEwEB
# /wQCMAAwDgYDVR0PAQH/BAQDAgeAMDwGA1UdJQQ1MDMGCisGAQQBgjdhAQAGCCsG
# AQUFBwMDBhsrBgEEAYI3YfDv1wuCjvLtEIK/965NguHHtUswHQYDVR0OBBYEFESQ
# muG2JtI5KfZiSJpKyRYA4xkMMB8GA1UdIwQYMBaAFCRFmaF3kCp8w8qDsG5kFoQq
# +CxnMGcGA1UdHwRgMF4wXKBaoFiGVmh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9w
# a2lvcHMvY3JsL01pY3Jvc29mdCUyMElEJTIwVmVyaWZpZWQlMjBDUyUyMEFPQyUy
# MENBJTIwMDIuY3JsMIGlBggrBgEFBQcBAQSBmDCBlTBkBggrBgEFBQcwAoZYaHR0
# cDovL3d3dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBJ
# RCUyMFZlcmlmaWVkJTIwQ1MlMjBBT0MlMjBDQSUyMDAyLmNydDAtBggrBgEFBQcw
# AYYhaHR0cDovL29uZW9jc3AubWljcm9zb2Z0LmNvbS9vY3NwMGYGA1UdIARfMF0w
# UQYMKwYBBAGCN0yDfQEBMEEwPwYIKwYBBQUHAgEWM2h0dHA6Ly93d3cubWljcm9z
# b2Z0LmNvbS9wa2lvcHMvRG9jcy9SZXBvc2l0b3J5Lmh0bTAIBgZngQwBBAEwDQYJ
# KoZIhvcNAQEMBQADggIBAFStqVNbZ5I48a3KB5dri+lH7koekVMm8N3P7wIVUdeN
# MHjXGi2jhz+FekXcPtgPD/mF/04NvQ1roDfQB9vjKR1xRYRVMrsBJvBmjvc0sohY
# DORrnYVd4l9bW4r+YeyIq6/i0/DLzDbeAKfaYFJkYe0BOef/3pqAZaGqEPAWvDnb
# rvAZDijVhV/71g4qD4C+gVeGtJqm1WFMxSDgj+B0V1mPF7qUEpzkLyZTMCA0Riyd
# A7PZOjVexWNGnfHG1/8mR01xjVNzfcDDbMQ57bJFVgtBIYaoQEJP9oiTU7PFKjBD
# G3uUzpJLvyYxUn83aobqAKVwFgejSIj5EPhOBInuMGEtPry3qDeekI6MZbP7f9VB
# w3MYuq8vuBFXxELvgfLzqfHyK6k0fulZUh0rGd4fG8OHt2Ddx1Oa+zq9bkSjTDUh
# y9PNwCT2D7kq7yiMRtcssiQv7PAy5TJmGQ1mJZBLn7bJ4sk+o5vGf7V30hkpGYs6
# 3CHFBC1eomiuzklKi7RbLnuZh1WXmPj3+p38j96fxpxCidWfFW57ijt01QaWsopC
# hRoPiKbCVSG6LDhbMH1wwwX5Dm9OR58hViw9Rchq1A3xmfuKCbjc02HR/JUudnkC
# S5h7JQh94b3WrUSvFpPWYyAKG3xCY7LZz5VGnT4ri1LxAvKqNmEVshv5mRuDK5Bx
# MIIHWjCCBUKgAwIBAgITMwAAAASWUEvS2+7LiAAAAAAABDANBgkqhkiG9w0BAQwF
# ADBjMQswCQYDVQQGEwJVUzEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9u
# MTQwMgYDVQQDEytNaWNyb3NvZnQgSUQgVmVyaWZpZWQgQ29kZSBTaWduaW5nIFBD
# QSAyMDIxMB4XDTIxMDQxMzE3MzE1MloXDTI2MDQxMzE3MzE1MlowWjELMAkGA1UE
# BhMCVVMxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjErMCkGA1UEAxMi
# TWljcm9zb2Z0IElEIFZlcmlmaWVkIENTIEFPQyBDQSAwMjCCAiIwDQYJKoZIhvcN
# AQEBBQADggIPADCCAgoCggIBAOHOoOgzomOmwDsAj2wZUBdrY6N3JFGbmm+WaKzJ
# 0aeKzpsGQ4k2yKcxZGf5PJOIrwSVdcOf2/6MpCPnlwKmmsTHcgDtDKHZxFuyJ30P
# q05MpBMx8UWwjYOig7E52HP2HS+yCIiZYvJOdbqWhyy+wmJvWDXNEhWL5WhY9jtB
# 4zvcvzUZnFjY2pmTpUY8VtnFoFLFHWs0h4EQnpPO1dmzP9e2/qPFl1FvdSKYIEWr
# JomeuVhBR1ym8oZti24QSumVpkKBXhPhlqylghiv6v+EYk2jDYR11r1r/v/yOfFL
# TsVYtw2itX0OmC8iCBh8w+AprXKxor8bqav3K6x7pxjQe//0JrpdmT/R3DpmP2qb
# YFJ8E/ttIPwN+4g37rlcOskti6NP5Kf42/ifLxOBTKiIsMRgci+PNjzFQQt6nfzW
# xUGvDJo+np7FPhxKr/Wq/gG3CsLpm2aiSSpkKxmkjXVn5NjaHYHFjpqu48oW8cGT
# o5y49P28J7FDXDQHtPb/qoqM8kEHrPAN1Fz3EUG/BvnNMmjtiAon1kyu8krslCfP
# JNZrTdtgjX7W44rYgHmn6GfVZoZ+UX2/kvyuWq1b03C7pLeT3Uw0MZeeexCBOgPu
# lxQaXbIzs5C83RIexC5PD1TzI0HzwoCrSfOHNe33dgvfqcRdZREFBV2P2LQi/jZr
# PXFlAgMBAAGjggIOMIICCjAOBgNVHQ8BAf8EBAMCAYYwEAYJKwYBBAGCNxUBBAMC
# AQAwHQYDVR0OBBYEFCRFmaF3kCp8w8qDsG5kFoQq+CxnMFQGA1UdIARNMEswSQYE
# VR0gADBBMD8GCCsGAQUFBwIBFjNodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtp
# b3BzL0RvY3MvUmVwb3NpdG9yeS5odG0wGQYJKwYBBAGCNxQCBAweCgBTAHUAYgBD
# AEEwEgYDVR0TAQH/BAgwBgEB/wIBADAfBgNVHSMEGDAWgBTZQSmwDw9jbO9p1/XN
# KZ6kSGow5jBwBgNVHR8EaTBnMGWgY6Bhhl9odHRwOi8vd3d3Lm1pY3Jvc29mdC5j
# b20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBJRCUyMFZlcmlmaWVkJTIwQ29kZSUy
# MFNpZ25pbmclMjBQQ0ElMjAyMDIxLmNybDCBrgYIKwYBBQUHAQEEgaEwgZ4wbQYI
# KwYBBQUHMAKGYWh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2lvcHMvY2VydHMv
# TWljcm9zb2Z0JTIwSUQlMjBWZXJpZmllZCUyMENvZGUlMjBTaWduaW5nJTIwUENB
# JTIwMjAyMS5jcnQwLQYIKwYBBQUHMAGGIWh0dHA6Ly9vbmVvY3NwLm1pY3Jvc29m
# dC5jb20vb2NzcDANBgkqhkiG9w0BAQwFAAOCAgEAZy04XZWzDSKJHSrc0mvIqPqR
# DveQnN1TsmP4ULCCHHTMpNoSTsy7fzNVl30MhJQ5P0Lci81+t03Tm+SfpzvLdKc8
# 8Iu2WLzIjairwEDudLDDiZ9094Qj6acTTYaBhVcc9lMokOG9rzq3LCyvUzhBV1m1
# DCTm0fTzNMGbAASIbuJOlVS8RA3tBknkF/2ROzx304OOC7n7eCCqmJp79QrqLKd4
# JRWLFXoC5zFmVGfFLTvRfEAogKLiWIS+TpQpLIA2/b3vx0ISxZ3pX4OnULmyBbKg
# fSJQqJ2CiWfx2jGb2LQO8vRDkSuHMZb03rQlwB2soklx9LnhP0/dsFRtHLL+VXVM
# o+sla5ttr5SmAJFyDSrwzgfPrOIfk4EoZVGtgArthVp+yc5U0m6ZNCBPERLmJpLs
# hPwU5JPd1gzMez8C55+CfuX5L2440NPDnsH6TIYfErj3UCqpmeNCOFtlMiSjDE23
# rdeiRYpkqgwoYJwgepcJaXtIH26Pe1O6a6W3wSqegdpNn+2Pk41q0GDfjnXDzskA
# HcRhjwcCUmiRt6IXZJQsYACeWpwsXmJe0o0ORLmumrYyHlYTdCnzyxT6WM+QkFPi
# Qth+/ceHfzumDhUfWmHuePwhrqe3UVCHy0r9f49Az3OhJX92MlsZaFo/MnmN5B62
# RWgJUTMIQF8j0N6xF/cwggeeMIIFhqADAgECAhMzAAAAB4ejNKN7pY4cAAAAAAAH
# MA0GCSqGSIb3DQEBDAUAMHcxCzAJBgNVBAYTAlVTMR4wHAYDVQQKExVNaWNyb3Nv
# ZnQgQ29ycG9yYXRpb24xSDBGBgNVBAMTP01pY3Jvc29mdCBJZGVudGl0eSBWZXJp
# ZmljYXRpb24gUm9vdCBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkgMjAyMDAeFw0yMTA0
# MDEyMDA1MjBaFw0zNjA0MDEyMDE1MjBaMGMxCzAJBgNVBAYTAlVTMR4wHAYDVQQK
# ExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xNDAyBgNVBAMTK01pY3Jvc29mdCBJRCBW
# ZXJpZmllZCBDb2RlIFNpZ25pbmcgUENBIDIwMjEwggIiMA0GCSqGSIb3DQEBAQUA
# A4ICDwAwggIKAoICAQCy8MCvGYgo4t1UekxJbGkIVQm0Uv96SvjB6yUo92cXdylN
# 65Xy96q2YpWCiTas7QPTkGnK9QMKDXB2ygS27EAIQZyAd+M8X+dmw6SDtzSZXyGk
# xP8a8Hi6EO9Zcwh5A+wOALNQbNO+iLvpgOnEM7GGB/wm5dYnMEOguua1OFfTUITV
# MIK8faxkP/4fPdEPCXYyy8NJ1fmskNhW5HduNqPZB/NkWbB9xxMqowAeWvPgHtpz
# yD3PLGVOmRO4ka0WcsEZqyg6efk3JiV/TEX39uNVGjgbODZhzspHvKFNU2K5MYfm
# Hh4H1qObU4JKEjKGsqqA6RziybPqhvE74fEp4n1tiY9/ootdU0vPxRp4BGjQFq28
# nzawuvaCqUUF2PWxh+o5/TRCb/cHhcYU8Mr8fTiS15kRmwFFzdVPZ3+JV3s5MulI
# f3II5FXeghlAH9CvicPhhP+VaSFW3Da/azROdEm5sv+EUwhBrzqtxoYyE2wmuHKw
# s00x4GGIx7NTWznOm6x/niqVi7a/mxnnMvQq8EMse0vwX2CfqM7Le/smbRtsEeOt
# bnJBbtLfoAsC3TdAOnBbUkbUfG78VRclsE7YDDBUbgWt75lDk53yi7C3n0WkHFU4
# EZ83i83abd9nHWCqfnYa9qIHPqjOiuAgSOf4+FRcguEBXlD9mAInS7b6V0UaNwID
# AQABo4ICNTCCAjEwDgYDVR0PAQH/BAQDAgGGMBAGCSsGAQQBgjcVAQQDAgEAMB0G
# A1UdDgQWBBTZQSmwDw9jbO9p1/XNKZ6kSGow5jBUBgNVHSAETTBLMEkGBFUdIAAw
# QTA/BggrBgEFBQcCARYzaHR0cDovL3d3dy5taWNyb3NvZnQuY29tL3BraW9wcy9E
# b2NzL1JlcG9zaXRvcnkuaHRtMBkGCSsGAQQBgjcUAgQMHgoAUwB1AGIAQwBBMA8G
# A1UdEwEB/wQFMAMBAf8wHwYDVR0jBBgwFoAUyH7SaoUqG8oZmAQHJ89QEE9oqKIw
# gYQGA1UdHwR9MHsweaB3oHWGc2h0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2lv
# cHMvY3JsL01pY3Jvc29mdCUyMElkZW50aXR5JTIwVmVyaWZpY2F0aW9uJTIwUm9v
# dCUyMENlcnRpZmljYXRlJTIwQXV0aG9yaXR5JTIwMjAyMC5jcmwwgcMGCCsGAQUF
# BwEBBIG2MIGzMIGBBggrBgEFBQcwAoZ1aHR0cDovL3d3dy5taWNyb3NvZnQuY29t
# L3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBJZGVudGl0eSUyMFZlcmlmaWNhdGlv
# biUyMFJvb3QlMjBDZXJ0aWZpY2F0ZSUyMEF1dGhvcml0eSUyMDIwMjAuY3J0MC0G
# CCsGAQUFBzABhiFodHRwOi8vb25lb2NzcC5taWNyb3NvZnQuY29tL29jc3AwDQYJ
# KoZIhvcNAQEMBQADggIBAH8lKp7+1Kvq3WYK21cjTLpebJDjW4ZbOX3HD5ZiG84v
# jsFXT0OB+eb+1TiJ55ns0BHluC6itMI2vnwc5wDW1ywdCq3TAmx0KWy7xulAP179
# qX6VSBNQkRXzReFyjvF2BGt6FvKFR/imR4CEESMAG8hSkPYso+GjlngM8JPn/ROU
# rTaeU/BRu/1RFESFVgK2wMz7fU4VTd8NXwGZBe/mFPZG6tWwkdmA/jLbp0kNUX7e
# lxu2+HtHo0QO5gdiKF+YTYd1BGrmNG8sTURvn09jAhIUJfYNotn7OlThtfQjXqe0
# qrimgY4Vpoq2MgDW9ESUi1o4pzC1zTgIGtdJ/IvY6nqa80jFOTg5qzAiRNdsUvzV
# koYP7bi4wLCj+ks2GftUct+fGUxXMdBUv5sdr0qFPLPB0b8vq516slCfRwaktAxK
# 1S40MCvFbbAXXpAZnU20FaAoDwqq/jwzwd8Wo2J83r7O3onQbDO9TyDStgaBNlHz
# MMQgl95nHBYMelLEHkUnVVVTUsgC0Huj09duNfMaJ9ogxhPNThgq3i8w3DAGZ61A
# MeF0C1M+mU5eucj1Ijod5O2MMPeJQ3/vKBtqGZg4eTtUHt/BPjN74SsJsyHqAdXV
# S5c+ItyKWg3Eforhox9k3WgtWTpgV4gkSiS4+A09roSdOI4vrRw+p+fL4WrxSK5n
# MYIXMTCCFy0CAQEwcTBaMQswCQYDVQQGEwJVUzEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSswKQYDVQQDEyJNaWNyb3NvZnQgSUQgVmVyaWZpZWQgQ1Mg
# QU9DIENBIDAyAhMzAAh1y68IXf3T2Wo1AAAACHXLMA0GCWCGSAFlAwQCAQUAoF4w
# EAYKKwYBBAGCNwIBDDECMAAwGQYJKoZIhvcNAQkDMQwGCisGAQQBgjcCAQQwLwYJ
# KoZIhvcNAQkEMSIEIOtYnOkSzMIEXY9kbpCHDLwgzit8fF6p9CT75ClB3Q9RMA0G
# CSqGSIb3DQEBAQUABIIBgHe1CJKQQt9FZcWf/VaT2+ZLZDPk/Q4sEaUGKldElzns
# HOLEzgnbtk2eC3kyrl6qq8L6x1hXp0yVEcfs6iOGWaPPPTYWIc1aMTMgAUFvt1tl
# /E3LPZxFobuj1uIJtXpInzdaE0C/vMGHngeQUtVh+l6eiM77Y1dMiuyACBWoSj1P
# Sp8WaU8FdkNL1q3MS8npj2z1JKoIcfR0INLRF+QIUSAmhPzw2hbSBP+nW6bzHdLM
# fUXNHMU90KLUxcZts2h110h3+BOJJpKwJYY5G4SNvl9+GV/gXCKRCvhOvipZpogN
# QLdZ65XZJibGFKSocA/CO2uzHkH/c4v7aDtyYubEUaBxI1kOOTeiDp177jIV/L+h
# B5y6KsWbwY51AMfGZf82kOfLGxXWlpm8eDjtkQmyhIViqKDzBH00oGJ4bMJniUtn
# Xi2sgvr4nOuk992wQD8tKi8NaikTfPtNnDiRc/MDqkj3JJDPUD+C3WMi8PGz3bZj
# WW7HmfL7AqQluLFsmnZKdKGCFLEwghStBgorBgEEAYI3AwMBMYIUnTCCFJkGCSqG
# SIb3DQEHAqCCFIowghSGAgEDMQ8wDQYJYIZIAWUDBAIBBQAwggFpBgsqhkiG9w0B
# CRABBKCCAVgEggFUMIIBUAIBAQYKKwYBBAGEWQoDATAxMA0GCWCGSAFlAwQCAQUA
# BCATlm1lSK3H6x4PmIy4BpZe0o5zKsyJQZMXLscBTla0mgIGab1LMT0GGBIyMDI2
# MDMyNTEzMTI0OC40MVowBIACAfSggemkgeYwgeMxCzAJBgNVBAYTAlVTMRMwEQYD
# VQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNy
# b3NvZnQgQ29ycG9yYXRpb24xLTArBgNVBAsTJE1pY3Jvc29mdCBJcmVsYW5kIE9w
# ZXJhdGlvbnMgTGltaXRlZDEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjdCMUEt
# MDVFMC1EOTQ3MTUwMwYDVQQDEyxNaWNyb3NvZnQgUHVibGljIFJTQSBUaW1lIFN0
# YW1waW5nIEF1dGhvcml0eaCCDykwggeCMIIFaqADAgECAhMzAAAABeXPD/9mLsmH
# AAAAAAAFMA0GCSqGSIb3DQEBDAUAMHcxCzAJBgNVBAYTAlVTMR4wHAYDVQQKExVN
# aWNyb3NvZnQgQ29ycG9yYXRpb24xSDBGBgNVBAMTP01pY3Jvc29mdCBJZGVudGl0
# eSBWZXJpZmljYXRpb24gUm9vdCBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkgMjAyMDAe
# Fw0yMDExMTkyMDMyMzFaFw0zNTExMTkyMDQyMzFaMGExCzAJBgNVBAYTAlVTMR4w
# HAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xMjAwBgNVBAMTKU1pY3Jvc29m
# dCBQdWJsaWMgUlNBIFRpbWVzdGFtcGluZyBDQSAyMDIwMIICIjANBgkqhkiG9w0B
# AQEFAAOCAg8AMIICCgKCAgEAnnznUmP94MWfBX1jtQYioxwe1+eXM9ETBb1lRkd3
# kcFdcG9/sqtDlwxKoVIcaqDb+omFio5DHC4RBcbyQHjXCwMk/l3TOYtgoBjxnG/e
# ViS4sOx8y4gSq8Zg49REAf5huXhIkQRKe3Qxs8Sgp02KHAznEa/Ssah8nWo5hJM1
# xznkRsFPu6rfDHeZeG1Wa1wISvlkpOQooTULFm809Z0ZYlQ8Lp7i5F9YciFlyAKw
# n6yjN/kR4fkquUWfGmMopNq/B8U/pdoZkZZQbxNlqJOiBGgCWpx69uKqKhTPVi3g
# VErnc/qi+dR8A2MiAz0kN0nh7SqINGbmw5OIRC0EsZ31WF3Uxp3GgZwetEKxLms7
# 3KG/Z+MkeuaVDQQheangOEMGJ4pQZH55ngI0Tdy1bi69INBV5Kn2HVJo9XxRYR/J
# PGAaM6xGl57Ei95HUw9NV/uC3yFjrhc087qLJQawSC3xzY/EXzsT4I7sDbxOmM2r
# l4uKK6eEpurRduOQ2hTkmG1hSuWYBunFGNv21Kt4N20AKmbeuSnGnsBCd2cjRKG7
# 9+TX+sTehawOoxfeOO/jR7wo3liwkGdzPJYHgnJ54UxbckF914AqHOiEV7xTnD1a
# 69w/UTxwjEugpIPMIIE67SFZ2PMo27xjlLAHWW3l1CEAFjLNHd3EQ79PUr8FUXet
# Xr0CAwEAAaOCAhswggIXMA4GA1UdDwEB/wQEAwIBhjAQBgkrBgEEAYI3FQEEAwIB
# ADAdBgNVHQ4EFgQUa2koOjUvSGNAz3vYr0npPtk92yEwVAYDVR0gBE0wSzBJBgRV
# HSAAMEEwPwYIKwYBBQUHAgEWM2h0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2lv
# cHMvRG9jcy9SZXBvc2l0b3J5Lmh0bTATBgNVHSUEDDAKBggrBgEFBQcDCDAZBgkr
# BgEEAYI3FAIEDB4KAFMAdQBiAEMAQTAPBgNVHRMBAf8EBTADAQH/MB8GA1UdIwQY
# MBaAFMh+0mqFKhvKGZgEByfPUBBPaKiiMIGEBgNVHR8EfTB7MHmgd6B1hnNodHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBJZGVu
# dGl0eSUyMFZlcmlmaWNhdGlvbiUyMFJvb3QlMjBDZXJ0aWZpY2F0ZSUyMEF1dGhv
# cml0eSUyMDIwMjAuY3JsMIGUBggrBgEFBQcBAQSBhzCBhDCBgQYIKwYBBQUHMAKG
# dWh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2lvcHMvY2VydHMvTWljcm9zb2Z0
# JTIwSWRlbnRpdHklMjBWZXJpZmljYXRpb24lMjBSb290JTIwQ2VydGlmaWNhdGUl
# MjBBdXRob3JpdHklMjAyMDIwLmNydDANBgkqhkiG9w0BAQwFAAOCAgEAX4h2x35t
# tVoVdedMeGj6TuHYRJklFaW4sTQ5r+k77iB79cSLNe+GzRjv4pVjJviceW6AF6yc
# WoEYR0LYhaa0ozJLU5Yi+LCmcrdovkl53DNt4EXs87KDogYb9eGEndSpZ5ZM74LN
# vVzY0/nPISHz0Xva71QjD4h+8z2XMOZzY7YQ0Psw+etyNZ1CesufU211rLslLKsO
# 8F2aBs2cIo1k+aHOhrw9xw6JCWONNboZ497mwYW5EfN0W3zL5s3ad4Xtm7yFM7Uj
# rhc0aqy3xL7D5FR2J7x9cLWMq7eb0oYioXhqV2tgFqbKHeDick+P8tHYIFovIP7Y
# G4ZkJWag1H91KlELGWi3SLv10o4KGag42pswjybTi4toQcC/irAodDW8HNtX+cbz
# 0sMptFJK+KObAnDFHEsukxD+7jFfEV9Hh/+CSxKRsmnuiovCWIOb+H7DRon9Tlxy
# diFhvu88o0w35JkNbJxTk4MhF/KgaXn0GxdH8elEa2Imq45gaa8D+mTm8LWVydt4
# ytxYP/bqjN49D9NZ81coE6aQWm88TwIf4R4YZbOpMKN0CyejaPNN41LGXHeCUMYm
# Bx3PkP8ADHD1J2Cr/6tjuOOCztfp+o9Nc+ZoIAkpUcA/X2gSMkgHAPUvIdtoSAHE
# UKiBhI6JQivRepyvWcl+JYbYbBh7pmgAXVswggefMIIFh6ADAgECAhMzAAAAWXza
# cemNXvXAAAAAAABZMA0GCSqGSIb3DQEBDAUAMGExCzAJBgNVBAYTAlVTMR4wHAYD
# VQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xMjAwBgNVBAMTKU1pY3Jvc29mdCBQ
# dWJsaWMgUlNBIFRpbWVzdGFtcGluZyBDQSAyMDIwMB4XDTI2MDEwODE4NTkwMVoX
# DTI3MDEwNzE4NTkwMVowgeMxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xLTArBgNVBAsTJE1pY3Jvc29mdCBJcmVsYW5kIE9wZXJhdGlvbnMgTGlt
# aXRlZDEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjdCMUEtMDVFMC1EOTQ3MTUw
# MwYDVQQDEyxNaWNyb3NvZnQgUHVibGljIFJTQSBUaW1lIFN0YW1waW5nIEF1dGhv
# cml0eTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAKYu5/40eEX+hT+5
# jFa146bid3dA4LnXYntvkP3CGw4LGARFhnvLMSJ/VtsubzDaeFnm7yb2KSM70WmH
# QprdCVqpvUH7l0uB4jNw7urLoAR9kKHLE0VlMlDStDSxUBI3qwsdrjvdmvV0k+9/
# njuDEiSlzJTf7Dowd1K3bO4beRyaFhR+Y8tymECOqlOAffYrG2wZdVM51+QSBSe+
# PEykr8C6OnnqSipuF8fZvCb6/huk0Zm6ZwsaixSHIAT2IEGvS7c63Im8jV3a8R0K
# 6i2yiw0NNlnTSpwy/Zfv7iwsLBwhfbjBTn+XOl6mPzDXQQ3V+SRP9xXbGKOsBTxz
# Gid7aKAHw3o4Ahl9UGWLH9kNP3VUokE6JYkjlfpuUGZ6gQyqDewfxD4VoYIlopt4
# HZ0xQvqajuJx+cr8LR/IZ56gLLmwyMzde5+vtjBoilry/gSZwVGwgkvkIgpKPBQH
# GsSB0y3szr7Y7wEb6v0yZal1XUvWnnz3inTaSWsCFrLPVwVmXy3ncY5/d25VpOkh
# t+m697GWNbvsNOhAOHRaftE9j/hhkoM6RsyJfBLnhqMcA/wcavf5oj5NeyRQdGZe
# LKcls9csKS3sBUzPidxx2iiNH9CPaDq/bLJEOXasYohXMnRinu+fUk81s8VO7DQS
# F6ffn5oqSHoV8lf1Ax6u+kdShb8BAgMBAAGjggHLMIIBxzAdBgNVHQ4EFgQUj5bn
# C18D0vlnSRhCOiODGGuXNnYwHwYDVR0jBBgwFoAUa2koOjUvSGNAz3vYr0npPtk9
# 2yEwbAYDVR0fBGUwYzBhoF+gXYZbaHR0cDovL3d3dy5taWNyb3NvZnQuY29tL3Br
# aW9wcy9jcmwvTWljcm9zb2Z0JTIwUHVibGljJTIwUlNBJTIwVGltZXN0YW1waW5n
# JTIwQ0ElMjAyMDIwLmNybDB5BggrBgEFBQcBAQRtMGswaQYIKwYBBQUHMAKGXWh0
# dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2lvcHMvY2VydHMvTWljcm9zb2Z0JTIw
# UHVibGljJTIwUlNBJTIwVGltZXN0YW1waW5nJTIwQ0ElMjAyMDIwLmNydDAMBgNV
# HRMBAf8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIH
# gDBmBgNVHSAEXzBdMFEGDCsGAQQBgjdMg30BATBBMD8GCCsGAQUFBwIBFjNodHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL0RvY3MvUmVwb3NpdG9yeS5odG0w
# CAYGZ4EMAQQCMA0GCSqGSIb3DQEBDAUAA4ICAQBEMhzC/ZcjpG/zURE7z2Yp5vrU
# xUjsE5Xa3t/2RGvESwvbmsk3bLHhSFAajgo2XQ8xoGDP3sUhKCLPeICSbkVv6V8s
# Sp8fJ8Jos6yrawf2YVis8tcV+OO7U9S6JGPQzpmPncfzQc4ne1fqZ4+HiKabIDEo
# FdddQT2Egkk9fzxCY/EZ52avJ27dSfrI/IDmyn9V10O3iQpg2F+C9vNTrk7nVgoD
# oHa9+Q3pYr0IHGnSmt5irgGT436zo5WnXP8FxMhswH1aiyiSZiVzhor10C9C52cP
# 3C8/PEoMKUXstLjoPO0TMkeW/1Fr186KXD45QRgBo0xImgtWTdzWFnlD+p7+iDBI
# uSrNcRXDRYuq/aYZaDhWSI0SYdPIWVh5XvXuWA31a8oQ0SO+oPa3Nk80k0864wii
# yJ1KsbSnaaefg9vspeghrpY8ljCwxfCUtx5HQRNgAJOI8IKACK4d014Mk0hlRO0l
# QVRHegqIg29K6Xqkc360W2ZJGUcstlKokkVj6KAHjGyrLRPzepYfiZUJq4gXyxbp
# vKb1XJ2FN2682aUoNXo9RyRK1ch0f66k6+yj88kzvuC7+vJWtNDs/UpIM6Hhm0kU
# 64JUJ7MMEQcAc7kpft7Gm7YeRK+oKgqUgYXCfmzbX8nJXJZnPa8ADWVsIqsuNAxC
# I0CZXkULofqo5Be6zzGCA9QwggPQAgEBMHgwYTELMAkGA1UEBhMCVVMxHjAcBgNV
# BAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEyMDAGA1UEAxMpTWljcm9zb2Z0IFB1
# YmxpYyBSU0EgVGltZXN0YW1waW5nIENBIDIwMjACEzMAAABZfNpx6Y1e9cAAAAAA
# AFkwDQYJYIZIAWUDBAIBBQCgggEtMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRAB
# BDAvBgkqhkiG9w0BCQQxIgQgc8qyrdSh7DFiBIZrecjptOb9buf5LZgG3g91BIp0
# vjIwgd0GCyqGSIb3DQEJEAIvMYHNMIHKMIHHMIGgBCDLRbqx24bpscXEJ+Hjj9xr
# cUVw7R8OyyMfSB2YGK3+vDB8MGWkYzBhMQswCQYDVQQGEwJVUzEeMBwGA1UEChMV
# TWljcm9zb2Z0IENvcnBvcmF0aW9uMTIwMAYDVQQDEylNaWNyb3NvZnQgUHVibGlj
# IFJTQSBUaW1lc3RhbXBpbmcgQ0EgMjAyMAITMwAAAFl82nHpjV71wAAAAAAAWTAi
# BCCbh7tkhUolB4Gw/lPVSNkzruwU7wt+ljCRPt6tTIjnXzANBgkqhkiG9w0BAQsF
# AASCAgBPqvchWkK0o6d0Rp2t2R5jwKOQ310N6C+WCcUApNr5d0jmlGpuBgw5QMZ0
# qE0T5l5TrGIn6F6yqQoXwQpqhttX5UWWxOT/lUjte63l5zckoHvhJgnLeQIGyix7
# +WMdUop6dgWgfZo4vSKSZTbsFn2caaZGGp/p9pDqllL4HyrLIUpCOGK/yVK0c06E
# c26rlLPpJ0QrwNreOHxLMyPDrEOuFAfNBdGOxc2aLMuRHC9DMfkZwrbdqaMN6xvQ
# jCIqXXWfRnoEsMwC05Kmuea6V3FzW++MBIfBuImHEYRVvvvbntE0VBdYbpOrmoI3
# XvPFs5xz8uowwPAacddDMouLHTH6jhn21vQtpYB7E+F8hqz5ASAz7pWwwcDoUkY2
# EcyADHs0Xx7ilFbMxSxgv3xmTVasDFx0vLWyt2/3TZ3GqXXD2xLPVdG1/8f4XV3t
# FidsoebswZlM6cGn83xbjo7aDfkkHKT+ORX6gif/6pyqglTMYbvSipgW/3MCqJfK
# vJsxG2TJSOZb6EvqqcHDDbMyRAKCwThipYKmJTRp9bFwKqWuOlu6yH7Qdm+zq0QC
# fkPUKpO8zVOrEVPJT3qp7L42U496tcMRYoFYkrcyf53DFszE5WpWmFWrNMIgyVOi
# Tr0luJM6+eREGfiCECvT0cBCXLv0g/rW51LJkYeG9aZ/R6YB5Q==
# SIG # End signature block
