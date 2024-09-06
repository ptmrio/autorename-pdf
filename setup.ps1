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

# Function to download and install German language data for Tesseract
function Install-TesseractGermanData {
    $tessdataPath = "C:\Program Files\Tesseract-OCR\tessdata"
    $germanDataUrl = "https://github.com/tesseract-ocr/tessdata/raw/main/deu.traineddata"
    $germanDataFile = Join-Path $tessdataPath "deu.traineddata"

    if (-not (Test-Path $tessdataPath)) {
        Write-Error "Tesseract tessdata directory not found. Make sure Tesseract is installed correctly."
        return
    }

    Write-Host "Downloading German language data for Tesseract..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $germanDataUrl -OutFile $germanDataFile

    if (Test-Path $germanDataFile) {
        Write-Host "German language data installed successfully." -ForegroundColor Green
    }
    else {
        Write-Error "Failed to download German language data."
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

    # Install German language data for Tesseract
    Install-TesseractGermanData

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
# MIIooAYJKoZIhvcNAQcCoIIokTCCKI0CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQH8w7YFlLCE63JNLG
# KX7zUQIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCBoP0xLLppRwKcK
# SfgIjbX94+sEePGecg4BpFueAJ2RoqCCDaAwgga5MIIEoaADAgECAhEAmaOACiZV
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
# P5oqJ2htYqYXyDGCGlYwghpSAgEBMGowVjELMAkGA1UEBhMCUEwxITAfBgNVBAoT
# GEFzc2VjbyBEYXRhIFN5c3RlbXMgUy5BLjEkMCIGA1UEAxMbQ2VydHVtIENvZGUg
# U2lnbmluZyAyMDIxIENBAhA5MbTyzEucC8urCrsHvepjMA0GCWCGSAFlAwQCAQUA
# oHwwEAYKKwYBBAGCNwIBDDECMAAwGQYJKoZIhvcNAQkDMQwGCisGAQQBgjcCAQQw
# HAYKKwYBBAGCNwIBCzEOMAwGCisGAQQBgjcCARUwLwYJKoZIhvcNAQkEMSIEIOOx
# 68t5OjQaebe06BQcbFz+mSGK65uiOK63l1M22i7EMA0GCSqGSIb3DQEBAQUABIIC
# AG0B3gh4DaLsSHiqd0oUNQsY819w8fYVD2wgUypJowMrX/Nwb7ycSu97/xZi4I0Q
# FFihdk1uoXz41K0p+bomkmlxU2YP8cFBFu5cMe5VuqiEr/aCQc4+ZKonLT6eGd9d
# c7JSKl9fokHh0zmW+TfVcbslRLOxfJcKSyDU8YlwfQgXV2rZUXBx+8qk7xUWtGVR
# 1H5ccK18kQ1px1+nscIx3HvHW0wiLisqiXB9m3UztSrYAoh8Rd45c3Jgm5q2iZSW
# 6L6n35e/X5+ccXh1qsy5kQ3tatEv+3RTplFvfkQJrzDBFjZUEB7D0jZoky9ENA9W
# LlxhUHoK1MtSePZUTOQiSLL0XRfyieAhOmTKtEeh1aCdghRPQNZHf3DVpU0pnqtq
# LbMg6PSjhfk94LQpQWWLuV+G+G7hFT4NSgR8bj0WAnlXCdzj8j9rOvflvO8WXiLn
# zsLIE8Xm35JMlLweLx6pNeWzpfZEXi1bAJFebrjLBQj66PlzWoHDQviE/1Jy8qYY
# ImwJMheReOpEnV1gZaKaZ58p8hnzAgNfyPqYVR4jgOXU8IbGaL4AzIQouUGURBx1
# XLlcjArXcNUwaDwor6pxnYtv5KnLcaK3J88SelRF9y7aGgb3lfBbIQEPptB0vab8
# +aCydYFOfEdvyH5E/0fEF851KXQh4kkahB2BweOBfDINoYIXPzCCFzsGCisGAQQB
# gjcDAwExghcrMIIXJwYJKoZIhvcNAQcCoIIXGDCCFxQCAQMxDzANBglghkgBZQME
# AgEFADB3BgsqhkiG9w0BCRABBKBoBGYwZAIBAQYJYIZIAYb9bAcBMDEwDQYJYIZI
# AWUDBAIBBQAEIPQbv6d/e/JjY9ji3V8LgdBEauaSHfxOOfvUJsWmuyp7AhAZ4ilS
# O3SXXIU2WvmWnJVmGA8yMDI0MDkwNjEwNDQwN1qgghMJMIIGwjCCBKqgAwIBAgIQ
# BUSv85SdCDmmv9s/X+VhFjANBgkqhkiG9w0BAQsFADBjMQswCQYDVQQGEwJVUzEX
# MBUGA1UEChMORGlnaUNlcnQsIEluYy4xOzA5BgNVBAMTMkRpZ2lDZXJ0IFRydXN0
# ZWQgRzQgUlNBNDA5NiBTSEEyNTYgVGltZVN0YW1waW5nIENBMB4XDTIzMDcxNDAw
# MDAwMFoXDTM0MTAxMzIzNTk1OVowSDELMAkGA1UEBhMCVVMxFzAVBgNVBAoTDkRp
# Z2lDZXJ0LCBJbmMuMSAwHgYDVQQDExdEaWdpQ2VydCBUaW1lc3RhbXAgMjAyMzCC
# AiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAKNTRYcdg45brD5UsyPgz5/X
# 5dLnXaEOCdwvSKOXejsqnGfcYhVYwamTEafNqrJq3RApih5iY2nTWJw1cb86l+uU
# UI8cIOrHmjsvlmbjaedp/lvD1isgHMGXlLSlUIHyz8sHpjBoyoNC2vx/CSSUpIIa
# 2mq62DvKXd4ZGIX7ReoNYWyd/nFexAaaPPDFLnkPG2ZS48jWPl/aQ9OE9dDH9kgt
# XkV1lnX+3RChG4PBuOZSlbVH13gpOWvgeFmX40QrStWVzu8IF+qCZE3/I+PKhu60
# pCFkcOvV5aDaY7Mu6QXuqvYk9R28mxyyt1/f8O52fTGZZUdVnUokL6wrl76f5P17
# cz4y7lI0+9S769SgLDSb495uZBkHNwGRDxy1Uc2qTGaDiGhiu7xBG3gZbeTZD+BY
# QfvYsSzhUa+0rRUGFOpiCBPTaR58ZE2dD9/O0V6MqqtQFcmzyrzXxDtoRKOlO0L9
# c33u3Qr/eTQQfqZcClhMAD6FaXXHg2TWdc2PEnZWpST618RrIbroHzSYLzrqawGw
# 9/sqhux7UjipmAmhcbJsca8+uG+W1eEQE/5hRwqM/vC2x9XH3mwk8L9CgsqgcT2c
# kpMEtGlwJw1Pt7U20clfCKRwo+wK8REuZODLIivK8SgTIUlRfgZm0zu++uuRONhR
# B8qUt+JQofM604qDy0B7AgMBAAGjggGLMIIBhzAOBgNVHQ8BAf8EBAMCB4AwDAYD
# VR0TAQH/BAIwADAWBgNVHSUBAf8EDDAKBggrBgEFBQcDCDAgBgNVHSAEGTAXMAgG
# BmeBDAEEAjALBglghkgBhv1sBwEwHwYDVR0jBBgwFoAUuhbZbU2FL3MpdpovdYxq
# II+eyG8wHQYDVR0OBBYEFKW27xPn783QZKHVVqllMaPe1eNJMFoGA1UdHwRTMFEw
# T6BNoEuGSWh0dHA6Ly9jcmwzLmRpZ2ljZXJ0LmNvbS9EaWdpQ2VydFRydXN0ZWRH
# NFJTQTQwOTZTSEEyNTZUaW1lU3RhbXBpbmdDQS5jcmwwgZAGCCsGAQUFBwEBBIGD
# MIGAMCQGCCsGAQUFBzABhhhodHRwOi8vb2NzcC5kaWdpY2VydC5jb20wWAYIKwYB
# BQUHMAKGTGh0dHA6Ly9jYWNlcnRzLmRpZ2ljZXJ0LmNvbS9EaWdpQ2VydFRydXN0
# ZWRHNFJTQTQwOTZTSEEyNTZUaW1lU3RhbXBpbmdDQS5jcnQwDQYJKoZIhvcNAQEL
# BQADggIBAIEa1t6gqbWYF7xwjU+KPGic2CX/yyzkzepdIpLsjCICqbjPgKjZ5+PF
# 7SaCinEvGN1Ott5s1+FgnCvt7T1IjrhrunxdvcJhN2hJd6PrkKoS1yeF844ektrC
# QDifXcigLiV4JZ0qBXqEKZi2V3mP2yZWK7Dzp703DNiYdk9WuVLCtp04qYHnbUFc
# jGnRuSvExnvPnPp44pMadqJpddNQ5EQSviANnqlE0PjlSXcIWiHFtM+YlRpUurm8
# wWkZus8W8oM3NG6wQSbd3lqXTzON1I13fXVFoaVYJmoDRd7ZULVQjK9WvUzF4UbF
# KNOt50MAcN7MmJ4ZiQPq1JE3701S88lgIcRWR+3aEUuMMsOI5ljitts++V+wQtaP
# 4xeR0arAVeOGv6wnLEHQmjNKqDbUuXKWfpd5OEhfysLcPTLfddY2Z1qJ+Panx+VP
# NTwAvb6cKmx5AdzaROY63jg7B145WPR8czFVoIARyxQMfq68/qTreWWqaNYiyjvr
# moI1VygWy2nyMpqy0tg6uLFGhmu6F/3Ed2wVbK6rr3M66ElGt9V/zLY4wNjsHPW2
# obhDLN9OTH0eaHDAdwrUAuBcYLso/zjlUlrWrBciI0707NMX+1Br/wd3H3GXREHJ
# uEbTbDJ8WC9nR2XlG3O2mflrLAZG70Ee8PBf4NvZrZCARK+AEEGKMIIGrjCCBJag
# AwIBAgIQBzY3tyRUfNhHrP0oZipeWzANBgkqhkiG9w0BAQsFADBiMQswCQYDVQQG
# EwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3d3cuZGlnaWNl
# cnQuY29tMSEwHwYDVQQDExhEaWdpQ2VydCBUcnVzdGVkIFJvb3QgRzQwHhcNMjIw
# MzIzMDAwMDAwWhcNMzcwMzIyMjM1OTU5WjBjMQswCQYDVQQGEwJVUzEXMBUGA1UE
# ChMORGlnaUNlcnQsIEluYy4xOzA5BgNVBAMTMkRpZ2lDZXJ0IFRydXN0ZWQgRzQg
# UlNBNDA5NiBTSEEyNTYgVGltZVN0YW1waW5nIENBMIICIjANBgkqhkiG9w0BAQEF
# AAOCAg8AMIICCgKCAgEAxoY1BkmzwT1ySVFVxyUDxPKRN6mXUaHW0oPRnkyibaCw
# zIP5WvYRoUQVQl+kiPNo+n3znIkLf50fng8zH1ATCyZzlm34V6gCff1DtITaEfFz
# sbPuK4CEiiIY3+vaPcQXf6sZKz5C3GeO6lE98NZW1OcoLevTsbV15x8GZY2UKdPZ
# 7Gnf2ZCHRgB720RBidx8ald68Dd5n12sy+iEZLRS8nZH92GDGd1ftFQLIWhuNyG7
# QKxfst5Kfc71ORJn7w6lY2zkpsUdzTYNXNXmG6jBZHRAp8ByxbpOH7G1WE15/teP
# c5OsLDnipUjW8LAxE6lXKZYnLvWHpo9OdhVVJnCYJn+gGkcgQ+NDY4B7dW4nJZCY
# OjgRs/b2nuY7W+yB3iIU2YIqx5K/oN7jPqJz+ucfWmyU8lKVEStYdEAoq3NDzt9K
# oRxrOMUp88qqlnNCaJ+2RrOdOqPVA+C/8KI8ykLcGEh/FDTP0kyr75s9/g64ZCr6
# dSgkQe1CvwWcZklSUPRR8zZJTYsg0ixXNXkrqPNFYLwjjVj33GHek/45wPmyMKVM
# 1+mYSlg+0wOI/rOP015LdhJRk8mMDDtbiiKowSYI+RQQEgN9XyO7ZONj4KbhPvbC
# dLI/Hgl27KtdRnXiYKNYCQEoAA6EVO7O6V3IXjASvUaetdN2udIOa5kM0jO0zbEC
# AwEAAaOCAV0wggFZMBIGA1UdEwEB/wQIMAYBAf8CAQAwHQYDVR0OBBYEFLoW2W1N
# hS9zKXaaL3WMaiCPnshvMB8GA1UdIwQYMBaAFOzX44LScV1kTN8uZz/nupiuHA9P
# MA4GA1UdDwEB/wQEAwIBhjATBgNVHSUEDDAKBggrBgEFBQcDCDB3BggrBgEFBQcB
# AQRrMGkwJAYIKwYBBQUHMAGGGGh0dHA6Ly9vY3NwLmRpZ2ljZXJ0LmNvbTBBBggr
# BgEFBQcwAoY1aHR0cDovL2NhY2VydHMuZGlnaWNlcnQuY29tL0RpZ2lDZXJ0VHJ1
# c3RlZFJvb3RHNC5jcnQwQwYDVR0fBDwwOjA4oDagNIYyaHR0cDovL2NybDMuZGln
# aWNlcnQuY29tL0RpZ2lDZXJ0VHJ1c3RlZFJvb3RHNC5jcmwwIAYDVR0gBBkwFzAI
# BgZngQwBBAIwCwYJYIZIAYb9bAcBMA0GCSqGSIb3DQEBCwUAA4ICAQB9WY7Ak7Zv
# mKlEIgF+ZtbYIULhsBguEE0TzzBTzr8Y+8dQXeJLKftwig2qKWn8acHPHQfpPmDI
# 2AvlXFvXbYf6hCAlNDFnzbYSlm/EUExiHQwIgqgWvalWzxVzjQEiJc6VaT9Hd/ty
# dBTX/6tPiix6q4XNQ1/tYLaqT5Fmniye4Iqs5f2MvGQmh2ySvZ180HAKfO+ovHVP
# ulr3qRCyXen/KFSJ8NWKcXZl2szwcqMj+sAngkSumScbqyQeJsG33irr9p6xeZmB
# o1aGqwpFyd/EjaDnmPv7pp1yr8THwcFqcdnGE4AJxLafzYeHJLtPo0m5d2aR8XKc
# 6UsCUqc3fpNTrDsdCEkPlM05et3/JWOZJyw9P2un8WbDQc1PtkCbISFA0LcTJM3c
# HXg65J6t5TRxktcma+Q4c6umAU+9Pzt4rUyt+8SVe+0KXzM5h0F4ejjpnOHdI/0d
# KNPH+ejxmF/7K9h+8kaddSweJywm228Vex4Ziza4k9Tm8heZWcpw8De/mADfIBZP
# J/tgZxahZrrdVcA6KYawmKAr7ZVBtzrVFZgxtGIJDwq9gdkT/r+k0fNX2bwE+oLe
# Mt8EifAAzV3C+dAjfwAL5HYCJtnwZXZCpimHCUcr5n8apIUP/JiW9lVUKx+A+sDy
# Divl1vupL0QVSucTDh3bNzgaoSv27dZ8/DCCBY0wggR1oAMCAQICEA6bGI750C3n
# 79tQ4ghAGFowDQYJKoZIhvcNAQEMBQAwZTELMAkGA1UEBhMCVVMxFTATBgNVBAoT
# DERpZ2lDZXJ0IEluYzEZMBcGA1UECxMQd3d3LmRpZ2ljZXJ0LmNvbTEkMCIGA1UE
# AxMbRGlnaUNlcnQgQXNzdXJlZCBJRCBSb290IENBMB4XDTIyMDgwMTAwMDAwMFoX
# DTMxMTEwOTIzNTk1OVowYjELMAkGA1UEBhMCVVMxFTATBgNVBAoTDERpZ2lDZXJ0
# IEluYzEZMBcGA1UECxMQd3d3LmRpZ2ljZXJ0LmNvbTEhMB8GA1UEAxMYRGlnaUNl
# cnQgVHJ1c3RlZCBSb290IEc0MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKC
# AgEAv+aQc2jeu+RdSjwwIjBpM+zCpyUuySE98orYWcLhKac9WKt2ms2uexuEDcQw
# H/MbpDgW61bGl20dq7J58soR0uRf1gU8Ug9SH8aeFaV+vp+pVxZZVXKvaJNwwrK6
# dZlqczKU0RBEEC7fgvMHhOZ0O21x4i0MG+4g1ckgHWMpLc7sXk7Ik/ghYZs06wXG
# XuxbGrzryc/NrDRAX7F6Zu53yEioZldXn1RYjgwrt0+nMNlW7sp7XeOtyU9e5TXn
# Mcvak17cjo+A2raRmECQecN4x7axxLVqGDgDEI3Y1DekLgV9iPWCPhCRcKtVgkEy
# 19sEcypukQF8IUzUvK4bA3VdeGbZOjFEmjNAvwjXWkmkwuapoGfdpCe8oU85tRFY
# F/ckXEaPZPfBaYh2mHY9WV1CdoeJl2l6SPDgohIbZpp0yt5LHucOY67m1O+Skjqe
# PdwA5EUlibaaRBkrfsCUtNJhbesz2cXfSwQAzH0clcOP9yGyshG3u3/y1YxwLEFg
# qrFjGESVGnZifvaAsPvoZKYz0YkH4b235kOkGLimdwHhD5QMIR2yVCkliWzlDlJR
# R3S+Jqy2QXXeeqxfjT/JvNNBERJb5RBQ6zHFynIWIgnffEx1P2PsIV/EIFFrb7Gr
# hotPwtZFX50g/KEexcCPorF+CiaZ9eRpL5gdLfXZqbId5RsCAwEAAaOCATowggE2
# MA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0OBBYEFOzX44LScV1kTN8uZz/nupiuHA9P
# MB8GA1UdIwQYMBaAFEXroq/0ksuCMS1Ri6enIZ3zbcgPMA4GA1UdDwEB/wQEAwIB
# hjB5BggrBgEFBQcBAQRtMGswJAYIKwYBBQUHMAGGGGh0dHA6Ly9vY3NwLmRpZ2lj
# ZXJ0LmNvbTBDBggrBgEFBQcwAoY3aHR0cDovL2NhY2VydHMuZGlnaWNlcnQuY29t
# L0RpZ2lDZXJ0QXNzdXJlZElEUm9vdENBLmNydDBFBgNVHR8EPjA8MDqgOKA2hjRo
# dHRwOi8vY3JsMy5kaWdpY2VydC5jb20vRGlnaUNlcnRBc3N1cmVkSURSb290Q0Eu
# Y3JsMBEGA1UdIAQKMAgwBgYEVR0gADANBgkqhkiG9w0BAQwFAAOCAQEAcKC/Q1xV
# 5zhfoKN0Gz22Ftf3v1cHvZqsoYcs7IVeqRq7IviHGmlUIu2kiHdtvRoU9BNKei8t
# tzjv9P+Aufih9/Jy3iS8UgPITtAq3votVs/59PesMHqai7Je1M/RQ0SbQyHrlnKh
# SLSZy51PpwYDE3cnRNTnf+hZqPC/Lwum6fI0POz3A8eHqNJMQBk1RmppVLC4oVaO
# 7KTVPeix3P0c2PR3WlxUjG/voVA9/HYJaISfb8rbII01YBwCA8sgsKxYoA5AY8WY
# IsGyWfVVa88nq2x2zm8jLfR+cWojayL/ErhULSd+2DrZ8LaHlv1b0VysGMNNn3O3
# AamfV6peKOK5lDGCA3YwggNyAgEBMHcwYzELMAkGA1UEBhMCVVMxFzAVBgNVBAoT
# DkRpZ2lDZXJ0LCBJbmMuMTswOQYDVQQDEzJEaWdpQ2VydCBUcnVzdGVkIEc0IFJT
# QTQwOTYgU0hBMjU2IFRpbWVTdGFtcGluZyBDQQIQBUSv85SdCDmmv9s/X+VhFjAN
# BglghkgBZQMEAgEFAKCB0TAaBgkqhkiG9w0BCQMxDQYLKoZIhvcNAQkQAQQwHAYJ
# KoZIhvcNAQkFMQ8XDTI0MDkwNjEwNDQwN1owKwYLKoZIhvcNAQkQAgwxHDAaMBgw
# FgQUZvArMsLCyQ+CXc6qisnGTxmcz0AwLwYJKoZIhvcNAQkEMSIEIPa9CN4HYXiD
# PGSJaSDiY2zvBaJQuLRp5sP25iB54llNMDcGCyqGSIb3DQEJEAIvMSgwJjAkMCIE
# INL25G3tdCLM0dRAV2hBNm+CitpVmq4zFq9NGprUDHgoMA0GCSqGSIb3DQEBAQUA
# BIICAIIs8VqFXlTsMrevwqkuKL0EcHh4JS3wPWJSFLhf0dBGWEL2CYudnTBv89bF
# o/ctDzk+6Sx6LBq5Kx7iJ3mTKIMHWkVMDHrzGEA51+3Ih+RZbM1CbQccdY/a6IWA
# 1n3zaxvsz/CK6AuFKa3ugGdd6REsu+M4VUwxB31viMz42jN6qAU5zZgqtooWb7L+
# Nfp0KamFsWLWDEhqBi/zx2FgYVNla+QlySTenNjaw1RwuTTWId6YhZ+++enR1Abj
# x+cByqdvr7aCUcvqiaDYPa/g30JvT9OBiIR4q99HzzLtw4QrufVqS5UejAKPZjZI
# T1kvAnal0EgcA5Zcxf9+HDdhVJJ3lV3DUu5RoiGeZHmF5Ld+3un46sFp1tNk485u
# Oi62s5xbnnbCx/ha9J4nemI4UZDZ6l4uDK2EtKLefnCBZUsyFH9f7N2qAMQjN7DO
# TqB7MPifqKikzCJ6GtceoRpYikaQ+Yiv6tnpuJAuXbf/Ra2KkfZur6i8MB3zTf+7
# 5+QWXr72TWBQa0xG3UqwsVLAvf5gvNVGdGXTQiilIEArQ91L7VrYir8E3sfSL2XF
# kvhIMsDAX2mCLW87NVtsxgM71EzvZp/fDpJaUX+HNfQWCPZ596kpdGw+ny/XODDs
# /Lh9fr7Szhvo456e8uZ8RWMQNvQlqitznzNTu0lDYS84jsQc
# SIG # End signature block
