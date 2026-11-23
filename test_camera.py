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
    cfg = dict(hgc.DEFAULT_CONFIG)
    cfg["last_camera"] = {"index": 2, "backend": cam.CameraManager(cfg)._backends()[0][0]}
    m = cam.CameraManager(cfg)
    plan = m._probe_plan()
    check("last working camera probed first",
          plan[0][0] == 2 and plan[0][1] == cfg["last_camera"]["backend"])
    check("no duplicate of the last-working pair",
          not any(p[0] == plan[0][0] and p[1] == plan[0][1] for p in plan[1:]))


def test_probe_plan_strict():
    cfg = dict(hgc.DEFAULT_CONFIG)
    cfg["camera_index"] = 1
    cfg["camera_strict"] = True
    m = cam.CameraManager(cfg)
    plan = m._probe_plan()
    check("strict mode only tries the chosen index",
          all(p[0] == 1 for p in plan))


def test_save_config_diff_only(tmp_path=None):
    path = hgc.CONFIG_PATH
    try:
        hgc.CONFIG_PATH = "/tmp/eidak-test-config.json"
        cfg = dict(hgc.DEFAULT_CONFIG)
        cfg["sensitivity"] = 2.0
        cfg["last_camera"] = {"index": 1, "backend": 700}
        hgc.save_config(cfg)
        with open(hgc.CONFIG_PATH, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        check("changed keys saved",
              saved.get("sensitivity") == 2.0 and saved.get("last_camera", {}).get("index") == 1)
        check("default keys not saved", "frame_width" not in saved and "pinch_ratio" not in saved)
        # round-trip: loading the diff over defaults reproduces the values
        cfg2 = hgc.load_config()
        check("round-trip sensitivity", cfg2["sensitivity"] == 2.0)
        check("round-trip defaults intact", cfg2["frame_width"] == hgc.DEFAULT_CONFIG["frame_width"])
        # empty diff removes nothing but writes {} when a file exists
        hgc.save_config(dict(hgc.DEFAULT_CONFIG))
        with open(hgc.CONFIG_PATH, "r", encoding="utf-8") as fh:
            check("all-default saves empty diff", json.load(fh) == {})
    finally:
        hgc.CONFIG_PATH = path
        if os.path.exists("/tmp/eidak-test-config.json"):
            os.remove("/tmp/eidak-test-config.json")


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


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"{len(tests)} camera tests passed")


if __name__ == "__main__":
    main()
