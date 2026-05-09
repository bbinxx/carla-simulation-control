@echo off
setlocal enabledelayedexpansion

:: Configuration
set VENV_DIR=.venv
set REQ_FILE=requirements.txt
set MAIN_APP=app.py

echo ===========================================
echo  CARLA Control Panel - Startup ^& Setup
echo ===========================================

:: -----------------------------------------------
:: 1. Check Python is installed
:: -----------------------------------------------
echo [INFO] Checking for Python...
where python >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARN] Python not found. Attempting to install via winget...
    winget install --id Python.Python.3 -e --source winget --silent
    if !errorlevel! neq 0 (
        echo [ERROR] Automatic Python installation failed.
        echo [HINT]  Please install Python manually from https://www.python.org/downloads/
        echo         Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    echo [INFO] Python installed. Refreshing PATH...
    :: Refresh PATH so python is visible in the current session
    for /f "tokens=*" %%i in ('where python 2^>nul') do set PYTHON_EXE=%%i
    if "!PYTHON_EXE!"=="" (
        echo [ERROR] Python still not found after installation.
        echo [HINT]  Please restart this script or reopen Command Prompt.
        pause
        exit /b 1
    )
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [INFO] Found %%v
)

:: -----------------------------------------------
:: 2. Check / Install uv (optional fast installer)
:: -----------------------------------------------
echo [INFO] Checking for uv...
where uv >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] uv not found. Installing via pip...
    python -m pip install uv --quiet
    if !errorlevel! neq 0 (
        echo [WARN] Could not install uv. Will fall back to pip directly.
    ) else (
        echo [INFO] uv installed successfully.
    )
) else (
    echo [INFO] uv is available.
)

:: -----------------------------------------------
:: 3. Virtual Environment Setup
:: -----------------------------------------------
if not exist "%VENV_DIR%\" (
    echo [INFO] Creating virtual environment...
    where uv >nul 2>&1
    if !errorlevel! == 0 (
        uv venv "%VENV_DIR%"
    ) else (
        python -m venv "%VENV_DIR%"
    )
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Virtual environment already exists.
)

:: -----------------------------------------------
:: 4. Activate
:: -----------------------------------------------
echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: -----------------------------------------------
:: 5. Install Dependencies
:: -----------------------------------------------
if exist "%REQ_FILE%" (
    echo [INFO] Syncing Python dependencies from %REQ_FILE%...
    where uv >nul 2>&1
    if !errorlevel! == 0 (
        uv pip install -r "%REQ_FILE%"
    ) else (
        python -m pip install --upgrade pip --quiet
        pip install -r "%REQ_FILE%"
    )
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install Python requirements.
        pause
        exit /b 1
    )
) else (
    echo [WARN] %REQ_FILE% not found. Skipping dependency installation.
)

:: -----------------------------------------------
:: 6. Verify OpenCV — auto-install if missing
:: -----------------------------------------------
echo [INFO] Verifying OpenCV installation...
python -c "import cv2" >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARN] OpenCV ^(cv2^) not found. Installing opencv-python...
    pip install opencv-python
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install OpenCV. Please run: pip install opencv-python
        pause
        exit /b 1
    )
    python -c "import cv2" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] OpenCV still not importable after install. Check environment.
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('python -c "import cv2; print(cv2.__version__)"') do echo [INFO] OpenCV version: %%v

:: -----------------------------------------------
:: 7. Launch
:: -----------------------------------------------
echo [INFO] Launching %MAIN_APP%...
echo -------------------------------------------
python "%MAIN_APP%"
