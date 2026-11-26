#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless tests for Eidak's config validation (hand_gesture_control).

No camera, display or real config.json is needed: validation is pure logic
and load_config is pointed at a temporary file.

Run:  python test_config.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hand_gesture_control as hgc


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"  ok  {name}")


def validated(**overrides):
    cfg = dict(hgc.DEFAULT_CONFIG)
    cfg.update(overrides)
    return hgc.validate_config(cfg)


def test_wrong_type_falls_back():
    out = validated(sensitivity="fast")
    check("string sensitivity falls back", out["sensitivity"] == hgc.DEFAULT_CONFIG["sensitivity"])
    out = validated(show_landmarks="yes")
    check("string bool falls back", out["show_landmarks"] == hgc.DEFAULT_CONFIG["show_landmarks"])
    out = validated(media_window_allowlist="youtube")
    check("string allowlist falls back",
          out["media_window_allowlist"] == hgc.DEFAULT_CONFIG["media_window_allowlist"])
    out = validated(media_window_allowlist=["vlc", 3])
    check("allowlist with non-string falls back",
          out["media_window_allowlist"] == hgc.DEFAULT_CONFIG["media_window_allowlist"])
    out = validated(media_window_allowlist=[""])
    check("blank allowlist token falls back",
          out["media_window_allowlist"] == hgc.DEFAULT_CONFIG["media_window_allowlist"])
    out = validated(last_camera={"index": "front", "backend": 700})
    check("last_camera with string index falls back", out["last_camera"] is None)


def test_out_of_range_falls_back():
    out = validated(sensitivity=999)
    check("huge sensitivity falls back", out["sensitivity"] == hgc.DEFAULT_CONFIG["sensitivity"])
    out = validated(camera_index=-5)
    check("camera_index below -1 falls back", out["camera_index"] == -1)
    out = validated(detection_confidence=2.0)
    check("confidence above 1 falls back",
          out["detection_confidence"] == hgc.DEFAULT_CONFIG["detection_confidence"])
    out = validated(frame_width=10)
    check("tiny frame_width falls back", out["frame_width"] == hgc.DEFAULT_CONFIG["frame_width"])
    out = validated(control_margin=0.75)
    check("degenerate control margin falls back",
          out["control_margin"] == hgc.DEFAULT_CONFIG["control_margin"])
    out = validated(start_mode="cinema")
    check("unknown start_mode falls back", out["start_mode"] == hgc.DEFAULT_CONFIG["start_mode"])


def test_valid_custom_values_kept():
    out = validated(sensitivity=2.0, camera_index=2, start_mode="media",
                    show_landmarks=False, frame_width=1280,
                    media_window_allowlist=["vlc"], last_camera={"index": 1, "backend": 700})
    check("valid sensitivity kept", out["sensitivity"] == 2.0)
    check("valid camera_index kept", out["camera_index"] == 2)
    check("valid start_mode kept", out["start_mode"] == "media")
    check("valid bool kept", out["show_landmarks"] is False)
    check("valid frame_width kept", out["frame_width"] == 1280)
    check("valid allowlist kept", out["media_window_allowlist"] == ["vlc"])
    check("valid last_camera kept", out["last_camera"] == {"index": 1, "backend": 700})
    out = validated(media_window_allowlist=[])
    check("empty allowlist remains explicit opt-out", out["media_window_allowlist"] == [])
    out = validated()
    check("all defaults pass validation untouched", out == hgc.DEFAULT_CONFIG)


def test_load_config_files(tmpdir):
    path = hgc.CONFIG_PATH
    tmp = os.path.join(tmpdir, "eidak-test-config.json")
    try:
        hgc.CONFIG_PATH = tmp
        # valid file: custom values survive the round trip through load_config
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"sensitivity": 2.5, "camera_index": 1}, fh)
        cfg = hgc.load_config()
        check("load_config keeps valid file values",
              cfg["sensitivity"] == 2.5 and cfg["camera_index"] == 1)
        # invalid values in a real file are replaced, not trusted
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"sensitivity": "fast", "smoothing": 42}, fh)
        cfg = hgc.load_config()
        check("load_config replaces invalid file values",
              cfg["sensitivity"] == hgc.DEFAULT_CONFIG["sensitivity"]
              and cfg["smoothing"] == hgc.DEFAULT_CONFIG["smoothing"])
        # corrupt JSON: never crash, always the defaults
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        cfg = hgc.load_config()
        check("corrupt JSON falls back to defaults", cfg == hgc.DEFAULT_CONFIG)
        # missing file: defaults
        os.remove(tmp)
        check("missing file falls back to defaults", hgc.load_config() == hgc.DEFAULT_CONFIG)
    finally:
        hgc.CONFIG_PATH = path
        if os.path.exists(tmp):
            os.remove(tmp)


def test_cli_rejects_invalid_overrides():
    original_path = hgc.CONFIG_PATH
    original_run = hgc.run
    calls = []
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            hgc.CONFIG_PATH = os.path.join(tmpdir, "config.json")
            hgc.run = lambda cfg: calls.append(dict(cfg)) or 0
            invalid = [
                (["--camera", "-1"], "negative camera index rejected"),
                (["--camera", "17"], "camera index above range rejected"),
                (["--sensitivity", "0"], "zero sensitivity rejected"),
                (["--sensitivity", "11"], "excessive sensitivity rejected"),
                (["--sensitivity", "nan"], "NaN sensitivity rejected"),
            ]
            for argv, label in invalid:
                try:
                    hgc.main(argv)
                except SystemExit as exc:
                    check(label, exc.code == 2)
                else:
                    raise AssertionError(label)
            hgc.main(["--camera", "2", "--sensitivity", "2.0"])
            check("valid CLI overrides reach run",
                  calls[-1]["camera_index"] == 2 and calls[-1]["camera_strict"]
                  and calls[-1]["sensitivity"] == 2.0)
    finally:
        hgc.CONFIG_PATH = original_path
        hgc.run = original_run


def main():
    test_wrong_type_falls_back()
    test_out_of_range_falls_back()
    test_valid_custom_values_kept()
    with tempfile.TemporaryDirectory() as tmpdir:
        test_load_config_files(tmpdir)
    test_cli_rejects_invalid_overrides()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
