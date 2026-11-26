#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless tests for Eidak's camera module and install-time helpers.

No real camera is needed: classification, grayscale detection, backend
ordering and config diff-saving are all pure logic.

Run:  python test_camera.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import camera as cam
import hand_gesture_control as hgc


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"  ok  {name}")


def test_classify_attempt():
    check("no device", cam.classify_attempt(False, False, 0.0) == cam.NO_DEVICE)
    check("opened no frames", cam.classify_attempt(True, False, 0.0) == cam.OPENED_NO_FRAMES)
    check("black frames", cam.classify_attempt(True, True, 2.0) == cam.BLACK_FRAMES)
    check("ok", cam.classify_attempt(True, True, 50.0) == cam.OK)
    check("threshold boundary", cam.classify_attempt(True, True, 5.0) == cam.OK)


def test_looks_grayscale():
    gray = np.full((64, 64, 3), 128, np.uint8)
    color = gray.copy()
    color[:, :, 2] = 220  # strong red channel
    check("gray frame is grayscale", cam.looks_grayscale(gray) is True)
    check("color frame is not", cam.looks_grayscale(color) is False)
    check("none frame is grayscale", cam.looks_grayscale(None) is True)
    check("2d frame is grayscale", cam.looks_grayscale(np.zeros((8, 8), np.uint8)) is True)


def test_backends_no_cap_any_on_windows():
    if cam.cv2 is None:
        print("  skip backends test (no cv2)")
        return
    m = cam.CameraManager(dict(hgc.DEFAULT_CONFIG))
    backends = m._backends()
    system = __import__("platform").system()
    if system == "Windows":
        check("no CAP_ANY on Windows",
              all(b != cam.cv2.CAP_ANY for b, _ in backends))
        check("DSHOW first on Windows",
              backends[0][0] == cam.cv2.CAP_DSHOW)
    else:
        check("backends listed", len(backends) >= 1)


def test_probe_plan_last_camera_first():
    backends = cam.CameraManager(dict(hgc.DEFAULT_CONFIG))._backends()
    if not backends:
        print("  skip probe-plan last-camera test (no cv2 / no camera backends)")
        return
    cfg = dict(hgc.DEFAULT_CONFIG)
    cfg["last_camera"] = {"index": 2, "backend": backends[0][0]}
    m = cam.CameraManager(cfg)
    plan = m._probe_plan()
    check("last working camera probed first",
          plan[0][0] == 2 and plan[0][1] == cfg["last_camera"]["backend"])
    check("no duplicate of the last-working pair",
          not any(p[0] == plan[0][0] and p[1] == plan[0][1] for p in plan[1:]))


def test_probe_plan_strict():
    if not cam.CameraManager(dict(hgc.DEFAULT_CONFIG))._backends():
        print("  skip probe-plan strict test (no cv2 / no camera backends)")
        return
    cfg = dict(hgc.DEFAULT_CONFIG)
    cfg["camera_index"] = 1
    cfg["camera_strict"] = True
    m = cam.CameraManager(cfg)
    plan = m._probe_plan()
    check("strict mode only tries the chosen index",
          all(p[0] == 1 for p in plan))


def test_save_config_diff_only(tmp_path=None):
    original_config_path = hgc.CONFIG_PATH
    import tempfile

    # Keep every test write inside its own temporary directory. Never touch or
    # delete the user's real config.json, even when this suite runs locally.
    with tempfile.TemporaryDirectory(prefix="eidak-config-test-") as tmpdir:
        try:
            hgc.CONFIG_PATH = os.path.join(tmpdir, "config.json")
            cfg = dict(hgc.DEFAULT_CONFIG)
            cfg["sensitivity"] = 2.0
            cfg["last_camera"] = {"index": 1, "backend": 700}
            hgc.save_config(cfg)
            with open(hgc.CONFIG_PATH, "r", encoding="utf-8") as fh:
                saved = json.load(fh)
            check("changed keys saved",
                  saved.get("sensitivity") == 2.0 and saved.get("last_camera", {}).get("index") == 1)
            check("default keys not saved", "frame_width" not in saved and "pinch_ratio" not in saved)
            cfg2 = hgc.load_config()
            check("round-trip sensitivity", cfg2["sensitivity"] == 2.0)
            check("round-trip defaults intact", cfg2["frame_width"] == hgc.DEFAULT_CONFIG["frame_width"])
            hgc.save_config(dict(hgc.DEFAULT_CONFIG))
            with open(hgc.CONFIG_PATH, "r", encoding="utf-8") as fh:
                check("all-default saves empty diff", json.load(fh) == {})
        finally:
            hgc.CONFIG_PATH = original_config_path



def test_config_test_preserves_existing_config():
    import tempfile

    original_config_path = hgc.CONFIG_PATH
    with tempfile.TemporaryDirectory(prefix="eidak-preserve-test-") as tmpdir:
        sentinel = os.path.join(tmpdir, "real-config.json")
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write('{"user_setting": "keep-me"}')
        hgc.CONFIG_PATH = sentinel
        try:
            test_save_config_diff_only()
        finally:
            hgc.CONFIG_PATH = original_config_path
        with open(sentinel, "r", encoding="utf-8") as fh:
            check("existing config survives config test", json.load(fh) == {"user_setting": "keep-me"})


def test_freeze_detection():
    # A frozen camera feeds identical frames; read() must flag it after the
    # configured window. We fake VideoCapture at the manager level.
    cfg = dict(hgc.DEFAULT_CONFIG)
    cfg["freeze_reconnect_sec"] = 0.05
    m = cam.CameraManager(cfg)

    frozen = np.full((480, 640, 3), 100, np.uint8)

    class FakeCap:
        def read(self):
            return True, frozen.copy()

    m.cap = FakeCap()
    m.active_index = 0
    m.active_backend = 0

    ok1, _, _ = m.read()
    check("first frozen frame passes", ok1 is True)
    # second identical frame starts the freeze clock
    ok2, _, _ = m.read()
    check("second frozen frame passes (clock starts)", ok2 is True)
    # pretend the clock has been running longer than the freeze window
    import time
    m._same_since = time.time() - 1.0
    ok3, _, status3 = m.read()
    check("frozen stream detected", ok3 is False and "froze" in status3)

    # a changing picture must NOT trigger freeze detection
    m2 = cam.CameraManager(dict(cfg))
    frames = {"i": 0}

    class LiveCap:
        def read(self):
            frames["i"] += 1
            f = np.full((480, 640, 3), frames["i"] % 250, np.uint8)
            return True, f

    m2.cap = LiveCap()
    for _ in range(5):
        ok4, _, _ = m2.read()
    check("changing frames never freeze", ok4 is True)


def test_failed_reopen_releases_old_handle():
    """When the quick reopen fails, the OLD camera handle must be released
    first: single-connection Windows cameras block every retry otherwise."""
    if cam.cv2 is None:
        print("  skip failed-reopen test (no cv2)")
        return
    cfg = dict(hgc.DEFAULT_CONFIG)
    m = cam.CameraManager(cfg)
    released = {"old": False}

    class OldCap:
        def read(self):
            return False, None
        def release(self):
            released["old"] = True

    class FailCap:
        def __init__(self, *a, **k):
            pass
        def isOpened(self):
            return False
        def release(self):
            pass

    m.cap = OldCap()
    m.active_index, m.active_backend = 0, 0
    m._last_reconnect_attempt = -100.0  # force an immediate reconnect attempt
    orig = cam.cv2.VideoCapture
    cam.cv2.VideoCapture = lambda *a, **k: FailCap()
    try:
        for _ in range(15):
            m.read()
        check("old handle released after failed reopen", released["old"] is True)
        check("cap cleared after failed reopen", m.cap is None)
        # a cap-less read must RETRY the reopen on backoff, not give up
        m._last_reconnect_attempt = -100.0
        ok2, _, status2 = m.read()
        check("cap-less read keeps reconnecting", ok2 is False and "Reconnecting" in status2)
    finally:
        cam.cv2.VideoCapture = orig


def test_successful_reopen_swaps_handle():
    """A successful quick reopen replaces the handle and resets the backoff."""
    if cam.cv2 is None:
        print("  skip successful-reopen test (no cv2)")
        return
    cfg = dict(hgc.DEFAULT_CONFIG)
    m = cam.CameraManager(cfg)
    released = {"old": False}
    bright = np.full((480, 640, 3), 100, np.uint8)

    class OldCap:
        def read(self):
            return False, None
        def release(self):
            released["old"] = True

    class GoodCap:
        def isOpened(self):
            return True
        def set(self, *a):
            return True
        def read(self):
            return True, bright.copy()
        def release(self):
            pass

    m.cap = OldCap()
    m.active_index, m.active_backend = 0, 0
    m._reconnect_delay = 8.0
    orig = cam.cv2.VideoCapture
    cam.cv2.VideoCapture = lambda *a, **k: GoodCap()
    try:
        for _ in range(15):
            m.read()
        m.read()
        check("old handle released on failure path", released["old"] is True)
        check("new handle installed", isinstance(m.cap, GoodCap))
        check("backoff reset after success", m._reconnect_delay == 1.0)
        # stream reads again from the new handle
        ok2, frame2, _ = m.read()
        check("reads resume after reconnect", ok2 is True and frame2 is not None)
    finally:
        cam.cv2.VideoCapture = orig


def test_probe_plan_strict_ignores_different_last_camera():
    backends = cam.CameraManager(dict(hgc.DEFAULT_CONFIG))._backends()
    if not backends:
        print("  skip strict last-camera test (no cv2 / no camera backends)")
        return
    cfg = dict(hgc.DEFAULT_CONFIG)
    cfg["camera_index"] = 1
    cfg["camera_strict"] = True
    cfg["last_camera"] = {"index": 2, "backend": backends[0][0]}
    plan = cam.CameraManager(cfg)._probe_plan()
    check("strict mode never probes remembered different camera",
          bool(plan) and all(index == 1 for index, _, _ in plan))


def test_diagnostics_reports_grayscale_camera_as_skipped():
    import contextlib
    import io

    if cam.cv2 is None:
        print("  skip grayscale diagnostics test (OpenCV unavailable)")
        return

    class FakeCap:
        def isOpened(self):
            return True

        def read(self):
            return True, hgc.np.full((40, 40), 100, dtype=hgc.np.uint8)

        def get(self, prop):
            if prop == cam.cv2.CAP_PROP_FRAME_WIDTH:
                return 40
            if prop == cam.cv2.CAP_PROP_FRAME_HEIGHT:
                return 40
            return 0

        def release(self):
            pass

    original_indices = cam.CameraManager._indices
    original_backends = cam.CameraManager._backends
    original_capture = cam.cv2.VideoCapture
    original_report = cam._write_report
    try:
        cam.CameraManager._indices = lambda self: [0]
        cam.CameraManager._backends = lambda self: [(700, "Fake")]
        cam.cv2.VideoCapture = lambda index, backend: FakeCap()
        cam._write_report = lambda lines: None
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cam.diagnose_cameras(dict(hgc.DEFAULT_CONFIG))
        text = output.getvalue()
        check("grayscale-only camera is reported as skipped",
              "grayscale/IR" in text and "skipped by app" in text)
        check("diagnostics does not claim skipped camera works",
              result == 1 and "At least one camera works" not in text)
    finally:
        cam.CameraManager._indices = original_indices
        cam.CameraManager._backends = original_backends
        cam.cv2.VideoCapture = original_capture
        cam._write_report = original_report


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"{len(tests)} camera tests passed")


if __name__ == "__main__":
    main()


