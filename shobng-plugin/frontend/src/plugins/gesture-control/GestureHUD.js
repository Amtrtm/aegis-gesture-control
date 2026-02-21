/**
 * GestureHUD.js — React UI component for the Gesture Control plugin panel.
 *
 * Renders inside the ShobNG Plugin Panel sidebar.
 * Subscribes to GestureControlPlugin.status live updates.
 */

import React, { useState, useEffect, useCallback } from 'react';
import GestureControlPlugin from './index';
import './GestureHUD.css';

const GestureHUD = () => {
  const [status, setStatus]     = useState({ ...GestureControlPlugin.status });
  const [enabled, setEnabled]   = useState(GestureControlPlugin.enabled);
  const [wsUrl, setWsUrl]       = useState(GestureControlPlugin.config.wsUrl);
  const [zoomSpeed, setZoomSpeed] = useState(GestureControlPlugin.config.zoomSpeed);
  const [panSpeed, setPanSpeed]   = useState(GestureControlPlugin.config.panSpeed);

  // Subscribe to live status updates from the plugin
  useEffect(() => {
    const handler = (s) => setStatus(s);
    GestureControlPlugin.subscribe(handler);
    return () => GestureControlPlugin.unsubscribe(handler);
  }, []);

  const handleToggle = useCallback(() => {
    if (enabled) {
      GestureControlPlugin.deactivate();
      GestureControlPlugin.enabled = false;
      setEnabled(false);
    } else {
      GestureControlPlugin.enabled = true;
      GestureControlPlugin.activate();
      setEnabled(true);
    }
  }, [enabled]);

  const handleApplyConfig = useCallback(() => {
    GestureControlPlugin.config.wsUrl     = wsUrl;
    GestureControlPlugin.config.zoomSpeed = parseFloat(zoomSpeed) || 0.3;
    GestureControlPlugin.config.panSpeed  = parseFloat(panSpeed)  || 80;
    // Reconnect with new URL
    if (enabled) {
      GestureControlPlugin._disconnect();
      setTimeout(() => GestureControlPlugin._connect(), 300);
    }
  }, [wsUrl, zoomSpeed, panSpeed, enabled]);

  const connColor = status.connected ? '#22c55e' : '#ef4444';
  const gestureLabel = status.activeGesture || '—';

  return (
    <div className="gesture-hud">

      {/* ── Status bar ─────────────────────────────────────────────── */}
      <div className="gesture-hud__status-row">
        <span className="gesture-hud__dot" style={{ background: connColor }} />
        <span className="gesture-hud__conn-label" style={{ color: connColor }}>
          {status.connected ? 'CONNECTED' : 'DISCONNECTED'}
        </span>
        <button
          className={`gesture-hud__toggle ${enabled ? 'active' : ''}`}
          onClick={handleToggle}
        >
          {enabled ? 'Disable' : 'Enable'}
        </button>
      </div>

      {/* ── Live metrics ────────────────────────────────────────────── */}
      <div className="gesture-hud__metrics">
        <div className="gesture-hud__metric">
          <span className="label">Gesture</span>
          <span className="value accent">{gestureLabel}</span>
        </div>
        <div className="gesture-hud__metric">
          <span className="label">Hand</span>
          <span className="value">{status.handDetected ? '✋ detected' : 'none'}</span>
        </div>
        <div className="gesture-hud__metric">
          <span className="label">FPS</span>
          <span className="value">{status.fps}</span>
        </div>
      </div>

      {/* ── Gesture reference ───────────────────────────────────────── */}
      <div className="gesture-hud__ref">
        <div className="gesture-hud__ref-title">Gesture Reference</div>
        <table>
          <tbody>
            <tr><td>✊ Fist</td><td>Idle (no action)</td></tr>
            <tr><td>🤏 Pinch close</td><td>Zoom in</td></tr>
            <tr><td>🤏 Pinch open</td><td>Zoom out</td></tr>
            <tr><td>👋 Swipe left</td><td>Pan left</td></tr>
            <tr><td>👋 Swipe right</td><td>Pan right</td></tr>
          </tbody>
        </table>
      </div>

      {/* ── Config ──────────────────────────────────────────────────── */}
      <div className="gesture-hud__config">
        <div className="gesture-hud__ref-title">Configuration</div>
        <label>
          WebSocket URL
          <input
            type="text"
            value={wsUrl}
            onChange={e => setWsUrl(e.target.value)}
          />
        </label>
        <label>
          Zoom Speed
          <input
            type="number"
            min="0.05" max="2" step="0.05"
            value={zoomSpeed}
            onChange={e => setZoomSpeed(e.target.value)}
          />
        </label>
        <label>
          Pan Speed (px)
          <input
            type="number"
            min="10" max="400" step="10"
            value={panSpeed}
            onChange={e => setPanSpeed(e.target.value)}
          />
        </label>
        <button className="gesture-hud__apply-btn" onClick={handleApplyConfig}>
          Apply &amp; Reconnect
        </button>
      </div>

    </div>
  );
};

export default GestureHUD;
