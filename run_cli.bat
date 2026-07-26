@echo off
chcp 65001 >nul
echo ==========================================
echo   Audiobook Automation Pipeline
echo ==========================================
echo.

cd /d "%~dp0"

echo Starting...
echo.

python -m txt_to_audiobook.cli %*

echo.
echo ==========================================
echo Done!
echo ==========================================
echo.
pause
