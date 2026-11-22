#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless tests for Eidak's gesture logic.

Builds synthetic MediaPipe-style landmark lists, so no camera,
no display and no real pyautogui are needed.

Run:  python test_gestures.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hand_gesture_control import (
    GestureEngine,
    Dispatcher,
    NullSink,
    classify_hand,
    DEFAULT_CONFIG,
)

WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20


def make_landmarks(up=(), thumb_extended=False, thumb_up=False,
                   pinch_index=False, pinch_middle=False, shift=(0.0, 0.0)):
    """Build a 21-point synthetic right hand. `up` lists extended fingers."""
    sx, sy = shift
    lm = [(0.5 + sx, 0.75 + sy, 0.0)] * 21  # wrist everywhere by default
    xs = {"index": 0.45, "middle": 0.52, "ring": 0.58, "pinky": 0.64}
    bases = {"index": INDEX_MCP, "middle": MIDDLE_MCP, "ring": RING_MCP, "pinky": PINKY_MCP}
    for name, mcp in bases.items():
        x = xs[name] + sx
        lm[mcp] = (x, 0.55 + sy, 0.0)
        lm[mcp + 1] = (x, 0.45 + sy, 0.0)  # PIP
        lm[mcp + 2] = (x, 0.38 + sy, 0.0)  # DIP
        if name in up:
            lm[mcp + 3] = (x, 0.28 + sy, 0.0)  # TIP extended
        else:
            lm[mcp + 3] = (x, 0.60 + sy, 0.0)  # TIP folded below PIP
    lm[THUMB_CMC] = (0.42 + sx, 0.62 + sy, 0.0)
    lm[THUMB_MCP] = (0.38 + sx, 0.56 + sy, 0.0)
    lm[THUMB_IP] = (0.36 + sx, 0.52 + sy, 0.0)
    if thumb_up:
        lm[THUMB_IP] = (0.36 + sx, 0.50 + sy, 0.0)
        lm[THUMB_TIP] = (0.36 + sx, 0.36 + sy, 0.0)
    elif thumb_extended:
        lm[THUMB_TIP] = (0.30 + sx, 0.44 + sy, 0.0)
    else:
        lm[THUMB_TIP] = (0.44 + sx, 0.57 + sy, 0.0)
    if pinch_index:
        lm[THUMB_TIP] = lm[INDEX_TIP] = (0.43 + sx, 0.33 + sy, 0.0)
    if pinch_middle:
        lm[THUMB_TIP] = lm[MIDDLE_TIP] = (0.50 + sx, 0.33 + sy, 0.0)
    return lm


def cfg(**over):
    c = dict(DEFAULT_CONFIG)
    c.update(over)
    return c


def names(events):
    return [e.name for e in events]


def feed(engine, lm, t0, frames=1, dt=0.033, shift_per_frame=(0.0, 0.0)):
    """Feed the same hand for several frames; returns all events."""
    out = []
    for i in range(frames):
        moved = [(x + shift_per_frame[0] * i, y + shift_per_frame[1] * i, z)
                 for (x, y, z) in lm]
        out += engine.update(classify_hand(moved), t0 + i * dt)
    return out


def test_classify():
    st = classify_hand(make_landmarks(up=("index", "middle", "ring", "pinky"),
                                      thumb_extended=True))
    assert st.found and st.count_up() == 4 and st.thumb_extended
    st = classify_hand(make_landmarks())
    assert st.found and st.count_up() == 0 and not st.thumb_extended
    st = classify_hand(make_landmarks(up=("index",)))
    assert st.fingers_up["index"] and not st.fingers_up["middle"]
    print("ok classify")


def test_move():
    eng = GestureEngine(cfg())
    ev = feed(eng, make_landmarks(up=("index",)), 100.0, frames=3)
    assert "MOVE" in names(ev) and "LEFT_CLICK" not in names(ev)
    print("ok move")


def test_click_and_double():
    eng = GestureEngine(cfg())
    idle = make_landmarks(up=("index",))
    pinch = make_landmarks(pinch_index=True)
    feed(eng, idle, 100.0, frames=2)
    feed(eng, pinch, 100.2, frames=1)          # press
    ev = feed(eng, idle, 100.3, frames=1)      # quick release -> click
    assert "LEFT_CLICK" in names(ev), names(ev)
    feed(eng, pinch, 100.5, frames=1)          # second press inside window
    ev = feed(eng, idle, 100.6, frames=1)
    assert "DOUBLE_CLICK" in names(ev), names(ev)
    print("ok click/double-click")


def test_right_click():
    eng = GestureEngine(cfg())
    idle = make_landmarks()
    feed(eng, idle, 100.0, frames=2)
    feed(eng, make_landmarks(pinch_middle=True), 100.2, frames=1)
    ev = feed(eng, idle, 100.3, frames=1)
    assert "RIGHT_CLICK" in names(ev), names(ev)
    print("ok right click")


def test_drag():
    eng = GestureEngine(cfg())
    idle = make_landmarks(up=("index",))
    pinch = make_landmarks(pinch_index=True)
    feed(eng, pinch, 100.0, frames=1)
    ev = feed(eng, pinch, 100.1, frames=10)    # held 0.3s+ -> drag starts
    assert "DRAG_START" in names(ev), names(ev)
    ev = feed(eng, idle, 101.0, frames=1)
    assert "DRAG_END" in names(ev), names(ev)
    print("ok drag")


def test_scroll():
    eng = GestureEngine(cfg())
    hand = make_landmarks(up=("index", "middle"))
    ev = feed(eng, hand, 100.0, frames=4, shift_per_frame=(0.0, 0.01))
    scrolls = [e for e in ev if e.name == "SCROLL"]
    assert scrolls and all(e.value > 0 for e in scrolls), names(ev)
    print("ok scroll")


def test_swipe():
    eng = GestureEngine(cfg())
    palm = make_landmarks(up=("index", "middle", "ring", "pinky"), thumb_extended=True)
    ev = feed(eng, palm, 100.0, frames=6, dt=0.05, shift_per_frame=(0.06, 0.0))
    assert "SWIPE_RIGHT" in names(ev), names(ev)
    print("ok swipe")


def test_holds():
    eng = GestureEngine(cfg())
    palm = make_landmarks(up=("index", "middle", "ring", "pinky"), thumb_extended=True)
    ev = feed(eng, palm, 100.0, frames=20, dt=0.05)  # 1.0s hold
    assert "PALM" in names(ev), names(ev)

    eng = GestureEngine(cfg())
    ev = feed(eng, make_landmarks(), 100.0, frames=25, dt=0.05)  # fist 1.25s
    assert "FIST" in names(ev), names(ev)

    eng = GestureEngine(cfg())
    three = make_landmarks(up=("index", "middle", "ring"))
    ev = feed(eng, three, 100.0, frames=15, dt=0.05)
    assert "THREE_FINGERS" in names(ev), names(ev)

    eng = GestureEngine(cfg())
    ev = feed(eng, make_landmarks(thumb_up=True), 100.0, frames=15, dt=0.05)
    assert "THUMBS_UP" in names(ev), names(ev)
    print("ok holds (palm/fist/three/thumbs-up)")


def test_dispatcher_mouse():
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    eng = GestureEngine(cfg())
    idle = make_landmarks(up=("index",))
    pinch = make_landmarks(pinch_index=True)
    disp.handle(feed(eng, idle, 100.0, frames=2), classify_hand(idle))
    disp.handle(feed(eng, pinch, 100.2, frames=1), classify_hand(pinch))
    disp.handle(feed(eng, idle, 100.3, frames=1), classify_hand(idle))
    got = [c[0] for c in sink.calls]
    assert "move_to" in got and "left_click" in got, got
    print("ok dispatcher mouse")


def test_dispatcher_media_and_pause():
    sink = NullSink()
    disp = Dispatcher(sink, cfg(start_mode="media"))
    assert disp.mode == "media"
    # palm -> play/pause (space)
    eng = GestureEngine(cfg())
    palm = make_landmarks(up=("index", "middle", "ring", "pinky"), thumb_extended=True)
    for ev_frame in [feed(eng, palm, 100.0, frames=20, dt=0.05)]:
        disp.handle(ev_frame, classify_hand(palm))
    got = [c[0] for c in sink.calls]
    assert ("press", ("space",)) in sink.calls, got
    # fist is destructive: one fist only arms, the second fist confirms.
    # Both fists go through ONE engine with a real release between them:
    # a confirming fist must be a NEW fist, not the same one still held.
    eng = GestureEngine(cfg())
    sink.calls.clear()
    disp.handle(feed(eng, make_landmarks(), 100.0, frames=25, dt=0.05),  # fist 1.25s
                classify_hand(make_landmarks()))
    assert ("hotkey", ("ctrl", "w")) not in sink.calls, sink.calls
    assert disp.notice, "arming must surface a HUD notice"
    relaxed = make_landmarks(up=("index",))
    disp.handle(feed(eng, relaxed, 102.0, frames=10, dt=0.05),  # hand opens: release
                classify_hand(relaxed))
    disp.handle(feed(eng, make_landmarks(), 103.0, frames=25, dt=0.05),  # confirm fist
                classify_hand(make_landmarks()))
    assert ("hotkey", ("ctrl", "w")) in sink.calls, sink.calls
    # three fingers -> speed up (shift+.)
    eng = GestureEngine(cfg())
    sink.calls.clear()
    three = make_landmarks(up=("index", "middle", "ring"))
    disp.handle(feed(eng, three, 100.0, frames=15, dt=0.05), classify_hand(three))
    assert ("hotkey", ("shift", ".")) in sink.calls, sink.calls

    # mouse-mode pause: palm toggles paused, MOVE must not reach the sink
    sink = NullSink()
    disp = Dispatcher(sink, cfg(start_mode="mouse"))
    eng = GestureEngine(cfg())
    palm = make_landmarks(up=("index", "middle", "ring", "pinky"), thumb_extended=True)
    disp.handle(feed(eng, palm, 100.0, frames=20, dt=0.05), classify_hand(palm))
    assert disp.paused
    sink.calls.clear()
    eng2 = GestureEngine(cfg())
    idx = make_landmarks(up=("index",))
    disp.handle(feed(eng2, idx, 101.0, frames=3), classify_hand(idx))
    assert not sink.calls, sink.calls
    print("ok dispatcher media + pause")


def test_mapping_bounds():
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    for tip in [(0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.5, 0.5, 0.0)]:
        x, y = disp._map_to_screen(tip)
        assert 0 <= x < sink.screen_w and 0 <= y < sink.screen_h
    print("ok screen mapping bounds")


def test_never_hits_failsafe_corners():
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    corners = {(0, 0), (sink.screen_w - 1, 0), (0, sink.screen_h - 1),
               (sink.screen_w - 1, sink.screen_h - 1)}
    for tip in [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0.2, 0.2, 0), (0.8, 0.2, 0)]:
        disp._smooth = None
        x, y = disp._map_to_screen(tip)
        assert (int(x), int(y)) not in corners, (tip, x, y)
        assert x >= 1 and y >= 1 and x <= sink.screen_w - 2 and y <= sink.screen_h - 2
    print("ok cursor never lands on fail-safe corners")


def test_single_fist_never_closes():
    sink = NullSink()
    disp = Dispatcher(sink, cfg(start_mode="media"))
    eng = GestureEngine(cfg())
    disp.handle(feed(eng, make_landmarks(), 200.0, frames=25, dt=0.05),
                classify_hand(make_landmarks()))
    assert not [c for c in sink.calls if c[0] == "hotkey"], sink.calls
    print("ok single fist does not close anything")


def test_continuous_fist_never_confirms():
    # One long uninterrupted fist can never close: the engine edge-triggers
    # holds, so without a release there is no second FIST event to confirm,
    # no matter how long the hand stays closed (here 8s > hold + window).
    sink = NullSink()
    disp = Dispatcher(sink, cfg(start_mode="media"))
    eng = GestureEngine(cfg())
    disp.handle(feed(eng, make_landmarks(), 300.0, frames=160, dt=0.05),
                classify_hand(make_landmarks()))
    assert not [c for c in sink.calls if c[0] == "hotkey"], sink.calls
    print("ok one long fist never closes (release required)")


def test_no_scroll_during_right_click_pose():
    eng = GestureEngine(cfg())
    for i in range(8):
        lm = make_landmarks(up=("index", "middle"), pinch_middle=True, shift=(0.0, 0.004 * i))
        names = [e.name for e in eng.update(classify_hand(lm), 100.0 + i * 0.03)]
        assert "SCROLL" not in names, names
    print("ok no scroll while pinching middle finger")


if __name__ == "__main__":
    test_classify()
    test_move()
    test_click_and_double()
    test_right_click()
    test_drag()
    test_scroll()
    test_swipe()
    test_holds()
    test_dispatcher_mouse()
    test_dispatcher_media_and_pause()
    test_mapping_bounds()
    test_never_hits_failsafe_corners()
    test_single_fist_never_closes()
    test_continuous_fist_never_confirms()
    test_no_scroll_during_right_click_pose()
    print("ALL TESTS PASSED")
