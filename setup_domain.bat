@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Need admin! Right-click -> Run as administrator
    pause
    exit /b 1
)

echo Adding hosts entry...
echo 127.0.0.1 ip.local >> %windir%\System32\drivers\etc\hosts
echo Done!
echo.
echo Now you can access: http://ip.local:8088
pause
