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
    GesturePipeline,
    Dispatcher,
    NullSink,
    PyAutoSink,
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


# --------------------------------------------------------------------------
# Safety + stability (fix/gesture-safety)
# --------------------------------------------------------------------------
PALM_KW = dict(up=("index", "middle", "ring", "pinky"), thumb_extended=True)


def pinch_at(ratio, shift=(0.0, 0.0)):
    """Index finger up, thumb tip `ratio` x hand-size away from the index tip."""
    lm = list(make_landmarks(up=("index",), shift=shift))
    hand_size = 0.20  # wrist (y .75) to middle MCP (y .55) in make_landmarks
    tx, ty, tz = lm[INDEX_TIP]
    lm[THUMB_TIP] = (tx - ratio * hand_size, ty, tz)
    return lm


def run_pipe(pipe, disp, frames):
    """frames: [(t, landmarks | None)] -> all events seen."""
    seen = []
    for t, lm in frames:
        state, events = pipe.process(lm, t)
        disp.handle(events, state)
        seen += events
    return seen


def real_calls(sink):
    return [c for c in sink.calls if c[0] != "move_to"]


def settle(lm, t0=100.0, n=14, dt=0.033):
    """Frames that let the stabilizer finish its warm-up."""
    return [(t0 + i * dt, lm) for i in range(n)]


def test_drag_is_released_when_hand_is_lost():
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle, pinch = make_landmarks(up=("index",)), pinch_at(0.2)
    run_pipe(pipe, disp, settle(idle, 100.0, n=14))            # hand enters open, settles
    run_pipe(pipe, disp, [(100.5 + i * 0.033, pinch) for i in range(15)])  # then pinches -> drag
    assert ("drag_start", ()) in sink.calls, sink.calls
    run_pipe(pipe, disp, [(101.2 + i * 0.033, None) for i in range(12)])  # hand leaves
    assert ("drag_end", ()) in sink.calls, "mouse button would stay down"
    print("ok drag released on hand loss")


def test_drag_is_released_on_mode_switch_and_pause():
    for how in ("mode", "pause"):
        pipe, sink = GesturePipeline(cfg()), NullSink()
        disp = Dispatcher(sink, cfg())
        run_pipe(pipe, disp, settle(make_landmarks(up=("index",)), 100.0, n=14))
        run_pipe(pipe, disp, [(100.5 + i * 0.033, pinch_at(0.2)) for i in range(15)])
        assert ("drag_start", ()) in sink.calls
        if how == "mode":
            disp.toggle_mode()
        else:
            disp.paused = True
        assert ("drag_end", ()) in sink.calls, how
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    disp.release_all(force=True)
    assert ("release_all", ()) in sink.calls
    print("ok drag released on mode switch / pause / forced cleanup")


def test_drag_end_event_passes_in_media_mode():
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    from hand_gesture_control import GestureEvent, HandState
    disp.handle([GestureEvent("DRAG_START")], HandState(found=True))
    disp.mode = "media"  # simulates a mode change that bypassed toggle_mode()
    disp.handle([GestureEvent("DRAG_END")], HandState(found=True))
    assert ("drag_end", ()) in sink.calls, sink.calls
    print("ok DRAG_END honoured in any mode")


def test_pause_is_honoured_in_media_mode():
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg(start_mode="media"))
    palm = make_landmarks(**PALM_KW)
    disp.paused = True
    run_pipe(pipe, disp, settle(palm, 100.0, n=40))            # 1.3 s palm while paused
    assert not real_calls(sink), real_calls(sink)
    disp.handle([__import__("hand_gesture_control").GestureEvent("SWIPE_RIGHT")],
                __import__("hand_gesture_control").HandState(found=True))
    assert not real_calls(sink), "paused media mode must not press keys"
    print("ok pause blocks media actions")


def test_long_palm_toggles_pause_in_media_mode():
    cfg_ = cfg(start_mode="media")
    pipe, sink = GesturePipeline(cfg_), NullSink()
    disp = Dispatcher(sink, cfg_)
    palm = make_landmarks(**PALM_KW)
    run_pipe(pipe, disp, settle(palm, 100.0, n=60))            # ~2 s hold
    assert disp.paused, "long palm must pause"
    sink.calls.clear()
    run_pipe(pipe, disp, [(102.0 + i * 0.033, None) for i in range(10)])  # hand away
    run_pipe(pipe, disp, settle(palm, 103.0, n=60))            # long palm again
    assert not disp.paused, "second long palm must resume"
    assert ("press", ("space",)) not in sink.calls, "no stray play/pause while paused/resuming"
    print("ok long palm pauses / resumes video mode")


def test_single_frame_pinch_glitch_is_not_a_click():
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle = make_landmarks(up=("index",))
    frames = settle(idle, 100.0, n=14) + [(100.5, pinch_at(0.2))] + \
        [(100.53 + i * 0.033, idle) for i in range(8)]
    run_pipe(pipe, disp, frames)
    assert not real_calls(sink), real_calls(sink)
    print("ok 1-frame pinch glitch ignored")


def test_real_pinch_still_clicks_once():
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle = make_landmarks(up=("index",))
    frames = settle(idle, 100.0, n=14) + [(100.5 + i * 0.033, pinch_at(0.2)) for i in range(5)] + \
        [(100.7 + i * 0.033, idle) for i in range(8)]
    run_pipe(pipe, disp, frames)
    assert real_calls(sink) == [("left_click", ())], real_calls(sink)
    print("ok real pinch = exactly one click")


def test_pinch_hysteresis_wobble_gives_one_click():
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle = make_landmarks(up=("index",))
    wobble = [0.30, 0.30, 0.30, 0.42, 0.30, 0.45, 0.30, 0.30]  # stays inside the 0.35-0.50 band
    frames = settle(idle, 100.0, n=14)
    frames += [(100.5 + i * 0.033, pinch_at(r)) for i, r in enumerate(wobble)]
    frames += [(100.8 + i * 0.033, pinch_at(0.8)) for i in range(8)]
    run_pipe(pipe, disp, frames)
    assert real_calls(sink) == [("left_click", ())], real_calls(sink)
    print("ok pinch wobble inside hysteresis band = one click")


def test_hold_survives_one_bad_frame():
    # The hold starts once the hand has settled (~t=100.36) and needs 0.5 s, so
    # it fires at ~100.86. A bad frame at ~100.79 would restart it without
    # voting, and the sequence ends before a restarted hold could finish.
    cfg_ = cfg(start_mode="media")
    pipe, sink = GesturePipeline(cfg_), NullSink()
    disp = Dispatcher(sink, cfg_)
    palm, other = make_landmarks(**PALM_KW), make_landmarks(up=("index",))
    frames = [(100.0 + i * 0.033, other if i == 24 else palm) for i in range(37)]
    run_pipe(pipe, disp, frames)
    assert ("press", ("space",)) in sink.calls, sink.calls
    print("ok palm hold survives one bad frame")


def test_short_dropout_does_not_restart_everything():
    cfg_ = cfg(start_mode="media")
    pipe, sink = GesturePipeline(cfg_), NullSink()
    disp = Dispatcher(sink, cfg_)
    palm = make_landmarks(**PALM_KW)
    frames = [(100.0 + i * 0.033, None if 24 <= i < 27 else palm) for i in range(37)]  # 0.1 s dropout
    run_pipe(pipe, disp, frames)
    assert ("press", ("space",)) in sink.calls, sink.calls
    print("ok 0.1 s tracking dropout is tolerated")


def test_hand_entering_fast_is_not_a_swipe():
    cfg_ = cfg(start_mode="media")
    pipe, sink = GesturePipeline(cfg_), NullSink()
    disp = Dispatcher(sink, cfg_)
    frames = [(100.0 + i * 0.033, make_landmarks(**PALM_KW, shift=(-0.25 + 0.05 * i, 0.0)))
              for i in range(8)]                              # sweeps in during 0.26 s
    run_pipe(pipe, disp, frames)
    assert not real_calls(sink), real_calls(sink)
    print("ok hand entering the frame is not a swipe")


def test_deliberate_swipe_after_settling_still_works():
    cfg_ = cfg(start_mode="media")
    pipe, sink = GesturePipeline(cfg_), NullSink()
    disp = Dispatcher(sink, cfg_)
    still = make_landmarks(**PALM_KW)
    frames = settle(still, 100.0, n=16)                       # 0.5 s, settled
    frames += [(100.6 + i * 0.05, make_landmarks(**PALM_KW, shift=(0.06 * (i + 1), 0.0)))
               for i in range(6)]
    run_pipe(pipe, disp, frames)
    assert ("press", ("right",)) in sink.calls, sink.calls
    print("ok deliberate swipe still works")


def test_double_pinch_is_one_double_click_not_three_clicks():
    # gap = time between the two pinch RELEASES. 0.20 s is a natural fast double
    # pinch; the old 0.25 s debounce swallowed it, and 0.30-0.38 s produced
    # click + doubleClick = a triple-click.
    idle, pinch = make_landmarks(up=("index",)), pinch_at(0.2)
    for gap in (0.20, 0.30, 0.38):
        r1 = 100.6
        r2 = r1 + gap
        def pinching(t):
            return (r1 - 0.12 <= t < r1) or (r2 - 0.12 <= t < r2)
        frames, t = [], 100.0
        while t < r2 + 0.3:
            frames.append((t, pinch if pinching(t) else idle))
            t += 0.01  # dense timeline so the two releases land where intended
        pipe, sink = GesturePipeline(cfg()), NullSink()
        disp = Dispatcher(sink, cfg())
        run_pipe(pipe, disp, frames)
        got = [c[0] for c in real_calls(sink)]
        assert got.count("left_click") == 2 and "double_click" not in got, (gap, got)
    print("ok double pinch -> exactly two OS clicks, never a triple")


def test_old_saved_config_cannot_bring_back_the_swallowed_double_pinch():
    # config.json written by earlier versions contains click_debounce_sec = 0.25
    idle, pinch = make_landmarks(up=("index",)), pinch_at(0.2)
    c = cfg(click_debounce_sec=0.25)
    r1, r2 = 100.6, 100.8                                     # 0.20 s between releases
    frames, t_ = [], 100.0
    while t_ < r2 + 0.3:
        on = (r1 - 0.12 <= t_ < r1) or (r2 - 0.12 <= t_ < r2)
        frames.append((t_, pinch if on else idle))
        t_ += 0.01
    pipe, sink = GesturePipeline(c), NullSink()
    run_pipe(pipe, Dispatcher(sink, c), frames)
    assert [x[0] for x in real_calls(sink)].count("left_click") == 2, real_calls(sink)
    print("ok persisted 0.25 s debounce no longer swallows a fast double pinch")


def test_smoothing_resets_after_hand_loss():
    from hand_gesture_control import HandState
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    for _ in range(30):
        a = disp._map_to_screen((0.2, 0.3, 0.0))
    disp.handle([], HandState())                              # hand lost
    b = disp._map_to_screen((0.8, 0.7, 0.0))
    target = Dispatcher(NullSink(), cfg())._map_to_screen((0.8, 0.7, 0.0))
    assert abs(b[0] - target[0]) < 1e-6 and abs(b[1] - target[1]) < 1e-6, (a, b, target)
    print("ok cursor does not sweep after the hand reappears")


class _FakePyAutoGUI:
    def __init__(self):
        self.FAILSAFE = True
        self.log = []

    def mouseUp(self, button="left", _pause=False):
        if self.FAILSAFE:                                     # mouse parked in a corner
            raise RuntimeError("FailSafeException")
        self.log.append(("up", button))

    def size(self):
        return (1920, 1080)


def test_mouse_release_survives_armed_failsafe():
    import sys as _sys
    mod = _sys.modules[PyAutoSink.__module__]
    old = mod.pyautogui
    mod.pyautogui = fake = _FakePyAutoGUI()
    try:
        sink = PyAutoSink()
        sink.drag_end()
        sink.release_all()
        assert ("up", "left") in fake.log and ("up", "right") in fake.log, fake.log
        assert fake.FAILSAFE is True, "fail-safe must be re-armed afterwards"
    finally:
        mod.pyautogui = old
    print("ok mouse-up is delivered even with the fail-safe armed")


# --------------------------------------------------------------------------
# Review-driven failure-path tests (fix/gesture-safety, independent review)
# --------------------------------------------------------------------------
def test_release_all_force_survives_drag_end_failure():
    """If drag_end() raises, forced cleanup must still reach sink.release_all()."""
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    disp.handle([__import__("hand_gesture_control").GestureEvent("DRAG_START")],
                __import__("hand_gesture_control").HandState(found=True))
    def boom():
        raise RuntimeError("mouse stuck")
    sink.drag_end = boom
    try:
        disp.release_all(force=True)
    except RuntimeError:
        pass
    assert ("release_all", ()) in sink.calls, sink.calls
    print("ok forced cleanup survives a failing drag_end")


def test_failsafe_exception_during_drag_releases_state():
    """The run()-level contract: on FailSafeException the dispatcher is force-cleaned,
    so no drag state or held button survives the emergency stop."""
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    disp.handle([__import__("hand_gesture_control").GestureEvent("DRAG_START")],
                __import__("hand_gesture_control").HandState(found=True))
    assert ("drag_start", ()) in sink.calls
    disp.release_all(force=True)  # what the except-block now does
    assert ("drag_end", ()) in sink.calls and ("release_all", ()) in sink.calls
    assert not disp._drag_down
    print("ok emergency stop leaves no drag state")


def test_held_palm_does_not_retrigger_pause_toggle():
    """Keeping the palm open after one PAUSE_TOGGLE must not toggle repeatedly."""
    cfg_ = cfg(start_mode="media")
    pipe, sink = GesturePipeline(cfg_), NullSink()
    disp = Dispatcher(sink, cfg_)
    palm = make_landmarks(**PALM_KW)
    run_pipe(pipe, disp, settle(palm, 100.0, n=60))          # ~2 s: first toggle
    assert disp.paused
    run_pipe(pipe, disp, settle(palm, 102.0, n=60))          # still the same held palm
    assert disp.paused, "a held palm must not toggle pause back and forth"
    print("ok held palm fires PAUSE_TOGGLE only once")


def test_hand_loss_during_pinch_makes_no_click():
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    frames = settle(pinch_at(0.2), 100.0, n=5)               # pinch starts
    frames += [(100.2 + i * 0.033, None) for i in range(12)]  # hand vanishes mid-pinch
    run_pipe(pipe, disp, frames)
    assert not real_calls(sink), real_calls(sink)
    print("ok hand loss mid-pinch = no phantom click")


def test_dropout_expiry_does_not_restore_old_state():
    """After lost_grace_sec expires, a returning hand restarts stabilization;
    a stale pinch from before the loss must not complete as a click."""
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    run_pipe(pipe, disp, settle(pinch_at(0.2), 100.0, n=5))   # pinch in progress
    run_pipe(pipe, disp, [(100.2 + i * 0.05, None) for i in range(10)])  # 0.5 s loss > grace
    idle = make_landmarks(up=("index",))
    run_pipe(pipe, disp, settle(idle, 101.0, n=20))           # hand back, fingers open
    assert not real_calls(sink), real_calls(sink)
    print("ok expired dropout starts a fresh cycle")


def test_mouse_up_failure_restores_failsafe_flag():
    import sys as _sys
    mod = _sys.modules[PyAutoSink.__module__]
    class _FailUp(_FakePyAutoGUI):
        def mouseUp(self, button="left", _pause=False):
            raise RuntimeError("os-level failure")
    old = mod.pyautogui
    mod.pyautogui = fake = _FailUp()
    try:
        sink = PyAutoSink()
        try:
            sink.drag_end()
        except RuntimeError:
            pass
        assert fake.FAILSAFE is True, "fail-safe flag must be restored even when mouseUp raises"
    finally:
        mod.pyautogui = old
    print("ok FAILSAFE restored after a failing mouseUp")


def test_hand_entering_already_pinched_never_clicks():
    """A hand that appears mid-pinch and KEEPS holding it must produce no click,
    even long after the settle window (arming rule, not just delayed confirmation)."""
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    run_pipe(pipe, disp, settle(pinch_at(0.2), 100.0, n=40))   # 1.3 s held pinch from entry
    assert not real_calls(sink), real_calls(sink)
    print("ok pinched entry held = never a click")


def test_release_then_new_pinch_after_pinched_entry_clicks_once():
    """After a pinched entry, a real release while settled re-arms; the next
    deliberate pinch clicks exactly once."""
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle = make_landmarks(up=("index",))
    run_pipe(pipe, disp, settle(pinch_at(0.2), 100.0, n=20))   # pinched entry, held
    assert not real_calls(sink)
    run_pipe(pipe, disp, [(100.8 + i * 0.033, idle) for i in range(8)])     # release
    run_pipe(pipe, disp, [(101.1 + i * 0.033, pinch_at(0.2)) for i in range(5)])  # new pinch
    run_pipe(pipe, disp, [(101.3 + i * 0.033, idle) for i in range(8)])     # release
    assert real_calls(sink) == [("left_click", ())], real_calls(sink)
    print("ok release re-arms, deliberate pinch clicks once")


def test_grace_replay_fires_no_new_gestures():
    """During dropout grace the engine sees stale frames: a hold that would
    complete during the replay must NOT fire from replayed data."""
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle, pinch = make_landmarks(up=("index",)), pinch_at(0.2)
    run_pipe(pipe, disp, settle(idle, 100.0, n=14))
    run_pipe(pipe, disp, [(100.5 + i * 0.033, pinch) for i in range(7)])    # 0.23 s pinch
    # hand vanishes for 0.1 s (inside grace); drag_hold 0.30 s would complete mid-dropout
    run_pipe(pipe, disp, [(100.75 + i * 0.033, None) for i in range(3)])
    assert ("drag_start", ()) not in sink.calls, sink.calls   # nothing fired from replay
    run_pipe(pipe, disp, [(100.9 + i * 0.033, None) for i in range(10)])    # past grace: reset
    assert not real_calls(sink), real_calls(sink)             # pinch aborted, no click
    print("ok dropout replay is inert")


def test_second_click_position_comes_from_click_frame():
    """DOUBLE_CLICK's second click must go to the first click's own position,
    even if no MOVE ever updated the smoothing cache."""
    from hand_gesture_control import GestureEvent, HandState
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    st = HandState(found=True, index_tip=(0.3, 0.4, 0.0))
    disp.handle([GestureEvent("LEFT_CLICK")], st)
    disp.handle([GestureEvent("DOUBLE_CLICK")], st)
    calls = [c for c in sink.calls if c[0] != "move_to"]
    assert [c[0] for c in calls] == ["left_click", "left_click"], sink.calls
    moves = [c for c in sink.calls if c[0] == "move_to"]
    assert len(moves) == 1, sink.calls                        # repositioned exactly once
    expected = disp._map_to_screen((0.3, 0.4, 0.0))
    assert abs(moves[0][1][0] - expected[0]) < 1e-6, (moves, expected)
    print("ok second click uses the click frame's own position")


def test_media_keys_fail_closed_when_windows_title_is_unknown():
    import gestures as g
    from hand_gesture_control import GestureEvent, HandState

    sink = NullSink()
    disp = Dispatcher(sink, cfg(media_window_allowlist=["youtube", "vlc"]))
    disp.mode = "media"
    original_name = g.os.name
    original_title = g.active_window_title
    try:
        g.os.name = "nt"
        g.active_window_title = lambda: ""
        disp.handle([GestureEvent("PALM")], HandState(found=True))
        assert not real_calls(sink), real_calls(sink)
        assert "cannot identify" in disp.notice
    finally:
        g.os.name = original_name
        g.active_window_title = original_title
    print("ok media keys fail closed when Windows foreground window is unknown")

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
    test_drag_is_released_when_hand_is_lost()
    test_drag_is_released_on_mode_switch_and_pause()
    test_drag_end_event_passes_in_media_mode()
    test_pause_is_honoured_in_media_mode()
    test_long_palm_toggles_pause_in_media_mode()
    test_single_frame_pinch_glitch_is_not_a_click()
    test_real_pinch_still_clicks_once()
    test_pinch_hysteresis_wobble_gives_one_click()
    test_hold_survives_one_bad_frame()
    test_short_dropout_does_not_restart_everything()
    test_hand_entering_fast_is_not_a_swipe()
    test_deliberate_swipe_after_settling_still_works()
    test_double_pinch_is_one_double_click_not_three_clicks()
    test_old_saved_config_cannot_bring_back_the_swallowed_double_pinch()
    test_smoothing_resets_after_hand_loss()
    test_mouse_release_survives_armed_failsafe()
    test_release_all_force_survives_drag_end_failure()
    test_failsafe_exception_during_drag_releases_state()
    test_held_palm_does_not_retrigger_pause_toggle()
    test_hand_loss_during_pinch_makes_no_click()
    test_dropout_expiry_does_not_restore_old_state()
    test_mouse_up_failure_restores_failsafe_flag()
    test_hand_entering_already_pinched_never_clicks()
    test_release_then_new_pinch_after_pinched_entry_clicks_once()
    test_grace_replay_fires_no_new_gestures()
    test_second_click_position_comes_from_click_frame()
    test_media_keys_fail_closed_when_windows_title_is_unknown()
    print("ALL TESTS PASSED")


def test_curl_during_pinch_does_not_rearm():
    """Folding the pinched finger into the palm ends the pinch but is NOT an
    open release: it must not re-arm the click. Only a real open hand does."""
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle = make_landmarks(up=("index",))
    curl = make_landmarks()                      # fist: index folded (reach < 1)
    curl[THUMB_TIP] = curl[INDEX_TIP]            # ...but thumb/index tips touch
    pinch = pinch_at(0.2)
    run_pipe(pipe, disp, settle(idle, 100.0, n=14))                 # open, settled, armed
    run_pipe(pipe, disp, [(100.5 + i * 0.033, pinch) for i in range(5)])   # pinch held
    run_pipe(pipe, disp, [(100.8 + i * 0.033, curl) for i in range(4)])    # finger folds in palm
    run_pipe(pipe, disp, [(101.0 + i * 0.033, pinch) for i in range(6)])   # "pinch" again
    assert not real_calls(sink), real_calls(sink)                    # no click from a curl arm
    run_pipe(pipe, disp, [(101.4 + i * 0.033, idle) for i in range(8)])    # real open release
    run_pipe(pipe, disp, [(101.8 + i * 0.033, pinch) for i in range(5)])   # deliberate pinch
    run_pipe(pipe, disp, [(102.1 + i * 0.033, idle) for i in range(5)])    # release
    assert real_calls(sink) == [("left_click", ())], real_calls(sink)
    print("ok curl during pinch does not re-arm")


def test_cursor_steers_by_knuckle_not_tip():
    """The cursor (and the remembered click spot) follow the index knuckle,
    which stays put during a pinch; the tip drifts toward the thumb."""
    from hand_gesture_control import GestureEvent, HandState
    sink = NullSink()
    disp = Dispatcher(sink, cfg())
    lm = [(0.5, 0.5, 0.0)] * 21
    lm[INDEX_MCP] = (0.30, 0.40, 0.0)
    lm[INDEX_TIP] = (0.90, 0.90, 0.0)   # pulled far away, as mid-pinch
    st = HandState(found=True, landmarks=lm, index_tip=(0.90, 0.90, 0.0))
    disp.handle([GestureEvent("LEFT_CLICK")], st)
    expected = Dispatcher(NullSink(), cfg())._map_to_screen((0.30, 0.40, 0.0))
    assert disp._click_pos == expected, (disp._click_pos, expected)
    assert expected != Dispatcher(NullSink(), cfg())._map_to_screen((0.90, 0.90, 0.0))
    print("ok cursor steers by knuckle")


def test_thumb_up_needs_axis_extension_not_only_height():
    """A tilted fist can put the thumb tip above its IP in Y; that alone must
    NOT classify as thumbs-up (the thumb has to be extended along its axis)."""
    lm = make_landmarks()                       # fist
    lm[THUMB_IP] = (0.40, 0.62, 0.0)
    lm[THUMB_TIP] = (0.40, 0.59, 0.0)           # above IP, but folded toward MCP
    st = classify_hand(lm)
    assert st.thumb_up is False
    st2 = classify_hand(make_landmarks(thumb_up=True))
    assert st2.thumb_up is True
    print("ok thumbs-up needs axis extension")


def test_pause_palm_hold_toggles_video_pause():
    """A long open-palm hold issues exactly one PAUSE_TOGGLE (video mode)."""
    eng = GestureEngine(cfg())
    palm = make_landmarks(**PALM_KW)
    ev = feed(eng, palm, 100.0, frames=34, dt=0.05)   # 1.7 s > pause_hold_sec
    toggles = [e for e in ev if e.name == "PAUSE_TOGGLE"]
    assert len(toggles) == 1, names(ev)
    print("ok pause palm hold toggles once")


def test_curl_during_drag_ends_drag_without_click():
    """Folding the finger mid-drag must release the button (DRAG_END) but
    never fire a click afterwards."""
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle = make_landmarks(up=("index",))
    curl = make_landmarks()
    curl[THUMB_TIP] = curl[INDEX_TIP]
    pinch = pinch_at(0.2)
    run_pipe(pipe, disp, settle(idle, 100.0, n=14))
    run_pipe(pipe, disp, [(100.5 + i * 0.033, pinch) for i in range(15)])  # 0.5s hold -> drag
    assert ("drag_start", ()) in sink.calls, sink.calls
    run_pipe(pipe, disp, [(101.2 + i * 0.033, curl) for i in range(4)])    # fold mid-drag
    assert ("drag_end", ()) in sink.calls, sink.calls                      # button released
    assert ("left_click", ()) not in sink.calls, sink.calls                # no click
    print("ok curl mid-drag releases button, no click")


def test_media_keys_blocked_without_player_window():
    """Media commands must not fire into a random focused window (review item:
    space typed into an editor, Ctrl+W closing any tab)."""
    import gestures as g
    from hand_gesture_control import GestureEvent, HandState
    sink = NullSink()
    c = cfg(media_window_allowlist=["youtube", "vlc"])
    disp = Dispatcher(sink, c)
    disp.mode = "media"
    orig = g.active_window_title
    try:
        g.active_window_title = lambda: "Untitled - Notepad"
        st = HandState(found=True)
        disp.handle([GestureEvent("PALM")], st)
        assert not real_calls(sink), real_calls(sink)          # space blocked
        disp.handle([GestureEvent("FIST")], st)
        disp.handle([GestureEvent("FIST")], st)                # confirmed close attempt
        assert not real_calls(sink), real_calls(sink)          # ctrl+w blocked
        g.active_window_title = lambda: "My video - YouTube - Google Chrome"
        disp.handle([GestureEvent("PALM")], st)
        assert real_calls(sink) == [("press", ("space",))], real_calls(sink)
        g.active_window_title = lambda: ""                     # unknown window
        before = len(real_calls(sink))
        disp.handle([GestureEvent("PALM")], st)
        if g.os.name == "nt":
            assert len(real_calls(sink)) == before              # fail closed on Windows
        else:
            assert real_calls(sink)[-1] == ("press", ("space",)) # legacy non-Windows behavior
    finally:
        g.active_window_title = orig
    print("ok media keys gated on focused player window")




def test_curl_and_separation_cancel_without_rearming():
    from gestures import HandStabilizer
    for key in ("index", "middle"):
        stab = HandStabilizer(cfg(pinch_confirm_frames=1))
        assert stab._update_pinch(key, 0.8, 1.8, True) == (False, False)
        assert stab._update_pinch(key, 0.2, 1.8, True) == (True, False)
        assert stab._update_pinch(key, 0.8, 0.7, True) == (False, True)
        for _ in range(4):
            assert stab._update_pinch(key, 0.8, 0.7, True) == (False, False)
        assert stab._update_pinch(key, 0.2, 1.8, True) == (False, False)
        assert stab._update_pinch(key, 0.8, 1.8, True) == (False, False)
        assert stab._update_pinch(key, 0.2, 1.8, True) == (True, False)


def test_simultaneous_curl_and_separation_emits_no_click():
    pipe, sink = GesturePipeline(cfg()), NullSink()
    disp = Dispatcher(sink, cfg())
    idle = make_landmarks(up=("index",))
    curl = make_landmarks()
    curl[THUMB_TIP] = (0.15, 0.55, 0.0)
    pinch = pinch_at(0.2)
    run_pipe(pipe, disp, settle(idle, 100.0, n=14))
    run_pipe(pipe, disp, [(100.5 + i * 0.033, pinch) for i in range(5)])
    run_pipe(pipe, disp, [(100.8 + i * 0.033, curl) for i in range(5)])
    run_pipe(pipe, disp, [(101.1 + i * 0.033, pinch) for i in range(5)])
    assert not real_calls(sink), real_calls(sink)
