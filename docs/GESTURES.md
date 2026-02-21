# AEGIS Gesture Reference Card

## Activation Zone

Only the **centre 60% × 70%** of the camera frame is active.  
Hands at your sides or outside this zone are completely ignored.

---

## Gestures

| Gesture | How to perform | MapLibre action |
|---------|---------------|-----------------|
| ✊ **Fist / Idle** | Close all fingers into a fist | No action — resets state |
| 🤏 **Pinch Close** | 2 hands — bring them together | **Zoom in** |
| 🤏 **Pinch Open** | 2 hands — spread them apart | **Zoom out** |
| ✈️ **Pitch Up** | 2 hands — tilt **both** fingers upward (nose-up) while wrists stay in place | **Pitch map up** (more perspective) |
| ✈️ **Pitch Down** | 2 hands — tilt **both** fingers downward (nose-down) while wrists stay in place | **Pitch map flat** (top-down) |
| 👋 **Swipe Left** | 1 hand open — move palm left at speed > threshold for ≥ 3 frames | **Pan left** |
| 👋 **Swipe Right** | 1 hand open — move palm right at speed > threshold for ≥ 3 frames | **Pan right** |
| 🧭 **Rotate CW** | 1 hand open, fingers together — rotate hand clockwise (wrist stays put) | **Bearing clockwise** |
| 🧭 **Rotate CCW** | 1 hand open, fingers together — rotate hand counter-clockwise (wrist stays put) | **Bearing counter-clockwise** |

---

## Tuning Parameters (backend/config.py)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `PINCH_THRESHOLD_CLOSE` | 0.05 | How close fingers must be to trigger zoom |
| `PINCH_THRESHOLD_OPEN`  | 0.10 | How far apart before zoom resets (hysteresis) |
| `SWIPE_VELOCITY_THRESHOLD` | 0.15 | Minimum palm speed for swipe |
| `SWIPE_MIN_FRAMES` | 3 | Frames of sustained swipe movement required |
| `FIST_THRESHOLD` | 0.08 | How close fingertips must be to palm for fist |
| `SMOOTHING_WINDOW` | 5 | Rolling average frames (higher = smoother, more lag) |
| `GESTURE_COOLDOWN_MS` | 300 | Minimum ms between same-gesture events |
| `ACTIVATION_ZONE` | (0.2, 0.8, 0.15, 0.85) | Active region of frame |
| `PITCH_TILT_RATE_MIN` | 0.06 | Min rate-of-tilt-change per window to register pitch |
| `PITCH_SPEED` | 2.5 | Degrees of MapLibre pitch change per event |

---

## Tips for Reliable Recognition

1. **Good lighting** — avoid backlight from windows behind you.
2. **Plain background** — a flat wall reduces false detections.
3. **Camera height** — position the camera so your hand is in the centre zone.
4. **Deliberate gestures** — slow, clear movements detect better than fast flicks.
5. **Make a fist to reset** — if the gesture system gets confused, form a fist.
