"""
camera_capture.py — Threaded IP camera frame grabber.

Runs a background thread that continuously grabs frames from an RTSP/MJPEG
or local camera source. Only the *latest* frame is kept in the buffer so the
main processing loop is never presented with stale data.

Reconnects automatically every 2 s if the stream drops.
"""

import cv2
import threading
import time
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)


class CameraCapture:
    """Threaded camera frame buffer.

    Usage
    -----
    cam = CameraCapture(source=config.CAMERA_SOURCE)
    cam.start()
    frame = cam.get_frame()   # returns latest BGR frame or None
    cam.stop()
    """

    def __init__(self, source=None):
        self._source = source if source is not None else config.CAMERA_SOURCE
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # FPS monitoring
        self._frame_count = 0
        self._fps = 0.0
        self._fps_timer = time.time()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the background capture thread."""
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="CameraThread")
        self._thread.start()
        logger.info(f"Camera capture started for source: {self._source}")

    def stop(self):
        """Signal the background thread to stop and wait for it."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap and self._cap.isOpened():
            self._cap.release()
        logger.info("Camera capture stopped.")

    def get_frame(self):
        """Return the latest BGR frame, or None if no frame yet / camera down."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def is_connected(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _open_camera(self) -> bool:
        """Attempt to open the camera source. Returns True on success."""
        if self._cap:
            self._cap.release()

        logger.info(f"Connecting to camera: {self._source}")
        # Normalise string integers ("0") to int so VideoCapture behaves correctly
        import sys
        source = self._source
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        # On Windows, integer indices require the DirectShow backend
        api = cv2.CAP_DSHOW if sys.platform == "win32" and isinstance(source, int) else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(source, api)

        if not self._cap.isOpened():
            logger.warning(f"Failed to open camera source: {self._source}")
            return False

        # Minimise latency by keeping buffer size small
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS,          config.CAMERA_FPS)

        logger.info("Camera connected successfully.")
        return True

    def _capture_loop(self):
        """Background thread: grab → retrieve → store, with auto-reconnect."""
        while self._running:
            # Connect / reconnect
            if not self.is_connected:
                if not self._open_camera():
                    logger.warning("Retrying camera connection in 2 s …")
                    time.sleep(2.0)
                    continue

            # Grab the next frame
            grabbed = self._cap.grab()
            if not grabbed:
                logger.warning("Camera grab() failed — stream may have dropped.")
                with self._lock:
                    self._frame = None
                self._cap.release()
                time.sleep(2.0)
                continue

            # Decode only the latest grab (skip decode of buffered frames)
            ret, frame = self._cap.retrieve()
            if ret and frame is not None:
                with self._lock:
                    self._frame = frame
                self._frame_count += 1
            else:
                logger.debug("retrieve() returned no frame, skipping.")

            # Log FPS every 5 s
            elapsed = time.time() - self._fps_timer
            if elapsed >= 5.0:
                self._fps = self._frame_count / elapsed
                logger.info(f"Camera FPS: {self._fps:.1f}")
                self._frame_count = 0
                self._fps_timer = time.time()
