@echo off
SETLOCAL EnableDelayedExpansion

:: --- STEP 1: INSTALL PYTHON 3.14 ---
echo [1/3] Checking for Python 3.14...

python --version 2>NUL | findstr /C:"3.14" >NUL
if %ERRORLEVEL% EQU 0 (
    echo Python 3.14 Installation Found.
) else (
    echo Python 3.14 Not Found. Installing...
    winget install -e --id Python.Python.3.14 --scope machine --override "/passive PrependPath=1"
    
    if %ERRORLEVEL% NEQ 0 (
        echo Installation failed. Please run this script as an administrator.
        pause
        exit /b
    )
    echo Python 3.14 Installation Successful.
)

:: --- STEP 2: CREATE VIRTUAL ENVIRONMENT ---
echo.
echo [2/3] Creating Python Virtual Environment...

:: Define the standard installation path for Python 3.14 (64-bit)
SET "PY_PATH=C:\Program Files\Python314\python.exe"

:: Check if the executable exists at the expected path
if exist "!PY_PATH!" (
    "!PY_PATH!" -m venv env
) else (
    :: Fallback to the global command if the path differs
    python -m venv env
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Virtual environment 'env' created successfully.
) else (
    echo.
    echo Failed to create virtual environment. Please check your Python installation.
    pause
    ENDLOCAL
    exit /b
)

:: --- STEP 3: INSTALL REQUIREMENTS ---
echo.
echo [3/3] Installing packages from requirements.txt...

if not exist requirements.txt (
    echo requirements.txt not found. Skipping package installation.
) else if not exist "env\Scripts\activate.bat" (
    echo Virtual environment activation script not found. Cannot install packages.
) else (
    call env\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
)

echo Installation complete.

pause
ENDLOCAL
