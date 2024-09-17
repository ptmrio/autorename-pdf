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

# Function to read OCR_LANGUAGES from .env file
function Get-OCRLanguages {
    $envPath = Join-Path $PSScriptRoot ".env"
    if (Test-Path $envPath) {
        $envContent = Get-Content $envPath -Raw
        if ($envContent -match "OCR_LANGUAGES=(.+)") {
            return $matches[1].Split(',')
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
# SIG # Begin signature block
# MIIooQYJKoZIhvcNAQcCoIIokjCCKI4CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCD1PKPK2xLJDjVL
# 7NqLp+FMB6pwqgXP6wmwpKrKq24UB6CCDaAwgga5MIIEoaADAgECAhEAmaOACiZV
# O2Wr3G6EprPqOTANBgkqhkiG9w0BAQwFADCBgDELMAkGA1UEBhMCUEwxIjAgBgNV
# BAoTGVVuaXpldG8gVGVjaG5vbG9naWVzIFMuQS4xJzAlBgNVBAsTHkNlcnR1bSBD
# ZXJ0aWZpY2F0aW9uIEF1dGhvcml0eTEkMCIGA1UEAxMbQ2VydHVtIFRydXN0ZWQg
# TmV0d29yayBDQSAyMB4XDTIxMDUxOTA1MzIxOFoXDTM2MDUxODA1MzIxOFowVjEL
# MAkGA1UEBhMCUEwxITAfBgNVBAoTGEFzc2VjbyBEYXRhIFN5c3RlbXMgUy5BLjEk
# MCIGA1UEAxMbQ2VydHVtIENvZGUgU2lnbmluZyAyMDIxIENBMIICIjANBgkqhkiG
# 9w0BAQEFAAOCAg8AMIICCgKCAgEAnSPPBDAjO8FGLOczcz5jXXp1ur5cTbq96y34
# vuTmflN4mSAfgLKTvggv24/rWiVGzGxT9YEASVMw1Aj8ewTS4IndU8s7VS5+djSo
# McbvIKck6+hI1shsylP4JyLvmxwLHtSworV9wmjhNd627h27a8RdrT1PH9ud0IF+
# njvMk2xqbNTIPsnWtw3E7DmDoUmDQiYi/ucJ42fcHqBkbbxYDB7SYOouu9Tj1yHI
# ohzuC8KNqfcYf7Z4/iZgkBJ+UFNDcc6zokZ2uJIxWgPWXMEmhu1gMXgv8aGUsRda
# CtVD2bSlbfsq7BiqljjaCun+RJgTgFRCtsuAEw0pG9+FA+yQN9n/kZtMLK+Wo837
# Q4QOZgYqVWQ4x6cM7/G0yswg1ElLlJj6NYKLw9EcBXE7TF3HybZtYvj9lDV2nT8m
# FSkcSkAExzd4prHwYjUXTeZIlVXqj+eaYqoMTpMrfh5MCAOIG5knN4Q/JHuurfTI
# 5XDYO962WZayx7ACFf5ydJpoEowSP07YaBiQ8nXpDkNrUA9g7qf/rCkKbWpQ5bou
# fUnq1UiYPIAHlezf4muJqxqIns/kqld6JVX8cixbd6PzkDpwZo4SlADaCi2JSplK
# ShBSND36E/ENVv8urPS0yOnpG4tIoBGxVCARPCg1BnyMJ4rBJAcOSnAWd18Jx5n8
# 58JSqPECAwEAAaOCAVUwggFRMA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0OBBYEFN10
# XUwA23ufoHTKsW73PMAywHDNMB8GA1UdIwQYMBaAFLahVDkCw6A/joq8+tT4HKbR
# Og79MA4GA1UdDwEB/wQEAwIBBjATBgNVHSUEDDAKBggrBgEFBQcDAzAwBgNVHR8E
# KTAnMCWgI6Ahhh9odHRwOi8vY3JsLmNlcnR1bS5wbC9jdG5jYTIuY3JsMGwGCCsG
# AQUFBwEBBGAwXjAoBggrBgEFBQcwAYYcaHR0cDovL3N1YmNhLm9jc3AtY2VydHVt
# LmNvbTAyBggrBgEFBQcwAoYmaHR0cDovL3JlcG9zaXRvcnkuY2VydHVtLnBsL2N0
# bmNhMi5jZXIwOQYDVR0gBDIwMDAuBgRVHSAAMCYwJAYIKwYBBQUHAgEWGGh0dHA6
# Ly93d3cuY2VydHVtLnBsL0NQUzANBgkqhkiG9w0BAQwFAAOCAgEAdYhYD+WPUCia
# U58Q7EP89DttyZqGYn2XRDhJkL6P+/T0IPZyxfxiXumYlARMgwRzLRUStJl490L9
# 4C9LGF3vjzzH8Jq3iR74BRlkO18J3zIdmCKQa5LyZ48IfICJTZVJeChDUyuQy6rG
# DxLUUAsO0eqeLNhLVsgw6/zOfImNlARKn1FP7o0fTbj8ipNGxHBIutiRsWrhWM2f
# 8pXdd3x2mbJCKKtl2s42g9KUJHEIiLni9ByoqIUul4GblLQigO0ugh7bWRLDm0Cd
# Y9rNLqyA3ahe8WlxVWkxyrQLjH8ItI17RdySaYayX3PhRSC4Am1/7mATwZWwSD+B
# 7eMcZNhpn8zJ+6MTyE6YoEBSRVrs0zFFIHUR08Wk0ikSf+lIe5Iv6RY3/bFAEloM
# U+vUBfSouCReZwSLo8WdrDlPXtR0gicDnytO7eZ5827NS2x7gCBibESYkOh1/w1t
# VxTpV2Na3PR7nxYVlPu1JPoRZCbH86gc96UTvuWiOruWmyOEMLOGGniR+x+zPF/2
# DaGgK2W1eEJfo2qyrBNPvF7wuAyQfiFXLwvWHamoYtPZo0LHuH8X3n9C+xN4YaNj
# t2ywzOr+tKyEVAotnyU9vyEVOaIYMk3IeBrmFnn0gbKeTTyYeEEUz/Qwt4HOUBCr
# W602NCmvO1nm+/80nLy5r0AZvCQxaQ4wggbfMIIEx6ADAgECAhA5MbTyzEucC8ur
# CrsHvepjMA0GCSqGSIb3DQEBCwUAMFYxCzAJBgNVBAYTAlBMMSEwHwYDVQQKExhB
# c3NlY28gRGF0YSBTeXN0ZW1zIFMuQS4xJDAiBgNVBAMTG0NlcnR1bSBDb2RlIFNp
# Z25pbmcgMjAyMSBDQTAeFw0yNDA4MDExMjA2MDVaFw0yNTA4MDExMjA2MDRaMIGE
# MQswCQYDVQQGEwJBVDEPMA0GA1UECAwGU3R5cmlhMREwDwYDVQQHDAhGZWxkYmFj
# aDEeMBwGA1UECgwVT3BlbiBTb3VyY2UgRGV2ZWxvcGVyMTEwLwYDVQQDDChPcGVu
# IFNvdXJjZSBEZXZlbG9wZXIsIEdlcmhhcmQgUGV0ZXJtZWlyMIICIjANBgkqhkiG
# 9w0BAQEFAAOCAg8AMIICCgKCAgEAoyE+k/6tkcIEzw6/wJuIHLmpvVX+KaP3Nh+u
# kb1Ugo9OSho3mHsk1lTZCKpCP4smmjQyfOeDo1qcc5oZS8DBLfLUu/gcqTPyFIvR
# +ZILzTjPQLY1ft1Vy06IjBRfOq4VgezGdpqHgg5hjGBsBDkP1crgz+dgSJ9sS2x5
# U1e5WkAeBNBdgmvineFK5C2UbZJvyohSfnlfJVr2nYH/PpyuyxwaJgm+eoVpgBAG
# qK79ZGsiRaQD5LRi8x6edDJXSy1y0sTnwpicXEH+qZPPZvlalOO4QpH9aqk1gVcS
# wu0Ji/WCcj7XsILaKnKmTnXSI+w8EH9bC6p38eFpd69E5lQcdpRTchtCr+HdQB/J
# gUp8IA8PkDU2FCoaFbkKPOayiZL+5zV3erVuRNLu7lB8v5WX6S0mNJMSCoKDBWwl
# wcSI5bnmOHjBOhaUYBk8EmZz3esyijnIQvOXlJGIEWEoTFKUk6fseEsXIAEiAzLQ
# 7KOmmyG3t3kzNplBfFnJ56mqoBCdqco9m4XqBIYCALQtN9saeFPYNXBA6zhVIsmB
# Lbo/rjmvDR1G0U6CXdyXnUMHCUUfNV5YhyfrfLe/wmI2ECIAO4/JxO6UDOx+rUjQ
# Ostt62fewtKpXabK1yeqdLL7ImwdMGTmmg0TrYvPR4rw/jhSR+wTfmVfefxB4lBW
# NRr3CIUCAwEAAaOCAXgwggF0MAwGA1UdEwEB/wQCMAAwPQYDVR0fBDYwNDAyoDCg
# LoYsaHR0cDovL2Njc2NhMjAyMS5jcmwuY2VydHVtLnBsL2Njc2NhMjAyMS5jcmww
# cwYIKwYBBQUHAQEEZzBlMCwGCCsGAQUFBzABhiBodHRwOi8vY2NzY2EyMDIxLm9j
# c3AtY2VydHVtLmNvbTA1BggrBgEFBQcwAoYpaHR0cDovL3JlcG9zaXRvcnkuY2Vy
# dHVtLnBsL2Njc2NhMjAyMS5jZXIwHwYDVR0jBBgwFoAU3XRdTADbe5+gdMqxbvc8
# wDLAcM0wHQYDVR0OBBYEFPLIIsE2cJ/rfmRif21ohtvUgOM3MEsGA1UdIAREMEIw
# CAYGZ4EMAQQBMDYGCyqEaAGG9ncCBQEEMCcwJQYIKwYBBQUHAgEWGWh0dHBzOi8v
# d3d3LmNlcnR1bS5wbC9DUFMwEwYDVR0lBAwwCgYIKwYBBQUHAwMwDgYDVR0PAQH/
# BAQDAgeAMA0GCSqGSIb3DQEBCwUAA4ICAQBA0D8td6CBusw+WPnGUL+KOh90o0Os
# 8yoFyk2RPw2uGpJrElwMaaC+ZXbwi4C/6fqErab5I0MOX90S3ItWjou2XYPUD8/6
# ycRTdRDFKXq6J1Az/1H1g8DU+CeTK3g6WVrLLnDyO1Nbg/Hw81W38vH3b3Wl7Z6d
# HR1FvElFXeKpQHjzvXHKNRX5vJFbAwqCiNs54kaNqsm3Ced/nrbMdC1M7qX64S3W
# x7EdnrX+L0X3fS58jG/+/2W0aBbw6c+Oyk8PiblUZrePWZ3JcZEBVSIzrbCQPYAh
# DMAksOLOPefFCW4rFQYN80TlNf4OMvdE4+d6xS9rdJcrCcnD32+YEjUVMK8bGClk
# y7DCstkMsFlTW+QoouFjBGNZhpoYzCwsMtHw2xCZl4AhhjUdKm084an4Jl/+pA1n
# TElTr0izCfO+NT8d9SEwMYY0994nxW2Vy9B7+L8MaNnBDAJUkYUuSjrrYDIk++oO
# 5THnS0knisZYqx1mzRieP7X6IznIUx+tbbM0/t/npH88sfT4cVP+wSVGXi7cd9gA
# 8EobelW3SHau+tZFRakbn5Of0Okmz0E10MvptRUd2GWLQ5Su4dRmbrAGxOQpVhTK
# 6zJmA9IetArs9Q2WefWTUQwomJGp0m8ZofGrqWUM9ZnbcvLQ3x+o9KhOdqsxxG1R
# P5oqJ2htYqYXyDGCGlcwghpTAgEBMGowVjELMAkGA1UEBhMCUEwxITAfBgNVBAoT
# GEFzc2VjbyBEYXRhIFN5c3RlbXMgUy5BLjEkMCIGA1UEAxMbQ2VydHVtIENvZGUg
# U2lnbmluZyAyMDIxIENBAhA5MbTyzEucC8urCrsHvepjMA0GCWCGSAFlAwQCAQUA
# oHwwEAYKKwYBBAGCNwIBDDECMAAwGQYJKoZIhvcNAQkDMQwGCisGAQQBgjcCAQQw
# HAYKKwYBBAGCNwIBCzEOMAwGCisGAQQBgjcCARUwLwYJKoZIhvcNAQkEMSIEIDIG
# z1N4sV8m10LtU27k74PY/QDf9hZxt+peEMEqIuX7MA0GCSqGSIb3DQEBAQUABIIC
# AFVXEyZwjDkFREvjs3JNioHmzhKDeviiR+VrCLtieHZkZjk5/cAGfFIr+NJb86j5
# vAOQBW6WT65ut17lK/fw8K++FMDs0NmsACvSAAOfZoiiuarpMQJ2Xgz9+bU8IFl5
# 1KbFT5UpM703bKbcvpwK2Ue9J0UqcOvuDzfCFJp0wKCIU34qLH/YxuuzFObRC910
# a4Pvppqp1d4OAP3AD3dC+U6j7pLUiPwO80oyU2B85ipe0EiY+vM2wpZxoPOksXta
# jwzw4K9DiapcL6wGzhokmh76expjKCnooRggcaGZw9Y1yezlVaElIas85opEzQBn
# z5qz1B/GAqTy8dv2FVcJxlqLKD1j8JKOCYK3AJwE7QkhT7w0BXd7MiwaoWOEle7+
# 2ED3a6OiTnuRYZsmW8/+gECXU7Dcf0oK9MVYjjISV3ae3py+QsSOsBuxV7Ih3DEi
# eLhf73DNJ2ZGFyyvB0Bzyx856PwMauzXXxYrY0b0GMw0JGK8N38+zSYS/zHeW7je
# 6+9bZtJAnP7K7ooUuktb3ZaSlRTHploLO7eDNUcOs1h/1nRHATMc+Rmy9ucQEWX0
# omT1+LD1E/t7NT080Y7ZYz6JMAjodoypkedBK/RnUXYKQuUcwTt01iLO3wFcZNbr
# 8eoe6JhKagpoQcXn2qippxTjpoYK0bCjyFPb95EolMpFoYIXQDCCFzwGCisGAQQB
# gjcDAwExghcsMIIXKAYJKoZIhvcNAQcCoIIXGTCCFxUCAQMxDzANBglghkgBZQME
# AgEFADB4BgsqhkiG9w0BCRABBKBpBGcwZQIBAQYJYIZIAYb9bAcBMDEwDQYJYIZI
# AWUDBAIBBQAEIIv8RfeMqVuZtHVq6EYUoIEwhNVEI0TBDayKD1eaG5xXAhEAgBdC
# qsWgIMtj2yKN8VphnRgPMjAyNDA5MTcwOTM5MTdaoIITCTCCBsIwggSqoAMCAQIC
# EAVEr/OUnQg5pr/bP1/lYRYwDQYJKoZIhvcNAQELBQAwYzELMAkGA1UEBhMCVVMx
# FzAVBgNVBAoTDkRpZ2lDZXJ0LCBJbmMuMTswOQYDVQQDEzJEaWdpQ2VydCBUcnVz
# dGVkIEc0IFJTQTQwOTYgU0hBMjU2IFRpbWVTdGFtcGluZyBDQTAeFw0yMzA3MTQw
# MDAwMDBaFw0zNDEwMTMyMzU5NTlaMEgxCzAJBgNVBAYTAlVTMRcwFQYDVQQKEw5E
# aWdpQ2VydCwgSW5jLjEgMB4GA1UEAxMXRGlnaUNlcnQgVGltZXN0YW1wIDIwMjMw
# ggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCjU0WHHYOOW6w+VLMj4M+f
# 1+XS512hDgncL0ijl3o7Kpxn3GIVWMGpkxGnzaqyat0QKYoeYmNp01icNXG/Opfr
# lFCPHCDqx5o7L5Zm42nnaf5bw9YrIBzBl5S0pVCB8s/LB6YwaMqDQtr8fwkklKSC
# Gtpqutg7yl3eGRiF+0XqDWFsnf5xXsQGmjzwxS55DxtmUuPI1j5f2kPThPXQx/ZI
# LV5FdZZ1/t0QoRuDwbjmUpW1R9d4KTlr4HhZl+NEK0rVlc7vCBfqgmRN/yPjyobu
# tKQhZHDr1eWg2mOzLukF7qr2JPUdvJscsrdf3/Dudn0xmWVHVZ1KJC+sK5e+n+T9
# e3M+Mu5SNPvUu+vUoCw0m+PebmQZBzcBkQ8ctVHNqkxmg4hoYru8QRt4GW3k2Q/g
# WEH72LEs4VGvtK0VBhTqYggT02kefGRNnQ/fztFejKqrUBXJs8q818Q7aESjpTtC
# /XN97t0K/3k0EH6mXApYTAA+hWl1x4Nk1nXNjxJ2VqUk+tfEayG66B80mC866msB
# sPf7Kobse1I4qZgJoXGybHGvPrhvltXhEBP+YUcKjP7wtsfVx95sJPC/QoLKoHE9
# nJKTBLRpcCcNT7e1NtHJXwikcKPsCvERLmTgyyIryvEoEyFJUX4GZtM7vvrrkTjY
# UQfKlLfiUKHzOtOKg8tAewIDAQABo4IBizCCAYcwDgYDVR0PAQH/BAQDAgeAMAwG
# A1UdEwEB/wQCMAAwFgYDVR0lAQH/BAwwCgYIKwYBBQUHAwgwIAYDVR0gBBkwFzAI
# BgZngQwBBAIwCwYJYIZIAYb9bAcBMB8GA1UdIwQYMBaAFLoW2W1NhS9zKXaaL3WM
# aiCPnshvMB0GA1UdDgQWBBSltu8T5+/N0GSh1VapZTGj3tXjSTBaBgNVHR8EUzBR
# ME+gTaBLhklodHRwOi8vY3JsMy5kaWdpY2VydC5jb20vRGlnaUNlcnRUcnVzdGVk
# RzRSU0E0MDk2U0hBMjU2VGltZVN0YW1waW5nQ0EuY3JsMIGQBggrBgEFBQcBAQSB
# gzCBgDAkBggrBgEFBQcwAYYYaHR0cDovL29jc3AuZGlnaWNlcnQuY29tMFgGCCsG
# AQUFBzAChkxodHRwOi8vY2FjZXJ0cy5kaWdpY2VydC5jb20vRGlnaUNlcnRUcnVz
# dGVkRzRSU0E0MDk2U0hBMjU2VGltZVN0YW1waW5nQ0EuY3J0MA0GCSqGSIb3DQEB
# CwUAA4ICAQCBGtbeoKm1mBe8cI1PijxonNgl/8ss5M3qXSKS7IwiAqm4z4Co2efj
# xe0mgopxLxjdTrbebNfhYJwr7e09SI64a7p8Xb3CYTdoSXej65CqEtcnhfOOHpLa
# wkA4n13IoC4leCWdKgV6hCmYtld5j9smViuw86e9NwzYmHZPVrlSwradOKmB521B
# XIxp0bkrxMZ7z5z6eOKTGnaiaXXTUOREEr4gDZ6pRND45Ul3CFohxbTPmJUaVLq5
# vMFpGbrPFvKDNzRusEEm3d5al08zjdSNd311RaGlWCZqA0Xe2VC1UIyvVr1MxeFG
# xSjTredDAHDezJieGYkD6tSRN+9NUvPJYCHEVkft2hFLjDLDiOZY4rbbPvlfsELW
# j+MXkdGqwFXjhr+sJyxB0JozSqg21Llyln6XeThIX8rC3D0y33XWNmdaifj2p8fl
# TzU8AL2+nCpseQHc2kTmOt44OwdeOVj0fHMxVaCAEcsUDH6uvP6k63llqmjWIso7
# 65qCNVcoFstp8jKastLYOrixRoZruhf9xHdsFWyuq69zOuhJRrfVf8y2OMDY7Bz1
# tqG4QyzfTkx9HmhwwHcK1ALgXGC7KP845VJa1qwXIiNO9OzTF/tQa/8Hdx9xl0RB
# ybhG02wyfFgvZ0dl5Rtztpn5aywGRu9BHvDwX+Db2a2QgESvgBBBijCCBq4wggSW
# oAMCAQICEAc2N7ckVHzYR6z9KGYqXlswDQYJKoZIhvcNAQELBQAwYjELMAkGA1UE
# BhMCVVMxFTATBgNVBAoTDERpZ2lDZXJ0IEluYzEZMBcGA1UECxMQd3d3LmRpZ2lj
# ZXJ0LmNvbTEhMB8GA1UEAxMYRGlnaUNlcnQgVHJ1c3RlZCBSb290IEc0MB4XDTIy
# MDMyMzAwMDAwMFoXDTM3MDMyMjIzNTk1OVowYzELMAkGA1UEBhMCVVMxFzAVBgNV
# BAoTDkRpZ2lDZXJ0LCBJbmMuMTswOQYDVQQDEzJEaWdpQ2VydCBUcnVzdGVkIEc0
# IFJTQTQwOTYgU0hBMjU2IFRpbWVTdGFtcGluZyBDQTCCAiIwDQYJKoZIhvcNAQEB
# BQADggIPADCCAgoCggIBAMaGNQZJs8E9cklRVcclA8TykTepl1Gh1tKD0Z5Mom2g
# sMyD+Vr2EaFEFUJfpIjzaPp985yJC3+dH54PMx9QEwsmc5Zt+FeoAn39Q7SE2hHx
# c7Gz7iuAhIoiGN/r2j3EF3+rGSs+QtxnjupRPfDWVtTnKC3r07G1decfBmWNlCnT
# 2exp39mQh0YAe9tEQYncfGpXevA3eZ9drMvohGS0UvJ2R/dhgxndX7RUCyFobjch
# u0CsX7LeSn3O9TkSZ+8OpWNs5KbFHc02DVzV5huowWR0QKfAcsW6Th+xtVhNef7X
# j3OTrCw54qVI1vCwMROpVymWJy71h6aPTnYVVSZwmCZ/oBpHIEPjQ2OAe3VuJyWQ
# mDo4EbP29p7mO1vsgd4iFNmCKseSv6De4z6ic/rnH1pslPJSlRErWHRAKKtzQ87f
# SqEcazjFKfPKqpZzQmiftkaznTqj1QPgv/CiPMpC3BhIfxQ0z9JMq++bPf4OuGQq
# +nUoJEHtQr8FnGZJUlD0UfM2SU2LINIsVzV5K6jzRWC8I41Y99xh3pP+OcD5sjCl
# TNfpmEpYPtMDiP6zj9NeS3YSUZPJjAw7W4oiqMEmCPkUEBIDfV8ju2TjY+Cm4T72
# wnSyPx4JduyrXUZ14mCjWAkBKAAOhFTuzuldyF4wEr1GnrXTdrnSDmuZDNIztM2x
# AgMBAAGjggFdMIIBWTASBgNVHRMBAf8ECDAGAQH/AgEAMB0GA1UdDgQWBBS6Ftlt
# TYUvcyl2mi91jGogj57IbzAfBgNVHSMEGDAWgBTs1+OC0nFdZEzfLmc/57qYrhwP
# TzAOBgNVHQ8BAf8EBAMCAYYwEwYDVR0lBAwwCgYIKwYBBQUHAwgwdwYIKwYBBQUH
# AQEEazBpMCQGCCsGAQUFBzABhhhodHRwOi8vb2NzcC5kaWdpY2VydC5jb20wQQYI
# KwYBBQUHMAKGNWh0dHA6Ly9jYWNlcnRzLmRpZ2ljZXJ0LmNvbS9EaWdpQ2VydFRy
# dXN0ZWRSb290RzQuY3J0MEMGA1UdHwQ8MDowOKA2oDSGMmh0dHA6Ly9jcmwzLmRp
# Z2ljZXJ0LmNvbS9EaWdpQ2VydFRydXN0ZWRSb290RzQuY3JsMCAGA1UdIAQZMBcw
# CAYGZ4EMAQQCMAsGCWCGSAGG/WwHATANBgkqhkiG9w0BAQsFAAOCAgEAfVmOwJO2
# b5ipRCIBfmbW2CFC4bAYLhBNE88wU86/GPvHUF3iSyn7cIoNqilp/GnBzx0H6T5g
# yNgL5Vxb122H+oQgJTQxZ822EpZvxFBMYh0MCIKoFr2pVs8Vc40BIiXOlWk/R3f7
# cnQU1/+rT4osequFzUNf7WC2qk+RZp4snuCKrOX9jLxkJodskr2dfNBwCnzvqLx1
# T7pa96kQsl3p/yhUifDVinF2ZdrM8HKjI/rAJ4JErpknG6skHibBt94q6/aesXmZ
# gaNWhqsKRcnfxI2g55j7+6adcq/Ex8HBanHZxhOACcS2n82HhyS7T6NJuXdmkfFy
# nOlLAlKnN36TU6w7HQhJD5TNOXrd/yVjmScsPT9rp/Fmw0HNT7ZAmyEhQNC3EyTN
# 3B14OuSereU0cZLXJmvkOHOrpgFPvT87eK1MrfvElXvtCl8zOYdBeHo46Zzh3SP9
# HSjTx/no8Zhf+yvYfvJGnXUsHicsJttvFXseGYs2uJPU5vIXmVnKcPA3v5gA3yAW
# Tyf7YGcWoWa63VXAOimGsJigK+2VQbc61RWYMbRiCQ8KvYHZE/6/pNHzV9m8BPqC
# 3jLfBInwAM1dwvnQI38AC+R2AibZ8GV2QqYphwlHK+Z/GqSFD/yYlvZVVCsfgPrA
# 8g4r5db7qS9EFUrnEw4d2zc4GqEr9u3WfPwwggWNMIIEdaADAgECAhAOmxiO+dAt
# 5+/bUOIIQBhaMA0GCSqGSIb3DQEBDAUAMGUxCzAJBgNVBAYTAlVTMRUwEwYDVQQK
# EwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5jb20xJDAiBgNV
# BAMTG0RpZ2lDZXJ0IEFzc3VyZWQgSUQgUm9vdCBDQTAeFw0yMjA4MDEwMDAwMDBa
# Fw0zMTExMDkyMzU5NTlaMGIxCzAJBgNVBAYTAlVTMRUwEwYDVQQKEwxEaWdpQ2Vy
# dCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5jb20xITAfBgNVBAMTGERpZ2lD
# ZXJ0IFRydXN0ZWQgUm9vdCBHNDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoC
# ggIBAL/mkHNo3rvkXUo8MCIwaTPswqclLskhPfKK2FnC4SmnPVirdprNrnsbhA3E
# MB/zG6Q4FutWxpdtHauyefLKEdLkX9YFPFIPUh/GnhWlfr6fqVcWWVVyr2iTcMKy
# unWZanMylNEQRBAu34LzB4TmdDttceItDBvuINXJIB1jKS3O7F5OyJP4IWGbNOsF
# xl7sWxq868nPzaw0QF+xembud8hIqGZXV59UWI4MK7dPpzDZVu7Ke13jrclPXuU1
# 5zHL2pNe3I6PgNq2kZhAkHnDeMe2scS1ahg4AxCN2NQ3pC4FfYj1gj4QkXCrVYJB
# MtfbBHMqbpEBfCFM1LyuGwN1XXhm2ToxRJozQL8I11pJpMLmqaBn3aQnvKFPObUR
# WBf3JFxGj2T3wWmIdph2PVldQnaHiZdpekjw4KISG2aadMreSx7nDmOu5tTvkpI6
# nj3cAORFJYm2mkQZK37AlLTSYW3rM9nF30sEAMx9HJXDj/chsrIRt7t/8tWMcCxB
# YKqxYxhElRp2Yn72gLD76GSmM9GJB+G9t+ZDpBi4pncB4Q+UDCEdslQpJYls5Q5S
# UUd0viastkF13nqsX40/ybzTQRESW+UQUOsxxcpyFiIJ33xMdT9j7CFfxCBRa2+x
# q4aLT8LWRV+dIPyhHsXAj6KxfgommfXkaS+YHS312amyHeUbAgMBAAGjggE6MIIB
# NjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBTs1+OC0nFdZEzfLmc/57qYrhwP
# TzAfBgNVHSMEGDAWgBRF66Kv9JLLgjEtUYunpyGd823IDzAOBgNVHQ8BAf8EBAMC
# AYYweQYIKwYBBQUHAQEEbTBrMCQGCCsGAQUFBzABhhhodHRwOi8vb2NzcC5kaWdp
# Y2VydC5jb20wQwYIKwYBBQUHMAKGN2h0dHA6Ly9jYWNlcnRzLmRpZ2ljZXJ0LmNv
# bS9EaWdpQ2VydEFzc3VyZWRJRFJvb3RDQS5jcnQwRQYDVR0fBD4wPDA6oDigNoY0
# aHR0cDovL2NybDMuZGlnaWNlcnQuY29tL0RpZ2lDZXJ0QXNzdXJlZElEUm9vdENB
# LmNybDARBgNVHSAECjAIMAYGBFUdIAAwDQYJKoZIhvcNAQEMBQADggEBAHCgv0Nc
# Vec4X6CjdBs9thbX979XB72arKGHLOyFXqkauyL4hxppVCLtpIh3bb0aFPQTSnov
# Lbc47/T/gLn4offyct4kvFIDyE7QKt76LVbP+fT3rDB6mouyXtTP0UNEm0Mh65Zy
# oUi0mcudT6cGAxN3J0TU53/oWajwvy8LpunyNDzs9wPHh6jSTEAZNUZqaVSwuKFW
# juyk1T3osdz9HNj0d1pcVIxv76FQPfx2CWiEn2/K2yCNNWAcAgPLILCsWKAOQGPF
# mCLBsln1VWvPJ6tsds5vIy30fnFqI2si/xK4VC0nftg62fC2h5b9W9FcrBjDTZ9z
# twGpn1eqXijiuZQxggN2MIIDcgIBATB3MGMxCzAJBgNVBAYTAlVTMRcwFQYDVQQK
# Ew5EaWdpQ2VydCwgSW5jLjE7MDkGA1UEAxMyRGlnaUNlcnQgVHJ1c3RlZCBHNCBS
# U0E0MDk2IFNIQTI1NiBUaW1lU3RhbXBpbmcgQ0ECEAVEr/OUnQg5pr/bP1/lYRYw
# DQYJYIZIAWUDBAIBBQCggdEwGgYJKoZIhvcNAQkDMQ0GCyqGSIb3DQEJEAEEMBwG
# CSqGSIb3DQEJBTEPFw0yNDA5MTcwOTM5MTdaMCsGCyqGSIb3DQEJEAIMMRwwGjAY
# MBYEFGbwKzLCwskPgl3OqorJxk8ZnM9AMC8GCSqGSIb3DQEJBDEiBCDnXz/B4RiU
# s3aAu0TQQiTe/0f1BYfno5V+ZJkxZfjLcTA3BgsqhkiG9w0BCRACLzEoMCYwJDAi
# BCDS9uRt7XQizNHUQFdoQTZvgoraVZquMxavTRqa1Ax4KDANBgkqhkiG9w0BAQEF
# AASCAgCXlzTNlSWeS/b0Xbi5Uxcz+lxFYhJ5yCFnbEtEf3PDQdoXmQir9v8OTwJE
# JQInVn1clGk2ao5DC5RcDYz/mXQCjN5dP6PK3IHsL7HtMPadUGtRHRnnRZP4aCGf
# Rq+Wzs1u/ROq59X4DXJelzLzOkOxnBC9VL29TbglDlQyI4W80vQQCGUu73ZorDTA
# hsG5BHOnsDZgRyiJQOeA7HyhtbHHWoBVIcwDndKjkmeogau3BngZjhiBzy9/MInX
# mysiDPUSIZi+U7DDCpTIWtAwV3Ulxwf63T8UNATOP/NAY8G/l5esIix3zZa+7Yox
# FWmQLEGd4XcuEKQpvFsZDIt68DTw3THVnZJ+SP34K2d9udA/y3L68/Ut6uM2wfxY
# w03CnJwRJ32opE6o/mCwVuim3615SxFrnKXtSUuGJ70KbcS0/UCxPRyHhlklSFRy
# cbeGVTmKdzQB1e63GuiefRjf99EdSoiJbw9KlVZJ02qteI26NhOwBMLfeMuXRLUy
# +wyN3tK11MwK+bVjxoJg14mMVzjvwQsqPVSCbnM4nkGo/gqIUX+HOiR3yLmWURpc
# 2REZTNN/1fb54yS990TEi5qRBIZP1EtPp0SfWwqXVE6JBd+v6Nj0JY27I4wrxDe+
# WZqST9iNiAwXZ5tCTt4yAZ5SD8IkQb8gkFi/qxPxedfCJRyB2w==
# SIG # End signature block
