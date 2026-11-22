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
# MediaPipe hand landmark indices
# --------------------------------------------------------------------------
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

FINGERS = {
    "index": (INDEX_MCP, INDEX_PIP, INDEX_TIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP),
    "ring": (RING_MCP, RING_PIP, RING_TIP),
    "pinky": (PINKY_MCP, PINKY_PIP, PINKY_TIP),
}

Point = Tuple[float, float, float]
Landmarks = List[Point]


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
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
    "click_debounce_sec": 0.25,
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
# Camera manager: the part that treats the camera as unreliable hardware
# --------------------------------------------------------------------------
class CameraManager:
    """Opens the camera defensively and recovers when frames stop flowing.

    - Probes several camera indices and several OS backends.
    - Verifies real, non-black frames before accepting a camera.
    - Detects mid-run freezes/disconnects and reconnects with backoff.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.cap = None
        self.active_index: Optional[int] = None
        self.active_backend: Optional[int] = None
        self.backend_name = ""
        self._fail_frames = 0
        self._last_reconnect_attempt = 0.0
        self._reconnect_delay = 1.0
        self.last_error = ""
        self.low_light = False

    def _backends(self) -> List[Tuple[int, str]]:
        system = platform.system()
        if cv2 is None:
            return []
        if system == "Windows":
            return [(cv2.CAP_DSHOW, "DirectShow"), (cv2.CAP_MSMF, "MediaFoundation"), (cv2.CAP_ANY, "Auto")]
        if system == "Darwin":
            return [(cv2.CAP_AVFOUNDATION, "AVFoundation"), (cv2.CAP_ANY, "Auto")]
        return [(cv2.CAP_V4L2, "V4L2"), (cv2.CAP_ANY, "Auto")]

    def _indices(self) -> List[int]:
        preferred = self.cfg.get("camera_index", -1)
        order = list(range(0, 5))
        if isinstance(preferred, int) and preferred >= 0:
            order = [preferred] + [i for i in order if i != preferred]
        return order

    def _validate(self, cap) -> bool:
        """Require several real, non-black frames before trusting a camera."""
        deadline = time.time() + 2.5
        got = 0
        while time.time() < deadline and got < 3:
            ok, frame = cap.read()
            if ok and frame is not None and frame.size > 0:
                if float(np.mean(frame)) > 5.0:
                    got += 1
            else:
                time.sleep(0.05)
        return got >= 3

    def open(self) -> bool:
        self.release()
        for index in self._indices():
            for backend, name in self._backends():
                cap = None
                try:
                    cap = cv2.VideoCapture(index, backend)
                    if not cap.isOpened():
                        cap.release()
                        continue
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg["frame_width"])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg["frame_height"])
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    if self._validate(cap):
                        self.cap = cap
                        self.active_index = index
                        self.active_backend = backend
                        self.backend_name = name
                        self._fail_frames = 0
                        self._reconnect_delay = 1.0
                        self.last_error = ""
                        return True
                    cap.release()
                except Exception as exc:
                    self.last_error = str(exc)
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
        self.last_error = self.last_error or "No working camera found"
        return False

    def read(self) -> Tuple[bool, Optional[np.ndarray], str]:
        """Returns (ok, frame, status_message). Reconnects automatically."""
        if self.cap is None:
            return False, None, "Camera is not open"
        try:
            ok, frame = self.cap.read()
        except Exception as exc:
            ok, frame = False, None
            self.last_error = str(exc)
        if ok and frame is not None and frame.size > 0:
            self._fail_frames = 0
            brightness = float(np.mean(frame))
            self.low_light = brightness < float(self.cfg.get("low_light_threshold", 35))
            return True, frame, ""
        self._fail_frames += 1
        if self._fail_frames < 15:
            return False, None, "Camera frame dropped..."
        # The camera froze or was unplugged: try to bring it back.
        now = time.time()
        if now - self._last_reconnect_attempt >= self._reconnect_delay:
            self._last_reconnect_attempt = now
            if self.open():
                return False, None, "Camera reconnected"
            self._reconnect_delay = min(self._reconnect_delay * 2, float(self.cfg["camera_reconnect_max_sec"]))
        return False, None, "Reconnecting camera... check the cable or close other camera apps"

    def release(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None


# --------------------------------------------------------------------------
# Hand geometry
# --------------------------------------------------------------------------
def dist(a: Point, b: Point) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


@dataclass
class HandState:
    """Static description of the hand in a single frame."""

    found: bool = False
    fingers_up: Dict[str, bool] = field(default_factory=dict)  # index/middle/ring/pinky
    thumb_up: bool = False
    thumb_extended: bool = False
    pinch_index: bool = False
    pinch_middle: bool = False
    index_tip: Point = (0.5, 0.5, 0.0)
    centroid: Point = (0.5, 0.5, 0.0)
    landmarks: Optional[Landmarks] = None

    def count_up(self) -> int:
        return sum(1 for v in self.fingers_up.values() if v)


def classify_hand(lm: Landmarks, pinch_ratio: float = 0.35) -> HandState:
    """Pure-geometry classification, independent of MediaPipe objects."""
    if not lm or len(lm) < 21:
        return HandState()
    hand_size = max(dist(lm[WRIST], lm[MIDDLE_MCP]), 1e-6)

    fingers_up = {}
    for name, (mcp, pip, tip) in FINGERS.items():
        # Finger counts as up when its tip is clearly above its PIP joint
        # and reasonably far from the wrist.
        fingers_up[name] = (lm[tip][1] < lm[pip][1] - 0.02) and (
            dist(lm[tip], lm[WRIST]) > dist(lm[pip], lm[WRIST])
        )

    thumb_up = lm[THUMB_TIP][1] < lm[THUMB_IP][1] - 0.02
    thumb_extended = dist(lm[THUMB_TIP], lm[PINKY_MCP]) > dist(lm[THUMB_IP], lm[PINKY_MCP]) * 1.15

    # A pinch is thumb tip touching the finger tip while that finger is
    # extended away from the wrist (a folded fist must NOT read as a pinch).
    extended_out = lambda tip: dist(lm[tip], lm[WRIST]) > hand_size * 1.2
    pinch_index = dist(lm[THUMB_TIP], lm[INDEX_TIP]) < hand_size * pinch_ratio and extended_out(INDEX_TIP)
    pinch_middle = dist(lm[THUMB_TIP], lm[MIDDLE_TIP]) < hand_size * pinch_ratio and extended_out(MIDDLE_TIP)

    cx = sum(p[0] for p in lm) / len(lm)
    cy = sum(p[1] for p in lm) / len(lm)

    return HandState(
        found=True,
        fingers_up=fingers_up,
        thumb_up=thumb_up,
        thumb_extended=thumb_extended,
        pinch_index=pinch_index,
        pinch_middle=pinch_middle,
        index_tip=lm[INDEX_TIP],
        centroid=(cx, cy, 0.0),
        landmarks=lm,
    )


# --------------------------------------------------------------------------
# Gesture engine: turns per-frame states into debounced events
# --------------------------------------------------------------------------
@dataclass
class GestureEvent:
    name: str
    value: float = 0.0


class GestureEngine:
    """Temporal layer: clicks, double clicks, drags, holds and swipes."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._centroid_hist: Deque[Tuple[float, float, float]] = deque(maxlen=40)
        self._pinch_index_down = False
        self._pinch_middle_down = False
        self._pinch_press_t = 0.0
        self._dragging = False
        self._last_click_t = 0.0
        self._last_event_t: Dict[str, float] = {}
        self._hold_start: Dict[str, float] = {}
        self._fired_holds: set = set()
        self.last_gesture = ""

    # -- helpers -----------------------------------------------------------
    def _cooled_down(self, name: str, now: float) -> bool:
        if name == "click":
            return now - self._last_event_t.get(name, -10.0) >= float(self.cfg["click_debounce_sec"])
        return now - self._last_event_t.get(name, -10.0) >= float(self.cfg["gesture_cooldown_sec"])

    def _mark(self, name: str, now: float) -> None:
        self._last_event_t[name] = now
        self.last_gesture = name

    def _update_hold(self, key: str, active: bool, need: float, now: float) -> bool:
        """Edge trigger: True once per continuous hold that reaches `need` seconds."""
        if active:
            start = self._hold_start.setdefault(key, now)
            if key not in self._fired_holds and now - start >= need:
                self._fired_holds.add(key)
                return True
        else:
            self._hold_start.pop(key, None)
            self._fired_holds.discard(key)
        return False

    def reset(self) -> None:
        self._centroid_hist.clear()
        self._pinch_index_down = False
        self._pinch_middle_down = False
        self._dragging = False
        self._hold_start.clear()
        self._fired_holds.clear()

    # -- main --------------------------------------------------------------
    def update(self, state: HandState, now: Optional[float] = None) -> List[GestureEvent]:
        now = time.time() if now is None else now
        events: List[GestureEvent] = []
        if not state.found:
            self.reset()
            return events

        cx, cy, _ = state.centroid
        self._centroid_hist.append((now, cx, cy))
        up = state.count_up()

        # --- pinches: click / double-click / drag -------------------------
        pinch_now = state.pinch_index
        if pinch_now and not self._pinch_index_down:
            self._pinch_press_t = now
        if not pinch_now and self._pinch_index_down:
            held = now - self._pinch_press_t
            if self._dragging:
                self._dragging = False
                events.append(GestureEvent("DRAG_END"))
            elif held < float(self.cfg["drag_hold_sec"]) and self._cooled_down("click", now):
                if now - self._last_click_t <= float(self.cfg["double_click_window_sec"]):
                    events.append(GestureEvent("DOUBLE_CLICK"))
                    self._last_click_t = 0.0
                else:
                    events.append(GestureEvent("LEFT_CLICK"))
                    self._last_click_t = now
                self._mark("click", now)
        if pinch_now and not self._dragging and now - self._pinch_press_t >= float(self.cfg["drag_hold_sec"]):
            self._dragging = True
            events.append(GestureEvent("DRAG_START"))
        self._pinch_index_down = pinch_now

        mid_now = state.pinch_middle
        if not mid_now and self._pinch_middle_down and self._cooled_down("click", now):
            events.append(GestureEvent("RIGHT_CLICK"))
            self._mark("click", now)
        self._pinch_middle_down = mid_now

        # --- continuous states --------------------------------------------
        only_index = up == 1 and state.fingers_up.get("index") and not pinch_now
        index_middle = (
            up == 2
            and state.fingers_up.get("index")
            and state.fingers_up.get("middle")
            and not pinch_now
            and not state.pinch_middle  # right-click pose must not scroll
        )
        if only_index or self._dragging:
            events.append(GestureEvent("MOVE", 0.0))
        if index_middle and len(self._centroid_hist) >= 2:
            _, _, prev_y = self._centroid_hist[-2]
            events.append(GestureEvent("SCROLL", cy - prev_y))

        # --- swipes (open hand moving fast) --------------------------------
        if up >= 3 and len(self._centroid_hist) >= 3:
            window = float(self.cfg["swipe_window_sec"])
            t0, x0, y0 = None, None, None
            for t, hx, hy in reversed(self._centroid_hist):
                if now - t <= window:
                    t0, x0, y0 = t, hx, hy
                else:
                    break
            if t0 is not None and now - t0 >= window * 0.6:
                dx, dy = cx - x0, cy - y0
                travel = float(self.cfg["swipe_min_travel"])
                if self._cooled_down("swipe", now):
                    if dx > travel and abs(dy) < travel * 0.6:
                        events.append(GestureEvent("SWIPE_RIGHT"))
                        self._mark("swipe", now)
                    elif dx < -travel and abs(dy) < travel * 0.6:
                        events.append(GestureEvent("SWIPE_LEFT"))
                        self._mark("swipe", now)
                    elif dy < -travel and abs(dx) < travel * 0.6:
                        events.append(GestureEvent("SWIPE_UP"))
                        self._mark("swipe", now)
                    elif dy > travel and abs(dx) < travel * 0.6:
                        events.append(GestureEvent("SWIPE_DOWN"))
                        self._mark("swipe", now)

        # --- holds ----------------------------------------------------------
        hold_need = float(self.cfg["hold_trigger_sec"])
        palm = up >= 4 and state.thumb_extended and not pinch_now
        if self._update_hold("palm", palm, hold_need, now) and self._cooled_down("palm", now):
            events.append(GestureEvent("PALM"))
            self._mark("palm", now)

        fist = up == 0 and not state.thumb_extended and not pinch_now
        if self._update_hold("fist", fist, float(self.cfg["fist_hold_sec"]), now) and self._cooled_down("fist", now):
            events.append(GestureEvent("FIST"))
            self._mark("fist", now)

        three = up == 3 and state.fingers_up.get("index") and state.fingers_up.get("middle") and state.fingers_up.get("ring")
        if self._update_hold("three", three, hold_need, now) and self._cooled_down("three", now):
            events.append(GestureEvent("THREE_FINGERS"))
            self._mark("three", now)

        four_no_thumb = up >= 4 and not state.thumb_extended and not pinch_now
        if self._update_hold("four", four_no_thumb, hold_need, now) and self._cooled_down("four", now):
            events.append(GestureEvent("FOUR_FINGERS"))
            self._mark("four", now)

        thumbs_up = state.thumb_up and up == 0
        if self._update_hold("thumbsup", thumbs_up, hold_need, now) and self._cooled_down("thumbsup", now):
            events.append(GestureEvent("THUMBS_UP"))
            self._mark("thumbsup", now)

        return events


# --------------------------------------------------------------------------
# Action sinks (real one drives the OS; null one is for tests)
# --------------------------------------------------------------------------
class PyAutoSink:
    name = "pyautogui"

    def __init__(self):
        if pyautogui is None:
            raise RuntimeError("pyautogui is unavailable on this machine")
        self.screen_w, self.screen_h = pyautogui.size()
        self._dragging = False

    def move_to(self, x: float, y: float) -> None:
        pyautogui.moveTo(int(x), int(y), _pause=False)

    def left_click(self) -> None:
        pyautogui.click(button="left", _pause=False)

    def right_click(self) -> None:
        pyautogui.click(button="right", _pause=False)

    def double_click(self) -> None:
        pyautogui.doubleClick(_pause=False)

    def drag_start(self) -> None:
        self._dragging = True
        pyautogui.mouseDown(_pause=False)

    def drag_end(self) -> None:
        self._dragging = False
        pyautogui.mouseUp(_pause=False)

    def scroll(self, amount: float) -> None:
        if amount:
            pyautogui.scroll(int(amount), _pause=False)

    def press(self, key: str) -> None:
        pyautogui.press(key, _pause=False)

    def hotkey(self, *keys: str) -> None:
        pyautogui.hotkey(*keys, _pause=False)


class NullSink:
    """Records actions instead of performing them (used by the test suite)."""

    name = "null"

    def __init__(self):
        self.screen_w, self.screen_h = 1920, 1080
        self.calls: List[Tuple[str, tuple]] = []

    def _rec(self, name, *args):
        self.calls.append((name, args))

    def move_to(self, x, y): self._rec("move_to", x, y)
    def left_click(self): self._rec("left_click")
    def right_click(self): self._rec("right_click")
    def double_click(self): self._rec("double_click")
    def drag_start(self): self._rec("drag_start")
    def drag_end(self): self._rec("drag_end")
    def scroll(self, amount): self._rec("scroll", amount)
    def press(self, key): self._rec("press", key)
    def hotkey(self, *keys): self._rec("hotkey", *keys)


# --------------------------------------------------------------------------
# Dispatcher: gesture events -> OS actions, per mode
# --------------------------------------------------------------------------
class Dispatcher:
    def __init__(self, sink, cfg: dict):
        self.sink = sink
        self.cfg = cfg
        self.mode = cfg.get("start_mode", "mouse")
        self.paused = False
        self._smooth: Optional[Tuple[float, float]] = None
        self._fist_armed_until = 0.0   # destructive close needs a double-fist
        self.notice = ""               # transient HUD message

    def toggle_mode(self) -> str:
        self.mode = "media" if self.mode == "mouse" else "mouse"
        return self.mode

    def _map_to_screen(self, tip: Point) -> Tuple[float, float]:
        m = float(self.cfg["control_margin"])
        nx = (tip[0] - m) / max(1e-6, 1 - 2 * m)
        ny = (tip[1] - m) / max(1e-6, 1 - 2 * m)
        nx = min(max(nx, 0.0), 1.0)
        ny = min(max(ny, 0.0), 1.0)
        sens = float(self.cfg["sensitivity"])
        # Sensitivity expands movement around the screen center.
        sx = 0.5 + (nx - 0.5) * sens
        sy = 0.5 + (ny - 0.5) * sens
        # Stay a few pixels inside the screen: PyAutoGUI's fail-safe fires on the
        # exact corner pixels, which would otherwise quit the app whenever the
        # hand reaches a corner (e.g. a window's close button).
        edge = int(self.cfg.get("edge_margin_px", 4))
        x = edge + min(max(sx, 0.0), 1.0) * (self.sink.screen_w - 1 - 2 * edge)
        y = edge + min(max(sy, 0.0), 1.0) * (self.sink.screen_h - 1 - 2 * edge)
        if self._smooth is None:
            self._smooth = (x, y)
        alpha = 1.0 - float(self.cfg["smoothing"])
        self._smooth = (
            self._smooth[0] + (x - self._smooth[0]) * alpha,
            self._smooth[1] + (y - self._smooth[1]) * alpha,
        )
        return self._smooth

    def handle(self, events: List[GestureEvent], state: HandState) -> None:
        if self._fist_armed_until and time.monotonic() > self._fist_armed_until:
            self._fist_armed_until = 0.0
            self.notice = ""
        for ev in events:
            if self.mode == "mouse":
                self._handle_mouse(ev, state)
            else:
                self._handle_media(ev, state)

    def _handle_mouse(self, ev: GestureEvent, state: HandState) -> None:
        if ev.name == "PALM":
            self.paused = not self.paused
            return
        if self.paused:
            return
        if ev.name == "MOVE":
            x, y = self._map_to_screen(state.index_tip)
            self.sink.move_to(x, y)
        elif ev.name == "LEFT_CLICK":
            self.sink.left_click()
        elif ev.name == "RIGHT_CLICK":
            self.sink.right_click()
        elif ev.name == "DOUBLE_CLICK":
            self.sink.double_click()
        elif ev.name == "DRAG_START":
            self.sink.drag_start()
        elif ev.name == "DRAG_END":
            self.sink.drag_end()
        elif ev.name == "SCROLL":
            self.sink.scroll(-ev.value * float(self.cfg["scroll_gain"]))

    def _handle_media(self, ev: GestureEvent, state: HandState) -> None:
        # Closing is destructive (Ctrl+W hits whatever window has focus), so a
        # single fist only ARMS it; a second fist inside the confirm window
        # actually closes. One stray fist can no longer close anything.
        if ev.name == "FIST":
            now = time.monotonic()
            if self._fist_armed_until and now <= self._fist_armed_until:
                self._fist_armed_until = 0.0
                self.notice = ""
                self.sink.hotkey("ctrl", "w")                    # confirmed close
            else:
                self._fist_armed_until = now + float(self.cfg["fist_confirm_window_sec"])
                self.notice = "FIST AGAIN TO CONFIRM CLOSE"
            return
        mapping = {
            "PALM": lambda: self.sink.press("space"),            # play / pause
            "SWIPE_RIGHT": lambda: self.sink.press("right"),     # seek forward (player step)
            "SWIPE_LEFT": lambda: self.sink.press("left"),       # seek back
            "SWIPE_UP": lambda: self.sink.press("volumeup"),
            "SWIPE_DOWN": lambda: self.sink.press("volumedown"),
            "THREE_FINGERS": lambda: self.sink.hotkey("shift", "."),  # speed up
            "FOUR_FINGERS": lambda: self.sink.hotkey("shift", ","),   # speed down
            "THUMBS_UP": lambda: self.sink.press("f"),           # fullscreen
        }
        action = mapping.get(ev.name)
        if action:
            action()
        elif ev.name == "MOVE":
            # Moving the mouse still works in media mode.
            x, y = self._map_to_screen(state.index_tip)
            self.sink.move_to(x, y)


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
# Camera diagnostics (for the "the camera does not work" moments)
# --------------------------------------------------------------------------
def diagnose_cameras(cfg: dict) -> int:
    print("Eidak camera diagnostics")
    print("=" * 40)
    if cv2 is None:
        print("OpenCV is not installed. Run:  pip install -r requirements.txt")
        return 1
    manager = CameraManager(cfg)
    found_any = False
    for index in manager._indices():
        for backend, name in manager._backends():
            cap = None
            try:
                cap = cv2.VideoCapture(index, backend)
                if not cap.isOpened():
                    print(f"camera {index} via {name:<16} : not available")
                    continue
                ok = manager._validate(cap)
                if ok:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    print(f"camera {index} via {name:<16} : WORKING ({w}x{h})")
                    found_any = True
                else:
                    print(f"camera {index} via {name:<16} : opens but no usable frames")
            except Exception as exc:
                print(f"camera {index} via {name:<16} : error {exc}")
            finally:
                if cap is not None:
                    cap.release()
    print("=" * 40)
    if not found_any:
        print("No working camera found. Check that:")
        print("  - no other app (Zoom/Teams/Camera) is using the webcam")
        print("  - Windows Settings > Privacy > Camera allows desktop apps")
        print("  - the USB camera is plugged in firmly")
        return 1
    print("At least one camera works. The app will pick it automatically.")
    return 0


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
    engine = GestureEngine(cfg)
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

            state = HandState()
            if results.multi_hand_landmarks:
                lm = [(p.x, p.y, p.z) for p in results.multi_hand_landmarks[0].landmark]
                state = classify_hand(lm, float(cfg["pinch_ratio"]))
                if cfg.get("show_landmarks", True):
                    drawing.draw_landmarks(
                        frame,
                        results.multi_hand_landmarks[0],
                        mp.solutions.hands.HAND_CONNECTIONS,
                        styles.get_default_hand_landmarks_style(),
                        styles.get_default_hand_connections_style(),
                    )

            now = time.time()
            events = engine.update(state, now)
            try:
                dispatcher.handle(events, state)
            except pyautogui.FailSafeException:
                print("Emergency stop triggered (mouse in screen corner).")
                break

            dt = now - prev_t
            prev_t = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            draw_hud(frame, dispatcher.mode, dispatcher.paused, engine.last_gesture,
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
