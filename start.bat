@echo off
setlocal enabledelayedexpansion

:: Configuration
set VENV_DIR=.venv
set REQ_FILE=requirements.txt
set MAIN_APP=app.py
set REQUIRED_PYTHON=3.12
set ERROR_LOG=.setup_error.log
set CARLA_HOST=127.0.0.1
set CARLA_PORT=2000

:: Virtual environment python path
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

:: Initial Status
set "STATUS_PY=[ Wait ]"
set "STATUS_UV=[ Wait ]"
set "STATUS_VENV=[ Wait ]"
set "STATUS_DEPS=[ Wait ]"
set "STATUS_CARLA=[ Wait ]"
set "STATUS_CV2=[ Wait ]"
set "STATUS_SERVER=[ Wait ]"
set "SERVER_ADDR=%CARLA_HOST%:%CARLA_PORT%"
set "CURRENT_ACTION=Starting setup..."

call :draw_panel

:: -----------------------------------------------
:: 1. Locate Python 3.12
:: -----------------------------------------------
set "CURRENT_ACTION=Locating Python %REQUIRED_PYTHON%..."
set "STATUS_PY=[ Search ]"
call :draw_panel

set PYTHON_EXE=

py -%REQUIRED_PYTHON% --version >nul 2>&1
if !errorlevel! == 0 (
    set "PYTHON_EXE=py -%REQUIRED_PYTHON%"
    for /f "tokens=*" %%v in ('py -%REQUIRED_PYTHON% --version 2^>^&1') do set "PY_VER_STR=%%v (Launcher)"
    goto :python_found
)

python3.12 --version >nul 2>&1
if !errorlevel! == 0 (
    set "PYTHON_EXE=python3.12"
    for /f "tokens=*" %%v in ('python3.12 --version 2^>^&1') do set "PY_VER_STR=%%v (PATH)"
    goto :python_found
)

python --version >nul 2>&1
if !errorlevel! == 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo !PY_VER! | findstr /b "3.12" >nul
    if !errorlevel! == 0 (
        set "PYTHON_EXE=python"
        set "PY_VER_STR=Python !PY_VER! (Default)"
        goto :python_found
    )
)

set "STATUS_PY=[ ERROR ]"
set "CURRENT_ACTION=Python 3.12 not found. CARLA 0.9.16 requires 3.12."
call :draw_panel
echo.
echo [HINT] CARLA 0.9.16 only provides wheels for Python 3.10, 3.11, 3.12.
echo [HINT] To fix this:
echo [HINT]   1. Download Python 3.12 from https://www.python.org/downloads/release/python-31211/
echo [HINT]   2. Run the installer, check "Add Python to PATH"
echo [HINT]   3. Re-run this script
echo.
pause
exit /b 1

:python_found
set "STATUS_PY=[ OK ] !PY_VER_STR!"
call :draw_panel

:: -----------------------------------------------
:: 2. Check / Install uv
:: -----------------------------------------------
set "CURRENT_ACTION=Checking for uv..."
set "STATUS_UV=[ Search ]"
call :draw_panel

where uv >nul 2>&1
if !errorlevel! neq 0 (
    set "CURRENT_ACTION=Installing uv via pip..."
    set "STATUS_UV=[ Installing ]"
    call :draw_panel
    !PYTHON_EXE! -m pip install uv --quiet > "%ERROR_LOG%" 2>&1
    if !errorlevel! neq 0 (
        set "STATUS_UV=[ WARN ] Fallback to pip"
    ) else (
        set "STATUS_UV=[ OK ] Installed"
    )
) else (
    set "STATUS_UV=[ OK ] Available"
)
call :draw_panel

:: -----------------------------------------------
:: 3. Virtual Environment Setup
:: -----------------------------------------------
set "CURRENT_ACTION=Checking virtual environment..."
set "STATUS_VENV=[ Check ]"
call :draw_panel

if exist "%VENV_DIR%\" (
    if exist "%VENV_PYTHON%" (
        for /f "tokens=2" %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do set VENV_PY_VER=%%v
        echo !VENV_PY_VER! | findstr /b "%REQUIRED_PYTHON%" >nul
        if !errorlevel! neq 0 (
            set "CURRENT_ACTION=Rebuilding venv (Found !VENV_PY_VER!)..."
            set "STATUS_VENV=[ Rebuild ]"
            call :draw_panel
            rmdir /s /q "%VENV_DIR%"
        ) else (
            set "STATUS_VENV=[ OK ] Exists (!VENV_PY_VER!)"
        )
    ) else (
        rmdir /s /q "%VENV_DIR%"
    )
)

if not exist "%VENV_DIR%\" (
    set "CURRENT_ACTION=Creating virtual environment..."
    set "STATUS_VENV=[ Creating ]"
    call :draw_panel
    where uv >nul 2>&1
    if !errorlevel! == 0 (
        uv venv "%VENV_DIR%" --python "%REQUIRED_PYTHON%" > "%ERROR_LOG%" 2>&1
    ) else (
        !PYTHON_EXE! -m venv "%VENV_DIR%" > "%ERROR_LOG%" 2>&1
    )
    if !errorlevel! neq 0 (
        set "STATUS_VENV=[ ERROR ]"
        set "CURRENT_ACTION=Failed to create virtual environment."
        call :draw_panel
        echo.
        echo ================= ERROR LOG =================
        type "%ERROR_LOG%"
        echo =============================================
        pause
        exit /b 1
    )
    set "STATUS_VENV=[ OK ] Created"
)
call :draw_panel

:: -----------------------------------------------
:: 4. Install Dependencies
:: -----------------------------------------------
set "CURRENT_ACTION=Installing Python dependencies..."
set "STATUS_DEPS=[ Installing ]"
call :draw_panel

if exist "%REQ_FILE%" (
    where uv >nul 2>&1
    if !errorlevel! == 0 (
        uv pip install -r "%REQ_FILE%" --python "%VENV_PYTHON%" > "%ERROR_LOG%" 2>&1
    ) else (
        "%VENV_PYTHON%" -m pip install --upgrade pip > "%ERROR_LOG%" 2>&1
        "%VENV_PIP%" install -r "%REQ_FILE%" >> "%ERROR_LOG%" 2>&1
    )
    if !errorlevel! neq 0 (
        set "STATUS_DEPS=[ ERROR ]"
        set "CURRENT_ACTION=Failed to install Python requirements."
        call :draw_panel
        echo.
        echo ================= ERROR LOG =================
        type "%ERROR_LOG%"
        echo =============================================
        pause
        exit /b 1
    )
    set "STATUS_DEPS=[ OK ] Synced"
) else (
    set "STATUS_DEPS=[ WARN ] %REQ_FILE% not found"
)
call :draw_panel

:: -----------------------------------------------
:: 5. Verify key imports
:: -----------------------------------------------
set "CURRENT_ACTION=Verifying CARLA module installation..."
set "STATUS_CARLA=[ Checking ]"
call :draw_panel

"%VENV_PYTHON%" -c "import carla" > "%ERROR_LOG%" 2>&1
if !errorlevel! neq 0 (
    set "STATUS_CARLA=[ ERROR ]"
    set "CURRENT_ACTION=CARLA import failed. Check dependencies."
    call :draw_panel
    echo.
    echo ================= ERROR LOG =================
    type "%ERROR_LOG%"
    echo =============================================
    pause
    exit /b 1
) else (
    set "STATUS_CARLA=[ OK ] Imported"
)
call :draw_panel

set "CURRENT_ACTION=Verifying OpenCV module installation..."
set "STATUS_CV2=[ Checking ]"
call :draw_panel

"%VENV_PYTHON%" -c "import cv2" > "%ERROR_LOG%" 2>&1
if !errorlevel! neq 0 (
    set "CURRENT_ACTION=Installing OpenCV..."
    set "STATUS_CV2=[ Installing ]"
    call :draw_panel
    "%VENV_PIP%" install opencv-python --quiet > "%ERROR_LOG%" 2>&1
    set "STATUS_CV2=[ OK ] Installed"
) else (
    for /f "tokens=*" %%v in ('"%VENV_PYTHON%" -c "import cv2; print(cv2.__version__)"') do set "CV2_VER=%%v"
    set "STATUS_CV2=[ OK ] !CV2_VER!"
)
call :draw_panel

:: -----------------------------------------------
:: 6. Check CARLA Server
:: -----------------------------------------------
set "CURRENT_ACTION=Checking CARLA Server status..."
set "STATUS_SERVER=[ Checking ]"
call :draw_panel

echo import carla > check_server.py
echo host = '%CARLA_HOST%' >> check_server.py
echo port = %CARLA_PORT% >> check_server.py
echo try: >> check_server.py
echo     client = carla.Client(host, port) >> check_server.py
echo     client.set_timeout(2.0) >> check_server.py
echo     version = client.get_server_version() >> check_server.py
echo     print(f"OK^|{host}:{port}^|{version}") >> check_server.py
echo except Exception as e: >> check_server.py
echo     print(f"FAIL^|{host}:{port}^|-") >> check_server.py

for /f "tokens=1,2,3 delims=|" %%a in ('"%VENV_PYTHON%" check_server.py') do (
    if "%%a"=="OK" (
        set "STATUS_SERVER=[ OK ] Online (v%%c)"
    ) else (
        set "STATUS_SERVER=[ WARN ] Offline"
    )
)
if exist check_server.py del check_server.py
call :draw_panel

:: Clean up log
if exist "%ERROR_LOG%" del "%ERROR_LOG%"

:: -----------------------------------------------
:: 7. Launch
:: -----------------------------------------------
set "CURRENT_ACTION=Launching %MAIN_APP%..."
call :draw_panel

echo.
:: Activate venv explicitly before launch to ensure the app environment is complete
call "%VENV_DIR%\Scripts\activate.bat"
python "%MAIN_APP%"
goto :eof

:: ===============================================
:: Panel Drawing Function
:: ===============================================
:draw_panel
cls
echo ===============================================================================
echo                           CARLA CONTROL PANEL SETUP
echo ===============================================================================
echo   Python 3.12    : !STATUS_PY!
echo   UV Manager     : !STATUS_UV!
echo   Virtual Env    : !STATUS_VENV!
echo   Dependencies   : !STATUS_DEPS!
echo   CARLA module   : !STATUS_CARLA!
echo   OpenCV module  : !STATUS_CV2!
echo   CARLA Server   : !STATUS_SERVER!
echo   Server Address : !SERVER_ADDR!
echo ===============================================================================
echo   ACTION         : !CURRENT_ACTION!
echo ===============================================================================
exit /b
