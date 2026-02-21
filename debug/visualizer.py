"""
debug/visualizer.py — OpenCV debug window.

Shows live camera feed with:
  • MediaPipe hand landmarks overlaid (all detected hands)
  • Inter-hand distance line and label (two-hand zoom mode)
  • Current gesture state (top-left)
  • Palm-center crosshairs
  • Activation zone rectangle
  • FPS counter

Toggle with --debug flag in main.py.
NOT used in the production demo.
"""

import cv2
import time
import sys
import os
import math

# Allow import from parent directory when running standalone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

# Hand landmark connections for manual drawing (21 landmarks, 0-indexed)
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index
    (0, 9), (9, 10), (10, 11), (11, 12),     # middle
    (0, 13), (13, 14), (14, 15), (15, 16),   # ring
    (0, 17), (17, 18), (18, 19), (19, 20),   # pinky
    (5, 9), (9, 13), (13, 17),               # palm
]

# Gesture → colour mapping for state label (BGR — bright green for readability)
_GREEN = (0, 255, 0)
_GESTURE_COLOURS = {
    "zoom_in":   _GREEN,
    "zoom_out":  _GREEN,
    "pan_left":  _GREEN,
    "pan_right": _GREEN,
    "idle":      _GREEN,
    None:        _GREEN,
}

# Per-hand skeleton colours (up to 2 hands)
_HAND_COLOURS = [
    (80, 200, 80),    # hand 0 — green
    (200, 80, 200),   # hand 1 — purple
]


class Visualizer:
    """Wraps an OpenCV named window and renders debug info."""

    def __init__(self, window_name: str = "AEGIS — Debug Visualizer"):
        self._win = window_name
        cv2.namedWindow(self._win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self._win, 960, 540)

        self._frame_count = 0
        self._fps = 0.0
        self._fps_timer = time.time()

    def draw(self, frame, hand_data: dict, gesture_event) -> bool:
        """
        Render all debug overlays onto ``frame`` and display it.

        Returns
        -------
        bool  False if the user pressed 'q' (signal to quit).
        """
        if frame is None:
            return True

        vis = frame.copy()
        h, w = vis.shape[:2]

        # ── FPS ──────────────────────────────────────────────────────────────
        self._frame_count += 1
        elapsed = time.time() - self._fps_timer
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_timer = time.time()

        # ── Activation zone ───────────────────────────────────────────────────
        xmin, xmax, ymin, ymax = config.ACTIVATION_ZONE
        az = (int(xmin * w), int(ymin * h), int(xmax * w), int(ymax * h))
        cv2.rectangle(vis, (az[0], az[1]), (az[2], az[3]), (50, 50, 200), 1)

        # ── Hand landmarks and palm crosshairs ───────────────────────────────
        hands = hand_data.get("hands", [])
        palm_pixels = []  # pixel coords of each palm center

        for i, hand in enumerate(hands):
            colour = _HAND_COLOURS[i % len(_HAND_COLOURS)]
            raw_landmarks = hand.get("raw")

            if raw_landmarks:
                pts = [(int(lm.x * w), int(lm.y * h)) for lm in raw_landmarks]
                for a, b in _HAND_CONNECTIONS:
                    cv2.line(vis, pts[a], pts[b], colour, 2)
                for pt in pts:
                    cv2.circle(vis, pt, 4, (255, 255, 255), -1)
                    cv2.circle(vis, pt, 4, colour, 1)

            # Palm center crosshair
            px, py = hand["palm_center"]
            cx, cy = int(px * w), int(py * h)
            palm_pixels.append((cx, cy))
            cv2.drawMarker(vis, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, 20, 2)

            # Handedness label near palm
            label = hand.get("handedness", "")
            cv2.putText(vis, label, (cx + 12, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1)

        # ── Inter-hand distance line (two-hand zoom mode) ──────────────────
        if len(palm_pixels) >= 2:
            p1, p2 = palm_pixels[0], palm_pixels[1]
            cv2.line(vis, p1, p2, (0, 255, 255), 1)
            dist = math.hypot(
                (p1[0] - p2[0]) / w,
                (p1[1] - p2[1]) / h,
            )
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            cv2.putText(vis, f"d={dist:.3f}", (mid[0] + 5, mid[1] - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # ── Gesture label ─────────────────────────────────────────────────────
        gesture = gesture_event.get("gesture") if gesture_event else "idle"
        colour = _GESTURE_COLOURS.get(gesture, (180, 180, 180))
        cv2.putText(vis, f"Gesture: {gesture or 'idle'}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2)

        # ── Intensity / velocity ──────────────────────────────────────────────
        if gesture_event:
            extra = gesture_event.get("intensity", gesture_event.get("velocity", 0))
            cv2.putText(vis, f"  value: {extra:.3f}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 1)

        # ── Mode indicator ────────────────────────────────────────────────────
        hand_count = hand_data.get("hand_count", 0)
        mode_labels = {0: "IDLE", 1: "SWIPE", 2: "ZOOM"}
        mode = mode_labels.get(hand_count, f"{hand_count} hands")
        cv2.putText(vis, f"Mode: {mode}  ({hand_count} hand{'s' if hand_count != 1 else ''})",
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, _GREEN, 1)

        # ── Hand detected indicator ───────────────────────────────────────────
        dot_col = (0, 255, 0) if hand_data.get("detected") else (0, 0, 220)
        cv2.circle(vis, (w - 20, 20), 10, dot_col, -1)

        # ── FPS counter ───────────────────────────────────────────────────────
        cv2.putText(vis, f"FPS: {self._fps:.1f}",
                    (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _GREEN, 1)

        cv2.imshow(self._win, vis)
        key = cv2.waitKey(1) & 0xFF
        return key != ord("q")

    def close(self):
        cv2.destroyWindow(self._win)
