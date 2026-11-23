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
import math
import os
import platform
import sys
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Deque, Dict, List, Optional, Tuple

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


# --------------------------------------------------------------------------
# Module split (step 0): camera handling and gesture logic live in their own
# modules and are re-exported here, so existing imports keep working.
# --------------------------------------------------------------------------
from camera import CameraManager, diagnose_cameras
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
    "frame_width": 1280,
    "frame_height": 720,
    "max_num_hands": 1,
    "detection_confidence": 0.65,
    "tracking_confidence": 0.55,
    "smoothing": 0.35,             # 0..1, higher = steadier cursor
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
    return cfg


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"[config] could not save config.json ({exc})")


# --------------------------------------------------------------------------
# HUD drawing
# --------------------------------------------------------------------------
def draw_hud(frame, mode: str, paused: bool, gesture: str, fps: float, status: str,
             low_light: bool, hand_found: bool) -> None:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 92), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    mode_txt = "MOUSE MODE" if mode == "mouse" else "VIDEO MODE"
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
def run(cfg: dict) -> int:
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
    if not camera.open():
        print("Could not open any camera.")
        print("Run  python hand_gesture_control.py --diagnose  for a full camera report.")
        return 1
    print(f"Camera {camera.active_index} via {camera.backend_name} is running.")

    sink = PyAutoSink()
    pipeline = GesturePipeline(cfg)
    dispatcher = Dispatcher(sink, cfg)

    hands = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=int(cfg["max_num_hands"]),
        min_detection_confidence=float(cfg["detection_confidence"]),
        min_tracking_confidence=float(cfg["tracking_confidence"]),
    )
    drawing = mp.solutions.drawing_utils
    styles = mp.solutions.drawing_styles

    window = "Eidak - Hand Gesture PC Control"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    prev_t = time.time()
    fps = 0.0
    print("Running. Q quits, M switches mouse/video mode, P pauses.")
    try:
        while True:
            ok, frame, status = camera.read()
            if not ok:
                canvas = np.zeros((480, 800, 3), dtype=np.uint8)
                draw_hud(canvas, dispatcher.mode, dispatcher.paused, "", fps,
                         status or "Camera problem", False, False)
                cv2.imshow(window, canvas)
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    break
                continue

            frame = cv2.flip(frame, 1)  # selfie view: hand right = cursor right
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
            try:
                dispatcher.handle(events, state)
            except pyautogui.FailSafeException:
                print("Emergency stop triggered (mouse in screen corner).")
                break

            dt = now - prev_t
            prev_t = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            draw_hud(frame, dispatcher.mode, dispatcher.paused, pipeline.last_gesture,
                     fps, dispatcher.notice or status, camera.low_light, state.found)
            cv2.imshow(window, frame)

            key = cv2.waitKey(1) & 0xFF
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
    except KeyboardInterrupt:
        pass
    finally:
        try:
            dispatcher.release_all(force=True)  # never leave a mouse button held down
        except Exception:
            pass
        save_config(cfg)
        hands.close()
        camera.release()
        cv2.destroyAllWindows()
    print("Stopped.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Eidak - hand gesture PC control")
    parser.add_argument("--mode", choices=["mouse", "media"], help="starting mode")
    parser.add_argument("--camera", type=int, help="force a camera index")
    parser.add_argument("--sensitivity", type=float, help="cursor sensitivity 0.4 - 3.0")
    parser.add_argument("--diagnose", action="store_true", help="camera diagnostics and exit")
    args = parser.parse_args(argv)

    cfg = load_config()
    if args.mode:
        cfg["start_mode"] = args.mode
    if args.camera is not None:
        cfg["camera_index"] = args.camera
    if args.sensitivity:
        cfg["sensitivity"] = args.sensitivity

    if args.diagnose:
        return diagnose_cameras(cfg)
    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
