# AutoRenamePDF Installation/Uninstallation Script

# Check if running as administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "You do not have Administrator rights to run this script!`nPlease re-run this script as an Administrator!"
    Break
}

# Function to find the autorename-pdf.exe
function Find-AutoRenamePDF {
    $scriptPath = $PSScriptRoot
    $exePath = Join-Path $scriptPath "autorename-pdf.exe"
    if (Test-Path $exePath) {
        return $exePath
    }
    else {
        Write-Error "autorename-pdf.exe not found in the script directory. Please ensure it's in the same folder as this script."
        exit
    }
}

# Function to install Chocolatey
function Install-Chocolatey {
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
}

# Function to install a package using Chocolatey
function Install-ChocoPackage {
    param($packageName)
    choco install $packageName -y
}

# Function to read OCR_LANGUAGES from config.yaml file
function Get-OCRLanguages {
    $configPath = Join-Path $PSScriptRoot "config.yaml"
    if (Test-Path $configPath) {
        $configContent = Get-Content $configPath -Raw
        # Simple YAML parsing for ocr_languages field
        if ($configContent -match 'ocr_languages:\s*["\']?([^"\'\r\n]+)["\']?') {
            return $matches[1].Split(',') | ForEach-Object { $_.Trim() }
        }
    }
    return @("eng", "deu")  # Default languages if not specified
}

# Function to download and install language data for Tesseract
function Install-TesseractLanguageData {
    $tessdataPath = "C:\Program Files\Tesseract-OCR\tessdata"
    $languages = Get-OCRLanguages

    if (-not (Test-Path $tessdataPath)) {
        Write-Error "Tesseract tessdata directory not found. Make sure Tesseract is installed correctly."
        return
    }

    foreach ($lang in $languages) {
        $langCode = $lang.Trim().ToLower()
        $dataUrl = "https://github.com/tesseract-ocr/tessdata/raw/main/$langCode.traineddata"
        $dataFile = Join-Path $tessdataPath "$langCode.traineddata"

        Write-Host "Downloading $langCode language data for Tesseract..." -ForegroundColor Yellow
        try {
            Invoke-WebRequest -Uri $dataUrl -OutFile $dataFile
            if (Test-Path $dataFile) {
                Write-Host "$langCode language data installed successfully." -ForegroundColor Green
            }
            else {
                Write-Error "Failed to download $langCode language data."
            }
        }
        catch {
            Write-Error "Error downloading $langCode language data: $_"
        }
    }
}


# Function to add registry entries for AutoRenamePDF
function Add-RegistryEntries {
    param($exePath)
    
    # For PDF files
    New-Item -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Force
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Name "(Default)" -Value "Auto Rename PDF"
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Name "Icon" -Value "shell32.dll,71"
    New-Item -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF\command" -Force
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF\command" -Name "(Default)" -Value "`"$exePath`" `"%1`""
    
    # For Folders
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Force
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Name "(Default)" -Value "Auto Rename PDFs in Folder"
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Name "Icon" -Value "shell32.dll,71"
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs\command" -Force
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs\command" -Name "(Default)" -Value "`"$exePath`" `"%1`""
    
    # For Directory Background
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Force
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Name "(Default)" -Value "Auto Rename PDFs in This Folder"
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Name "Icon" -Value "shell32.dll,71"
    New-Item -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs\command" -Force
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs\command" -Name "(Default)" -Value "`"$exePath`" `"%V`""
}

# Function to remove registry entries
function Remove-RegistryEntries {
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\AutoRenamePDF" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\Directory\shell\AutoRenamePDFs" -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SOFTWARE\Classes\Directory\Background\shell\AutoRenamePDFs" -Recurse -ErrorAction SilentlyContinue
}

# Main routine
$exePath = Find-AutoRenamePDF

$choice = Read-Host "Do you want to (I)nstall or (U)ninstall AutoRenamePDF? (I/U)"

if ($choice -eq "I" -or $choice -eq "i") {
    Write-Host "Starting AutoRenamePDF installation..." -ForegroundColor Green

    # Install Chocolatey if not already installed
    if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "Installing Chocolatey..." -ForegroundColor Yellow
        Install-Chocolatey
        refreshenv
    }
    else {
        Write-Host "Chocolatey is already installed." -ForegroundColor Green
    }

    # Install Tesseract
    Write-Host "Installing Tesseract..." -ForegroundColor Yellow
    Install-ChocoPackage "tesseract"

    # Install Tesseract language data
    Install-TesseractLanguageData

    # Install Ghostscript
    Write-Host "Installing Ghostscript..." -ForegroundColor Yellow
    Install-ChocoPackage "ghostscript"

    # Add registry entries
    Write-Host "Adding AutoRenamePDF to context menu..." -ForegroundColor Yellow
    Add-RegistryEntries -exePath $exePath

    Write-Host "Installation completed successfully!" -ForegroundColor Green
    Write-Host "Please restart your computer to ensure all changes take effect." -ForegroundColor Yellow
}
elseif ($choice -eq "U" -or $choice -eq "u") {
    Write-Host "Starting AutoRenamePDF uninstallation..." -ForegroundColor Green

    # Remove registry entries
    Write-Host "Removing AutoRenamePDF from context menu..." -ForegroundColor Yellow
    Remove-RegistryEntries

    Write-Host "Uninstallation completed successfully!" -ForegroundColor Green
    Write-Host "The registry entries for AutoRenamePDF have been removed." -ForegroundColor Yellow
    Write-Host "Tesseract and Ghostscript have not been uninstalled. If you wish to remove them, please use Chocolatey or the Windows Control Panel." -ForegroundColor Yellow
}
else {
    Write-Host "Invalid choice. Please run the script again and choose 'I' to install or 'U' to uninstall." -ForegroundColor Red
}