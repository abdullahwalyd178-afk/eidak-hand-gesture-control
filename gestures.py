# -*- coding: utf-8 -*-
"""Gesture classification, gesture engine and event dispatch for Eidak.

Split out of hand_gesture_control.py (step 0, mechanical - no behavior change).
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Deque, Dict, List, Optional, Tuple

import os

try:
    import pyautogui

    pyautogui.PAUSE = 0.0
    pyautogui.FAILSAFE = True  # slam the mouse to a screen corner to emergency-stop
except Exception:  # headless machines / missing display - handled at runtime
    pyautogui = None


def active_window_title() -> str:
    """Title of the foreground window (Windows only; '' anywhere else or on
    any failure, so non-Windows machines simply skip the media-safety gate)."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


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
    # raw measurements used by HandStabilizer (hysteresis needs the numbers,
    # not just the booleans)
    pinch_index_ratio: float = 9.0     # thumb-index distance / hand size
    pinch_middle_ratio: float = 9.0
    index_reach: float = 0.0           # tip-to-wrist distance / hand size
    middle_reach: float = 0.0
    settled: bool = True               # False while the hand has just appeared
    stale: bool = False                # True for a replayed dropout-grace frame (no new gestures)
    # Set by the stabilizer on the frame a pinch ends because the finger
    # FOLDED into the palm (not because the fingers separated): the engine
    # must treat that pinch as cancelled, never as a click (advisor review).
    pinch_index_cancelled: bool = False
    pinch_middle_cancelled: bool = False

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

    # Raised AND extended along its own axis: a Y-only test misreads a
    # tilted hand, letting a fist open as THUMBS_UP (advisor review item).
    thumb_up = (
        lm[THUMB_TIP][1] < lm[THUMB_IP][1] - 0.02
        and dist(lm[THUMB_TIP], lm[THUMB_MCP]) > dist(lm[THUMB_IP], lm[THUMB_MCP]) * 1.1
    )
    thumb_extended = dist(lm[THUMB_TIP], lm[PINKY_MCP]) > dist(lm[THUMB_IP], lm[PINKY_MCP]) * 1.15

    # A pinch is thumb tip touching the finger tip while that finger is
    # extended away from the wrist (a folded fist must NOT read as a pinch).
    extended_out = lambda tip: dist(lm[tip], lm[WRIST]) > hand_size * 1.2
    pinch_index = dist(lm[THUMB_TIP], lm[INDEX_TIP]) < hand_size * pinch_ratio and extended_out(INDEX_TIP)
    pinch_middle = dist(lm[THUMB_TIP], lm[MIDDLE_TIP]) < hand_size * pinch_ratio and extended_out(MIDDLE_TIP)
    pinch_index_ratio = dist(lm[THUMB_TIP], lm[INDEX_TIP]) / hand_size
    pinch_middle_ratio = dist(lm[THUMB_TIP], lm[MIDDLE_TIP]) / hand_size
    index_reach = dist(lm[INDEX_TIP], lm[WRIST]) / hand_size
    middle_reach = dist(lm[MIDDLE_TIP], lm[WRIST]) / hand_size

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
        pinch_index_ratio=pinch_index_ratio,
        pinch_middle_ratio=pinch_middle_ratio,
        index_reach=index_reach,
        middle_reach=middle_reach,
    )


# --------------------------------------------------------------------------
# Stabilizer: per-frame guesses -> trustworthy state
# --------------------------------------------------------------------------
class HandStabilizer:
    """Sits between classify_hand() and GestureEngine.

    - majority vote over the last N frames for finger/thumb booleans, so one
      bad frame neither fires nor cancels a gesture;
    - pinch hysteresis (enter below `pinch_ratio`, leave above
      `pinch_release_ratio`) plus a confirmation count, so a one-frame
      glitch is not a click;
    - `settled` stays False for `settle_sec` after the hand appears, so a hand
      sweeping into the frame cannot read as a swipe or a hold;
    - a short dropout (`lost_grace_sec`) keeps the last state instead of
      restarting everything.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        n = max(1, int(self.cfg.get("stab_window_frames", 5)))
        self._hist: Deque[HandState] = deque(maxlen=n)
        self._pinch = {"index": False, "middle": False}
        self._run = {"index": 0, "middle": 0}
        # A pinch may only be ARMED by an open/released frame observed while
        # the hand is settled. A hand that enters the frame already pinching
        # (or keeps holding that pinch) never produces a click; the first
        # deliberate pinch after a settled open frame works normally.
        self._released_seen = {"index": False, "middle": False}
        self._first_seen: Optional[float] = None
        self._last_seen: Optional[float] = None
        self._last_out: Optional[HandState] = None

    @staticmethod
    def _vote(values: List[bool]) -> bool:
        return sum(1 for v in values if v) * 2 > len(values)

    def _update_pinch(self, key: str, ratio: float, reach: float, settled: bool) -> Tuple[bool, bool]:
        """Returns (pinch_active, ended_by_curl_this_frame)."""
        curl_ended = False
        enter = float(self.cfg["pinch_ratio"])
        leave = float(self.cfg.get("pinch_release_ratio", 0.50))
        confirm = max(1, int(self.cfg.get("pinch_confirm_frames", 2)))
        if self._pinch[key]:
            if ratio > leave:
                # the fingers actually separated: a real release, so the NEXT
                # settled pinch may be treated as deliberate
                self._pinch[key] = False
                self._run[key] = 0
                if settled:
                    self._released_seen[key] = True
            elif reach < 1.0:
                # the finger folded into the palm (e.g. closing a fist): the
                # pinch is CANCELLED, not released - no click, no re-arm
                # (advisor review: curl-during-pinch re-arm and spurious click)
                self._pinch[key] = False
                self._run[key] = 0
                curl_ended = True
        elif ratio > leave and settled:
            # openly released while settled: the next pinch is deliberate
            self._released_seen[key] = True
            self._run[key] = 0
        elif ratio < enter and reach > 1.2:
            if settled and self._released_seen[key]:
                self._run[key] += 1
                if self._run[key] >= confirm:
                    self._pinch[key] = True
                    self._released_seen[key] = False
            # not armed: a pinch already held at/after entry is ignored, not queued
        else:
            self._run[key] = 0
        return self._pinch[key], curl_ended

    def update(self, raw: HandState, now: float) -> HandState:
        grace = float(self.cfg.get("lost_grace_sec", 0.15))
        if not raw.found:
            if self._last_out is not None and self._last_seen is not None and now - self._last_seen <= grace:
                # short dropout: keep the last known position/state for continuity,
                # but mark it STALE so the engine never acts on replayed data
                return replace(self._last_out, stale=True)
            self.reset()
            return HandState()

        if self._last_seen is None:
            self._first_seen = now
        self._last_seen = now
        self._hist.append(raw)
        hist = list(self._hist)

        fingers = {name: self._vote([h.fingers_up.get(name, False) for h in hist]) for name in FINGERS}
        settled = (now - (self._first_seen if self._first_seen is not None else now)) >= float(
            self.cfg.get("settle_sec", 0.35)
        )
        out = replace(
            raw,
            fingers_up=fingers,
            thumb_up=self._vote([h.thumb_up for h in hist]),
            thumb_extended=self._vote([h.thumb_extended for h in hist]),
            settled=settled,
        )
        pinch_i, cancel_i = self._update_pinch("index", raw.pinch_index_ratio, raw.index_reach, settled)
        pinch_m, cancel_m = self._update_pinch("middle", raw.pinch_middle_ratio, raw.middle_reach, settled)
        out = replace(
            out,
            pinch_index=pinch_i,
            pinch_middle=pinch_m,
            pinch_index_cancelled=cancel_i,
            pinch_middle_cancelled=cancel_m,
        )
        self._last_out = out
        return out


class GesturePipeline:
    """landmarks -> classify -> stabilize -> gesture events (one call per frame)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.stabilizer = HandStabilizer(cfg)
        self.engine = GestureEngine(cfg)

    @property
    def last_gesture(self) -> str:
        return self.engine.last_gesture

    def process(self, landmarks: Optional[Landmarks], now: Optional[float] = None):
        """Returns (stabilized HandState, [GestureEvent]). Pass None when no hand."""
        now = time.time() if now is None else now
        raw = classify_hand(landmarks, float(self.cfg["pinch_ratio"])) if landmarks else HandState()
        state = self.stabilizer.update(raw, now)
        return state, self.engine.update(state, now)


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
        self._last_click_t = -1e9
        self._last_event_t: Dict[str, float] = {}
        self._hold_start: Dict[str, float] = {}
        self._fired_holds: set = set()
        self.last_gesture = ""

    # -- helpers -----------------------------------------------------------
    def _cooled_down(self, name: str, now: float) -> bool:
        if name == "click":
            # config.json files saved by older versions still carry 0.25 s, which
            # swallows a fast double pinch. Whatever the config says, the
            # debounce must stay well below the double-click window.
            debounce = min(float(self.cfg["click_debounce_sec"]),
                           0.3 * float(self.cfg["double_click_window_sec"]))
            return now - self._last_event_t.get(name, -10.0) >= debounce
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

    def reset(self) -> List["GestureEvent"]:
        """Forget all temporal state. Returns the events that must still be
        delivered: a drag in progress MUST end, or the mouse button stays down."""
        events: List[GestureEvent] = []
        if self._dragging:
            events.append(GestureEvent("DRAG_END"))
        self._centroid_hist.clear()
        self._pinch_index_down = False
        self._pinch_middle_down = False
        self._dragging = False
        self._hold_start.clear()
        self._fired_holds.clear()
        return events

    # -- main --------------------------------------------------------------
    def update(self, state: HandState, now: Optional[float] = None) -> List[GestureEvent]:
        now = time.time() if now is None else now
        events: List[GestureEvent] = []
        if not state.found:
            return self.reset()
        if state.stale:  # dropout-grace replay: continuity only, no new gestures or timers
            return events
        if not state.settled:  # the hand has only just appeared: do nothing yet
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
            if state.pinch_index_cancelled:
                # finger folded into the palm: cancel the gesture silently -
                # end any drag so the button never sticks, but NEVER click
                if self._dragging:
                    self._dragging = False
                    events.append(GestureEvent("DRAG_END"))
            elif self._dragging:
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
        if not mid_now and self._pinch_middle_down and not state.pinch_middle_cancelled and self._cooled_down("click", now):
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

        pause_palm = up >= 4 and state.thumb_extended and not pinch_now
        if self._update_hold("pausepalm", pause_palm, float(self.cfg.get("pause_hold_sec", 1.5)), now):
            events.append(GestureEvent("PAUSE_TOGGLE"))

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

    def _mouse_up(self, button: str = "left") -> None:
        # A button release must ALWAYS get through. If the fail-safe is armed
        # (mouse parked in a corner) pyautogui would raise instead of releasing
        # and leave the button stuck down.
        armed = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False
        try:
            pyautogui.mouseUp(button=button, _pause=False)
        finally:
            pyautogui.FAILSAFE = armed

    def drag_end(self) -> None:
        self._dragging = False
        self._mouse_up("left")

    def release_all(self) -> None:
        """Last-resort cleanup (exit / crash): release every mouse button."""
        self._dragging = False
        for button in ("left", "right"):
            try:
                self._mouse_up(button)
            except Exception:
                pass

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
    def release_all(self): self._rec("release_all")
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
        self._paused = False
        self._smooth: Optional[Tuple[float, float]] = None
        self.active_window = ""      # foreground window title, shown on the HUD
        self._drag_down = False        # we sent mouseDown and still owe a mouseUp
        self._click_pos: Optional[Tuple[float, float]] = None
        self._fist_armed_until = 0.0   # destructive close needs a double-fist
        self.notice = ""               # transient HUD message

    # -- pause ----------------------------------------------------------------
    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        value = bool(value)
        if value and not self._paused:
            self._end_drag()
            self._fist_armed_until = 0.0
            self.notice = ""
        self._paused = value

    # -- safe state transitions ------------------------------------------------
    def _end_drag(self) -> None:
        if self._drag_down:
            self._drag_down = False
            self.sink.drag_end()

    def release_all(self, force: bool = False) -> None:
        """Drop everything held or armed. `force=True` additionally tells the
        sink to release every mouse button (use it on exit / error paths).
        A failing drag_end() must NOT keep the forced cleanup from running."""
        try:
            self._end_drag()
        finally:
            self._smooth = None
            self._click_pos = None
            self._fist_armed_until = 0.0
            self.notice = ""
            if force:
                self.sink.release_all()

    def toggle_mode(self) -> str:
        self.release_all()  # never carry a held button or an armed close across modes
        self.mode = "media" if self.mode == "mouse" else "mouse"
        return self.mode

    @staticmethod
    def _cursor_point(state: HandState) -> Point:
        # Steer with the index KNUCKLE (MCP), not the tip: pinching pulls the
        # tip toward the thumb, so a tip-based cursor drifts exactly while the
        # user is aiming a click (advisor review / click-accuracy item).
        if state.landmarks and len(state.landmarks) > INDEX_TIP:
            return state.landmarks[INDEX_MCP]
        return state.index_tip

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
        if not state.found:
            self._smooth = None  # the next appearance must not glide from a stale spot
        if self._fist_armed_until and time.monotonic() > self._fist_armed_until:
            self._fist_armed_until = 0.0
            self.notice = ""
        for ev in events:
            # Safety events are honoured in EVERY mode and while paused.
            if ev.name == "DRAG_END":
                self._end_drag()
            elif ev.name == "PAUSE_TOGGLE":
                if self.mode == "media":  # in mouse mode a plain palm hold already toggles
                    self.paused = not self._paused
            elif self.mode == "mouse":
                self._handle_mouse(ev, state)
            else:
                self._handle_media(ev, state)

    def _handle_mouse(self, ev: GestureEvent, state: HandState) -> None:
        if ev.name == "PALM":
            self.paused = not self._paused
            return
        if self._paused:
            return
        if ev.name == "MOVE":
            x, y = self._map_to_screen(self._cursor_point(state))
            self.sink.move_to(x, y)
        elif ev.name == "LEFT_CLICK":
            # remember THIS click's position (freshly mapped, not cached smoothing)
            self._click_pos = self._map_to_screen(self._cursor_point(state))
            self.sink.left_click()
        elif ev.name == "RIGHT_CLICK":
            self.sink.right_click()
        elif ev.name == "DOUBLE_CLICK":
            # The first click of the pair was already sent. Send only the SECOND
            # click, at the same spot, so Windows sees exactly one double-click
            # (sending doubleClick() here made it a triple-click).
            if self._click_pos is not None:
                self.sink.move_to(*self._click_pos)
            self.sink.left_click()
            self._click_pos = None
        elif ev.name == "DRAG_START":
            self._drag_down = True
            self.sink.drag_start()
        elif ev.name == "SCROLL":
            self.sink.scroll(-ev.value * float(self.cfg["scroll_gain"]))

    def _media_target_ok(self) -> bool:
        """Media keys go to WHATEVER window has focus - a space lands as a
        typed space in any editor, Ctrl+W closes any tab (advisor review
        item). On Windows, only fire them when a known player window is
        focused; if the foreground window cannot be determined (non-Windows,
        API failure), stay permissive rather than breaking the feature."""
        title = active_window_title()
        self.active_window = title
        if not title:
            return True
        allow = self.cfg.get("media_window_allowlist") or []
        if not allow:
            return True
        low = title.lower()
        return any(str(tok).lower() in low for tok in allow)

    def _handle_media(self, ev: GestureEvent, state: HandState) -> None:
        if self._paused:
            return
        if not self._media_target_ok():
            self.notice = "MEDIA KEYS OFF - focus a player window"
            return
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
            x, y = self._map_to_screen(self._cursor_point(state))
            self.sink.move_to(x, y)


