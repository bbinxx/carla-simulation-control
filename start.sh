#!/bin/bash
cd "$(dirname "$0")"

# Configuration
VENV_DIR=".venv"
REQ_FILE="requirements.txt"
MAIN_APP="app.py"
REQUIRED_PYTHON="3.12"
ERROR_LOG=".setup_error.log"
CARLA_HOST="127.0.0.1"
CARLA_PORT=2000

# Virtual environment python path
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ANSI Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

STATUS_SYS="[ Wait ]"
STATUS_PY="[ Wait ]"
STATUS_UV="[ Wait ]"
STATUS_VENV="[ Wait ]"
STATUS_DEPS="[ Wait ]"
STATUS_CARLA="[ Wait ]"
STATUS_CV2="[ Wait ]"
STATUS_SERVER="[ Wait ]"
SERVER_ADDR="${CARLA_HOST}:${CARLA_PORT}"
CURRENT_ACTION="Starting setup..."

draw_panel() {
    clear
    echo -e "${CYAN}${BOLD}===============================================================================${NC}"
    echo -e "${CYAN}${BOLD}                          CARLA CONTROL PANEL SETUP                            ${NC}"
    echo -e "${CYAN}${BOLD}===============================================================================${NC}"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo -e "  System Libs    : ${STATUS_SYS}"
    fi
    echo -e "  Python 3.12    : ${STATUS_PY}"
    echo -e "  UV Manager     : ${STATUS_UV}"
    echo -e "  Virtual Env    : ${STATUS_VENV}"
    echo -e "  Dependencies   : ${STATUS_DEPS}"
    echo -e "  CARLA module   : ${STATUS_CARLA}"
    echo -e "  OpenCV module  : ${STATUS_CV2}"
    echo -e "  CARLA Server   : ${STATUS_SERVER}"
    echo -e "  Server Address : ${SERVER_ADDR}"
    echo -e "${CYAN}${BOLD}===============================================================================${NC}"
    echo -e "  ACTION         : ${YELLOW}${CURRENT_ACTION}${NC}"
    echo -e "${CYAN}${BOLD}===============================================================================${NC}"
}

draw_panel

# 1. System Dependency Check (Linux specific for OpenCV)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CURRENT_ACTION="Checking system dependencies for OpenCV..."
    STATUS_SYS="${YELLOW}[ Checking ]${NC}"
    draw_panel
    
    MISSING_LIBS=()
    for lib in libGL.so.1 libglib-2.0.so.0; do
        if ! ldconfig -p | grep -q "$lib"; then
            MISSING_LIBS+=("$lib")
        fi
    done

    if [ ${#MISSING_LIBS[@]} -gt 0 ]; then
        CURRENT_ACTION="Missing libs: ${MISSING_LIBS[*]}. Installing..."
        STATUS_SYS="${YELLOW}[ Installing ]${NC}"
        draw_panel
        sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libglib2.0-0 > "$ERROR_LOG" 2>&1
        if [ $? -ne 0 ]; then
            STATUS_SYS="${RED}[ ERROR ]${NC}"
            CURRENT_ACTION="Failed to install system libs."
            draw_panel
            echo -e "\n================ ERROR LOG ================"
            cat "$ERROR_LOG"
            echo -e "==========================================="
            exit 1
        fi
        STATUS_SYS="${GREEN}[ OK ] Installed${NC}"
    else
        STATUS_SYS="${GREEN}[ OK ] Found${NC}"
    fi
    draw_panel
fi

# 1.5. Check Python 3.12
CURRENT_ACTION="Locating Python $REQUIRED_PYTHON..."
STATUS_PY="${YELLOW}[ Search ]${NC}"
draw_panel

if command -v python3.12 &> /dev/null; then
    PYTHON_EXE="python3.12"
    PY_VER_STR=$(python3.12 --version)
    STATUS_PY="${GREEN}[ OK ] ${PY_VER_STR}${NC}"
elif command -v python3 &> /dev/null && python3 --version | grep -q "3.12"; then
    PYTHON_EXE="python3"
    PY_VER_STR=$(python3 --version)
    STATUS_PY="${GREEN}[ OK ] ${PY_VER_STR}${NC}"
else
    STATUS_PY="${RED}[ ERROR ] Not Found${NC}"
    CURRENT_ACTION="Python 3.12 is required but was not found."
    draw_panel
    echo -e "${RED}Error: Python 3.12 is required for CARLA 0.9.16.${NC}"
    echo "Please install Python 3.12: sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update && sudo apt install python3.12 python3.12-venv"
    exit 1
fi
draw_panel

# 2. Check / Install uv
CURRENT_ACTION="Checking for uv..."
STATUS_UV="${YELLOW}[ Search ]${NC}"
draw_panel

if command -v uv &> /dev/null; then
    STATUS_UV="${GREEN}[ OK ] Available${NC}"
else
    CURRENT_ACTION="Installing uv..."
    STATUS_UV="${YELLOW}[ Installing ]${NC}"
    draw_panel
    $PYTHON_EXE -m pip install uv --user --quiet > "$ERROR_LOG" 2>&1 || {
        STATUS_UV="${YELLOW}[ WARN ] Fallback to pip${NC}"
    }
    if command -v uv &> /dev/null; then
        STATUS_UV="${GREEN}[ OK ] Installed${NC}"
    fi
fi
draw_panel

# 3. Virtual Environment Setup
CURRENT_ACTION="Checking virtual environment..."
STATUS_VENV="${YELLOW}[ Check ]${NC}"
draw_panel

if [ -d "$VENV_DIR" ]; then
    if [ -f "$VENV_PYTHON" ]; then
        VENV_PY_VER=$("$VENV_PYTHON" --version 2>&1)
        if echo "$VENV_PY_VER" | grep -q "$REQUIRED_PYTHON"; then
            STATUS_VENV="${GREEN}[ OK ] Exists ($VENV_PY_VER)${NC}"
        else
            CURRENT_ACTION="Rebuilding venv (Found $VENV_PY_VER)..."
            STATUS_VENV="${YELLOW}[ Rebuild ]${NC}"
            draw_panel
            rm -rf "$VENV_DIR"
        fi
    else
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    CURRENT_ACTION="Creating virtual environment..."
    STATUS_VENV="${YELLOW}[ Creating ]${NC}"
    draw_panel
    if command -v uv &> /dev/null; then
        uv venv "$VENV_DIR" --python "$REQUIRED_PYTHON" > "$ERROR_LOG" 2>&1
    else
        $PYTHON_EXE -m venv "$VENV_DIR" > "$ERROR_LOG" 2>&1
    fi
    
    if [ $? -ne 0 ]; then
        STATUS_VENV="${RED}[ ERROR ]${NC}"
        CURRENT_ACTION="Failed to create virtual environment."
        draw_panel
        echo -e "${RED}Error: Failed to create venv. You might need: sudo apt install python3.12-venv${NC}"
        echo -e "\n================ ERROR LOG ================"
        cat "$ERROR_LOG"
        echo -e "==========================================="
        exit 1
    fi
    STATUS_VENV="${GREEN}[ OK ] Created${NC}"
fi
draw_panel

# 4. Dependency Installation
CURRENT_ACTION="Installing Python dependencies..."
STATUS_DEPS="${YELLOW}[ Installing ]${NC}"
draw_panel

if [ -f "$REQ_FILE" ]; then
    if command -v uv &> /dev/null; then
        uv pip install -r "$REQ_FILE" --python "$VENV_PYTHON" > "$ERROR_LOG" 2>&1
    else
        "$VENV_PYTHON" -m pip install --upgrade pip > "$ERROR_LOG" 2>&1
        "$VENV_PIP" install -r "$REQ_FILE" >> "$ERROR_LOG" 2>&1
    fi
    
    if [ $? -ne 0 ]; then
        STATUS_DEPS="${RED}[ ERROR ]${NC}"
        CURRENT_ACTION="Failed to install Python requirements."
        draw_panel
        echo -e "\n================ ERROR LOG ================"
        cat "$ERROR_LOG"
        echo -e "==========================================="
        exit 1
    fi
    STATUS_DEPS="${GREEN}[ OK ] Synced${NC}"
else
    STATUS_DEPS="${YELLOW}[ WARN ] $REQ_FILE not found${NC}"
fi
draw_panel

# 5. Verify CARLA
CURRENT_ACTION="Verifying CARLA module installation..."
STATUS_CARLA="${YELLOW}[ Checking ]${NC}"
draw_panel

"$VENV_PYTHON" -c "import carla" > "$ERROR_LOG" 2>&1
if [ $? -ne 0 ]; then
    STATUS_CARLA="${RED}[ ERROR ]${NC}"
    CURRENT_ACTION="CARLA import failed. Check dependencies."
    draw_panel
    echo -e "\n================ ERROR LOG ================"
    cat "$ERROR_LOG"
    echo -e "==========================================="
    exit 1
else
    STATUS_CARLA="${GREEN}[ OK ] Imported${NC}"
fi
draw_panel

# 6. Verify OpenCV
CURRENT_ACTION="Verifying OpenCV module installation..."
STATUS_CV2="${YELLOW}[ Checking ]${NC}"
draw_panel

CV2_VER=$("$VENV_PYTHON" -c "import cv2; print(cv2.__version__)" 2>/dev/null)
if [ $? -eq 0 ]; then
    STATUS_CV2="${GREEN}[ OK ] ${CV2_VER}${NC}"
else
    CURRENT_ACTION="Installing OpenCV..."
    STATUS_CV2="${YELLOW}[ Installing ]${NC}"
    draw_panel
    "$VENV_PIP" install opencv-python --quiet > "$ERROR_LOG" 2>&1
    CV2_VER=$("$VENV_PYTHON" -c "import cv2; print(cv2.__version__)" 2>/dev/null)
    STATUS_CV2="${GREEN}[ OK ] ${CV2_VER}${NC}"
fi
draw_panel

# 7. Check CARLA Server
CURRENT_ACTION="Checking CARLA Server status..."
STATUS_SERVER="${YELLOW}[ Checking ]${NC}"
draw_panel

cat << EOF > check_server.py
import carla
host = '${CARLA_HOST}'
port = ${CARLA_PORT}
try:
    client = carla.Client(host, port)
    client.set_timeout(2.0)
    version = client.get_server_version()
    print(f"OK|{host}:{port}|{version}")
except Exception as e:
    print(f"FAIL|{host}:{port}|-")
EOF

SERVER_STATUS=$("$VENV_PYTHON" check_server.py)
rm -f check_server.py

STATUS_CODE=$(echo "$SERVER_STATUS" | cut -d'|' -f1)
ADDRESS=$(echo "$SERVER_STATUS" | cut -d'|' -f2)
VER=$(echo "$SERVER_STATUS" | cut -d'|' -f3)

if [ "$STATUS_CODE" == "OK" ]; then
    STATUS_SERVER="${GREEN}[ OK ] Online (v${VER})${NC}"
else
    STATUS_SERVER="${YELLOW}[ WARN ] Offline${NC}"
fi
draw_panel

# Clean up log
[ -f "$ERROR_LOG" ] && rm "$ERROR_LOG"

# 8. Launch
CURRENT_ACTION="Launching $MAIN_APP..."
draw_panel

echo ""
source "$VENV_DIR/bin/activate"
python "$MAIN_APP"
