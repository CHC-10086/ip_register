@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Need admin! Right-click -^> Run as administrator
    pause
    exit /b 1
)

echo 127.0.0.1 ip >> %windir%\System32\drivers\etc\hosts
echo Done!
echo.
echo Now access: http://ip
pause
