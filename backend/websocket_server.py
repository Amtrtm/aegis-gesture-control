"""
websocket_server.py — Async WebSocket broadcast server.

Broadcasts gesture events (JSON) to all connected browser clients.
Also sends a heartbeat every HEARTBEAT_INTERVAL seconds so clients
can detect connection loss.
"""

import asyncio
import json
import logging
import time
from typing import Set

import websockets
import websockets.exceptions

import config

logger = logging.getLogger(__name__)


class WebSocketServer:
    """
    Async WebSocket server.  Run alongside the main processing loop with::

        server = WebSocketServer()
        asyncio.get_event_loop().run_until_complete(server.start())

    Use ``broadcast(message_dict)`` (thread-safe via
    ``run_coroutine_threadsafe``) to push gesture events from the
    synchronous main loop.
    """

    def __init__(self, host: str = None, port: int = None):
        self._host = host or config.WS_HOST
        self._port = port or config.WS_PORT
        self._clients: Set[websockets.WebSocketServerProtocol] = set()
        self._loop: asyncio.AbstractEventLoop = None
        self._server = None

        # Shared state updated by main loop (for heartbeat)
        self.hand_detected: bool  = False
        self.current_fps:   float = 0.0
        self.active_gesture: str  = "idle"
        self._last_gesture_time: float = 0.0  # timestamp of last send_gesture call

    # ── Public ───────────────────────────────────────────────────────────────

    async def start(self):
        """Coroutine: start the WS server and heartbeat loop.  Runs forever."""
        self._loop = asyncio.get_running_loop()
        self._server = await websockets.serve(
            self._handler,
            self._host,
            self._port,
        )
        logger.info(f"WebSocket server listening on ws://{self._host}:{self._port}")
        asyncio.ensure_future(self._heartbeat_loop())
        await self._server.wait_closed()

    def broadcast(self, message: dict):
        """Thread-safe broadcast from the synchronous main loop."""
        if self._loop is None or not self._clients:
            return
        asyncio.run_coroutine_threadsafe(self._async_broadcast(message), self._loop)

    def stop(self):
        if self._server:
            self._server.close()

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _handler(self, websocket, path=None):
        self._clients.add(websocket)
        ip = websocket.remote_address
        logger.info(f"Client connected: {ip}  (total: {len(self._clients)})")
        try:
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info(f"Client disconnected: {ip}  (remaining: {len(self._clients)})")

    async def _async_broadcast(self, message: dict):
        if not self._clients:
            return
        payload = json.dumps(message)
        dead = set()
        for ws in self._clients.copy():
            try:
                await ws.send(payload)
            except websockets.exceptions.ConnectionClosed:
                dead.add(ws)
            except Exception as exc:
                logger.error(f"Send error to {ws.remote_address}: {exc}")
                dead.add(ws)
        self._clients -= dead

    async def _heartbeat_loop(self):
        """Send periodic heartbeat to all clients."""
        while True:
            await asyncio.sleep(config.HEARTBEAT_INTERVAL)
            # Auto-reset gesture label after 1 s of no gesture events
            if time.time() - self._last_gesture_time > 1.0:
                self.active_gesture = "idle"
            msg = {
                "type":           "heartbeat",
                "hand_detected":  self.hand_detected,
                "fps":            round(self.current_fps, 1),
                "active_gesture": self.active_gesture,
                "timestamp":      int(time.time() * 1000),
            }
            await self._async_broadcast(msg)

    def send_gesture(self, event: dict):
        """Convenience: wrap a gesture event and broadcast it."""
        msg = {
            "type":      "gesture",
            "gesture":   event.get("gesture", "idle"),
            "intensity": event.get("intensity", 0.0),
            "velocity":  event.get("velocity", 0.0),
            "timestamp": int(time.time() * 1000),
        }
        self.active_gesture = msg["gesture"]
        self._last_gesture_time = time.time()
        self.broadcast(msg)

    def send_status(self, **kwargs):
        """Send a status message (e.g. camera disconnect, hand timeout)."""
        msg = {"type": "status", "timestamp": int(time.time() * 1000), **kwargs}
        self.broadcast(msg)
