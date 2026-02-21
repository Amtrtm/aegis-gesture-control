# PROJECT AEGIS — Gesture-Based MapLibre Control

Real-time hand gesture recognition that controls the **ShobNG** tactical
MapLibre display using an IP camera and MediaPipe Hands.

```
[IP Camera]  →  Python Backend  →  WebSocket  →  Browser (ShobNG / MapLibre)
```

---

## Quick Start

### 1. Install Python dependencies

```bash
cd aegis-gesture-control/backend
pip install -r requirements.txt
```

### 2. Test your camera first

```bash
# Local webcam
python debug/test_camera.py --source 0

# IP camera (MJPEG — most reliable)
python debug/test_camera.py --source http://192.168.1.x:8080/video

# RTSP
python debug/test_camera.py --source rtsp://192.168.1.x:554/stream
```

### 3. Start the backend

```bash
# With camera + debug visualiser
python backend/main.py --source 0 --debug

# Headless (production)
python backend/main.py --source http://phone-ip:8080/video

# No-camera keyboard fallback (for demo resilience)
python backend/main.py --no-camera
```

The WebSocket server starts on **`ws://0.0.0.0:8765`**.

### 4a. Use the standalone test page

Open `frontend/index.html` in a browser.  
The MapLibre map loads with the ShobNG default view (Haifa).  
The HUD in the bottom-left shows connection status.

### 4b. Use with ShobNG

AEGIS ships a self-contained plugin installer — no commits to the ShobNG repo needed.

**Windows:**
```powershell
# From the aegis-gesture-control directory:
.\install.ps1
# or specify ShobNG path explicitly:
.\install.ps1 -ShobNGPath "C:\Projects\ShobNG"
```

**Linux / macOS / WSL:**
```bash
./install.sh
# or:
./install.sh /path/to/ShobNG
```

The installer copies `shobng-plugin/frontend/src/plugins/gesture-control/` into your
ShobNG installation and prints the next steps.

Then start ShobNG normally and:
1. Open the **Plugins** panel in the sidebar.
2. Find **Gesture Control** → enable it.
3. Click the **›** chevron to expand the config panel.
4. Confirm the WebSocket URL matches your backend, click **Apply & Reconnect**.

---

## Architecture

```
aegis-gesture-control/
├── backend/
│   ├── main.py               Entry point (asyncio + threading)
│   ├── camera_capture.py     Threaded RTSP/MJPEG frame grabber
│   ├── hand_detector.py      MediaPipe Hands wrapper (BGR→RGB→landmarks)
│   ├── gesture_recognizer.py Stateful state machine (pinch, swipe, fist)
│   ├── websocket_server.py   Async broadcast server + heartbeat
│   ├── config.py             All tunable parameters
│   └── requirements.txt
├── frontend/
│   ├── gesture_client.js     GestureController class (MapLibre)
│   ├── index.html            Standalone MapLibre test page
│   └── style.css
├── debug/
│   ├── visualizer.py         OpenCV overlay (landmarks, zones, FPS)
│   └── test_camera.py        Camera connectivity test
└── docs/
    └── GESTURES.md           Gesture reference card
```

**ShobNG plugin** lives at:
`ShobNG/frontend/src/plugins/gesture-control/`

---

## Gestures → MapLibre Actions

| Hands | Gesture | MapLibre call |
|-------|---------|--------------|
| 2 | Distance increasing | `map.easeTo({ zoom: zoom - Δ })` |
| 2 | Distance decreasing | `map.easeTo({ zoom: zoom + Δ })` |
| 2 | Both hands tilt up (nose-up) | `map.easeTo({ pitch: pitch + Δ })` |
| 2 | Both hands tilt down (nose-down) | `map.easeTo({ pitch: pitch - Δ })` |
| 1 | ✊ Fist / no hand | Idle, no action |
| 1 | 👋 Swipe left | `map.panBy([-px, 0])` |
| 1 | 👋 Swipe right | `map.panBy([+px, 0])` |
| 1 | 🧭 Rotate CW | `map.easeTo({ bearing: bearing + Δ })` |
| 1 | 🧭 Rotate CCW | `map.easeTo({ bearing: bearing - Δ })` |

---

## Keyboard Fallback (`--no-camera`)

| Key | Action |
|-----|--------|
| `W` | Zoom in |
| `S` | Zoom out |
| `A` | Pan left |
| `D` | Pan right |
| `Space` | Idle / reset |

Sends identical WebSocket messages to the browser — the frontend cannot
tell the difference.  Use this if the camera or MediaPipe fails during
the demo.

---

## Configuration

All tunable values live in `backend/config.py`.  
See `docs/GESTURES.md` for gesture tuning guidance.

---

## WebSocket Message Format

**Gesture event:**
```json
{ "type": "gesture", "gesture": "zoom_in", "intensity": 0.42, "velocity": 0.0, "timestamp": 1703001234567 }
```

**Heartbeat (every 500 ms):**
```json
{ "type": "heartbeat", "hand_detected": true, "fps": 28.5, "active_gesture": "idle" }
```

**Status:**
```json
{ "type": "status", "camera": "disconnected" }
{ "type": "status", "hand_timeout": true }
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| End-to-end latency | < 150 ms |
| Backend FPS | ≥ 25 fps |
| CPU usage | < 40% one core |

---

*PROJECT AEGIS — AI-Orchestrated Tactical Command Demo*
