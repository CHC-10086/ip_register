@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Need admin! Right-click -^> Run as administrator
    pause
    exit /b 1
)

powershell -Command "(Get-Content %windir%\System32\drivers\etc\hosts) | Where-Object { $_ -notmatch '^127\.0\.0\.1\s+ip$' } | Set-Content %windir%\System32\drivers\etc\hosts"
echo Done!
pause
