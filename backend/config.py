# config.py — PROJECT AEGIS Gesture Control
# All tunable parameters in one place. Nothing hardcoded in other files.

import logging

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
CAMERA_SOURCE = 1                                    # Microsoft LifeCam HD-3000 (USB)
# Alternative sources:
# CAMERA_SOURCE = "rtsp://192.168.1.100:554/stream"  # IP camera RTSP URL
# CAMERA_SOURCE = "http://192.168.1.100:8080/video"  # MJPEG (IP Webcam Android app)
# CAMERA_SOURCE = 0                                   # Integrated webcam (dev fallback)
CAMERA_WIDTH  = 640
CAMERA_HEIGHT = 480
CAMERA_FPS    = 30

# ---------------------------------------------------------------------------
# MediaPipe
# ---------------------------------------------------------------------------
MP_MAX_HANDS          = 2    # Track both hands for two-hand zoom
MP_MIN_DETECTION_CONF = 0.7
MP_MIN_TRACKING_CONF  = 0.6

# ---------------------------------------------------------------------------
# Gesture Recognition
# ---------------------------------------------------------------------------
ZOOM_DIST_RATE_MIN       = 0.015  # minimum |rate of change| of inter-hand distance per window — filters jitter
SWIPE_VELOCITY_THRESHOLD = 0.04  # normalized units/frame — minimum palm velocity for swipe
SWIPE_MIN_FRAMES         = 3     # consecutive movement frames needed to register a swipe
FIST_THRESHOLD           = 0.08  # all fingertips within this dist of palm_center → fist/idle
SMOOTHING_WINDOW         = 5     # rolling average over N frames for position smoothing
GESTURE_COOLDOWN_MS      = 80    # ms between same-gesture events

# Activation zone: (x_min, x_max, y_min, y_max) normalized [0–1]
# Only the centre of the frame triggers gestures — prevents accidental triggers
ACTIVATION_ZONE = (0.2, 0.8, 0.15, 0.85)

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
WS_HOST = "0.0.0.0"
WS_PORT = 8765

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 0.5

# ---------------------------------------------------------------------------
# Map Control (MapLibre zoom/pan sent to browser)
# ---------------------------------------------------------------------------
ZOOM_SPEED  = 0.02   # per-tick zoom increment (in MapLibre zoom levels)
ZOOM_MIN    = 1.0    # minimum MapLibre zoom
ZOOM_MAX    = 20.0   # maximum MapLibre zoom

PAN_SPEED     = 60.0   # pixels per event  (MapLibre panBy)
PAN_SMOOTHING = 0.15   # lerp factor for smooth client-side animation

# Pitch control (hand tilt — wrist as pivot, fingers tilt like airplane nose)
PITCH_TILT_RATE_MIN = 0.03   # min |rate of tilt change| per smoothing window — filters jitter
PITCH_SPEED         = 12.0   # degrees per event sent to frontend
PITCH_MIN           = 0.0    # MapLibre min pitch (degrees)
PITCH_MAX           = 85.0   # MapLibre max pitch (degrees) — MapLibre supports up to 85
PITCH_COOLDOWN_MS   = 50     # tighter cooldown for pitch — allows rapid accumulation

# Bearing control (hand rotation — wrist anchored, hand rotates CW/CCW like compass needle)
BEARING_ANGLE_RATE_MIN = 0.06  # min cumulative angular rotation (radians) per smoothing window
BEARING_SPEED          = 6.0   # degrees of map bearing change per event
BEARING_COOLDOWN_MS    = 50    # ms between bearing events

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL   = logging.DEBUG    # change to logging.INFO for demo
LOG_FILE    = "gesture_control.log"

# Hand-loss timeout: if no hand detected for this many seconds, emit status event
HAND_TIMEOUT_SEC = 5.0
