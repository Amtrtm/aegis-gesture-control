"""
main.py — PROJECT AEGIS Gesture Control · Entry Point

Orchestrates:
  1. CameraCapture   – threaded frame grabber
  2. HandDetector    – MediaPipe Hands
  3. GestureRecognizer – state machine
  4. WebSocketServer – async broadcast to browser
  5. Visualizer      – optional OpenCV debug window

Usage
-----
  python main.py
  python main.py --debug
  python main.py --source 0               # local webcam
  python main.py --source http://phone-ip:8080/video
  python main.py --port 9000
  python main.py --no-camera              # keyboard fallback mode
  python main.py --debug --source 0
"""

import argparse
import asyncio
import cv2
import logging
import os
import sys
import threading
import time

# Ensure project root is on the path so `debug.*` imports work whether
# running as `python backend/main.py` or `python main.py` from backend/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config

# ── Logging setup (must happen before any module import that logs) ──────────
log_handlers = [
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
]
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description="AEGIS Gesture Control Backend")
    p.add_argument("--source",    type=str,  default=None,  help="Camera source URL or index (overrides config)")
    p.add_argument("--port",      type=int,  default=None,  help="WebSocket port (overrides config)")
    p.add_argument("--debug",     action="store_true",      help="Show OpenCV debug visualiser")
    p.add_argument("--no-camera", action="store_true",      help="Keyboard fallback mode (no camera/MediaPipe)")
    p.add_argument("--verbose",   action="store_true",      help="Set log level to DEBUG")
    return p.parse_args()


# ── Main processing loop ──────────────────────────────────────────────────────

def run_camera_loop(ws_server, args):
    """Synchronous camera → detection → gesture → broadcast loop."""
    from camera_capture   import CameraCapture
    from hand_detector    import HandDetector
    from gesture_recognizer import GestureRecognizer

    cam  = CameraCapture(source=args.source)
    det  = HandDetector()
    gest = GestureRecognizer()

    debugger = None
    if args.debug:
        from debug.visualizer import Visualizer
        debugger = Visualizer()

    cam.start()
    logger.info("Camera processing loop started.")

    last_hand_time = time.time()
    hand_timeout_sent = False

    try:
        while True:
            frame = cam.get_frame()

            if frame is None:
                # Camera down — notify clients once
                ws_server.send_status(camera="disconnected")
                time.sleep(0.05)
                continue

            # ── Mirror frame so left/right gestures match natural movement ──
            frame = cv2.flip(frame, 1)

            # ── Hand detection ──────────────────────────────────────────────
            try:
                hand_data = det.process(frame)
            except Exception as exc:
                logger.error(f"HandDetector error (skipping frame): {exc}")
                continue

            # ── Update heartbeat state ──────────────────────────────────────
            ws_server.hand_detected = hand_data["detected"]
            ws_server.current_fps   = cam.fps

            # ── Hand timeout check ──────────────────────────────────────────
            if hand_data["detected"]:
                last_hand_time    = time.time()
                hand_timeout_sent = False
            else:
                elapsed = time.time() - last_hand_time
                if elapsed > config.HAND_TIMEOUT_SEC and not hand_timeout_sent:
                    ws_server.send_status(hand_timeout=True)
                    hand_timeout_sent = True

            # ── Gesture recognition ─────────────────────────────────────────
            event = gest.update(hand_data)
            if event:
                logger.debug(f"Gesture event: {event}")
                ws_server.send_gesture(event)

            # ── Debug visualiser ────────────────────────────────────────────
            if debugger:
                keep_open = debugger.draw(frame, hand_data, event)
                if not keep_open:
                    logger.info("Debug window closed — exiting.")
                    break

    finally:
        cam.stop()
        det.close()
        if debugger:
            debugger.close()
        logger.info("Camera processing loop stopped.")


def run_keyboard_loop(ws_server):
    """Keyboard fallback mode — no camera or MediaPipe required."""
    try:
        from pynput import keyboard as kb
    except ImportError:
        logger.error("pynput not installed. Run: pip install pynput")
        return

    logger.info("Keyboard fallback mode active.")
    logger.info("  w/s  → zoom in/out   |   a/d  → pan left/right   |  space  → idle")

    _current = {"gesture": "idle"}

    def on_press(key):
        try:
            ch = key.char
        except AttributeError:
            ch = None

        if ch == "w":
            _current["gesture"] = "zoom_in"
            ws_server.send_gesture({"gesture": "zoom_in", "intensity": 0.5})
        elif ch == "s":
            _current["gesture"] = "zoom_out"
            ws_server.send_gesture({"gesture": "zoom_out", "intensity": 0.5})
        elif ch == "a":
            _current["gesture"] = "pan_left"
            ws_server.send_gesture({"gesture": "pan_left", "velocity": 0.3})
        elif ch == "d":
            _current["gesture"] = "pan_right"
            ws_server.send_gesture({"gesture": "pan_right", "velocity": 0.3})
        elif key == kb.Key.space:
            _current["gesture"] = "idle"
            ws_server.active_gesture = "idle"

        ws_server.active_gesture = _current["gesture"]

    listener = kb.Listener(on_press=on_press)
    listener.start()
    listener.join()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.port:
        config.WS_PORT = args.port

    from websocket_server import WebSocketServer
    ws_server = WebSocketServer(port=config.WS_PORT)

    # Start WebSocket server in its own event loop on a background thread
    def _ws_thread():
        asyncio.run(ws_server.start())

    ws_t = threading.Thread(target=_ws_thread, daemon=True, name="WebSocketThread")
    ws_t.start()

    # Give the WS server a moment to bind
    time.sleep(0.5)

    logger.info("=" * 60)
    logger.info("PROJECT AEGIS — Gesture Control Backend")
    logger.info(f"  WebSocket : ws://{config.WS_HOST}:{config.WS_PORT}")
    logger.info(f"  Mode      : {'KEYBOARD FALLBACK' if args.no_camera else 'CAMERA'}")
    logger.info(f"  Debug     : {args.debug}")
    logger.info("=" * 60)

    if args.no_camera:
        run_keyboard_loop(ws_server)
    else:
        run_camera_loop(ws_server, args)


if __name__ == "__main__":
    main()
