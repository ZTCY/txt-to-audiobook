@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo ==========================================
echo   Audiobook Web UI
echo ==========================================
echo.

cd /d "%~dp0"

set PORT=8081
set PYTHONPATH=%~dp0src;%PYTHONPATH%

:: ====== Auto-detect Python with dependency check ======
set "PYTHON="
set "NEED_INSTALL=0"

:: Build candidate list
set "CANDIDATES="
where py >nul 2>&1 && set "CANDIDATES=!CANDIDATES! py"
where python >nul 2>&1 && set "CANDIDATES=!CANDIDATES! python"
where python3 >nul 2>&1 && set "CANDIDATES=!CANDIDATES! python3"

if not defined CANDIDATES (
    echo ERROR: Python not found. Please install Python 3.8+ and add to PATH.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Try each candidate: prefer one that already has dependencies
for %%C in (!CANDIDATES!) do (
    if not defined PYTHON (
        echo Checking %%C ...
        %%C -c "import sys, edge_tts, fastapi, uvicorn, websockets; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            echo   ^> %%C has all dependencies, using it.
            set "PYTHON=%%C"
        ) else (
            echo   ^> %%C missing dependencies or wrong version.
        )
    )
)

:: If none has deps, pick the first one and install
if not defined PYTHON (
    for %%C in (!CANDIDATES!) do (
        if not defined PYTHON set "PYTHON=%%C"
    )
    echo.
    echo No Python found with dependencies pre-installed.
    echo Using !PYTHON! and installing dependencies...
    set "NEED_INSTALL=1"
)

:: Verify version
!PYTHON! -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if !errorlevel! neq 0 (
    echo ERROR: !PYTHON! is not Python 3.8+.
    pause
    exit /b 1
)

:: Install dependencies if needed
if "!NEED_INSTALL!" == "1" (
    echo.
    echo Installing dependencies, this may take a minute...
    echo.
    !PYTHON! -m pip install edge-tts tqdm "fastapi>=0.100.0" "uvicorn[standard]" python-multipart "websockets>=12.0"
    if !errorlevel! neq 0 (
        echo.
        echo ERROR: Failed to install dependencies.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Dependencies installed successfully.
)

:: ====== Kill existing process on port ======
echo.
echo Checking port !PORT!...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8081.*LISTENING" 2^>nul') do (
    echo   Found existing process PID %%a on port !PORT!, killing...
    taskkill /PID %%a /F 2>nul
    echo   Done.
)

echo.
echo Starting web server at http://127.0.0.1:!PORT!
echo Press Ctrl+C to stop, or close this window.
echo.

:: Run server — use cmd /c so Ctrl+C goes directly to Python without
:: the "Terminate batch job (Y/N)?" prompt
cmd /c "!PYTHON! -m txt_to_audiobook.web"

:: Cleanup lingering process on our port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":!PORT!.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F 2>nul
)

exit /b 0
