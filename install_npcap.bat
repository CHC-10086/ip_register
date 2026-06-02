@echo off
:: Use UTF-8 code page
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ============================================
echo   Npcap Install Script
echo ============================================
echo.

:: Check admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Need administrator privileges!
    echo Please right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

:: Check if already installed
if exist "C:\Program Files\Npcap\npcap.sys" (
    echo [INFO] Npcap is already installed.
    echo.
    pause
    exit /b 0
)

echo [Step 1] Downloading Npcap installer...
echo.

set DOWNLOAD_DIR=%TEMP%
set NPCAP_URL=https://npcap.com/dist/npcap-1.80.exe
set NPCAP_FILE=%DOWNLOAD_DIR%\npcap-installer.exe

:: Download using PowerShell
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%NPCAP_URL%' -OutFile '%NPCAP_FILE%'}"

if not exist "%NPCAP_FILE%" (
    echo [ERROR] Download failed!
    echo Please download manually: https://npcap.com/#download
    echo.
    pause
    exit /b 1
)

echo [INFO] Download complete: %NPCAP_FILE%
echo.
echo [Step 2] Starting installer...
echo.
echo IMPORTANT - During installation:
echo   - CHECK "Install Npcap in WinPcap API-compatible Mode"
echo   - Keep other options as default
echo.

:: Launch installer
start /wait "" "%NPCAP_FILE%"

:: Check result
if exist "C:\Program Files\Npcap\npcap.sys" (
    echo.
    echo ============================================
    echo   Npcap installed successfully!
    echo ============================================
    echo You can now use ARP scanning.
) else (
    echo.
    echo [WARNING] Installation may not be complete.
)

:: Cleanup
del "%NPCAP_FILE%" >nul 2>&1

echo.
pause
