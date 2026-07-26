@echo off
chcp 65001 >nul
echo ==========================================
echo   Audiobook Web UI
echo ==========================================
echo.

cd /d "%~dp0"

set PORT=8081

echo Checking port %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081.*LISTENING" 2^>nul') do (
    echo   Found existing process PID %%a on port %PORT%, killing...
    taskkill /PID %%a /F 2>nul
    echo   Done.
)

echo.
echo Starting web server at http://127.0.0.1:%PORT%
echo Press Ctrl+C to stop (or close this window)
echo.

python -m txt_to_audiobook.web

:: When server exits (Ctrl+C or close), clean up lingering process on our port
echo.
echo Cleaning up port %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F 2>nul
)
echo Done.
