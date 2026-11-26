#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eidak | إيدك — Hand Gesture PC Control
=====================================

Control your computer with hand gestures through the webcam:
move the mouse, click, drag and scroll, plus a dedicated mode for
video players (play/pause, seek, volume, speed, fullscreen, close).

Everything runs locally and offline. No video ever leaves the PC.

Tested target: Windows 10/11 with a built-in or USB webcam.
Requires Python 3.9 - 3.12.
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import time
from typing import List, Optional

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - reported nicely at runtime
    cv2 = None

try:
    import mediapipe as mp
except ImportError:  # pragma: no cover
    mp = None

try:
    import pyautogui

    pyautogui.PAUSE = 0.0
    pyautogui.FAILSAFE = True  # slam the mouse to a screen corner to emergency-stop
except Exception:  # headless machines / missing display - handled at runtime
    pyautogui = None

try:  # optional: global quit hotkey (Ctrl+Alt+Q) even when the window is unfocused
    import keyboard  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    keyboard = None


# --------------------------------------------------------------------------
# Module split (step 0): camera handling and gesture logic live in their own
# modules and are re-exported here, so existing imports keep working.
# --------------------------------------------------------------------------
from camera import (
    CameraManager,
    diagnose_cameras,
    list_cameras,
    NO_DEVICE,
    OPENED_NO_FRAMES,
    BLACK_FRAMES,
    PRIVACY_HINT,
)
from gestures import (
    WRIST,
    THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP,
    INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP,
    MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP,
    RING_MCP, RING_PIP, RING_DIP, RING_TIP,
    PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP,
    FINGERS,
    Point,
    Landmarks,
    dist,
    HandState,
    classify_hand,
    GestureEvent,
    GestureEngine,
    HandStabilizer,
    GesturePipeline,
    PyAutoSink,
    NullSink,
    Dispatcher,
)


DEFAULT_CONFIG = {
    "camera_index": -1,            # -1 = auto-probe all cameras
    "camera_strict": False,        # True = only try camera_index (--camera)
    "last_camera": None,           # learned: {"index": int, "backend": int}
    "skip_grayscale_cameras": True,  # skip IR/virtual grayscale cameras when probing
    "mjpg": True,                  # request MJPG compression (USB bandwidth)
    "freeze_reconnect_sec": 4.0,   # identical frames for this long = frozen camera
    "frame_width": 640,            # 640x480 keeps CPU low on modest hardware
    "frame_height": 480,
    "max_num_hands": 1,
    "detection_confidence": 0.65,
    "tracking_confidence": 0.55,
    "smoothing": 0.35,             # 0..1, higher = steadier cursor
    # Media keys only fire when a window whose title contains one of these
    # tokens is focused (Windows). Empty list = send to any window.
    "media_window_allowlist": ["youtube", "netflix", "vlc", "mpv", "media player",
                               "kodi", "plex", "spotify", "disney", "prime video",
                               "twitch", "dailymotion", "mpc-hc", "kmplayer", "potplayer"],
    "sensitivity": 1.4,            # cursor speed multiplier
    "control_margin": 0.18,        # camera-area margin mapped to full screen
    "click_debounce_sec": 0.12,    # must stay well below double_click_window_sec
    "double_click_window_sec": 0.40,
    "drag_hold_sec": 0.30,
    "scroll_gain": 900,
    "swipe_window_sec": 0.30,
    "swipe_min_travel": 0.22,      # normalized frame units
    "hold_trigger_sec": 0.50,      # palm / fingers holds
    "fist_hold_sec": 1.00,            # hold time for ONE fist
    "fist_confirm_window_sec": 3.0,  # close needs a SECOND fist within this window
    "gesture_cooldown_sec": 0.80,
    "pinch_ratio": 0.35,           # pinch distance / hand size
    "camera_reconnect_max_sec": 20,
    "start_mode": "mouse",         # mouse | media
    "show_landmarks": True,
    "low_light_threshold": 35,
    "edge_margin_px": 4,           # keep cursor off exact corners (fail-safe)
    # --- stabilizer (anti false-positive layer, see gestures.HandStabilizer) ---
    "stab_window_frames": 5,       # majority vote over the last N frames
    "pinch_release_ratio": 0.50,   # pinch hysteresis: enters at pinch_ratio, leaves above this
    "pinch_confirm_frames": 2,     # a pinch must persist this many frames to count
    "settle_sec": 0.35,            # ignore gestures right after the hand appears
    "lost_grace_sec": 0.15,        # tolerate short tracking dropouts
    "pause_hold_sec": 1.5,         # long open-palm hold = pause/resume in video mode
}

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Sane ranges for numeric config keys (inclusive). A merged user value
# outside its range is rejected by validate_config, not silently trusted.
_CONFIG_RANGES = {
    "camera_index": (-1, 16),
    "freeze_reconnect_sec": (0.1, 120.0),
    "frame_width": (160, 3840),
    "frame_height": (120, 2160),
    "max_num_hands": (1, 4),
    "detection_confidence": (0.0, 1.0),
    "tracking_confidence": (0.0, 1.0),
    "smoothing": (0.0, 1.0),
    "sensitivity": (0.1, 10.0),
    "control_margin": (0.0, 1.0),
    "click_debounce_sec": (0.0, 2.0),
    "double_click_window_sec": (0.05, 3.0),
    "drag_hold_sec": (0.0, 3.0),
    "scroll_gain": (10, 10000),
    "swipe_window_sec": (0.05, 3.0),
    "swipe_min_travel": (0.01, 1.0),
    "hold_trigger_sec": (0.05, 5.0),
    "fist_hold_sec": (0.1, 5.0),
    "fist_confirm_window_sec": (0.1, 30.0),
    "gesture_cooldown_sec": (0.0, 5.0),
    "pinch_ratio": (0.0, 1.0),
    "camera_reconnect_max_sec": (1, 300),
    "low_light_threshold": (0, 255),
    "edge_margin_px": (0, 100),
    "stab_window_frames": (1, 30),
    "pinch_release_ratio": (0.0, 1.0),
    "pinch_confirm_frames": (1, 10),
    "settle_sec": (0.0, 3.0),
    "lost_grace_sec": (0.0, 3.0),
    "pause_hold_sec": (0.1, 10.0),
}

# Keys whose values must be whole numbers (a float is accepted only when it
# is integral, e.g. 640.0 from a hand-edited JSON file).
_CONFIG_INT_KEYS = {
    "camera_index", "frame_width", "frame_height", "max_num_hands",
    "low_light_threshold", "edge_margin_px", "stab_window_frames",
    "pinch_confirm_frames",
}

_CONFIG_CHOICES = {
    "start_mode": ("mouse", "media"),
}


def _valid_config_value(key: str, value) -> bool:
    """True when `value` is a sane value for the known config `key`."""
    default = DEFAULT_CONFIG[key]
    if key == "last_camera":
        if value is None:
            return True
        return (isinstance(value, dict)
                and isinstance(value.get("index"), int)
                and not isinstance(value.get("index"), bool)
                and value.get("index", -1) >= 0
                and isinstance(value.get("backend"), int)
                and not isinstance(value.get("backend"), bool))
    if isinstance(default, bool):
        return isinstance(value, bool)
    if key in _CONFIG_RANGES:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if key in _CONFIG_INT_KEYS and isinstance(value, float) and not value.is_integer():
            return False
        low, high = _CONFIG_RANGES[key]
        return low <= value <= high
    if isinstance(default, str):
        if not isinstance(value, str):
            return False
        choices = _CONFIG_CHOICES.get(key)
        return choices is None or value in choices
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return True


def validate_config(cfg: dict) -> dict:
    """Return `cfg` with every invalid known-key value replaced by its
    default (with a warning naming the key). Unknown keys are left alone,
    and valid values are kept exactly as given."""
    cfg = dict(cfg)
    for key, default in DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = default
            continue
        if not _valid_config_value(key, cfg[key]):
            print(f"[config] invalid value for '{key}' ({cfg[key]!r}); "
                  f"using default {default!r}")
            cfg[key] = default
    return cfg


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                user_cfg = json.load(fh)
            if isinstance(user_cfg, dict):
                cfg.update(user_cfg)
    except Exception as exc:  # corrupt config should never kill the app
        print(f"[config] could not read config.json ({exc}); using defaults")
    return validate_config(cfg)


def save_config(cfg: dict) -> None:
    """Write only keys that differ from the defaults (item 16): the file stays
    small, and new defaults in future versions reach existing installs."""
    diff = {k: v for k, v in cfg.items() if k not in DEFAULT_CONFIG or DEFAULT_CONFIG[k] != v}
    try:
        if diff or os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(diff, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"[config] could not save config.json ({exc})")


# --------------------------------------------------------------------------
# HUD drawing
# --------------------------------------------------------------------------
def draw_hud(frame, mode: str, paused: bool, gesture: str, fps: float, status: str,
             low_light: bool, hand_found: bool, active_window: str = "") -> None:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 92), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    mode_txt = "MOUSE MODE" if mode == "mouse" else "VIDEO MODE"
    if mode != "mouse" and active_window:
        mode_txt += f"  |  {active_window[:38]}"
    color = (0, 220, 120) if mode == "mouse" else (255, 170, 40)
    cv2.putText(frame, mode_txt, (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    info = f"FPS {fps:4.0f}"
    cv2.putText(frame, info, (w - 120, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    if paused:
        cv2.putText(frame, "PAUSED (open palm to resume)", (w // 2 - 190, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 90, 255), 2)
    elif gesture:
        cv2.putText(frame, gesture, (w // 2 - 80, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 255), 2)

    line = status
    if not line:
        if not hand_found:
            line = "Show your hand to the camera"
        elif low_light:
            line = "Low light - gestures may be unreliable, add lighting"
    if line:
        cv2.putText(frame, line, (14, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 200, 255), 1)

    hint = "Q quit | M switch mouse/video | +/- sensitivity | P pause"
    cv2.putText(frame, hint, (14, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)




# --------------------------------------------------------------------------
# Main application
# --------------------------------------------------------------------------
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eidak.log")


def _setup_logging() -> logging.Logger:
    """Rotating log file (item 16): recurring problems become diagnosable after
    the fact instead of living only in a closed console window."""
    logger = logging.getLogger("eidak")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def _failsafe_corner_hit() -> bool:
    """pyautogui's FAILSAFE only fires on its own calls; a user slamming the mouse
    into a corner between calls would not trip it. Check once per frame (item 3a)."""
    try:
        x, y = pyautogui.position()
        w, h = pyautogui.size()
        margin = 10  # corner zone in px
        return (x <= margin and y <= margin) or (x >= w - 1 - margin and y <= margin) \
            or (x <= margin and y >= h - 1 - margin) or (x >= w - 1 - margin and y >= h - 1 - margin)
    except Exception:
        return False


def run(cfg: dict) -> int:
    log = _setup_logging()
    missing = []
    if cv2 is None:
        missing.append("opencv-python")
    if mp is None:
        missing.append("mediapipe")
    if missing:
        print("Missing packages: " + ", ".join(missing))
        print("Install them with:  pip install -r requirements.txt")
        return 1
    if pyautogui is None:
        print("pyautogui could not start (no display?). The app needs a desktop session.")
        return 1

    camera = CameraManager(cfg)
    print("Looking for a working camera...")
    if not camera.open(progress=lambda msg: print("  " + msg)):
        print("Could not open any camera.")
        if camera.failure_kind == OPENED_NO_FRAMES:
            print("A camera was found but delivered no frames.")
            print("  - close other apps that use the camera (Zoom/Teams/Camera app)")
            print("  - " + PRIVACY_HINT)
        elif camera.failure_kind == BLACK_FRAMES:
            print("The camera only sends black or grayscale frames - check the lens cover;")
            print("an IR-only camera (e.g. Windows Hello) cannot be used for hand tracking.")
        else:
            print("No usable camera was detected - check the cable / drivers, that no other")
            print("app is using the webcam, and the Windows camera privacy settings.")
        print("Run  python hand_gesture_control.py --diagnose  for a full camera report.")
        log.warning("camera open failed: %s (%s)", camera.failure_kind or NO_DEVICE, camera.last_error)
        return 1
    print(f"Camera {camera.active_index} via {camera.backend_name} is running.")

    # Camera is already open. Guard every later initialization so a failure
    # (PyAutoGUI screen lookup, MediaPipe model creation, or window creation)
    # cannot leave the camera handle locked until the process exits.
    hands = None
    try:
        sink = PyAutoSink()
        pipeline = GesturePipeline(cfg)
        dispatcher = Dispatcher(sink, cfg)
        hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=int(cfg["max_num_hands"]),
            min_detection_confidence=float(cfg["detection_confidence"]),
            min_tracking_confidence=float(cfg["tracking_confidence"]),
            model_complexity=0,  # lighter model: roughly halves CPU per frame (item 15)
        )
        drawing = mp.solutions.drawing_utils
        styles = mp.solutions.drawing_styles
        window = "Eidak - Hand Gesture PC Control"
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    except Exception as exc:
        log.exception("startup initialization failed")
        print(f"Could not initialize Eidak: {exc}")
        if hands is not None:
            try:
                hands.close()
            except Exception:
                log.exception("failed to close MediaPipe during startup cleanup")
        try:
            camera.release()
        except Exception:
            log.exception("failed to release camera during startup cleanup")
        try:
            cv2.destroyAllWindows()
        except Exception:
            log.exception("failed to destroy OpenCV windows during startup cleanup")
        return 1

    hotkey_registered = False
    if keyboard is not None:
        try:
            quit_flag = {"quit": False}
            keyboard.add_hotkey("ctrl+alt+q", lambda: quit_flag.__setitem__("quit", True))
            hotkey_registered = True
            print("Global quit hotkey: Ctrl+Alt+Q")
        except Exception as exc:
            quit_flag = {"quit": False}
            log.info("keyboard hotkey unavailable: %s", exc)
    else:
        quit_flag = {"quit": False}

    def _emergency_stop(reason: str) -> None:
        try:
            dispatcher.release_all(force=True)
        except Exception:
            pass
        print(reason)
        log.warning("emergency stop: %s", reason)

    prev_t = time.time()
    fps = 0.0
    frame_errors = 0          # consecutive per-frame failures (item 16)
    idle_since = None         # last time a hand was seen; idle = slow down (item 15)
    idle_frame = 0
    print("Running. Q quits, M switches mouse/video mode, P pauses.")
    log.info("run started (camera %s via %s)", camera.active_index, camera.backend_name)
    try:
        while True:
            if quit_flag["quit"]:
                print("Quit hotkey pressed.")
                break
            try:
                ok, frame, status = camera.read()
            except Exception:
                frame_errors += 1
                log.exception("camera read error #%d", frame_errors)
                if frame_errors >= 30:
                    _emergency_stop(f"Too many camera errors ({frame_errors}); stopping.")
                    return 1
                time.sleep(0.05)
                continue
            if not ok:
                canvas = np.zeros((480, 800, 3), dtype=np.uint8)
                draw_hud(canvas, dispatcher.mode, dispatcher.paused, "", fps,
                         status or "Camera problem", False, False)
                cv2.imshow(window, canvas)
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    break
                if _window_closed(window):
                    break
                continue

            frame = cv2.flip(frame, 1)  # selfie view: hand right = cursor right

            # When no hand has been around for a while, process every 3rd frame:
            # hand tracking is the expensive part (item 15).
            idle = idle_since is not None and (time.time() - idle_since) > 5.0
            if idle:
                idle_frame += 1
                if idle_frame % 3 != 0:
                    cv2.imshow(window, frame)
                    key = cv2.waitKey(10) & 0xFF
                    if key == ord("q") or _window_closed(window):
                        break
                    continue

            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb.flags.writeable = False
                results = hands.process(rgb)

                lm = None
                if results.multi_hand_landmarks:
                    lm = [(p.x, p.y, p.z) for p in results.multi_hand_landmarks[0].landmark]
                    if cfg.get("show_landmarks", True):
                        drawing.draw_landmarks(
                            frame,
                            results.multi_hand_landmarks[0],
                            mp.solutions.hands.HAND_CONNECTIONS,
                            styles.get_default_hand_landmarks_style(),
                            styles.get_default_hand_connections_style(),
                        )

                now = time.time()
                state, events = pipeline.process(lm, now)
                if state.found:
                    idle_since = now
                    idle_frame = 0
                elif idle_since is None:
                    idle_since = now
                try:
                    dispatcher.handle(events, state)
                except pyautogui.FailSafeException:
                    # Never leave a held button or drag state behind on emergency stop;
                    # a cleanup failure must not block the stop itself.
                    _emergency_stop("Emergency stop triggered (mouse in screen corner).")
                    break
                frame_errors = 0
            except pyautogui.FailSafeException:
                _emergency_stop("Emergency stop triggered (mouse in screen corner).")
                break
            except Exception:
                frame_errors += 1
                log.exception("frame processing error #%d", frame_errors)
                if frame_errors >= 30:
                    _emergency_stop(f"Too many processing errors ({frame_errors}); stopping.")
                    return 1
                continue

            # Per-frame fail-safe check: catches corner-slams between pyautogui calls (item 3a)
            if _failsafe_corner_hit():
                _emergency_stop("Emergency stop triggered (mouse in screen corner).")
                break

            dt = now - prev_t
            prev_t = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            draw_hud(frame, dispatcher.mode, dispatcher.paused, pipeline.last_gesture,
                     fps, dispatcher.notice or status, camera.low_light, state.found,
                     active_window=dispatcher.active_window)
            cv2.imshow(window, frame)

            key = cv2.waitKey(1 if not idle else 10) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("m"):
                print("Mode:", dispatcher.toggle_mode())
            elif key == ord("p"):
                dispatcher.paused = not dispatcher.paused
            elif key in (ord("+"), ord("=")):
                cfg["sensitivity"] = round(min(3.0, float(cfg["sensitivity"]) + 0.1), 2)
                print("Sensitivity:", cfg["sensitivity"])
            elif key == ord("-"):
                cfg["sensitivity"] = round(max(0.4, float(cfg["sensitivity"]) - 0.1), 2)
                print("Sensitivity:", cfg["sensitivity"])

            # Clicking the window's X must also quit (item 4)
            if _window_closed(window):
                break
    except KeyboardInterrupt:
        pass
    finally:
        if hotkey_registered and keyboard is not None:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
        try:
            dispatcher.release_all(force=True)  # never leave a mouse button held down
        except Exception:
            pass
        save_config(cfg)
        # Cleanup each resource independently: one failing close must not
        # prevent the camera or OpenCV windows from being released.
        if hands is not None:
            try:
                hands.close()
            except Exception:
                log.exception("failed to close MediaPipe")
        try:
            camera.release()
        except Exception:
            log.exception("failed to release camera")
        try:
            cv2.destroyAllWindows()
        except Exception:
            log.exception("failed to destroy OpenCV windows")
        log.info("run stopped")
    print("Stopped.")
    return 0


def _window_closed(window: str) -> bool:
    """True when the user clicked the window's X (item 4)."""
    try:
        return cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1
    except Exception:
        return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Eidak - hand gesture PC control")
    parser.add_argument("--mode", choices=["mouse", "media"], help="starting mode")
    parser.add_argument("--camera", type=int, help="force a camera index (strict: no fallback)")
    parser.add_argument("--list-cameras", action="store_true", help="list detected cameras and exit")
    parser.add_argument("--sensitivity", type=float, help="cursor sensitivity 0.4 - 3.0")
    parser.add_argument("--diagnose", action="store_true", help="camera diagnostics and exit")
    args = parser.parse_args(argv)

    cfg = load_config()
    if args.mode:
        cfg["start_mode"] = args.mode
    if args.camera is not None:
        cfg["camera_index"] = args.camera
        cfg["camera_strict"] = True  # --camera means THIS camera, not a hint (item 12)
    if args.sensitivity:
        cfg["sensitivity"] = args.sensitivity

    if args.list_cameras:
        return list_cameras(cfg)
    if args.diagnose:
        return diagnose_cameras(cfg)
    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
