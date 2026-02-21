/**
 * gesture_client.js — PROJECT AEGIS Gesture WebSocket Client
 * ============================================================
 * Connects to the Python backend WebSocket server and maps
 * gesture events to MapLibre GL camera controls.
 *
 * Replaces the Three.js camera spec with MapLibre equivalents:
 *   zoom_in   → map.easeTo({ zoom: zoom + delta })
 *   zoom_out  → map.easeTo({ zoom: zoom - delta })
 *   pan_left  → map.panBy([-panPx, 0])
 *   pan_right → map.panBy([+panPx, 0])
 *
 * Usage (standalone test page)
 * ----------------------------
 *   const ctrl = new GestureController({
 *     wsUrl:     'ws://localhost:8765',
 *     map:       maplibreInstance,    // maplibre-gl Map object
 *     zoomSpeed: 0.3,                 // zoom delta per event
 *     panSpeed:  80,                  // pixels per pan event
 *     smoothing: 150,                 // easeTo duration (ms)
 *   });
 *
 * Usage in React / ShobNG plugin
 * --------------------------------
 *   import { GestureController } from './gesture_client';
 *   // pass mapRef.current after map loads
 */

'use strict';

// ── HUD helpers ──────────────────────────────────────────────────────────────

function createHUD() {
  const hud = document.createElement('div');
  hud.id = 'aegis-hud';
  hud.style.cssText = `
    position: fixed;
    bottom: 16px;
    left: 16px;
    background: rgba(10, 15, 25, 0.88);
    border: 1px solid rgba(100, 160, 255, 0.35);
    border-radius: 8px;
    padding: 10px 14px;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
    color: #c8d8f0;
    z-index: 9999;
    min-width: 180px;
    pointer-events: none;
    backdrop-filter: blur(4px);
  `;
  hud.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
      <span id="aegis-dot" style="width:10px;height:10px;border-radius:50%;background:#e33;display:inline-block;"></span>
      <span id="aegis-conn-label" style="font-weight:600;letter-spacing:.05em;">DISCONNECTED</span>
    </div>
    <div>Gesture: <span id="aegis-gesture" style="color:#7dd3fc;">—</span></div>
    <div>Hand:    <span id="aegis-hand"    style="color:#7dd3fc;">—</span></div>
    <div style="margin-top:4px;font-size:10px;opacity:.7;">FPS: <span id="aegis-fps">—</span></div>
  `;
  document.body.appendChild(hud);
  return {
    setConnected(v) {
      document.getElementById('aegis-dot').style.background = v ? '#22c55e' : '#e33';
      document.getElementById('aegis-conn-label').textContent = v ? 'CONNECTED' : 'DISCONNECTED';
    },
    setGesture(g)  { document.getElementById('aegis-gesture').textContent = g || '—'; },
    setHand(v)     { document.getElementById('aegis-hand').textContent = v ? '✋ detected' : 'none'; },
    setFps(f)      { document.getElementById('aegis-fps').textContent = f; },
  };
}

// ── GestureController ─────────────────────────────────────────────────────────

class GestureController {
  /**
   * @param {object} opts
   * @param {string}  opts.wsUrl      WebSocket URL, e.g. 'ws://localhost:8765'
   * @param {object}  opts.map        maplibre-gl Map instance (can be set later)
   * @param {number}  [opts.zoomSpeed=0.3]   zoom delta per event (MapLibre zoom levels)
   * @param {number}  [opts.panSpeed=80]     pixels per pan event
   * @param {number}  [opts.smoothing=150]   easeTo / panBy animation duration ms
   * @param {boolean} [opts.showHUD=true]    show corner HUD overlay
   */
  constructor(opts = {}) {
    this.wsUrl      = opts.wsUrl     || 'ws://localhost:8765';
    this.map        = opts.map       || null;
    this.zoomSpeed  = opts.zoomSpeed ?? 0.3;
    this.panSpeed   = opts.panSpeed  ?? 80;
    this.smoothing  = opts.smoothing ?? 150;
    this.pitchSpeed = opts.pitchSpeed ?? 8.0;  // degrees per pitch event

    this._ws        = null;
    this._reconnect = true;
    this._retryMs   = 2000;

    // Continuous pan animation state
    this._panRaf       = null;
    this._panDir       = 0;
    this._panFramePx   = 0;
    this._panLastEvent = 0;
    this._PAN_TIMEOUT  = 600;

    // HUD
    this._hud = (opts.showHUD !== false) ? createHUD() : null;

    this._connect();
  }

  /** Attach or swap the MapLibre map instance. */
  setMap(mapInstance) {
    this.map = mapInstance;
  }

  /** Permanently disconnect and destroy the HUD. */
  destroy() {
    this._reconnect = false;
    if (this._ws) this._ws.close();
    const el = document.getElementById('aegis-hud');
    if (el) el.remove();
  }

  // ── Private ─────────────────────────────────────────────────────────────────

  _connect() {
    console.log(`[AEGIS] Connecting to ${this.wsUrl} …`);
    this._ws = new WebSocket(this.wsUrl);

    this._ws.onopen = () => {
      console.log('[AEGIS] WebSocket connected.');
      if (this._hud) this._hud.setConnected(true);
    };

    this._ws.onclose = () => {
      console.warn('[AEGIS] WebSocket closed.');
      if (this._hud) this._hud.setConnected(false);
      if (this._reconnect) {
        setTimeout(() => this._connect(), this._retryMs);
      }
    };

    this._ws.onerror = (err) => {
      console.error('[AEGIS] WebSocket error:', err);
    };

    this._ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        this._handleMessage(msg);
      } catch (e) {
        console.error('[AEGIS] Failed to parse message:', evt.data);
      }
    };
  }

  _handleMessage(msg) {
    switch (msg.type) {
      case 'gesture':
        this._applyGesture(msg);
        if (this._hud) this._hud.setGesture(msg.gesture);
        break;

      case 'heartbeat':
        if (this._hud) {
          this._hud.setHand(msg.hand_detected);
          this._hud.setFps(msg.fps);
          this._hud.setGesture(msg.active_gesture);
        }
        break;

      case 'status':
        if (msg.camera === 'disconnected') {
          console.warn('[AEGIS] Camera disconnected on backend.');
          if (this._hud) this._hud.setGesture('⚠ cam offline');
        }
        if (msg.hand_timeout) {
          console.info('[AEGIS] No hand detected for >5 s.');
          if (this._hud) this._hud.setHand(false);
        }
        break;

      default:
        break;
    }
  }

  _applyGesture(msg) {
    if (!this.map) return;

    const { gesture, intensity = 0, velocity = 0 } = msg;
    const map = this.map;
    const dur  = this.smoothing;

    switch (gesture) {
      case 'zoom_in': {
        this._stopPan();
        const z = map.getZoom() + this.zoomSpeed * (1 + intensity);
        map.easeTo({ zoom: Math.min(z, 20), duration: dur });
        break;
      }
      case 'zoom_out': {
        this._stopPan();
        const z = map.getZoom() - this.zoomSpeed * (1 + intensity);
        map.easeTo({ zoom: Math.max(z, 1), duration: dur });
        break;
      }
      case 'pan_left':
        this._startPan(-1, velocity);
        break;
      case 'pan_right':
        this._startPan(+1, velocity);
        break;
      case 'pitch_up': {
        this._stopPan();
        const p = Math.min((map.getPitch?.() ?? 0) + this.pitchSpeed * (1 + intensity), 85);
        map.easeTo({ pitch: p, duration: 30 });
        break;
      }
      case 'pitch_down': {
        this._stopPan();
        const p = Math.max((map.getPitch?.() ?? 0) - this.pitchSpeed * (1 + intensity), 0);
        map.easeTo({ pitch: p, duration: 30 });
        break;
      }
      case 'bearing_cw': {
        this._stopPan();
        const b = (map.getBearing?.() ?? 0) + (this.bearingSpeed ?? 6) * (1 + intensity);
        map.easeTo({ bearing: b, duration: 30 });
        break;
      }
      case 'bearing_ccw': {
        this._stopPan();
        const b = (map.getBearing?.() ?? 0) - (this.bearingSpeed ?? 6) * (1 + intensity);
        map.easeTo({ bearing: b, duration: 30 });
        break;
      }
      case 'idle':
        this._stopPan();
        break;
      default:
        console.debug('[AEGIS] Unknown gesture:', gesture);
    }
  }

  _stopPan() {
    if (this._panRaf) {
      cancelAnimationFrame(this._panRaf);
      this._panRaf = null;
    }
    this._panDir = 0;
  }

  _startPan(dir, velocity) {
    this._panDir       = dir;
    this._panFramePx   = 6 + velocity * 120;
    this._panLastEvent = performance.now();

    if (this._panRaf) return;

    const loop = () => {
      if (!this.map || this._panDir === 0) { this._panRaf = null; return; }
      if (performance.now() - this._panLastEvent > this._PAN_TIMEOUT) {
        this._panRaf = null; this._panDir = 0; return;
      }
      this.map.panBy([this._panDir * this._panFramePx, 0], { duration: 0, animate: false });
      this._panRaf = requestAnimationFrame(loop);
    };
    this._panRaf = requestAnimationFrame(loop);
  }
}

// Export for ES-module environments (React / ShobNG plugin)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { GestureController };
}
