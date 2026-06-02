@echo off
del /f .lock >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
echo IP Register stopped.
timeout /t 2 >nul
