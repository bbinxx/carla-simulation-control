#!/bin/bash

# Configuration
VENV_DIR=".venv"
REQ_FILE="requirements.txt"
MAIN_APP="app.py"

echo "🚀 Starting CARLA Control Panel..."

# 1. Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv "$VENV_DIR"
    else
        python3 -m venv "$VENV_DIR"
    fi
    
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to create virtual environment."
        exit 1
    fi
fi

# 2. Activate virtual environment
echo "🔌 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 3. Install/Update requirements
if [ -f "$REQ_FILE" ]; then
    echo "🛠 Checking/Installing dependencies..."
    if command -v uv &> /dev/null; then
        uv pip install -r "$REQ_FILE"
    else
        pip install --upgrade pip
        pip install -r "$REQ_FILE"
    fi
    
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install requirements."
        exit 1
    fi
else
    echo "⚠️ Warning: $REQ_FILE not found. Skipping dependency installation."
fi

# 4. Run the application
echo "⚡ Launching application..."
python "$MAIN_APP"
