@echo off
chcp 65001 >nul
echo ==========================================
echo   Audiobook Web UI
echo ==========================================
echo.

cd /d "%~dp0"

echo Starting web server...
echo.
echo Press Ctrl+C to stop
echo.

set PYTHONPATH=%~dp0src;%PYTHONPATH%
set PORT=8081
py -m txt_to_audiobook.web

pause
