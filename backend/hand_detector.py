"""
hand_detector.py — MediaPipe Hands wrapper.

Accepts a BGR frame (from OpenCV) and returns normalised landmark data
in a structured dict that the gesture recogniser can consume.

Uses the MediaPipe Tasks API (mediapipe >= 0.10.21).
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import logging
import urllib.request
import os
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Hand landmarker model — downloaded automatically on first run
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# MediaPipe landmark indices we care about
_LM = {
    "wrist":       0,
    "thumb_tip":   4,
    "index_mcp":   5,
    "index_tip":   8,
    "middle_mcp":  9,
    "middle_tip":  12,
    "ring_mcp":    13,
    "ring_tip":    16,
    "pinky_mcp":   17,
    "pinky_tip":   20,
}


class HandDetector:
    """
    Wraps MediaPipe HandLandmarker (Tasks API) and returns a clean landmark dict.

    Returned structure
    ------------------
    {
        "detected":   bool,         # True if at least one hand found
        "hand_count": int,          # 0, 1, or 2
        "hands": [                  # one entry per detected hand
            {
                "landmarks":  {
                    "wrist":      (x, y, z),
                    "thumb_tip":  (x, y, z),
                    "index_tip":  (x, y, z),
                    "middle_tip": (x, y, z),
                    "ring_tip":   (x, y, z),
                    "pinky_tip":  (x, y, z),
                    "index_mcp":  (x, y, z),
                    "middle_mcp": (x, y, z),
                    "ring_mcp":   (x, y, z),
                    "pinky_mcp":  (x, y, z),
                },
                "palm_center": (x, y),   # avg of wrist + MCP landmarks
                "handedness":  "Left" | "Right",
                "raw":         list[NormalizedLandmark]   # 21 landmarks, for visualiser
            },
            ...
        ]
    }
    """

    def __init__(self):
        if not os.path.exists(_MODEL_PATH):
            logger.info("Downloading hand_landmarker.task model (~8 MB)...")
            urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
            logger.info("Model saved to %s", _MODEL_PATH)

        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=config.MP_MAX_HANDS,
            min_hand_detection_confidence=config.MP_MIN_DETECTION_CONF,
            min_hand_presence_confidence=config.MP_MIN_DETECTION_CONF,
            min_tracking_confidence=config.MP_MIN_TRACKING_CONF,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        logger.info("HandDetector initialised (MediaPipe Tasks HandLandmarker).")

    def process(self, bgr_frame) -> dict:
        """
        Run inference on a single BGR frame.

        Parameters
        ----------
        bgr_frame : np.ndarray   BGR image from OpenCV

        Returns
        -------
        dict  as described above; "detected" is False if no hand found
        """
        if bgr_frame is None:
            return self._empty_result()

        try:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._landmarker.detect(mp_image)
        except Exception as exc:
            logger.error(f"MediaPipe inference failed: {exc}")
            return self._empty_result()

        if not result.hand_landmarks:
            return self._empty_result()

        hands = []
        for i, lm_list in enumerate(result.hand_landmarks):
            handedness = "Right"
            if result.handedness and i < len(result.handedness):
                handedness = result.handedness[i][0].category_name

            def _xyz(idx, lm=lm_list):
                l = lm[idx]
                return (l.x, l.y, l.z)

            landmarks = {name: _xyz(idx) for name, idx in _LM.items()}

            # Palm centre = average of wrist + 4 MCP points
            palm_pts = [lm_list[j] for j in [0, 5, 9, 13, 17]]
            px = sum(p.x for p in palm_pts) / len(palm_pts)
            py = sum(p.y for p in palm_pts) / len(palm_pts)

            hands.append({
                "landmarks":   landmarks,
                "palm_center": (px, py),
                "handedness":  handedness,
                "raw":         lm_list,
            })

        return {
            "detected":   True,
            "hand_count": len(hands),
            "hands":      hands,
        }

    def close(self):
        self._landmarker.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> dict:
        return {
            "detected":   False,
            "hand_count": 0,
            "hands":      [],
        }
