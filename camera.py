# -*- coding: utf-8 -*-
"""Camera management and diagnostics for Eidak.

Split out of hand_gesture_control.py (step 0, mechanical - no behavior change).
"""

from __future__ import annotations

import platform
import time

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - reported nicely at runtime
    cv2 = None


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
