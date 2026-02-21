/**
 * gesture-control/index.js
 * ========================
 * PROJECT AEGIS Gesture Control — ShobNG Plugin
 *
 * Connects to the Python WebSocket backend and maps gesture events
 * to MapLibre GL camera movements (zoom, pan).
 *
 * Registers as a 'panel' category plugin so it appears in the Plugin Panel
 * sidebar with an enable/disable toggle.
 *
 * Gesture → MapLibre mapping
 * --------------------------
 *   zoom_in   → map.easeTo({ zoom: +delta })
 *   zoom_out  → map.easeTo({ zoom: -delta })
 *   pan_left  → map.panBy([-px, 0])
 *   pan_right → map.panBy([+px, 0])
 */

const GestureControlPlugin = {
  // ── Metadata ──────────────────────────────────────────────────────────────
  id:          'gesture-control',
  name:        'Gesture Control',
  version:     '1.0.0',
  description: 'Real-time hand gesture control via MediaPipe + WebSocket (PROJECT AEGIS)',
  author:      'AEGIS Team',
  category:    'panel',
  icon:        'Hand',   // Lucide icon
  enabled:     true,

  // ── Internal state ────────────────────────────────────────────────────────
  _map:     null,
  _context: null,
  _ws:      null,
  _retryTimer: null,
  isActive: false,

  // Continuous pan animation state
  _panRaf:       null,   // requestAnimationFrame handle
  _panDir:       0,      // -1 = left, +1 = right
  _panSpeed:     0,      // px per frame, derived from velocity
  _panLastEvent: 0,      // timestamp of last pan WS event (ms)
  _PAN_TIMEOUT:  1500,   // ms — stop panning if no fresh event within this window

  // ── Configuration (can be overridden before initialize) ──────────────────
  config: {
    wsUrl:        'ws://localhost:8765',
    zoomSpeed:    0.3,    // MapLibre zoom-level delta per event
    panSpeed:     80,     // pixels per pan event
    smoothing:    150,    // easeTo / panBy duration (ms)
    pitchSpeed:   8.0,    // degrees per pitch event
    bearingSpeed: 6.0,    // degrees per bearing event
  },

  // ── Observable state (read by GestureHUD React component) ─────────────────
  status: {
    connected:     false,
    handDetected:  false,
    activeGesture: '—',
    fps:           '—',
  },

  // Subscribers for status changes (simple pub/sub for React component)
  _subscribers: [],
  _notify() {
    this._subscribers.forEach(fn => fn({ ...this.status }));
  },
  subscribe(fn)   { this._subscribers.push(fn); },
  unsubscribe(fn) { this._subscribers = this._subscribers.filter(s => s !== fn); },

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  initialize(context) {
    this._context = context;

    // Handle map:loaded for future loads
    context.on('map:loaded', (map) => {
      this._map = map;
      console.log('[GestureControl] Map ref acquired via event.');
      if (this.enabled) this._connect();
    });

    // Handle the race condition: map may have already loaded before this plugin registered
    const existingMap = context.getMap?.();
    if (existingMap) {
      this._map = existingMap;
      console.log('[GestureControl] Map ref acquired immediately (already loaded).');
      if (this.enabled) this._connect();
    }

    console.log('[GestureControl] Plugin initialised.');
  },

  // Called by PluginManager when the user enables the plugin in the panel
  onEnable() { this.activate(); },

  // Called by PluginManager when the user disables the plugin in the panel
  onDisable() { this.deactivate(); },

  activate() {
    this.isActive = true;
    if (this._map) this._connect();
  },

  deactivate() {
    this.isActive = false;
    this._disconnect();
  },

  cleanup() {
    this._stopPan();
    this._disconnect();
    this._subscribers = [];
  },

  // ── WebSocket ─────────────────────────────────────────────────────────────

  _connect() {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) return;

    console.log(`[GestureControl] Connecting to ${this.config.wsUrl} …`);
    this._ws = new WebSocket(this.config.wsUrl);

    this._ws.onopen = () => {
      console.log('[GestureControl] WebSocket connected.');
      this.status.connected = true;
      this._notify();
      if (this._retryTimer) { clearTimeout(this._retryTimer); this._retryTimer = null; }
    };

    this._ws.onclose = () => {
      console.warn('[GestureControl] WebSocket closed.');
      this.status.connected     = false;
      this.status.handDetected  = false;
      this.status.activeGesture = '—';
      this._notify();
      if (this.isActive) {
        this._retryTimer = setTimeout(() => this._connect(), 2000);
      }
    };

    this._ws.onerror = (err) => {
      console.error('[GestureControl] WebSocket error:', err);
    };

    this._ws.onmessage = (evt) => {
      try {
        this._handleMessage(JSON.parse(evt.data));
      } catch (e) {
        console.error('[GestureControl] Parse error:', e);
      }
    };
  },

  _disconnect() {
    if (this._retryTimer) { clearTimeout(this._retryTimer); this._retryTimer = null; }
    this._stopPan();
    if (this._ws) {
      this._ws.onclose = null; // prevent reconnect loop
      this._ws.close();
      this._ws = null;
    }
    this.status.connected     = false;
    this.status.handDetected  = false;
    this.status.activeGesture = '—';
    this._notify();
  },

  // ── Message handling ──────────────────────────────────────────────────────

  _handleMessage(msg) {
    switch (msg.type) {
      case 'gesture':
        console.log('[GestureControl] gesture received:', msg.gesture, msg);
        this.status.activeGesture = msg.gesture;
        this._notify();
        GestureControlPlugin._applyGesture(msg);
        break;

      case 'heartbeat':
        this.status.handDetected  = msg.hand_detected;
        this.status.fps           = String(msg.fps);
        // Do NOT overwrite activeGesture from heartbeat — gesture events own that field
        this._notify();
        break;

      case 'status':
        if (msg.camera === 'disconnected') {
          this.status.activeGesture = '⚠ cam offline';
          this._notify();
        }
        if (msg.hand_timeout) {
          this.status.handDetected = false;
          this._notify();
        }
        break;

      default:
        break;
    }
  },

  // ── Camera control ────────────────────────────────────────────────────────

  _stopPan() {
    const self = GestureControlPlugin;
    if (self._panRaf) {
      cancelAnimationFrame(self._panRaf);
      self._panRaf = null;
    }
    self._panDir = 0;
  },

  _startPan(dir, velocity) {
    const self = GestureControlPlugin;
    self._panDir       = dir;
    self._panSpeed     = 6 + velocity * 120;
    self._panLastEvent = performance.now();

    // Immediate first hit — use window.__aegisMap as fallback for HMR safety
    const mapNow = self._map || window.__aegisMap || null;
    if (mapNow) {
      if (!self._map) self._map = mapNow;
      mapNow.panBy([dir * self._panSpeed * 4, 0], { duration: 0 });
    }

    if (self._panRaf) return;

    const loop = () => {
      const m = self._map || window.__aegisMap || null;
      if (!m || self._panDir === 0) { self._panRaf = null; return; }
      if (performance.now() - self._panLastEvent > self._PAN_TIMEOUT) {
        self._panRaf = null; self._panDir = 0; return;
      }
      m.panBy([self._panDir * self._panSpeed, 0], { duration: 0 });
      self._panRaf = requestAnimationFrame(loop);
    };
    self._panRaf = requestAnimationFrame(loop);
  },

  _applyGesture(msg) {
    // Always use the module-level reference — never trust 'this' in a plain object
    const self = GestureControlPlugin;
    // Fallback to window.__aegisMap so HMR resets don't break the map ref
    const map  = self._map || window.__aegisMap || null;
    if (map && !self._map) self._map = map; // re-cache for next call

    console.log('[GestureControl] _applyGesture:', msg.gesture, '| map:', !!map);

    if (!map) {
      console.warn('[GestureControl] _applyGesture: no map ref, dropping gesture');
      return;
    }

    const { gesture, intensity = 0, velocity = 0 } = msg;
    const dur = self.config.smoothing;
    const zs  = self.config.zoomSpeed;

    switch (gesture) {
      case 'zoom_in':
        self._stopPan();
        map.easeTo({ zoom: Math.min(map.getZoom() + zs * (1 + intensity), 20), duration: dur });
        break;
      case 'zoom_out':
        self._stopPan();
        map.easeTo({ zoom: Math.max(map.getZoom() - zs * (1 + intensity), 1),  duration: dur });
        break;
      case 'pan_left':
        self._startPan(-1, velocity);
        break;
      case 'pan_right':
        self._startPan(+1, velocity);
        break;
      case 'pitch_up': {
        self._stopPan();
        const p = Math.min((map.getPitch?.() ?? 0) + self.config.pitchSpeed * (1 + intensity), 85);
        map.easeTo({ pitch: p, duration: 30 });
        break;
      }
      case 'pitch_down': {
        self._stopPan();
        const p = Math.max((map.getPitch?.() ?? 0) - self.config.pitchSpeed * (1 + intensity), 0);
        map.easeTo({ pitch: p, duration: 30 });
        break;
      }
      case 'bearing_cw': {
        self._stopPan();
        const b = (map.getBearing?.() ?? 0) + self.config.bearingSpeed * (1 + intensity);
        map.easeTo({ bearing: b, duration: 30 });
        break;
      }
      case 'bearing_ccw': {
        self._stopPan();
        const b = (map.getBearing?.() ?? 0) - self.config.bearingSpeed * (1 + intensity);
        map.easeTo({ bearing: b, duration: 30 });
        break;
      }
      case 'idle':
        self._stopPan();
        break;
      default:
        break;
    }
  },

  // ── Panel UI (React component ref) ────────────────────────────────────────

  /**
   * Returns JSX to render inside the Plugin Panel.
   * Import and use GestureControlPanel from GestureHUD.js.
   */
  renderPanel() {
    // Dynamically imported in PluginPanel.js
    return null;
  },
};

export default GestureControlPlugin;
