# -*- coding: utf-8 -*-
"""EXPERIMENTAL prototype — MediaPipe Tasks backend for Eidak.

*** This module is NOT wired into the app. Nothing imports it. ***

It wraps the new MediaPipe Tasks `HandLandmarker` API behind the exact
shape the existing gesture pipeline already consumes:

    legacy (mp.solutions.hands):
        results = hands.process(rgb)
        lm = [(p.x, p.y, p.z) for p in results.multi_hand_landmarks[0].landmark]

    this prototype:
        lm = backend.process(rgb, timestamp_ms)   # same list, or None

so `GesturePipeline.process(lm, now)` would not need to change.

Why this exists: the legacy `mp.solutions.hands` API is only available in
mediapipe==0.10.14, which caps the project at Python <= 3.12. The Tasks API
is the supported replacement in current MediaPipe releases.
See docs/MEDIAPIPE_MIGRATION.md for the full picture, including everything
that is NOT done yet (starting with: never tested with a real camera).

API signatures below were verified against the mediapipe 0.10.14 package
(the Tasks API already ships inside it):
  - mediapipe.tasks.python.vision.HandLandmarker.create_from_options(options)
  - vision.HandLandmarkerOptions(base_options, running_mode, num_hands,
        min_hand_detection_confidence, min_hand_presence_confidence,
        min_tracking_confidence, result_callback)
  - mediapipe.tasks.python.BaseOptions(model_asset_path=...)
  - landmarker.detect_for_video(mp.Image(ImageFormat.SRGB, data=rgb), timestamp_ms)
  - result.hand_landmarks -> per-hand list of NormalizedLandmark(x, y, z, ...)
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

Point = Tuple[float, float, float]
Landmarks = List[Point]

# The HandLandmarker model is a separate download (a .task file); it is NOT
# bundled with the mediapipe wheel. Default location: next to this file.
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")


class HandLandmarkerBackend:
    """Drop-in-shaped replacement for the legacy Hands object (prototype).

    Parameters mirror the legacy configuration keys Eidak already uses:
    `max_num_hands`, `detection_confidence`, `tracking_confidence`.
    The Tasks API adds `min_hand_presence_confidence`, which has no legacy
    equivalent; it defaults to the detection confidence.
    """

    def __init__(self, cfg: dict, model_path: str = DEFAULT_MODEL_PATH):
        if not os.path.exists(model_path):
            raise RuntimeError(
                "HandLandmarker model file not found: "
                f"{model_path}\nDownload hand_landmarker.task from the "
                "MediaPipe model repository and place it next to "
                "hand_gesture_control.py (see docs/MEDIAPIPE_MIGRATION.md).")
        # Imported here, not at module level, so importing this module can
        # never break the existing app on a machine without mediapipe.
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.HandLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=int(cfg.get("max_num_hands", 1)),
            min_hand_detection_confidence=float(cfg.get("detection_confidence", 0.65)),
            min_hand_presence_confidence=float(cfg.get("detection_confidence", 0.65)),
            min_tracking_confidence=float(cfg.get("tracking_confidence", 0.55)),
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

    def process(self, rgb_frame, timestamp_ms: int) -> Optional[Landmarks]:
        """Return 21 (x, y, z) points for the first hand, or None.

        `rgb_frame` is an RGB numpy array (same array the legacy code passes
        to `hands.process`). Timestamps must strictly increase in VIDEO
        mode; a repeated or backwards timestamp is bumped by 1 ms instead
        of raising, matching the legacy API's forgiving behavior.
        """
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        if not result.hand_landmarks:
            return None
        return [(p.x, p.y, p.z) for p in result.hand_landmarks[0]]

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
