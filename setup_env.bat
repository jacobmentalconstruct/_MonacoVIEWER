@echo off
setlocal EnableDelayedExpansion

echo [SYSTEM] Initializing Systems Thinker environment...

:: --- 1. Python Version Check ---
:: We need a stable version (3.10, 3.11, or 3.12) because 3.14 breaks pythonnet.
:: We check for specific versions in order of preference.

set "TARGET_PY="

:: Check for 3.11 (Ideal)
py -3.11 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "TARGET_PY=py -3.11"
    goto :FOUND_PYTHON
)

:: Check for 3.12 (Backup)
py -3.12 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "TARGET_PY=py -3.12"
    goto :FOUND_PYTHON
)

:: Check for 3.10 (Backup)
py -3.10 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "TARGET_PY=py -3.10"
    goto :FOUND_PYTHON
)

:: Fallback warning if only 3.14/other exists
echo [WARNING] Could not find Python 3.10, 3.11, or 3.12.
echo [WARNING] Attempting with default 'py' (This may fail if version is 3.14+)...
set "TARGET_PY=py"

:FOUND_PYTHON
echo [SYSTEM] Using Python interpreter: %TARGET_PY%

:: --- 2. Clean/Create Venv ---
:: If .venv exists but might be broken (wrong version), prompt to rebuild? 
:: For now, we will trust the existing one OR you can delete it manually to force rebuild.
if not exist .venv (
    echo [SYSTEM] Creating .venv...
    %TARGET_PY% -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create venv. Ensure you have the requested Python version installed.
        pause
        exit /b 1
    )
) else (
    echo [SYSTEM] Found existing .venv.
)

:: --- 3. Install Dependencies ---
echo [SYSTEM] Upgrading pip and installing requirements...
.venv\Scripts\python.exe -m pip install --upgrade pip

if exist requirements.txt (
    .venv\Scripts\pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [ERROR] Dependency installation failed!
        echo [TIP] If this is a 'pythonnet' error, please install Python 3.11 specifically.
        pause
        exit /b 1
    )
)

echo.
echo [SUCCESS] Environment ready!
echo [INFO] Launch pattern: .venv\Scripts\python -m src.app
pause