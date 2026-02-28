

# 🚦 AI-Based Smart Traffic Control System (CARLA Control)

A comprehensive, modular web interface for real-time monitoring and control of the CARLA simulator. This system provides advanced tools for traffic management, environment manipulation, and AI behavior orchestration.

## 🚀 Features

### 📡 Real-Time Monitoring
- **Live Video Feed**: Low-latency MJPEG stream synchronized with the spectator view.
- **Spectator Tracking**: Live camera actor that follows simulator movement in real-time.
- **Performance Optimized**: Tuned 800x450 resolution at 25 FPS for responsive visual feedback.

### 🛠️ Simulator Control
- **Advanced Spawner**: Custom spawning for Vehicles, NPCs (Auto-pilot), Walkers, and Emergency vehicles.
- **Traffic Manager (TM) Logic**: Integrated behavior utility that prevents common CARLA "driving in circles" bugs via strict lane discipline.
- **Weather Mastery**: Real-time slider-based controls and presets for all CARLA weather parameters.
- **Environment Object Toggle**: Selective hiding/showing of world objects (buildings, foliage, etc.) by semantic label.

### 🔍 Debug & Analysis
- **Smart Bounding Boxes**: Flicker-free 3D debug overlays for vehicles (with speed labels), pedestrians, and traffic lights.
- **Proximity Optimized**: System only renders debug primitives within 100m of the spectator for maximum performance.
- **Traffic Light Control**: Individual or global control over traffic light states (Red, Green, Yellow) including freeze capabilities.

## 📂 Project Structure

```text
CARLA_CONTROL/
├── app.py              # Flask entry point & Background debug loops
├── routes/             # Modular API endpoints
│   ├── main.py         # Live stream & Core UI routes
│   ├── spawner.py      # Vehicle/Actor spawning logic
│   ├── traffic.py      # Traffic light orchestration
│   ├── weather.py      # Environment controls
│   └── environment.py  # Object visibility management
├── utils/              # Core Logic Utilities
│   ├── behaviour.py    # Traffic Manager AI behavior logic
│   └── helpers.py      # Shared CARLA API wrappers
├── static/             # Frontend assets (CSS/JS)
└── templates/          # Responsive UI (index.html)
```

## 🛠️ Installation & Setup

### Prerequisites
- **CARLA Simulator 0.9.16+** (Running as Server)
- **Python 3.12+**
- **UV** (Recommended package manager)

### Installation
1. Ensure your CARLA simulator is running.
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Run the application:
   ```bash
   uv run app.py
   ```
4. Open your browser at `http://localhost:5000`

## ⚙️ Configuration
The system uses a shared state pattern via `config/state.py`. You can adjust core settings like:
- **Default Port**: 2000 (CARLA) / 5000 (Web UI)
- **Target FPS**: Configured via `utils/behaviour.py` and MJPEG sensor ticks.
- **Debug Distances**: Adjustable in `app.py` for bounding box rendering.

## 🎯 Usage Tips
- **Spectator Sync**: Move around in the CARLA window; the Web UI stream follows your perspective automatically.
- **TM Fix**: If vehicles behave oddly, use the "TM Fix All" button to re-apply strict lane discipline rules.
- **ROI Analysis**: Built-in support for MJPEG-level frame analysis for third-party computer vision integration.
