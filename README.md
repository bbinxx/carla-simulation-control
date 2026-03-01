
# 🚦 AI-Based Smart Traffic Control System (CARLA Control Panel v2)

A powerful, high-performance web orchestration platform for the **CARLA Autonomous Driving Simulator**. This system provides a unified interface for real-time monitoring, traffic orchestration, and environment manipulation, designed to streamline autonomous vehicle research and simulation management.

## 🌟 Key Features

### 📡 Real-Time Visual Intelligence
- **Persistent Spectator Sync**: A "follow-cam" system that automatically tracks the simulator's spectator view in the web dashboard.
- **Multi-Camera MJPEG Streaming**: Low-latency, optimized (800x450 @ 25 FPS) video feeds from any camera actor in the world.
- **Dynamic 3D Debug Overlays**: Flicker-free 3D bounding boxes for vehicles, pedestrians, and traffic lights, complete with real-time speed labels and distance-based culling (100m proximity).

### 🛠️ Advanced Traffic Orchestration
- **Modular Spawner**: One-click deployment for Vehicles (Autopilot-enabled), NPCs, Walkers, and Emergency responders.
- **Traffic Manager (TM) Logic**: Integrated behavioral utilities to enforce strict lane discipline and resolve common CARLA navigation loops.
- **Global Signal Control**: Synchronized control over traffic light states (Red, Yellow, Green) and the ability to "freeze" intersection logic for testing.

### 🌤️ Environment & World Management
- **Weather Mastery**: Real-time slider-based controls and presets for all 10+ CARLA weather parameters (rain, sun, wind, fog, humidity).
- **Object Visibility Management**: Semantic-based world object toggling (e.g., hide buildings, trees, or foliage) to simplify or complexify the detection environment.
- **Fast Screenshot Capture**: High-resolution (1280x720) frame capture utility from the current spectator perspective.

---

## 📂 Project Architecture

```text
CARLA_CONTROL/
├── app.py              # Main Flask entry point & Thread-safe background loops
├── core/               # Engine logic (Camera processing, Actor tracking)
├── routes/             # Modular API architecture (Spawning, Traffic, Weather)
├── utils/              # Helper utilities (Behavioral fixes, CARLA API wrappers)
├── static/             # Modern Hud-inspired UI (CSS, JS)
└── templates/          # Single-page Responsive Dashboard
```

---

## 🛠️ Installation & Setup

### Prerequisites
- **CARLA Simulator 0.9.16+** (Running as Server)
- **Python 3.12+**
- **UV** (Recommended for performance and dependency management)

### Quick Start
1. **Launch the CARLA Simulator** (ensure the server is listening on port 2000).
2. **Sync Dependencies**:
   ```bash
   uv sync
   ```
3. **Boot the Control Panel**:
   ```bash
   uv run python app.py
   ```
4. **Access the Web Dashboard**: Navigate to `http://localhost:5000` in your browser.

---

## 🎯 Usage Strategies
- **Connectivity**: Use the sidebar `CONN` button to link the panel to your running CARLA instance.
- **Spectator Mode**: Move your perspective in the CARLA simulation window; the web feed will track your movement automatically.
- **Stability**: If vehicles show erratic behavior, use the "Force Auto-Pilot" or "Fix Lane Discipline" buttons to re-initialize Traffic Manager rules.

---

## 🏗️ Technical Stack
- **Core**: Python, Flask, CARLA Python API
- **Processing**: OpenCV, NumPy, Threading (for non-blocking MJPEG streams)
- **Frontend**: Vanilla HTML5, CSS (Modern HUD aesthetics), and JavaScript (Async Fetch API)

---
*Developed for advanced AI-driven traffic monitoring and autonomous vehicle simulation.*
