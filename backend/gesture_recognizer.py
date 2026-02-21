"""
gesture_recognizer.py — Stateful gesture recognition.

Consumes multi-hand data from HandDetector and emits gesture events.

Routing by hand count
----------------------
2 hands  →  distance changing  → zoom in / zoom out
           distance stable     → both hands tilt together → pitch up / pitch down
1 hand   →  lateral velocity   → pan left / pan right  (swipe)
           rotation in place   → bearing CW / bearing CCW
0 hands  →  IDLE               (reset all state)

All states fall back to IDLE when no hand is detected or hands leave
the activation zone.
"""

import math
import time
from collections import deque
from typing import Optional

import config


# ── State constants ──────────────────────────────────────────────────────────
STATE_IDLE        = "idle"
STATE_ZOOM        = "zoom"
STATE_SWIPE_LEFT  = "swipe_left"
STATE_SWIPE_RIGHT = "swipe_right"
STATE_PITCH_UP    = "pitch_up"
STATE_PITCH_DOWN  = "pitch_down"
STATE_BEARING_CW  = "bearing_cw"
STATE_BEARING_CCW = "bearing_ccw"


def _dist2d(a, b) -> float:
    """Euclidean distance between two (x, y[, z]) tuples (uses only x, y)."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


class GestureRecognizer:
    """
    Stateful gesture recogniser.

    Call ``update(hand_data)`` every frame.  Returns a gesture event dict
    or ``None`` when there is nothing to report (cooldown / idle / no change).

    Event formats
    -------------
    { "gesture": "zoom_in",   "intensity": float }
    { "gesture": "zoom_out",  "intensity": float }
    { "gesture": "pan_left",  "velocity":  float }
    { "gesture": "pan_right", "velocity":  float }
    { "gesture": "idle" }

    Input format (hand_data from HandDetector)
    ------------------------------------------
    {
        "detected":   bool,
        "hand_count": int,
        "hands": [
            { "landmarks": {...}, "palm_center": (x, y), "handedness": str, "raw": ... },
            ...
        ]
    }
    """

    def __init__(self):
        self._state = STATE_IDLE

        # Rolling inter-hand distance buffer (two-hand zoom)
        self._dist_buf: deque = deque(maxlen=config.SMOOTHING_WINDOW)

        # Rolling palm position buffer for single-hand swipe (x coords)
        self._palm_buf: deque = deque(maxlen=config.SMOOTHING_WINDOW)

        # Rolling tilt angle buffer for pitch gesture (wrist→middle_mcp vertical component)
        self._tilt_buf: deque = deque(maxlen=config.SMOOTHING_WINDOW)

        # Rolling angle buffer for bearing gesture (atan2 of wrist→middle_mcp, radians)
        self._angle_buf: deque = deque(maxlen=config.SMOOTHING_WINDOW)

        # Swipe frame counters
        self._swipe_frames_left  = 0
        self._swipe_frames_right = 0

        # Swipe coasting: once a direction is confirmed, keep emitting for N
        # more frames even when velocity momentarily drops below threshold.
        # This prevents short wobbles from killing an active pan.
        self._coast_dir:    int = 0    # -1 = left, +1 = right, 0 = none
        self._coast_frames: int = 0    # frames remaining in coast
        self._COAST_MAX = 12           # frames to coast after velocity drops

        # Cooldown timestamps per gesture type  { gesture_type: last_emit_time }
        self._cooldowns: dict = {}

    # ── Public ───────────────────────────────────────────────────────────────

    def update(self, hand_data: dict) -> Optional[dict]:
        """
        Process one frame of hand data and return a gesture event or None.

        Parameters
        ----------
        hand_data : dict   output of HandDetector.process()
        """
        if not hand_data.get("detected"):
            self._reset_buffers()
            self._state = STATE_IDLE
            return None

        hand_count = hand_data.get("hand_count", 0)
        hands = hand_data.get("hands", [])

        # ── Two-hand: zoom or pitch ────────────────────────────────────────
        if hand_count >= 2:
            return self._eval_two_hand(hands[0], hands[1])

        # ── Single-hand: swipe or bearing ─────────────────────────────────
        if hand_count == 1:
            return self._eval_single_hand(hands[0])

        self._reset_buffers()
        self._state = STATE_IDLE
        return None

    # ── Private helpers ──────────────────────────────────────────────────────

    def _in_activation_zone(self, palm_center) -> bool:
        x, y = palm_center
        xmin, xmax, ymin, ymax = config.ACTIVATION_ZONE
        return xmin <= x <= xmax and ymin <= y <= ymax

    def _eval_two_hand(self, hand_a: dict, hand_b: dict) -> Optional[dict]:
        """
        Two-hand routing:
          distance changing  → zoom in / zoom out
          distance stable    → both hands tilting together → pitch up / pitch down
        """
        # Reset single-hand state
        self._palm_buf.clear()
        self._angle_buf.clear()
        self._swipe_frames_left  = 0
        self._swipe_frames_right = 0

        pc_a = hand_a["palm_center"]
        pc_b = hand_b["palm_center"]

        if not self._in_activation_zone(pc_a) and not self._in_activation_zone(pc_b):
            self._dist_buf.clear()
            self._tilt_buf.clear()
            return None

        # Always accumulate both buffers in parallel
        self._dist_buf.append(_dist2d(pc_a, pc_b))

        ndy_a = self._hand_norm_dy(hand_a)
        ndy_b = self._hand_norm_dy(hand_b)
        if ndy_a is not None and ndy_b is not None:
            self._tilt_buf.append((ndy_a + ndy_b) / 2.0)

        if len(self._dist_buf) < 2:
            return None

        dist_rate = self._dist_buf[-1] - self._dist_buf[0]

        # Zoom takes priority when distance is actively changing
        if abs(dist_rate) >= config.ZOOM_DIST_RATE_MIN:
            self._state = STATE_ZOOM
            gesture   = "zoom_out" if dist_rate > 0 else "zoom_in"
            intensity = min(abs(dist_rate) / 0.3, 1.0)
            if not self._can_emit(gesture):
                return None
            self._record_emit(gesture)
            return {"gesture": gesture, "intensity": round(intensity, 3)}

        # Distance stable → both-hand shared tilt → pitch
        return self._eval_two_hand_pitch()

    def _hand_norm_dy(self, hand: dict) -> Optional[float]:
        """Normalised vertical component of wrist→middle_mcp for one hand."""
        wrist      = hand["landmarks"]["wrist"]
        middle_mcp = hand["landmarks"]["middle_mcp"]
        dx = middle_mcp[0] - wrist[0]
        dy = middle_mcp[1] - wrist[1]
        length = math.hypot(dx, dy)
        return (dy / length) if length >= 0.01 else None

    def _eval_two_hand_pitch(self) -> Optional[dict]:
        """
        Both hands tilt up/down together (nose-up / nose-down).
        Uses the averaged norm_dy of both wrist→middle_mcp vectors.
        """
        if len(self._tilt_buf) < 2:
            return None

        tilt_rate = self._tilt_buf[-1] - self._tilt_buf[0]

        if abs(tilt_rate) < config.PITCH_TILT_RATE_MIN:
            return None

        gesture   = "pitch_up" if tilt_rate < 0 else "pitch_down"
        intensity = min(abs(tilt_rate) / 0.3, 1.0)
        self._state = STATE_PITCH_UP if gesture == "pitch_up" else STATE_PITCH_DOWN

        if not self._can_emit(gesture):
            return None
        self._record_emit(gesture)
        return {"gesture": gesture, "intensity": round(intensity, 3)}

    def _eval_single_hand(self, hand: dict) -> Optional[dict]:
        """
        Route single-hand events.

        Priority order
        --------------
        1. Swipe   — palm translates laterally  → pan left / pan right
        2. Bearing — hand rotates in place      → bearing CW / CCW
        """
        # Reset two-hand state when switching to single-hand mode
        self._dist_buf.clear()
        self._tilt_buf.clear()

        palm_center = hand["palm_center"]

        if not self._in_activation_zone(palm_center):
            self._reset_buffers()
            self._state = STATE_IDLE
            return None

        self._palm_buf.append(palm_center)

        if len(self._palm_buf) < 2:
            return None

        # x-axis velocity: positive = moving right, negative = moving left
        velocity = self._palm_buf[-1][0] - self._palm_buf[0][0]

        # Swipe takes priority — clear angle buffer so bearing doesn't accumulate while swiping
        swipe_result = self._eval_swipe(velocity)
        if swipe_result:
            self._angle_buf.clear()
            return swipe_result

        # Wrist is not translating — check for CW/CCW rotation (bearing)
        return self._eval_bearing(hand)

    def _eval_swipe(self, velocity: float) -> Optional[dict]:
        """Handle swipe left/right detection."""
        if velocity < -config.SWIPE_VELOCITY_THRESHOLD:
            self._swipe_frames_left  += 1
            self._swipe_frames_right  = 0
        elif velocity > config.SWIPE_VELOCITY_THRESHOLD:
            self._swipe_frames_right += 1
            self._swipe_frames_left   = 0
        else:
            self._swipe_frames_left  = 0
            self._swipe_frames_right = 0
            return None

        if self._swipe_frames_left >= config.SWIPE_MIN_FRAMES:
            gesture = "pan_left"
            vel = abs(velocity)
            if not self._can_emit(gesture):
                return None
            self._record_emit(gesture)
            self._state = STATE_SWIPE_LEFT
            return {"gesture": gesture, "velocity": round(vel, 3)}

        if self._swipe_frames_right >= config.SWIPE_MIN_FRAMES:
            gesture = "pan_right"
            vel = abs(velocity)
            if not self._can_emit(gesture):
                return None
            self._record_emit(gesture)
            self._state = STATE_SWIPE_RIGHT
            return {"gesture": gesture, "velocity": round(vel, 3)}

        return None

    def _eval_bearing(self, hand: dict) -> Optional[dict]:
        """
        Detect CW / CCW rotation: wrist anchored, hand spins like a compass needle.

        Method
        ------
        Compute atan2(wrist→middle_mcp) each frame and accumulate sequential
        angle deltas with proper ±π unwrapping.  The total angular rotation
        over the smoothing window determines direction and magnitude.

        Image-coordinate convention: Y increases downward.
          positive total_delta → CW  rotation  → bearing_cw
          negative total_delta → CCW rotation  → bearing_ccw
        """
        wrist      = hand["landmarks"]["wrist"]
        middle_mcp = hand["landmarks"]["middle_mcp"]

        dx = middle_mcp[0] - wrist[0]
        dy = middle_mcp[1] - wrist[1]
        length = math.hypot(dx, dy)

        if length < 0.01:
            return None

        angle = math.atan2(dy, dx)
        self._angle_buf.append(angle)

        if len(self._angle_buf) < 2:
            return None

        # Sum sequential deltas — proper ±π unwrap so crossing atan2 seam
        # doesn't produce a spurious 2π spike.
        total_delta = 0.0
        for i in range(1, len(self._angle_buf)):
            d = self._angle_buf[i] - self._angle_buf[i - 1]
            if d >  math.pi: d -= 2 * math.pi
            elif d < -math.pi: d += 2 * math.pi
            total_delta += d

        if abs(total_delta) < config.BEARING_ANGLE_RATE_MIN:
            return None

        gesture   = "bearing_cw"  if total_delta > 0 else "bearing_ccw"
        intensity = min(abs(total_delta) / (math.pi / 3), 1.0)

        self._state = STATE_BEARING_CW if gesture == "bearing_cw" else STATE_BEARING_CCW

        if not self._can_emit(gesture):
            return None

        self._record_emit(gesture)
        return {"gesture": gesture, "intensity": round(intensity, 3)}

    def _can_emit(self, gesture: str) -> bool:
        last = self._cooldowns.get(gesture, 0.0)
        if gesture.startswith("pitch"):
            cooldown = config.PITCH_COOLDOWN_MS
        elif gesture.startswith("bearing"):
            cooldown = config.BEARING_COOLDOWN_MS
        else:
            cooldown = config.GESTURE_COOLDOWN_MS
        return (time.time() - last) * 1000 >= cooldown

    def _record_emit(self, gesture: str):
        self._cooldowns[gesture] = time.time()

    def _reset_buffers(self):
        self._dist_buf.clear()
        self._palm_buf.clear()
        self._tilt_buf.clear()
        self._angle_buf.clear()
        self._swipe_frames_left  = 0
        self._swipe_frames_right = 0
        self._coast_dir    = 0
        self._coast_frames = 0
