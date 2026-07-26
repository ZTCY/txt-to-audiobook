@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo ==========================================
echo   Audiobook Automation Pipeline (CLI)
echo ==========================================
echo.

cd /d "%~dp0"

set PYTHONPATH=%~dp0src;%PYTHONPATH%

:: ====== Auto-detect Python with dependency check ======
set "PYTHON="
set "NEED_INSTALL=0"

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

for %%C in (!CANDIDATES!) do (
    if not defined PYTHON (
        echo Checking %%C ...
        %%C -c "import sys, edge_tts; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            echo   ^> %%C has all dependencies, using it.
            set "PYTHON=%%C"
        ) else (
            echo   ^> %%C missing dependencies or wrong version.
        )
    )
)

if not defined PYTHON (
    for %%C in (!CANDIDATES!) do (
        if not defined PYTHON set "PYTHON=%%C"
    )
    echo.
    echo No Python found with dependencies pre-installed.
    echo Using !PYTHON! and installing dependencies...
    set "NEED_INSTALL=1"
)

!PYTHON! -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if !errorlevel! neq 0 (
    echo ERROR: !PYTHON! is not Python 3.8+.
    pause
    exit /b 1
)

if "!NEED_INSTALL!" == "1" (
    echo.
    echo Installing dependencies...
    !PYTHON! -m pip install edge-tts tqdm "fastapi>=0.100.0" "uvicorn[standard]" python-multipart "websockets>=12.0"
    if !errorlevel! neq 0 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
    echo Dependencies installed successfully.
)

echo.
echo Starting...
echo.

!PYTHON! -m txt_to_audiobook.cli %*

exit /b 0

endlocal
