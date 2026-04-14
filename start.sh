#!/bin/bash

# Configuration
VENV_DIR=".venv"
REQ_FILE="requirements.txt"
MAIN_APP="app.py"

echo "==========================================="
echo "🚀 CARLA Control Panel - Startup & Setup"
echo "==========================================="

# 1. System Dependency Check (Linux specific for OpenCV)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🔍 Checking system dependencies for OpenCV..."
    MISSING_LIBS=()
    for lib in libGL.so.1 libglib-2.0.so.0; do
        if ! ldconfig -p | grep -q "$lib"; then
            MISSING_LIBS+=("$lib")
        fi
    done

    if [ ${#MISSING_LIBS[@]} -gt 0 ]; then
        echo "⚠️ Missing system libraries: ${MISSING_LIBS[*]}"
        echo "💡 These are required for OpenCV (cv2). Attempting to fix..."
        echo "   Please enter your password if prompted for: sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libglib2.0-0"
        sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
    else
        echo "✅ System dependencies look good."
    fi
fi

# 2. Virtual Environment Setup
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv "$VENV_DIR"
    else
        python3 -m venv "$VENV_DIR" || {
            echo "❌ Error: Failed to create venv. You might need: sudo apt install python3-venv"
            exit 1
        }
    fi
fi

# 3. Activation
echo "🔌 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 4. Dependency Installation
if [ -f "$REQ_FILE" ]; then
    echo "🛠 Syncing Python dependencies..."
    if command -v uv &> /dev/null; then
        uv pip install -r "$REQ_FILE"
    else
        pip install --upgrade pip
        pip install -r "$REQ_FILE"
    fi
    
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install Python requirements."
        exit 1
    fi
else
    echo "⚠️ Warning: $REQ_FILE not found."
fi

# 5. Final Verification for cv2
echo "🧪 Verifying OpenCV installation..."
if ! python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" &> /dev/null; then
    echo "❌ CRITICAL: OpenCV (cv2) is still not found in the environment."
    echo "💡 Try running: pip install opencv-python"
    exit 1
fi

# 6. Launch
echo "⚡ Launching $MAIN_APP..."
echo "-------------------------------------------"
python "$MAIN_APP"

